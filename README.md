# HAEO Device Forecast

Home Assistant Custom Component (HACS) für die Lastprognose selten genutzter Geräte (z. B. Waschmaschine, Geschirrspüler).

Das Programm erkennt anhand eines Leistungssensors wiederkehrende Lastprofile ("Programme") eines Geräts, speichert sie als toleranz-bewusstes Band (min/mean/max je Zeit-Bucket) und erkennt laufende Programme live per Dynamic-Time-Warping-Abgleich gegen die bekannten Profile. Daraus wird eine 5-Minuten-Prognose erzeugt, die u. a. für [HAEO (Home Assistant Energy Optimizer)](https://haeo.io) nutzbar ist.

Details zu Zielen, Architektur und Verhalten: siehe [Specs.md](Specs.md).

## Features

- Automatische Erkennung von Lastprofilen aus der Rohdaten-Historie eines Leistungssensors
- Live-Tracking (`sleeping`/`running`), Prognose des Programmendes, Konfidenz-Anzeige
- `forecast`-Attribut im von HAEO erwarteten Format
- Profilverwaltung über HA-Services (`rename_profile`, `merge_profiles`, `search_profiles`)
- Mehrsprachig (Deutsch/Englisch)

## Installation

### Über HACS

1. HACS → Integrationen → Menü (⋮) → Benutzerdefinierte Repositories
2. Repository-URL dieses Projekts hinzufügen, Kategorie „Integration“
3. „HAEO Device Forecast“ installieren und Home Assistant neu starten

### Manuell

`custom_components/haeo_device_forecast` in das `custom_components`-Verzeichnis der HA-Konfiguration kopieren und Home Assistant neu starten.

## Einrichtung

Einstellungen → Geräte & Dienste → Integration hinzufügen → „HAEO Device Forecast“. Anschließend Name, Leistungssensor des Geräts sowie optional Startschwelle und Bucket-Breite angeben.

## Entwicklung

```bash
pip install -r requirements.txt -r requirements_test.txt
pytest
ruff check .
```

Lokale HA-Testinstanz: `./scripts/develop` (Port 8123).
