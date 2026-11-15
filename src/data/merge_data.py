"""Merge raw OpenAQ + weather data and save it (Faryal's merge, but saved).

Run from the repo root:
    python -m src.data.merge_data

Output: data/interim/merged.parquet
"""

import logging

from src.data.ingest_weather import load_config, merge_weather_with_stations

OUTPUT_DIR = "data/interim"


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config()
    merged = merge_weather_with_stations(
        cfg["paths"]["raw_weather"], cfg["paths"]["raw_openaq"], OUTPUT_DIR
    )
    print(f"Merged shape: {merged.shape}")
    print(merged.dtypes)


if __name__ == "__main__":
    main()
