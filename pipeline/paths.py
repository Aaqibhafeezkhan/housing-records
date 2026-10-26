"""Repo-relative paths, so every pipeline script can be run from anywhere."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = str(ROOT / "data" / "raw") + "/"
DERIVED = str(ROOT / "data" / "derived") + "/"  # figures this project worked out from published text (committed)
OUT = str(ROOT / "data" / "out") + "/"
SITE = str(ROOT / "site") + "/"
DIST = str(ROOT / "dist") + "/"
