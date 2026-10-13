# 2. Use the forecast in HAEO

**Goal:** let [HAEO](https://haeo.io) plan with the remaining load of a running appliance, e.g.
so the home battery is not discharged into the grid while the dishwasher still needs energy.

## What the integration provides

The **Forecast power** sensor (`sensor.washer_forecast_power`) is all HAEO needs:

- **State:** current power draw in W (`device_class: power`, `state_class: measurement`)
- **`forecast` attribute:** the expected power for the rest of the run, one point per 5 minutes:

  ```json
  [
    { "time": "2026-09-10T14:00:00+02:00", "value": 1200 },
    { "time": "2026-09-10T14:05:00+02:00", "value": 1150 }
  ]
  ```

While the appliance is sleeping, or while no known profile matches the run yet, `forecast` is
an empty list.

## Setup in HAEO

In HAEO, add a load and select the appliance's Forecast power sensor as its forecast source.
No other HAEO-specific setup is needed. With several appliances, add one load per appliance.

## Things to know

- The forecast only covers a run that has already started. Predicting *when* the appliance
  will be used next is not implemented yet (see `docs/REQUIREMENTS.md`).
- If several profiles fit the beginning of a run, the one with the highest energy is used, so
  the forecast can only get smaller as the run goes on.
- If no profile fits well, the Match confidence sensor drops below 90 %; the forecast then
  still uses the highest-energy profile.
