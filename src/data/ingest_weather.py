"""Open-Meteo weather ingestion: hourly fetch, one-time backfill, merge with station data.

Run from the repo root:
    python -m src.data.ingest_weather                # hourly run (last 6 hours)
    python -m src.data.ingest_weather --backfill     # one-time download from backfill_start_date

Output: data/raw/weather/date=YYYY-MM-DD/weather.parquet
Columns: timestamp (UTC), temperature_2m, relative_humidity_2m, dew_point_2m,
         precipitation, wind_speed_10m, wind_dir_sin, wind_dir_cos,
         surface_pressure, cloud_cover, boundary_layer_height
"""

import argparse
import logging
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
import yaml

log = logging.getLogger(__name__)

CONFIG_PATH = Path("configs/pipeline_config.yaml")
DEFAULT_LOOKBACK_HOURS = 6
MAX_DAYS_PER_REQUEST = 90  # Open-Meteo limits historical requests; chunk to stay safe


def load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8-sig") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Open-Meteo client
# ---------------------------------------------------------------------------
def fetch_open_meteo(url, latitude, longitude, variables, start_date, end_date,
                     retries=5):
    """Fetch hourly weather from Open-Meteo for a date range. Returns a DataFrame."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(variables),
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "UTC",
    }
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=60)
        except requests.RequestException as exc:
            log.warning("Network error (attempt %d): %s", attempt, exc)
            time.sleep(5 * attempt)
            continue
        if resp.status_code == 429:
            log.warning("Rate limited, sleeping 60s")
            time.sleep(60)
            continue
        if resp.status_code >= 500:
            log.warning("Server error %d (attempt %d)", resp.status_code, attempt)
            time.sleep(5 * attempt)
            continue
        resp.raise_for_status()
        data = resp.json()
        hourly = data.get("hourly", {})
        if not hourly or "time" not in hourly:
            log.warning("No hourly data in response for %s..%s", start_date, end_date)
            return pd.DataFrame()
        df = pd.DataFrame(hourly)
        df["timestamp"] = pd.to_datetime(df["time"], utc=True)
        df = df.drop(columns=["time"])
        return df
    raise RuntimeError(f"Open-Meteo request failed after {retries} attempts")

