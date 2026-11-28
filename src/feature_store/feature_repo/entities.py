"""Feast entity definitions for the Lahore smog risk project."""

from feast import Entity, ValueType

station = Entity(
    name="station_id",
    value_type=ValueType.INT64,
    description="OpenAQ station identifier",
)
