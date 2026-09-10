"""Public recorder-history API for the HAEO Device Forecast integration.

Other modules must import :func:`fetch_raw_history` from here, not from the
internal ``recorder_client`` file directly.
"""

from __future__ import annotations

from .recorder_client import fetch_raw_history

__all__ = ["fetch_raw_history"]
