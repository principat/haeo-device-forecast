"""Smoke tests verifying the hub entry sets up multiple devices and unloads cleanly."""

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haeo_device_forecast.config_flow import SUBENTRY_TYPE_DEVICE
from custom_components.haeo_device_forecast.const import CONF_POWER_ENTITY_ID, DOMAIN


def _device_subentry(name: str, power_entity_id: str) -> dict:
    return {
        "data": {"name": name, CONF_POWER_ENTITY_ID: power_entity_id},
        "subentry_type": SUBENTRY_TYPE_DEVICE,
        "title": name,
        "unique_id": None,
    }


async def test_setup_creates_five_entities_per_device_and_unloads_cleanly(hass):
    """A hub entry with two device subentries exposes 5 entities each, then unloads."""
    hass.states.async_set("sensor.waschmaschine_power", "0")
    hass.states.async_set("sensor.geschirrspueler_power", "0")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HAEO Device Forecast",
        data={},
        subentries_data=[
            _device_subentry("Waschmaschine", "sensor.waschmaschine_power"),
            _device_subentry("Geschirrspüler", "sensor.geschirrspueler_power"),
        ],
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state.value == "loaded"

    registry = er.async_get(hass)
    entries_for_hub = [
        entity for entity in registry.entities.values() if entity.config_entry_id == entry.entry_id
    ]
    assert len(entries_for_hub) == 12  # 6 entities (5 sensors + 1 button) x 2 devices

    per_subentry_counts: dict[str, int] = {}
    for entity in entries_for_hub:
        per_subentry_counts[entity.config_subentry_id] = (
            per_subentry_counts.get(entity.config_subentry_id, 0) + 1
        )
    assert list(per_subentry_counts.values()) == [6, 6]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state.value == "not_loaded"


async def test_reloads_when_a_device_subentry_is_added(hass):
    """Adding a device subentry after setup reloads the entry with the new device."""
    hass.states.async_set("sensor.waschmaschine_power", "0")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HAEO Device Forecast",
        data={},
        subentries_data=[_device_subentry("Waschmaschine", "sensor.waschmaschine_power")],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.geschirrspueler_power", "0")
    from homeassistant.config_entries import ConfigSubentry

    subentry_data = _device_subentry("Geschirrspüler", "sensor.geschirrspueler_power")

    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=subentry_data["data"],
            subentry_type=subentry_data["subentry_type"],
            title=subentry_data["title"],
            unique_id=None,
        ),
    )
    await hass.async_block_till_done()

    coordinators = hass.data[DOMAIN][entry.entry_id]
    assert len(coordinators) == 2
