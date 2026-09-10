"""Tests for the HA services wrapping profile management (rename/merge/search)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haeo_device_forecast.config_flow import SUBENTRY_TYPE_DEVICE
from custom_components.haeo_device_forecast.const import CONF_POWER_ENTITY_ID, DOMAIN
from custom_components.haeo_device_forecast.models import BandBucket, Profile
from custom_components.haeo_device_forecast.services import (
    ATTR_DEVICE_ID,
    ATTR_NAME,
    ATTR_PROFILE_ID,
    ATTR_PROFILE_IDS,
    SERVICE_MERGE_PROFILES,
    SERVICE_RENAME_PROFILE,
    SERVICE_SEARCH_PROFILES,
    async_register_services,
)

ENTITY_ID = "sensor.test_power"


async def _setup_entry_with_device(hass) -> tuple[MockConfigEntry, str, str]:
    """Set up a hub entry with one device subentry; return (entry, subentry_id, ha_device_id)."""
    hass.states.async_set(ENTITY_ID, "0")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        subentries_data=[
            {
                "data": {"name": "Test", CONF_POWER_ENTITY_ID: ENTITY_ID},
                "subentry_type": SUBENTRY_TYPE_DEVICE,
                "title": "Test",
                "unique_id": None,
            }
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    subentry_id = next(iter(entry.subentries))
    device_entry = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, subentry_id)})
    assert device_entry is not None
    return entry, subentry_id, device_entry.id


async def test_rename_profile_service_updates_coordinator(hass) -> None:
    entry, subentry_id, device_id = await _setup_entry_with_device(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id][subentry_id]
    coordinator.profiles = [
        Profile(
            id="p1",
            name="Old",
            buckets=(),
            pause_windows=(),
            created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        )
    ]
    async_register_services(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_RENAME_PROFILE,
        {ATTR_DEVICE_ID: device_id, ATTR_PROFILE_ID: "p1", ATTR_NAME: "New"},
        blocking=True,
    )

    assert coordinator.profiles[0].name == "New"


async def test_rename_profile_service_raises_for_unknown_device(hass) -> None:
    await _setup_entry_with_device(hass)
    async_register_services(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RENAME_PROFILE,
            {ATTR_DEVICE_ID: "does-not-exist", ATTR_PROFILE_ID: "p1", ATTR_NAME: "New"},
            blocking=True,
        )


async def test_merge_profiles_service(hass) -> None:
    entry, subentry_id, device_id = await _setup_entry_with_device(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id][subentry_id]

    coordinator.profiles = [
        Profile(
            id="a",
            name="A",
            buckets=(BandBucket(offset_seconds=0, min=10.0, mean=10.0, max=10.0),),
            pause_windows=(),
            created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        ),
        Profile(
            id="b",
            name="B",
            buckets=(BandBucket(offset_seconds=0, min=20.0, mean=20.0, max=20.0),),
            pause_windows=(),
            created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        ),
    ]
    async_register_services(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_MERGE_PROFILES,
        {ATTR_DEVICE_ID: device_id, ATTR_PROFILE_IDS: ["a", "b"], ATTR_NAME: "Merged"},
        blocking=True,
    )

    assert len(coordinator.profiles) == 1
    assert coordinator.profiles[0].name == "Merged"


async def test_search_profiles_service(recorder_mock, hass, enable_custom_integrations) -> None:
    entry, subentry_id, device_id = await _setup_entry_with_device(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id][subentry_id]
    async_register_services(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_PROFILES,
        {ATTR_DEVICE_ID: device_id},
        blocking=True,
    )

    assert coordinator.profiles == []  # no recorder history and no raw samples -> no profiles found
