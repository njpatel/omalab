# Offscreen video and input

Use an existing, task-owned lab. Set `lab` to its unique name. Start at the
final size/scale before preparing transient UI; do not restart or change scale
while recording. No visible viewer is required.

## Video

Requires installed `wf-recorder` and an available encoder such as `libx264`.
Record inside the lab, then export the finalized file through stdout. Arbitrary
host paths are not mounted by `exec`.

```sh
mkdir -p artifacts
omalab exec -n "$lab" timeout --preserve-status --signal=INT --kill-after=5s 10s \
  sh -c 'exec wf-recorder -o LAB -f "$HOME/lab-demo.mp4" -r 30 -x yuv420p \
    -c libx264 -p preset=ultrafast -D'
omalab exec -n "$lab" sh -c 'cat "$HOME/lab-demo.mp4"' > artifacts/lab-demo.mp4
```

Use the agent's background process facility for the recording when input needs
to run concurrently. Keep the finite timeout. SIGINT lets the recorder finalize
its MP4; wait for it to exit before exporting or tearing down the lab. Inspect
actual decoded frames and media metadata, not merely file size.

This recipe is video-only. Do not enable microphone, webcam or host-audio capture
without explicit authorization. Do not substitute the host desktop recorder.
Missing encoder/tool prerequisites are not permission to install system packages
or expose host devices.

## Pointer and keyboard

`omalab input` talks to a persistent input controller inside the lab. The
controller holds a WayVNC connection that keeps the headless virtual pointer and
keyboard available even when `show` has never been called. Events use the lab's
private Unix socket, not kernel-global input devices.

```sh
omalab input -n "$lab" move 400 200
omalab input -n "$lab" click 400 200
omalab input -n "$lab" type 'test input'
omalab input -n "$lab" key Ctrl+a
omalab input -n "$lab" key Return
```

- Coordinates are **physical pixels in the original screenshot/framebuffer**.
  At 2x, logical `(200,100)` is framebuffer `(400,200)`. Do not use coordinates
  from a downscaled preview without accounting for its resize.
- `click` is a left-button press and release at the point. It does not require
  separate down/up commands or a manual pointer-frame workaround.
- `type` takes one quoted Unicode text argument and uses `wtype` inside the
  namespace, while the persistent VNC connection keeps the seat available.
  Focus the intended field inside the child first.
- `key` accepts a single ASCII character or Return/Enter, Escape, Tab, BackSpace,
  Delete, Left/Up/Right/Down, Home, End, PageUp, PageDown or Space. Prefix chords
  with Ctrl, Shift, Alt or Super, separated by `+`.
- Out-of-bounds coordinates and unknown commands are errors; they do not target
  another desktop. Rejected input does not close the lab.
- Scrolling, dragging and arbitrary held-button sequences are not implemented.
  Do not invent flags or fall back to host-global input for them.
- Prefer plugin IPC when it can establish the desired state more reliably than
  coordinate-dependent UI interaction.

Input and geometry-changing CLI operations are serialized, so a scale-changing
shot restores its geometry before the next input command runs. For screenshots
of transient UI, start the lab at the requested scale, drive the state and call
`shot` without a scale override.

## Optional lower-level tools

Tools such as `wtype` can still run through `omalab exec` against the child.
However, the tested first-class `input` API handles virtual-seat lifetime and
button frames. Historical bare `send_key_state` button events lacked a pointer
frame, and an entirely headless seat had no devices without a VNC connection.
Do not revive those assumptions or compensate by showing a host window.

Even help-looking arguments can be interpreted as typing by an input injector.
Read its manual rather than trying unknown invocations on the host.

## Safety and completion

- Use `omalab input -n "$lab"` for input and `omalab exec -n "$lab"` for recorders.
- Never substitute `ydotool`, `/dev/uinput`, host `xdotool`, desktop-global
  automation or an implicit host `hyprctl` command.
- `show` still requires explicit permission for this task. Screenshots, video
  and input do not require a visible viewer.
- Verify the resulting UI through screenshots or the plugin's observable IPC;
  a successful input-tool exit does not establish the intended application state.
- Review artifacts for sensitive data before publishing them. Offscreen content
  can still contain credentials explicitly configured in the lab.
- Finalize recording, preserve artifacts, stop task-owned helpers, then remove
  only the task-owned lab.

## Verification record

The integrated CLI drove a real Qt text field and button without a visible
viewer: text changed, the click counter increased and hover remained active
between commands. A finalized 1280x800 H.264 recording at approximately 30 fps
showed the interactions and was exported from private HOME through `exec`.
An out-of-bounds input request failed while the controller remained usable.
A measured child movement left host cursor samples unchanged. These are bounded
observations, not a VM-grade security guarantee.
