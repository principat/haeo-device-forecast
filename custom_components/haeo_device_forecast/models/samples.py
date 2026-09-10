"""A single raw power measurement read from the recorder history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util


@dataclass(frozen=True, slots=True)
class RawSample:
    """One raw power reading at a point in time.

    Attributes:
        timestamp: When the reading was taken (timezone-aware).
        value: Measured power in watts.
    """

    timestamp: datetime
    value: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict for storage."""
        return {"timestamp": self.timestamp.isoformat(), "value": self.value}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RawSample:
        """Deserialize from the dict produced by :meth:`to_dict`."""
        timestamp = dt_util.parse_datetime(data["timestamp"])
        if timestamp is None:
            raise ValueError(f"Invalid timestamp: {data['timestamp']!r}")
        return cls(timestamp=timestamp, value=float(data["value"]))
