# Omalab engineering reference

This document records the contracts behind the default `bin/omalab` backend,
not a general nested-desktop recipe. The public CLI remains the entry point;
`bin/omalab-setup` prepares its private runtime separately.

## Process and display boundary

```text
host: omalab CLI                         show only: ordinary VNC viewer
          |                                         |
          |                                  private UNIX socket
          v                                         |
Bubblewrap namespace                                |
  headless Cage (GPU render node only)               |
    Hyprland (private LAB headless output) -- WayVNC --+
      real Omarchy shell + read-only live plugin mounts
      private D-Bus and PipeWire
      grim / wf-recorder / child input
```

`up` needs no active host desktop. Cage runs with its headless backend and GLES
renderer on a GPU render node. Hyprland uses Cage's Wayland backend to obtain a
buffer allocator and renders the shell on its own `LAB` headless output. The
host Wayland/X11 socket is not mounted. No lab monitor, workspace rule, window
rule, keyword, focus call or other mutation is sent to the host compositor.

The Bubblewrap keeper owns the lab process lifetime. Commands enter the same
namespaces through `nsenter`; Quickshell IPC and helper processes therefore
share the child PID namespace rather than guessing another process's instance.
The child reports its own display and Hyprland instance; the implementation
must not inherit a host signature or select the newest compositor directory.

Only `show` launches a viewer in the caller's current desktop. It connects to
WayVNC through a private UNIX socket, not a TCP listener. Clipboard transfer,
remote resize and system-key grabs are disabled. The window is an ordinary
client subject to the user's window-manager policy, not a specially dispatched
host window. `hide` closes only that lab's recorded viewer; the desktop and
private VNC server remain running. Visible inspection requires explicit user
permission. The integrated viewer was tested on an offscreen X server without
opening a window on the user's real desktop; placement/focus follow normal
window-manager policy. TigerVNC needs `DISPLAY` (X11/XWayland) only for `show`.

## Private runtime and compatibility patch

Run `omalab-setup` before first use. Its default destination is
`${XDG_DATA_HOME:-$HOME/.local/share}/omalab-runtime`; `OMALAB_RUNTIME_DIR` can
override it for both setup and the CLI. The runtime contains:

- `lib/libaquamarine.so.13`: patched Aquamarine v0.14.0;
- `tools/usr/bin/{cage,wayvnc,vncviewer}` when the system lacks those tools,
  with their privately supplied library dependencies;
- `manifest.json` with `format: 1` and `aquamarineVersion: "0.14.0"`.

The CLI resolves private tools before `PATH` and mounts the runtime read-only
at `/runtime`. Only the isolated Cage/Hyprland process receives the compatibility
library path; other lab clients use private tool libraries as needed. The
ordinary host viewer gets only its tool-library directory, never patched
Aquamarine. Setup changes no system loader configuration, installs no system
packages and requires no sudo. There is no compilation on `up`.

Setup targets Arch Linux x86_64 with installed Aquamarine 0.14.0 / ABI 13 and
its development dependencies. It needs Git, curl, CMake, Ninja, a C++23 compiler,
pkg-config, binutils, jq, flock and standard utilities. Missing Cage, WayVNC or
TigerVNC tools are obtained from the configured pacman repositories using the
local sync database and verified package signatures; this additionally needs
pacman-key and bsdtar. Setup does not refresh that database. See
`omalab-setup --help` for the full prerequisite check. A valid existing runtime
is reused; do not remove or replace one while labs use it.

The compatibility target is Hyprland 0.56.2, Quickshell 0.3.1 and Aquamarine
0.14.0 (ABI 13). The patch in
[`support/aquamarine-parent-versions.patch`](../support/aquamarine-parent-versions.patch)
applies to upstream commit `a79fb21b2e2a82dd061a6d071802bcf38bd5c383`.
It caps the `wl_compositor` and `xdg_wm_base` bind versions at
`min(advertised, supported)` instead of requesting version 6 unconditionally.
This is a local compatibility patch, not a claim that an upstream release
already includes the fix.

### Why an isolated parent is necessary

The predecessor backend added a virtual output to the host compositor.
Desktop disruption was reported despite offscreen placement: monitor services,
bars and pointer layout can react to any added output. Negative coordinates and
narrow before/after checks were not a sufficient boundary. That path is no
longer normal usage and must not be used as a fallback.

