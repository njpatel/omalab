# Plan

Ordered. Each step ends with its proof recorded in `docs/HOW.md` or this
file (what was run, what was seen). Do not start the next step before the
proof exists. Nothing appears on Neil's screen before step 3, and step 3
asks him first.

## 1. up / down / ls / log / ipc / restart — headless only

- `up <plugin-dir>`: scratch HOME under `$XDG_RUNTIME_DIR/omalab/<name>/home`;
  `shell.json` generated from `$OMARCHY_PATH/config/omarchy/shell.json` with
  the plugin (id read from its `manifest.json`) in `plugins[]` and its
  `barWidget.defaultSection`; theme `tokyo-night` staged via
  `omarchy-theme-set-templates` under the scratch HOME; plugin symlinked into
  `.config/omarchy/plugins/<id>`; host headless output created and sized;
  child Hyprland launched detached with the signature unset; window moved to
  the headless output; private D-Bus session; shell launched with the lab env
  and its log to `shell.log`. Print the lab name and how to look at it.
- Options in this step: `-n`, `--theme NAME|mine`, `--size`, `--scale`,
  `--plus`, `--shared-bus`.
- `down`: kill shell, bus, child compositor (in that order), remove the host
  headless output, `rm -rf` the lab dir. `--all`.
- `ls`: name, plugin, size@scale, theme, age, pids alive?
- `log [-f]`, `ipc`, `restart`, `exec`.
- Prove with omaquota, then two labs at once (omaquota + omaherdr), then
  omapager on a private bus owning `org.freedesktop.Notifications` (check with
  `busctl --user --address=<lab bus> list`), and `omalab exec notify-send hi`
  landing in the lab's omapager, not Neil's.
- Chase the idle problem from HOW.md here: a lab must still answer `ipc` and
  accept a new Wayland client after 10 minutes untouched.

## 2. shot

- `shot [FILE] [--scale N] [--size WxH]`: capture the parked window via
  `grim -o <headless>` on the host. `--scale`/`--size` reconfigure the child
  output (`hl.monitor` on the child sig), wait for the shell to relayout, shoot,
  and put it back. Default file `omalab-<name>-<WxH>@<scale>.png` in cwd.
- Prove: 1280x800@1 and @2 of omaquota; the @2 PNG is 2560x1600 and the bar
  text is crisper, not upscaled (compare a glyph edge). Look at both.

## 3. show / hide

- `show`: `hl.dsp.window.move` the lab window to the host's active workspace,
  float, exact size, center. `hide`: back to the headless output.
- **Ask Neil in the tab before the first `show`**; he watches. Prove: `show`
  puts one floating window on his workspace and nothing else changes; `hide`
  removes it; his `hyprctl activeworkspace` is identical before and after.

## 4. stamp plugin

- `stamp/`: kind `service`, a `PanelWindow` on `WlrLayer.Background` above the
  wallpaper, bottom-right, reading `$OMALAB_STAMP` (JSON: plugin id, commit,
  dirty, theme, size, scale, date) from the environment `up` sets. Block-glyph
  "omalab" mark (see the README banners of ~/src/omaherdr and ~/src/omaquota
  for the style Neil likes; make it cooler than Windows' build stamp), theme
  accent colour from `Color`, ~40% opacity, monospace facts beneath.
  `--no-stamp` omits it from `shell.json`. Develop it inside a lab.
- Prove: a `shot` of a lab shows the stamp; `--no-stamp` does not.

## 5. Docs and first release

- README matches the CLI exactly. HOW.md complete. `shellcheck bin/omalab`
  clean. `omalab --help`. Tag v0.1.0 (Neil pushes).

## Later, not now

- `--x11` backend from the review rig; `omalab test`; a GitHub Action.
- A bar widget listing labs (like omaherdr for sessions).
- Offer upstream as `omarchy dev lab`.
