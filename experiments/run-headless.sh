#!/bin/bash
# Experimental, isolated-parent launch. Requires the separately built compatibility
# library documented in docs/HOW.md. This does not invoke the normal omalab backend.
set -euo pipefail
umask 077

fail() { printf 'headless experiment: %s\n' "$*" >&2; exit 1; }

inside() {
  [[ ${OMALAB_HEADLESS_EXPERIMENT:-} == 1 && -d /artifacts && -f /plugin/manifest.json ]] || fail 'missing isolated experiment mounts'
  mkdir -p "$HOME/.config/omarchy/plugins" "$HOME/.local/state/omarchy/current" "$HOME/.local/share" "$HOME/.cache" /lab/run /lab/tmp
  chmod 700 /lab/run
  local id section current=$HOME/.local/state/omarchy/current
  id=$(jq -er .id /plugin/manifest.json)
  [[ $id =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ && $id != *..* ]] || fail 'invalid plugin id'
  case $id in
    omarchy.idle|omarchy.lock|omarchy.battery|omarchy.polkit|omarchy.nightlight) fail 'machine-control plugins are not supported' ;;
  esac
  section=$(jq -r 'if (.kinds | index("bar-widget")) then .barWidget.defaultSection // "right" else "" end' /plugin/manifest.json)
  [[ -z $section || $section == left || $section == center || $section == right ]] || fail 'invalid defaultSection'
  ln -s /plugin "$HOME/.config/omarchy/plugins/$id"
  jq --arg id "$id" --arg section "$section" '
    .disabledPlugins = ["omarchy.idle","omarchy.lock","omarchy.battery","omarchy.polkit","omarchy.nightlight","omarchy.notifications"] |
    .plugins = [{id:$id}] |
    if $section != "" then .bar.layout[$section] += [{id:$id}] else . end
  ' "$OMARCHY_PATH/config/omarchy/shell.json" > "$HOME/.config/omarchy/shell.json"
  mkdir "$current/next-theme"
  cp -a "$OMARCHY_PATH/themes/tokyo-night/." "$current/next-theme/"
  omarchy-theme-set-templates > /artifacts/theme.log 2>&1
  mv "$current/next-theme" "$current/theme"
  local background
  for background in "$current/theme/backgrounds/"*; do
    [[ -f $background ]] || continue
    ln -s "$background" "$current/background"
    break
  done
  [[ -L $current/background ]] || fail 'default theme has no background'

  cat > /lab/hyprland.lua <<'CONFIG'
hl.config({
  misc = { disable_hyprland_logo=true, disable_splash_rendering=true, disable_watchdog_warning=true },
  xwayland = { enabled=false },
  animations = { enabled=false },
})
hl.monitor({output="LAB", mode="1280x800@60", position="0x0", scale=1})
hl.on("hyprland.start", function() hl.exec_cmd("env > /lab/child.env") end)
CONFIG
  cat > /lab/omalab-pipewire.conf <<'CONFIG'
