"""Tests for grouping device runs into profiles (matching, creation, merging)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.haeo_device_forecast.analysis.clustering import (
    assign_run,
    create_profile_from_run,
    detect_profiles,
    merge_profiles,
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
ECO_RUN_VARIANT = _run((58.0, 0), (62.0, 10), (61.0, 20), (5.0, 30), ended_offset=30)
INTENSIVE_RUN = _run((150.0, 0), (150.0, 10), (150.0, 20), (5.0, 30), ended_offset=30)


def test_create_profile_from_run_has_generic_name_and_matching_buckets() -> None:
    profile = create_profile_from_run(ECO_RUN, bucket_seconds=10, pause_threshold=5.0)

    assert profile.name.startswith("Profil ")
    assert len(profile.buckets) > 0
    assert profile.buckets[0].mean == 60.0


def test_assign_run_matches_similar_existing_profile() -> None:
    existing = create_profile_from_run(ECO_RUN, bucket_seconds=10, pause_threshold=5.0)

    profile, is_new = assign_run(
        ECO_RUN_VARIANT, [existing], bucket_seconds=10, pause_threshold=5.0
    )

    assert is_new is False
    assert profile.id == existing.id


def test_assign_run_creates_new_profile_for_dissimilar_run() -> None:
    existing = create_profile_from_run(ECO_RUN, bucket_seconds=10, pause_threshold=5.0)

    profile, is_new = assign_run(INTENSIVE_RUN, [existing], bucket_seconds=10, pause_threshold=5.0)

    assert is_new is True
    assert profile.id != existing.id


def test_assign_run_creates_new_profile_when_no_profiles_exist() -> None:
    profile, is_new = assign_run(ECO_RUN, [], bucket_seconds=10, pause_threshold=5.0)

    assert is_new is True
    assert profile.buckets[0].mean == 60.0


def test_assign_run_widens_band_when_matched() -> None:
    existing = create_profile_from_run(ECO_RUN, bucket_seconds=10, pause_threshold=5.0)
    original_max = existing.buckets[1].max  # ECO_RUN_VARIANT's second bucket is 62.0

    updated, is_new = assign_run(
        ECO_RUN_VARIANT, [existing], bucket_seconds=10, pause_threshold=5.0
    )

    assert is_new is False
    assert updated.buckets[1].max >= original_max
    assert updated.buckets[1].max >= 62.0


def test_detect_profiles_groups_similar_runs_and_separates_dissimilar_ones() -> None:
    profiles = detect_profiles(
        [ECO_RUN, ECO_RUN_VARIANT, INTENSIVE_RUN], bucket_seconds=10, pause_threshold=5.0
    )

    assert len(profiles) == 2
    energies = sorted(p.total_energy_wh() for p in profiles)
    assert energies[1] > energies[0]


def test_merge_profiles_widens_band_and_renames() -> None:
    profile_a = create_profile_from_run(ECO_RUN, bucket_seconds=10, pause_threshold=5.0)
    profile_b = create_profile_from_run(ECO_RUN_VARIANT, bucket_seconds=10, pause_threshold=5.0)

    merged = merge_profiles([profile_a, profile_b], name="Eco 50°")

    assert merged.name == "Eco 50°"
    assert merged.buckets[0].min <= min(profile_a.buckets[0].min, profile_b.buckets[0].min)
    assert merged.buckets[0].max >= max(profile_a.buckets[0].max, profile_b.buckets[0].max)
