"""Home Assistant services for managing a device's profiles.

Thin wrappers around :class:`~.coordinator.DeviceForecastCoordinator`'s
profile-management methods, exposed as standard HA services so profile
maintenance (Benennen, Mergen, Suche nach neuen Profilen) can be done via
HA's own UI (Developer Tools > Actions) or automations, per Specs.md
"Dashboard" (Pflege über Standardmechanismen, keine Custom Card).
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import DeviceForecastCoordinator

SERVICE_RENAME_PROFILE = "rename_profile"
SERVICE_MERGE_PROFILES = "merge_profiles"
SERVICE_SEARCH_PROFILES = "search_profiles"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_PROFILE_ID = "profile_id"
ATTR_PROFILE_IDS = "profile_ids"
ATTR_NAME = "name"

_RENAME_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_PROFILE_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
    }
)

_MERGE_PROFILES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_PROFILE_IDS): vol.All(cv.ensure_list, [cv.string], vol.Length(min=2)),
        vol.Required(ATTR_NAME): cv.string,
    }
)

_SEARCH_PROFILES_SCHEMA = vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string})


def _get_coordinator(hass: HomeAssistant, config_entry_id: str) -> DeviceForecastCoordinator:
    """Look up a device's coordinator by config entry id, or raise a user-facing error."""
    try:
        return hass.data[DOMAIN][config_entry_id]
    except KeyError as err:
        raise ServiceValidationError(
            f"Unknown or unloaded HAEO Device Forecast config entry: {config_entry_id}"
        ) from err


def async_register_services(hass: HomeAssistant) -> None:
    """Register this integration's profile-management services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_RENAME_PROFILE):
        return

    async def handle_rename_profile(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call.data[ATTR_CONFIG_ENTRY_ID])
        try:
            await coordinator.async_rename_profile(
                call.data[ATTR_PROFILE_ID], call.data[ATTR_NAME]
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def handle_merge_profiles(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call.data[ATTR_CONFIG_ENTRY_ID])
        try:
            await coordinator.async_merge_profiles(
                call.data[ATTR_PROFILE_IDS], call.data[ATTR_NAME]
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def handle_search_profiles(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call.data[ATTR_CONFIG_ENTRY_ID])
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
