# Examples

Practical examples for using HAEO Device Forecast. Replace the example entity ids
(`sensor.washer_...`) with your own: Settings → Devices & services → HAEO Device Forecast →
your device shows its entities.

[Deutsche Version](../de/README.md)

| # | Use case | Uses |
|---|---|---|
| 1 | [Notify when a program starts and ends](01-program-notification.md) | Status, Profile, `estimated_end` |
| 2 | [Use the forecast in HAEO](02-haeo-load-forecast.md) | Forecast power, `forecast` |
| 3 | [Dashboard for operation and profile maintenance](03-dashboard.md) | all entities, actions |

## Entity ids in these examples

Entity ids are derived from the device name and the entity names in the language Home Assistant
had when the device was added. For a device named "Washer" on an English system:

| Entity | Example entity id |
|---|---|
| Forecast power | `sensor.washer_forecast_power` |
| Status | `sensor.washer_status` |
| Profile | `sensor.washer_profile` |
| Match confidence | `sensor.washer_match_confidence` |
| Known profiles | `sensor.washer_known_profiles` |
| Profile preview | `sensor.washer_profile_preview` |
| Search for new profiles | `button.washer_search_for_new_profiles` |
