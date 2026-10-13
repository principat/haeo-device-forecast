# 1. Benachrichtigung bei Programmstart und -ende

**Ziel:** kurz nach dem Start des Geräts eine Nachricht mit dem erkannten Programm und dem
voraussichtlichen Ende erhalten, und eine weitere, wenn es fertig ist.

Benachrichtigungen sind bewusst nicht Teil der Integration: Sie werden als eigene Automation
auf Basis des Status-Sensors angelegt, mit einem beliebigen `notify`-Ziel.

## Programm gestartet (mit voraussichtlichem Ende)

Wartet 5 Minuten nach dem Start, damit der Live-Abgleich genug vom Lauf gesehen hat, um ein
Profil zuzuordnen. `estimated_end` ist leer, solange kein Profil passt; das Template fängt das ab.

```yaml
alias: Waschmaschine gestartet
triggers:
  - trigger: state
    entity_id: sensor.waschmaschine_status
    to: running
    for: "00:05:00"
actions:
  - action: notify.notify
    data:
      title: Waschmaschine
      message: >
        {% set end = state_attr('sensor.waschmaschine_prognose_leistung', 'estimated_end') %}
        Programm {{ states('sensor.waschmaschine_profil') }} läuft,
        voraussichtlich fertig um {{ as_timestamp(end) | timestamp_custom('%H:%M') if end else 'unbekannt' }}.
mode: single
```

## Programm beendet

```yaml
alias: Waschmaschine fertig
triggers:
  - trigger: state
    entity_id: sensor.waschmaschine_status
    from: running
    to: sleeping
actions:
  - action: notify.notify
    data:
      title: Waschmaschine
      message: Die Waschmaschine ist fertig.
mode: single
```

**Hinweis:** Ein als abgebrochen erkannter Lauf (z. B. Leistung fällt außerhalb einer erwarteten
Pause auf Standby) wechselt ebenfalls von `running` auf `sleeping` – die Nachricht kommt dann
also auch.

`notify.notify` durch das eigene Ziel ersetzen, z. B. `notify.mobile_app_<eigenes_handy>`.
