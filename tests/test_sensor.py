"""Tests for the sensor entities exposing live-tracking state."""

from __future__ import annotations

from datetime import datetime, timezone

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
    ProfileNameSensor,
    StatusSensor,
)
from custom_components.haeo_device_forecast.storage import DeviceStore

ENTITY_ID = "sensor.test_power"


async def _make_coordinator(hass) -> DeviceForecastCoordinator:
    entry = MockConfigEntry(domain="haeo_device_forecast", data={"power_entity_id": ENTITY_ID})
    store = DeviceStore(hass, entry_id=entry.entry_id)
    coordinator = DeviceForecastCoordinator(
        hass,
        config_entry=entry,
        power_entity_id=ENTITY_ID,
        start_threshold=5.0,
        store=store,
        bucket_seconds=10,
    )
    coordinator.config_entry = entry
    return coordinator


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


async def test_sensors_have_stable_unique_ids_per_entry(hass) -> None:
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
    assert coordinator.config_entry.entry_id in sensor_a.unique_id


async def test_sensors_are_namespaced_by_device_to_avoid_cross_device_collisions(
    hass,
) -> None:
    # Specs.md requires supporting ~10 devices at once; without a device
    # per config entry, has_entity_name would collapse every device's
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
    assert (DOMAIN, coordinator.config_entry.entry_id) in sensor.device_info["identifiers"]
