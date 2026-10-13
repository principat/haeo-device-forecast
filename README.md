# HAEO Device Forecast

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/principat/haeo-device-forecast)](https://github.com/principat/haeo-device-forecast/releases)
[![License](https://img.shields.io/github/license/principat/haeo-device-forecast)](LICENSE)

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=principat&repository=haeo-device-forecast&category=integration)
[![Open your Home Assistant instance and start setting up this integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=haeo_device_forecast)

**English** | [Deutsche Version](#deutsch) (further down in this file)

Home Assistant custom integration (HACS) that forecasts the load of rarely used appliances such
as washing machines or dishwashers.

From a power sensor, it learns the recurring load profiles ("programs") of an appliance, stores
each one as a tolerance-aware band (min/mean/max per time bucket) and recognizes running programs
live by matching them against the known profiles with Dynamic Time Warping. The result is a
5-minute forecast that [HAEO (Home Assistant Energy Optimizer)](https://haeo.io) and others can
use.

## Features

- Automatic discovery of load profiles from the raw history of a power sensor
- Live tracking (`sleeping`/`running`), forecast of the program end, match confidence
- `forecast` attribute in the format HAEO expects
- Profile management through Home Assistant actions (`rename_profile`, `merge_profiles`,
  `delete_profile`, `search_profiles`) and a "Search for new profiles" button per device
- A profile's load curve as a chart: `preview_profile` puts the selected profile's band on
  the "Profile preview" sensor, anchored to the current time
- Several appliances in one integration entry, each added as its own device
- English and German UI

## Installation

### HACS

The easiest way is the badge above ("Open your Home Assistant instance and open this repository
inside the Home Assistant Community Store"), which opens HACS directly on this integration.

Manually in HACS:

1. HACS → Integrations → menu (⋮) → Custom repositories
2. Add this repository's URL, category "Integration"
3. Install "HAEO Device Forecast" and restart Home Assistant

### Manual

Copy `custom_components/haeo_device_forecast` into the `custom_components` folder of your Home
Assistant configuration and restart Home Assistant.

## Setup

1. Settings → Devices & services → Add integration → "HAEO Device Forecast". This creates the
   integration entry (once).
2. On the integration's page, add each appliance with **Add device**: name, the appliance's
   power sensor, and optionally the start threshold (W) and the band bucket width (s).

Devices can be edited or removed later from the same page.

## Entities per device

| Entity | Meaning |
|---|---|
| Forecast power | Current power (W) as state; `forecast` attribute (5-minute grid) for HAEO; `estimated_end` attribute |
| Status | `sleeping` or `running` |
| Profile | Name of the profile currently used for the forecast (diagnostic) |
| Match confidence | How well the running program matches that profile, in % (diagnostic) |
| Known profiles | Number of learned profiles; `profiles` attribute with id, name, duration, energy (diagnostic) |
| Profile preview | Name of the profile selected via `preview_profile`; `forecast` attribute with its load curve (`value` = mean, plus `min`/`max` per point) on a wall-clock axis starting when it was selected (diagnostic) |
| Search for new profiles | Button that re-runs profile discovery over all stored raw data (diagnostic) |

## Examples

Notification when a program ends, using the forecast in HAEO, and a dashboard: see
[examples/en](examples/en/README.md).

---

# Deutsch

[English version](#haeo-device-forecast)

Home Assistant Custom Integration (HACS) für die Lastprognose selten genutzter Geräte
(z. B. Waschmaschine, Geschirrspüler).

Die Integration erkennt anhand eines Leistungssensors wiederkehrende Lastprofile ("Programme")
eines Geräts, speichert sie als toleranz-bewusstes Band (min/mean/max je Zeit-Bucket) und erkennt
laufende Programme live per Dynamic-Time-Warping-Abgleich gegen die bekannten Profile. Daraus
wird eine 5-Minuten-Prognose erzeugt, die u. a. für
[HAEO (Home Assistant Energy Optimizer)](https://haeo.io) nutzbar ist.

## Funktionen

- Automatische Erkennung von Lastprofilen aus der Rohdaten-Historie eines Leistungssensors
- Live-Tracking (`sleeping`/`running`), Prognose des Programmendes, Konfidenz-Anzeige
- `forecast`-Attribut im von HAEO erwarteten Format
- Profilverwaltung über Home-Assistant-Aktionen (`rename_profile`, `merge_profiles`,
  `delete_profile`, `search_profiles`) und einen Button "Nach neuen Profilen suchen" je Gerät
- Lastkurve eines Profils als Diagramm: `preview_profile` legt das Band des gewählten Profils
  auf den Sensor "Profil-Vorschau", bezogen auf die aktuelle Uhrzeit
- Mehrere Geräte in einem Integrationseintrag, jedes als eigenes Gerät angelegt
- Oberfläche auf Deutsch und Englisch

## Installation

### Über HACS

Am einfachsten über den Badge oben ("Open your Home Assistant instance and open this repository
inside the Home Assistant Community Store") – öffnet HACS direkt auf dieser Integration.

Manuell in HACS:

1. HACS → Integrationen → Menü (⋮) → Benutzerdefinierte Repositories
2. Repository-URL dieses Projekts hinzufügen, Kategorie "Integration"
3. "HAEO Device Forecast" installieren und Home Assistant neu starten

### Manuell

`custom_components/haeo_device_forecast` in das `custom_components`-Verzeichnis der
HA-Konfiguration kopieren und Home Assistant neu starten.

## Einrichtung

1. Einstellungen → Geräte & Dienste → Integration hinzufügen → "HAEO Device Forecast". Damit wird
   der Integrationseintrag (einmalig) angelegt.
2. Auf der Seite der Integration jedes Gerät über **Gerät hinzufügen** ergänzen: Name,
   Leistungssensor des Geräts sowie optional Startschwelle (W) und Band-Bucket-Breite (s).

Geräte lassen sich später auf derselben Seite bearbeiten oder entfernen.

## Entitäten je Gerät

| Entität | Bedeutung |
|---|---|
| Prognose-Leistung | Aktuelle Leistung (W) als Zustand; Attribut `forecast` (5-Minuten-Raster) für HAEO; Attribut `estimated_end` |
| Status | `sleeping` (Ruhend) oder `running` (Läuft) |
| Profil | Name des aktuell für die Prognose verwendeten Profils (Diagnose) |
| Übereinstimmung | Wie gut das laufende Programm zu diesem Profil passt, in % (Diagnose) |
| Bekannte Profile | Anzahl gelernter Profile; Attribut `profiles` mit ID, Name, Dauer, Energie (Diagnose) |
| Profil-Vorschau | Name des über `preview_profile` gewählten Profils; Attribut `forecast` mit dessen Lastkurve (`value` = Mittelwert, dazu `min`/`max` je Punkt) auf einer Wanduhr-Zeitachse ab dem Zeitpunkt der Auswahl (Diagnose) |
| Nach neuen Profilen suchen | Button, der die Profilerkennung über alle gespeicherten Rohdaten erneut ausführt (Diagnose) |

## Beispiele

Benachrichtigung bei Programmende, Nutzung der Prognose in HAEO und ein Dashboard: siehe
[examples/de](examples/de/README.md).

---

## Entwicklung

Anforderungen und Architektur: [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md).

```bash
pip install -r requirements_test.txt
python -m pytest
ruff check .
```

Immer `python -m pytest` verwenden (ein bloßes `pytest` hat das Repo-Root nicht im `sys.path`).

Browser-E2E-Tests (echte, wegwerfbare HA-Instanz mit echtem Frontend, Playwright/Chromium):

```bash
pip install -r requirements_e2e.txt
python -m playwright install --with-deps chromium
python -m pytest tests_e2e
```

Lokale HA-Testinstanz: `./scripts/develop` (Port 8123).

Releases entstehen automatisch per semantic-release aus den Commit-Nachrichten
(Conventional Commits: `fix` → Patch, `feat` → Minor, `feat!`/`BREAKING CHANGE:` → Major;
`docs`/`chore`/`ci`/`test` erzeugen kein Release). Version in `manifest.json`, `CHANGELOG.md`
und Release-Commits werden ausschließlich von CI gepflegt.
