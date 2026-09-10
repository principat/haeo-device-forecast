"""Load profile ("band") data model.

A profile represents one recognized device program (e.g. "Eco 50°") as a
band of min/mean/max power values per time bucket, learned from one or more
historical runs, per Specs.md section "Analyse von Lastprofilen".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

#: Schema version of the serialized Profile format, bumped on breaking changes.
PROFILE_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class BandBucket:
    """Min/mean/max power observed across all runs within one time bucket.

    Attributes:
        offset_seconds: Offset of this bucket from the profile's start, in seconds.
        min: Lowest power (W) observed in this bucket across all contributing runs.
        mean: Average power (W) observed in this bucket.
        max: Highest power (W) observed in this bucket across all contributing runs.
    """

    offset_seconds: int
    min: float
    mean: float
    max: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict for storage."""
        return {
            "offset_seconds": self.offset_seconds,
            "min": self.min,
            "mean": self.mean,
            "max": self.max,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BandBucket:
        """Deserialize from the dict produced by :meth:`to_dict`."""
        return cls(
            offset_seconds=int(data["offset_seconds"]),
            min=float(data["min"]),
            mean=float(data["mean"]),
            max=float(data["max"]),
        )


@dataclass(frozen=True, slots=True)
class Profile:
    """A recognized, user-nameable load profile ("band") for one device program.

    Attributes:
        id: Stable, unique identifier of the profile.
        name: User-facing name (generic default, renameable by the user).
        buckets: Ordered band buckets covering the full profile duration.
        pause_windows: Expected in-program pauses as
            ``(start_offset_seconds, end_offset_seconds)`` tuples; a pause here
            is part of the program and must not be treated as an end/abort.
        created_at: When the profile was first created.
        updated_at: When the profile was last changed (e.g. through a merge).
        schema_version: Version of this serialized format, for storage migration.
    """

    id: str
    name: str
    buckets: tuple[BandBucket, ...]
    pause_windows: tuple[tuple[int, int], ...]
    created_at: datetime
    updated_at: datetime
    schema_version: int = field(default=PROFILE_SCHEMA_VERSION)

    def total_energy_wh(self) -> float:
        """Total energy of the profile, integrating mean power over time.

        Uses trapezoidal integration across consecutive buckets' `mean` values.

        Returns:
            Energy in watt-hours (Wh).
        """
        if len(self.buckets) < 2:
            return 0.0
        energy_ws = 0.0
        for previous, current in zip(self.buckets, self.buckets[1:]):
            duration_s = current.offset_seconds - previous.offset_seconds
            energy_ws += (previous.mean + current.mean) / 2 * duration_s
        return energy_ws / 3600

    def duration_seconds(self) -> int:
        """Total duration of the profile from its buckets, in seconds."""
        if not self.buckets:
            return 0
        return self.buckets[-1].offset_seconds

    def longest_pause_seconds(self) -> int:
        """Longest expected in-program pause duration, in seconds.

        Used to derive the end-of-run detection threshold, per Specs.md:
        a fixed global timeout would misclassify a profile-internal pause
        as the run's end.
        """
        if not self.pause_windows:
            return 0
        return max(end - start for start, end in self.pause_windows)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict for storage."""
        return {
            "id": self.id,
            "name": self.name,
            "buckets": [bucket.to_dict() for bucket in self.buckets],
            "pause_windows": [list(window) for window in self.pause_windows],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        """Deserialize from the dict produced by :meth:`to_dict`."""
        created_at = dt_util.parse_datetime(data["created_at"])
        updated_at = dt_util.parse_datetime(data["updated_at"])
        if created_at is None or updated_at is None:
            raise ValueError("Invalid created_at/updated_at timestamp")
        return cls(
            id=data["id"],
            name=data["name"],
            buckets=tuple(BandBucket.from_dict(b) for b in data["buckets"]),
            pause_windows=tuple((int(w[0]), int(w[1])) for w in data["pause_windows"]),
            created_at=created_at,
            updated_at=updated_at,
            schema_version=int(data.get("schema_version", PROFILE_SCHEMA_VERSION)),
        )
