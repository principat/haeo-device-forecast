"""Reduce raw power samples to a fixed-size band of min/mean/max buckets.

Raw states only change when the reading itself changes (event-driven, not a
fixed grid), so a sample's value is treated as held constant ("last value
wins") until the next sample. Buckets aggregate this piecewise-constant
signal with a time-weighted mean, per Specs.md "Analyse von Lastprofilen"
(Richtwert 5-10s Bucket-Größe).
"""

from __future__ import annotations

from datetime import datetime

from ..models import BandBucket, RawSample


def build_band(samples: list[RawSample], bucket_seconds: int, end: datetime) -> list[BandBucket]:
    """Reduce raw samples into consecutive min/mean/max buckets.

    Args:
        samples: Raw samples in chronological order, covering one run.
        bucket_seconds: Width of each bucket in seconds (Richtwert 5-10s).
        end: Timestamp marking the end of the covered range (e.g. run end).

    Returns:
        One :class:`BandBucket` per bucket, starting at ``samples[0].timestamp``
        with ``offset_seconds`` 0, ``bucket_seconds``, ``2 * bucket_seconds``, ...
        Empty if ``samples`` is empty.
    """
    if not samples:
        return []

    start = samples[0].timestamp
    total_seconds = (end - start).total_seconds()
    if total_seconds <= 0:
        # A single sample (or a zero-length range): report it as one bucket.
        value = samples[-1].value
        return [BandBucket(offset_seconds=0, min=value, mean=value, max=value)]
    bucket_count = max(1, -(-int(total_seconds) // bucket_seconds))  # ceil division

    # Segments of constant value: (segment_start, segment_end, value).
    segments: list[tuple[float, float, float]] = []
    for index, sample in enumerate(samples):
        segment_start = (sample.timestamp - start).total_seconds()
        if index + 1 < len(samples):
            segment_end = (samples[index + 1].timestamp - start).total_seconds()
        else:
            segment_end = total_seconds
        if segment_end > segment_start:
            segments.append((segment_start, segment_end, sample.value))

    buckets: list[BandBucket] = []
    for bucket_index in range(bucket_count):
        bucket_start = bucket_index * bucket_seconds
        bucket_end = min(bucket_start + bucket_seconds, total_seconds)
        weighted_sum = 0.0
        weight_total = 0.0
        values: list[float] = []
        for segment_start, segment_end, value in segments:
            overlap_start = max(segment_start, bucket_start)
            overlap_end = min(segment_end, bucket_end)
            overlap = overlap_end - overlap_start
            if overlap <= 0:
                continue
            weighted_sum += value * overlap
            weight_total += overlap
            values.append(value)

        if not values:
            continue

        buckets.append(
            BandBucket(
                offset_seconds=bucket_start,
                min=min(values),
                mean=weighted_sum / weight_total,
                max=max(values),
            )
        )

    return buckets
