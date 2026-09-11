---
name: omalab
description: Use when developing or testing an Omarchy shell plugin in an isolated omalab session, capturing plugin screenshots or videos, or exercising child-scoped pointer and keyboard input. Triggers include Omarchy plugin development, Quickshell plugin debugging, omalab, offscreen preview, and visual validation.
---

# Omalab

Use omalab as an optional workflow aid for trusted Omarchy shell-plugin work.
It is not a runtime dependency of a plugin and is not a sandbox for untrusted
code.

## Headless backend and permissions

The default backend is Bubblewrap → headless Cage → Hyprland's private `LAB`
output. It mounts no host Wayland/X11 socket, creates no host monitor and makes
no host compositor mutation. `up`, `shot`, IPC and cleanup do not need an active
graphical desktop or separate host-display approval. Only `show` launches an
ordinary visible viewer, and **requires explicit permission for this task**.

The installed Omarchy stack, an accessible GPU render node, Bubblewrap/user
namespaces and the private `omalab-setup` runtime are prerequisites. Setup is a
separate download/build step, not work performed by `up`; do not install system
packages or prepare missing dependencies without authorization. It prepares
`${XDG_DATA_HOME:-$HOME/.local/share}/omalab-runtime` (or `OMALAB_RUNTIME_DIR`),
including a patched Aquamarine 0.14.0 / ABI 13 library and missing viewer/parent
tools. It does not replace system libraries. Never export the sandbox's private
library search path into the host desktop.

The normal viewer and repeated show/hide were verified on a separate offscreen
X server, not by opening an unapproved window on the user's desktop. Missing
prerequisites are never permission to use the old host-output backend.

## Before acting

1. Read `omalab --help` for the installed CLI contract.
2. Consult the omalab project's [README](https://github.com/njpatel/omalab#readme)
   and [engineering reference](https://github.com/njpatel/omalab/blob/main/docs/HOW.md),
   or their local copies beside the installed CLI checkout, for isolation
   boundaries. These are omalab's docs, not the plugin repository's README.
3. Treat the plugin checkout as trusted code. The lab has private HOME/XDG,
   mount/PID/user/IPC and default network namespaces; arbitrary host HOME,
   inherited secrets, agent sockets and the system bus are not exposed.
   The kernel and GPU remain shared: this is not a VM-grade security sandbox.
4. Use a unique lab name for each task or concurrent agent. Do not reuse,
   replace or remove a lab you did not create.
5. Decide deliberately whether the plugin needs credentials or host services.
   Do not copy secrets into the lab unless the user explicitly authorizes it.
   Avoid `--shared-bus` and `--network` unless each needed integration is
   explicitly authorized. `--shared-bus` exposes only the requested filesystem
   session-bus socket, not the system bus. `--network` shares host networking,
   including host loopback and external services. Neither is a filtered allowlist.
   Never guess cross-session or cross-user socket paths.

## Conservative workflow

Use this order, adapting IPC targets and screenshot geometry to the plugin:

```text
omalab up <plugin-dir> -n <unique-name>
omalab ipc -n <unique-name> <target> <method> [args...]
omalab exec -n <unique-name> <command> [args...]
omalab input -n <unique-name> <operation> [args...]
omalab shot -n <unique-name> <artifact.png> [--size WxH] [--scale N]
omalab log -n <unique-name>
omalab down -n <unique-name>
```

- `up` mounts the real plugin checkout live and read-only. Edit on the host;
  lab processes cannot write back through that mount. Use `restart` when the
  shell must reload those edits.
- Prefer plugin IPC for controlled behavior. Use `exec` only for commands that
  are safe inside the lab environment and necessary for the task. `exec` starts
  in scratch HOME, not the host working directory; arbitrary host file paths
  are unavailable. Export private files through stdout with host redirection,
  for example `omalab exec -n <name> sh -c 'cat "$HOME/result.json"' > result.json`.
  `shot` accepts a host file destination itself without mounting its directory.
- Check the unfiltered shell log for QML errors, TypeErrors, binding loops and
  plugin-specific failures. Missing NetworkManager, Bluetooth and UPower are
  expected no-system-bus limitations; raw logs are not filtered. Missing
  credentials or state do not excuse unrelated plugin errors.
- Capture screenshots before cleanup. Inspect image content, not only command
  success or dimensions.
- A scale override restarts the lab shell for native rendering and again while
  restoring it. Expect transient panels and in-memory plugin state to reset.
  Size-only capture does not restart the shell.
- For stateful screenshots, start the lab at the target scale, drive the
  desired state, then capture without a scale override instead of resetting it.
- Copy any required logs, screenshots or other artifacts out of the disposable
  lab before `down`.

## Video and input

Use the [automation recipes](automation.md) for `wf-recorder` capture and
`omalab input` move/click/type/key operations. Recorders run through `exec`;
record to private storage, finalize, then export through stdout. Input uses the
lab-local persistent controller and the same private WayVNC socket as the viewer.
No visible viewer is necessary and no kernel-global injection is used.

Input coordinates are physical pixels in the original screenshot, including its
scale. Focus fields within the child before typing and verify the resulting UI,
not just tool exit status. Prefer stable plugin IPC when possible.

Start at the final scale before driving stateful UI. Finish and inspect a video
before tearing down the lab. Verify actual UI changes, not just successful
input-tool exit codes. Do not publish captures or install missing automation
tools without the user's authorization.

## Visibility and host safety

A normal lab runs headlessly without any window on the user's desktop.

- Never run `omalab show` without explicit permission for this task's visible
  inspection. An earlier preview approval is not blanket permission for future
  labs. Screenshot and video validation do not require showing the lab.
- Never issue host `hyprctl keyword`, focus, workspace-switch, special-workspace
  or direct window-dispatch commands. Do not modify physical monitor rules,
  host layer rules or desktop configuration. Use omalab's supported commands.
- Never compensate for a failed lab by manipulating the host desktop directly.
  Read logs and use the documented lab lifecycle instead.
- Do not call `omalab down --all` unless the user explicitly authorizes removal
  of every lab. Remove only the unique lab created for this task.
- Do not use `--shared-bus` or `--network` without explicit authorization.
  If authorized, account for real side effects through host services/network;
  teardown cannot undo them. The options are independent trust decisions.

## Completion checklist

Before reporting completion:

- Exercise the plugin through `ipc` or another consumer-visible action when
  applicable.
- Produce and visually inspect the requested screenshot at the requested size
  and scale.
- Review the lab log without filtering away real diagnostics.
- Preserve requested artifacts before cleanup.
- Run `omalab down -n <unique-name>` for only the lab created by this task.
- Report intentional missing credentials, empty state, isolated network,
  unavailable system services, private audio or scale-restart state loss as
  lab limitations, not as successful plugin behavior.

Installation is optional. Do not modify a user's agent configuration without
an explicit request; the CLI works without this skill or an agent.
