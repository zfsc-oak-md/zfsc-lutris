#!/usr/bin/env bash
# Copy the ZFSC service into a Lutris source tree and install its icon.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src="${1:-$root/build/lutris}"

if [[ ! -f "$src/lutris/services/__init__.py" ]]; then
    echo "error: not a Lutris source tree: $src" >&2
    exit 1
fi

python3 "$root/scripts/apply.py" "$src"

runtime="${LUTRIS_RUNTIME_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/lutris/runtime}"
icon_dir="$runtime/icons/hicolor/scalable/apps"
mkdir -p "$icon_dir"
cp "$root/assets/zfsc.svg" "$icon_dir/zfsc.svg"

echo "installed icon: $icon_dir/zfsc.svg"
echo "applied ZFSC service to: $src"
