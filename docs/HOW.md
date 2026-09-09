# How omalab isolates, and what was learned proving it

Initial findings from a hand probe on 2026-09-09 (Hyprland 0.56.2, Omarchy
shell from /usr/share/omarchy, Intel iGPU, one 5120x2880@2 output), followed by
implementation source contracts and runtime proofs. Corrections are explicit.

## Nested Hyprland

- `Hyprland --config <file>` inside a Wayland session picks the Wayland
  backend automatically (aquamarine: "Connected to a wayland compositor:
  Hyprland") and appears as a normal toplevel, class `aquamarine`, title
  `aquamarine - WAYLAND-1`.
- **Unset `HYPRLAND_INSTANCE_SIGNATURE`** in its environment. With the parent's
  signature inherited, the child tries to lock the parent's `wayland-1` and
  dies silently ("unable to lock lockfile ... maybe another compositor is
  running"). With it unset, it takes the next free name (`wayland-2`).
- The child is launched asynchronously by the host's PID-bound executor, not
  `start-hyprland`. Its Lua config sets `misc.disable_watchdog_warning=true`,
  the supported standalone-startup warning control on this build. General
  `debug.suppress_errors` remains false; configuration errors are not hidden.
- Discover signature and display from a command the child `exec`s, not the
  newest global instance directory (which races concurrent labs). The runtime
  implementation captures the child's environment from a `hyprland.start`
  Lua event callback via `hl.exec_cmd`.
  Under a private runtime directory its display can be `wayland-1` again;
  the host display is passed as an absolute socket path.
- Output inside is `WAYLAND-1`. **Corrected release:** generate
  `hyprland.lua` with `hl.monitor({output=..., mode=..., position=..., scale=...})`
  and `hl.config(...)`; no legacy `.conf` file or keyword path remains.
  1280x800 logical pixels at scale 2 needs a 2560x1600 mode. For screenshots,
  update the first monitor declaration and reload only the child, then restore
  that declaration afterward. This preserves the proven relayout behavior.
- The child disables logo, splash, XWayland, animations and the watchdog-startup
  warning. The earlier claims that `.conf` was preferable and warning banners
  would harmlessly expire were wrong for product screenshots; Neil's external
  verification caught them. Lua removes the deprecation warning at its source.
- **Idle requirement proved for the implemented backend:** the hand probe
  hung after roughly a minute while offscreen. With the lab mapped on its
  headless output, IPC and a new `grim` Wayland client both succeeded after
  605 seconds untouched (step 1 proof below). No watchdog, VFR workaround or
  periodic keepalive was needed. This does not root-cause the old probe hang.

## The host side

- **Safety correction before implementation:** creating a headless output and
  moving an already-mapped child there is not a safe startup sequence. The
  child can appear or take focus before the move. A lab must have offscreen
  placement and no-initial-focus rules installed **before** its first map;
  do not launch it if those prerequisites cannot be established. The probe
  did not prove this startup guarantee.
- The proposed host headless-output operations are
  `hyprctl output create headless <name>` and an output-specific
  `hl.monitor({output="<name>", mode="WxH@60", position="<negative x>x0", scale=1})`.
  These target an output, not a window. Neil explicitly authorized a narrow
  exception on 2026-09-09: omalab-owned headless output lifecycle operations
  and read-only host discovery are allowed. Physical-output configuration,
  visible windows before `show`, focus changes, workspace switching, and host
  keywords remain forbidden. No real desktop config files may be modified.
  `hyprctl -j monitors all`, `hyprctl -j activeworkspace`, and
  `hyprctl -j clients` are permitted read-only discovery/verification calls;
  they do not dispatch actions or change compositor state.
- Omarchy's `default/hypr/helpers.lua` implements `o.window` through
  `hl.window_rule`; its `apps/webcam-overlay.lua` uses `no_initial_focus`.
  The current [window-rule documentation](https://wiki.hypr.land/Configuring/Basics/Window-Rules/)
  distinguishes initial placement effects from later window moves. This is
  source evidence for the required approach, not a runtime proof of safe lab
  startup. No host commands were run for this correction.
- **Never** toggle special workspaces, change the active workspace, or run
  `hyprctl keyword` on the host to make a screenshot work. That bounces the
  user's desktop. It happened during the probe and is the reason this file
  exists.
- Dispatchers on this Hyprland are Lua: `hl.dsp.window.float/resize/move/center`,
  `hl.dsp.workspace.toggle_special("name")` (positional string), `hl.dsp.exec_cmd`.
  Names in `/usr/share/omarchy/default/hypr/bindings/*.lua` are the reference.
  `hyprctl -j clients` `at`/`size` are logical (post-scale) coordinates; so is
  `grim -g`.
- Product screenshots now capture directly from the child's Wayland socket.
  Capturing the host's headless output can include host notification overlays,
  even over a fullscreen lab window. Direct child `grim` excludes those layers
  without changing host notifications, focus, or layer rules.

## The shell side

- The shell launcher runs `quickshell -n -p $OMARCHY_PATH/shell`; the
  `omarchy-shell` command itself is only an IPC wrapper. Quickshell reads
  `Quickshell.env("HOME")` for `~/.config/omarchy/shell.json` and
  `~/.config/omarchy/plugins/`, and `$XDG_STATE_HOME/omarchy/current/{theme,background}`
  for colours and wallpaper. So the lab is: `HOME`, `XDG_CONFIG_HOME`,
  `XDG_STATE_HOME`, `XDG_CACHE_HOME`, `XDG_DATA_HOME` and a short private
  `XDG_RUNTIME_DIR`, plus the child's display and instance signature. Leave
  `OMARCHY_PATH` alone: the real shell code, `Commons`, `Ui`, first-party
  plugins.
- With that env and a `shell.json` copied from
  `$OMARCHY_PATH/config/omarchy/shell.json` (stock layout) plus
  `plugins: [{id: "<plugin id>"}]` and the id inserted into
  `bar.layout.<defaultSection>`, the bar and background layers rendered inside
  the child (`hyprctl -i <sig> -j layers` showed `omarchy-background` at level 0
  and `omarchy-bar` at level 2). Plugin ids in `plugins[]` are objects
  `{"id": ...}`, not strings; a wrong shape silently loads nothing.
- Theme: `omarchy-theme-set-templates` derives every path from `$HOME`, so
  running it under the scratch HOME after copying
  `$OMARCHY_PATH/themes/<name>/*` into `$XDG_STATE_HOME/omarchy/current/next-theme`
  stages a full theme (`shell.toml`, `colors.toml`, backgrounds) without
  reimplementing anything. `omarchy-theme-set` itself touches the live
  desktop; do not call it. Default theme is `tokyo-night`; its first
  background is `0-winding-road.jpg`. `--theme mine` = symlink the host's
  `current/theme` and `current/background`.
- A private bus permits separate notification ownership, but polkit and
  hardware-control services must still be disabled. Remove the inherited
  `QT_QPA_PLATFORMTHEME=gtk3` selector to avoid inappropriate GTK portal and
  accessibility initialization. Set `QT_NO_XDG_DESKTOP_PORTAL=1` for private
  buses and `0` for explicit shared buses. These prevent unsupported integration
  requests; they do not filter Qt logging. Detailed classification follows below.
- Stock audio widgets connect to a private, no-hardware PipeWire server started
  before Quickshell. Use the lab runtime socket explicitly, not the live host
  server; terminate this owned helper after the shell and before the bus/child.
- `QS_DISABLE_FILE_WATCHER=1` as the launcher sets it; omalab restarts
  deliberately. The shell's log is on stdout/stderr; capture it to a file per
  lab so `omalab log` can grep for `TypeError`, `binding loop`, `qml:`.
- `qs ipc -n -p $OMARCHY_PATH/shell call <target> <method> ...` with the lab's
  `WAYLAND_DISPLAY` reaches the lab's shell; `omarchy-shell` wraps this and
  can be run with the lab env exported.

## Prior art on this machine

`~/.herdr/worktrees/omapager/repoman-pr-5/.review-runtime/` — an Xvfb +
private-D-Bus + component-harness rig a review agent built to test a PR at
four scales without a compositor. No `PanelWindow` under X11, so the widget
could not instantiate; component-level only. Candidate for a `--x11` backend
that runs in CI. Not a priority.

## Implementation safety contracts (2026-09-09)

The following operations are authorized by Neil's narrow output-lifecycle
exception. All use the captured host signature, never an implicit instance:

- Read-only `hyprctl -j monitors [all]`, `activeworkspace`, and `clients`:
  discover geometry and verify placement without changing state.
- `hyprctl eval` with `hl.workspace_rule({workspace="name:omalab-<name>",
  monitor="OMALAB-<name>", default=true})` and an output-specific
  `hl.monitor(...)`: reserve a named default workspace and offscreen geometry
  **before** creating that lab's headless output. No workspace dispatcher is
  called; a named workspace avoids adding numeric buttons to the real bar.
- `hyprctl output create headless OMALAB-<name>` / `output remove OMALAB-<name>`:
  only create/remove the lab-owned output; reject a pre-existing name. The
  create/remove verbs are documented by `hyprctl output --help`; the optional
  create name was verified by the probe. Omarchy's monitor shape is in
  `config/hypr/monitors.lua`.
- `hyprctl eval 'hl.exec_cmd(command, rules)'`: launch only the lab compositor
  (`aquamarine`). The command uses an unbroken `exec` chain. Rules bind to its
  PID and `HL_EXEC_RULE_TOKEN` token, not other windows of that class. Effects
  set the lab monitor/workspace silently, initial no-focus, no-animation,
  fullscreen coverage, and undecorated opaque rendering. The wrapper waits for
  `map.allowed`; the caller creates it only after host acknowledgement, so no
  child Wayland connection can race rule registration.
- Once the PID is verified on the lab output, `hyprctl eval` dispatches
  `hl.dsp.window.fullscreen_state({internal=2, client=2, window="address:<lab>"})`
  through `hl.dispatch`. This only covers the headless output and does not
  follow or focus the window. The static fullscreen rule alone did not retain
  fullscreen state. Omarchy's `omarchy-hyprland-window-tiled-fullscreen-toggle`
  supplies the dispatcher convention; the installed version's Lua binding
  explicitly supports `window` selectors and defaults to set semantics.
  Host layers created after this transition can still overlay the lab; a
  later headless capture must reassert the addressed window's fullscreen
  transition once those layers exist. No host layer rule may be changed.
  `shot` performs an addressed `internal=0, client=0` then `internal=2,
  client=2` transition before capturing; both operations remain on the
  headless lab output. This hides host layers that appeared after startup.
- Screenshot overrides use the same output-specific `hl.monitor` operation
  on the lab-owned output only, temporarily moving it farther left to avoid
  overlap as it grows. Its original geometry/position and child scale are
  restored after capture or a catchable failure. No physical-output rule,
  workspace selection, focus, or host layer rule is changed.
- Teardown disables only the retained lab workspace-rule handle and the
  exact lab output rule after removing the output. It never reloads host
  configuration or changes physical-output rules.
- Neil approved the first `show` in this tab before step 3. `show` uses a
  single host `eval` request whose every dispatcher explicitly targets the
  verified lab address: unset fullscreen, set floating, move to the current
  workspace with `follow=false`, set exact logical `x`/`y` size with
  `relative=false`, then center that window. The current workspace is read
  inside the same request. No focus or workspace-switch dispatcher is used.
  `hide` unsets fullscreen on that same address, silently moves it back to
  `name:omalab-<name>`, and restores fullscreen on its lab-owned output only.
  Omarchy's `default/hypr/bindings/tiling.lua` provides the silent-move and
  float/resize patterns. **Correction:** this installed version's Lua resize
  API is `{x=W, y=H, relative=false, window=...}`, not `{size={W,H}, exact=true}`.
  Its `center` dispatcher also accepts an explicit `window` selector.
  Floating uses `action="enable"`: the installed parser treats unrecognized
  `"set"` as **toggle**, unlike fullscreen-state's `action="set"`. The first
  attempted show exposed that distinction and was immediately hidden; its
  active-workspace snapshot remained unchanged.

The initial far-right parking proposal was wrong: on this host, whose physical
output uses `position="auto"`, two headless outputs shifted its global x from
0 to 10198. Windows retained their monitor-relative coordinates, sizes,
workspace and focus; removing the lab outputs restores the original layout.
Place lab outputs wholly left of zero and existing outputs instead, without
changing physical-output rules. A floating child also leaves the *host's*
top-layer bar above the child in `grim -o` captures. Park the child fullscreen
on its own output so the capture shows only the lab shell.

Source evidence: installed `/usr/share/hypr/stubs/hl.meta.lua` documents
`hl.exec_cmd(cmd, rules)` and workspace/monitor specifications; Omarchy uses
`hl.exec_cmd` in `default/hypr/autostart.lua`. The Hyprland v0.56.2 executor's
`spawnWithRules` / `applyRuleToProc` functions
register PID/token properties. Ordinary `hl.window_rule` has no PID matcher;
Aquamarine hardcodes the class and title, so broad temporary class rules are
not safe for concurrent instances.

**Shell-side corrections to the probe:** `omarchy-shell` is an IPC wrapper,
not a launcher. Run `quickshell -n -p "$OMARCHY_PATH/shell"` directly, with
`QS_DISABLE_FILE_WATCHER=1` and `QS_NO_RELOAD_POPUP=1` as in
`bin/omarchy-launch-shell`. A private bus alone does not isolate hardware
control: built-in idle, lock, battery, polkit, and night-light services are
disabled in the generated `shell.json`. Idle timeout zero means *immediate
lock*, not disabled. The battery service calls `omarchy-powerprofiles-set`;
lock can change brightness; polkit registers a machine-level agent.

The built-in notification service is also disabled by default, leaving
`org.freedesktop.Notifications` available to the plugin under development.
`--plus omarchy.notifications` opts into stock notifications. This uses the
shell's existing `disabledPlugins` mechanism, not plugin-specific source
inspection or an omapager special case.

Scratch HOME/XDG directories and a private bus are **not a security sandbox**.
Plugins still run as the user. For example, omaherdr reads `/proc` and can
control host terminal panes on an interactive jump. The headless proof loads
its daemon but never requests a jump. No automatic host session lock,
power-profile change, or broad window rule is part of lab startup.

Keep a private `XDG_RUNTIME_DIR` too: otherwise Quickshell, Hyprland and
D-Bus-activated helpers create state outside `omalab/`. The host Wayland
display must then be an absolute socket path. Do **not** use the long
`<lab>/runtime` pathname directly: Linux AF_UNIX paths stop at 107 bytes.
Hyprland silently truncated `.socket.sock` and `.socket2.sock` into the same
`.soc` file while `hyprctl` still appeared to answer; Quickshell's event socket
failed. Use a short owned `omalab/.<slot>` symlink to `<lab>/runtime` and pass
that spelling to both compositor and clients; reject roots too long for the
maximum signature before any host mutation. `down` removes the alias too.

## Step 1 proof runs

Commands below used `bin/omalab` from the checkout; all lab windows remained
on named, negative-coordinate headless outputs. No `show`, host workspace
dispatcher, focus dispatcher, keyword, config reload, or real config write
was used.

- `up ~/src/omaquota -n quota`: `exec -n quota hyprctl -j layers` reported
  `omarchy-background` at layer 0 and `omarchy-bar` at layer 2, both owned by
  the lab Quickshell. `ipc -n quota shell listPlugins` reported
  `njpatel.omaquota` enabled. A parked PNG was opened and showed the stock
  Tokyo Night wallpaper and lab bar. `restart -n quota` replaced only its
  shell and returned successfully; `log` and supervised `log -f` showed the
  actual Quickshell log.
- Concurrently, `up ~/src/omaherdr -n herdr --theme mine --size 1400x900
  --scale 1.25 --plus omarchy.notifications`: `ls` showed quota and herdr
  alive at their respective geometry/theme; IPC named the enabled widget and
  stock notification service. `/proc` showed exactly one daemon carrying
  `OMALAB_DIR=<herdr lab>` and executing the symlinked checkout. Its widget
  was inspected in a 1750x1125 PNG. No jump/focus action was invoked.
- `up ~/src/omapager -n pager`: private `busctl --user --address=<lab bus>
  list` showed `org.freedesktop.Notifications` owned by lab Quickshell PID
  1056763. `exec -n pager notify-send -a omalab hi`, followed immediately by
  `ipc -n pager omapager probe`, returned `toasts:1`, `actions:["hi=[]"]`,
  one deck and 56-pixel card height. The PNG was opened and the `hi` card
  inspected. The real bus's notification owner was identical before/after.
- `up ~/src/omaquota -n shared --shared-bus --theme catppuccin` succeeded;
  `exec ... printenv DBUS_SESSION_BUS_ADDRESS` equalled the host bus. No
  notification was sent there, and its notification owner remained unchanged.
  `down -n shared` removed that lab.
- Invalid names, zero dimensions/scale, missing `--plus` values, `ls -n`, and
  `down -n default --all` were rejected. A nonexistent extra plugin failed
  before creating a host output; `down` removed the retained diagnostics.
- `down --all` was exercised between implementation runs. Lab directories
  disappeared; `/proc` scanning found no remaining process carrying their
  `OMALAB_DIR`, including bus-activated helper processes. No matching nested
  `Hyprland --config` remained. Physical output geometry returned exactly to
  its baseline after removing the initial far-right experiments; the corrected
  negative-coordinate startup preserved physical geometry and, in its measured
  before/after interval, the active workspace and focused window.
- SHA-256 fingerprints of the real `shell.json`, theme tree and background
  stayed identical. ShellCheck v0.11.0 and `bash -n bin/omalab` passed. A
  verified upstream portable ShellCheck binary was used from runtime proof
  storage; no package was installed.
- **Idle acceptance:** after restarting the quota shell, a supervised command
  slept for 605 seconds without querying or touching the lab, then ran
  `ipc -n quota shell listPlugins` and
  `exec -n quota timeout 15 grim <proof>/idle-new-client.png`. It exited 0 at
  `2026-09-09T11:53:23+04:00`; IPC still named enabled `njpatel.omaquota`.
  The new PNG was opened and showed the stock lab bar, omaquota's `setup`
  widget and Tokyo Night wallpaper, not an empty or stale host capture.
- Final `down --all` after that proof removed quota, herdr and pager, all short
  runtime aliases and all OMALAB outputs. `/proc` again showed zero processes
  carrying those lab environments; `ls` printed only its heading. The real
  config/theme/background fingerprints still matched. **Step 1 complete.**

## Step 2 proof: native screenshots

The original step-2 implementation captured the host headless output. The
corrected release captures the child output directly to exclude parent
notification overlays. It still verifies the exact lab PID/address is parked,
temporarily resizes only lab geometry, and restores mode, position, scale and
child config. The destination PNG is replaced atomically after restoration.

**Rendering correction and approved tradeoff:** simply changing a running
Qt shell's output scale produced a larger PNG with upscaled cached glyphs.
The defect was visible both in the host capture and a direct child capture;
reloading the child compositor config did not rerasterize those glyphs.
Starting the shell at scale 2 produced native detail. Neil explicitly approved
restarting only the lab shell on each scale transition (capture and restore).
This resets transient plugin state; size-only overrides do not restart it.

Verified commands/results:

- `shot -n quota`: default filename `omalab-quota-1280x800@1.png`, exactly
  1280x800. Opened and inspected: Tokyo Night wallpaper, stock lab bar and
  omaquota's `setup` indicator.
- `shot -n quota <proof>/final-2.png --scale 2`: exactly 2560x1600, same
  logical desktop. Opened and inspected at native resolution. Equal-logical
  crops of the workspace digits `2` and `3` were enlarged with nearest-neighbor
  display for comparison: @1 has coarse one-pixel stair steps; @2 has finer
  contours and distinct antialias samples, not doubled or bilinearly enlarged
  @1 pixels. Pixel comparisons also rejected both upscaling equivalents.
- `shot -n quota <proof>/size-only.png --size 1600x900`: 1600x900 with correctly
  relaid-out bar; opened and inspected. Lab shell PID unchanged. Original
  1280x800@1 output and byte-identical child config restored.
- A real capture failure was induced with a non-writable destination directory
  after requesting 1800x1000@2. `mktemp` failed with permission denied and the
  command returned nonzero without a final PNG. The EXIT path restored
  1280x800@1, the byte-identical child config, and a responsive shell (`ping`
  returned `ok`). A second `hires` lab remained responsive throughout.
- Exact snapshots of physical monitor geometry, host active workspace/focus,
  and existing host client geometry were identical across the measured
  size-only-success plus scale-override-failure sequence.

ShellCheck v0.11.0 passed after the final screenshot changes. No `show` or
host focus/workspace dispatcher was used. **Step 2 complete; step 3 requires
Neil's separate in-tab approval.**

## Step 3 proof: approved show / hide

Neil approved proceeding in this tab before the first visible test.
`show -n quota` placed one floating 1280x800 logical window on workspace 3,
centered at `[640,333]` within the physical monitor's available area. It was
left visible for eight seconds; a crop of the actual visible lab window was
opened and inspected. Repeating `show` kept it floating rather than toggling
it back into the layout. `hide -n quota` returned the same address to
`name:omalab-quota`, fullscreen only on its headless output.

The complete `hyprctl -j activeworkspace` JSON was exactly identical before
and after. Snapshots of all original clients' address, PID, class, workspace,
position and size, plus physical monitor geometry/focus, were also identical.
`shot -n quota` succeeded after hiding. No workspace-switch or focus
dispatcher was used. **Step 3 complete.**

## Step 4 proof: stamp service

`stamp/manifest.json` registers the `omalab.stamp` service. Its background-layer
`PanelWindow` is click-through, has no keyboard focus or exclusive zone, and
uses `Color.accent` at 42% content opacity. The block-glyph wordmark follows
the quota/herdr README banner style; monospace facts show plugin, commit,
dirty marker, theme, logical size@scale and UTC date.

`up` injects the service by symlink unless `--no-stamp`. `OMALAB_STAMP` is compact
JSON seeded from `stamp.json`; commit/dirty/date refresh when the lab shell
starts or restarts. Git status uses `--no-optional-locks` to avoid modifying
the plugin checkout's index. Size-only shots update displayed geometry through
the stamp's own IPC; scale shots seed the restarted service at the new scale.
Both paths restore the original label afterward.

An observed resize trap: a background-layer stamp could remain at its old
position or below the remapped wallpaper after resizing. The service now
reuses Omarchy's `Ui/ScreenMoveRemap.qml`, pulsing its remap after a geometry
update so it maps above the wallpaper again. It stays on `WlrLayer.Background`;
no host layer/window rules are added.

Verification:

- `up ~/src/omaquota -n stamped`, then `shot -n stamped`: opened the PNG and
  inspected the bottom-right mark, `njpatel.omaquota / a3f0ff90`, theme,
  `1280x800@1` and date. Child `hyprctl -j layers` placed `omalab-stamp` after
  `omarchy-background` at level 0, in a 340x119 surface with 32-pixel margins.
- `up ~/src/omaquota -n clean --no-stamp`, then `shot -n clean`: opened the
  comparison PNG; the same wallpaper corner had no stamp. The generated
  plugin list and plugin directory contained no `omalab.stamp`.
- `shot -n stamped --size 1600x900` retained the stamp at the new bottom-right
  corner with `1600x900@1`; the cropped detail was opened and inspected after
  the remap fix. `--scale 2` produced a native-resolution stamp with
  `1280x800@2`. On restoration, metadata returned to `1280x800@1`.
- `up ./stamp -n stamp-self --theme catppuccin` developed the stamp as the
  primary plugin. Its screenshot showed the alternative theme and real
  `ada0da02+dirty` repository state. No copied plugin checkout or fabricated
  commit was used.
- Final restart, stamped/unstamped captures, ShellCheck and Bash syntax checks
  passed. All stamp development remained headless. **Step 4 complete.**

## Step 5 proof: v0.1.0 release

- README and `bin/omalab --help` describe all implemented commands/options,
  naming and geometry limits, the explicit show boundary, hidden-only capture,
  scale-transition shell restarts, private-bus/runtime limitations and stamp
  semantics. Compatibility is stated as verified Hyprland 0.56.2 / Quickshell
  0.3.1, not a claim about future parser/API versions.
- Added the declared Apache-2.0 distribution license from Apache's official
  license text. No additional runtime package or test dependency is bundled.
- Final `up ~/src/omaquota` created the default named lab with its stamp and
  printed working show/capture/log instructions. `ipc shell ping` returned
  `ok`; `shot <proof>/release-default.png` produced a 1280x800 PNG that was
  opened and inspected, including the stamp. No additional visible show was
  needed for release verification.
- Final ShellCheck v0.11.0 and `bash -n bin/omalab` passed. `bin/omalab --help`
  printed the complete CLI and exited successfully.
- Final `down --all` removed quota, stamped, clean, stamp-self and default.
  `/proc` contained zero processes carrying their lab environments; no
  OMALAB output, short runtime alias or named lab directory remained. `ls`
  printed only its heading. The real shell config/theme/background fingerprints
  remained unchanged, and the physical output returned to its original
  5120x2880@2 geometry at `[0,0]`.

The release commit is tagged locally as `v0.1.0`; pushing is Neil's step.

## Release correction after external verification

Neil verified lifecycle/capture/scale/teardown externally, then rejected the
child's visible `.conf` and standalone-startup warnings and the noisy shell
log. The earlier assumption that those banners merely expired was wrong.

### Warning-free child and product capture

The child now loads `hyprland.lua`; the startup callback uses
`hl.on("hyprland.start", ...)` and `hl.exec_cmd` to report its environment.
The generated config and all resize/restore/launch callers use Lua. No
legacy config path or compatibility shim remains.

Verified on the installed Hyprland:

```text
hyprctl -j status                         configProvider: lua, backend: wayland
hyprctl -j getoption misc:disable_watchdog_warning   bool: true, set: true
hyprctl -j getoption debug:suppress_errors           bool: false, set: false
hyprctl configerrors                      empty
```

These commands were run through `omalab exec` against the child, not the host.
`misc.disable_watchdog_warning` is the narrow supported control for the
intentional standalone nested launch; general error reporting stays enabled.
Normal 1280x800 and native 2560x1600 shots were opened and inspected with no
Hyprland warning banners. Size-only 1600x900 capture and restoration also passed.

Inspection also exposed parent desktop notifications over host-side captures.
The final `grim` now connects directly to the child's socket: parent layers
cannot enter the PNG. This is real child rendering, not cropping, masking,
post-processing, or changing the host's notification settings. Existing scale
and atomic-output restoration behavior is retained.

### Complete baseline diagnostic split

The external verification lab had already been removed. A fresh omaquota lab
was used to collect the exact messages for classification; its complete log
is retained at `$XDG_RUNTIME_DIR/omalab/.proof/correction-before.log`.
The sample has **4 lines matching `error|TypeError|binding loop`, all plumbing**,
plus **3 accessibility warnings, also plumbing**. Logs append across shell
restarts, so counts in an accumulated log can be higher.

| Baseline line(s) | Diagnostic | Classification and fix |
|---|---|---|
| 6, 7 | `qt.qpa.theme.gnome`: `org.freedesktop.portal.Settings` / `UnknownMethod` | Plumbing: inherited `QT_QPA_PLATFORMTHEME=gtk3` loads GTK desktop integration on a private bus. Unset that selector; Omarchy's Qt Quick theme remains intact. |
| 9 | `AT-SPI: Could not obtain desktop path or name` | Plumbing: GTK initialized accessibility against an incomplete private registry. Removing the inherited GTK platform theme prevents this initialization. |
| 11 | `qt.qpa.services`: `Connection already associated with an application ID` | Plumbing: Qt's initial portal registration can race its service-registration watcher during fresh private portal activation. Unsetting GTK alone did not reliably fix a fresh launch. Set `QT_NO_XDG_DESKTOP_PORTAL=1` for private buses, where host portal integration is unsupported; use `0` for explicit `--shared-bus`. |
| 13 | `atk-bridge: GetRegisteredEvents returned message with unknown signature` | Plumbing: same inappropriate GTK accessibility initialization; fixed by platform-theme isolation. |
| 15 | `atk-bridge: get_device_events_reply: unknown signature` | Plumbing: same GTK/accessibility path; fixed by platform-theme isolation. |
| 16 | `quickshell.service.pipewire.loop`: `Failed to connect pipewire context. Errno: 112` | Plumbing: stock audio clients had no server in the private runtime. Start a real private PipeWire server before Quickshell, with no hardware devices or session manager. |

There were **0 omaquota-owned matching shell-log lines**, and no TypeError or
binding-loop messages in this preserved sample. Missing credentials are not
an excuse to dismiss such messages if they occur. Separately, the actual
omaquota snapshot contained the expected plugin-owned state:

```text
ok: false
error: no management key at <scratch HOME>/.config/omaquota/management-key - run omaquota-setup
stats: {}
accounts: []
```

This is an expected `setup` state, not a shell-log TypeError. The fetcher writes
it to `~/.local/state/omarchy/omaquota/snapshot.json` and exits before contacting
the proxy. The real management key and usage history are intentionally not
copied. README's **What a lab does not have** section explains that boundary.

### Source fixes, not logging suppression

- Omarchy's `default/hypr/envs.lua` exports the GTK3 platform-theme selector.
  Qt's GTK3 theme initializes GTK and its portal-settings client. Removing that
  inherited selector fixes the Settings/accessibility messages without an
  accessibility blacklist or log-category filter.
- Qt's `QDesktopUnixServices` constructor checks
  `QT_NO_XDG_DESKTOP_PORTAL` before creating portal queries/registration/watchers.
  This deliberately disables unsupported private-bus integration, not logging.
  Explicit shared-bus startup was also verified with clean logs and the portal
  selector at `0`.
- `omalab-pipewire.conf` is a uniquely named lab-owned config, following
  Omarchy's private filter-host configuration convention. It loads only native
  protocol, client-node, metadata and access modules. No ALSA, device factories,
  WirePlumber, Pulse server or hardware session manager is started.
  `PIPEWIRE_RUNTIME_DIR` and `PIPEWIRE_REMOTE` select only the private socket.
  Using the host socket to silence the error was rejected: it would connect
  the lab's audio controls to real devices. `pw-dump` confirmed the private
  core PID equals the recorded lab PipeWire PID and there are zero Device/Node
  objects. `down` and failed startup stop the owned audio process too.

After fresh corrected startup plus scale-change/restoration shell restarts,
the complete unfiltered omaquota shell log contains **0 matching errors,
0 warnings, 0 TypeErrors and 0 binding loops**. It is retained as
`$XDG_RUNTIME_DIR/omalab/.proof/correction-after.log`. Neither Qt logging rules
nor the shell's stderr capture were suppressed. The missing-key snapshot
still reports its genuine expected plugin state.

Final correction checks exercised seven shell starts (including scale
transitions and failed-capture restoration) with zero matching errors or
warnings in the raw corrected log. A permission-denied capture restored the
byte-identical Lua config and a responsive shell. Normal, native-scale and
stamped direct-child PNGs were inspected without startup banners or parent
overlays. ShellCheck v0.11.0 and Bash syntax checks passed.

Only the five correction test labs were stopped. Their compositor, shell,
bus and private PipeWire processes, output names and state directories were
gone afterward; real shell config/theme/background fingerprints still matched
the pre-correction values. The fixed commit replaces the local `v0.1.0` tag
at Neil's request; nothing is pushed.
