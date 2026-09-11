#!/usr/bin/env python3
"""Send input only to a validated lab's private WayVNC Unix socket."""
import json
import socket
import struct
import subprocess
import sys
import time

KEYS = {"Return": 0xFF0D, "Enter": 0xFF0D, "Escape": 0xFF1B, "Tab": 0xFF09,
        "BackSpace": 0xFF08, "Delete": 0xFFFF, "Left": 0xFF51, "Up": 0xFF52,
        "Right": 0xFF53, "Down": 0xFF54, "Home": 0xFF50, "End": 0xFF57,
        "PageUp": 0xFF55, "PageDown": 0xFF56, "Space": 0x20}
MODIFIERS = {"Ctrl": 0xFFE3, "Shift": 0xFFE1, "Alt": 0xFFE9, "Super": 0xFFEB}


class Client:
    def __init__(self, path):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(10)
        self.socket.connect(path)
        if self.receive(12) != b"RFB 003.008\n":
            raise RuntimeError("unsupported viewer protocol version")
        self.socket.sendall(b"RFB 003.008\n")
        count = self.receive(1)[0]
        if not count or 1 not in self.receive(count):
            raise RuntimeError("private viewer socket does not offer local authentication")
        self.socket.sendall(b"\x01")
        if self.receive(4) != b"\0\0\0\0":
            raise RuntimeError("private viewer rejected the connection")
        self.socket.sendall(b"\x01")  # Share without disconnecting a visible viewer.
        info = self.receive(24)
        self.width, self.height = struct.unpack(">HH", info[:4])
        self.discard(struct.unpack(">I", info[20:24])[0], 1 << 20)
        if not (0 < self.width <= 16384 and 0 < self.height <= 16384):
            raise RuntimeError("invalid viewer dimensions")
        # Wait for an actual frame so the server's virtual seat is initialized.
        pixel_format = struct.pack(">BBBBHHHBBB3x", 32, 24, 0, 1, 255, 255, 255, 16, 8, 0)
        self.socket.sendall(b"\0\0\0\0" + pixel_format)
        self.socket.sendall(struct.pack(">BBHi", 2, 0, 1, 0))  # Raw encoding only.
        self.socket.sendall(struct.pack(">BBHHHH", 3, 0, 0, 0, 1, 1))
        while True:
            message_type = self.receive(1)[0]
            if message_type == 2:  # Bell.
                continue
            if message_type == 3:  # Ignore clipboard; never apply it to the host.
                header = self.receive(7)
                self.discard(struct.unpack(">I", header[3:])[0], 1 << 20)
                continue
            if message_type != 0:
                raise RuntimeError("unexpected viewer initialization message")
            header = self.receive(3)
            rectangles = struct.unpack(">H", header[1:])[0]
            for _ in range(rectangles):
                x, y, width, height, encoding = struct.unpack(">HHHHi", self.receive(12))
                if encoding != 0 or x + width > self.width or y + height > self.height:
                    raise RuntimeError("invalid viewer framebuffer rectangle")
                self.discard(width * height * 4, self.width * self.height * 4)
            break

    def receive(self, length):
        data = bytearray()
        while len(data) < length:
            block = self.socket.recv(length - len(data))
            if not block:
                raise RuntimeError("viewer connection closed")
            data.extend(block)
        return bytes(data)

    def discard(self, length, limit):
        if length > limit:
            raise RuntimeError("oversized viewer response")
        while length:
            block = self.socket.recv(min(length, 65536))
            if not block:
                raise RuntimeError("viewer connection closed")
            length -= len(block)

    def pointer(self, x, y, buttons=0):
        self.socket.sendall(struct.pack(">BBHH", 5, buttons, x, y))
        time.sleep(0.06)

    def key(self, keysym, pressed):
        self.socket.sendall(struct.pack(">BBHI", 4, int(pressed), 0, keysym))
        time.sleep(0.01)

    def tap(self, keysym):
        try:
            self.key(keysym, True)
        finally:
            self.key(keysym, False)


