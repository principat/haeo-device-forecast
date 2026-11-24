# 3. Dashboard for operation and profile maintenance

**Goal:** see the running program at a glance, and maintain the learned profiles (list them,
search for new ones, rename, merge) with standard cards only.

## Operation

```yaml
type: entities
title: Washer
entities:
  - entity: sensor.washer_status
  - entity: sensor.washer_profile
  - entity: sensor.washer_forecast_power
  - type: attribute
    entity: sensor.washer_forecast_power
    attribute: estimated_end
    name: Expected end
    format: time
  - entity: sensor.washer_match_confidence
```

Current power over time, together with the status:

```yaml
type: history-graph
title: Washer today
hours_to_show: 12
entities:
  - entity: sensor.washer_forecast_power
  - entity: sensor.washer_status
```

## Profile maintenance

List of all learned profiles, with the ids needed for the actions below:

```yaml
type: markdown
title: Washer profiles
content: |
  | Profile | Duration | Energy | Id |
  |---|---|---|---|
  {% for p in state_attr('sensor.washer_known_profiles', 'profiles') or [] -%}
  | {{ p.name }} | {{ (p.duration_seconds / 60) | round }} min | {{ (p.energy_wh / 1000) | round(2) }} kWh | `{{ p.id }}` |
  {% endfor %}
```

Button to search the stored raw data for new profiles:

```yaml
type: button
entity: button.washer_search_for_new_profiles
name: Search for new profiles
show_state: false
```

Rename or merge profiles with the actions `haeo_device_forecast.rename_profile` and
`haeo_device_forecast.merge_profiles` (Developer tools → Actions, or in a script). The device is
selected from a list; the profile ids come from the table above:

```yaml
action: haeo_device_forecast.merge_profiles
data:
  device_id: <device of the washer>
  profile_ids:
    - <id 1>
    - <id 2>
  name: Eco 40-60
```

Delete a single profile (removes only the learned band – the raw samples are kept, so a later
profile search can create an equivalent profile again):

```yaml
action: haeo_device_forecast.delete_profile
data:
  device_id: <the washer's device>
  profile_id: <ID>
```

## A profile's load curve as a chart

Profiles run on a relative time axis (seconds since the run started), so a history-graph card
cannot plot them directly. The `preview_profile` action maps the selected profile's band onto the
current time and exposes it as the `forecast` attribute of the "Profile preview" sensor – with
`value` (the mean) plus `min`/`max` per point:

```yaml
action: haeo_device_forecast.preview_profile
data:
  device_id: <the washer's device>
  profile_id: <ID>
```

Omitting `profile_id` clears the preview. Any chart card with a time axis then draws the curve,
for example:

```yaml
type: markdown
title: Profile preview
content: |
  **{{ states('sensor.washer_profile_preview') }}** –
  {{ (state_attr('sensor.washer_profile_preview', 'duration_seconds') / 60) | round }} min,
  {{ (state_attr('sensor.washer_profile_preview', 'energy_wh') / 1000) | round(2) }} kWh
```

A handy addition is an automation that calls `preview_profile` whenever an `input_select` holding
the profile IDs changes – the chart then follows the dashboard selection directly.

## Previewing a merge

Before merging, `preview_profile` can show what the merge would produce. Pass `profile_ids`
(two or more) instead of `profile_id` – nothing is changed, it is a dry run of `merge_profiles`:

```yaml
action: haeo_device_forecast.preview_profile
data:
  device_id: <the washer's device>
  profile_ids:
    - <id 1>
    - <id 2>
```

The `forecast` attribute of the "Profile preview" sensor then holds the **merge result**, and the
`source_profiles` attribute lists the profiles being merged (`profile_id`, `name`, `forecast`).
Draw the sources faded or dotted next to the result, e.g. with
[apexcharts-card](https://github.com/RomRider/apexcharts-card) (a custom card, installable via HACS):

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Merge preview
span:
  start: minute
graph_span: 3h
series:
  - entity: sensor.washer_profile_preview
    name: Merge result
    type: line
    stroke_width: 3
    data_generator: |
      return entity.attributes.forecast.map(p => [new Date(p.time).getTime(), p.value]);
  - entity: sensor.washer_profile_preview
    name: Source 1
    type: line
    stroke_width: 1
    opacity: 0.4
    data_generator: |
      const s = entity.attributes.source_profiles[0];
      return s ? s.forecast.map(p => [new Date(p.time).getTime(), p.value]) : [];
  - entity: sensor.washer_profile_preview
    name: Source 2
    type: line
    stroke_width: 1
    opacity: 0.4
    data_generator: |
      const s = entity.attributes.source_profiles[1];
      return s ? s.forecast.map(p => [new Date(p.time).getTime(), p.value]) : [];
```

If you then run `merge_profiles` with exactly these profiles, the preview keeps showing the saved
result (the `source_profiles` list is empty afterwards, since the sources no longer exist).
