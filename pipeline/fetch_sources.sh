#!/usr/bin/env bash
# Re-download the official source files into data/raw. See data/SOURCES.md for what each one is.
# Asset URLs are versioned by the publisher: if one 404s, take the current link from the landing page.
set -euo pipefail
cd "$(dirname "$0")/../data/raw"
mkdir -p rsh mhclg shr ons ho
get () { echo "→ $2"; curl -fsSL --retry 3 -o "$2" "$1"; }

A=https://assets.publishing.service.gov.uk/media
get $A/6a842f1e54bcee010d5144aa/List_of_registered_providers_17_August_2026.xlsx rsh/List_of_registered_providers_17_August_2026.xlsx
get $A/69394723e447374889cd9005/2025_TSM_Full_Data_v1.1_FINAL.xlsx               rsh/2025_TSM_Full_Data_v1.1_FINAL.xlsx
get $A/69394574e447374889cd9004/2024_TSM_Full_Data_v2.1_FINAL.xlsx               rsh/2024_TSM_Full_Data_v2.1_FINAL.xlsx
get $A/69049e3a823bdda9488b24f3/PRP_Data_Release_2025_Full_Data_FINAL_V1.1.zip   rsh/PRP_Data_Release_2025_Full_Data_FINAL_V1.1.zip
get $A/68f8a6560794bb80118bb71f/GEO_PRP_TOOL_2025_FINAL_V1.0.xlsx                rsh/GEO_PRP_TOOL_2025_FINAL_V1.0.xlsx
get $A/6a9a92545a0c25165ae468f8/20260909_RegulatoryJudgementsNotices_Published.xlsx rsh/20260909_RegulatoryJudgementsNotices_Published.xlsx
get $A/69a5a25db346998e6646b5a6/2026-02-11_1231_VFM_Metrics_tables.xlsx                rsh/2026-02-11_1231_VFM_Metrics_tables.xlsx
get $A/69611bef4343a0da370869de/20251211_GA2025_Datafile_for_Publication.xlsx          rsh/20251211_GA2025_Datafile_for_Publication.xlsx
get $A/6a2bf079c39255c595b507d2/LAHS_open_data_1978-79_to_2024-25.csv            mhclg/LAHS_open_data_1978-79_to_2024-25.csv
get $A/67e68bde96745eff958c9fe3/2024-25_LAHS_form.xlsx                          mhclg/2024-25_LAHS_form.xlsx
get $A/67e6ae0737baea91c58ca012/LAHS_Guidance_2024-25.pdf                        mhclg/LAHS_Guidance_2024-25.pdf
get https://shrpublicdata.blob.core.windows.net/csv/charter_current.csv          shr/charter_current.csv
get "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/Local_Authority_Districts_December_2024_Boundaries_UK_BUC/FeatureServer/0/query?where=LAD24CD+like+'E%25'&outFields=LAD24CD,LAD24NM&outSR=4326&f=geojson" ons/lad_dec2024_england_buc.geojson
get "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/Local_Authority_Districts_December_2024_Boundaries_UK_BUC/FeatureServer/0/query?where=1%3D1&outFields=LAD24CD,LAD24NM&outSR=4326&f=geojson" ons/lad_dec2024_uk_buc.geojson

rm -rf rsh/prp && mkdir -p rsh/prp && unzip -q -o rsh/PRP_Data_Release_2025_Full_Data_FINAL_V1.1.zip -d rsh/prp
echo "Done. The Ombudsman snapshot in ho/ is committed to the repo; re-crawl with pipeline/crawler.js only if you need fresher cases."
