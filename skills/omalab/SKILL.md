---
name: omalab
description: Use when developing or testing an Omarchy shell plugin in an isolated omalab session, capturing plugin screenshots or videos, or exercising child-scoped pointer and keyboard input. Triggers include Omarchy plugin development, Quickshell plugin debugging, omalab, offscreen preview, and visual validation.
---

# Omalab

Use omalab as an optional workflow aid for trusted Omarchy shell-plugin work.
It is not a runtime dependency of a plugin and is not a sandbox for untrusted
code.

## Host-display safety warning

The current backend creates a real `OMALAB-*` virtual output on the host
compositor. Offscreen placement does not hide it from display settings, bars,
monitor-management services or the host pointer layout. Desktop disruption has
been reported; previous narrow before/after checks do not establish safety on
an actively used desktop.

Do not automatically run `up` on a personal desktop. Explain this host-display
side effect and obtain explicit approval for the current task, or use a
dedicated disposable desktop session. Installing this skill or asking for
screenshots is not approval to alter the host monitor layout. If disruption
is reported, stop launching labs and inspect existing state without creating
another output to reproduce it. This warning is not a backend fix.

The repository now includes `experiments/run-headless.sh`, a separately verified
isolated-parent proof runner. It requires Bubblewrap, Cage and a patched
Aquamarine build; it is not the default backend or a substitute for the CLI's
full lifecycle. Read the engineering reference before an explicitly requested
experiment. Do not install system packages, replace system libraries or remove
the host-display warning merely because the proof runner works.

## Before acting

1. Read `omalab --help` for the installed CLI contract.
2. Consult the omalab project's [README](https://github.com/njpatel/omalab#readme)
   and [engineering reference](https://github.com/njpatel/omalab/blob/main/docs/HOW.md),
   or their local copies beside the installed CLI checkout, for isolation
   boundaries. These are omalab's docs, not the plugin repository's README.
3. Treat the plugin checkout as trusted code running as the current user. The
   lab has a scratch HOME/XDG environment, but it can still access the
   filesystem, network, `/proc` and system bus. Inherited environment variables
   and agent sockets may expose credentials; scratch HOME is not containment.
4. Use a unique lab name for each task or concurrent agent. Do not reuse,
   replace or remove a lab you did not create.
5. Decide deliberately whether the plugin needs credentials or host services.
   Do not copy secrets into the lab unless the user explicitly authorizes it.
   Avoid `--shared-bus`; use it only when the user authorizes access to host
   session services and the plugin genuinely requires them.

## Conservative workflow

Use this order, adapting IPC targets and screenshot geometry to the plugin:

```text
omalab up <plugin-dir> -n <unique-name>
omalab ipc -n <unique-name> <target> <method> [args...]
omalab exec -n <unique-name> <command> [args...]
omalab shot -n <unique-name> <artifact.png> [--size WxH] [--scale N]
omalab log -n <unique-name>
omalab down -n <unique-name>
```

- `up` loads the real plugin checkout through a symlink. Use `restart` after
  edits when the shell must reload.
- Prefer plugin IPC for controlled behavior. Use `exec` only for commands that
  are safe inside the lab environment and necessary for the task.
- Check the unfiltered shell log for QML errors, TypeErrors, binding loops and
  plugin-specific failures. Do not dismiss errors merely because credentials
  or state are intentionally absent.
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

Use the [tested automation recipes](automation.md) for optional `wf-recorder`
video capture, `wtype` keyboard input and child-only Hyprland pointer actions.
Always route them through `omalab exec -n <owned-lab>`; never target the host
or use kernel-global input injection as a substitute. The recipes cover the
pointer-frame requirement for clicks on the verified Hyprland version.

Start at the final scale before driving stateful UI. Finish and inspect a video
before tearing down the lab. Verify actual UI changes, not just successful
input-tool exit codes. Do not publish captures or install missing automation
tools without the user's authorization.

## Visibility and host safety

A normal lab remains parked on a negative-coordinate headless output.

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
- Do not use `--shared-bus` without explicit authorization. If it was
  authorized, remember that lab commands and plugins can reach host session
  services.

## Completion checklist

Before reporting completion:

- Exercise the plugin through `ipc` or another consumer-visible action when
  applicable.
- Produce and visually inspect the requested screenshot at the requested size
  and scale.
- Review the lab log without filtering away real diagnostics.
- Preserve requested artifacts before cleanup.
- Run `omalab down -n <unique-name>` for only the lab created by this task.
- Report any intentional missing credentials, empty state, private-audio
  behavior or scale-restart state loss as a lab limitation, not as successful
  plugin behavior.

Installation is optional. Do not modify a user's agent configuration without
an explicit request; the CLI works without this skill or an agent.
