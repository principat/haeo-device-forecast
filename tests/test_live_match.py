"""Tests for matching an in-progress run against known profiles (live tracking)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.haeo_device_forecast.analysis.clustering import (
    create_profile_from_run,
    match_live,
)
from custom_components.haeo_device_forecast.models import DeviceRun, RawSample

T0 = datetime(2026, 9, 3, 20, 0, 0, tzinfo=timezone.utc)


def _run(*value_offsets: tuple[float, int], ended_offset: int | None = None) -> DeviceRun:
    samples = tuple(
        RawSample(timestamp=T0 + timedelta(seconds=offset), value=value)
        for value, offset in value_offsets
    )
    ended_at = T0 + timedelta(seconds=ended_offset) if ended_offset is not None else None
    return DeviceRun(started_at=samples[0].timestamp, ended_at=ended_at, samples=samples)


ECO_RUN = _run((60.0, 0), (60.0, 10), (60.0, 20), (5.0, 30), ended_offset=30)
INTENSIVE_RUN = _run((150.0, 0), (150.0, 10), (150.0, 20), (5.0, 30), ended_offset=30)

ECO_PROFILE = create_profile_from_run(ECO_RUN, bucket_seconds=10, pause_threshold=5.0)
INTENSIVE_PROFILE = create_profile_from_run(INTENSIVE_RUN, bucket_seconds=10, pause_threshold=5.0)


def test_match_live_with_no_profiles_returns_unknown() -> None:
    live = [RawSample(timestamp=T0, value=60.0)]

    result = match_live(live, [], bucket_seconds=10)

    assert result.profile is None
    assert result.is_known is False


def test_match_live_picks_matching_profile_with_high_confidence() -> None:
    live = [RawSample(timestamp=T0, value=60.0), RawSample(timestamp=T0 + timedelta(seconds=10), value=60.0)]

    result = match_live(live, [ECO_PROFILE, INTENSIVE_PROFILE], bucket_seconds=10)

    assert result.is_known is True
    assert result.profile.id == ECO_PROFILE.id
    assert result.confidence_percent >= 90.0


def test_match_live_picks_worst_case_among_multiple_matching_profiles() -> None:
    # A short prefix that both an "Eco" and "Intensive" profile share
    # (both start high and steady) should resolve to the higher-energy one.
    shared_start_eco = create_profile_from_run(
        _run((100.0, 0), (100.0, 10), (5.0, 20), ended_offset=20), bucket_seconds=10, pause_threshold=5.0
    )
    shared_start_intensive = create_profile_from_run(
        _run((100.0, 0), (100.0, 10), (100.0, 20), (100.0, 30), (5.0, 40), ended_offset=40),
        bucket_seconds=10,
        pause_threshold=5.0,
    )
    live = [RawSample(timestamp=T0, value=100.0)]

    result = match_live(live, [shared_start_eco, shared_start_intensive], bucket_seconds=10)

    assert result.is_known is True
    assert result.profile.id == shared_start_intensive.id


def test_match_live_falls_back_to_worst_case_when_nothing_matches() -> None:
    live = [RawSample(timestamp=T0, value=999.0)]

    result = match_live(live, [ECO_PROFILE, INTENSIVE_PROFILE], bucket_seconds=10)

    assert result.is_known is False
    assert result.profile.id == INTENSIVE_PROFILE.id  # highest energy among all known
