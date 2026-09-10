"""A single recorded or in-progress device run (one program execution)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

from .samples import RawSample


@dataclass(frozen=True, slots=True)
class DeviceRun:
    """One contiguous device run, from start-threshold to end-threshold.

    Attributes:
        started_at: When the power value first crossed the start threshold.
        ended_at: When the run was recognized as finished, or ``None`` while
            the run is still in progress (status ``running``).
        samples: Raw samples captured during this run.
    """

    started_at: datetime
    ended_at: datetime | None
    samples: tuple[RawSample, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict for storage."""
        return {
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "samples": [sample.to_dict() for sample in self.samples],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceRun:
        """Deserialize from the dict produced by :meth:`to_dict`."""
        started_at = dt_util.parse_datetime(data["started_at"])
        if started_at is None:
            raise ValueError(f"Invalid started_at: {data['started_at']!r}")
        ended_at = dt_util.parse_datetime(data["ended_at"]) if data["ended_at"] else None
        return cls(
            started_at=started_at,
            ended_at=ended_at,
            samples=tuple(RawSample.from_dict(s) for s in data["samples"]),
        )
