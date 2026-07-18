#!/bin/zsh
set -euo pipefail

if [[ $# -ne 1 ]]; then
    print -u2 "usage: scripts/notarize-release.sh path/to/NASE-version.dmg"
    exit 64
fi
if [[ -z ${NASE_NOTARY_PROFILE:-} ]]; then
    print -u2 "NASE_NOTARY_PROFILE must name an xcrun notarytool keychain profile."
    exit 64
fi

artifact=${1:A}
xcrun notarytool submit "$artifact" --keychain-profile "$NASE_NOTARY_PROFILE" --wait
xcrun stapler staple "$artifact"
xcrun stapler validate "$artifact"
spctl --assess --type open --context context:primary-signature --verbose=2 "$artifact"
