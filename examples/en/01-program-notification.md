# 1. Notify when a program starts and ends

**Goal:** get a message with the recognized program and its expected end shortly after the
appliance starts, and another one when it is done.

Notifications are deliberately not built into the integration: you create them as your own
automation on top of the Status sensor, with whatever `notify` target you like.

## Program started (with expected end)

Waits 5 minutes after the start so the live matching has seen enough of the run to pick a
profile. `estimated_end` is empty as long as no profile matches; the template handles that.

```yaml
alias: Washer started
triggers:
  - trigger: state
    entity_id: sensor.washer_status
    to: running
    for: "00:05:00"
actions:
  - action: notify.notify
    data:
      title: Washer
      message: >
        {% set end = state_attr('sensor.washer_forecast_power', 'estimated_end') %}
        Program {{ states('sensor.washer_profile') }} is running,
        expected end {{ as_timestamp(end) | timestamp_custom('%H:%M') if end else 'unknown' }}.
mode: single
```

## Program finished

```yaml
alias: Washer finished
triggers:
  - trigger: state
    entity_id: sensor.washer_status
    from: running
    to: sleeping
actions:
  - action: notify.notify
    data:
      title: Washer
      message: The washing machine has finished.
mode: single
```

**Note:** a run that is detected as aborted (for example power drops to standby outside an
expected pause) also goes from `running` to `sleeping`, so this message also appears then.

Replace `notify.notify` with your own target, e.g. `notify.mobile_app_<your_phone>`.
