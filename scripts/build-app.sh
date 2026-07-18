#!/bin/zsh
set -euo pipefail

script_dir=${0:A:h}
repo_root=${script_dir:h}
version=${NASE_VERSION:-0.1.0}
build_number=${NASE_BUILD_NUMBER:-1}
bundle_id=${NASE_BUNDLE_ID:-com.nase.launcher}
sign_identity=${NASE_SIGN_IDENTITY:--}
update_url=${NASE_UPDATE_MANIFEST_URL:-}
update_key=${NASE_UPDATE_PUBLIC_KEY:-}
configuration=${NASE_CONFIGURATION:-release}
output_root=${NASE_OUTPUT_DIR:-$repo_root/dist}
app_path="$output_root/NASE.app"

cd "$repo_root"
swift build -c "$configuration"
bin_dir=$(swift build -c "$configuration" --show-bin-path)

if [[ -e "$app_path" ]]; then
    rm -rf -- "$app_path"
fi
mkdir -p "$app_path/Contents/MacOS" "$app_path/Contents/Resources/Backend"
cp "$bin_dir/SteamWineApp" "$app_path/Contents/MacOS/SteamWineApp"
cp release/Info.plist "$app_path/Contents/Info.plist"
cp "assets/NASE App Logo.icns" "$app_path/Contents/Resources/NASE App Logo.icns"
cp mysteamwine.py "$app_path/Contents/Resources/Backend/mysteamwine.py"
cp -R mysteamwine "$app_path/Contents/Resources/Backend/mysteamwine"
cp -R Tools "$app_path/Contents/Resources/Backend/Tools"

resource_bundle=$(find "$bin_dir" -maxdepth 1 -type d -name 'SteamWineApp_*.bundle' -print -quit)
if [[ -n "$resource_bundle" ]]; then
    cp -R "$resource_bundle" "$app_path/Contents/Resources/"
fi

/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier $bundle_id" "$app_path/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $version" "$app_path/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $build_number" "$app_path/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :NASEUpdateManifestURL $update_url" "$app_path/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :NASEUpdatePublicKey $update_key" "$app_path/Contents/Info.plist"

find "$app_path/Contents/Resources/Backend" -type d -name __pycache__ -prune -exec rm -rf {} +
codesign --force --timestamp --options runtime --entitlements release/NASE.entitlements --sign "$sign_identity" "$app_path"
codesign --verify --deep --strict --verbose=2 "$app_path"

mkdir -p "$output_root"
archive="$output_root/NASE-$version.dmg"
staging=$(mktemp -d /tmp/nase-dmg.XXXXXX)
cp -R "$app_path" "$staging/NASE.app"
ln -s /Applications "$staging/Applications"
hdiutil create -volname "NASE $version" -srcfolder "$staging" -ov -format UDZO "$archive"
if [[ "$sign_identity" != "-" ]]; then
    codesign --force --timestamp --sign "$sign_identity" "$archive"
fi

print "Built $app_path"
print "Built $archive"
