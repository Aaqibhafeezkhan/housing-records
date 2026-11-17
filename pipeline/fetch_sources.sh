#!/usr/bin/env bash
# Refresh only the frequently changing RSH register and regulatory judgements.
# Annual source files remain pinned to the archived snapshot.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/pipeline/refresh_sources.py" download

# The pipeline reads the stock and group CSVs extracted from the archived annual PRP release.
cd "$ROOT/data/raw"
PRP_ARCHIVE="$(find rsh -maxdepth 1 -type f -name 'PRP_Data_Release_2025_Full_Data*.zip' -print -quit)"
if [ -z "$PRP_ARCHIVE" ]; then
  echo "Missing archived PRP stock-and-rents release in data/raw/rsh." >&2
  exit 1
fi
rm -rf rsh/prp
mkdir -p rsh/prp
unzip -q -o "$PRP_ARCHIVE" -d rsh/prp
