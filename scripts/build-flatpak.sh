#!/usr/bin/env bash
# Build the ZFSC Lutris flatpak and export a local repository.
#
# The manifest layers a small module on top of the Flathub net.lutris.Lutris
# app, so this only needs flatpak-builder plus that app and its runtime; it
# does not compile Lutris itself. See docs/flatpak.md.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
app_id="io.github.zfsc_oak_md.ZfscLutris"
manifest="$root/flatpak/${app_id}.yml"
build_dir="${FLATPAK_BUILD_DIR:-$root/build/flatpak-build}"
repo_dir="${FLATPAK_REPO_DIR:-$root/build/flatpak-repo}"
bundle="$root/build/${app_id}.flatpak"
base_ref="net.lutris.Lutris//stable"
runtime_ref="org.gnome.Platform//51"
sdk_ref="org.gnome.Sdk//51"
gpg_key="${FLATPAK_GPG_KEY:-}"
expected_base_commit="${FLATPAK_BASE_COMMIT:-}"
make_bundle=1

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Build $app_id and update a local flatpak repository.

Options:
  --no-bundle          do not also write $app_id.flatpak
  --build-dir DIR      build directory (default: $build_dir)
  --repo DIR           repository directory (default: $repo_dir)
  -h, --help           show this help

Environment:
  FLATPAK_GPG_KEY      GPG key ID used to sign the repository and bundle
  FLATPAK_BASE_COMMIT  fail unless net.lutris.Lutris is this commit
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-bundle) make_bundle=0 ;;
        --build-dir)
            build_dir="$2"
            shift
            ;;
        --repo)
            repo_dir="$2"
            shift
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

for tool in flatpak flatpak-builder; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "error: $tool not found; install flatpak and flatpak-builder" >&2
        exit 1
    fi
done

missing=()
for ref in "$sdk_ref" "$runtime_ref" "$base_ref"; do
    if ! flatpak info --user "$ref" >/dev/null 2>&1; then
        missing+=("$ref")
    fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
    cat >&2 <<EOF
error: missing flatpak refs: ${missing[*]}

Install them first:
  flatpak remote-add --if-not-exists --user flathub https://flathub.org/repo/flathub.flatpakrepo
  flatpak install --user flathub $sdk_ref $runtime_ref $base_ref

The base app is what gets copied into the build, so installing
net.lutris.Lutris (and its Wine base runtime) is required.
EOF
    exit 1
fi

mkdir -p "$(dirname "$repo_dir")"

base_commit="$(flatpak info --user --show-commit "$base_ref")"
if [[ -n "$expected_base_commit" && "$base_commit" != "$expected_base_commit" ]]; then
    echo "error: base app is $base_commit, expected $expected_base_commit" >&2
    echo "run 'flatpak update --user $base_ref' or unset FLATPAK_BASE_COMMIT" >&2
    exit 1
fi

builder_args=(--user --force-clean --repo="$repo_dir")
repo_args=(--prune)
# The module edits files that came from the base app. rofiles-fuse makes those
# read-only (and cannot be used at all inside org.flatpak.Builder), so build
# without it.
builder_args+=(--disable-rofiles-fuse)
if [[ -n "$gpg_key" ]]; then
    builder_args+=("--gpg-sign=$gpg_key")
    repo_args+=("--gpg-sign=$gpg_key")
fi

echo "building against $base_commit"
flatpak-builder "${builder_args[@]}" "$build_dir" "$manifest"
flatpak build-update-repo "${repo_args[@]}" "$repo_dir"

verify_flag=""
if [[ -z "$gpg_key" ]]; then
    verify_flag=" --no-gpg-verify"
fi

echo
echo "Built $app_id"
echo

if [[ $make_bundle -eq 1 ]]; then
    bundle_args=(--runtime-repo=https://flathub.org/repo/flathub.flatpakrepo)
    if [[ -n "$gpg_key" ]]; then
        bundle_args+=(--gpg-sign="$gpg_key")
    fi
    flatpak build-bundle "${bundle_args[@]}" "$repo_dir" "$bundle" "$app_id" stable
    echo "  flatpak install --user --bundle \"$bundle\""
    echo
fi

echo "Or add the local repository, which also gives you updates:"
echo
echo "  flatpak remote-add --user --if-not-exists$verify_flag zfsc-local \"file://$repo_dir\""
echo "  flatpak install --user zfsc-local $app_id"
