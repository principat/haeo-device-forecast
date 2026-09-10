"""Tests for the hub config flow and the per-device subentry flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.haeo_device_forecast.config_flow import SUBENTRY_TYPE_DEVICE
from custom_components.haeo_device_forecast.const import (
    CONF_POWER_ENTITY_ID,
    CONF_START_THRESHOLD,
    DOMAIN,
)


async def test_user_flow_creates_singleton_hub_entry(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HAEO Device Forecast"
    assert result["data"] == {}


async def test_user_flow_aborts_if_hub_already_exists(hass) -> None:
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert first["type"] is FlowResultType.CREATE_ENTRY

    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert second["type"] is FlowResultType.ABORT
    # manifest.json's single_config_entry catches this before our own
    # _async_abort_entries_match({}) safety net would ever run.
    assert second["reason"] == "single_instance_allowed"


async def test_device_subentry_flow_adds_a_device(hass) -> None:
    hub = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    entry = hass.config_entries.async_get_entry(hub["result"].entry_id)
    hass.states.async_set("sensor.geschirrspueler_power", "0")

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
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

    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.title == "Geschirrspüler"
    assert subentry.subentry_type == SUBENTRY_TYPE_DEVICE


async def test_device_subentry_reconfigure_updates_existing_device(hass) -> None:
    hub = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    entry = hass.config_entries.async_get_entry(hub["result"].entry_id)
    hass.states.async_set("sensor.waschmaschine_power", "0")

    add_result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": config_entries.SOURCE_USER},
    )
    add_result = await hass.config_entries.subentries.async_configure(
        add_result["flow_id"],
        {"name": "Waschmaschine", CONF_POWER_ENTITY_ID: "sensor.waschmaschine_power"},
    )
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    subentry_id = next(iter(entry.subentries))

    reconfigure_result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": config_entries.SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )
    assert reconfigure_result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        reconfigure_result["flow_id"],
        {
            "name": "Waschmaschine",
            CONF_POWER_ENTITY_ID: "sensor.waschmaschine_power",
            CONF_START_THRESHOLD: 8.0,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert len(entry.subentries) == 1
    assert entry.subentries[subentry_id].data[CONF_START_THRESHOLD] == 8.0
