#!/bin/bash
set -euo pipefail
umask 077

fail() {
  printf 'omalab-ci: %s\n' "$*" >&2
  exit 1
}

[[ $# -ge 1 && $# -le 2 ]] || fail 'usage: ci-smoke.sh PLUGIN_DIR [ARTIFACT_DIR]'

PLUGIN_DIR=$(realpath -e -- "$1") || fail "plugin directory does not exist: $1"
[[ -d $PLUGIN_DIR ]] || fail "plugin path is not a directory: $PLUGIN_DIR"
[[ -f $PLUGIN_DIR/manifest.json ]] || fail "plugin manifest is missing: $PLUGIN_DIR/manifest.json"
PLUGIN_ID=$(jq -er '.id | select(type == "string" and length > 0)' "$PLUGIN_DIR/manifest.json") ||
  fail 'plugin manifest must contain a string id'
[[ $PLUGIN_ID =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ && $PLUGIN_ID != *..* ]] ||
  fail "invalid plugin id: $PLUGIN_ID"

ARTIFACT_INPUT=${2:-$PWD/omalab-ci-artifacts}
mkdir -p -- "$ARTIFACT_INPUT"
ARTIFACT_DIR=$(realpath -e -- "$ARTIFACT_INPUT") || fail "cannot resolve artifact directory: $ARTIFACT_INPUT"
[[ -d $ARTIFACT_DIR ]] || fail "artifact path is not a directory: $ARTIFACT_DIR"

OMALAB_COMMAND=${OMALAB_BIN:-omalab}
OMALAB_RESOLVED=$(command -v "$OMALAB_COMMAND") || fail "omalab executable not found: $OMALAB_COMMAND"
[[ -x $OMALAB_RESOLVED && ! -d $OMALAB_RESOLVED ]] || fail "omalab is not executable: $OMALAB_RESOLVED"
OMALAB_BIN=$(realpath -e -- "$OMALAB_RESOLVED")

for variable in XDG_RUNTIME_DIR WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE OMARCHY_PATH DBUS_SESSION_BUS_ADDRESS; do
  [[ -n ${!variable:-} ]] || fail "$variable is unavailable; launch the runner inside the active Omarchy session"
done
[[ -d $XDG_RUNTIME_DIR && -O $XDG_RUNTIME_DIR ]] || fail "XDG_RUNTIME_DIR is not an owned directory: $XDG_RUNTIME_DIR"
[[ -f $OMARCHY_PATH/shell/shell.qml ]] || fail "OMARCHY_PATH is not an Omarchy installation: $OMARCHY_PATH"
[[ -r /proc/sys/kernel/random/uuid ]] || fail 'the Linux UUID source is unavailable'
IFS= read -r LAB_UUID < /proc/sys/kernel/random/uuid
LAB_NAME=ci-${LAB_UUID//-/}
LAB_ROOT=${OMALAB_HOST_RUNTIME:-$XDG_RUNTIME_DIR}/omalab
LAB_PATH=$LAB_ROOT/$LAB_NAME
[[ ! -e $LAB_PATH && ! -L $LAB_PATH ]] || fail "refusing to reuse an existing lab: $LAB_NAME"

collect_logs() {
  local log failed=0
  mkdir -p -- "$ARTIFACT_DIR/logs" || return
  shopt -s nullglob
  for log in "$LAB_PATH"/*.log; do
    cp -p -- "$log" "$ARTIFACT_DIR/logs/${log##*/}" || failed=1
  done
  if [[ -f $LAB_PATH/meta.json ]]; then
    cp -p -- "$LAB_PATH/meta.json" "$ARTIFACT_DIR/logs/meta.json" || failed=1
  fi
  return "$failed"
}

cleanup() {
  local status=$?
  trap - EXIT INT TERM

  if [[ -d $LAB_PATH ]]; then
    if (( status != 0 )); then
      collect_logs || printf 'omalab-ci: could not copy all failure logs from %s\n' "$LAB_PATH" >&2
    fi
    if ! "$OMALAB_BIN" down -n "$LAB_NAME"; then
      printf 'omalab-ci: teardown failed for lab %s\n' "$LAB_NAME" >&2
      (( status != 0 )) || status=1
    fi
  fi

  exit "$status"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

"$OMALAB_BIN" up "$PLUGIN_DIR" -n "$LAB_NAME" --size 1280x800 --scale 1 --no-stamp
"$OMALAB_BIN" ipc -n "$LAB_NAME" shell listPlugins > "$ARTIFACT_DIR/plugin-registry.json"
jq -e --arg id "$PLUGIN_ID" 'any(.[]; .id == $id and .enabled == true)' \
  "$ARTIFACT_DIR/plugin-registry.json" >/dev/null || fail "plugin is not enabled in the shell registry: $PLUGIN_ID"
"$OMALAB_BIN" shot -n "$LAB_NAME" "$ARTIFACT_DIR/screenshot-1280x800@1.png" --size 1280x800 --scale 1
"$OMALAB_BIN" shot -n "$LAB_NAME" "$ARTIFACT_DIR/screenshot-1280x800@2.png" --size 1280x800 --scale 2
collect_logs

printf 'omalab CI smoke artifacts: %s\n' "$ARTIFACT_DIR"
