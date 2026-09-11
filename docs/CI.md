# Continuous integration

omalab provides a headless startup and rendering smoke check for an Omarchy
shell plugin. Its default backend is Bubblewrap → headless Cage → Hyprland's
private `LAB` output. **No active graphical desktop or host compositor socket
is needed.** Use a dedicated, disposable, provisioned runner for trusted code.

The compatibility target is Omarchy 4.0.2, Hyprland 0.56.2, Quickshell 0.3.1,
PipeWire 1.6.8 and the private patched Aquamarine 0.14.0 (ABI 13) runtime.
Headless does not mean dependency-free: the worker needs GPU render-node
access, Bubblewrap with user namespaces, and the installed Omarchy stack.
Vanilla GitHub-hosted runners and unprovisioned containers remain unsupported
without supplying that stack and GPU access.

## What the smoke helper checks

[`../examples/ci-smoke.sh`](../examples/ci-smoke.sh) starts one uniquely named,
hidden lab at 1280x800 logical pixels, confirms that the plugin is enabled in
the shell registry, and captures:

- `plugin-registry.json`
- `screenshot-1280x800@1.png`
- `screenshot-1280x800@2.png`
- available logs, `meta.json` and `supervisor-info.json` under `logs/`

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

Run it as the provisioned runner user; no graphical session is required:

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
power loss or a failed namespace keeper. A runner can also disappear before
artifact upload runs. Inspect any leftover labs and reset the dedicated
machine before reusing a failed worker; cleanup is not a security boundary.

## Prepare a self-hosted runner

Use a machine or account dedicated to this purpose rather than a personal
desktop. A VM must still expose a suitable GPU render node; omalab does not
provision GPU virtualization. Run the worker unprivileged, not as root.

1. Install the Omarchy stack and runtime dependencies from the
   [README](../README.md#requirements), including Bubblewrap and util-linux's
   `nsenter`. Ensure the worker can use unprivileged user namespaces and read
   and write its assigned `/dev/dri/renderD*` node. Do not grant input devices
   or DRM card access as a workaround.
2. Install omalab and run `omalab-setup` as that worker user, outside the job.
   Setup needs additional build/download dependencies and prepares a private
   patched Aquamarine library; it does not replace system libraries. Its
   default is `${XDG_DATA_HOME:-$HOME/.local/share}/omalab-runtime`. If you use
   `OMALAB_RUNTIME_DIR`, pass the same value to jobs. No build runs on `up`.
3. Provide an owned, live `XDG_RUNTIME_DIR` and set `OMARCHY_PATH` to the installed
   Omarchy source. A user service or SSH session can provide this context.
   Keep the worker awake and available for the job; omalab does not change
   machine idle, locking or power policies.
4. Register a self-hosted runner only for the trusted repository or a tightly
   restricted runner group, following GitHub's current registration commands.
   Add a custom `omalab` label. Check the runtime context before launching:

   ```bash
   (
   for name in XDG_RUNTIME_DIR OMARCHY_PATH; do
     [[ -n ${!name:-} ]] || { printf 'missing %s\n' "$name" >&2; exit 1; }
   done
   [[ -d $XDG_RUNTIME_DIR && -O $XDG_RUNTIME_DIR ]] || { printf 'invalid XDG_RUNTIME_DIR ownership\n' >&2; exit 1; }
   [[ -f $OMARCHY_PATH/shell/shell.qml ]] || { printf 'invalid OMARCHY_PATH\n' >&2; exit 1; }
   command -v omalab >/dev/null || { printf 'omalab is not on PATH\n' >&2; exit 1; }

   ./run.sh
   )
   ```

The helper intentionally does not require `WAYLAND_DISPLAY`,
`HYPRLAND_INSTANCE_SIGNATURE` or `DBUS_SESSION_BUS_ADDRESS`. The lab creates its
own display and private session bus. Do not invent display names, select the
newest compositor directory, copy other users' socket paths or install host
compositor rules. No visible viewer is needed in CI.

The runtime directory must belong to the runner user and remain available for
the job. Long-lived services must be provisioned with that user context and
access to the installed stack; a stale or removed runtime directory is not
fixed by borrowing a desktop session's sockets. `show` alone would require the
current graphical environment and explicit permission; CI must not call it.

### Controlling an existing lab over SSH

Both new and existing labs can be controlled over SSH as the same provisioned
user, with the correct owned `XDG_RUNTIME_DIR`, `OMARCHY_PATH`, runtime and CLI:

```sh
ssh -t lab-host 'omalab exec -n dev bash'
ssh lab-host 'omalab ipc -n dev shell listPlugins' > artifacts/plugin-registry.json
```

`lab-host` is your configured SSH host and `dev` is a lab you own. `exec` starts
inside the same namespaces in **scratch HOME**, not the host working directory.
Arbitrary host paths, including CI artifact directories, are not mounted.
Keep fixtures private and export a generated file through stdout:

```sh
omalab exec -n dev sh -c 'cat "$HOME/result.json"' > artifacts/result.json
omalab log -n dev > artifacts/shell.log
```

`shot` accepts a host destination itself and streams the actual child capture
there. The helper's artifact directory remains outside the lab. SSH is only
transport to the CLI, not a separate omalab backend.

## Trust boundary

The lab has private mount/PID/user/IPC namespaces, a rebuilt environment and
scratch HOME/XDG state. Plugin code is a read-only live mount. Host HOME,
arbitrary inherited tokens/agent sockets, host display sockets, input devices
and the system bus are not exposed. Host-side edits to the checkout remain
visible; the lab cannot write back through that mount.

Networking is private by default. `--network` explicitly shares host networking,
including loopback and external services; `--shared-bus` independently exposes
only the requested filesystem session-bus socket. These opt-ins weaken the
boundary and should not be added to generic smoke jobs. If a plugin needs them,
authorize that integration deliberately and do not guess cross-session sockets.
No credentials or personal fixtures should be copied implicitly. Missing
NetworkManager, Bluetooth and UPower are expected no-system-bus limitations;
logs remain raw so real plugin errors are still visible.

This is **not VM-grade isolation**: the host kernel and GPU remain shared.
More importantly, checkout actions, job scripts and other steps run outside
the lab with the runner user's privileges. Never:

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

## Control worker concurrency

Use one runner process per dedicated worker and unique lab names per job. The
example workflow sets a repository-scoped `concurrency` group, but GitHub's
groups do not serialize jobs from different repositories. The CLI can own
distinct concurrent labs; that does not isolate host-side jobs, GPU resource
contention or artifact paths from each other.

Keep runtime setup/updates outside active jobs and never replace the private
runtime while labs use it. Do not use `down --all` to recover shared workers;
collect evidence and remove only the failed job's owned lab. Reset the worker
when ownership or trust cannot be established.

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

The updated helper was exercised locally with the integrated isolated backend.
It produced registry output, 1280x800 and native 2560x1600 screenshots, and all
available service logs before removing its own lab. An actual artifact-write
failure returned nonzero, retained diagnostics (including namespace metadata)
and still performed scoped teardown. No active graphical desktop was used by
the helper. That local verification is separate from remote GitHub deployment.
