# omalab

Read `README.md` for what this is (it is the spec: the CLI it describes is
the CLI to build) and `docs/HOW.md` for what has already been proven about
nested Hyprland, the shell's environment contract, and the traps. Do not
rediscover anything in HOW.md; do add to it when you learn something.

## Shape

- `bin/omalab` — Bash CLI and namespace supervisor (`set -euo pipefail`).
  `bin/omalab-setup` prepares the private dependency runtime; no system library
  replacement or root package installation. Both remain shellcheck clean.
- `stamp/` — an Omarchy shell plugin (`manifest.json`, kind `service`) that
  draws the lab stamp on a background layer. Injected into every lab's
  `shell.json` unless `--no-stamp`.
- `docs/HOW.md` — the knowledge. `README.md` — the product.
- State per lab: `$XDG_RUNTIME_DIR/omalab/<name>/` holds `home/`, `run/`,
  `hyprland.lua`, `meta.json` (format 2), child `env`, outer `pids`, inner
  `session.pids`, namespace `supervisor-info.json`, and raw service logs.
  `support/input.py` provides the lab-local persistent virtual input controller.

## Rules

1. **Nothing on the user's screen unless they asked.** Only `show` may open a
   normal viewer on the desktop. No command may create a host output, toggle
   special workspaces, switch host workspaces, dispatch host focus or alter
   host compositor configuration. All rendering/input occurs in the isolated
   session. Host compositor queries are permitted only as read-only proof.
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
4. Test plugins: `~/src/omaquota`, `~/src/omaherdr`, `~/src/omapager`, and the
   bundled stamp. Mount their directories read-only so host edits remain live;
   never copy a checkout or pass host credentials without explicit permission.
5. This is going to be open source. Write for a plugin author who has never
   seen this machine: no paths that only exist here, no assumptions about
   monitor count or scale, and every host command discovered from Omarchy's
   own files, not hardcoded.
