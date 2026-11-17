"""Discover current GOV.UK source attachments and summarize a refreshed data build.

The pipeline consumes stable local filenames; this module resolves those names to the
current attachment URLs published on GOV.UK instead of pinning versioned asset URLs.
"""
import argparse
import csv
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
TIMEOUT = 60

SOURCES = (
    ("registered-providers-of-social-housing", r"List_of_registered_providers.*\.xlsx$", "rsh/List_of_registered_providers_17_August_2026.xlsx"),
    ("tenant-satisfaction-measures-202526", r"2026_TSM_Full_Dataset.*\.xlsx$", "rsh/2026_TSM_Full_Dataset_FINAL.xlsx"),
    ("tenant-satisfaction-measures-202425", r"2025_TSM_Full_Data.*\.xlsx$", "rsh/2025_TSM_Full_Data_v1.1_FINAL.xlsx"),
    ("private-registered-provider-social-housing-stock-and-rents-in-england-2024-to-2025", r"PRP_Data_Release_2025_Full_Data.*\.zip$", "rsh/PRP_Data_Release_2025_Full_Data_FINAL_V1.1.zip"),
    ("regulatory-judgements-and-enforcement-notices", r".*RegulatoryJudgementsNotices_Published.*\.xlsx$", "rsh/20260909_RegulatoryJudgementsNotices_Published.xlsx"),
    ("value-for-money-metrics-and-reporting-2025", r".*VFM_Metrics_tables.*\.xlsx$", "rsh/2026-02-11_1231_VFM_Metrics_tables.xlsx"),
    ("2025-global-accounts-of-private-registered-providers", r".*GA2025_Datafile_for_Publication.*\.xlsx$", "rsh/20251211_GA2025_Datafile_for_Publication.xlsx"),
    ("local-authority-housing-statistics-open-data", r"LAHS_open_data_.*\.csv$", "mhclg/LAHS_open_data_1978-79_to_2024-25.csv"),
)


class SourceError(RuntimeError):
    """A source page or attachment could not be resolved safely."""


def _attachment_name(item):
    for key in ("filename", "file_name", "name", "title"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    url = item.get("url") or item.get("file_url") or item.get("asset_url")
    return Path(urllib.parse.urlparse(url).path).name if isinstance(url, str) else ""


def collect_assets(value):
    """Return attachment assets from nested GOV.UK Content API structures."""
    found = []
    if isinstance(value, dict):
        url = value.get("url") or value.get("file_url") or value.get("asset_url")
        name = _attachment_name(value)
        if isinstance(url, str) and url.startswith(("https://", "http://", "/")) and name:
            found.append({"name": name, "url": url})
        for child in value.values():
            found.extend(collect_assets(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(collect_assets(child))
    return list({(item["name"], item["url"]): item for item in found}.values())


def resolve_attachment(page, filename_pattern):
    matches = [item for item in collect_assets(page)
               if re.fullmatch(filename_pattern, item["name"], flags=re.IGNORECASE)]
    if len(matches) != 1:
        names = sorted(item["name"] for item in matches)
        raise SourceError(
            f"Expected exactly one attachment matching {filename_pattern!r}; "
            f"found {len(matches)}: {names}"
        )
    return matches[0]


def _request(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "housing-records-data-refresh/1.0", "Accept": "application/json, */*"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SourceError(f"Could not retrieve {url}: {exc}") from exc


def download_sources():
    for slug, pattern, relative_output in SOURCES:
        api_url = f"https://www.gov.uk/api/content/{slug}"
        try:
            page = json.loads(_request(api_url))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SourceError(f"GOV.UK returned invalid JSON for {slug}: {exc}") from exc
        asset = resolve_attachment(page, pattern)
        asset_url = urllib.parse.urljoin("https://www.gov.uk", asset["url"])
        target = RAW / relative_output
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {asset['name']} -> {relative_output}", flush=True)
        payload = _request(asset_url)
        if not payload or payload.lstrip().lower().startswith((b"<!doctype html", b"<html")):
            raise SourceError(f"Downloaded an empty or HTML response instead of a data file: {asset_url}")
        target.write_bytes(payload)
        if target.suffix.lower() in (".xlsx", ".zip") and not zipfile.is_zipfile(target):
            target.unlink(missing_ok=True)
            raise SourceError(f"Downloaded attachment is not a valid XLSX/ZIP archive: {asset_url}")
        if target.suffix.lower() == ".csv":
            try:
                payload.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                target.unlink(missing_ok=True)
                raise SourceError(f"Downloaded CSV is not valid UTF-8 text: {asset_url}") from exc
    print(f"Resolved and downloaded {len(SOURCES)} current GOV.UK source files.")


def _git_text(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)


def _csv_rows(path, content=None):
    if content is None:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            return list(csv.DictReader(stream))
    import io
    return list(csv.DictReader(io.StringIO(content)))


def build_summary():
    spine_path = ROOT / "data" / "out" / "landlord_spine_2024_25.csv"
    if not spine_path.exists():
        raise SourceError("Pipeline did not produce data/out/landlord_spine_2024_25.csv")
    try:
        previous = _git_text("show", "HEAD:data/out/landlord_spine_2024_25.csv")
        old_rows = {row["landlord_code"]: row for row in _csv_rows(spine_path, previous) if row.get("landlord_code")}
    except (subprocess.CalledProcessError, KeyError):
        old_rows = {}
    new_rows = {row["landlord_code"]: row for row in _csv_rows(spine_path) if row.get("landlord_code")}
    added = sorted(set(new_rows) - set(old_rows))
    removed = sorted(set(old_rows) - set(new_rows))
    changed = sorted(code for code in set(old_rows) & set(new_rows) if old_rows[code] != new_rows[code])
    changed_files = _git_text("status", "--short", "--", "data/out", "site/data.json").splitlines()
    lines = [
        "# Automated data refresh", "",
        f"- **Landlord records:** {len(new_rows):,} in the refreshed spine.",
        f"- **New landlords:** {len(added):,}.",
        f"- **Removed landlords:** {len(removed):,}.",
        f"- **Landlords with changed published fields:** {len(changed):,}.",
        "", "## Record-level changes", "",
    ]
    for label, values in (("New registration codes", added), ("Removed registration codes", removed),
                          ("Changed registration codes", changed)):
        if values:
            lines.append(f"- {label}: {', '.join(values[:30])}" + (" (first 30 shown)" if len(values) > 30 else ""))
    if not (added or removed or changed):
        lines.append("- No landlord-level changes were detected in the spine.")
    lines += ["", "## Changed build outputs", ""]
    lines.extend(f"- `{line[3:]}`" for line in changed_files if line[3:].strip())
    if not changed_files:
        lines.append("- No generated output files changed.")
    lines += [
        "", "This refresh ran the repository's full pipeline against the currently published source attachments. "
        "It does not publish or deploy the refreshed data; merge remains a human decision.", "",
    ]
    (ROOT / "data-refresh-summary.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("download", "summarize"))
    args = parser.parse_args()
    if args.command == "download":
        download_sources()
    else:
        build_summary()


if __name__ == "__main__":
    try:
        main()
    except SourceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
