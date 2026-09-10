"""The HAEO Device Forecast integration.

One hub config entry manages any number of devices, each represented by a
config subentry (Specs.md "Technische Anforderungen"). Every subentry gets
its own long-term storage and live-tracking coordinator.
"""

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

PLATFORMS: list[str] = ["sensor", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HAEO Device Forecast from the hub config entry.

    Creates one long-term storage and one live-tracking coordinator per
    device (config subentry), loads any previously learned profiles for
    each, and forwards setup to the sensor/button platforms.
    """
    coordinators: dict[str, DeviceForecastCoordinator] = {}
    for subentry_id, subentry in entry.subentries.items():
        store = DeviceStore(hass, device_id=subentry_id)
        coordinator = DeviceForecastCoordinator(
            hass,
            config_entry=entry,
            subentry_id=subentry_id,
            device_name=subentry.title,
            power_entity_id=subentry.data[CONF_POWER_ENTITY_ID],
            start_threshold=subentry.data.get(CONF_START_THRESHOLD, DEFAULT_START_THRESHOLD),
            store=store,
            bucket_seconds=subentry.data.get(CONF_BUCKET_SECONDS, DEFAULT_BUCKET_SECONDS),
        )
        await coordinator.async_load_profiles()
        await coordinator.async_config_entry_first_refresh()
        coordinators[subentry_id] = coordinator

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinators
    async_register_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_reload_on_subentry_change))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload_on_subentry_change(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when a device (subentry) is added, edited, or removed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the hub config entry (all of its devices)."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
