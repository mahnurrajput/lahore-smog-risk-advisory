"""Feature engineering (Module 3.2).

Turns merged station + weather rows into model features:
    - full hourly grid per station (missing hours = empty row, so shift(N) = N hours)
    - lag and rolling PM2.5 features (past and present only)
    - calendar features (from the UTC timestamp) and wind direction as sin/cos
    - drop rows with any missing feature (feature list read from the config)

No-leakage rule: features only use hour t or earlier (positive shifts only).
All timestamps are UTC.

Run from the repo root (this is the `dvc repro` prepare stage):
    python -m src.features.preprocessing

Output: data/processed/features.parquet = station_id, timestamp, features, labels
"""

import logging
from pathlib import Path

import pandas as pd

from src.data.ingest_weather import add_wind_components, load_config, merge_weather_with_stations
from src.features.risk_labeling import add_window_labels, drop_unlabeled, load_thresholds

log = logging.getLogger(__name__)

LAG_HOURS = [1, 3, 24]       # pm25_lag_1h, pm25_lag_3h, pm25_lag_24h
ROLLING_HOURS = [3, 24]      # pm25_roll_mean_3h, pm25_roll_mean_24h (hours t-N+1 .. t)


def build_hourly_grid(df):
    """Give every station one row per UTC hour, from its first to its last reading.

    Hours with no reading become rows with empty (NaN) values. Nothing is filled in.
    df needs columns station_id and timestamp (UTC).
    """
    df = df.drop_duplicates(["station_id", "timestamp"], keep="last")

    parts = []
    for station_id, group in df.groupby("station_id"):
        hours = pd.date_range(group["timestamp"].min(), group["timestamp"].max(),
                              freq="h", tz="UTC", name="timestamp")
        group = group.set_index("timestamp").reindex(hours).reset_index()
        group["station_id"] = station_id
        parts.append(group)

    return pd.concat(parts, ignore_index=True)


def add_pm25_history(df):
    """Add lag and rolling-mean PM2.5 features per station. Needs the hourly grid.

    A rolling mean needs more than half of its hours (e.g. 2 of 3, 13 of 24),
    otherwise it is empty.
    """
    df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)
    pm25 = df.groupby("station_id")["pm25"]

    for h in LAG_HOURS:
        df[f"pm25_lag_{h}h"] = pm25.shift(h)

    for h in ROLLING_HOURS:
        df[f"pm25_roll_mean_{h}h"] = pm25.transform(
            lambda s, h=h: s.rolling(h, min_periods=h // 2 + 1).mean()
        )

    return df


def add_calendar_and_wind(df):
    """Add hour_of_day, day_of_week (0 = Monday), month (UTC) and wind_dir_sin/cos.

    Wind: converts wind_direction_10m if it is present (ingestion normally does this
    already, then nothing changes).
    """
    df = add_wind_components(df.copy())
    df["hour_of_day"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.month
    return df


def build_features(df):
    """Hourly grid + all computed features. Keeps every row (missing values stay empty)."""
    df = build_hourly_grid(df)
    df = add_pm25_history(df)
    return add_calendar_and_wind(df)


def drop_missing_features(df, feature_cols):
    """Drop rows with any missing feature (Logistic Regression cannot handle NaN)."""
    return df.dropna(subset=feature_cols).reset_index(drop=True)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config()
    feature_cols = cfg["features"]
    label_cfg = cfg["labels"]
    label_cols = [w["label"] for w in label_cfg["windows"]]

    merged = merge_weather_with_stations(cfg["paths"]["raw_weather"], cfg["paths"]["raw_openaq"])
    df = build_features(merged)
    # Labels are made on the full hourly grid, before any rows are dropped
    df = add_window_labels(df, load_thresholds(), label_cfg)
    log.info("Hourly grid: %d rows", len(df))

    df = drop_unlabeled(df, label_cfg)
    log.info("After dropping rows without labels: %d rows", len(df))
    df = drop_missing_features(df, feature_cols)
    log.info("After dropping rows with missing features: %d rows", len(df))

    df = df[["station_id", "timestamp"] + feature_cols + label_cols]
    out = Path(cfg["paths"]["features"])
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    log.info("Saved %d rows x %d features to %s", len(df), len(feature_cols), out)


if __name__ == "__main__":
    main()
