"""Tests for risk labels (Module 3.1). Uses small made-up data, real config files."""

import math

import pandas as pd
import pytest

from src.features.risk_labeling import (
    add_window_labels,
    drop_unlabeled,
    load_label_config,
    load_thresholds,
    pm25_to_category,
)

CLASSES = load_thresholds()
LABEL_CFG = load_label_config()
START = pd.Timestamp("2025-01-01 00:00", tz="UTC")


def make_station(station_id, values, skip_hours=()):
    """Hourly rows for one station from START. Hours in skip_hours are left out (missing)."""
    rows = [
        {"station_id": station_id, "timestamp": START + pd.Timedelta(hours=h), "pm25": v}
        for h, v in enumerate(values)
        if h not in skip_hours
    ]
    return pd.DataFrame(rows)


def label_at(df, column, hour=0):
    return df.loc[df["timestamp"] == START + pd.Timedelta(hours=hour), column].iloc[0]


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, 0),
        (35.4, 0),
        (35.49, 0),  # truncated to 35.4
        (35.5, 1),
        (55.4, 1),
        (55.5, 2),
        (125.4, 2),
        (125.5, 3),
        (900, 3),
    ],
)
def test_boundary_values(value, expected):
    assert pm25_to_category(value, CLASSES) == expected


@pytest.mark.parametrize("value", [None, math.nan, -1])
def test_missing_or_negative_returns_none(value):
    assert pm25_to_category(value, CLASSES) is None


def test_window_label_uses_future_average():
    # hours 0-5 = 20 (Safe), hours 6-15 = 200 (Hazardous)
    df = make_station(1, [20] * 6 + [200] * 10)
    out = add_window_labels(df, CLASSES, LABEL_CFG)
    assert label_at(out, "risk_0_5h") == 0
    assert label_at(out, "risk_5_10h") == 3
    assert label_at(out, "risk_10_15h") == 3


def test_missing_hours_min_3_readings():
    values = [100] * 16  # Unhealthy
    # hours 1, 2 missing -> window t+1..t+5 has 3 readings -> labelled
    out = add_window_labels(make_station(1, values, skip_hours={1, 2}), CLASSES, LABEL_CFG)
    assert label_at(out, "risk_0_5h") == 2
    # hours 1, 2, 3 missing -> only 2 readings -> empty label
    out = add_window_labels(make_station(1, values, skip_hours={1, 2, 3}), CLASSES, LABEL_CFG)
    assert pd.isna(label_at(out, "risk_0_5h"))


def test_last_15_hours_dropped():
    df = pd.concat([make_station(1, [50] * 40), make_station(2, [150] * 40)])
    out = drop_unlabeled(add_window_labels(df, CLASSES, LABEL_CFG), LABEL_CFG)
    for station_id in (1, 2):
        station = out[out["station_id"] == station_id]
        assert len(station) == 25
        assert station["timestamp"].max() == START + pd.Timedelta(hours=24)
    # stations do not leak into each other's labels
    assert (out.loc[out["station_id"] == 1, "risk_10_15h"] == 1).all()
    assert (out.loc[out["station_id"] == 2, "risk_10_15h"] == 3).all()
