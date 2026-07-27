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
      SpectraData/            <- add a project below when this exists
      DailyTrajectoryData/
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
    # "SpectraData": {
    #     "key": "spectra",
    #     "label": "San Juan Spectra",
    #     "icon": "\U0001F9EA",  # test tube
    #     "color": "#2f6f8f",
    # },
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
    """Earliest timestamp we can find for a trial: first line of
    health_log.txt (written at power-on / storage wipe) with a fallback to
    the first row of smell_log.csv."""
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

    return None


def main():
    trials = []

    for folder_name, meta in PROJECTS.items():
        project_dir = DATA_ROOT / folder_name
        if not project_dir.is_dir():
            print(f"skip {folder_name}: not found at {project_dir}")
            continue

        for trial_dir in sorted(project_dir.glob("TRIAL*")):
            if not trial_dir.is_dir():
                continue

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