The isolated-parent investigation established these technical constraints:

1. Direct standalone Hyprland 0.56.2 inside Bubblewrap, with no host display,
   DRM card, input devices or system/login bus, failed with
   `no allocator available`. Aquamarine 0.14.0's headless backend supplied no
   DRM allocator; environment variables alone did not solve it.
2. Headless Weston 15.0.1 started on a render node, but advertised
   `wl_compositor` version 5 while Aquamarine requested 6.
3. Headless Cage 0.3.1 / wlroots 0.20 also started without a host connection,
   but advertised `xdg_wm_base` version 5 while Aquamarine requested 6.
4. A separately built Aquamarine library with the two version caps allowed
   Hyprland and the real Omarchy shell to run under Cage. No system library
   was replaced.

These facts explain the private patched runtime. Manual experiment builds are
not an additional normal-user setup path; use `omalab-setup` and the CLI.

## Namespace, filesystem and environment contract

The boundary uses user, mount, PID and IPC namespaces and, by default, a private
network namespace. HOME, configuration, state, cache, data, runtime and temporary
storage are private. The environment is reconstructed deliberately rather than
passing arbitrary inherited variables, tokens or agent sockets to the child.
Selected installed system code is read-only; host HOME and arbitrary host
artifact directories are not mounted. Private `/proc`, `/run`, `/tmp` and `/dev`
do not expose the host process tree or runtime sockets.

Only a validated GPU `/dev/dri/renderD*` node is exposed: no DRM card nodes,
`/dev/input`, `/dev/uinput`, host display socket or system D-Bus socket. The
kernel and GPU remain shared, so this is not a VM or a GPU denial-of-service
boundary. Run trusted code only.

Plugins are live read-only binds, not snapshots. Editing the checkout from the
host changes the code visible inside the lab; `restart` deliberately reloads
the shell. The lab cannot write back through the plugin mount. Symlinks in a
checkout do not grant access to arbitrary host targets. `--plus` plugins and
the bundled provenance stamp follow the same staging contract.

`exec` enters the running lab's namespaces with its environment and starts in
**scratch HOME**, not the caller's host working directory. External file paths
are not made available just because they appear in command arguments. Write
fixtures in private storage or explicitly stream input/output through the CLI:

```sh
omalab exec -n dev sh -c 'cat > "$HOME/fixture.json"' < fixture.json
omalab exec -n dev sh -c 'cat "$HOME/result.json"' > artifacts/result.json
omalab log -n dev > artifacts/shell.log
```

The outer shell performs those redirections. `shot` independently accepts a
host destination and streams child capture bytes out without binding that
host directory into the namespace.

## Child configuration, shell and plugins

The child Hyprland config uses the Lua API and declares logical geometry at
`0x0`, with a physical mode of `logical size × scale`. XWayland, animations,
logo and splash are disabled. The standalone watchdog warning alone is disabled;
general configuration errors remain visible through `hyprctl configerrors`.

Quickshell runs the installed Omarchy shell; `omarchy-shell` provides IPC.
File watching and reload popups are disabled because omalab owns deliberate
shell restarts. The lab starts from stock `shell.json`, not the user's plugin
configuration. Plugin manifests supply valid ids and bar-widget default
sections (`left`, `center` or `right`); service plugins need no bar slot.
Additional installed plugins are selected explicitly with `--plus`.

Idle, lock, battery power profiles, polkit and night light are disabled and
cannot be staged directly. An idle timeout of zero is not a safe substitute:
it can mean immediate lock. Stock notifications are off so a service plugin
can own `org.freedesktop.Notifications` on the private bus; enable the stock
service explicitly with `--plus omarchy.notifications` when needed.

Themes are copied into a private snapshot and generated through Omarchy's
template tooling, never its host-mutating theme setter. `--theme mine` snapshots
only the current theme/background; later host theme changes require a new lab.

## Network, D-Bus, portals and audio

Default networking is isolated. Host loopback and external services are not
available. `--network` explicitly shares the host network namespace, including
loopback; it is not a per-service firewall. Require authorization before using
it for integration with host or external services.

The session bus is private by default. `--shared-bus` deliberately weakens that
boundary by mounting only the explicitly requested filesystem session-bus
socket. It is not permission to search other users' sockets or guess a bus
address, and it does not expose the system bus. Network and session-bus sharing
are independent options.

