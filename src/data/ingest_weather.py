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


def add_wind_components(df):
    """Convert wind_direction_10m to sin/cos and drop the raw column."""
    if "wind_direction_10m" in df.columns:
        rad = df["wind_direction_10m"].astype(float) * (math.pi / 180.0)
        df["wind_dir_sin"] = rad.apply(math.sin)
        df["wind_dir_cos"] = rad.apply(math.cos)
        df = df.drop(columns=["wind_direction_10m"])
    return df


# ---------------------------------------------------------------------------
# Chunked fetch (backfill can span > 1 year)
# ---------------------------------------------------------------------------
def fetch_weather_chunked(url, latitude, longitude, variables, start, end):
    """Fetch weather in chunks of MAX_DAYS_PER_REQUEST days."""
    frames = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + timedelta(days=MAX_DAYS_PER_REQUEST), end)
        start_str = chunk_start.strftime("%Y-%m-%d")
        end_str = chunk_end.strftime("%Y-%m-%d")
        log.info("Fetching weather %s .. %s", start_str, end_str)
        df = fetch_open_meteo(url, latitude, longitude, variables, start_str, end_str)
        if not df.empty:
            frames.append(df)
        chunk_start = chunk_end + timedelta(days=1)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------
def save_raw(df, raw_dir):
    """Write df into raw_dir/date=YYYY-MM-DD/weather.parquet, merging with existing."""
    if df.empty:
        return 0
    df = df.copy()
    df["_date"] = df["timestamp"].dt.strftime("%Y-%m-%d")
    total = 0
    for date, part in df.groupby("_date"):
        part = part.drop(columns="_date")
        path = Path(raw_dir) / f"date={date}" / "weather.parquet"
        if path.exists():
            part = pd.concat([pd.read_parquet(path), part], ignore_index=True)
        part = part.drop_duplicates(["timestamp"], keep="last")
        part = part.sort_values("timestamp")
        path.parent.mkdir(parents=True, exist_ok=True)
        part.to_parquet(path, index=False)
        total += len(part)
    return total


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------
def run(backfill=False):
    cfg = load_config()
    om = cfg["open_meteo"]

    now = datetime.now(timezone.utc)
    if backfill:
        start = datetime.strptime(cfg["backfill_start_date"], "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
        url = om["historical_url"]
    else:
        start = now - timedelta(hours=DEFAULT_LOOKBACK_HOURS)
        url = om["live_url"]

    variables = om["hourly_variables"]
    latitude = om["latitude"]
    longitude = om["longitude"]

    df = fetch_weather_chunked(url, latitude, longitude, variables, start, now)
    if df.empty:
        log.warning("No weather data returned")
        return 0

    # Convert wind direction to sin/cos
    df = add_wind_components(df)

    # Save raw weather
    saved = save_raw(df, cfg["paths"]["raw_weather"])
    log.info("Saved %d weather rows to %s", saved, cfg["paths"]["raw_weather"])

    return saved


def main():
    parser = argparse.ArgumentParser(
        description="Ingest Open-Meteo weather data for Lahore"
    )
    parser.add_argument(
        "--backfill", action="store_true",
        help="download from backfill_start_date (uses historical endpoint)",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    run(backfill=args.backfill)


if __name__ == "__main__":
    main()
