#!/usr/bin/env bash
# Rebuild everything from data/raw into data/out and site/data.json.
# Usage: ./pipeline/run.sh
set -euo pipefail
cd "$(dirname "$0")"

python3 build_spine.py       # RSH register + Tenant Satisfaction Measures + stock by local authority
python3 build_layers.py      # regulatory gradings, council stock (LAHS), group roll-up, Scotland
python3 build_ombudsman.py   # Housing Ombudsman cases -> per-landlord record, attached to the spine
python3 build_vfm.py         # Regulator Value for Money cost per home, housing associations only
python3 build_rents.py       # average weekly rent per landlord and per borough (SDR)
python3 build_lahs.py        # the council card: LAHS 2024/25 per stock-owning council
python3 build_stock.py       # homes built, bought, sold and lost in the year (SDR stock balance sheet)
python3 build_bundle.py      # site/data.json for the map
python3 build_standalone.py  # dist/the-housing-record.html, single-file build
