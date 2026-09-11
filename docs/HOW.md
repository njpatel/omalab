# Omalab engineering reference

This document records the implementation contracts behind omalab and the traps
that shaped them. It describes the current `bin/omalab`, not a general recipe
for nested desktops and not a security boundary.

**Important:** the current host-output backend has caused desktop disruption.
The historical snapshots below are narrow observations, not proof that adding
an offscreen monitor is harmless. Bars, monitor-management services and pointer
layout can still react. The isolated-parent experiment below does not connect
to the host display and is separate from the existing `bin/omalab` implementation.

## Process and pre-map boundary

A lab is a nested Hyprland compositor running as a Wayland client of the host.
The child must never map visibly before the host has installed its placement
rules.

Startup uses the following gate:

1. The host declares the lab's monitor and workspace rules before creating its
   named headless output.
2. Host `hl.exec_cmd(command, rules)` registers rules bound to the spawned
   process's PID and `HL_EXEC_RULE_TOKEN`.
3. The internal compositor launcher confirms that it has the lab environment
   and a rule token, then waits for `map.allowed`.
4. Only after the host call returns does `up` create `map.allowed`, allowing the
   launcher to `exec Hyprland`.

This avoids a broad rule for Aquamarine's shared class/title and closes the
race in which the nested compositor could map or take focus before placement.
The child PID, class, address and monitor are verified before the address is
recorded or later used.

The nested compositor must not inherit the host
`HYPRLAND_INSTANCE_SIGNATURE`. Its own signature and display are reported by a
command run from the child's `hyprland.start` callback; choosing the newest
instance directory is unsafe when labs start concurrently.

## Host compositor allowlist

Host mutations are intentionally narrow and are always sent to the captured
host instance, never to an implicit Hyprland instance:

- Read monitor, client, active-workspace and cursor state to calculate placement
  and verify the exact lab window and input isolation. `hyprctl -j cursorpos`
  is a read-only observation; input dispatch must target only the child.
- Declare one named workspace rule and one monitor rule for
  `OMALAB-<name>`.
- Create or remove that exact named headless output.
- Launch the nested compositor with PID/token-bound initial rules.
- Apply fullscreen transitions to the verified `address:<lab-window>`.
- For an explicit `show`, float, resize, center and silently move only that
  address to the currently active workspace. `hide` silently returns the same
  address to the lab workspace.

Startup, capture and teardown do not dispatch focus, change the active
workspace, select a workspace, reload host configuration, write desktop
configuration, use `hyprctl keyword`, alter a physical-output rule, or install
host layer rules. `show` is the sole operation intended to make a lab visible;
it still does not explicitly focus the window or switch the user's workspace.

Headless outputs are placed wholly to the left of the leftmost existing output,
with additional clearance. Positive placement is unsafe: with auto-positioned
physical displays, adding a far-right output can shift global physical-output
coordinates. Screenshot overrides may move only the lab output farther left as
it grows.

The lab window is parked fullscreen on its own output. Static fullscreen rules
were insufficient by themselves, so capture reasserts an addressed fullscreen
state transition. No action follows a class selector, current focus or current
window.

## Child Hyprland configuration

The generated child config is Lua. It declares a single output whose physical
mode is `logical size × scale`, while its logical position remains `0x0`.
XWayland, animations, the logo and splash are disabled.

The nested launch intentionally triggers Hyprland's standalone watchdog
warning, so the config sets only:

```lua
hl.config({ misc = { disable_watchdog_warning = true } })
```

It does not enable general error suppression. `debug.suppress_errors` remains
false, and `hyprctl configerrors` remains the authoritative check for actual
child configuration errors. A legacy `.conf` file or keyword-based child
configuration would be a stale implementation path.

## Private HOME, XDG state and sockets

The shell runs against the real Omarchy and Quickshell code, but with private
writable state:

- `HOME`
- `XDG_CONFIG_HOME`
- `XDG_STATE_HOME`
- `XDG_CACHE_HOME`
- `XDG_DATA_HOME`
- `XDG_RUNTIME_DIR`
- `TMPDIR`

The parent Wayland display is converted to an absolute socket path before the
child receives it. The child compositor, clients, D-Bus helpers and Quickshell
then use the private runtime directory.

