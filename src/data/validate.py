"""Validation of the merged station + weather data (Module 1.3).

Steps (in order):
  1. Pandera schema + range checks. A violation fails the run (passed=False).
  2. Drop bad rows and log the count:
       - pm1 AND pm25 both missing
       - boundary_layer_height AND wind_speed_10m AND relative_humidity_2m all missing
     (a row missing only one of them is kept)
  3. Freshness filter: a station whose latest remaining reading is older than
     openaq.freshness_threshold_days (7) is skipped for this run, with a warning.
     It stays on the allowlist.

Run from the repo root:
    python -m src.data.validate                 # checks data/interim/merged.parquet
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pandera as pa
import yaml

log = logging.getLogger(__name__)

CONFIG_PATH = Path("configs/pipeline_config.yaml")
MERGED_PATH = "data/interim/merged.parquet"

PM_COLUMNS = ["pm1", "pm25"]
DISPERSION_COLUMNS = ["boundary_layer_height", "wind_speed_10m", "relative_humidity_2m"]

# column -> (min, max); None = no limit on that side
RANGES = {
    "pm1": (0, None),
    "pm25": (0, 1000),
    "particle_count_03": (0, None),
    "station_temp": (-50, 70),
    "station_rh": (0, 100),
    "temperature_2m": (-50, 70),
    "relative_humidity_2m": (0, 100),
    "dew_point_2m": (-60, 50),
    "precipitation": (0, None),
    "wind_speed_10m": (0, None),
    "wind_dir_sin": (-1, 1),
    "wind_dir_cos": (-1, 1),
    "surface_pressure": (800, 1100),
    "cloud_cover": (0, 100),
    "boundary_layer_height": (0, None),
}


def load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8-sig") as f:
        return yaml.safe_load(f)


def raw_columns(cfg):
    """Columns of the merged frame, built from the config (nothing hard-coded)."""
    cols = list(cfg["openaq"]["parameters"].values())
    for var in cfg["open_meteo"]["hourly_variables"]:
        if var == "wind_direction_10m":  # converted to sin/cos by ingest_weather
            cols += ["wind_dir_sin", "wind_dir_cos"]
        else:
            cols.append(var)
    return cols


def build_schema(cfg):
    allowed_ids = [s["id"] for s in cfg["openaq"]["stations"]]
    columns = {
        "station_id": pa.Column(int, pa.Check.isin(allowed_ids), coerce=True),
        "timestamp": pa.Column("datetime64[ns, UTC]", coerce=True),
    }
    for col in raw_columns(cfg):
        lo, hi = RANGES.get(col, (None, None))
        columns[col] = pa.Column(
            float,
            pa.Check.in_range(lo if lo is not None else -1e12, hi if hi is not None else 1e12),
            nullable=True,  # empty values are handled by drop_bad_rows
            coerce=True,
        )
    return pa.DataFrameSchema(columns, strict=False)


def check_schema(df, cfg):
    """Return True if the frame passes the schema and range checks."""
    try:
        build_schema(cfg).validate(df, lazy=True)
    except pa.errors.SchemaErrors as err:
        log.error("Validation failed:\n%s", err.failure_cases.head(20).to_string())
        return False
    return True


def drop_bad_rows(df):
    """Drop rows missing both PM columns, or all three dispersion columns."""
    no_pm = df[PM_COLUMNS].isna().all(axis=1)
    no_dispersion = df[DISPERSION_COLUMNS].isna().all(axis=1)
    bad = no_pm | no_dispersion
    if bad.any():
        per_station = df[bad].groupby("station_id").size().to_dict()
        log.warning(
            "Dropped %d rows (%d with pm1 and pm25 both missing, %d with boundary_layer_height, "
            "wind_speed_10m and relative_humidity_2m all missing). Per station: %s",
            bad.sum(), no_pm.sum(), no_dispersion.sum(), per_station,
        )
    return df[~bad].copy()


def filter_fresh_stations(df, cfg, now=None):
    """Skip stations with no reading in the last N days (N from config). Logs a warning."""
    now = now or datetime.now(timezone.utc)
    days = cfg["openaq"]["freshness_threshold_days"]
    cutoff = pd.Timestamp(now) - pd.Timedelta(days=days)
    last_seen = df.groupby("station_id")["timestamp"].max()
    stale = []
    for station in cfg["openaq"]["stations"]:
        last = last_seen.get(station["id"])
        if last is None or last < cutoff:
            stale.append(station["id"])
            log.warning(
                "Skipping station %s (%s): last reading %s is older than %d days",
                station["id"], station["name"], last if last is not None else "never", days,
            )
    return df[~df["station_id"].isin(stale)].copy()


def validate(df, cfg=None, now=None, apply_freshness=True):
    """Return (clean_df, passed). passed=False means the run must stop.

    Use apply_freshness=False for historical/training data, where old stations are fine.
    """
    cfg = cfg or load_config()
    if not check_schema(df, cfg):
        return df, False
    clean = drop_bad_rows(df)
    if apply_freshness:
        clean = filter_fresh_stations(clean, cfg, now)
    return clean, True


def main():
    parser = argparse.ArgumentParser(description="Validate the merged station + weather data")
    parser.add_argument("--path", default=MERGED_PATH)
    parser.add_argument("--no-freshness", action="store_true",
                        help="skip the freshness filter (historical data)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    df = pd.read_parquet(args.path)
    clean, passed = validate(df, apply_freshness=not args.no_freshness)
    log.info("Validation %s: %d rows in, %d rows out",
             "PASSED" if passed else "FAILED", len(df), len(clean))
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
