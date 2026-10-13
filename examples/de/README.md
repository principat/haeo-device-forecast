# Beispiele

Praxisbeispiele für HAEO Device Forecast. Die Beispiel-Entity-IDs (`sensor.waschmaschine_...`)
durch die eigenen ersetzen: Einstellungen → Geräte & Dienste → HAEO Device Forecast → das
eigene Gerät zeigt seine Entitäten.

[English version](../en/README.md)

| # | Anwendungsfall | Nutzt |
|---|---|---|
| 1 | [Benachrichtigung bei Programmstart und -ende](01-programm-benachrichtigung.md) | Status, Profil, `estimated_end` |
| 2 | [Prognose in HAEO nutzen](02-haeo-lastprognose.md) | Prognose-Leistung, `forecast` |
| 3 | [Dashboard für Betrieb und Profilpflege](03-dashboard.md) | alle Entitäten, Aktionen |

## Entity-IDs in diesen Beispielen

Entity-IDs entstehen aus dem Gerätenamen und den Entitätsnamen in der Sprache, die Home
Assistant beim Anlegen des Geräts hatte. Für ein Gerät "Waschmaschine" auf einem deutschen
System:

| Entität | Beispiel-Entity-ID |
|---|---|
| Prognose-Leistung | `sensor.waschmaschine_prognose_leistung` |
| Status | `sensor.waschmaschine_status` |
| Profil | `sensor.waschmaschine_profil` |
| Übereinstimmung | `sensor.waschmaschine_ubereinstimmung` |
| Bekannte Profile | `sensor.waschmaschine_bekannte_profile` |
| Profil-Vorschau | `sensor.waschmaschine_profil_vorschau` |
| Nach neuen Profilen suchen | `button.waschmaschine_nach_neuen_profilen_suchen` |
