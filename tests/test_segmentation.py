"""Tests for start/end/pause run segmentation from raw power samples."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.haeo_device_forecast.analysis import detect_runs
from custom_components.haeo_device_forecast.models import RawSample

from .fixture_loader import fixture_timestamps

T0 = datetime(2026, 9, 3, 20, 0, 0, tzinfo=timezone.utc)


def _samples(*value_offsets: tuple[float, int]) -> list[RawSample]:
    return [RawSample(timestamp=T0 + timedelta(seconds=offset), value=value) for value, offset in value_offsets]


def test_no_run_detected_when_always_below_threshold() -> None:
    samples = _samples((1.0, 0), (2.0, 10), (1.5, 20))

    runs = detect_runs(samples, start_threshold=5.0, end_timeout_seconds=60)

    assert runs == []


def test_run_starts_on_threshold_crossing_and_ends_after_timeout_below() -> None:
    samples = _samples(
        (1.0, 0),
        (50.0, 10),  # start
        (60.0, 20),
        (1.0, 30),  # drops below threshold
        (1.0, 100),  # still below, 70s later -> exceeds 60s timeout -> run ends at t=30
    )

    runs = detect_runs(samples, start_threshold=5.0, end_timeout_seconds=60)

    assert len(runs) == 1
    assert runs[0].started_at == T0 + timedelta(seconds=10)
    assert runs[0].ended_at == T0 + timedelta(seconds=30)


def test_short_dip_below_threshold_does_not_end_run() -> None:
    samples = _samples(
        (50.0, 0),  # start
        (1.0, 10),  # short dip (pause within program)
        (55.0, 20),  # resumes within timeout
        (1.0, 200),  # drops for good, well beyond timeout
        (1.0, 300),
    )

    runs = detect_runs(samples, start_threshold=5.0, end_timeout_seconds=60)

    assert len(runs) == 1
    assert runs[0].started_at == T0
    assert runs[0].ended_at == T0 + timedelta(seconds=200)


def test_run_still_active_at_end_of_samples_has_no_end_time() -> None:
    samples = _samples((1.0, 0), (50.0, 10), (60.0, 20))

    runs = detect_runs(samples, start_threshold=5.0, end_timeout_seconds=60)

    assert len(runs) == 1
    assert runs[0].ended_at is None


def test_multiple_separate_runs_are_detected() -> None:
    samples = _samples(
        (50.0, 0),
        (1.0, 10),
        (1.0, 200),  # run 1 ends at t=10
        (50.0, 300),
        (1.0, 310),
        (1.0, 500),  # run 2 ends at t=310
    )

    runs = detect_runs(samples, start_threshold=5.0, end_timeout_seconds=60)

    assert len(runs) == 2
    assert runs[0].started_at == T0
    assert runs[0].ended_at == T0 + timedelta(seconds=10)
    assert runs[1].started_at == T0 + timedelta(seconds=300)
    assert runs[1].ended_at == T0 + timedelta(seconds=310)


def test_run_ends_even_when_no_below_threshold_sample_follows_the_gap() -> None:
    # Regression test: Home Assistant's recorder does not re-log an
    # unchanged state, so a device sitting idle for days produces exactly
    # one below-threshold sample, then nothing until the next real run
    # starts (a sample straight back ABOVE threshold, with no intervening
    # below-threshold sample to trigger the elapsed-time check). The first
    # run must still be closed at the idle sample, not merged with the
    # next run just because no further below-threshold reading arrived.
    samples = _samples(
        (50.0, 0),  # run 1 starts
        (60.0, 10),
        (0.0, 20),  # drops to idle - last sample recorded before a long gap
        (55.0, 100_000),  # run 2 starts directly, >>60s timeout later, no dip in between
        (60.0, 100_010),
    )

    runs = detect_runs(samples, start_threshold=5.0, end_timeout_seconds=60)

    assert len(runs) == 2
    assert runs[0].started_at == T0
    assert runs[0].ended_at == T0 + timedelta(seconds=20)
    assert runs[1].started_at == T0 + timedelta(seconds=100_000)
    assert runs[1].ended_at is None


def test_real_geschirrspueler_fixture_detects_one_open_run() -> None:
    pairs = fixture_timestamps("geschirrspueler_run.json")
    samples = [
        RawSample(timestamp=ts, value=float(state))
        for ts, state in pairs
        if state not in ("unavailable", "unknown")
    ]

    runs = detect_runs(samples, start_threshold=5.0, end_timeout_seconds=120)

    assert len(runs) == 1
    # First sample above the 5W threshold is the "15" reading at 20:25:55.
    first_above_threshold = next(s for s in samples if s.value > 5.0)
    assert runs[0].started_at == first_above_threshold.timestamp
    assert runs[0].ended_at is None  # still running at end of the captured window
