# Continuous integration

omalab can provide a startup and rendering smoke check for an Omarchy shell
plugin, but it is not a conventional headless test runner. It needs a real
parent Hyprland/Wayland session and it runs the plugin as the desktop user.
Use a dedicated, disposable Omarchy desktop session for trusted code only.

The measured compatibility baseline is Omarchy 4.0.2, Hyprland 0.56.2,
Quickshell 0.3.1 and PipeWire 1.6.8. Other combinations have not been verified.
Stock GitHub-hosted runners, containers, and headless machines without a parent
Omarchy Hyprland session are unsupported.

## What the smoke helper proves

[`../examples/ci-smoke.sh`](../examples/ci-smoke.sh) starts one uniquely named,
hidden lab at 1280x800 logical pixels, confirms that the plugin is enabled in
the shell registry, and captures:

- `plugin-registry.json`
- `screenshot-1280x800@1.png`
- `screenshot-1280x800@2.png`
- the lab's available logs under `logs/`

This checks generic startup, registration and rendering. It does **not** assert
plugin-specific behavior such as displayed values, IPC results, daemon state,
notification actions or error handling. Add those assertions in the plugin
repository using its stable IPC or command interface; do not treat the PNGs as
byte-for-byte or pixel-perfect golden files. Fonts, theme assets, graphics
drivers, compositor and shell versions, and frame timing can all change pixels
without indicating a plugin regression.

The helper never calls `show` or `hide`, never changes a visible workspace or
focus, and never uses `down --all`. Its exit trap copies every available lab log
before teardown on failure, removes only the lab name it created, and preserves
the failing status. It does not change the caller's working directory, `HOME`,
omalab defaults or other labs.

Run it from an already active Omarchy session:

```sh
OMALAB_BIN=omalab ./examples/ci-smoke.sh /path/to/plugin /path/to/artifacts
```

`PLUGIN_DIR` is required. `ARTIFACT_DIR` defaults to
`./omalab-ci-artifacts`. `OMALAB_BIN` may name an executable on `PATH` or an
explicit path to the installed CLI.

Pass the directory containing `manifest.json`, including a subdirectory for a
monorepo. Keep CI artifacts outside the plugin checkout, as the workflow does,
to avoid adding generated files to the code under inspection. The example uses
a run/attempt-specific artifact directory so a failed run cannot upload an old
successful run's screenshots.

The exit trap covers ordinary failures and catchable signals, not SIGKILL,
power loss or a dead parent compositor. A runner can also disappear before
artifact upload runs. Inspect any leftover labs and reset the dedicated
session/machine before reusing a failed worker; cleanup is not containment.

## Prepare a self-hosted runner

Use a machine, VM or account dedicated to this purpose rather than a personal
desktop. The runner user must also be the user logged into the graphical
Omarchy session; do not run the runner as root or as a separate service user.

1. Install omalab for that user from
   <https://github.com/njpatel/omalab>, along with the runtime dependencies
   listed in its README.
2. Log in graphically to a normal Omarchy session. Keep that parent session
   running and the machine unsuspended for the entire job. Lock-screen and
   suspend/resume behavior are not part of the verified runner baseline;
   provision session availability deliberately on the dedicated worker.
   Omalab does not disable the host's idle, locking or power policies.
3. In GitHub, create a self-hosted runner for only the trusted repository or a
   tightly restricted runner group. Follow GitHub's current registration
   commands and add a custom `omalab` label.
4. Open a terminal **inside that Omarchy session**, enter the runner directory,
   check the inherited environment, and launch the runner in the foreground:

   ```bash
   (
   for name in XDG_RUNTIME_DIR WAYLAND_DISPLAY \
     HYPRLAND_INSTANCE_SIGNATURE OMARCHY_PATH DBUS_SESSION_BUS_ADDRESS; do
     [[ -n ${!name:-} ]] || { printf 'missing %s\n' "$name" >&2; exit 1; }
   done
   [[ -d $XDG_RUNTIME_DIR && -O $XDG_RUNTIME_DIR ]] || { printf 'invalid XDG_RUNTIME_DIR ownership\n' >&2; exit 1; }
   [[ -f $OMARCHY_PATH/shell/shell.qml ]] || { printf 'invalid OMARCHY_PATH\n' >&2; exit 1; }
   command -v omalab >/dev/null || { printf 'omalab is not on PATH\n' >&2; exit 1; }

   ./run.sh
   )
   ```

Launching the runner there is important: it inherits the session's real
`XDG_RUNTIME_DIR`, `WAYLAND_DISPLAY`, `HYPRLAND_INSTANCE_SIGNATURE`,
`OMARCHY_PATH` and D-Bus session address. Do not invent a display such as
`wayland-1`, select the newest Hyprland signature, copy socket paths from
another process, or add host-wide compositor rules to make a detached runner
work.

