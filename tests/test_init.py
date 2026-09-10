"""Smoke test verifying the integration sets up and unloads cleanly."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haeo_device_forecast.const import DOMAIN


async def test_setup_and_unload_entry(hass):
    """A config entry should set up and unload without errors."""
    entry = MockConfigEntry(domain=DOMAIN, data={"name": "Waschmaschine"})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state.value == "loaded"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state.value == "not_loaded"
