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

Needs what Omarchy already has: Hyprland, quickshell, grim, jq, dbus. No
root, no packages, nothing written outside `$XDG_RUNTIME_DIR/omalab/`.

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

The default lab name is `default`; size defaults to `1280x800` logical pixels
at scale `1`. `--plus` accepts installed plugin IDs or first-party Omarchy
IDs. Machine-control services (idle, lock, battery power profiles, polkit and
night light) are disabled: the real desktop owns those. Stock notifications
are disabled so a notification plugin can own its private bus name; use
`--plus omarchy.notifications` when you want the stock notification service.

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
plugin id, its git commit, theme, and size@scale, so a screenshot says where
it came from. `--no-stamp` for clean product shots.

## How

Everything the shell reads comes from `$HOME`, so the lab is an environment,
not a copy: a scratch `HOME` with a generated `shell.json`, the theme staged
by Omarchy's own `omarchy-theme-set-templates`, the plugin symlinked into
`.config/omarchy/plugins/`. Hyprland runs as a Wayland client of your
compositor (its window is parked on a headless output), the shell runs
against that nested compositor, and a private D-Bus session lets a
`service`-kind plugin own a bus name your real desktop already holds.
`docs/HOW.md` has the details and the traps.

## License

Apache-2.0
