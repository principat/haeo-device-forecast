"""Band-aware Dynamic Time Warping between a live power trace and a profile band.

Per Specs.md ("Offene Punkte" / Mustererkennungs-Algorithmus): standard DTW
uses a Euclidean local cost function, but here a reading counts as a full
match anywhere inside the profile's ``[min, max]`` band for that time
bucket - only a deviation outside the band should reduce the confidence,
proportional to the distance from the band. Bucket-size, exact confidence
formula and DTW windowing are explicitly left as implementation details in
Specs.md; this module documents the concrete choices made here.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ..models import BandBucket

#: Confidence below which Specs.md considers a run to not match a profile.
CONFIDENCE_MATCH_THRESHOLD = 90.0

#: Relative measurement-tolerance margin added to every bucket's [min, max]
#: band before computing distance, per Specs.md "Messtoleranzen (Richtwert 5%)".
#: This matters most for a profile still based on a single run, whose raw
#: band otherwise has zero width.
DEFAULT_TOLERANCE_RATIO = 0.05

#: Absolute floor (W) for the tolerance margin, so near-zero-power buckets
#: (e.g. standby) still tolerate a small absolute deviation.
DEFAULT_TOLERANCE_FLOOR = 1.0


def _band_distance(value: float, bucket: BandBucket, tolerance_ratio: float, tolerance_floor: float) -> float:
    """Distance of a value from a bucket's tolerance-widened band; 0 if inside it."""
    margin = max(abs(bucket.mean) * tolerance_ratio, tolerance_floor)
    lower = bucket.min - margin
    upper = bucket.max + margin
    if value < lower:
        return lower - value
    if value > upper:
        return value - upper
    return 0.0


def band_aware_dtw_cost(
    live_values: Sequence[float],
    band: Sequence[BandBucket],
    window: int | None = None,
    tolerance_ratio: float = DEFAULT_TOLERANCE_RATIO,
    tolerance_floor: float = DEFAULT_TOLERANCE_FLOOR,
    open_end: bool = False,
) -> float:
    """Compute the total band-aware DTW alignment cost.

    Args:
        live_values: Live power readings in chronological order (one per
            bucket of the same resolution as ``band``).
        band: Profile band buckets to align against.
        window: Optional Sakoe-Chiba window (max index offset between an
            aligned live/band pair) to bound compute cost and prevent
            pathological alignments; ``None`` disables windowing.
        tolerance_ratio: Extra relative margin added to each bucket's
            ``[min, max]`` before computing distance (Specs.md: 5% measurement
            tolerance).
        tolerance_floor: Absolute floor (W) for that margin.
        open_end: If ``True``, ``live_values`` must be fully consumed but
            the alignment may end at any point along ``band`` (not just its
            last bucket). Use this for matching an in-progress run against
            a profile that may still have more buckets ahead of it; a
            closed match (the default) forces both sequences to end
            together and suits comparing two already-finished runs.

    Returns:
        The cumulative alignment cost (0.0 means a perfect in-band match
        throughout). Returns 0.0 if either input is empty.
    """
    n = len(live_values)
    if n == 0 or len(band) == 0:
        return 0.0
    if open_end and window is not None:
        # Buckets beyond reach of the window can never be the open end's
        # arg-min, so trimming them keeps the cost matrix small even for a
        # long profile band.
        band = band[: n + window]
    m = len(band)

    cost = np.array(
        [
            [
                _band_distance(live_values[i], band[j], tolerance_ratio, tolerance_floor)
                for j in range(m)
            ]
            for i in range(n)
        ]
    )

    inf = float("inf")
    dtw = np.full((n + 1, m + 1), inf)
    dtw[0, 0] = 0.0
    for i in range(1, n + 1):
        j_lo = max(1, i - window) if window is not None else 1
        j_hi = min(m, i + window) if window is not None else m
        for j in range(j_lo, j_hi + 1):
            dtw[i, j] = cost[i - 1, j - 1] + min(dtw[i - 1, j], dtw[i, j - 1], dtw[i - 1, j - 1])

    if open_end:
        return float(np.min(dtw[n, 1 : m + 1]))
    return float(dtw[n, m])


def confidence_percent(
    total_cost: float, live_values: Sequence[float], band: Sequence[BandBucket]
) -> float:
    """Convert a DTW alignment cost into a 0-100% confidence score.

    The cost is normalized by the number of live samples (average
    out-of-band distance per reading) and scaled by the band's own overall
    power range, so the same absolute deviation counts for less on a
    high-power profile than on a low-power one.

    Args:
        total_cost: Result of :func:`band_aware_dtw_cost`.
        live_values: The live readings that produced ``total_cost`` (only
            its length is used, for normalization).
        band: The profile band that produced ``total_cost`` (used to scale
            the deviation).

    Returns:
        Confidence percentage, clamped to ``[0, 100]``.
    """
    if not live_values or not band:
        return 100.0 if total_cost == 0.0 else 0.0

    average_cost = total_cost / len(live_values)
    band_range = max(bucket.max for bucket in band) - min(bucket.min for bucket in band)
    scale = max(band_range, 1.0)
    confidence = 100.0 * (1.0 - average_cost / scale)
    return max(0.0, min(100.0, confidence))
