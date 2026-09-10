"""Button entity to trigger automatic profile discovery for one device.

Per Specs.md "Dashboard" (Für die Pflege: Suche nach neuen Profilen): in
addition to the ``search_profiles`` service, this is exposed as a standard
button entity so it can be triggered with a single click from a dashboard
card or the device page, without going through Developer Tools.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DeviceForecastCoordinator
from .entity import DeviceForecastEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the "search for new profiles" button for every device."""
    coordinators: dict[str, DeviceForecastCoordinator] = hass.data[DOMAIN][entry.entry_id]
    for subentry_id, coordinator in coordinators.items():
        async_add_entities([SearchProfilesButton(coordinator)], config_subentry_id=subentry_id)


class SearchProfilesButton(DeviceForecastEntity, ButtonEntity):
    """Button that re-runs automatic profile discovery for one device."""

    _attr_translation_key = "search_profiles"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DeviceForecastCoordinator) -> None:
        """Initialize the search-profiles button."""
        super().__init__(coordinator, "search_profiles")

    async def async_press(self) -> None:
        """Re-run automatic profile discovery over all stored raw samples."""
        await self.coordinator.async_search_profiles()