Unix-domain socket paths are limited to 107 bytes on Linux. Hyprland creates
several long socket names below `XDG_RUNTIME_DIR`; truncation can make two
sockets collide while some IPC still appears functional. Omalab therefore
creates a short, owned alias such as `$XDG_RUNTIME_DIR/omalab/.<slot>` pointing
to the lab's private runtime directory, passes the short spelling to all child
processes, and rejects a runtime root that cannot fit the longest expected
socket name. Teardown removes the alias.

## Shell, plugins and services

`omarchy-shell` is used for IPC; Quickshell itself is launched with the real
Omarchy shell path. File watching and reload popups are disabled because omalab
owns deliberate shell restarts.

The lab starts from Omarchy's stock `shell.json`. A plugin checkout is never
copied: its real directory is symlinked into the private
`.config/omarchy/plugins/<id>`. The manifest is the contract:

- `id` must be a valid plugin id.
- Entries in `plugins` are objects of the form `{ "id": "..." }`, not strings.
- A `bar-widget` is inserted into its manifest's `barWidget.defaultSection`,
  which must be `left`, `center` or `right`; non-bar plugins are enabled without
  a bar-layout entry.
- `--plus` resolves another installed plugin or first-party Omarchy manifest
  and stages it through the same path.

Because these are real plugins, edits are visible after `restart`, and their
processes, filesystem access and side effects are real too.

Machine-control services are disabled in the generated shell configuration:
idle, lock, battery power profiles, polkit and night light. Omalab also refuses
to stage those ids directly. An idle timeout of zero is not a safe substitute;
in the shell it can mean immediate lock.

Stock notifications are disabled by default so a service plugin can own
`org.freedesktop.Notifications` on the private session bus. They can be added
explicitly with `--plus omarchy.notifications`. Omalab does not fake service
ownership or provide arbitrary service replacement: plugins must use their
real manifests and contend for names on the bus they were deliberately given.

Themes are staged with Omarchy's template tool under the private HOME. The
host-mutating theme setter is not used. `--theme mine` shares only the host's
current theme and background through symlinks that omalab only reads; it does
not import plugin configuration, credential files or application state. These
are ordinary symlinks, not filesystem-enforced read-only mounts.

## D-Bus, Qt and portals

The default is a private session bus, allowing a lab service to own a name that
the host desktop already owns. `--shared-bus` is an explicit trust decision and
passes the host session-bus address instead.

A private session bus is not enough to make desktop integration safe. Omalab:

- unsets inherited `QT_QPA_PLATFORMTHEME`, avoiding GTK portal and
  accessibility initialization against the incomplete private desktop;
- sets `QT_NO_XDG_DESKTOP_PORTAL=1` on a private bus;
- sets it to `0` only for an explicit shared bus;
- leaves shell logging unfiltered so real plugin errors remain visible.

This policy prevents inappropriate private-bus portal integration; it is not a
D-Bus filter. The system bus is not isolated.

## Private PipeWire

Every lab gets a real private PipeWire server, selected through the lab runtime
socket even when `--shared-bus` is used. Its configuration provides only the
native protocol, client-node, metadata and access modules. It starts no ALSA or
hardware factories, Pulse server, WirePlumber or other session manager.

The result satisfies stock PipeWire clients without attaching lab audio
controls to the user's devices. Empty device and node lists are expected.
Using the host PipeWire socket merely to silence a client error would violate
this boundary.

## Screenshots and restoration

`shot` requires the verified child window to be parked on its lab output and
the nested compositor to expose exactly one child output. It connects `grim`
directly to the child's Wayland socket. Capturing the parent headless output is
not equivalent: parent notification or layer surfaces can appear in the image.

Logical size and scale determine the physical PNG size. A size-only override
reloads the child monitor declaration and waits for shell relayout without
restarting Quickshell. A scale change must restart the lab shell at the capture
scale to rebuild Qt's glyph caches at native resolution; after capture it
restarts again at the original scale. Those restarts reset transient panels,
in-memory plugin state and other non-persisted service state.