Qt portal integration is disabled on the private bus and enabled only for an
explicit shared bus. Inherited platform-theme settings do not leak into the
private environment. Shell logs remain raw: absent NetworkManager, Bluetooth
and UPower system services can produce expected unavailable-service diagnostics.
This is an integration limit, not grounds to suppress QML errors, TypeErrors,
binding loops or other real plugin failures.

Each lab runs real private PipeWire, including with `--shared-bus`. It starts
no ALSA/hardware discovery, Pulse server, WirePlumber or session manager. Empty
device and node lists are expected. Connecting host audio merely to silence a
warning would violate the intended boundary.

## Screenshots and provenance

`shot` captures the child's `LAB` output with `grim`, not Cage's framebuffer or
the host desktop. Logical size and scale determine physical PNG dimensions.
A size-only override waits for relayout without restarting Quickshell. A scale
change restarts the shell to rebuild native-resolution Qt glyph caches, then
restarts it again while restoring the original geometry. Transient panels and
in-memory plugin state reset. For stateful captures, start at the final scale
before driving the UI.

Capture streams to a temporary host destination and publishes atomically only
after restoration. Catchable failures restore child geometry, generated config
and stamp metadata; a failed restoration is reported. No host output geometry
or fullscreen state is involved. Closing a viewer before scale changes avoids
showing its transient shell restart; capture itself remains child-only.

The optional stamp is a real background-layer service plugin. It records plugin
id, commit/dirty state, theme, logical size, scale and UTC date; commit/date
refresh at shell startup. Its click-through non-focusable panel sits at the
bottom-right and updates geometry over IPC. Rectangle-based wordmark geometry
snaps through the screen's device pixel ratio. `--no-stamp` removes provenance,
not time-dependent content elsewhere in the shell.

## Video and child input

Optional `wf-recorder` and input tools run through `exec` in the same child
session. Record to private storage, finalize with SIGINT, then export through
stdout before teardown. The [automation recipes](../skills/omalab/automation.md)
cover that workflow and coordinate scaling. Video-only recording is not
permission for microphone, webcam or host-audio capture.

A headless seat has no physical pointer or keyboard. `support/input.py` holds
a persistent RFB connection to the private WayVNC socket, keeping virtual
devices available without a visible viewer. The controller serves bounded JSON
commands through a separate lab-only Unix socket; `omalab input` validates the
selected namespace before connecting. Move/click coordinates are physical
framebuffer pixels. Named keys/chords use RFB; Unicode text uses `wtype` inside
the namespace so characters absent from the VNC keyboard layout are not lost.
The initial WayVNC handshake can report a smaller size before its first captured
frame. Pointer bounds therefore come from the live child monitor mode, not that
cached handshake. A native 3840x2160@2 capture exercised a far-edge input point
and rejection immediately outside the screenshot; no coordinate downscaling is
applied to the RFB input events.

The controller requests only a one-pixel initialization frame, not a full-screen
transfer for every input action. Clicks and key chords pair releases, invalid
coordinates are rejected, and a cancelled requester does not kill the virtual
seat. Scrolling/drags are not implemented. Historical dispatcher-only recipes
on an empty headless seat must not be treated as equivalent.

Never substitute global input injectors, `/dev/uinput`, host `xdotool` or host
Hyprland dispatch. Prefer stable plugin IPC when available. No host focus or
workspace manipulation is needed to repair child-session input.

## State, ownership and teardown

Each named lab stores `meta.json` (`format: 2`), `env`, `pids`,
`supervisor-info.json` and available logs under the user's omalab runtime root.
Logs include `parent.log`, `supervisor.log`, `shell.log`, `pipewire.log`,
`input.log`, `bus.log`, `theme.log`, `vnc.log` and `viewer.log` as stages are reached.
PID start times distinguish owned processes from recycled PIDs; namespace and
viewer ownership must be checked before entering or terminating them.

Teardown asks the inner supervisor to stop its services, then terminates the
verified keeper if needed; killing the PID-namespace init removes all remaining
descendants, including commands entered through `exec`. Parent-death protection
also covers abrupt outer-supervisor death. Only the named viewer/namespace is
stopped before state removal. Failed startup retains diagnostics until `down`.
Old-format records are refused rather than automatically migrated or treated
as new-backend ownership evidence. Do not erase old records blindly while
legacy processes may still be running.

