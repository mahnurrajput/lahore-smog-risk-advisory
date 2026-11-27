"""Feature engineering (Module 3.2).

Turns merged station + weather rows into model features:
    - full hourly grid per station (missing hours = empty row, so shift(N) = N hours)
    - lag and rolling PM2.5 features (past and present only)

No-leakage rule: features only use hour t or earlier (positive shifts only).
All timestamps are UTC.
"""

import pandas as pd

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
