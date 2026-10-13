# 2. Prognose in HAEO nutzen

**Ziel:** [HAEO](https://haeo.io) mit der restlichen Last eines laufenden Geräts planen lassen,
z. B. damit der Hausspeicher nicht ins Netz entladen wird, während der Geschirrspüler noch
Energie braucht.

## Was die Integration bereitstellt

Der Sensor **Prognose-Leistung** (`sensor.waschmaschine_prognose_leistung`) ist alles, was HAEO
braucht:

- **Zustand:** aktuelle Leistungsaufnahme in W (`device_class: power`, `state_class: measurement`)
- **Attribut `forecast`:** die erwartete Leistung für den Rest des Laufs, ein Punkt je 5 Minuten:

  ```json
  [
    { "time": "2026-09-10T14:00:00+02:00", "value": 1200 },
    { "time": "2026-09-10T14:05:00+02:00", "value": 1150 }
  ]
  ```

Solange das Gerät ruht oder noch kein bekanntes Profil zum Lauf passt, ist `forecast` eine leere
Liste.

## Einrichtung in HAEO

In HAEO eine Last anlegen und als Prognosequelle den Sensor Prognose-Leistung des Geräts
auswählen. Weitere HAEO-spezifische Einrichtung ist nicht nötig. Bei mehreren Geräten je Gerät
eine Last anlegen.

## Gut zu wissen

- Die Prognose deckt nur einen bereits gestarteten Lauf ab. Die Vorhersage, *wann* das Gerät
  als Nächstes genutzt wird, ist noch nicht umgesetzt (siehe `docs/REQUIREMENTS.md`).
- Passen zu Beginn eines Laufs mehrere Profile, wird das mit dem höchsten Energieverbrauch
  verwendet – die Prognose kann im weiteren Verlauf also nur kleiner werden.
- Passt kein Profil gut, fällt der Sensor Übereinstimmung unter 90 %; die Prognose verwendet
  dann weiterhin das Profil mit dem höchsten Energieverbrauch.
