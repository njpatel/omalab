# How omalab isolates, and what was learned proving it

Findings from a hand probe on 2026-09-09 (Hyprland 0.56.2, Omarchy shell from
/usr/share/omarchy, Intel iGPU, one 5120x2880@2 output). Everything below was
observed, not assumed.

## Nested Hyprland

- `Hyprland --config <file>` inside a Wayland session picks the Wayland
  backend automatically (aquamarine: "Connected to a wayland compositor:
  Hyprland") and appears as a normal toplevel, class `aquamarine`, title
  `aquamarine - WAYLAND-1`.
- **Unset `HYPRLAND_INSTANCE_SIGNATURE`** in its environment. With the parent's
  signature inherited, the child tries to lock the parent's `wayland-1` and
  dies silently ("unable to lock lockfile ... maybe another compositor is
  running"). With it unset, it takes the next free name (`wayland-2`).
- It does not need `start-hyprland`; the warning is harmless. It does need to
  be detached (`setsid`/`nohup`) or it dies with the shell that launched it.
- Its instance signature is the newest dir under `$XDG_RUNTIME_DIR/hypr/`
  after launch. Its socket name is in the env of anything it `exec`s
  (`WAYLAND_DISPLAY=wayland-2`). Read both from `hyprctl -i <sig>` / a probe
  exec, never guess.
- Output inside is `WAYLAND-1`. Size and scale are set with
  `hyprctl -i <sig> eval 'hl.monitor({output="WAYLAND-1", mode="1280x800@60", scale=1})'`
  (`keyword monitor` is rejected by the Lua config parser; `hl.monitor` needs
  `output` and `mode`, not `name`/`resolution`). Scale 2 is what makes a
  HiDPI screenshot.
- Config needs `misc { disable_hyprland_logo = true; disable_splash_rendering = true }`
  and `xwayland { enabled = false }`; nothing else. Keep it Hyprland-conf, not
  Lua, so it works on any Omarchy without their bootstrap.
- **Open problem:** after ~1 min idle the nested instance stopped accepting new
  Wayland clients (`grim` and `wayland-info` on its socket hung; `hyprctl -i`
  still answered). Not root-caused. Suspects: no `--watchdog-fd`, or the parent
  stopped sending frame callbacks to an unmapped/offscreen window so the child
  never ticks. Test with the window on a headless output first; if it recurs,
  try `debug:disable_scale_checks` / `misc:vfr = false` in the child config.

## The host side

- Park the child window on a headless output so it never appears on the user's
  screen: `hyprctl output create headless <name>` then
  `hyprctl eval 'hl.monitor({output="<name>", mode="WxH@60", position="<far right>x0", scale=1})'`
  and a window rule / `hl.dsp.window.move` to send `class:aquamarine` there.
  `show` moves it to the active workspace as a float (`hl.dsp.window.float`,
  `hl.dsp.window.resize({size={W,H}, exact=true})`, `window.center`); `hide`
  sends it back.
- **Never** toggle special workspaces, change the active workspace, or run
  `hyprctl keyword` on the host to make a screenshot work. That bounces the
  user's desktop. It happened during the probe and is the reason this file
  exists.
- Dispatchers on this Hyprland are Lua: `hl.dsp.window.float/resize/move/center`,
  `hl.dsp.workspace.toggle_special("name")` (positional string), `hl.dsp.exec_cmd`.
  Names in `/usr/share/omarchy/default/hypr/bindings/*.lua` are the reference.
  `hyprctl -j clients` `at`/`size` are logical (post-scale) coordinates; so is
  `grim -g`.
- Screenshots: `grim -o <headless-output-name>` on the host captures the whole
  parked window without ever showing it. Inside-the-child `grim` is the
  alternative once the idle problem is solved.

## The shell side

- `omarchy-shell` is `quickshell -n -p $OMARCHY_PATH/shell`. It reads
  `Quickshell.env("HOME")` for `~/.config/omarchy/shell.json` and
  `~/.config/omarchy/plugins/`, and `$XDG_STATE_HOME/omarchy/current/{theme,background}`
  for colours and wallpaper. So the lab is: `HOME`, `XDG_CONFIG_HOME`,
  `XDG_STATE_HOME`, `XDG_CACHE_HOME` pointed at a scratch dir, plus
  `WAYLAND_DISPLAY` and `HYPRLAND_INSTANCE_SIGNATURE` of the child. Leave
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
- The shell warns that `org.freedesktop.Notifications` and the polkit agent
  are already registered, and the portal app id is taken. On the shared bus
  these are harmless; a private `dbus-run-session`/`dbus-daemon --session`
  per lab removes them and lets `service` plugins (omapager) own the name.
  Tray, portals and secrets then need `--shared-bus`.
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
