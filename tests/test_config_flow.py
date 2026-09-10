"""Tests for the config flow that sets up one device."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.haeo_device_forecast.const import (
    CONF_POWER_ENTITY_ID,
    CONF_START_THRESHOLD,
    DOMAIN,
)


async def test_user_flow_creates_entry_with_defaults(hass) -> None:
    hass.states.async_set("sensor.geschirrspueler_power", "0")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Geschirrspüler",
            CONF_POWER_ENTITY_ID: "sensor.geschirrspueler_power",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Geschirrspüler"
    assert result["data"][CONF_POWER_ENTITY_ID] == "sensor.geschirrspueler_power"
    assert result["data"][CONF_START_THRESHOLD] == 5.0


async def test_user_flow_accepts_custom_threshold(hass) -> None:
    hass.states.async_set("sensor.waschmaschine_power", "0")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Waschmaschine",
            CONF_POWER_ENTITY_ID: "sensor.waschmaschine_power",
            CONF_START_THRESHOLD: 8.0,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_START_THRESHOLD] == 8.0
