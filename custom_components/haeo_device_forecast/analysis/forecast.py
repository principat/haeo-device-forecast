"""Map a matched profile's remaining band onto the HAEO 5-minute forecast grid.

Per docs/REQUIREMENTS.md "Schnittstelle zu HAEO": the ``forecast`` attribute is a list
of ``{"time": ..., "value": ...}`` points on a fixed grid (5 minutes by
default here, matching the integration's live-tracking resolution).
"""

from __future__ import annotations

from ..models import Profile


def _value_at_offset(profile: Profile, offset_seconds: float) -> float:
    """Value of a profile's band at a given offset, holding the last bucket beyond the end."""
    value = profile.buckets[0].mean
    for bucket in profile.buckets:
        if bucket.offset_seconds > offset_seconds:
            break
        value = bucket.mean
    return value


def build_forecast_points(
    profile: Profile, elapsed_seconds: float, grid_seconds: int = 300
) -> list[tuple[int, float]]:
    """Build forecast points for the remainder of a profile on a fixed grid.

    Args:
        profile: The profile currently used for the forecast.
        elapsed_seconds: How far into the run we already are.
        grid_seconds: Spacing between forecast points, in seconds (Richtwert
            5 Minuten, per docs/REQUIREMENTS.md "Erkennen von Lastprofilen während der
            Nutzung").

    Returns:
        ``(offset_seconds, value)`` pairs from the next grid point at or
        after ``elapsed_seconds`` through the profile's last bucket. Empty
        if the profile has no buckets.
    """
    if not profile.buckets:
        return []

    duration = profile.duration_seconds()
    first_offset = -(-int(elapsed_seconds) // grid_seconds) * grid_seconds  # ceil to grid
    points: list[tuple[int, float]] = []
    offset = first_offset
    while offset <= duration:
        points.append((offset, _value_at_offset(profile, offset)))
        offset += grid_seconds

    if not points:
        points.append((duration, _value_at_offset(profile, duration)))

    return points


def build_curve_points(
    profile: Profile, max_points: int = 300
) -> list[tuple[int, float, float, float]]:
    """Downsample a profile's full band to a point list for visualization.

    Per docs/REQUIREMENTS.md "Dashboard": the learned profiles are shown with their
    load curve. A profile's band is stored on the 5-10 s bucket grid, which
    is far too fine for a dashboard chart (a multi-hour program has
    thousands of buckets), so neighbouring buckets are aggregated into at
    most ``max_points`` points - keeping ``min``/``max`` as the envelope of
    each window so the band never looks narrower than it is.

    Args:
        profile: The profile whose band to render.
        max_points: Upper bound on the number of returned points.

    Returns:
        ``(offset_seconds, mean, min, max)`` tuples ordered by offset,
        always including the profile's last bucket. Empty if the profile
        has no buckets.
    """
    buckets = profile.buckets
    if not buckets:
        return []

    stride = max(1, -(-len(buckets) // max(1, max_points)))
    points: list[tuple[int, float, float, float]] = []
    for start in range(0, len(buckets), stride):
        window = buckets[start : start + stride]
        points.append(
            (
                window[0].offset_seconds,
                sum(bucket.mean for bucket in window) / len(window),
                min(bucket.min for bucket in window),
                max(bucket.max for bucket in window),
            )
        )

    last = buckets[-1]
    if points[-1][0] != last.offset_seconds:
        points.append((last.offset_seconds, last.mean, last.min, last.max))

    return points
