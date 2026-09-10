"""Tests for the per-device 'search for new profiles' button."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haeo_device_forecast.button import SearchProfilesButton
from custom_components.haeo_device_forecast.const import DOMAIN
from custom_components.haeo_device_forecast.coordinator import DeviceForecastCoordinator
from custom_components.haeo_device_forecast.models import RawSample
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


async def test_pressing_button_runs_profile_search(hass, hass_storage) -> None:
    coordinator = await _make_coordinator(hass)
    t0 = datetime(2026, 9, 3, 20, 0, tzinfo=timezone.utc)
    await coordinator._store.async_append_raw_samples(
        [
            RawSample(timestamp=t0, value=60.0),
            RawSample(timestamp=t0 + timedelta(seconds=10), value=60.0),
            RawSample(timestamp=t0 + timedelta(seconds=20), value=1.0),
        ]
    )
    button = SearchProfilesButton(coordinator)

    await button.async_press()

    assert len(coordinator.profiles) == 1
