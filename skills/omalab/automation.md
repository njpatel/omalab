# Offscreen video and input

These recipes operate inside an existing, task-owned lab. Set `lab` to its
unique name. Start at the desired size and scale before opening transient UI;
do not restart or change scale while recording.

This is not a new `omalab record` or `omalab click` API. It uses optional tools
through `omalab exec`, which supplies the complete child session environment.
A display name alone is insufficient: different labs can all use `wayland-1`
under different private runtime directories.

## Video

Requires `wf-recorder` and an available encoder. The following bounded,
video-only recipe was exercised with the installed wlroots recorder and
`libx264`:

```sh
output=$(omalab exec -n "$lab" hyprctl -j monitors |
  jq -er 'if length == 1 then .[0].name else error("choose a child output explicitly") end')
mkdir -p artifacts
video="$PWD/artifacts/lab-demo.mp4"
omalab exec -n "$lab" timeout --preserve-status --signal=INT --kill-after=5s 10s \
  wf-recorder -o "$output" -f "$video" -r 30 -x yuv420p \
  -c libx264 -p preset=ultrafast -D
```

- Run the recorder with the agent's background/process facility when input
  commands need to run concurrently. Keep the finite timeout.
- SIGINT lets the recorder finalize the MP4. Wait for it to exit before opening
  the file or tearing down the lab. Do not kill all recorder processes by name.
- Inspect decoded video frames and media metadata, not just file existence.
- The recipe does not request audio. Do not add microphone, webcam or host-audio
  capture without explicit authorization and verified device/session scoping.
- Do not use the desktop's global recording wrapper: record the child output
  directly so parent notifications and other desktop content stay out.
- If tools or the required protocol/encoder are missing, report the prerequisite;
  do not install packages or switch to a host capture without permission.

## Coordinates and pointer movement

Hyprland cursor coordinates are logical child coordinates. A point at
`(400, 400)` in a native 2x PNG corresponds to `(200, 200)` in the child. Image
previews can also be downscaled; derive coordinates from the original image,
not an assumed preview size.

```sh
omalab exec -n "$lab" hyprctl -j cursorpos
omalab exec -n "$lab" hyprctl dispatch 'hl.dsp.cursor.move({x=200, y=200})'
```

Choose coordinates from the actual lab UI. Moving the child's pointer does not
require showing its host window.

## Mouse buttons on the verified Hyprland version

Hyprland 0.56.2 accepts `mouse:272` for the left button in `send_key_state`.
However, that action sends button events without a `wl_pointer.frame`. Bare
press/release calls can therefore queue without the intended Qt click.

The tested sequence below flushes each state with child pointer motion. Pick an
interior point of the target, with room for the one-logical-pixel movement:

```sh
omalab exec -n "$lab" hyprctl dispatch 'hl.dsp.cursor.move({x=200, y=200})'
omalab exec -n "$lab" hyprctl eval \
  'hl.dispatch(hl.dsp.send_key_state({mods="", key="mouse:272", state="down"})); hl.dispatch(hl.dsp.cursor.move({x=201, y=200}))'
omalab exec -n "$lab" hyprctl eval \
  'hl.dispatch(hl.dsp.send_key_state({mods="", key="mouse:272", state="up"})); hl.dispatch(hl.dsp.cursor.move({x=200, y=200}))'
```

Always send the matching release, including on a failed intermediate action.
Verify the resulting UI state through a screenshot or plugin IPC; an `ok`
response alone does not establish that the application handled the click.
These dispatch details are version-specific. Scrolling and drag sequences are
not covered by this validation; do not assume they work from a successful move.

## Keyboard input

Requires `wtype` and the child's virtual-keyboard protocol. Focus the intended
field inside the lab first, then type through its Wayland connection:

```sh
omalab exec -n "$lab" wtype -- 'test input'
omalab exec -n "$lab" wtype -k Return
```

Use the installed `wtype` manual for key/modifier syntax. Even a help-looking
argument to an input-injection tool may be interpreted as input: do not invoke
it against the host to experiment.

## Safety and verification

- Every recording/input command must go through `omalab exec -n "$lab"`.
- Never substitute `ydotool`, `/dev/uinput`, host `xdotool`, a global desktop
  automation tool, or an implicit host `hyprctl` call. A scratch HOME does not
  contain kernel-global input injection.
- Prefer the plugin's stable IPC over coordinate-dependent UI automation.
- Review captures for sensitive plugin data before publishing them. Being
  offscreen does not make data safe to upload.
- Finish the recorder, preserve artifacts, stop task-owned helper applications,
  then remove only the task-owned lab.

A disposable Qt probe was used to verify a real text field, hover state and
click counter, along with a finalized 1280x800 H.264 video at approximately
30 fps without audio. A measured child click increased the counter by one
while read-only host cursor samples immediately before and after were equal.
This is a bounded validation record, not a security sandbox guarantee.
