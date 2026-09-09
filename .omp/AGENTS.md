# omalab

Read `README.md` for what this is (it is the spec: the CLI it describes is
the CLI to build) and `docs/HOW.md` for what has already been proven about
nested Hyprland, the shell's environment contract, and the traps. Do not
rediscover anything in HOW.md; do add to it when you learn something.

## Shape

- `bin/omalab` — one bash script, Omarchy-style (`set -euo pipefail`, `fail()`,
  a `usage` heredoc, subcommands as functions). No dependencies beyond what
  Omarchy installs. `shellcheck` clean.
- `stamp/` — an Omarchy shell plugin (`manifest.json`, kind `service`) that
  draws the lab stamp on a background layer. Injected into every lab's
  `shell.json` unless `--no-stamp`.
- `docs/HOW.md` — the knowledge. `README.md` — the product.
- State per lab: `$XDG_RUNTIME_DIR/omalab/<name>/` holding `home/` (scratch
  HOME), `hyprland.lua`, `env` (KEY=VALUE for the child: sig, display, bus),
  `pids`, `shell.log`. `omalab ls` reads these dirs. `down` removes the dir.

## Rules

1. **Nothing on the user's screen unless they asked.** Only `show` may put a
   window on a visible workspace. Never toggle special workspaces, switch
   workspaces, move focus, or set host keywords. Every host-side `hyprctl`
   call must name the lab window by address or class `aquamarine` and must
   be listed in HOW.md with why it is safe.
2. **Never touch the user's real desktop config or state.** No writes under
   the real `~/.config/omarchy`, `~/.local/state/omarchy`, no
   `omarchy-restart-shell`, no `omarchy-theme-set`. Read-only symlinks into
   them are fine.
3. **Verify inside the lab.** Proof of a working `up` is
   `hyprctl -i <sig> -j layers` showing `omarchy-bar`, `omalab ipc shell
   listPlugins` naming the plugin, and `omalab shot` producing a PNG whose
   content the lab bar — checked by looking at it, not by file size. Proof of
   `down` is an empty `$XDG_RUNTIME_DIR/omalab/<name>` and no leftover
   `Hyprland --config` or `quickshell` processes from that lab.
4. Test plugins: `~/src/omaquota` (bar widget, simplest), `~/src/omaherdr`
   (bar widget with a daemon), `~/src/omapager` (service kind, owns a bus
   name — the hard case). Symlink, never copy, so edits are live.
5. This is going to be open source. Write for a plugin author who has never
   seen this machine: no paths that only exist here, no assumptions about
   monitor count or scale, and every host command discovered from Omarchy's
   own files, not hardcoded.
