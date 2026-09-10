"""Public storage API for the HAEO Device Forecast integration.

Other modules must import :class:`DeviceStore` from here, not from the
internal ``device_store`` file directly.
"""

from __future__ import annotations

from .device_store import DeviceStore

__all__ = ["DeviceStore"]
