#!/usr/bin/env bash
# Fetch the pinned Lutris commit into a shallow source checkout.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dest="${1:-$root/build/lutris}"
ref="${LUTRIS_REF:-eace36e97bd0e4d65bcb361b0d785d75433c65e9}"
repo="${LUTRIS_REPO:-https://github.com/lutris/lutris.git}"

if [[ -e "$dest" && ! -d "$dest/.git" ]]; then
    echo "error: $dest exists but is not a git checkout" >&2
    exit 1
fi

if [[ ! -d "$dest/.git" ]]; then
    mkdir -p "$dest"
    git -C "$dest" init -q
    git -C "$dest" remote add origin "$repo"
fi

git -C "$dest" fetch --depth 1 origin "$ref"
git -C "$dest" checkout --detach --force FETCH_HEAD

echo "checked out Lutris $ref in $dest"