context.properties = { core.daemon = true core.name = pipewire-0 }
context.spa-libs = { support.* = support/libspa-support }
context.modules = [
  { name = libpipewire-module-protocol-native }
  { name = libpipewire-module-client-node }
  { name = libpipewire-module-metadata }
  { name = libpipewire-module-access }
]
context.objects = [ { factory = metadata args = { metadata.name = default } } ]
CONFIG
  # All descendants share this PID namespace. Bubblewrap tears it down when
  # this command exits; logs already live outside its disposable state directory.
  export DBUS_SESSION_BUS_ADDRESS=unix:path=/lab/run/bus
  dbus-daemon --session --nofork --address="$DBUS_SESSION_BUS_ADDRESS" > /artifacts/bus.log 2>&1 &
  pipewire -c /lab/omalab-pipewire.conf > /artifacts/pipewire.log 2>&1 &
  env LD_LIBRARY_PATH=/aquamarine WLR_BACKENDS=headless WLR_HEADLESS_OUTPUTS=1 \
    WLR_RENDERER=gles2 WLR_RENDER_DRM_DEVICE="$RENDER_NODE" \
    /cage -d -- Hyprland --config /lab/hyprland.lua > /artifacts/compositor.log 2>&1 &
  local compositor=$! attempt key value
  for ((attempt=0; attempt<200; attempt++)); do
    if [[ -s /lab/child.env && -S /lab/run/bus && -S /lab/run/pipewire-0 ]]; then break; fi
    kill -0 "$compositor" 2>/dev/null || fail 'parent/child failed; inspect compositor.log'
    sleep 0.1
  done
  [[ -s /lab/child.env ]] || fail 'child did not become ready'
  while IFS='=' read -r key value; do
    case $key in WAYLAND_DISPLAY|HYPRLAND_INSTANCE_SIGNATURE) export "$key=$value" ;; esac
  done < /lab/child.env
  [[ -n ${WAYLAND_DISPLAY:-} && -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]] || fail 'missing child identity'
  # This output is created on the isolated child, never the host compositor.
  hyprctl output create headless LAB
  for ((attempt=0; attempt<100; attempt++)); do
    if hyprctl -j monitors | jq -e '.[] | select(.name=="LAB" and .width==1280 and .height==800 and .scale==1)' >/dev/null; then break; fi
    sleep 0.1
  done
  (( attempt < 100 )) || fail 'child output did not become ready'
  export OMALAB_STAMP
  OMALAB_STAMP=$(jq -cn --arg id "$id" --arg commit "$PLUGIN_COMMIT" --argjson dirty "$PLUGIN_DIRTY" --arg date "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '{plugin:$id,commit:$commit,dirty:$dirty,theme:"tokyo-night",size:"1280x800",scale:1,date:$date}')
  quickshell -n -p "$OMARCHY_PATH/shell" > /artifacts/shell.log 2>&1 &
  local shell_pid=$!
  for ((attempt=0; attempt<100; attempt++)); do
    if omarchy-shell shell ping >/dev/null 2>&1; then break; fi
    kill -0 "$shell_pid" 2>/dev/null || fail 'shell failed; inspect shell.log'
    sleep 0.1
  done
  (( attempt < 100 )) || fail 'shell IPC did not become ready'
  omarchy-shell shell listPlugins > /artifacts/plugin-registry.json
  jq -e --arg id "$id" 'any(.[]; .id==$id and .enabled)' /artifacts/plugin-registry.json >/dev/null || fail 'plugin not enabled'
  hyprctl -j layers > /artifacts/layers.json
  jq -e '.. | objects | select(.namespace?=="omarchy-bar")' /artifacts/layers.json >/dev/null || fail 'no real shell bar'
  hyprctl -j status > /artifacts/child-status.json
  hyprctl -j monitors > /artifacts/child-monitors.json
  # Shell ping precedes asynchronous wallpaper/theme loading. This proof runner
  # allows the initial frame to settle; inspect its PNG, not only its exit code.
  sleep 2
  timeout 15 grim -o LAB /artifacts/headless.png
  printf 'Isolated headless session ready; output LAB. No host display mounted.\n'
  if (( $# )); then "$@"; fi
}

if [[ ${1:-} == --inside ]]; then shift; inside "$@"; exit; fi
if [[ ${1:-} == --help || $# -lt 2 ]]; then
  cat <<'HELP'
Usage: experiments/run-headless.sh PLUGIN_DIR ARTIFACT_DIR [COMMAND [ARGS...]]

Runs the plugin in a Bubblewrap-isolated Hyprland session beneath headless Cage.
Captures real shell/plugin evidence, optionally runs COMMAND inside the lab, then
tears down the entire process namespace. Does not add host outputs or show a window.

Prerequisites: bubblewrap, cage, installed Omarchy dependencies and an Aquamarine
0.14.0 build with experiments/aquamarine-parent-versions.patch applied.
Set AQUAMARINE_LIBDIR to that build directory. CAGE_BIN may override cage's path.
RENDER_NODE may select an accessible /dev/dri/renderD* node (never a card device).

The isolated command sees /plugin (read-only), /artifacts (writable), private HOME,
and the child Wayland/Hyprland environment. It has no host network or system bus.
This is an experimental proof runner, not the normal omalab CLI or a supported
replacement for its show/hide and live-edit workflows. No downloads or installs.
HELP
  [[ ${1:-} == --help ]] && exit 0
  exit 2
fi
plugin=$(realpath -e -- "$1"); shift
[[ -f $plugin/manifest.json ]] || fail 'plugin manifest is missing'
mkdir -p -- "$1"
artifacts=$(realpath -e -- "$1"); shift
[[ -n ${AQUAMARINE_LIBDIR:-} ]] || fail 'set AQUAMARINE_LIBDIR to the patched experimental build'
library=$(realpath -e -- "$AQUAMARINE_LIBDIR")
[[ -f $library/libaquamarine.so.13 ]] || fail 'expected Aquamarine ABI 13 library'
cage=$(command -v "${CAGE_BIN:-cage}") || fail 'cage is not installed; set CAGE_BIN to a prepared binary'
cage=$(realpath -e -- "$cage")
render=${RENDER_NODE:-}
if [[ -z $render ]]; then
  for render in /dev/dri/renderD*; do [[ ! -c $render ]] || break; done
fi
[[ $render =~ ^/dev/dri/renderD[0-9]+$ && -c $render && -r $render && -w $render ]] || fail 'an accessible DRM render node is required; card devices are forbidden'
[[ -n ${XDG_RUNTIME_DIR:-} && -d $XDG_RUNTIME_DIR ]] || fail 'XDG_RUNTIME_DIR is unavailable'
[[ -n ${OMARCHY_PATH:-} && -f $OMARCHY_PATH/shell/shell.qml ]] || fail 'OMARCHY_PATH must identify the installed Omarchy source'
omarchy=$(realpath -e -- "$OMARCHY_PATH")
mkdir -p "$XDG_RUNTIME_DIR/omalab"
state=$(mktemp -d "$XDG_RUNTIME_DIR/omalab/.headless-XXXXXXXX")
trap 'rm -rf -- "$state"' EXIT
commit=$(git -C "$plugin" rev-parse --short=8 HEAD 2>/dev/null) || commit=unversioned
dirty=false
if [[ $commit != unversioned && -n $(git --no-optional-locks -C "$plugin" status --porcelain) ]]; then dirty=true; fi
bwrap --unshare-all --new-session --die-with-parent \
  --ro-bind /usr /usr --ro-bind /etc /etc --ro-bind /sys /sys \
  --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib /lib64 \
  --proc /proc --dev /dev --dev-bind "$render" "$render" \
  --tmpfs /run --tmpfs /tmp --bind "$state" /lab \
  --bind "$artifacts" /artifacts --ro-bind "$plugin" /plugin \
  --ro-bind "$library" /aquamarine --ro-bind "$cage" /cage \
  --ro-bind "$omarchy" /omarchy \
  --ro-bind "$(realpath -- "${BASH_SOURCE[0]}")" /runner \
  --clearenv --setenv HOME /lab/home --setenv XDG_RUNTIME_DIR /lab/run \
  --setenv XDG_CONFIG_HOME /lab/home/.config --setenv XDG_STATE_HOME /lab/home/.local/state \
  --setenv XDG_DATA_HOME /lab/home/.local/share --setenv XDG_CACHE_HOME /lab/home/.cache \
  --setenv TMPDIR /lab/tmp --setenv LANG C.UTF-8 \
  --setenv PATH /usr/bin:/omarchy/bin --setenv OMARCHY_PATH /omarchy \
  --setenv QT_NO_XDG_DESKTOP_PORTAL 1 --setenv QT_QPA_PLATFORM wayland \
  --setenv QS_DISABLE_FILE_WATCHER 1 --setenv QS_NO_RELOAD_POPUP 1 \
  --setenv OMALAB_HEADLESS_EXPERIMENT 1 --setenv RENDER_NODE "$render" \
  --setenv PLUGIN_COMMIT "$commit" --setenv PLUGIN_DIRTY "$dirty" --chdir /lab \
  /bin/bash /runner --inside "$@"
