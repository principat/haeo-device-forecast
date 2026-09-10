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


async def test_async_search_profiles_pulls_recorder_history_and_finds_profiles(
    recorder_mock, hass, hass_storage
) -> None:
    # Regression test: search_profiles must work even when the device's own
    # storage is still empty (fresh install, no run has completed yet under
    # live-tracking) by pulling raw states from the recorder, per Specs.md
    # "Analyse von Lastprofilen" (automatischer Modus über die letzten 30 Tage).
    from pytest_homeassistant_custom_component.components.recorder.common import (
        async_wait_recording_done,
    )

    coordinator = await _make_coordinator(hass)
    hass.states.async_set(ENTITY_ID, "60.0")
    await hass.async_block_till_done()
    hass.states.async_set(ENTITY_ID, "70.0")  # distinct value: recorder dedupes unchanged states
    await hass.async_block_till_done()
    hass.states.async_set(ENTITY_ID, "1.0")
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    profiles = await coordinator.async_search_profiles()

    assert len(profiles) == 1
    assert coordinator.profiles == profiles
    stored = await coordinator._store.async_load_raw_samples()
    assert len(stored) == 3  # the fetched recorder history was also persisted


async def test_async_search_profiles_only_fetches_the_gap_since_last_stored_sample(
    recorder_mock, hass, hass_storage
) -> None:
    from pytest_homeassistant_custom_component.components.recorder.common import (
        async_wait_recording_done,
    )

    coordinator = await _make_coordinator(hass)
    hass.states.async_set(ENTITY_ID, "60.0")
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)
    await coordinator.async_search_profiles()
    first_load = await coordinator._store.async_load_raw_samples()
    assert len(first_load) == 1

    hass.states.async_set(ENTITY_ID, "1.0")
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)
    await coordinator.async_search_profiles()

    second_load = await coordinator._store.async_load_raw_samples()
    assert len(second_load) == 2  # appended, not duplicated or refetched from scratch
