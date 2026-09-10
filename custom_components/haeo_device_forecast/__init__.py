"""The HAEO Device Forecast integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BUCKET_SECONDS,
    CONF_POWER_ENTITY_ID,
    CONF_START_THRESHOLD,
    DEFAULT_BUCKET_SECONDS,
    DEFAULT_START_THRESHOLD,
    DOMAIN,
)
from .coordinator import DeviceForecastCoordinator
from .services import async_register_services
from .storage import DeviceStore

PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HAEO Device Forecast from a config entry.

    Creates the device's long-term storage and its live-tracking
    coordinator, loads any previously learned profiles, and forwards setup
    to the sensor platform.
    """
    store = DeviceStore(hass, entry_id=entry.entry_id)
    coordinator = DeviceForecastCoordinator(
        hass,
        config_entry=entry,
        power_entity_id=entry.data[CONF_POWER_ENTITY_ID],
        start_threshold=entry.data.get(CONF_START_THRESHOLD, DEFAULT_START_THRESHOLD),
        store=store,
        bucket_seconds=entry.data.get(CONF_BUCKET_SECONDS, DEFAULT_BUCKET_SECONDS),
    )
    await coordinator.async_load_profiles()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    async_register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
