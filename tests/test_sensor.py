"""Tests for the sensor entities exposing live-tracking state."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haeo_device_forecast.const import DOMAIN
from custom_components.haeo_device_forecast.coordinator import (
    STATUS_RUNNING,
    STATUS_SLEEPING,
    DeviceForecastCoordinator,
    DeviceForecastData,
)
from custom_components.haeo_device_forecast.sensor import (
    ConfidenceSensor,
    ForecastPowerSensor,
    KnownProfilesSensor,
    ProfileNameSensor,
    ProfilePreviewSensor,
    StatusSensor,
)
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


async def test_sensors_reflect_sleeping_state(hass) -> None:
    coordinator = await _make_coordinator(hass)
    coordinator.data = DeviceForecastData(
        status=STATUS_SLEEPING,
        profile_name=None,
        confidence_percent=None,
        current_power=1.0,
        estimated_end=None,
        forecast=[],
    )

    status_sensor = StatusSensor(coordinator)
    power_sensor = ForecastPowerSensor(coordinator)
    profile_sensor = ProfileNameSensor(coordinator)
    confidence_sensor = ConfidenceSensor(coordinator)

    assert status_sensor.native_value == STATUS_SLEEPING
    assert power_sensor.native_value == 1.0
    assert power_sensor.device_class == "power"
    assert power_sensor.state_class == "measurement"
    assert power_sensor.native_unit_of_measurement == "W"
    assert power_sensor.extra_state_attributes["forecast"] == []
    assert profile_sensor.native_value is None
    assert confidence_sensor.native_value is None


async def test_sensors_reflect_running_state_with_forecast(hass) -> None:
    coordinator = await _make_coordinator(hass)
    estimated_end = datetime(2026, 9, 3, 21, 0, tzinfo=timezone.utc)
    forecast = [{"time": "2026-09-03T20:30:00+00:00", "value": 60.0}]
    coordinator.data = DeviceForecastData(
        status=STATUS_RUNNING,
        profile_name="Eco 50°",
        confidence_percent=97.5,
        current_power=60.0,
        estimated_end=estimated_end,
        forecast=forecast,
    )

    status_sensor = StatusSensor(coordinator)
    power_sensor = ForecastPowerSensor(coordinator)
    profile_sensor = ProfileNameSensor(coordinator)
    confidence_sensor = ConfidenceSensor(coordinator)

    assert status_sensor.native_value == STATUS_RUNNING
    assert power_sensor.native_value == 60.0
    assert power_sensor.extra_state_attributes["forecast"] == forecast
    assert power_sensor.extra_state_attributes["estimated_end"] == estimated_end.isoformat()
    assert profile_sensor.native_value == "Eco 50°"
    assert confidence_sensor.native_value == 97.5
    assert confidence_sensor.native_unit_of_measurement == "%"


async def test_sensors_have_stable_unique_ids_per_device(hass) -> None:
    coordinator = await _make_coordinator(hass)
    coordinator.data = DeviceForecastData(
        status=STATUS_SLEEPING,
        profile_name=None,
        confidence_percent=None,
        current_power=None,
        estimated_end=None,
        forecast=[],
    )

    sensor_a = ForecastPowerSensor(coordinator)
    sensor_b = ForecastPowerSensor(coordinator)

    assert sensor_a.unique_id == sensor_b.unique_id
    assert SUBENTRY_ID in sensor_a.unique_id


async def test_sensors_are_namespaced_by_device_to_avoid_cross_device_collisions(
    hass,
) -> None:
    # docs/REQUIREMENTS.md requires supporting ~10 devices at once; without a device
    # per config subentry, has_entity_name would collapse every device's
    # "Status" sensor to the same generic entity_id (sensor.status).
    coordinator = await _make_coordinator(hass)
    coordinator.data = DeviceForecastData(
        status=STATUS_SLEEPING,
        profile_name=None,
        confidence_percent=None,
        current_power=None,
        estimated_end=None,
        forecast=[],
    )

    sensor = StatusSensor(coordinator)

    assert sensor.device_info is not None
    assert (DOMAIN, SUBENTRY_ID) in sensor.device_info["identifiers"]
    assert sensor.device_info["name"] == "Testgerät"


async def test_known_profiles_sensor_lists_all_learned_profiles(hass) -> None:
    from custom_components.haeo_device_forecast.models import BandBucket, Profile

    coordinator = await _make_coordinator(hass)
    coordinator.data = DeviceForecastData(
        status=STATUS_SLEEPING,
        profile_name=None,
        confidence_percent=None,
        current_power=None,
        estimated_end=None,
        forecast=[],
    )
    coordinator.profiles = [
        Profile(
            id="p1",
            name="Eco 50°",
            buckets=(
                BandBucket(offset_seconds=0, min=55.0, mean=60.0, max=65.0),
                BandBucket(offset_seconds=600, min=0.0, mean=0.0, max=2.0),
            ),
            pause_windows=(),
            created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        ),
        Profile(
            id="p2",
            name="Intensiv 65°",
            buckets=(),
            pause_windows=(),
            created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        ),
    ]

    sensor = KnownProfilesSensor(coordinator)

    assert sensor.native_value == 2
    profiles_attr = sensor.extra_state_attributes["profiles"]
    assert len(profiles_attr) == 2
    assert profiles_attr[0]["id"] == "p1"
    assert profiles_attr[0]["name"] == "Eco 50°"
    assert profiles_attr[0]["duration_seconds"] == 600
    assert profiles_attr[0]["energy_wh"] == pytest.approx(5.0)
    assert profiles_attr[0]["updated_at"] == "2026-09-02T00:00:00+00:00"


def _profile_with_band():
    from custom_components.haeo_device_forecast.models import BandBucket, Profile

    return Profile(
        id="p1",
        name="Eco 50°",
        buckets=(
            BandBucket(offset_seconds=0, min=55.0, mean=60.0, max=65.0),
            BandBucket(offset_seconds=600, min=0.0, mean=0.0, max=2.0),
        ),
        pause_windows=(),
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
    )


async def test_profile_preview_sensor_is_empty_without_a_selection(hass) -> None:
    coordinator = await _make_coordinator(hass)
    coordinator.profiles = [_profile_with_band()]

    sensor = ProfilePreviewSensor(coordinator)

    assert sensor.native_value is None
    assert sensor.extra_state_attributes["forecast"] == []
    assert sensor.extra_state_attributes["profile_id"] is None


async def test_profile_preview_sensor_exposes_the_selected_profiles_band(hass) -> None:
    coordinator = await _make_coordinator(hass)
    coordinator.profiles = [_profile_with_band()]
    coordinator.async_set_profile_preview("p1")

    sensor = ProfilePreviewSensor(coordinator)
    attributes = sensor.extra_state_attributes

    assert sensor.native_value == "Eco 50°"
    assert attributes["profile_id"] == "p1"
    assert attributes["duration_seconds"] == 600
    assert [point["value"] for point in attributes["forecast"]] == [60.0, 0.0]
    assert attributes["forecast"][0]["min"] == 55.0
    assert attributes["forecast"][0]["max"] == 65.0
    # The relative band is anchored to wall-clock time, 600 s apart.
    first = datetime.fromisoformat(attributes["forecast"][0]["time"])
    last = datetime.fromisoformat(attributes["forecast"][1]["time"])
    assert (last - first).total_seconds() == 600
    assert attributes["started_at"] == coordinator.preview_anchor.isoformat()


async def test_profile_preview_sensor_clears_when_the_previewed_profile_is_deleted(hass) -> None:
    coordinator = await _make_coordinator(hass)
    coordinator.profiles = [_profile_with_band()]
    coordinator.async_set_profile_preview("p1")

    await coordinator.async_delete_profile("p1")

    sensor = ProfilePreviewSensor(coordinator)
    assert sensor.native_value is None
    assert sensor.extra_state_attributes["forecast"] == []
