#!/usr/bin/env bash
# Download the exact official files the committed data was built from, as archived in a GitHub release,
# into data/raw. Use this to check or reproduce the published figures. (Publishers replace and remove
# old files, e.g. the monthly register, so pipeline/fetch_sources.sh gets the CURRENT files instead.)
#
# Usage: bash pipeline/fetch_snapshot.sh [tag]        default tag: raw-2026-09
set -euo pipefail
TAG="${1:-raw-2026-09}"
REPO="crbtgab/housing-records"
cd "$(dirname "$0")/../data/raw"
FILE="$TAG.tar.gz"
if command -v gh >/dev/null && [ -n "${GH_TOKEN:-}" ]; then
  gh release download "$TAG" --repo "$REPO" --pattern "$FILE" --clobber
else
  curl -fsSL --retry 3 -o "$FILE" "https://github.com/$REPO/releases/download/$TAG/$FILE"
fi
tar -xzf "$FILE" && rm "$FILE"
echo "Unpacked the $TAG snapshot into data/raw. Now run: bash pipeline/run.sh"