Capture uses a temporary destination and publishes the PNG atomically only
after geometry restoration. The exit trap restores the original child Lua
monitor line, child geometry, host lab-output geometry, fullscreen state and
stamp metadata after success or a catchable failure. A failed restoration is
reported rather than hidden.

## Provenance stamp

Unless `--no-stamp` is used, omalab stages `stamp/` as a real service plugin.
It is a click-through, non-exclusive, non-focusable `WlrLayer.Background`
`PanelWindow` anchored 32 logical pixels from the bottom-right. Its width is at
most 340 logical pixels and its content uses the theme accent at 42% opacity.
The facts record plugin id, commit/dirty state, theme, logical size, scale and
UTC date.

The wordmark is shape geometry, not block-font text: seven bitmap rows are
converted into non-overlapping horizontal rectangle runs. Cell size and inset
are snapped through `Screen.devicePixelRatio`; this avoids font fallback,
glyph advance, ink-bound and translucent-overlap artifacts. Metadata uses Qt's
scalable text renderer.

Geometry changes are sent to the service over its own IPC. The panel pulses
Omarchy's `ScreenMoveRemap` so a resized background-layer surface remaps above
the wallpaper while remaining on the child background layer. No host layer or
window rule is involved.

## Video and child input

Optional recording and input tools run through `omalab exec`, preserving the
full child runtime/display environment. `wf-recorder` can capture the child's
output directly; a bounded timeout sends SIGINT to finalize the video before
teardown. Video-only capture does not enable microphone or host-audio recording.

The verified Hyprland cursor dispatcher updates that compositor's own pointer
manager. `wtype` uses its Wayland virtual-keyboard protocol. Mouse-button
`send_key_state` dispatches have an important protocol detail in 0.56.2: they
send button events without a pointer frame. Flushing each press/release with
child pointer motion made a Qt test control receive the intended click; bare
button commands alone were insufficient. The [automation recipes](../skills/omalab/automation.md)
include the tested sequence and coordinate scaling rules.

Never substitute host dispatches or kernel-global injection tools. Environment
variables do not sandbox or redirect host-wide injection through tools such as
`ydotool` or `/dev/uinput`. Prefer plugin IPC for directly establishing state.

## Teardown and failure state

Normal teardown stops the shell, private PipeWire server, private bus and child
compositor; removes only the named lab output; disables the exact named
workspace and output rules; removes the short runtime alias; then deletes the
lab directory. PID start times are recorded so a recycled PID is not killed by
mistake.

Failed startup stops owned processes and removes the created output, but retains
the lab directory and logs for diagnosis until an explicit `down`. The host Lua
workspace handle is disabled and discarded. The monitor declaration is changed
to `disabled=true` rather than erased through a host reload, so Hyprland may
retain an inert disabled rule in runtime state; no physical output is targeted.

`down` destroys private runtime state. A later `up` is a fresh shell environment,
not a resume. Use unique names for concurrent or automated work, and preserve
logs or screenshots before cleanup.

## Security and isolation limits

Omalab is for trusted plugin development, not untrusted-code execution. There
are no user, mount, PID or network namespaces. A plugin and `omalab exec`
command run as the user and can reach the user's filesystem, network, `/proc`
and system bus. With `--shared-bus`, they can also reach host session-bus
services. Credential files are not copied, but arbitrary environment variables
and agent sockets are inherited. A plugin can use those credentials or seek
them elsewhere in the host filesystem.

The boundary protects ordinary desktop state from accidental shell-plugin
experimentation. It does not provide containment against malicious code.

## Validation record

The following behavior was measured during implementation; this is a compact
record of those runs, not a claim of fresh verification or future-version
compatibility:

- Hyprland 0.56.2 and Quickshell 0.3.1 started multiple concurrent labs with
  distinct child signatures, private runtimes and negative-coordinate outputs.
- A parked lab remained responsive after 605 seconds without polling or a
  keepalive; IPC and a newly connected screenshot client both succeeded.
- The private session bus allowed the lab shell to own the notification service
  without changing the host owner. Explicit shared-bus startup was also
  exercised separately.
- The private PipeWire core was the recorded lab process and exposed no Device
  or Node objects.
- Direct-child captures of a 1280×800 logical desktop were inspected at 1×
  and 2× (1280×800 and 2560×1600 PNGs), plus fractional scale. Native-scale
  text was not an enlargement of the scale-1 glyph cache.
