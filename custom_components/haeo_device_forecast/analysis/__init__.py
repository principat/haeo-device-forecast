"""Public pattern-analysis API for the HAEO Device Forecast integration.

Other modules must import from here, not from the internal ``banding`` /
``segmentation`` / ``dtw`` / ``clustering`` files directly.
"""

from __future__ import annotations

from .banding import build_band
from .clustering import (
    LiveMatch,
    assign_run,
    create_profile_from_run,
    detect_profiles,
    match_live,
    merge_profiles,
    merge_run_into_profile,
)
from .dtw import CONFIDENCE_MATCH_THRESHOLD, band_aware_dtw_cost, confidence_percent
from .forecast import build_forecast_points
from .segmentation import detect_runs

__all__ = [
    "CONFIDENCE_MATCH_THRESHOLD",
    "LiveMatch",
    "assign_run",
    "band_aware_dtw_cost",
    "build_band",
    "build_forecast_points",
    "confidence_percent",
    "create_profile_from_run",
    "detect_profiles",
    "detect_runs",
    "match_live",
    "merge_profiles",
    "merge_run_into_profile",
]
