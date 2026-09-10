"""Smoke test verifying the integration sets up and unloads cleanly."""

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haeo_device_forecast.const import CONF_POWER_ENTITY_ID, DOMAIN


async def test_setup_and_unload_entry(hass):
    """A config entry should set up, expose its five sensors, and unload without errors."""
    hass.states.async_set("sensor.waschmaschine_power", "0")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"name": "Waschmaschine", CONF_POWER_ENTITY_ID: "sensor.waschmaschine_power"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state.value == "loaded"

    registry = er.async_get(hass)
    entries_for_device = [
        entity for entity in registry.entities.values() if entity.config_entry_id == entry.entry_id
    ]
    assert len(entries_for_device) == 5

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state.value == "not_loaded"
