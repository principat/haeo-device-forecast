"""Shared entity wiring for this integration's per-device entities.

Used by both the sensor and button platforms so every entity of one device
(one config subentry, per Specs.md "Technische Anforderungen": a single hub
config entry manages multiple devices as subentries) is grouped under the
same Home Assistant device and gets a stable, device-namespaced unique id.
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DeviceForecastCoordinator


class DeviceForecastEntity(CoordinatorEntity[DeviceForecastCoordinator]):
    """Common device/unique_id wiring for this integration's per-device entities.

    Registers a Home Assistant device per config subentry so entity ids are
    namespaced by device name (e.g. ``sensor.waschmaschine_status``) instead
    of colliding across devices - Specs.md requires managing up to ~10
    devices at once, all under one config entry.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: DeviceForecastCoordinator, key: str) -> None:
        """Initialize the entity for one device.

        Args:
            coordinator: The device's live-tracking coordinator.
            key: Unique suffix identifying this entity within the device.
        """
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.subentry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.subentry_id)},
            name=coordinator.device_name,
            manufacturer="HAEO Device Forecast",
        )