`down` is destruction, not suspend/resume. Preserve requested logs, videos,
screenshots and fixtures first. Use unique names for concurrent tasks and
never use `down --all` for shared-runner cleanup. SIGKILL, power loss or kernel
failure can interrupt normal cleanup; inspect retained state before reuse.

## Validation record

These are bounded **historical isolated-parent experiments**, not fresh proof
of the integrated CLI, setup command, CI job or visible viewer:

- Cage with the private Aquamarine patch rendered the real Omarchy bar,
  wallpaper and bundled service. 1280×800 and native 2560×1600 PNGs were inspected.
- Direct-child `grim` capture and a finalized 1280×800 H.264 recording worked
  without a host display output.
- WayVNC 0.10.1 bound a private UNIX socket. A non-visible RFB client received
  the framebuffer and changed a Qt test UI's text and click counter using
  persistent virtual devices. No TCP listener or viewer window was opened;
  measured host cursor/workspace samples matched before and after.
- With no connected viewer or polling for 605 seconds, shell IPC returned `ok`
  and a fresh 2560×1600 capture succeeded and was inspected.
- The one-namespace proof runner handled success and an explicit failing child
  command, preserving artifacts and removing its temporary namespace state.
  No host output was added and no system package/library was installed or replaced.

### Integrated CLI verification

The normal CLI was exercised after replacing the host-output backend:

- `omalab-setup` fetched the pinned source, verified signed tool packages,
  built the private compatibility library and published the runtime. Repeating
  setup reused it without downloads/builds. No system package or library changed.
- `up`, `ipc`, namespace `exec`, `restart`, `ls`, 1x/2x/size-only `shot` and
  scoped `down` ran against the real Omarchy shell. Screenshot PNGs and their
  native dimensions were inspected. A real bar-widget checkout and a notification
  service checkout also loaded; the latter received and rendered a private-bus
  notification. Public fixtures remain generic; no production credentials were copied.
- Five concurrent isolated labs kept distinct state and services. The host
  output identities and physical geometry remained unchanged; no host output
  or compositor mutation was used.
- Host edits to a disposable plugin source changed its actual IPC revision
  after `restart`. Writing back from inside its mount failed with a read-only
  filesystem error. A sentinel environment variable was absent, along with
  host HOME, display sockets, system bus and physical input/card devices.
- Default network isolation rejected a host-loopback fixture. `--network`
  permitted that exact fixture without exposing display sockets. The shared-bus
  option was tested against an independent caller-supplied bus: inside/outside
  bus IDs matched, with only that socket mounted. No personal session service
  was needed for that verification.
- `show` opened one real TigerVNC window on a separate offscreen X server.
  Repeated show did not duplicate it, its rendered contents were inspected,
  and `hide` removed only that window while shell IPC continued working.
  No unapproved window was opened on the user's actual desktop. The ordinary
  viewer follows the target desktop's placement/focus policy.
- `input` drove a real Qt field/button without a viewer: text, a Ctrl+A chord,
  Unicode text, hover and clicks were observed. Out-of-bounds input and a
  cancelled requester did not kill the controller. A measured input movement
  left host cursor samples unchanged.
- A 1280x800 H.264 recording at approximately 30 fps captured real input and
  was exported from private HOME through `exec`. A 605-second untouched lab
  still answered IPC and produced a fresh screenshot; the foreground `exec`
  wrapper returned status zero. Explicit child exit statuses propagate intact.
- A failed scaled screenshot restored byte-identical child Lua configuration,
  the original geometry and a working input controller. Abrupt SIGKILL of an
  owned outer supervisor killed its namespace keeper and descendants. Normal
  teardown explicitly stops the child compositor before the parent.
- The updated CI helper passed locally, preserving registry data, native-scale
  screenshots and logs. An actual artifact-write failure returned nonzero,
  retained diagnostics and still removed its own lab. Remote GitHub job
  deployment is not claimed.
- All task-owned lab namespaces, viewers, test servers and display fixtures
  were removed. Host output geometry matched the initial baseline. ShellCheck
  and Bash syntax validation passed for the CLI, setup and smoke helper;
  the Python input helper's syntax was validated without generated repository files.
