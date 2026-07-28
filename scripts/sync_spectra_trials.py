#!/usr/bin/env python3
"""
Sync San Juan Spectra trials from SpectraGlyph into SJSData, then rebuild
the home page map data.

SpectraGlyph (Documents/SpectraGlyph/spectralData) is where San Juan
Spectra's raw data actually lives day to day -- date-named folders, each
holding one subfolder per trial, tied together by a metadata.csv that maps
each trial's csv to GPS coordinates. That layout is unrelated to how the
Tristanium site reads project data, so this script re-organizes it into
the same shape Mr. Whiff uses (one folder per trial, sibling to
TristaniumWeb, not version controlled) and writes the small files
build_trial_map_data.py knows how to read.

Trial folders are named after metadata.csv's "identifier" column (e.g.
"ovaic") rather than its "trial" column (e.g. "T001"), because "trial"
values repeat across different dates (T001 shows up dozens of times) while
"identifier" is unique per row -- so it's what keeps each trial's own
metadata.csv label recognizable without folder collisions.

Calibration rows (is_calibration == yes) are skipped entirely: they're
reference spectra, not field samples, so they don't belong in SJSData or
on the map.

Trials with no GPS in metadata.csv (mostly the pre-July-2026 legacy
imports) are still copied into SJSData for safekeeping/organization -- they
just won't get a location.txt, so build_trial_map_data.py will skip them
on the map until coordinates are added.

Usage:

    python3 scripts/sync_spectra_trials.py
    python3 scripts/sync_spectra_trials.py --source "D:\\some\\other\\spectralData"
    python3 scripts/sync_spectra_trials.py --no-map   # skip the map rebuild step
"""

import argparse
import csv
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
QUARTOWEB_DIR = REPO_DIR.parent
DEFAULT_SOURCE = Path.home() / "Documents" / "SpectraGlyph" / "spectralData"
DEST_DIR = QUARTOWEB_DIR / "SJSData"


def is_calibration(row):
    return row.get("is_calibration", "").strip().lower() == "yes"


def parse_float(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def resolve_source_csv(row, source_root: Path) -> Path:
    """Prefer the absolute filepath recorded in metadata.csv; fall back to
    reconstructing it from date/trial/filename if that path doesn't
    resolve on this machine (e.g. metadata.csv was copied from elsewhere)."""
    filepath = (row.get("filepath") or "").strip()
    if filepath:
        candidate = Path(filepath)
        if candidate.exists():
            return candidate

    return source_root / row["date"] / row["trial"] / row["filename"]


# A handful of legacy rows carry a collection_utc_unix that isn't a real
# unix timestamp at all (e.g. "29580745" -- some old internal counter from
# the original Spectragryph export, not seconds since 1970). Sanity-bound
# it to "sometime after 2000" so we fall back to the date column instead
# of computing a bogus 1970s start time for those rows.
MIN_PLAUSIBLE_UNIX_TIME = 946684800  # 2000-01-01T00:00:00Z


def start_time_iso(row):
    """Prefer the precise collection timestamp; fall back to the date
    folder name (date-only precision) if collection_utc_unix is missing
    or implausible."""
    raw = (row.get("collection_utc_unix") or "").strip()
    if raw:
        try:
            unix_time = int(float(raw))
            if unix_time >= MIN_PLAUSIBLE_UNIX_TIME:
                dt = datetime.fromtimestamp(unix_time, tz=timezone.utc)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, OverflowError, OSError):
            pass

    date = (row.get("date") or "").strip()
    if len(date) == 8 and date.isdigit():
        return f"{date[0:4]}-{date[4:6]}-{date[6:8]}T00:00:00Z"

    return None


def sync(source_root: Path):
    metadata_path = source_root / "metadata.csv"
    if not metadata_path.exists():
        sys.exit(f"metadata.csv not found at {metadata_path}")

    DEST_DIR.mkdir(parents=True, exist_ok=True)

    synced, skipped_calibration, skipped_no_source, missing_gps = 0, 0, 0, 0

    with metadata_path.open(newline="") as f:
        for row in csv.DictReader(f):
            identifier = row.get("identifier", "").strip()
            if not identifier:
                continue

            if is_calibration(row):
                skipped_calibration += 1
                continue

            source_csv = resolve_source_csv(row, source_root)
            if not source_csv.exists():
                print(f"skip {identifier}: source file not found ({source_csv})")
                skipped_no_source += 1
                continue

            trial_dir = DEST_DIR / identifier
            trial_dir.mkdir(parents=True, exist_ok=True)

            shutil.copy2(source_csv, trial_dir / source_csv.name)

            lat = parse_float(row.get("latitude"))
            lon = parse_float(row.get("longitude"))
            if lat is not None and lon is not None:
                (trial_dir / "location.txt").write_text(f"{lat}, {lon}\n")
            else:
                missing_gps += 1

            start_time = start_time_iso(row)
            if start_time:
                (trial_dir / "start_time.txt").write_text(start_time + "\n")

            # Keep the full metadata.csv row for this trial alongside it --
            # handy for anything beyond the map later, and it's how you can
            # still find the original "T00X" label metadata.csv used.
            (trial_dir / "metadata.json").write_text(
                json.dumps(row, indent=2) + "\n"
            )

            synced += 1

    print(
        f"synced {synced} trials into {DEST_DIR} "
        f"({skipped_calibration} calibration rows skipped, "
        f"{skipped_no_source} missing source files skipped, "
        f"{missing_gps} synced without GPS)"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Path to SpectraGlyph's spectralData folder (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--no-map",
        action="store_true",
        help="Skip rebuilding data/trials.json after syncing",
    )
    args = parser.parse_args()

    if not args.source.is_dir():
        sys.exit(f"source folder not found: {args.source}")

    sync(args.source)

    if not args.no_map:
        subprocess.run(
            [sys.executable, str(REPO_DIR / "scripts" / "build_trial_map_data.py")],
            check=True,
        )


if __name__ == "__main__":
    main()
