"""Tests for reducing raw samples to a fixed-size min/mean/max bucket band."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.haeo_device_forecast.analysis import build_band
from custom_components.haeo_device_forecast.models import RawSample

T0 = datetime(2026, 9, 3, 20, 0, 0, tzinfo=timezone.utc)


def test_build_band_constant_value_yields_equal_min_mean_max() -> None:
    samples = [
        RawSample(timestamp=T0, value=60.0),
        RawSample(timestamp=T0 + timedelta(seconds=10), value=60.0),
    ]

    buckets = build_band(samples, bucket_seconds=10, end=T0 + timedelta(seconds=10))

    assert len(buckets) == 1
    assert buckets[0].offset_seconds == 0
    assert buckets[0].min == buckets[0].mean == buckets[0].max == 60.0


def test_build_band_step_change_mid_bucket_is_time_weighted() -> None:
    samples = [
        RawSample(timestamp=T0, value=0.0),
        RawSample(timestamp=T0 + timedelta(seconds=5), value=100.0),
    ]

    buckets = build_band(samples, bucket_seconds=10, end=T0 + timedelta(seconds=10))

    assert len(buckets) == 1
    assert buckets[0].min == 0.0
    assert buckets[0].max == 100.0
    assert buckets[0].mean == 50.0


def test_build_band_covers_full_range_in_consecutive_buckets() -> None:
    samples = [
        RawSample(timestamp=T0, value=10.0),
        RawSample(timestamp=T0 + timedelta(seconds=12), value=20.0),
    ]

    buckets = build_band(samples, bucket_seconds=10, end=T0 + timedelta(seconds=20))

    assert [b.offset_seconds for b in buckets] == [0, 10]
    assert buckets[0].mean == 10.0
    # second bucket: 2s at 10.0, 8s at 20.0 -> (2*10+8*20)/10 = 18.0
    assert buckets[1].mean == 18.0


def test_build_band_empty_samples_returns_no_buckets() -> None:
    assert build_band([], bucket_seconds=10, end=T0) == []


def test_build_band_single_sample_yields_one_flat_bucket() -> None:
    buckets = build_band([RawSample(timestamp=T0, value=42.0)], bucket_seconds=10, end=T0)

    assert len(buckets) == 1
    assert buckets[0].offset_seconds == 0
    assert buckets[0].min == buckets[0].mean == buckets[0].max == 42.0
