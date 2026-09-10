"""Config flow for HAEO Device Forecast: set up one device to track."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
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

_USER_SCHEMA = vol.Schema(
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
    """Handle a config flow for HAEO Device Forecast (one device per entry)."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> Any:
        """Handle the initial step: pick the device's power sensor and threshold."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_USER_SCHEMA,
            errors=errors,
        )
