#!/bin/sh
# Renders the logo (logo.svg) into the files the app serves from frontend/public/.
# Needs Inkscape and ImageMagick; run from anywhere, commit the results.
set -eu
cd "$(dirname "$0")"
out=../frontend/public
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

png() { inkscape "$1" --export-type=png --export-width="$2" --export-filename="$3" >/dev/null 2>&1; }

cp logo.svg "$out/favicon.svg"
cp logo.svg "$out/logo.svg"
# Emails: Gmail and Outlook show no SVG; 96 px for a 32 px logo on high-density screens. The backend
# sends it along with every email; the frontend keeps serving it for emails that linked to it.
png logo.svg 96 "$out/mail-logo.png"
cp "$out/mail-logo.png" ../backend/core/assets/mail-logo.png
# iOS rounds the corners itself and wants a square without transparency.
sed 's/rx="14" //' logo.svg > "$tmp/square.svg"
png "$tmp/square.svg" 180 "$out/apple-touch-icon.png"
# Android home screen (manifest.json): the plain logo, and a maskable one that the launcher may cut
# into any shape, so the motif sits smaller, inside the middle 80 %, on a tile without corners.
png logo.svg 192 "$out/icon-192.png"
png logo.svg 512 "$out/icon-512.png"
sed -e 's#<rect width="64" height="64" rx="14" fill="\(.*\)"/>#<rect width="64" height="64" fill="\1"/><g transform="translate(32 32) scale(.7) translate(-32 -32)">#' \
    -e 's#</svg>#</g></svg>#' logo.svg > "$tmp/maskable.svg"
png "$tmp/maskable.svg" 512 "$out/icon-maskable-512.png"
for size in 16 32 48; do png logo.svg "$size" "$tmp/$size.png"; done
convert "$tmp/16.png" "$tmp/32.png" "$tmp/48.png" "$out/favicon.ico"
