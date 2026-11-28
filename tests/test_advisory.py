"""Tests for src.advisory.advisory_mapper."""

from datetime import datetime, timezone, timedelta

import pytest

from src.advisory.advisory_mapper import (
    build_advisory,
    get_advisory_text,
    load_thresholds,
    _format_hour,
)


@pytest.fixture(scope="module")
def thresholds():
    return load_thresholds()


# ---------------------------------------------------------------------------
# get_advisory_text
# ---------------------------------------------------------------------------
class TestGetAdvisoryText:
    def test_safe(self, thresholds):
        assert "acceptable" in get_advisory_text("Safe", thresholds)

    def test_caution(self, thresholds):
        assert "sensitive" in get_advisory_text("Caution", thresholds)

    def test_unhealthy(self, thresholds):
        assert "limit" in get_advisory_text("Unhealthy", thresholds)

    def test_hazardous(self, thresholds):
        assert "indoors" in get_advisory_text("Hazardous", thresholds)

    def test_unknown_category(self, thresholds):
        assert get_advisory_text("Nonexistent", thresholds) == "unknown risk level"


# ---------------------------------------------------------------------------
# _format_hour (UTC -> Pakistan time display)
# ---------------------------------------------------------------------------
class TestFormatHour:
    def test_morning_utc_to_pkt(self):
        # 04:00 UTC = 09:00 PKT
        dt = datetime(2026, 11, 12, 4, 0, tzinfo=timezone.utc)
        assert _format_hour(dt) == "9 AM"

    def test_noon_pkt(self):
        # 07:00 UTC = 12:00 PKT
        dt = datetime(2026, 11, 12, 7, 0, tzinfo=timezone.utc)
        assert _format_hour(dt) == "12 PM"

    def test_midnight_pkt(self):
        # 19:00 UTC = 00:00 PKT next day
        dt = datetime(2026, 11, 12, 19, 0, tzinfo=timezone.utc)
        assert _format_hour(dt) == "12 AM"

    def test_afternoon_pkt(self):
        # 10:00 UTC = 15:00 PKT = 3 PM
        dt = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
        assert _format_hour(dt) == "3 PM"


# ---------------------------------------------------------------------------
# build_advisory — each category
# ---------------------------------------------------------------------------
class TestBuildAdvisory:
    def _make_forecasts(self, categories):
        """Helper: 3 windows starting at 10:00 UTC."""
        base = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
        windows = [
            {"window": "0-5h", "start": base, "end": base + timedelta(hours=4)},
            {"window": "5-10h", "start": base + timedelta(hours=5), "end": base + timedelta(hours=9)},
            {"window": "10-15h", "start": base + timedelta(hours=10), "end": base + timedelta(hours=14)},
        ]
        for w, cat in zip(windows, categories):
            w["risk_category"] = cat
        return windows

    def test_all_safe(self, thresholds):
        forecasts = self._make_forecasts(["Safe", "Safe", "Safe"])
        result = build_advisory(forecasts, thresholds)
        # All same category -> joined into one sentence
        assert result.count("Safe") == 1
        assert "acceptable" in result
        assert "not medical advice" in result

    def test_all_different(self, thresholds):
        forecasts = self._make_forecasts(["Safe", "Unhealthy", "Hazardous"])
        result = build_advisory(forecasts, thresholds)
        assert "Safe" in result
        assert "Unhealthy" in result
        assert "Hazardous" in result
        assert "not medical advice" in result

    def test_neighbours_joined(self, thresholds):
        """Two consecutive Unhealthy windows should produce one sentence."""
        forecasts = self._make_forecasts(["Unhealthy", "Unhealthy", "Safe"])
        result = build_advisory(forecasts, thresholds)
        # "Unhealthy" appears once (the joined sentence), "Safe" appears once
        assert result.count("Unhealthy") == 1
        assert result.count("Safe") == 1

    def test_non_neighbours_not_joined(self, thresholds):
        """Same category in windows 1 and 3 (not neighbours) -> two sentences."""
        forecasts = self._make_forecasts(["Unhealthy", "Safe", "Unhealthy"])
        result = build_advisory(forecasts, thresholds)
        assert result.count("Unhealthy") == 2

    def test_empty_forecasts(self, thresholds):
        result = build_advisory([], thresholds)
        assert "not medical advice" in result

    def test_string_timestamps(self, thresholds):
        """Timestamps can be ISO strings with Z suffix."""
        forecasts = [
            {"window": "0-5h", "start": "2026-11-12T10:00:00Z",
             "end": "2026-11-12T14:00:00Z", "risk_category": "Caution"},
            {"window": "5-10h", "start": "2026-11-12T15:00:00Z",
             "end": "2026-11-12T19:00:00Z", "risk_category": "Caution"},
            {"window": "10-15h", "start": "2026-11-12T20:00:00Z",
             "end": "2026-11-13T00:00:00Z", "risk_category": "Hazardous"},
        ]
        result = build_advisory(forecasts, thresholds)
        assert "Caution" in result
        assert "Hazardous" in result

    def test_pakistan_time_in_output(self, thresholds):
        """Hours in the advisory should be in Pakistan time (UTC+5)."""
        forecasts = [
            {"window": "0-5h",
             "start": datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc),
             "end": datetime(2026, 11, 12, 14, 0, tzinfo=timezone.utc),
             "risk_category": "Unhealthy"},
        ]
        result = build_advisory(forecasts, thresholds)
        # 10:00 UTC = 3 PM PKT, 14:00 UTC = 7 PM PKT
        assert "3 PM" in result
        assert "7 PM" in result

    def test_disclaimer_present(self, thresholds):
        forecasts = self._make_forecasts(["Safe", "Safe", "Safe"])
        result = build_advisory(forecasts, thresholds)
        assert result.endswith("This is not medical advice.")

    def test_plan_example_output(self, thresholds):
        """Plan example: Unhealthy then two Hazardous windows -> two sentences, Pakistan time."""
        forecasts = [
            {"window": "0-5h", "start": "2026-11-12T10:00:00Z", "end": "2026-11-12T14:00:00Z",
             "risk_category": "Unhealthy"},
            {"window": "5-10h", "start": "2026-11-12T15:00:00Z", "end": "2026-11-12T19:00:00Z",
             "risk_category": "Hazardous"},
            {"window": "10-15h", "start": "2026-11-12T20:00:00Z", "end": "2026-11-13T00:00:00Z",
             "risk_category": "Hazardous"},
        ]
        assert build_advisory(forecasts, thresholds) == (
            "3 PM\u20137 PM: Unhealthy \u2014 limit outdoor activity. "
            "8 PM\u20135 AM: Hazardous \u2014 stay indoors. This is not medical advice."
        )
