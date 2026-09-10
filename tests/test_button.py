"""Tests for the per-device 'search for new profiles' button."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haeo_device_forecast.button import SearchProfilesButton
from custom_components.haeo_device_forecast.const import DOMAIN
from custom_components.haeo_device_forecast.coordinator import DeviceForecastCoordinator
from custom_components.haeo_device_forecast.storage import DeviceStore

ENTITY_ID = "sensor.test_power"
SUBENTRY_ID = "subentry1"


async def _make_coordinator(hass) -> DeviceForecastCoordinator:
    entry = MockConfigEntry(domain="haeo_device_forecast", data={})
    store = DeviceStore(hass, device_id=SUBENTRY_ID)
    return DeviceForecastCoordinator(
        hass,
        config_entry=entry,
        subentry_id=SUBENTRY_ID,
        device_name="Testgerät",
        power_entity_id=ENTITY_ID,
        start_threshold=5.0,
        store=store,
        bucket_seconds=10,
    )


async def test_button_is_namespaced_by_device(hass) -> None:
    coordinator = await _make_coordinator(hass)

    button = SearchProfilesButton(coordinator)

    assert SUBENTRY_ID in button.unique_id
    assert (DOMAIN, SUBENTRY_ID) in button.device_info["identifiers"]


async def test_pressing_button_runs_profile_search(recorder_mock, hass, hass_storage) -> None:
    from pytest_homeassistant_custom_component.components.recorder.common import (
        async_wait_recording_done,
    )

    coordinator = await _make_coordinator(hass)
    hass.states.async_set(ENTITY_ID, "60.0")
    await hass.async_block_till_done()
    hass.states.async_set(ENTITY_ID, "60.0")
    await hass.async_block_till_done()
    hass.states.async_set(ENTITY_ID, "1.0")
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)
    button = SearchProfilesButton(coordinator)

    await button.async_press()

    assert len(coordinator.profiles) == 1
