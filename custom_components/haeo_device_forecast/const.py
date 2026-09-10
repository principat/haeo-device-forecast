"""Constants for the HAEO Device Forecast integration."""

DOMAIN = "haeo_device_forecast"

#: Config/options entry keys.
CONF_POWER_ENTITY_ID = "power_entity_id"
CONF_START_THRESHOLD = "start_threshold"
CONF_BUCKET_SECONDS = "bucket_seconds"

#: Default power (W) above which a device run is considered started.
DEFAULT_START_THRESHOLD = 5.0
#: Default band bucket width in seconds (Specs.md Richtwert: 5-10s).
DEFAULT_BUCKET_SECONDS = 10