An SSH login normally lacks the graphical environment. A system service,
container, login-time agent or long-lived terminal multiplexer may run as the
right user while still holding missing or stale display, compositor and session
bus values. Static service `Environment=` entries are especially unsafe because
the sockets and Hyprland signature change across graphical sessions. Start the
runner from a fresh terminal in the current session instead.

Stop the runner before logging out or restarting Omarchy. After every graphical
session or compositor restart, launch a fresh runner process from a fresh
terminal so it receives the new environment. A runner surviving the restart
must not continue accepting jobs with its old values.

### Controlling an existing lab over SSH

`up` needs the host session's graphical environment. Commands addressing an
existing lab recover its compositor and bus from that lab's metadata. They
still need the matching desktop user, correct `XDG_RUNTIME_DIR`, `OMARCHY_PATH`
and an installed `omalab` on `PATH`. When your SSH login provides that context:

```sh
ssh -t lab-host 'omalab exec -n dev bash'
ssh lab-host 'omalab ipc -n dev shell listPlugins'
```

Here `lab-host` is your configured SSH host and `dev` is a lab you already
created. `exec` changes environment, not working directory: use `cd "$HOME"`
inside that shell to work in the scratch home. This is not an SSH backend or
a way to start a desktop-free lab. If session context is missing, establish it
from the actual desktop session rather than guessing sockets or changing users.

## Trust boundary

A scratch lab `HOME` and private lab bus are isolation from normal desktop
configuration, not credential containment or a security sandbox. Plugin code
still runs as the runner user and can inherit arbitrary job environment
variables and agent sockets, read the host filesystem and `/proc`, use the
host network and system bus, and deliberately connect to graphical session
services. Never:

- run code from an untrusted fork or contributor on this runner;
- trigger it from `pull_request` for fork code;
- use `pull_request_target` to check out or execute pull-request code;
- expose repository, organization, cloud or signing secrets to the smoke job;
- share a personal-desktop runner with repositories whose maintainers are not
  equally trusted.

Use manual `workflow_dispatch` runs from trusted refs and restrict who can
modify or dispatch the workflow. A self-hosted runner is persistent state: a
malicious job can affect later jobs even after its lab is removed. Recreate or
reset the disposable runner environment when its trust can no longer be
assumed.

Screenshots, plugin registry output and logs may contain credentials, tokens,
private data, filesystem paths or rendered notifications produced by the
plugin. Review them before sharing, keep artifact retention short, and limit
repository access. Avoid passing secrets to the job in the first place.

## Serialize access to the desktop

Run exactly one runner process against a given Omarchy session and do not attach
multiple runner registrations to the same desktop. One GitHub runner process
accepts one job at a time, which is the cross-repository serialization boundary
when that is the only process using the session.

The example workflow also sets a repository-scoped `concurrency` group. That
prevents overlapping manual jobs in one repository, but GitHub concurrency
groups do not serialize jobs from different repositories. The single runner
process is therefore still required. Do not run unrelated desktop automation
in the session while an omalab job is active.

## GitHub Actions example

Copy the helper into the plugin repository as `ci/omalab-smoke.sh`, retain its
executable bit, and copy
[`../examples/github-actions.yml`](../examples/github-actions.yml) to a workflow
under `.github/workflows/`. The example:

- has only a `workflow_dispatch` trigger;
- targets `[self-hosted, linux, omalab]`;
- accepts `omalab` from `PATH`, or an optional repository Actions variable named
  `OMALAB_BIN` containing the installed executable path;
- pins the official checkout and artifact actions to verified release commits;
- uploads the artifact directory with `always()`, including failure logs when
  the helper was able to create a lab.

The action revisions used by the example are the official
[`actions/checkout` v7.0.1 commit](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1)
and
[`actions/upload-artifact` v7.0.1 commit](https://github.com/actions/upload-artifact/commit/043fb46d1a93c77aae656e7c1c64a875d1fc6a0a).
Review and deliberately update those pins rather than replacing them with a
floating branch.
Use an up-to-date Actions runner: checkout's Node 24 runtime requires runner
2.327.1 or newer. This upload example targets GitHub.com; GitHub Enterprise
Server requires an artifact action version supported by that server, as noted
in the [official artifact action documentation](https://github.com/actions/upload-artifact#ghes-support).

This repository's workflow example is configuration guidance. Deployment to a
remote GitHub self-hosted runner and execution as a GitHub Actions job have not
been verified.

The helper itself has been exercised locally in a real Omarchy session against
the bundled service plugin. The successful run produced registry output, both
native-size screenshots and all available logs, then removed its lab. A forced
artifact-write failure retained the lab logs, returned a nonzero status and
still removed only its own lab. That local verification is separate from
deploying the example workflow on GitHub.
