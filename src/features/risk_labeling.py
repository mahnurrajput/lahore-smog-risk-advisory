"""Risk labels from PM2.5 (Module 3.1).

Maps a PM2.5 value (ug/m3) to one of 4 risk classes using the thresholds in
configs/risk_thresholds.yaml:
    0 = Safe, 1 = Caution, 2 = Unhealthy, 3 = Hazardous

Window labels (risk_0_5h, risk_5_10h, risk_10_15h) = category of the average
FUTURE PM2.5 in each window. Windows and the minimum number of readings come
from the `labels` section of configs/pipeline_config.yaml.
Labels use the future (negative shift) - features never do.

Run from the repo root to print the class balance (after the backfill):
    python -m src.features.risk_labeling       # reads data/interim/merged.parquet
"""

import math
from pathlib import Path

import pandas as pd
import yaml

THRESHOLDS_PATH = Path("configs/risk_thresholds.yaml")
CONFIG_PATH = Path("configs/pipeline_config.yaml")
MERGED_PATH = "data/interim/merged.parquet"
MIN_CLASS_SHARE = 5.0  # % - a class below this is raised at the daily sync before training


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


def load_label_config(path=CONFIG_PATH):
    """Return the `labels` section: source_column, min_readings_per_window, windows."""
    with open(path, encoding="utf-8-sig") as f:
        return yaml.safe_load(f)["labels"]


def add_window_labels(df, classes, label_cfg):
    """Add one label column per window. Missing label = <NA> (never filled in).

    df needs columns station_id, timestamp (UTC) and the source column (pm25).
    Returns the same rows (sorted by station_id, timestamp) plus the label columns.
    """
    col = label_cfg["source_column"]
    min_readings = label_cfg["min_readings_per_window"]
    df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)

    parts = []
    for _, group in df.groupby("station_id"):
        group = group.copy()
        # Full hourly grid, so a shift of N always means N hours (missing hours = NaN)
        pm25 = group.set_index("timestamp")[col].astype(float).resample("h").mean()

        for w in label_cfg["windows"]:
            size = w["end_hour"] - w["start_hour"] + 1
            # rolling at hour i covers [i-size+1, i]; shift(-end_hour) moves it to
            # hour t, so it covers [t+start_hour, t+end_hour]
            avg = pm25.rolling(size, min_periods=1).mean().shift(-w["end_hour"])
            count = pm25.rolling(size, min_periods=1).count().shift(-w["end_hour"])
            avg = avg.where(count >= min_readings)
            labels = avg.map(lambda v: pm25_to_category(v, classes)).astype("Int64")
            group[w["label"]] = labels.reindex(group["timestamp"]).values

        parts.append(group)

    return pd.concat(parts, ignore_index=True)


def drop_unlabeled(df, label_cfg):
    """Drop rows with any missing label (includes the last 15 hours of each station)."""
    label_cols = [w["label"] for w in label_cfg["windows"]]
    return df.dropna(subset=label_cols).reset_index(drop=True)


def class_balance(df, classes, label_cfg):
    """Table of row count and % per class (rows) for each window (columns)."""
    codes = [c["code"] for c in classes]
    table = pd.DataFrame(index=[c["name"] for c in classes])
    for w in label_cfg["windows"]:
        counts = df[w["label"]].value_counts().reindex(codes, fill_value=0)
        table[f"{w['label']} n"] = counts.values
        table[f"{w['label']} %"] = (100 * counts / counts.sum()).round(1).values
    return table


def main():
    classes = load_thresholds()
    label_cfg = load_label_config()
    df = pd.read_parquet(MERGED_PATH)
    labelled = drop_unlabeled(add_window_labels(df, classes, label_cfg), label_cfg)

    print(f"Rows: {len(df)} merged -> {len(labelled)} labelled")
    table = class_balance(labelled, classes, label_cfg)
    print(table.to_string())

    pct_cols = [col for col in table.columns if col.endswith("%")]
    low = [(name, col) for col in pct_cols for name in table.index
           if table.loc[name, col] < MIN_CLASS_SHARE]
    for name, col in low:
        print(f"WARNING: {name} is below {MIN_CLASS_SHARE}% in {col[:-2]} - raise at daily sync")
    if not low:
        print(f"All classes are at least {MIN_CLASS_SHARE}% in every window.")


if __name__ == "__main__":
    main()
