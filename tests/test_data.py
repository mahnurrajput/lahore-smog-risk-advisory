"""Tests for src/data/validate.py (run from the repo root: python -m pytest tests/test_data.py)."""

import logging

import pandas as pd
import pytest

from src.data.validate import (
    drop_bad_rows,
    filter_fresh_stations,
    load_config,
    raw_columns,
    validate,
)

NOW = pd.Timestamp("2026-11-16 12:00", tz="UTC")
NAN = float("nan")


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def make_df(cfg, station_id=4527035, hours=3, end=NOW):
    """A small valid frame: one station, `hours` hourly rows ending at `end`."""
    df = pd.DataFrame({
        "station_id": station_id,
        "timestamp": pd.date_range(end=end, periods=hours, freq="h"),
    })
    for col in raw_columns(cfg):
        df[col] = 10.0
    df["station_rh"] = 50.0
    df["relative_humidity_2m"] = 50.0
    df["wind_dir_sin"] = 0.5
    df["wind_dir_cos"] = 0.5
    df["surface_pressure"] = 990.0
    df["cloud_cover"] = 20.0
    return df


# ---- schema ----------------------------------------------------------------
def test_valid_frame_passes(cfg):
    clean, passed = validate(make_df(cfg), cfg, now=NOW)
    assert passed and len(clean) == 3


def test_missing_column_fails(cfg):
    _, passed = validate(make_df(cfg).drop(columns=["pm25"]), cfg, now=NOW)
    assert not passed


def test_unknown_station_fails(cfg):
    _, passed = validate(make_df(cfg, station_id=1894641), cfg, now=NOW)  # Clarity, excluded
    assert not passed


def test_wrong_type_fails(cfg):
    df = make_df(cfg)
    df["pm25"] = "high"
    _, passed = validate(df, cfg, now=NOW)
    assert not passed


# ---- ranges ----------------------------------------------------------------
@pytest.mark.parametrize("col,value", [
    ("pm25", -1), ("pm1", -5), ("pm25", 1001),
    ("station_rh", 101), ("relative_humidity_2m", -1),
    ("wind_speed_10m", -2), ("wind_dir_sin", 1.5),
])
def test_out_of_range_fails(cfg, col, value):
    df = make_df(cfg)
    df.loc[0, col] = value
    _, passed = validate(df, cfg, now=NOW)
    assert not passed


# ---- dropping bad rows -----------------------------------------------------
def test_drops_row_when_pm1_and_pm25_both_missing(cfg, caplog):
    df = make_df(cfg)
    df.loc[0, ["pm1", "pm25"]] = NAN
    with caplog.at_level(logging.WARNING):
        clean, passed = validate(df, cfg, now=NOW)
    assert passed and len(clean) == 2
    assert "Dropped 1 rows" in caplog.text


def test_keeps_row_when_only_one_pm_missing(cfg):
    df = make_df(cfg)
    df.loc[0, "pm1"] = NAN
    assert len(drop_bad_rows(df)) == 3


def test_drops_row_when_all_three_dispersion_missing(cfg):
    df = make_df(cfg)
    df.loc[1, ["boundary_layer_height", "wind_speed_10m", "relative_humidity_2m"]] = NAN
    assert len(drop_bad_rows(df)) == 2


def test_keeps_row_when_only_one_dispersion_missing(cfg):
    df = make_df(cfg)
    df.loc[1, "boundary_layer_height"] = NAN
    assert len(drop_bad_rows(df)) == 3


# ---- freshness -------------------------------------------------------------
def test_stale_station_is_skipped_with_warning(cfg, caplog):
    fresh = make_df(cfg, station_id=4527035)
    stale = make_df(cfg, station_id=4535267, end=NOW - pd.Timedelta(days=8))
    with caplog.at_level(logging.WARNING):
        out = filter_fresh_stations(pd.concat([fresh, stale]), cfg, now=NOW)
    assert set(out["station_id"]) == {4527035}
    assert "Skipping station 4535267" in caplog.text


def test_station_inside_7_days_is_kept(cfg):
    df = make_df(cfg, end=NOW - pd.Timedelta(days=6))
    assert len(filter_fresh_stations(df, cfg, now=NOW)) == 3


def test_station_with_no_pm_for_over_7_days_is_skipped(cfg):
    # Rows keep arriving but pm1/pm25 are empty (Barki case): after dropping, nothing recent is left.
    old = make_df(cfg, station_id=4515157, end=NOW - pd.Timedelta(days=20))
    recent = make_df(cfg, station_id=4515157, end=NOW)
    recent[["pm1", "pm25"]] = NAN
    clean, passed = validate(pd.concat([old, recent]), cfg, now=NOW)
    assert passed and clean.empty


def test_freshness_can_be_turned_off_for_history(cfg):
    df = make_df(cfg, end=NOW - pd.Timedelta(days=100))
    clean, passed = validate(df, cfg, now=NOW, apply_freshness=False)
    assert passed and len(clean) == 3
