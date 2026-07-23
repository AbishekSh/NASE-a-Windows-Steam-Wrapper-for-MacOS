#!/bin/zsh
set -euo pipefail

script_dir=${0:A:h}
repo_root=${script_dir:h}
release_tag=20260510
python_version=3.13.13
machine=${NASE_PYTHON_ARCH:-$(uname -m)}
cache_root=${NASE_RUNTIME_CACHE_DIR:-$repo_root/.build/nase-runtime-cache}
output_root=${NASE_PYTHON_RUNTIME_DIR:-$repo_root/.build/nase-python-$machine}

case "$machine" in
    arm64)
        artifact="cpython-$python_version+$release_tag-aarch64-apple-darwin-install_only_stripped.tar.gz"
        expected_sha256="16d2332d950178968534e65fe09f01f876d13af1147176fd0c77a74c9e4d1a4b"
        ;;
    x86_64)
        artifact="cpython-$python_version+$release_tag-x86_64-apple-darwin-install_only_stripped.tar.gz"
        expected_sha256="8937475b0b8536d391270da4510488cb41ecd21040b63f9d8f84a8b1cdd491fc"
        ;;
    *)
        print -u2 "Unsupported Python runtime architecture: $machine"
        exit 1
        ;;
esac

runtime="$output_root/python"
python="$runtime/bin/python3"
if [[ -x "$python" ]] && "$python" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 13) else 1)'; then
    print "$runtime"
    exit 0
fi

mkdir -p "$cache_root" "$output_root"
archive="$cache_root/$artifact"
url="https://github.com/astral-sh/python-build-standalone/releases/download/$release_tag/${artifact/+/%2B}"
partial="$archive.partial"

if [[ -f "$archive" ]]; then
    actual_sha256=$(shasum -a 256 "$archive" | awk '{print $1}')
    if [[ "$actual_sha256" != "$expected_sha256" ]]; then
        rm -f -- "$archive"
    fi
fi

if [[ ! -f "$archive" ]]; then
    rm -f -- "$partial"
    curl --fail --location --show-error --output "$partial" "$url"
    actual_sha256=$(shasum -a 256 "$partial" | awk '{print $1}')
    if [[ "$actual_sha256" != "$expected_sha256" ]]; then
        rm -f -- "$partial"
        print -u2 "Bundled Python checksum mismatch: expected $expected_sha256, got $actual_sha256"
        exit 1
    fi
    mv "$partial" "$archive"
fi

extract_root=$(mktemp -d /tmp/nase-python-runtime.XXXXXX)
trap 'rm -rf -- "$extract_root"' EXIT
tar -xzf "$archive" -C "$extract_root"
if [[ ! -x "$extract_root/python/bin/python3" ]]; then
    print -u2 "Bundled Python archive did not contain python/bin/python3"
    exit 1
fi

rm -rf -- "$runtime"
mv "$extract_root/python" "$runtime"
"$python" -c 'import ssl, sqlite3, sys, urllib.request; assert sys.version_info[:2] == (3, 13)'
print "$runtime"
