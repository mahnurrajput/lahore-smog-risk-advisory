"""Feature engineering (Module 3.2).

Turns merged station + weather rows into model features:
    - full hourly grid per station (missing hours = empty row, so shift(N) = N hours)

All timestamps are UTC.
"""

import pandas as pd


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
