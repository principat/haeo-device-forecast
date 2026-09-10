"""Config flow for HAEO Device Forecast.

One singleton hub config entry is created for the whole integration; each
device to track is added, edited or removed as a config subentry on that
entry ("+ Add device" on the integration's page), per Specs.md "Technische
Anforderungen" - no need for multiple integration instances to manage
multiple devices.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.helpers import selector

from .const import (
    CONF_BUCKET_SECONDS,
    CONF_POWER_ENTITY_ID,
    CONF_START_THRESHOLD,
    DEFAULT_BUCKET_SECONDS,
    DEFAULT_START_THRESHOLD,
    DOMAIN,
)

CONF_NAME = "name"
SUBENTRY_TYPE_DEVICE = "device"

_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_POWER_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="power")
        ),
        vol.Optional(CONF_START_THRESHOLD, default=DEFAULT_START_THRESHOLD): vol.Coerce(float),
        vol.Optional(CONF_BUCKET_SECONDS, default=DEFAULT_BUCKET_SECONDS): vol.Coerce(int),
    }
)


class HaeoDeviceForecastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the (singleton) hub config flow; devices are added as subentries."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> Any:
        """Create the single hub entry; devices are added afterwards as subentries."""
        self._async_abort_entries_match({})
        return self.async_create_entry(title="HAEO Device Forecast", data={})

    @classmethod
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentry types this integration supports."""
        return {SUBENTRY_TYPE_DEVICE: DeviceSubentryFlowHandler}


class DeviceSubentryFlowHandler(ConfigSubentryFlow):
    """Add or reconfigure one device (power sensor to track) under the hub entry."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new device."""
        return await self._async_step_device(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing device."""
        return await self._async_step_device(user_input)

    async def _async_step_device(
        self, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            if self.source == SOURCE_RECONFIGURE:
                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    title=user_input[CONF_NAME],
                    data=user_input,
                )
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        suggested = self._get_reconfigure_subentry().data if self.source == SOURCE_RECONFIGURE else {}
        return self.async_show_form(
            step_id="user" if self.source != "reconfigure" else "reconfigure",
            data_schema=self.add_suggested_values_to_schema(_DEVICE_SCHEMA, suggested),
            errors=errors,
        )
