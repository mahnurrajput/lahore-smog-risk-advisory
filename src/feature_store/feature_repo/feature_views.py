"""Feast feature view — one view with all 23 features, sourced from features.parquet."""

from datetime import timedelta
from pathlib import Path

from feast import FeatureView, FileSource

from src.feature_store.feature_repo.entities import station
from src.feature_store.feature_repo.features import ALL_FEATURES

# File source points to the processed features parquet (output of the DVC prepare stage)
REPO_ROOT = Path(__file__).resolve().parents[3]  # independent of the working directory

smog_source = FileSource(
    path=str(REPO_ROOT / "data" / "processed" / "features.parquet"),
    timestamp_field="timestamp",
)

smog_features_view = FeatureView(
    name="smog_features",
    entities=[station],
    schema=ALL_FEATURES,
    source=smog_source,
    ttl=timedelta(hours=24),
    online=True,
)
