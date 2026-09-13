#!/usr/bin/env python3
"""Display one lab's private VNC socket using the native GTK window backend."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys


def session_environment(environ):
    """Preserve explicit display choices; recover only absent session endpoints."""
    allowed = ("WAYLAND_DISPLAY", "DISPLAY", "XDG_RUNTIME_DIR", "XAUTHORITY")
    selected = {key: environ[key] for key in allowed if environ.get(key)}
    source = "caller"
    if not selected.get("WAYLAND_DISPLAY") and not selected.get("DISPLAY"):
        try:
            reply = subprocess.run(
                ["systemctl", "--user", "show-environment", "--output=json"],
                capture_output=True, text=True, timeout=5, check=True,
            )
            manager = json.loads(reply.stdout)
            if not isinstance(manager, dict):
                raise ValueError("unexpected user-manager environment response")
            for key in allowed:
                value = manager.get(key)
                if key not in selected and isinstance(value, str) and value:
                    selected[key] = value
            source = "user-manager"
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            raise ValueError("no graphical endpoint in caller; cannot recover it from the user session manager") from error
    if selected.get("WAYLAND_DISPLAY"):
        display = Path(selected["WAYLAND_DISPLAY"])
        if not display.is_absolute():
            runtime = selected.get("XDG_RUNTIME_DIR")
            if not runtime:
                raise ValueError("relative WAYLAND_DISPLAY needs the graphical session's XDG_RUNTIME_DIR")
            display = Path(runtime) / display
        try:
            info = display.stat()
        except OSError as error:
            raise ValueError(f"Wayland endpoint is unavailable: {display}; run show from the current desktop session") from error
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError(f"Wayland endpoint is not an owned Unix socket: {display}")
        selected["WAYLAND_DISPLAY"] = str(display)
        selected["backend"] = "wayland"
    elif selected.get("DISPLAY"):
        selected["backend"] = "x11"
        if not selected.get("XAUTHORITY"):
            authority = Path(environ.get("HOME", "")) / ".Xauthority"
            if authority.is_file():
                selected["XAUTHORITY"] = str(authority)
    else:
        raise ValueError("no graphical session endpoint is available; headless labs remain usable with shot/ipc/input")
    selected["source"] = source
    return selected


def load_gtk():
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        gi.require_version("GtkVnc", "2.0")
        gi.require_version("GLibUnix", "2.0")
        from gi.repository import Gdk, GLib, GLibUnix, Gtk, GtkVnc
    except (ImportError, ValueError) as error:
        raise ValueError("native viewer dependencies unavailable; run omalab-setup --viewer") from error
    return Gdk, GLib, GLibUnix, Gtk, GtkVnc


def run_viewer(args):
    Gdk, GLib, GLibUnix, Gtk, GtkVnc = load_gtk()
    initialized, _ = Gtk.init_check([])
    if not initialized:
        endpoint = os.environ.get("WAYLAND_DISPLAY") if os.environ.get("GDK_BACKEND") == "wayland" else os.environ.get("DISPLAY")
        raise ValueError(f"cannot connect to {os.environ.get('GDK_BACKEND', 'graphical')} endpoint {endpoint!r}; no host repair attempted")
    GLib.set_prgname("omalab-viewer")
    GLib.set_application_name("omalab")
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(5)
    connection.connect(args.socket)
    connection.settimeout(None)

    view = GtkVnc.Display()
    view.set_shared_flag(True)
    view.set_keyboard_grab(False)
    view.set_grab_keys(GtkVnc.GrabSequence.new([]))
    view.set_pointer_grab(False)
    view.set_force_size(False)
    view.set_scaling(True)
    view.set_keep_aspect_ratio(True)
    view.set_lossy_encoding(False)
    view.set_depth(GtkVnc.DisplayDepthColor.FULL)
    view.set_allow_resize(False)
    # No clipboard, audio, bell, host launch, fullscreen or remote-resize hooks.
    window = Gtk.Window(title=f"omalab: {args.name}")
    window.set_default_size(args.width, args.height)
    window.set_focus_on_map(False)
    window.add(view)
    result = {"status": 0, "ready": False, "frame": False, "mapped": False, "closing": False}

    def stop(status=0, message=None):
        if result["closing"]:
            return False
        result["closing"] = True
        result["status"] = status
        if message:
            print(f"omalab viewer: {message}", file=sys.stderr, flush=True)
        view.close()
        window.destroy()
        Gtk.main_quit()
        return False

    def initialized(*_):
        if not result["closing"]:
            window.show_all()

    def first_frame(*_):
        result["frame"] = True
        publish_ready()

    def mapped(*_):
        result["mapped"] = True
        publish_ready()

    def publish_ready():
        if result["ready"] or result["closing"] or not (result["frame"] and result["mapped"]):
            return
        result["ready"] = True
        info = {"pid": os.getpid(), "backend": os.environ.get("GDK_BACKEND"),
                "displayType": Gdk.Display.get_default().__gtype__.name,
                "framebufferWidth": view.get_width(), "framebufferHeight": view.get_height()}
        destination = Path(args.ready_file)
        temporary = destination.with_name(destination.name + ".next")
        temporary.write_text(json.dumps(info) + "\n")
        temporary.replace(destination)
        print("Native viewer ready: " + json.dumps(info), flush=True)

    def disconnected(*_):
        return stop(0 if result["closing"] else 1, None if result["closing"] else "lab viewer connection closed")

    def timed_out():
        if result["ready"]:
            return False
        return stop(1, "timed out waiting for the lab's first VNC frame")

    window.connect("delete-event", lambda *_: stop())
    window.connect("map-event", mapped)
    view.connect("vnc-initialized", initialized)
    view.get_connection().connect("vnc-framebuffer-update", first_frame)
    view.connect("vnc-error", lambda _view, message: stop(1, str(message)))
    view.connect("vnc-disconnected", disconnected)
    view.connect("vnc-auth-failure", lambda _view, message: stop(1, f"unexpected VNC authentication failure: {message}"))
    view.connect("vnc-auth-unsupported", lambda *_: stop(1, "unsupported authentication on private viewer socket"))
    view.connect("vnc-auth-credential", lambda *_: stop(1, "private viewer socket unexpectedly requested credentials"))
    GLib.timeout_add_seconds(12, timed_out)
    GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, stop)
    GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, stop)
    descriptor = connection.detach()
    if not view.open_fd(descriptor):
        os.close(descriptor)
        raise ValueError("native VNC widget refused the lab socket")
    Gtk.main()
    return result["status"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--environment", action="store_true")
    parser.add_argument("--socket")
    parser.add_argument("--name")
    parser.add_argument("--ready-file")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
    args = parser.parse_args()
    if args.environment:
        print(json.dumps(session_environment(os.environ)))
        return 0
    if args.check:
        load_gtk()  # Import only. No display connection or window.
        return 0
    if not args.socket or not args.name or not args.ready_file:
        parser.error("--socket, --name and --ready-file are required")
    if not (200 <= args.width <= 8192 and 200 <= args.height <= 8192):
        parser.error("invalid viewer window size")
    return run_viewer(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        print(f"omalab viewer: {error}", file=sys.stderr)
        sys.exit(1)
