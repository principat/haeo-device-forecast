"""Sensor entities exposing one device's live-tracking state.

Per Specs.md "Schnittstelle zu HAEO" and "Benachrichtigung": the power/
forecast sensor is the one HAEO actually consumes (current load as state,
``forecast`` attribute for the preview); the status, profile-name and
confidence sensors exist for dashboards and for user-built notification
automations.
"""

from __future__ import annotations

from typing import Any, ClassVar

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DeviceForecastCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the device's forecast, status, profile-name and confidence sensors."""
    coordinator: DeviceForecastCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ForecastPowerSensor(coordinator),
            StatusSensor(coordinator),
            ProfileNameSensor(coordinator),
            ConfidenceSensor(coordinator),
        ]
    )


class _DeviceForecastEntity(CoordinatorEntity[DeviceForecastCoordinator], SensorEntity):
    """Common wiring for this integration's per-device sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DeviceForecastCoordinator, key: str) -> None:
        """Initialize the entity for one device's config entry.

        Args:
            coordinator: The device's live-tracking coordinator.
            key: Unique suffix identifying this sensor within the device.
        """
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"


class ForecastPowerSensor(_DeviceForecastEntity):
    """Current power draw, with the HAEO ``forecast`` attribute.

    Per Specs.md "Schnittstelle zu HAEO": HAEO reads the current load from
    this sensor's state and the preview from its ``forecast`` attribute -
    no further HAEO-specific registration is needed.
    """

    _attr_translation_key = "forecast_power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: DeviceForecastCoordinator) -> None:
        """Initialize the forecast power sensor."""
        super().__init__(coordinator, "forecast_power")

    @property
    def native_value(self) -> float | None:
        """Current power draw (W)."""
        return self.coordinator.data.current_power

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """HAEO ``forecast`` payload, plus the estimated run end for dashboards."""
        data = self.coordinator.data
        return {
            "forecast": data.forecast,
            "estimated_end": data.estimated_end.isoformat() if data.estimated_end else None,
        }


class StatusSensor(_DeviceForecastEntity):
    """Current device status: ``sleeping`` or ``running``."""

    _attr_translation_key = "status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = ["sleeping", "running"]

    def __init__(self, coordinator: DeviceForecastCoordinator) -> None:
        """Initialize the status sensor."""
        super().__init__(coordinator, "status")

    @property
    def native_value(self) -> str:
        """Current device status."""
        return self.coordinator.data.status


class ProfileNameSensor(_DeviceForecastEntity):
    """Name of the profile currently used for the forecast."""

    _attr_translation_key = "profile_name"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DeviceForecastCoordinator) -> None:
        """Initialize the profile-name sensor."""
        super().__init__(coordinator, "profile_name")

    @property
    def native_value(self) -> str | None:
        """Name of the currently matched profile, or ``None`` if sleeping/unmatched."""
        return self.coordinator.data.profile_name


class ConfidenceSensor(_DeviceForecastEntity):
    """DTW-based match confidence (%) of the current run against its profile."""

    _attr_translation_key = "confidence"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DeviceForecastCoordinator) -> None:
        """Initialize the confidence sensor."""
        super().__init__(coordinator, "confidence")

    @property
    def native_value(self) -> float | None:
        """Match confidence (0-100), or ``None`` while sleeping/unmatched."""
        return self.coordinator.data.confidence_percent
