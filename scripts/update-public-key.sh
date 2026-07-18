#!/bin/zsh
set -euo pipefail

if [[ $# -ne 1 ]]; then
    print -u2 "usage: scripts/update-public-key.sh path/to/ed25519-private-key.pem"
    exit 64
fi

der_file=$(mktemp /tmp/nase-update-public.XXXXXX)
openssl pkey -in "${1:A}" -pubout -outform DER -out "$der_file"
tail -c 32 "$der_file" | base64
