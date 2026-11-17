#!/usr/bin/env bash
# Re-download current official source files. GOV.UK assets are discovered from their publication pages;
# non-GOV.UK sources retain their stable official endpoints. See data/SOURCES.md.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/pipeline/refresh_sources.py" download
cd "$ROOT/data/raw"
mkdir -p mhclg shr ons ho
get () { echo "→ $2"; curl -fsSL --retry 3 -o "$2" "$1"; }

get "https://assets.publishing.service.gov.uk/media/67e68bde96745eff958c9fe3/2024-25_LAHS_form.xlsx" mhclg/2024-25_LAHS_form.xlsx
get "https://assets.publishing.service.gov.uk/media/67e6ae0737baea91c58ca012/LAHS_Guidance_2024-25.pdf" mhclg/LAHS_Guidance_2024-25.pdf
get https://shrpublicdata.blob.core.windows.net/csv/charter_current.csv shr/charter_current.csv
get "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/Local_Authority_Districts_December_2024_Boundaries_UK_BUC/FeatureServer/0/query?where=LAD24CD+like+'E%25'&outFields=LAD24CD,LAD24NM&outSR=4326&f=geojson" ons/lad_dec2024_england_buc.geojson
get "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/Local_Authority_Districts_December_2024_Boundaries_UK_BUC/FeatureServer/0/query?where=1%3D1&outFields=LAD24CD,LAD24NM&outSR=4326&f=geojson" ons/lad_dec2024_uk_buc.geojson

rm -rf rsh/prp && mkdir -p rsh/prp && unzip -q -o rsh/PRP_Data_Release_2025_Full_Data_FINAL_V1.1.zip -d rsh/prp
echo "Done. The Ombudsman snapshot in ho/ is committed to the repo; re-crawl with pipeline/crawler.js only if you need fresher cases."
