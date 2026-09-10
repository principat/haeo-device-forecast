"""Home Assistant services for managing a device's profiles.

Thin wrappers around :class:`~.coordinator.DeviceForecastCoordinator`'s
profile-management methods, exposed as standard HA services so profile
maintenance (Benennen, Mergen, Suche nach neuen Profilen) can be done via
HA's own UI (Developer Tools > Actions) or automations, per Specs.md
"Dashboard" (Pflege über Standardmechanismen, keine Custom Card). Devices
are targeted by their HA device id (one hub config entry manages multiple
devices as config subentries, each registered as its own HA device).
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import DeviceForecastCoordinator

SERVICE_RENAME_PROFILE = "rename_profile"
SERVICE_MERGE_PROFILES = "merge_profiles"
SERVICE_SEARCH_PROFILES = "search_profiles"

ATTR_DEVICE_ID = "device_id"
ATTR_PROFILE_ID = "profile_id"
ATTR_PROFILE_IDS = "profile_ids"
ATTR_NAME = "name"

_RENAME_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_PROFILE_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
    }
)

_MERGE_PROFILES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_PROFILE_IDS): vol.All(cv.ensure_list, [cv.string], vol.Length(min=2)),
        vol.Required(ATTR_NAME): cv.string,
    }
)

_SEARCH_PROFILES_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})


def _get_coordinator(hass: HomeAssistant, device_id: str) -> DeviceForecastCoordinator:
    """Look up a device's coordinator by its HA device id.

    Args:
        hass: The Home Assistant instance.
        device_id: The HA device registry id of the target device.

    Returns:
        The device's live-tracking coordinator.

    Raises:
        ServiceValidationError: If ``device_id`` is not a known
            HAEO Device Forecast device.
    """
    device_entry = dr.async_get(hass).async_get(device_id)
    if device_entry is not None:
        for entry_id, subentry_ids in device_entry.config_entries_subentries.items():
            devices = hass.data.get(DOMAIN, {}).get(entry_id)
            if not devices:
                continue
            for subentry_id in subentry_ids:
                if subentry_id in devices:
                    return devices[subentry_id]

    raise ServiceValidationError(f"Unknown HAEO Device Forecast device: {device_id}")


def async_register_services(hass: HomeAssistant) -> None:
    """Register this integration's profile-management services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_RENAME_PROFILE):
        return

    async def handle_rename_profile(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call.data[ATTR_DEVICE_ID])
        try:
            await coordinator.async_rename_profile(
                call.data[ATTR_PROFILE_ID], call.data[ATTR_NAME]
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def handle_merge_profiles(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call.data[ATTR_DEVICE_ID])
        try:
            await coordinator.async_merge_profiles(
                call.data[ATTR_PROFILE_IDS], call.data[ATTR_NAME]
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def handle_search_profiles(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call.data[ATTR_DEVICE_ID])
        await coordinator.async_search_profiles()

    hass.services.async_register(
        DOMAIN, SERVICE_RENAME_PROFILE, handle_rename_profile, schema=_RENAME_PROFILE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MERGE_PROFILES, handle_merge_profiles, schema=_MERGE_PROFILES_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SEARCH_PROFILES, handle_search_profiles, schema=_SEARCH_PROFILES_SCHEMA
    )
