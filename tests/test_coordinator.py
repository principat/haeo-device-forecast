"""Tests for the live-tracking coordinator's state machine."""

from __future__ import annotations

from datetime import timedelta

from freezegun import freeze_time
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haeo_device_forecast.coordinator import (
    STATUS_RUNNING,
    STATUS_SLEEPING,
    DeviceForecastCoordinator,
)
from custom_components.haeo_device_forecast.storage import DeviceStore

ENTITY_ID = "sensor.test_power"


async def _make_coordinator(hass) -> DeviceForecastCoordinator:
    entry = MockConfigEntry(domain="haeo_device_forecast", data={})
    subentry_id = "subentry1"
    store = DeviceStore(hass, device_id=subentry_id)
    return DeviceForecastCoordinator(
        hass,
        config_entry=entry,
        subentry_id=subentry_id,
        device_name="Testgerät",
        power_entity_id=ENTITY_ID,
        start_threshold=5.0,
        store=store,
        bucket_seconds=10,
    )


async def test_stays_sleeping_below_threshold(hass, hass_storage) -> None:
    coordinator = await _make_coordinator(hass)
    hass.states.async_set(ENTITY_ID, "1.0")

    await coordinator.async_refresh()

    assert coordinator.status == STATUS_SLEEPING
    assert coordinator.data.status == STATUS_SLEEPING
    assert coordinator.data.forecast == []


async def test_transitions_to_running_above_threshold(hass, hass_storage) -> None:
    coordinator = await _make_coordinator(hass)
    hass.states.async_set(ENTITY_ID, "60.0")

    await coordinator.async_refresh()

    assert coordinator.status == STATUS_RUNNING
    assert coordinator.data.status == STATUS_RUNNING
    assert coordinator.data.current_power == 60.0


async def test_short_dip_does_not_end_run(hass, hass_storage) -> None:
    with freeze_time("2026-09-03 20:00:00") as frozen:
        coordinator = await _make_coordinator(hass)
        hass.states.async_set(ENTITY_ID, "60.0")
        await coordinator.async_refresh()
        assert coordinator.status == STATUS_RUNNING

        frozen.tick(timedelta(seconds=30))
        hass.states.async_set(ENTITY_ID, "1.0")  # brief dip
        await coordinator.async_refresh()
        assert coordinator.status == STATUS_RUNNING

        frozen.tick(timedelta(seconds=30))
        hass.states.async_set(ENTITY_ID, "60.0")  # resumes
        await coordinator.async_refresh()

        assert coordinator.status == STATUS_RUNNING


async def test_run_ends_after_sustained_low_power_and_is_learned_as_profile(
    hass, hass_storage
) -> None:
    with freeze_time("2026-09-03 20:00:00") as frozen:
        coordinator = await _make_coordinator(hass)
        hass.states.async_set(ENTITY_ID, "60.0")
        await coordinator.async_refresh()
        assert coordinator.status == STATUS_RUNNING

        frozen.tick(timedelta(seconds=10))
        hass.states.async_set(ENTITY_ID, "1.0")
        await coordinator.async_refresh()

        # No known profiles yet -> default end timeout (5 min) + margin (60s).
        frozen.tick(timedelta(seconds=400))
        hass.states.async_set(ENTITY_ID, "1.0")
        await coordinator.async_refresh()

        assert coordinator.status == STATUS_SLEEPING
        assert len(coordinator.profiles) == 1
        stored = await coordinator._store.async_load_profiles()
        assert len(stored) == 1


async def test_forecast_reflects_matched_profile(hass, hass_storage) -> None:
    coordinator = await _make_coordinator(hass)
    from datetime import datetime, timezone

    from custom_components.haeo_device_forecast.models import BandBucket, Profile

    coordinator.profiles = [
        Profile(
            id="p1",
            name="Eco",
            buckets=(
                BandBucket(offset_seconds=0, min=55.0, mean=60.0, max=65.0),
                BandBucket(offset_seconds=300, min=55.0, mean=60.0, max=65.0),
                BandBucket(offset_seconds=600, min=0.0, mean=0.0, max=2.0),
            ),
            pause_windows=(),
            created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        )
    ]
    hass.states.async_set(ENTITY_ID, "60.0")

    await coordinator.async_refresh()

    assert coordinator.data.profile_name == "Eco"
    assert coordinator.data.confidence_percent == 100.0
    assert len(coordinator.data.forecast) > 0
    assert coordinator.data.forecast[0]["value"] == 60.0


async def test_async_rename_profile_updates_name_and_persists(hass, hass_storage) -> None:
    import pytest

    coordinator = await _make_coordinator(hass)
    from datetime import datetime, timezone

    from custom_components.haeo_device_forecast.models import Profile

    profile = Profile(
        id="p1",
        name="Profil 1",
        buckets=(),
        pause_windows=(),
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    coordinator.profiles = [profile]

    await coordinator.async_rename_profile("p1", "Eco 50°")

    assert coordinator.profiles[0].name == "Eco 50°"
    stored = await coordinator._store.async_load_profiles()
    assert stored[0].name == "Eco 50°"

    with pytest.raises(ValueError):
        await coordinator.async_rename_profile("unknown", "x")


async def test_async_merge_profiles_combines_and_persists(hass, hass_storage) -> None:
    coordinator = await _make_coordinator(hass)
    from datetime import datetime, timezone

    from custom_components.haeo_device_forecast.models import BandBucket, Profile

    profile_a = Profile(
        id="a",
        name="A",
        buckets=(BandBucket(offset_seconds=0, min=10.0, mean=10.0, max=10.0),),
        pause_windows=(),
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    profile_b = Profile(
        id="b",
        name="B",
        buckets=(BandBucket(offset_seconds=0, min=20.0, mean=20.0, max=20.0),),
        pause_windows=(),
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    coordinator.profiles = [profile_a, profile_b]

    merged = await coordinator.async_merge_profiles(["a", "b"], "Merged")

    assert merged.name == "Merged"
    assert [p.id for p in coordinator.profiles] == [merged.id]
    assert coordinator.profiles[0].buckets[0].min == 10.0
    assert coordinator.profiles[0].buckets[0].max == 20.0
    stored = await coordinator._store.async_load_profiles()
    assert len(stored) == 1


async def test_async_search_profiles_rebuilds_from_stored_raw_samples(hass, hass_storage) -> None:
    coordinator = await _make_coordinator(hass)
    from datetime import datetime, timedelta, timezone

    from custom_components.haeo_device_forecast.models import RawSample

    t0 = datetime(2026, 9, 3, 20, 0, tzinfo=timezone.utc)
    samples = [
        RawSample(timestamp=t0, value=60.0),
        RawSample(timestamp=t0 + timedelta(seconds=10), value=60.0),
        RawSample(timestamp=t0 + timedelta(seconds=20), value=1.0),
    ]
    await coordinator._store.async_append_raw_samples(samples)

    profiles = await coordinator.async_search_profiles()

    assert len(profiles) == 1
    assert coordinator.profiles == profiles
