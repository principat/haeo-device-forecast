"""Sensor entities exposing one device's live-tracking state.

Per docs/REQUIREMENTS.md "Schnittstelle zu HAEO" and "Benachrichtigung": the power/
forecast sensor is the one HAEO actually consumes (current load as state,
``forecast`` attribute for the preview); the status, profile-name and
confidence sensors exist for dashboards and for user-built notification
automations.
"""

from __future__ import annotations

from datetime import timedelta
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

from .analysis import build_curve_points
from .const import DOMAIN
from .coordinator import DeviceForecastCoordinator
from .entity import DeviceForecastEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up this integration's per-device sensors (live tracking plus profile preview)."""
    coordinators: dict[str, DeviceForecastCoordinator] = hass.data[DOMAIN][entry.entry_id]
    for subentry_id, coordinator in coordinators.items():
        async_add_entities(
            [
                ForecastPowerSensor(coordinator),
                StatusSensor(coordinator),
                ProfileNameSensor(coordinator),
                ConfidenceSensor(coordinator),
                KnownProfilesSensor(coordinator),
                ProfilePreviewSensor(coordinator),
            ],
            config_subentry_id=subentry_id,
        )


class _DeviceForecastEntity(DeviceForecastEntity, SensorEntity):
    """Common wiring for this integration's per-device sensors."""


class ForecastPowerSensor(_DeviceForecastEntity):
    """Current power draw, with the HAEO ``forecast`` attribute.

    Per docs/REQUIREMENTS.md "Schnittstelle zu HAEO": HAEO reads the current load from
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


class KnownProfilesSensor(_DeviceForecastEntity):
    """List of all profiles learned for this device (Dashboard/Pflege).

    Per docs/REQUIREMENTS.md "Dashboard": profiles are managed as a per-device list.
    Since no custom card is used, the list is exposed as this diagnostic
    sensor's ``profiles`` attribute (state = count) so it can be inspected
    via a standard Entities/Markdown card or Developer Tools, and so
    profile ids are available for the ``rename_profile``/``merge_profiles``
    services. Each profile's own load-curve visualization is out of scope
    for this attribute (docs/REQUIREMENTS.md points to a standard History/Statistics
    graph card fed by the live-tracking entities for that).
    """

    _attr_translation_key = "known_profiles"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DeviceForecastCoordinator) -> None:
        """Initialize the known-profiles sensor."""
        super().__init__(coordinator, "known_profiles")

    @property
    def native_value(self) -> int:
        """Number of profiles currently known for this device."""
        return len(self.coordinator.profiles)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Summary of every known profile (id, name, duration, energy, timestamps)."""
        return {
            "profiles": [
                {
                    "id": profile.id,
                    "name": profile.name,
                    "duration_seconds": profile.duration_seconds(),
                    "energy_wh": profile.total_energy_wh(),
                    "created_at": profile.created_at.isoformat(),
                    "updated_at": profile.updated_at.isoformat(),
                }
                for profile in self.coordinator.profiles
            ]
        }


class ProfilePreviewSensor(_DeviceForecastEntity):
    """Load curve of the profile selected via ``preview_profile`` (Dashboard/Pflege).

    Per docs/REQUIREMENTS.md "Dashboard": a learned profile's load curve runs on a
    relative time axis (seconds since run start), which a standard
    time-axis chart card cannot plot. This sensor anchors the selected
    profile's band to wall-clock time - starting when the preview was
    selected - and exposes it in the same ``{"time", "value"}`` shape as
    the HAEO ``forecast`` attribute, plus ``min``/``max`` per point for the
    band, so a chart card can draw "what this program looks like if it
    started now". The state is the previewed profile's name.
    """

    _attr_translation_key = "profile_preview"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DeviceForecastCoordinator) -> None:
        """Initialize the profile-preview sensor."""
        super().__init__(coordinator, "profile_preview")

    @property
    def native_value(self) -> str | None:
        """Name of the previewed profile, or ``None`` if none is selected."""
        profile = self.coordinator.preview_profile
        return profile.name if profile else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The previewed profile's band as time-anchored forecast points."""
        profile = self.coordinator.preview_profile
        anchor = self.coordinator.preview_anchor
        if profile is None or anchor is None:
            return {
                "profile_id": None,
                "started_at": None,
                "duration_seconds": None,
                "energy_wh": None,
                "forecast": [],
            }

        return {
            "profile_id": profile.id,
            "started_at": anchor.isoformat(),
            "duration_seconds": profile.duration_seconds(),
            "energy_wh": profile.total_energy_wh(),
            "forecast": [
                {
                    "time": (anchor + timedelta(seconds=offset)).isoformat(),
                    "value": mean,
                    "min": minimum,
                    "max": maximum,
                }
                for offset, mean, minimum, maximum in build_curve_points(profile)
            ],
        }
