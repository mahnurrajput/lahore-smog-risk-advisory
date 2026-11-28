"""Map risk categories to plain-language advisory text.

Reads thresholds and advisory text from configs/risk_thresholds.yaml.
Converts UTC forecast windows to Pakistan time (Asia/Karachi) and joins
neighbouring windows with the same category into a single sentence.

Usage:
    from src.advisory.advisory_mapper import build_advisory
    text = build_advisory(forecasts)
    # forecasts = [{"window": "0-5h", "start": ..., "end": ..., "risk_category": "Unhealthy"}, ...]
"""

from datetime import timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

THRESHOLDS_PATH = Path("configs/risk_thresholds.yaml")
PKT = ZoneInfo("Asia/Karachi")  # UTC+5


def load_thresholds(path=THRESHOLDS_PATH):
    with open(path, encoding="utf-8-sig") as f:
        return yaml.safe_load(f)


def get_advisory_text(category_name, thresholds=None):
    """Return the advisory string for a given category name (e.g. 'Unhealthy')."""
    if thresholds is None:
        thresholds = load_thresholds()
    for cls in thresholds["classes"]:
        if cls["name"] == category_name:
            return cls["advisory"]
    return "unknown risk level"


def _format_hour(dt):
    """Format a UTC datetime as Pakistan-time hour string like '3 PM' or '12 AM'."""
    pkt = dt.astimezone(PKT)
    hour = pkt.hour
    if hour == 0:
        return "12 AM"
    elif hour < 12:
        return f"{hour} AM"
    elif hour == 12:
        return "12 PM"
    else:
        return f"{hour - 12} PM"


def build_advisory(forecasts, thresholds=None):
    """Build a full advisory string from a list of forecast dicts.

    Each forecast dict must have:
        - window: str (e.g. "0-5h")
        - start: str or datetime (UTC)
        - end: str or datetime (UTC)
        - risk_category: str (e.g. "Unhealthy")

    Returns a string like:
        "3–7 PM: Unhealthy — limit outdoor activity. 8 PM–5 AM: Hazardous — stay indoors.
         This is not medical advice."
    """
    if thresholds is None:
        thresholds = load_thresholds()

    if not forecasts:
        return thresholds.get("disclaimer", "")

    # Parse timestamps if they are strings
    from datetime import datetime as dt
    parsed = []
    for f in forecasts:
        start = f["start"]
        end = f["end"]
        if isinstance(start, str):
            start = dt.fromisoformat(start.replace("Z", "+00:00"))
        if isinstance(end, str):
            end = dt.fromisoformat(end.replace("Z", "+00:00"))
        parsed.append({
            "start": start,
            "end": end,
            "risk_category": f["risk_category"],
        })

    # Sort by start time
    parsed.sort(key=lambda x: x["start"])

    # Group consecutive windows with the same category
    groups = []
    for p in parsed:
        if groups and groups[-1]["risk_category"] == p["risk_category"]:
            # Extend the previous group
            groups[-1]["end"] = p["end"]
        else:
            groups.append({
                "start": p["start"],
                "end": p["end"],
                "risk_category": p["risk_category"],
            })

    # Build sentences
    sentences = []
    for g in groups:
        start_str = _format_hour(g["start"])
        end_str = _format_hour(g["end"])
        category = g["risk_category"]
        advisory = get_advisory_text(category, thresholds)
        sentences.append(f"{start_str}\u2013{end_str}: {category} \u2014 {advisory}.")

    disclaimer = thresholds.get("disclaimer", "")
    parts = " ".join(sentences)
    if disclaimer:
        parts = f"{parts} {disclaimer}"
    return parts
