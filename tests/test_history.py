"""Tests for fetching raw (non-statistics) recorder history for a power sensor."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.haeo_device_forecast.history import fetch_raw_history

from .fixture_loader import load_fixture_states


async def test_fetch_raw_history_returns_numeric_samples_in_order(
    recorder_mock, hass
) -> None:
    entity_id, states = load_fixture_states("waschmaschine_run.json")
    start = dt_util.utcnow()
    for item in states:
        hass.states.async_set(entity_id, item["state"])
        await hass.async_block_till_done()
    await async_wait_recording_done(hass)
    end = dt_util.utcnow() + timedelta(seconds=1)

    samples = await fetch_raw_history(hass, entity_id, start, end)

    assert len(samples) > 0
    assert samples == sorted(samples, key=lambda s: s.timestamp)
    for sample in samples:
        assert isinstance(sample.value, float)


async def test_fetch_raw_history_skips_unavailable_and_unknown_states(
    recorder_mock, hass
) -> None:
    entity_id = "sensor.test_power"
    hass.states.async_set(entity_id, "10")
    await hass.async_block_till_done()
    hass.states.async_set(entity_id, "unavailable")
    await hass.async_block_till_done()
    hass.states.async_set(entity_id, "unknown")
    await hass.async_block_till_done()
    hass.states.async_set(entity_id, "20")
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    now = dt_util.utcnow()
    samples = await fetch_raw_history(
        hass, entity_id, now - timedelta(minutes=5), now + timedelta(minutes=5)
    )

    assert [s.value for s in samples] == [10.0, 20.0]
