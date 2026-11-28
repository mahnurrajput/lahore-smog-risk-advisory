"""Feature definitions — the 23 model input features.

The feature list matches configs/pipeline_config.yaml exactly.
"""

from feast import Field
from feast.types import Float64, Int64

# Station pollutants (OpenAQ)
STATION_POLLUTANT_FEATURES = [
    Field(name="pm1", dtype=Float64),
    Field(name="pm25", dtype=Float64),
    Field(name="particle_count_03", dtype=Float64),
]

# Station weather (OpenAQ)
STATION_WEATHER_FEATURES = [
    Field(name="station_temp", dtype=Float64),
    Field(name="station_rh", dtype=Float64),
]

# City weather (Open-Meteo)
CITY_WEATHER_FEATURES = [
    Field(name="temperature_2m", dtype=Float64),
    Field(name="relative_humidity_2m", dtype=Float64),
    Field(name="dew_point_2m", dtype=Float64),
    Field(name="precipitation", dtype=Float64),
    Field(name="wind_speed_10m", dtype=Float64),
    Field(name="wind_dir_sin", dtype=Float64),
    Field(name="wind_dir_cos", dtype=Float64),
    Field(name="surface_pressure", dtype=Float64),
    Field(name="cloud_cover", dtype=Float64),
    Field(name="boundary_layer_height", dtype=Float64),
]

# Recent history (computed from station PM2.5, past only)
HISTORY_FEATURES = [
    Field(name="pm25_lag_1h", dtype=Float64),
    Field(name="pm25_lag_3h", dtype=Float64),
    Field(name="pm25_lag_24h", dtype=Float64),
    Field(name="pm25_roll_mean_3h", dtype=Float64),
    Field(name="pm25_roll_mean_24h", dtype=Float64),
]

# Calendar
CALENDAR_FEATURES = [
    Field(name="hour_of_day", dtype=Int64),
    Field(name="day_of_week", dtype=Int64),
    Field(name="month", dtype=Int64),
]

# All 23 features combined
ALL_FEATURES = (
    STATION_POLLUTANT_FEATURES
    + STATION_WEATHER_FEATURES
    + CITY_WEATHER_FEATURES
    + HISTORY_FEATURES
    + CALENDAR_FEATURES
)
