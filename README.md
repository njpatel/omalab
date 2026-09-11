<!-- Pin the CDN revision to the commit containing assets/header.png. -->
<img src="https://cdn.jsdelivr.net/gh/njpatel/omalab@183fe7d29b2d1eb3787fd356d9c5d127af812d80/assets/header.png" alt="omalab — the real lab stamp over the default wallpaper" width="100%">

**Develop shell plugins against a real Omarchy desktop without restarting your own.**

`omalab` runs the installed Hyprland compositor and Omarchy shell around your
plugin checkout, with disposable configuration, state and session services.
It starts headlessly inside Bubblewrap and Cage, with no connection to your host
display. Open a viewer deliberately, capture native-resolution screenshots,
send plugin IPC, and remove the lab when you are finished.

This is a development environment, **not a sandbox for untrusted code**.

`up` and `shot` need an installed Omarchy stack and an accessible GPU render
node, **not an active host desktop**. Only `show` opens a normal viewer window.
The backend creates no host monitors and issues no host compositor mutations.

[Quick start](#quick-start) · [Commands](#commands) · [Isolation](#isolation-boundaries)
· [CI](docs/CI.md) · [Engineering reference](docs/HOW.md) · [Agent skill](skills/omalab/SKILL.md)
· [Contributing](CONTRIBUTING.md)

## Requirements

- Linux with the installed **Omarchy desktop stack**, an owned `XDG_RUNTIME_DIR`,
  and `OMARCHY_PATH` pointing to that installation.
- An accessible `/dev/dri/renderD*` GPU render node, Bubblewrap with working
  unprivileged user namespaces, and `nsenter` from util-linux.
- Hyprland, Quickshell, PipeWire, D-Bus, grim, jq, Git and standard shell tools.
- Python 3, `wtype`, headless Cage, WayVNC and TigerVNC's `vncviewer`, plus the private
  patched Aquamarine runtime prepared by **`omalab-setup`** below. Setup has additional
  download/build dependencies; there is no build on `up`.

The compatibility target is Omarchy **4.0.2**, Hyprland **0.56.2**, Quickshell
**0.3.1**, PipeWire **1.6.8** and Aquamarine **0.14.0 (ABI 13)**. The CLI depends
on Omarchy's shell/plugin API and Hyprland's Lua API; other versions are not a
compatibility guarantee. See the [engineering reference](docs/HOW.md) for the
patch rationale and the scope of recorded verification.

A stock GitHub-hosted Linux runner or plain container is not provisioned with
this GPU/desktop stack. Headless operation does not remove those requirements.

## Install

```sh
git clone https://github.com/njpatel/omalab.git "$HOME/.local/share/omalab"
mkdir -p "$HOME/.local/bin"
ln -s "$HOME/.local/share/omalab/bin/omalab" "$HOME/.local/bin/omalab"
ln -s "$HOME/.local/share/omalab/bin/omalab-setup" "$HOME/.local/bin/omalab-setup"
omalab-setup --help
omalab-setup
omalab --help
```

Ensure `~/.local/bin` is on `PATH`. Keep the checkout intact: the executable
locates the bundled stamp and compatibility patch relative to itself.

Setup prepares `${XDG_DATA_HOME:-$HOME/.local/share}/omalab-runtime`; set
`OMALAB_RUNTIME_DIR` consistently for setup and the CLI to override it. It builds
the patched Aquamarine v0.14.0 library and supplies missing Cage/WayVNC/viewer
tools privately. It does **not** replace system libraries or install system
packages. Its library search path is set only inside the sandbox; do not export
`LD_LIBRARY_PATH` into your desktop.

Setup targets **Arch Linux x86_64** with installed Aquamarine 0.14.0 / ABI 13
and its development dependencies. It needs Git, curl, CMake, Ninja, a C++23
compiler, pkg-config, binutils, jq, flock and standard utilities. Supplying
missing Cage/WayVNC/TigerVNC tools also needs the configured pacman repositories,
local sync database, pacman-key and bsdtar; downloaded packages are signature
verified and unpacked privately, not installed. Read `omalab-setup --help` for
the complete prerequisite check.

To update, pull the checkout with `git pull --ff-only` and rerun setup when the
runtime requirements change. Recreate existing labs after an update; `restart`
reloads the shell, not its compositor or generated environment. Old-format lab
records are refused rather than migrated automatically; do not delete them
blindly while their old processes may still be running.

## Quick start

Run as your normal user with the requirements above; an SSH login or user
service can be used without a graphical session. The plugin directory must
contain a valid Omarchy `manifest.json`.

```sh
cd ~/src/my-plugin
omalab up . -n dev
omalab ipc -n dev shell listPlugins
mkdir -p artifacts
omalab shot -n dev artifacts/preview.png
```

The checkout is **mounted live and read-only, not copied**. Host edits are
visible inside the lab, but lab processes cannot write back through that mount.
The lab starts with the stock bar,
Tokyo Night theme and wallpaper, your plugin, and a provenance stamp. Bar
widgets go into their manifest's `barWidget.defaultSection`; service plugins
are enabled without needing a bar slot.

Only show it when you want a normal TigerVNC window in your current desktop
session (`DISPLAY`/XWayland is required by that viewer). Placement and focus
follow your window-manager policy; omalab issues no host dispatches. Agents
must obtain explicit permission for this task's visible inspection:

```sh
omalab show -n dev
omalab hide -n dev
```

After editing your checkout:

```sh
omalab restart -n dev
omalab shot -n dev artifacts/updated.png
omalab log -n dev
```

Finish by removing only that lab:

```sh
omalab down -n dev
```

`down` deletes the lab's private state. Save screenshots, logs and any useful
fixtures first. If `up` fails, its diagnostic files remain until `down`.

## Settings, fixtures and services

The lab deliberately starts without your desktop's plugin configuration,
credential files, application history or cached data. A plugin displaying
"not configured", "sign in" or "no data" can be behaving correctly. That does
not make a QML TypeError or binding loop an expected condition: read the log.

Use `exec` to configure or inspect the **lab's** environment:

```sh
omalab exec -n dev printenv HOME XDG_CONFIG_HOME XDG_STATE_HOME
omalab exec -n dev sh -c 'cat "$HOME/.config/omarchy/shell.json"'
omalab exec -n dev bash
```

The last command opens a shell in your current terminal, inside the lab's
namespaces and **scratch HOME working directory**, with its display, session
bus and audio connection. Your host working directory and arbitrary host file
paths are not mounted. Create fixtures in the lab, or explicitly stream data
through stdin/stdout; do not assume a host artifact path works inside `exec`.

For example, the outer shell writes these files on the host:

```sh
omalab log -n dev > artifacts/shell.log
omalab exec -n dev sh -c 'cat "$HOME/result.json"' > artifacts/result.json
```

`shot` accepts a host destination itself and streams the actual child capture
out; it does not expose that destination directory to the lab.

Quote variables when expansion must happen inside the lab. In the example
above, single quotes prevent your outer shell from expanding its own `$HOME`.
Do not automatically copy production credentials into a disposable lab.

Additional plugins must already be installed on the machine:

```sh
omalab up . -n integration --plus omarchy.notifications
```

The built-in notification service is **off by default**, leaving its private
bus name available to notification-service plugins. Enable the stock service
only when it is the one you want. Other service dependencies, test data and
backend processes belong to your plugin's setup; omalab does not invent or
start them for you.

Networking is isolated by default, including access to host loopback services.
Use `up --network` only when host-loopback or external services are explicitly
needed and authorized; it shares the host network namespace, not a filtered
allowlist. `--shared-bus` independently permits the explicitly supplied
filesystem session-bus socket and weakens that boundary. It does not expose
the system bus. Missing NetworkManager, Bluetooth and UPower services are
expected limits of the private environment; raw logs are not filtered to hide
them. Neither option copies credentials or other host state.

## Screenshots

```sh
omalab shot -n dev artifacts/preview.png
omalab shot -n dev artifacts/large.png --size 1600x1000
omalab shot -n dev artifacts/retina.png --size 1280x800 --scale 2
```

For offscreen UI automation, use the lab's persistent input controller:

```sh
omalab input -n dev move 400 200
omalab input -n dev click 400 200
omalab input -n dev type 'test input'
omalab input -n dev key Ctrl+a
```

Coordinates are pixels in the original screenshot/framebuffer, not a downscaled
preview: double them for the same logical point at scale 2. Input stays on the
private viewer socket and requires no visible viewer. Supported operations are
move, left-click, text and named key/chord input; scrolling and drags are not
implemented. Prefer plugin IPC when it can establish state directly.

Sizes are **logical pixels**. `1280x800` at scale `2` produces a `2560x1600`
PNG. Capture reads the child compositor directly, so host notifications and
other desktop overlays do not enter the image. Closing an open viewer before
a scale-changing shot avoids showing its transient shell restart.

- Without a file argument, the filename is `omalab-<name>-<WxH>@<scale>.png`
  in the current directory. An explicit destination's parent directory must exist.
- Size-only overrides keep the shell running.
- **Scale overrides restart the lab shell twice**: once to render at the target
  scale, and again when restoring it. Open panels and in-memory plugin state reset.
- Original geometry is restored after capture or a catchable failure. The final
  file is published atomically after successful restoration.

For a stateful screenshot, start at the target scale first, then drive your
plugin and capture without changing scale:

```sh
omalab up . -n preview-2x --size 1280x800 --scale 2
# Open the desired state through your plugin's documented IPC or UI.
omalab shot -n preview-2x artifacts/stateful.png
omalab down -n preview-2x
```

The stamp records plugin id, commit/dirty state, theme, geometry and UTC date.
Commit/date refresh on shell startup; screenshot overrides update its geometry.
Use `--no-stamp` on `up` for unstamped product images. This does not freeze the
bar clock, weather, network data or your plugin's live content.

## Commands

```text
omalab up <plugin-dir> [-n NAME] [--theme NAME|mine] [--size WxH] [--scale N]
                       [--plus PLUGIN-ID ...] [--network] [--shared-bus] [--no-stamp]
omalab show [-n NAME]
omalab hide [-n NAME]
omalab shot [-n NAME] [FILE] [--scale N] [--size WxH]
omalab ipc [-n NAME] <target> <method> [args...]
omalab exec [-n NAME] <cmd...>
omalab input [-n NAME] move X Y | click X Y | type TEXT | key CHORD
omalab log [-n NAME] [-f]
omalab restart [-n NAME]
omalab ls
omalab down [-n NAME | --all]
```

Defaults: name `default`, theme `tokyo-night`, size `1280x800`, scale `1`.
`--theme mine` uses the host's current theme and wallpaper, not its plugin
configuration. Names are 1–48 letters, digits, underscores or hyphens, starting
with a letter or digit. Dimensions are 200–8192 logical pixels; scale must be
positive and at most 4, with integral physical dimensions no larger than 16384.

Labs can run side by side. Use a unique name per task or job. Mutating CLI
operations are serialized per runtime root. `down --all` really removes every
lab belonging to that user—do not use it as a shared-runner cleanup shortcut.

## Isolation boundaries

| Resource | Lab behavior |
|---|---|
| HOME, configuration, cache, data, application state, runtime | Private writable directories under `$XDG_RUNTIME_DIR/omalab/<name>/`. Removed by `down`. |
| Plugin code | Read-only live bind of the real checkout. Host edits appear; writes from inside the lab are denied. |
| Compositor and Wayland clients | Bubblewrap → headless Cage → Hyprland's private `LAB` output. No host Wayland/X11 socket or monitor. |
| Viewer | `show` opens an ordinary viewer through WayVNC's private UNIX socket; no TCP listener. `hide` closes only that lab's viewer. Clipboard sync, remote resize and system-key grabs are disabled. |
| Session D-Bus | Private by default. `--shared-bus` binds only the explicitly requested filesystem session-bus socket and re-enables Qt portal integration. |
| Audio | Private PipeWire with no hardware discovery or session manager, even with `--shared-bus`. Empty device lists are intentional. |
| Machine-control services | Idle/lock, battery power profiles, polkit and night light are disabled; the system bus is not mounted. |
| Theme | Theme and wallpaper copied into a private snapshot; `--theme mine` snapshots the current theme/background, not plugin settings. |
| Filesystem and processes | Private mount/PID namespaces, scratch HOME and `/proc`; selected system code is read-only. No arbitrary host HOME, artifact directory, input device or DRM card mounts. |
| Network | Private by default. `--network` explicitly shares host networking, including host loopback. |
| Environment and agent sockets | Environment rebuilt deliberately; arbitrary inherited secrets and agent sockets are not passed through. |
| Kernel and GPU | Shared host kernel and one GPU render node. **Not VM-grade isolation or a GPU denial-of-service boundary.** |

Use trusted plugin code only. Namespace isolation reduces accidental access;
it does not make a self-hosted runner safe for hostile pull requests. Opt-in
host services can have real side effects, and `down` cannot undo them. The
workflow running outside the lab still has the runner user's privileges.

## Local automation, SSH and CI

| Where you run it | What is required |
|---|---|
| Terminal in Omarchy | Installed stack, private runtime and render-node access. The graphical environment is needed only for `show`. |
| Local script or agent | Unique lab name, capture/log collection and scoped cleanup; no viewer or display approval needed for headless `up`/`shot`. |
| SSH or a user service | Correct user, owned `XDG_RUNTIME_DIR`, installed Omarchy/runtime and GPU access. Do not guess host display or bus sockets. |
| Dedicated self-hosted CI runner | Provisioned Omarchy/GPU/Bubblewrap stack, working user namespaces and trusted jobs; no active graphical desktop required. |
| Stock hosted runner or standalone container | Not supported without provisioning that stack and GPU access. There is no bundled desktop bootstrap, Docker image, X11 backend or `omalab test` command. |

See **[CI and automation](docs/CI.md)** for runner setup, environment handling,
security restrictions, artifact collection and an opt-in GitHub Actions example.
The runnable [smoke helper](examples/ci-smoke.sh) exercises startup, plugin
registration and rendering; it does not replace your plugin's unit tests,
behavioral assertions or visual review.

Run the same smoke check locally from your plugin checkout:

```sh
artifacts=$(mktemp -d)
"$HOME/.local/share/omalab/examples/ci-smoke.sh" "$PWD" "$artifacts"
```

Screenshots are not deterministic goldens out of the box. Pin the desktop,
shell, plugin versions, fonts and theme; control time-dependent data and fixture
state in your own tests. A hard-killed job or compositor failure can interrupt
cleanup. Disposable runner machines are preferable to accumulating state on a
shared desktop.

## Agent skill

Humans only need the CLI. The optional [omalab skill](skills/omalab/SKILL.md)
gives coding agents the safe development loop: unique labs, no unapproved
`show`, explicit credential/network/shared-bus decisions, real screenshot inspection,
and cleanup of only the lab they created.

The skill also includes [video and input recipes](skills/omalab/automation.md).
Recorders run through `exec` and export video from private storage. `omalab input`
uses a persistent lab-local WayVNC connection so virtual devices remain available
without a visible viewer; it never injects host input. There is no separate
`omalab record` command.

For agents that read the shared user skill directory, after the CLI installation
above:

```sh
mkdir -p "$HOME/.agents/skills"
ln -s "$HOME/.local/share/omalab/skills/omalab" "$HOME/.agents/skills/omalab"
```

Use your actual checkout path if it differs. Claude Code and Codex users can
link that same directory under their respective `~/.claude/skills/` and
`~/.codex/skills/` roots. Start a new agent session so it rescans skills.
The CLI installation itself does not alter agent configuration or require a
skill, and existing skill directories should not be overwritten.

## Troubleshooting and implementation

- Use `omalab log -n NAME` for the unfiltered shell log; `-f` follows it.
- Failed startup retains available `parent.log`, `compositor.log`, `shell.log`,
  `pipewire.log`, `bus.log`, `theme.log`, `vnc.log` and `viewer.log`. Collect
  diagnostic files before `down`.
- Only `show` launches a visible window. Window placement and normal focus
  follow the user's desktop policy; omalab issues no host focus, workspace,
  monitor or keyword calls. `hide` terminates only its recorded viewer.
- The ordinary viewer has not yet been exercised on the user's visible screen;
  private-socket framebuffer/input experiments are not full `show` proof.
- A missing runtime, denied render node or unavailable user namespace is a
  prerequisite failure, not a reason to fall back to the host display.

The [engineering reference](docs/HOW.md) describes the namespace and process
ownership contracts, rendering, teardown and bounded historical evidence.

## License

Code: [Apache-2.0](LICENSE). Header background: Omarchy's Tokyo Night wallpaper, captured with the omalab stamp at native 2× scale.
