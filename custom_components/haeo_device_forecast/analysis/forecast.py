"""Map a matched profile's remaining band onto the HAEO 5-minute forecast grid.

Per Specs.md "Schnittstelle zu HAEO": the ``forecast`` attribute is a list
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
            5 Minuten, per Specs.md "Erkennen von Lastprofilen während der
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
