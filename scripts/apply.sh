#!/usr/bin/env bash
# Copy the ZFSC service into a Lutris source tree.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src="${1:-$root/build/lutris}"

if [[ ! -f "$src/lutris/services/__init__.py" ]]; then
    echo "error: not a Lutris source tree: $src" >&2
    exit 1
fi

python3 "$root/scripts/apply.py" "$src"

echo "applied ZFSC service to: $src"