def execute(client, command):
    if not isinstance(command, list) or not command or not all(isinstance(value, str) for value in command):
        raise ValueError("input command must be an array of strings")
    operation, *args = command
    if operation in ("move", "click"):
        if len(args) != 2:
            raise ValueError("move/click requires framebuffer pixel coordinates X Y")
        x, y = map(int, args)
        # The first VNC handshake can precede the first native-size frame.
        # Validate screenshot coordinates against the live child mode instead.
        result = subprocess.run(["hyprctl", "-j", "monitors"], capture_output=True, text=True, timeout=5)
        if result.returncode:
            raise ValueError("cannot read child output geometry")
        output = next((item for item in json.loads(result.stdout) if item["name"] == "LAB"), None)
        if output is None or not (0 <= x < output["width"] and 0 <= y < output["height"]):
            raise ValueError("pointer is outside the lab screenshot")
        client.pointer(x, y)
        if operation == "click":
            try:
                client.pointer(x, y, 1)
            finally:
                client.pointer(x, y, 0)
    elif operation == "type":
        if len(args) != 1:
            raise ValueError("type requires one text argument")
        try:
            result = subprocess.run(["wtype", "--", args[0]], capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired as error:
            raise ValueError("child virtual keyboard timed out") from error
        if result.returncode:
            raise ValueError(result.stderr.strip() or "child virtual keyboard rejected text")
    elif operation == "key":
        if len(args) != 1:
            raise ValueError("key requires one key or modifier chord")
        *modifiers, name = args[0].split("+")
        if any(modifier not in MODIFIERS for modifier in modifiers):
            raise ValueError("modifiers are Ctrl, Shift, Alt and Super")
        if name not in KEYS and (len(name) != 1 or not name.isascii()):
            raise ValueError("key expects a named key or ASCII character; use type for Unicode text")
        pressed = []
        try:
            for modifier in modifiers:
                key = MODIFIERS[modifier]
                client.key(key, True)
                pressed.append(key)
            client.tap(KEYS[name] if name in KEYS else ord(name))
        finally:
            for key in reversed(pressed):
                client.key(key, False)
    else:
        raise ValueError("input operation must be move, click, type or key")
    time.sleep(0.1)


def packet(connection):
    data = bytearray()
    while b"\n" not in data:
        block = connection.recv(4096)
        if not block:
            raise ValueError("incomplete input request")
        data.extend(block)
        if len(data) > 65536:
            raise ValueError("input request exceeds 64 KiB")
    return json.loads(data.split(b"\n", 1)[0])


def serve(path, viewer):
    client = Client(viewer)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(path)
        server.listen(8)
        while True:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(30)
                try:
                    command = packet(connection)
                except OSError:
                    continue
                except ValueError as error:
                    response = {"ok": False, "error": str(error)}
                else:
                    try:
                        execute(client, command)
                        response = {"ok": True}
                    except ValueError as error:
                        response = {"ok": False, "error": str(error)}
                try:
                    connection.sendall(json.dumps(response).encode() + b"\n")
                except OSError:
                    pass  # A cancelled caller must not kill the lab's seat.


def main():
    if len(sys.argv) < 4:
        raise ValueError("expected serve INPUT_SOCKET VIEWER_SOCKET or request INPUT_SOCKET COMMAND")
    mode, path, *args = sys.argv[1:]
    if mode == "serve" and len(args) == 1:
        serve(path, args[0])
    elif mode == "request" and args:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(120)
            connection.connect(path)
            request = json.dumps(args).encode() + b"\n"
            if len(request) > 65536:
                raise ValueError("input request exceeds 64 KiB")
            connection.sendall(request)
            response = packet(connection)
            if not response.get("ok"):
                raise ValueError(response.get("error", "input request failed"))
    else:
        raise ValueError("invalid input helper invocation")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        print(f"omalab input: {error}", file=sys.stderr)
        sys.exit(1)
