#!/bin/sh
# Lutris only looks for service icons under the per-user runtime directory, and
# that directory is not writable while the flatpak is built. Seed the ZFSC icon
# on first launch, then hand over to the normal Lutris entry point.
set -eu

runtime_dir="${LUTRIS_RUNTIME_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/lutris/runtime}"
icon="${runtime_dir}/icons/hicolor/scalable/apps/zfsc.svg"

if [ ! -f "$icon" ]; then
    mkdir -p "$(dirname "$icon")"
    cp /app/share/zfsc/zfsc.svg "$icon"
fi

exec lutris "$@"