- Size-only capture kept the shell PID. Scale-changing capture restarted the
  shell. A forced destination failure returned nonzero while restoring the
  byte-identical generated Lua config and a responsive shell.
- Explicit show/hide left the active workspace, focus, physical monitor
  geometry and pre-existing client geometry unchanged in the measured
  before/after snapshots.
- Stamp captures at integer and fractional scale showed snapped rectangle edges
  and correct bottom-right remapping after resize.
- Child status reported the Lua config provider and Wayland backend; the narrow
  watchdog option was set, general suppression was unset, and `configerrors`
  was empty. Corrected raw shell logs retained no baseline Qt/portal/PipeWire
  plumbing warnings while remaining unfiltered.
- Final teardown left no recorded lab processes, named lab outputs, short
  runtime aliases or lab directories, and measured host shell/theme/background
  content remained unchanged.

- A disposable Qt input probe received virtual-keyboard text, pointer hover and
  a framed mouse click. The click incremented its counter once while host
  cursor samples immediately before/after the measured sequence matched.
  A finalized 1280x800 H.264 video at approximately 30 fps showed the actual
  typing and click state changes, with no audio track.

For user-facing commands and supported options, use `bin/omalab --help` and the
project README. This file explains why the implementation is conservative.

## Isolated-parent experiment

The reproducible [experiment runner](../experiments/run-headless.sh) starts a
real Omarchy shell without creating any output on the user's compositor.
It is a proof runner, not a drop-in backend release or an implementation of
the normal CLI's `show`/`hide` lifecycle. Run `--help` before using it.

### What was tried

1. **Standalone Hyprland 0.56.2:** started inside a Bubblewrap boundary with no
   host display socket, DRM card devices, input devices or system/login bus.
   Aquamarine 0.14.0's headless backend returns no DRM allocator; without a DRM
   or Wayland backend, startup failed with `no allocator available`. An ordinary
   environment-variable-only standalone headless launch is not proven here.
2. **Headless Weston 15.0.1:** started successfully using the GPU render node
   only, but Aquamarine requested `wl_compositor` version 6 while the parent
   advertised version 5, terminating the client connection.
3. **Headless Cage 0.3.1 / wlroots 0.20:** likewise started without a host
   connection, but Aquamarine requested `xdg_wm_base` version 6 while this parent
   advertised version 5.
4. **Cage with a temporary corrected Aquamarine library:** succeeded after
   negotiating `min(advertised, supported)` for those two globals. This was a
   separate build loaded only inside the experiment, not a replacement for
   the machine's installed library.

The tested compatibility patch is preserved in
[`experiments/aquamarine-parent-versions.patch`](../experiments/aquamarine-parent-versions.patch).
It applies to Aquamarine v0.14.0, commit
`a79fb21b2e2a82dd061a6d071802bcf38bd5c383`, ABI 13. This is experimental evidence,
not an assertion that an upstream release already contains the fix.

### Boundary and launch shape

```text
host desktop — no lab output, no lab Wayland connection

Bubblewrap namespace
  headless Cage (GPU render node only)
    Hyprland (LAB memory output belongs to this child)
      real Omarchy shell + read-only plugin checkout
      private D-Bus and PipeWire
      grim / wf-recorder / child input
```

The boundary uses new user, mount, PID, IPC and network namespaces; clears the
environment; provides private `/run`, `/tmp` and `/dev`; mounts system code and
the plugin read-only; and exposes only a specifically validated
`/dev/dri/renderD*` node. It does **not** mount host Wayland/X11 sockets, host
HOME, the system bus, `/dev/input` or DRM `/dev/dri/card*` nodes. Kernel/GPU
resources are still shared: this is not a VM or a GPU denial-of-service boundary.

Cage is explicitly restricted to `WLR_BACKENDS=headless`, with GLES rendering
through that render node. The isolated Hyprland uses Cage to acquire a buffer
allocator, then creates `LAB` on its own headless backend. No host `hyprctl`
mutation is performed. Shell IPC works normally when the services share the
runner's PID namespace. Earlier separate-namespace probes required explicit
Quickshell instance selection; the runner avoids that mismatch.

