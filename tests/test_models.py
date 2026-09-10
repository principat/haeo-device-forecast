"""Tests for the data model dataclasses (serialization round-trips)."""

from __future__ import annotations

from datetime import datetime, timezone

from custom_components.haeo_device_forecast.models import (
    BandBucket,
    DeviceRun,
    Profile,
    RawSample,
)


def test_raw_sample_round_trip() -> None:
    sample = RawSample(timestamp=datetime(2026, 9, 3, 20, 30, tzinfo=timezone.utc), value=72.5)

    restored = RawSample.from_dict(sample.to_dict())

    assert restored == sample


def test_band_bucket_round_trip() -> None:
    bucket = BandBucket(offset_seconds=15, min=10.0, mean=12.5, max=16.0)

    restored = BandBucket.from_dict(bucket.to_dict())

    assert restored == bucket


def test_profile_round_trip_preserves_buckets_and_pauses() -> None:
    profile = Profile(
        id="p1",
        name="Eco 50°",
        buckets=(
            BandBucket(offset_seconds=0, min=0.0, mean=0.0, max=2.0),
            BandBucket(offset_seconds=10, min=50.0, mean=60.0, max=70.0),
        ),
        pause_windows=((300, 900),),
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
    )

    restored = Profile.from_dict(profile.to_dict())

    assert restored == profile


def test_profile_total_energy_wh_integrates_mean_power_over_time() -> None:
    # Two buckets 10s apart, mean power 60W then 120W -> trapezoidal energy.
    profile = Profile(
        id="p1",
        name="Test",
        buckets=(
            BandBucket(offset_seconds=0, min=60.0, mean=60.0, max=60.0),
            BandBucket(offset_seconds=10, min=120.0, mean=120.0, max=120.0),
        ),
        pause_windows=(),
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    # trapezoid: (60+120)/2 W * 10s = 900 Ws = 0.25 Wh
    assert profile.total_energy_wh() == 0.25


def test_device_run_round_trip_with_open_end() -> None:
    run = DeviceRun(
        started_at=datetime(2026, 9, 3, 20, 25, tzinfo=timezone.utc),
        ended_at=None,
        samples=(
            RawSample(timestamp=datetime(2026, 9, 3, 20, 25, tzinfo=timezone.utc), value=3.0),
        ),
    )

    restored = DeviceRun.from_dict(run.to_dict())

    assert restored == run
