"""Tests for the versioned, backup-safe device storage layer."""

from __future__ import annotations

from datetime import datetime, timezone

from custom_components.haeo_device_forecast.models import BandBucket, Profile, RawSample
from custom_components.haeo_device_forecast.storage import DeviceStore


async def test_append_and_load_raw_samples_accumulates_across_calls(hass, hass_storage) -> None:
    store = DeviceStore(hass, device_id="entry1")

    await store.async_append_raw_samples(
        [RawSample(timestamp=datetime(2026, 9, 3, tzinfo=timezone.utc), value=1.0)]
    )
    await store.async_append_raw_samples(
        [RawSample(timestamp=datetime(2026, 9, 4, tzinfo=timezone.utc), value=2.0)]
    )

    samples = await store.async_load_raw_samples()

    assert [s.value for s in samples] == [1.0, 2.0]


async def test_raw_samples_persist_across_store_instances(hass, hass_storage) -> None:
    store_a = DeviceStore(hass, device_id="entry1")
    await store_a.async_append_raw_samples(
        [RawSample(timestamp=datetime(2026, 9, 3, tzinfo=timezone.utc), value=1.0)]
    )

    store_b = DeviceStore(hass, device_id="entry1")
    samples = await store_b.async_load_raw_samples()

    assert [s.value for s in samples] == [1.0]


async def test_two_devices_do_not_share_storage(hass, hass_storage) -> None:
    store_a = DeviceStore(hass, device_id="entry1")
    store_b = DeviceStore(hass, device_id="entry2")

    await store_a.async_append_raw_samples(
        [RawSample(timestamp=datetime(2026, 9, 3, tzinfo=timezone.utc), value=1.0)]
    )

    assert await store_a.async_load_raw_samples() != []
    assert await store_b.async_load_raw_samples() == []


async def test_save_and_load_profiles_round_trip(hass, hass_storage) -> None:
    store = DeviceStore(hass, device_id="entry1")
    profile = Profile(
        id="p1",
        name="Eco 50°",
        buckets=(BandBucket(offset_seconds=0, min=0.0, mean=0.0, max=2.0),),
        pause_windows=(),
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    await store.async_save_profiles([profile])
    profiles = await store.async_load_profiles()

    assert profiles == [profile]


async def test_load_profiles_returns_empty_list_when_nothing_stored(hass, hass_storage) -> None:
    store = DeviceStore(hass, device_id="entry1")

    assert await store.async_load_profiles() == []


async def test_async_remove_all_wipes_raw_samples_and_profiles(hass, hass_storage) -> None:
    store = DeviceStore(hass, device_id="entry1")
    await store.async_append_raw_samples(
        [RawSample(timestamp=datetime(2026, 9, 3, tzinfo=timezone.utc), value=1.0)]
    )
    await store.async_save_profiles(
        [
            Profile(
                id="p1",
                name="Test",
                buckets=(),
                pause_windows=(),
                created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
                updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            )
        ]
    )

    await store.async_remove_all()

    assert await store.async_load_raw_samples() == []
    assert await store.async_load_profiles() == []


async def test_stored_payload_carries_schema_version_for_migration(hass, hass_storage) -> None:
    store = DeviceStore(hass, device_id="entry1")
    await store.async_append_raw_samples(
        [RawSample(timestamp=datetime(2026, 9, 3, tzinfo=timezone.utc), value=1.0)]
    )

    raw_key = store.raw_samples_store.key
    assert hass_storage[raw_key]["version"] == DeviceStore.RAW_SAMPLES_VERSION
