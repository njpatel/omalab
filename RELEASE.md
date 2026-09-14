omalab now runs its desktop inside an isolated headless session, without adding an output to your host compositor. This release also adds native Wayland viewing, persistent offscreen input and bounded video recording.

## What's new

- **Headless sessions without host display outputs.** Bubblewrap and headless Cage host Hyprland and the real Omarchy shell. `up` and `shot` need the installed Omarchy stack and a GPU render node, but no active host desktop. Plugin checkouts remain live, read-only mounts.
- **Private runtime setup.** `omalab-setup` builds the pinned Aquamarine 0.14.0 compatibility patch and supplies missing Cage, WayVNC and viewer libraries privately. It does not replace system libraries or install system packages.
- **Native viewer.** `show` uses GTK-VNC on Wayland, with explicit X11 support, and waits for a mapped window and its first framebuffer. When display variables are absent, it recovers only display endpoints from the user manager. `hide` closes only that lab's viewer; clipboard synchronisation, remote resizing and system-key grabs remain disabled.
- **Offscreen pointer and keyboard input.** `omalab input` supports move, left-click, Unicode text and key chords through the lab's private virtual seat, without a visible viewer. Coordinates use the original framebuffer pixels, including at high density.
- **Bounded recordings.** `omalab record` produces a validated, video-only H.264 MP4. Recordings default to 10 seconds, accept 1–300 seconds and are limited to one managed recorder per lab. Restart and geometry changes are blocked during recording; files are published only after successful finalisation and validation.
- **Sharper provenance stamps.** The wordmark uses pixel-aligned rectangles rather than font glyphs, with density-aware text rendering.
- **Automation guidance.** New CI documentation, a runnable smoke helper, an opt-in GitHub Actions example and an agent skill cover isolated sessions, screenshots, input, recording and scoped cleanup. Contribution-review guidance is now documented.

## Updating from v0.1.0

- Run `omalab-setup` before using the new backend. Setup targets Arch Linux x86_64 with Aquamarine 0.14.0 / ABI 13 and its development dependencies. The documented compatibility target is Omarchy 4.0.2, Hyprland 0.56.2, Quickshell 0.3.1 and PipeWire 1.6.8.
- Save artifacts and shut down old labs with the version that created them before updating. Recreate labs afterwards: `restart` reloads the shell, not the compositor or generated environment. Old-format records are refused, not migrated; do not delete them blindly while old processes may remain.
- If the core private runtime already exists, `omalab-setup --viewer` can add native-viewer dependencies without rebuilding the core runtime or stopping retained labs. PyGObject must already be installed.
- Network access remains isolated by default. `--network` explicitly shares host networking; `--shared-bus` separately exposes the requested session-bus socket. Only `show` opens a host window. There is no fallback to creating a host display output.
- Scale-changing screenshots restart the lab shell and reset transient UI state. Start at the final scale for stateful captures. Raw recorders launched through `exec` bypass the managed recording safeguards.
- This remains a development environment for trusted code, not a security sandbox. Hosted CI runners need the desktop/GPU stack provisioned; no Docker image or X11 compositor backend is included.

## Contributors

Neil Jagdish Patel (@njpatel) implemented the runtime, viewer, input, recording, stamp and documentation changes. @pateltron handled the contribution-review guidance in [#1](https://github.com/njpatel/omalab/pull/1).

**Full changelog:** https://github.com/njpatel/omalab/compare/v0.1.0...v0.2.0
