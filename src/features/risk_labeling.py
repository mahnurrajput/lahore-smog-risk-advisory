"""Risk labels from PM2.5 (Module 3.1).

Maps a PM2.5 value (ug/m3) to one of 4 risk classes using the thresholds in
configs/risk_thresholds.yaml:
    0 = Safe, 1 = Caution, 2 = Unhealthy, 3 = Hazardous
"""

import math
from pathlib import Path

import yaml

THRESHOLDS_PATH = Path("configs/risk_thresholds.yaml")


def load_thresholds(path=THRESHOLDS_PATH):
    """Return the list of classes (code, name, pm25_min, pm25_max, advisory)."""
    with open(path, encoding="utf-8-sig") as f:  # utf-8-sig: file starts with a BOM
        return yaml.safe_load(f)["classes"]


def pm25_to_category(value, classes):
    """Return the class code for one PM2.5 value, or None if missing/negative."""
    if value is None or math.isnan(value):
        return None
    value = math.floor(value * 10) / 10  # EPA rule: truncate to 1 decimal
    for c in classes:
        if value >= c["pm25_min"] and (c["pm25_max"] is None or value <= c["pm25_max"]):
            return c["code"]
    return None
