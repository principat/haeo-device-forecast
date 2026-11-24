# 3. Dashboard für Betrieb und Profilpflege

**Ziel:** das laufende Programm auf einen Blick sehen und die gelernten Profile pflegen
(auflisten, nach neuen suchen, umbenennen, zusammenführen) – nur mit Standard-Karten.

## Betrieb

```yaml
type: entities
title: Waschmaschine
entities:
  - entity: sensor.waschmaschine_status
  - entity: sensor.waschmaschine_profil
  - entity: sensor.waschmaschine_prognose_leistung
  - type: attribute
    entity: sensor.waschmaschine_prognose_leistung
    attribute: estimated_end
    name: Voraussichtliches Ende
    format: time
  - entity: sensor.waschmaschine_ubereinstimmung
```

Aktuelle Leistung im Zeitverlauf, zusammen mit dem Status:

```yaml
type: history-graph
title: Waschmaschine heute
hours_to_show: 12
entities:
  - entity: sensor.waschmaschine_prognose_leistung
  - entity: sensor.waschmaschine_status
```

## Profilpflege

Liste aller gelernten Profile, mit den IDs, die die Aktionen unten brauchen:

```yaml
type: markdown
title: Profile der Waschmaschine
content: |
  | Profil | Dauer | Energie | ID |
  |---|---|---|---|
  {% for p in state_attr('sensor.waschmaschine_bekannte_profile', 'profiles') or [] -%}
  | {{ p.name }} | {{ (p.duration_seconds / 60) | round }} min | {{ (p.energy_wh / 1000) | round(2) }} kWh | `{{ p.id }}` |
  {% endfor %}
```

Button, der die gespeicherten Rohdaten nach neuen Profilen durchsucht:

```yaml
type: button
entity: button.waschmaschine_nach_neuen_profilen_suchen
name: Nach neuen Profilen suchen
show_state: false
```

Profile umbenennen oder zusammenführen mit den Aktionen `haeo_device_forecast.rename_profile`
und `haeo_device_forecast.merge_profiles` (Entwicklerwerkzeuge → Aktionen oder in einem Skript).
Das Gerät wird aus einer Liste gewählt, die Profil-IDs stehen in der Tabelle oben:

```yaml
action: haeo_device_forecast.merge_profiles
data:
  device_id: <Gerät der Waschmaschine>
  profile_ids:
    - <ID 1>
    - <ID 2>
  name: Eco 40-60
```

Einzelnes Profil löschen (entfernt nur das gelernte Band – die Rohdaten bleiben erhalten, eine
spätere Profilsuche kann ein gleichwertiges Profil also neu anlegen):

```yaml
action: haeo_device_forecast.delete_profile
data:
  device_id: <Gerät der Waschmaschine>
  profile_id: <ID>
```

## Lastkurve eines Profils als Diagramm

Profile laufen über eine relative Zeitachse (Sekunden seit Laufstart), eine History-Graph-Card
kann sie deshalb nicht direkt zeichnen. Die Aktion `preview_profile` legt das Band des gewählten
Profils auf die aktuelle Uhrzeit um und stellt es als Attribut `forecast` des Sensors
"Profil-Vorschau" bereit – mit `value` (Mittelwert) sowie `min`/`max` je Punkt:

```yaml
action: haeo_device_forecast.preview_profile
data:
  device_id: <Gerät der Waschmaschine>
  profile_id: <ID>
```

Ohne `profile_id` wird die Vorschau geleert. Danach zeichnet jede Diagramm-Card mit Zeitachse die
Kurve, zum Beispiel:

```yaml
type: markdown
title: Profil-Vorschau
content: |
  **{{ states('sensor.waschmaschine_profil_vorschau') }}** –
  {{ (state_attr('sensor.waschmaschine_profil_vorschau', 'duration_seconds') / 60) | round }} min,
  {{ (state_attr('sensor.waschmaschine_profil_vorschau', 'energy_wh') / 1000) | round(2) }} kWh
```

Praktisch ist eine Automation, die `preview_profile` bei jeder Änderung einer `input_select` mit
den Profil-IDs aufruft – dann wechselt das Diagramm direkt mit der Auswahl im Dashboard.

## Zusammenführung vorab ansehen

Vor dem Zusammenführen kann `preview_profile` zeigen, was dabei herauskäme. Dazu `profile_ids`
(zwei oder mehr) statt `profile_id` übergeben – es wird nichts verändert, es ist ein Probelauf von
`merge_profiles`:

```yaml
action: haeo_device_forecast.preview_profile
data:
  device_id: <Gerät der Waschmaschine>
  profile_ids:
    - <ID 1>
    - <ID 2>
```

Das Attribut `forecast` des Sensors "Profil-Vorschau" enthält dann das **Ergebnis der
Zusammenführung**, das Attribut `source_profiles` die zusammengeführten Profile (`profile_id`,
`name`, `forecast`). Die Quellen lassen sich blass oder gepunktet neben dem Ergebnis zeichnen, z. B.
mit [apexcharts-card](https://github.com/RomRider/apexcharts-card) (Custom Card, über HACS
installierbar):

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Vorschau Zusammenführung
span:
  start: minute
graph_span: 3h
series:
  - entity: sensor.waschmaschine_profil_vorschau
    name: Ergebnis
    type: line
    stroke_width: 3
    data_generator: |
      return entity.attributes.forecast.map(p => [new Date(p.time).getTime(), p.value]);
  - entity: sensor.waschmaschine_profil_vorschau
    name: Quelle 1
    type: line
    stroke_width: 1
    opacity: 0.4
    data_generator: |
      const s = entity.attributes.source_profiles[0];
      return s ? s.forecast.map(p => [new Date(p.time).getTime(), p.value]) : [];
  - entity: sensor.waschmaschine_profil_vorschau
    name: Quelle 2
    type: line
    stroke_width: 1
    opacity: 0.4
    data_generator: |
      const s = entity.attributes.source_profiles[1];
      return s ? s.forecast.map(p => [new Date(p.time).getTime(), p.value]) : [];
```

Führst du danach `merge_profiles` mit genau diesen Profilen aus, zeigt die Vorschau weiter das
gespeicherte Ergebnis (`source_profiles` ist dann leer, weil die Quellen nicht mehr existieren).
