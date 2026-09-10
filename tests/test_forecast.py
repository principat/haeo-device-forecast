"""Tests for mapping a matched profile onto the 5-minute HAEO forecast grid."""

from __future__ import annotations

from datetime import datetime, timezone

from custom_components.haeo_device_forecast.analysis.forecast import (
    build_forecast_points,
)
from custom_components.haeo_device_forecast.models import BandBucket, Profile

PROFILE = Profile(
    id="p1",
    name="Test",
    buckets=(
        BandBucket(offset_seconds=0, min=0.0, mean=0.0, max=0.0),
        BandBucket(offset_seconds=300, min=60.0, mean=60.0, max=60.0),
        BandBucket(offset_seconds=600, min=100.0, mean=100.0, max=100.0),
        BandBucket(offset_seconds=900, min=10.0, mean=10.0, max=10.0),
    ),
    pause_windows=(),
    created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
)


def test_forecast_points_start_at_elapsed_time_on_5_minute_grid() -> None:
    points = build_forecast_points(PROFILE, elapsed_seconds=0, grid_seconds=300)

    assert [offset for offset, _ in points] == [0, 300, 600, 900]
    assert [value for _, value in points] == [0.0, 60.0, 100.0, 10.0]


def test_forecast_points_skip_already_elapsed_time() -> None:
    points = build_forecast_points(PROFILE, elapsed_seconds=400, grid_seconds=300)

    # Next grid point at or after 400s is 600s.
    assert [offset for offset, _ in points] == [600, 900]


def test_forecast_points_use_last_bucket_value_beyond_profile_end() -> None:
    points = build_forecast_points(PROFILE, elapsed_seconds=900, grid_seconds=300)

    assert points == [(900, 10.0)]


def test_forecast_points_empty_when_profile_has_no_buckets() -> None:
    empty_profile = Profile(
        id="p2",
        name="Empty",
        buckets=(),
        pause_windows=(),
        created_at=PROFILE.created_at,
        updated_at=PROFILE.updated_at,
    )

    assert build_forecast_points(empty_profile, elapsed_seconds=0, grid_seconds=300) == []
