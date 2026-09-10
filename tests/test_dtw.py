"""Tests for the band-aware DTW alignment and confidence scoring."""

from __future__ import annotations

from custom_components.haeo_device_forecast.analysis.dtw import (
    band_aware_dtw_cost,
    confidence_percent,
)
from custom_components.haeo_device_forecast.models import BandBucket


def _band(*mean_values: float, half_width: float = 5.0) -> list[BandBucket]:
    return [
        BandBucket(offset_seconds=i * 10, min=v - half_width, mean=v, max=v + half_width)
        for i, v in enumerate(mean_values)
    ]


def test_confidence_is_100_when_live_matches_band_exactly() -> None:
    band = _band(10, 50, 60, 50, 10)
    live = [10.0, 50.0, 60.0, 50.0, 10.0]

    cost = band_aware_dtw_cost(live, band)

    assert cost == 0.0
    assert confidence_percent(cost, live, band) == 100.0


def test_confidence_is_100_when_live_stays_within_band_tolerance() -> None:
    band = _band(10, 50, 60, 50, 10, half_width=5.0)
    live = [12.0, 47.0, 63.0, 53.0, 8.0]  # all within +/-5 of the means

    cost = band_aware_dtw_cost(live, band)

    assert cost == 0.0
    assert confidence_percent(cost, live, band) == 100.0


def test_confidence_drops_when_live_deviates_outside_band() -> None:
    band = _band(10, 50, 60, 50, 10, half_width=5.0)
    live = [10.0, 50.0, 200.0, 50.0, 10.0]  # one wild outlier, far outside [55, 65]

    cost = band_aware_dtw_cost(live, band)
    confidence = confidence_percent(cost, live, band)

    assert cost > 0.0
    assert confidence < 90.0


def test_confidence_never_goes_below_zero_for_extreme_mismatch() -> None:
    band = _band(10, 10, 10, half_width=2.0)
    live = [500.0, 500.0, 500.0]

    cost = band_aware_dtw_cost(live, band)
    confidence = confidence_percent(cost, live, band)

    assert confidence == 0.0


def test_dtw_tolerates_a_small_time_shift_via_window() -> None:
    # Live is the same shape as the band (low/low/high/high/low/low) but the
    # rising and falling edges are shifted one bucket later.
    band = _band(10, 10, 80, 80, 10, 10, half_width=5.0)
    live = [10.0, 10.0, 10.0, 80.0, 80.0, 10.0]

    windowed_cost = band_aware_dtw_cost(live, band, window=2)
    windowed_confidence = confidence_percent(windowed_cost, live, band)

    # Forcing a strict diagonal (window=0) disables shift tolerance and
    # should score markedly worse than allowing the DTW to re-align.
    diagonal_cost = band_aware_dtw_cost(live, band, window=0)
    diagonal_confidence = confidence_percent(diagonal_cost, live, band)

    assert windowed_confidence >= 90.0
    assert windowed_confidence > diagonal_confidence