The retained runner produces a 1280x800 screenshot, plugin registry, layer and
compositor metadata, and logs. An optional command runs in the same isolated
environment before exit; all its descendants terminate with the PID namespace.
Only the explicitly supplied artifact directory remains writable/persistent.
The initial screenshot waits for asynchronous theme loading and must still be
inspected; shell `ping` alone is not a rendering-ready assertion.

### Reproducing the experiment

Prerequisites: Bubblewrap with working user namespaces, Cage 0.3.1 with wlroots
0.20, the verified Omarchy stack, an accessible GPU render node, and a build of
Aquamarine 0.14.0 with the patch above. Building the library needs its normal
CMake/compiler/development dependencies. The runner downloads or installs
nothing and does not alter the system library search path.

From the omalab checkout, with the dependencies already available:

```sh
work=$(mktemp -d)
git clone --depth 1 --branch v0.14.0 https://github.com/hyprwm/aquamarine.git "$work/aquamarine"
git -C "$work/aquamarine" apply "$PWD/experiments/aquamarine-parent-versions.patch"
cmake -S "$work/aquamarine" -B "$work/aquamarine/build" -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build "$work/aquamarine/build" --target aquamarine -j 4
AQUAMARINE_LIBDIR="$work/aquamarine/build" \
  ./experiments/run-headless.sh ./stamp "$work/artifacts"
```

`CAGE_BIN` can select a separately prepared Cage executable; `RENDER_NODE` can
select another accessible render node. `OMARCHY_PATH` must identify the installed
Omarchy source. These are experimental dependencies, not silently added runtime
requirements of the existing CLI. The investigation unpacked signature-verified
packages under temporary storage and changed no installed packages.

To exercise your plugin instead, pass its directory. It appears read-only at
`/plugin` inside the namespace, and artifacts are available at `/artifacts`.
For example, add `bash -c 'omarchy-shell shell ping'` as the optional command.
No host graphical environment is required by this runner; it deliberately does
not support the old backend's desktop integrations or live editable mounts.

### Measured capabilities and limitations

- Real `omarchy-bar`, wallpaper and bundled service rendered; plugin registry
  reported the service enabled. Inspected 1280x800 and native 2560x1600 PNGs.
- Direct child `grim` and a finalized 1280x800 H.264 recording worked without
  a host display output. Native-scale changes affected the child only.
- A WayVNC 0.10.1 server bound only a private Unix socket. A non-visible RFB
  client received the actual framebuffer and delivered typing and clicks to a
  Qt test UI. The text and click counter changed; host cursor/workspace samples
  before and after that sequence matched. No TCP listener or host viewer window
  was opened. This establishes a viable viewer transport, not a finished `show`.
- A truly headless seat initially has no physical pointer/keyboard. The old
  dispatcher-only click recipe did not suffice; persistent virtual devices
  created by WayVNC delivered correct input. This distinction must be retained
  in the eventual backend's agent input API.
- The system bus and network are unavailable by design. Stock Bluetooth,
  NetworkManager and UPower components log unavailable-service diagnostics;
  those are explicit experimental integration limits, not hidden or filtered.
- The complete one-namespace runner returned success, preserved artifacts and
  removed its own temporary state. This proof does not claim live plugin edits,
  shared host services, a production viewer lifecycle or the ordinary CLI's
  complete option set. Do not substitute it silently for `omalab up` yet.
- With no connected viewer and no polling for 605 seconds, shell IPC returned
  `ok` and a fresh 2560x1600 `grim` capture succeeded. The resulting image was
  opened and inspected. The isolated parent did not need a visible host window
  or a periodic keepalive.
- The one-namespace runner also executed an explicit failing command: it
  returned status 1, preserved logs/capture artifacts and removed its temporary
  namespace state rather than leaving the child desktop running.
- All experiment services were stopped afterward. No experiment Bubblewrap
  process namespace remained; the host output names, dimensions, positions,
  scales and disabled flags matched the baseline. No host output was added,
  no host mutation was dispatched, and no system package/library was installed
  or replaced. The experiment runner passed ShellCheck v0.11.0 and Bash syntax
  validation; its retained screenshots were visually inspected.
