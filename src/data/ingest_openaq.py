"""OpenAQ v3 ingestion: hourly fetch, one-time backfill, raw save.

Run from the repo root:
    python -m src.data.ingest_openaq               # hourly run (last lookback_hours)
    python -m src.data.ingest_openaq --backfill    # one-time download from backfill_start_date
    python -m src.data.ingest_openaq --backfill --station 4527035   # one station only (testing)

Output: data/raw/openaq/date=YYYY-MM-DD/openaq.parquet
Columns: station_id, timestamp (UTC, start of the hour), pm1, pm25,
         particle_count_03, station_temp, station_rh
"""

import argparse
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
import yaml

log = logging.getLogger(__name__)

CONFIG_PATH = Path("configs/pipeline_config.yaml")
PAGE_LIMIT = 1000  # max rows per OpenAQ request
DEFAULT_LOOKBACK_HOURS = 6  # hourly run re-fetches this many hours (overridable via openaq.lookback_hours)


def load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8-sig") as f:
        return yaml.safe_load(f)


def get_api_key():
    """Read OPENAQ_API_KEY from the environment, falling back to a local .env file."""
    key = os.environ.get("OPENAQ_API_KEY")
    if not key and Path(".env").exists():
        for line in Path(".env").read_text(encoding="utf-8-sig").splitlines():
            if line.startswith("OPENAQ_API_KEY="):
                key = line.split("=", 1)[1]
    key = (key or "").strip().strip("\"'")
    if not key:
        raise RuntimeError("OPENAQ_API_KEY is not set (put it in .env or the environment)")
    return key


def parse_utc(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------
class OpenAQClient:
    def __init__(self, api_key, base_url, rate_limit_per_min=60):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers["X-API-Key"] = api_key
        self.min_gap = 60.0 / rate_limit_per_min + 0.1  # stay just under the limit
        self._last_call = 0.0

    def get(self, path, params=None, retries=5):
        """GET with rate limiting and retry on 429 / 5xx / network errors."""
        url = f"{self.base_url}{path}"
        for attempt in range(1, retries + 1):
            wait = self.min_gap - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            try:
                resp = self.session.get(url, params=params, timeout=60)
            except requests.RequestException as exc:
                log.warning("Network error on %s (attempt %d): %s", path, attempt, exc)
                time.sleep(5 * attempt)
                continue
            if resp.status_code == 429:
                reset = int(resp.headers.get("X-Ratelimit-Reset", 60))
                log.warning("Rate limited, sleeping %ds", reset + 1)
                time.sleep(reset + 1)
                continue
            if resp.status_code >= 500:
                log.warning("Server error %d on %s (attempt %d)", resp.status_code, path, attempt)
                time.sleep(5 * attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"OpenAQ request failed after {retries} attempts: {path}")
