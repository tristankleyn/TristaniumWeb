#!/usr/bin/env python3
"""
Build data/trials.json for the Tristanium home page map.

Reads raw trial data from sibling "<Project>Data" folders that live NEXT TO
this git repo (e.g. ../MrWhiffData) and are NOT version controlled. Extracts
just the small bits needed to plot a point on a map -- trial location and
start time -- and writes them to data/trials.json, which IS version
controlled and small enough to ship with the site.

Run this locally whenever you add/finish a trial, then commit the updated
data/trials.json:

    python3 scripts/build_trial_map_data.py

Layout expected:

    QuartoWeb/
      TristaniumWeb/        <- this repo
        scripts/build_trial_map_data.py
        data/trials.json    <- output (versioned)
      MrWhiffData/           <- sibling, NOT versioned
        TRIAL1/
          location.txt       <- "lat, lon"
          health_log.txt     <- first line timestamp used as start time
          smell_log.csv       (raw data, not read by this script)
        TRIAL2/ ...
      SJSData/                <- sibling, NOT versioned (see sync_spectra_trials.py)
        ovaic/
          location.txt        <- "lat, lon" (only present if metadata.csv has GPS)
          start_time.txt      <- ISO8601 timestamp, generic fallback (see below)
        msdfl/ ...
      DailyTrajectoryData/

Each trial folder just needs to provide, in whatever way suits that
project's raw data: a location.txt with "lat, lon", and *something* this
script can turn into a start time. Project-specific formats (like Mr.
Whiff's health_log.txt) are handled in find_start_time() below; anything
else can just drop a start_time.txt with a plain ISO8601 string
("YYYY-MM-DDTHH:MM:SSZ") and it'll be picked up automatically.
"""

import json
import re
from pathlib import Path

# Register each raw-data sibling folder here. key/label/icon/color are
# whatever you want shown on the map -- add a new entry when you start
# extracting data for a new project.
PROJECTS = {
    "MrWhiffData": {
        "key": "mr_whiff",
        "label": "Mr. Whiff",
        "icon": "\U0001F443",  # nose
        "color": "#4c6b52",
    },
    "SJSData": {
        "key": "san_juan_spectra",
        "label": "San Juan Spectra",
        "icon": "\U0001F4A1",  # light bulb
        "color": "#3a6b8a",
    },
    # "DailyTrajectoryData": {
    #     "key": "daily_trajectory",
    #     "label": "The Daily Trajectory",
    #     "icon": "\U0001F463",  # footprints
    #     "color": "#8a6d3b",
    # },
}

TIMESTAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)")

REPO_DIR = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_DIR.parent  # QuartoWeb/
OUT_PATH = REPO_DIR / "data" / "trials.json"


def parse_location(path: Path):
    text = path.read_text().strip()
    lat_str, lon_str = [p.strip() for p in text.split(",")]
    return float(lat_str), float(lon_str)


def find_start_time(trial_dir: Path):
    """Earliest timestamp we can find for a trial. Tries project-specific
    conventions first (Mr. Whiff's health_log.txt / smell_log.csv), then
    falls back to a generic start_time.txt containing a plain ISO8601
    string -- the contract any new project can use without needing a
    project-specific branch here."""
    health_log = trial_dir / "health_log.txt"
    if health_log.exists():
        with health_log.open() as f:
            first_line = f.readline()
        m = TIMESTAMP_RE.search(first_line)
        if m:
            return m.group(1)

    smell_log = trial_dir / "smell_log.csv"
    if smell_log.exists():
        with smell_log.open() as f:
            next(f, None)  # header
            first_row = f.readline()
        if first_row:
            ts = first_row.split(",")[0].strip()
            if TIMESTAMP_RE.match(ts):
                return ts

    start_time_file = trial_dir / "start_time.txt"
    if start_time_file.exists():
        ts = start_time_file.read_text().strip()
        m = TIMESTAMP_RE.search(ts)
        if m:
            return m.group(1)

    return None


def main():
    trials = []

    for folder_name, meta in PROJECTS.items():
        project_dir = DATA_ROOT / folder_name
        if not project_dir.is_dir():
            print(f"skip {folder_name}: not found at {project_dir}")
            continue

        for trial_dir in sorted(p for p in project_dir.iterdir() if p.is_dir()):

            location_file = trial_dir / "location.txt"
            if not location_file.exists():
                print(f"skip {trial_dir}: no location.txt")
                continue

            try:
                lat, lon = parse_location(location_file)
            except ValueError:
                print(f"skip {trial_dir}: unparsable location.txt")
                continue

            start_time = find_start_time(trial_dir)

            trials.append(
                {
                    "project": meta["key"],
                    "project_label": meta["label"],
                    "icon": meta["icon"],
                    "color": meta["color"],
                    "trial": trial_dir.name,
                    "lat": lat,
                    "lon": lon,
                    "start_time": start_time,
                }
            )

    trials.sort(key=lambda t: (t["project"], t["trial"]))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(trials, indent=2) + "\n")
    print(f"wrote {len(trials)} trials to {OUT_PATH}")


if __name__ == "__main__":
    main()
