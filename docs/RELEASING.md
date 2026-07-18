# Releasing NASE

NASE ships as a native app bundle containing the SwiftUI launcher, Python
backend, and graphics probe executables. Release builds target macOS 14 or newer.
Private signing keys, Apple credentials, and update signing keys must never be
stored in this repository.

## One-time setup

1. Join the Apple Developer Program and install a `Developer ID Application`
   certificate in the login keychain.
2. Store notarization credentials:

   ```bash
   xcrun notarytool store-credentials NASE-notary \
     --apple-id "APPLE_ID" --team-id "TEAM_ID" --password "APP_SPECIFIC_PASSWORD"
   ```

3. Create the independent Ed25519 update-feed key:

   ```bash
   mkdir -p release/private
   openssl genpkey -algorithm ED25519 -out release/private/update-key.pem
   scripts/update-public-key.sh release/private/update-key.pem
   ```

   Back up the private key outside the repository. The printed Base64 public key
   is embedded in release builds and may be published.

Apple's current release guidance is the authority for certificate and
notarization requirements: [Notarizing macOS software before distribution](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution).

## Build and sign

```bash
export NASE_VERSION=0.1.0
export NASE_BUILD_NUMBER=1
export NASE_SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
export NASE_UPDATE_MANIFEST_URL="https://releases.example.com/nase/latest.json"
export NASE_UPDATE_PUBLIC_KEY="BASE64_RAW_ED25519_PUBLIC_KEY"
scripts/build-app.sh
```

The script builds with SwiftPM in release mode, embeds `mysteamwine.py`, the
Python package, and probe executables, enables the hardened runtime, signs the
app, verifies it, and creates `dist/NASE-VERSION.dmg`.

## Notarize and staple

```bash
export NASE_NOTARY_PROFILE=NASE-notary
scripts/notarize-release.sh "dist/NASE-$NASE_VERSION.dmg"
```

Do not publish unless `notarytool`, `stapler validate`, and Gatekeeper assessment
all succeed.

## Create the signed update feed

Create the manifest only after notarization, because its checksum covers the
final DMG:

```bash
scripts/make-update-manifest.py "dist/NASE-$NASE_VERSION.dmg" \
  --version "$NASE_VERSION" --build "$NASE_BUILD_NUMBER" \
  --download-url "https://releases.example.com/nase/NASE-$NASE_VERSION.dmg" \
  --release-notes-url "https://releases.example.com/nase/$NASE_VERSION" \
  --private-key release/private/update-key.pem \
  --output dist/latest.json
```

Upload the DMG first and `latest.json` last. The app verifies the manifest's
Ed25519 signature and the downloaded DMG's SHA-256 before opening it.

## Automated clean-machine smoke test

```bash
scripts/clean-machine-test.sh dist/NASE.app
```

The test uses an isolated empty `HOME`, verifies bundle structure and signing,
compiles the bundled backend with system Python, exercises its structured job
contract, launches the packaged app for five seconds, and runs Gatekeeper when a
Developer ID signature is present.

Set `NASE_SKIP_LAUNCH_SMOKE=1` only on a headless runner.

## Fresh macOS VM release gate

The isolated-home test does not replace a fresh macOS installation. Before a
public release, test the notarized DMG on both a clean Apple Silicon VM/device
and an Intel Mac if Intel remains supported:

- Download through a browser so quarantine is applied.
- Open the DMG and drag NASE into Applications.
- Confirm Gatekeeper opens it without a security bypass.
- Confirm first launch opens Setup Wizard automatically.
- Verify missing Python, Rosetta, Wine, and Winetricks are explained clearly.
- Install the recommended dependencies through the app.
- Complete DXMT profile setup, Steam login, library discovery, launch, stop, and
  repair.
- Check for an update using a staged signed manifest; corrupt the DMG in a
  separate negative test and confirm checksum rejection.
- Restart NASE and confirm onboarding does not reopen while Jobs history and
  managed bottles remain available.

Record OS version, hardware, installer checksum, pass/fail, and logs for every
release candidate.
