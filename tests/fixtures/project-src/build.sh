#!/bin/sh
# Regenerates ../project/{AndroidManifest.xml,resources.arsc} (binary) from this synthetic source.
# Needs the Android SDK: build-tools (aapt2) and platforms;android-35.
set -e
cd "$(dirname "$0")"
SDK=${ANDROID_HOME:-/opt/homebrew/share/android-commandlinetools}
AAPT2=$(ls -d "$SDK"/build-tools/*/aapt2 | tail -1)
tmp=$(mktemp -d)
"$AAPT2" compile --dir res -o "$tmp/res.zip"
"$AAPT2" link -o "$tmp/app.apk" -I "$SDK/platforms/android-35/android.jar" --manifest AndroidManifest.xml "$tmp/res.zip"
mkdir -p ../project
unzip -o -q "$tmp/app.apk" AndroidManifest.xml resources.arsc -d ../project
rm -rf "$tmp"
