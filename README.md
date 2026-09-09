# omalab

A throwaway Omarchy desktop for developing shell plugins.

`omalab up ~/src/myplugin` starts a second Omarchy — real Hyprland, real
`omarchy-shell`, real theme — with your plugin checkout loaded and nothing
else of yours touched. It runs on a headless output, so your desktop never
flickers, restarts, or loses its notification daemon while you work. Bring it
onto your screen when you want to look, screenshot it at any size and scale
when you want a picture, throw it away when the idea did not work out.

## Install

```sh
git clone https://github.com/njpatel/omalab ~/src/omalab
ln -s ~/src/omalab/bin/omalab ~/.local/bin/omalab
```

Needs Omarchy's Hyprland, Quickshell, grim, jq, D-Bus, Git and standard shell
utilities. No root or additional runtime packages. Lab state lives under
`$XDG_RUNTIME_DIR/omalab/`; screenshots go to the file you choose.

Verified with **Hyprland 0.56.2 and Quickshell 0.3.1** and the current Omarchy
shell plugin API. The host uses Hyprland's Lua configuration API; the child
uses its legacy `.conf` parser. Other versions are not yet verified, and
Hyprland's announced removal of that parser in 0.57 will require an update.

## Use

```
omalab up <plugin-dir> [-n NAME] [--theme NAME|mine] [--size WxH] [--scale N]
                       [--plus PLUGIN-ID ...] [--shared-bus] [--no-stamp]
omalab show [-n NAME]         float the lab on your current workspace
omalab hide [-n NAME]         put it back on the headless output
omalab shot [-n NAME] [FILE] [--scale N] [--size WxH]
omalab ipc  [-n NAME] <target> <method> [args...]    omarchy-shell inside the lab
omalab exec [-n NAME] <cmd...>                       run a command in the lab session
omalab log  [-n NAME] [-f]    the lab shell's log (QML warnings included)
omalab restart [-n NAME]      restart the lab shell; the plugin is a symlink, so edits are live
omalab ls
omalab down [-n NAME | --all]
```

The lab looks like a fresh Omarchy install: stock bar layout, the default
theme and wallpaper, your plugin added in its manifest's `defaultSection`.
`--theme mine` uses your current theme and background instead. Several labs
run side by side; `-n` names them.
`show` is the only command that brings a lab onto your visible workspace;
it does not switch workspaces or explicitly change focus. `hide` parks it
again. Hide a lab before using `shot`.

The default lab name is `default`; size defaults to `1280x800` logical pixels
at scale `1`. `--plus` accepts installed plugin IDs or first-party Omarchy
IDs. Machine-control services (idle, lock, battery power profiles, polkit and
night light) are disabled: the real desktop owns those. Stock notifications
are disabled so a notification plugin can own its private bus name; use
`--plus omarchy.notifications` when you want the stock notification service.
Names use 1–48 letters, digits, underscores or hyphens, starting with a letter
or digit. Sizes range from 200 to 8192 logical pixels per dimension, at a
positive scale up to 4; physical dimensions must be integral and at most
16384 pixels. A short runtime path is required by Unix socket limits.

`shot` writes `omalab-<name>-<WxH>@<scale>.png` in the current directory unless
you supply a file. Sizes are logical pixels: `--size 1280x800 --scale 2`
produces 2560x1600 pixels. Geometry and scale are restored afterward, including
on a catchable capture failure. **Changing scale restarts the lab shell twice**
to render native-resolution text and restore its original scale; transient
panels and in-memory plugin state reset. Size-only shots keep the shell running.

This is an isolated desktop environment, **not a sandbox for untrusted
plugins**. Plugins and `exec` commands still run as your user. `--shared-bus`
deliberately shares the host session bus; only use it when the plugin needs
host session services. Private runtime sockets also mean host audio services
are not connected by default.

Every lab carries a small stamp in the bottom-right of the wallpaper: the
plugin id, git commit and dirty marker, theme, size@scale, and UTC date, so a
screenshot says where it came from. Commit/date refresh on `up` and `restart`;
shot overrides update the displayed geometry. `--no-stamp` omits the service
for clean product shots.

## How

The shell reads its configuration from `$HOME` and XDG directories, so the
lab is an environment, not a copy: a scratch `HOME` and private runtime,
config, state, cache and data directories; a generated `shell.json`; the theme
staged by Omarchy's own `omarchy-theme-set-templates`; the plugin symlinked into
`.config/omarchy/plugins/`. Hyprland runs as a Wayland client of your
compositor (its window is parked on a headless output), the shell runs
against that nested compositor, and a private D-Bus session lets a
`service`-kind plugin own a bus name your real desktop already holds.
`docs/HOW.md` has the details and the traps.

The lab is disposable: `down` removes its state; `down --all` removes all labs.
Failed startup retains diagnostics under the lab directory until `down`.
Use `log` for QML warnings. Private labs can log unavailable audio/portal
services, and Hyprland's startup warning banners can appear briefly in early
screenshots before expiring normally.

## License

[Apache-2.0](LICENSE). Copyright 2026 Neil Patel.
