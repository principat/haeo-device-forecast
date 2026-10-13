# Anforderungsspezifikation – HAEO Device Forecast

Dieses Dokument fasst alle fachlichen und technischen Anforderungen zusammen. Es dient als
Referenz, um das Projekt bei Bedarf neu aufzusetzen, und wird fortlaufend gepflegt.
Der Bereich **Funktionale Anforderungen** beschreibt, *was* das Projekt können muss, der
Bereich **Technische Aspekte** *wie* es aktuell umgesetzt ist (kann beim Neuaufbau ersetzt werden).

> **Pflegehinweis:** Bei neuen oder geänderten Anforderungen wird dieses Dokument im selben
> Change aktualisiert. Erledigt = "im aktuellen Code umgesetzt", nicht "irgendwann gewünscht".
> Noch nicht umgesetzte Anforderungen sind mit **Status: noch nicht umgesetzt** markiert.

## 1. Zweck des Projekts

Ich habe Geräte, die nur selten verwendet werden (Waschmaschine, Geschirrspüler). Deren Nutzung ist schlecht planbar. Da sie aber immer ein bestimmtes Programm abarbeiten, haben sie je nach eingestelltem Programm immer wieder die gleiche Lastkurve, meist für mehr als eine Stunde.
Es sollen mehrere Geräte verwaltet werden können.

Ziel ist es, eine Prognose-Lösung zu entwickeln mit folgenden Eigenschaften. Die Lösung wird als native HA-Integration (Custom Component) umgesetzt; ein HA-Add-on (in der HA-UI unter "Apps" geführt) ist ausgeschlossen, u. a. weil es nur auf HA OS/Supervised läuft, nicht auf Core/Container-Installationen.

## 2. Funktionale Anforderungen

### 2.1 Analyse von Lastprofilen über Muster in der Lastverteilung
- Datenbasis: ein Power-Sensor (Leistung, z. B. W) pro Gerät, erfasst über einen dedizierten Smart-Plug-Sensor
  - Für den Anfang wird davon ausgegangen, dass jedes Gerät einen eigenen dedizierten Smart-Plug-Sensor hat (kein Auftrennen aus einem Gesamtzähler)
- Basis der Analyse sind die rohen States der letzten 30 Tage (nicht die von HA aggregierten Langzeitstatistik-/Statistiktabellen), damit die Mustererkennung mit voller Messauflösung arbeitet und nicht durch das 5-Minuten-Raster der Prognoseausgabe eingeschränkt wird. Das 5-Minuten-Raster betrifft ausschließlich die Ausgabe der Prognose (siehe Abschnitt "Erkennen von Lastprofilen während der Nutzung"), nicht die Datenbasis für die Mustererkennung selbst
- Diese Rohdaten sollen dauerhaft aufbewahrt und erweitert werden können
- Erkannte Lastprofile sollen benannt werden können
  - Jedes automatisch gefundene Profil erhält zunächst einen generischen Namen, der vom Nutzer angepasst werden kann
- Programmstart-/Endeerkennung erfolgt rein über den Leistungswert:
  - Start: Überschreiten einer Leistungsschwelle
  - Ende: Unterschreiten der Schwelle für eine bestimmte Zeit (Berücksichtigung des Standby-Verbrauchs). Diese Zeit ist kein fester, global vorgegebener Wert, sondern wird aus den bereits bekannten Profilen des Geräts abgeleitet (z. B. aus der längsten bekannten Pausendauer der infrage kommenden Profile plus Sicherheitsmarge). Ein fester Wert wäre problematisch, da er Pausenphasen innerhalb eines Profils fälschlich als Ende/Abbruch werten und damit eigentlich zusammengehörige Läufe in mehrere Profile aufsplitten könnte
  - Im Programmverlauf enthaltene Pausen (z. B. Einwirkzeit von Lösungsmitteln bei Waschmaschine/Geschirrspüler mit geringem, aber von null verschiedenem Stromverbrauch) sind Teil des Lastprofils und werden beim Erlernen des Profils als solche mit erfasst, nicht als Programmende gewertet
- Die Analyse erfolgt in zwei Modi:
  - Automatisch: Suche nach Profilen über die kompletten 30 Tage
  - Aktuelles Profil: Hier wird das jüngste Lastprofil gesucht, analysiert und kann benannt werden
- Die Unterscheidung, ob ein aufgezeichneter Lauf ein neues Profil ist oder einem bestehenden Profil zugeordnet wird, entscheidet das Programm automatisch. Dabei werden toleriert:
  - Messtoleranzen (Richtwert: 5 %)
  - Kleinere zeitliche Versätze (Richtwert: 5 min)
  - Messwertaussetzer
  - Kurze Unterbrechungen (< 5 min)
- Ein Profil wird nicht als einzelne Lastkurve, sondern als **Band** gespeichert: Die rohen States werden dafür auf ein feineres, aber begrenztes Raster heruntergerechnet (Richtwert: 5–10 s), wobei je Zeit-Bucket `min`, `mean` und `max` der darin liegenden Messwerte abgelegt werden. Fließen mehrere historische Läufe in ein Profil ein (automatisches Clustering oder manuelles Mergen, siehe Abschnitt "Dashboard"/Offene Punkte), ergibt sich das Band aus deren Streuung je Zeit-Bucket – das Profil "lernt" so seine eigene Toleranz aus den beobachteten Läufen, ergänzend zu den o. g. festen Richtwerten

### 2.2 Erkennen von Lastprofilen während der Nutzung
- Prognose des Verlaufs im 5-Minuten-Raster
- Erkennen des laufenden Programms (Zuordnung zu einem bekannten Profil, auch bei nur teilweise bekanntem Verlauf)
  - Passen zu einem Zeitpunkt (z. B. kurz nach dem Start) mehrere Profile gleichzeitig auf den bisherigen Verlauf, wird das Profil mit dem höchsten Gesamtenergieverbrauch für die Prognose angenommen – energetischer Worst Case, sodass sich die tatsächliche Prognose im weiteren Verlauf nur noch nach unten korrigieren kann
  - Passt gar kein bekanntes Profil zum bisherigen Verlauf, wird ebenfalls das zuletzt bekannte Worst-Case-Profil (höchster Energieverbrauch) als Prognose weiter ausgegeben; zusätzlich zeigt ein eigener Sensor den Übereinstimmungsgrad (Konfidenz) in Prozent an, damit erkennbar ist, dass es sich um eine unsichere Zuordnung handelt
    - Berechnungsbasis: Abweichung des tatsächlichen Verlaufs vom aktuell zur Prognose verwendeten Lastprofil über die Zeit – konkret die per DTW (Dynamic Time Warping) ermittelte, zeitversatz-tolerante Ausrichtung des Live-Verlaufs auf das Profil-Band; Messwerte innerhalb des `[min, max]`-Bandes je Zeit-Bucket zählen als Übereinstimmung, Abweichungen außerhalb des Bandes mindern den %-Wert proportional zur Distanz zum Band
    - Liegt die Übereinstimmung unter 90 %, gilt der Lauf als nicht zu einem bestehenden Profil passend ("kein bekanntes Profil")
  - Ist ein Lauf beendet, der während der Laufzeit durchgehend unter 90 % Übereinstimmung lag (kein bekanntes Profil), wird er automatisch als neues Profil mit generischem Namen hinzugefügt (analog zur automatischen Profilerkennung, siehe Abschnitt "Analyse von Lastprofilen")
- Ausgeben des prognostizierten Endes
- Bereitstellung von Sensoren für nachgelagerte Automationen (siehe Abschnitt Benachrichtigung)
- Abbruch-Erkennung: Eine im gelernten Profil enthaltene, geplante Pause (geringer, aber von null verschiedener Verbrauch an der im Profil erwarteten Stelle/Dauer) wird nicht als Ende gewertet, der Status bleibt `running`. Weicht der tatsächliche Verlauf vom erwarteten Profil ab (z. B. Leistung fällt auf reinen Standby-Wert außerhalb einer erwarteten Pausenphase, oder eine erwartete Pause dauert deutlich länger als im Profil), gilt der Lauf als abgebrochen: Der Status wechselt zurück auf `sleeping`, bis ein neuer Lauf per Start-Schwelle erkannt wird
  - Die dabei verwendete Zeitschwelle ist wie bei der Endeerkennung (siehe Abschnitt "Analyse von Lastprofilen") nicht fix, sondern wird aus den bekannten Profilen abgeleitet (z. B. längste bekannte Pausendauer des aktuell wahrscheinlichsten bzw. der noch infrage kommenden Profile plus Sicherheitsmarge). Setzt der Lauf danach fort, deckt die ohnehin vorgesehene zeitliche Toleranz (Richtwert 5 min, siehe "Analyse von Lastprofilen") eine kurze Verzögerung ab; setzt er nicht fort, gilt der Lauf als abgebrochen bzw. – falls es sich um einen noch unbekannten Lauf handelt – als beendet und wird als neues Profil übernommen (siehe oben)

### 2.3 Benachrichtigung
- Die Benachrichtigung selbst ist **nicht** Teil des Kernprogramms, sondern ein optionales Feature, das über eine HA-Automation ausgelöst wird, die vom Nutzer auf Basis der bereitgestellten Sensoren erstellt wird
- Das Programm stellt dafür pro Gerät folgende Sensoren bereit:
  - Aktueller Gerätestatus: `sleeping` / `running`
  - Wahrscheinlichster Programmname
- Die eigentliche Benachrichtigung erfolgt über den HA `notify`-Service; jedes konfigurierte Gerät kann eine eigene Notification-Konfiguration erhalten (Text, Ziel)

### 2.4 Ermitteln einer wahrscheinlichen nächsten Nutzung für die langfristige Forecast-Planung von HAEO

**Status: noch nicht umgesetzt.**

- Es geht hierbei nicht um klassische Anwesenheitserkennung ("ist jemand da"), sondern um das Erkennen wiederkehrender Alltagssituationen (Wochentag, Wochenende, Feiertag, Ferien, Urlaub), die mit der Gerätenutzung korrelieren
- Diese Situationen sollen aus verschiedenen, vom Nutzer frei wählbaren Sensoren des Hauses abgeleitet werden können, z. B.:
  - Türsensoren
  - Allgemeiner Hausstromverbrauch
  - Zeitpunkt der letzten Meldung des E-Autos
- Dieser Bereich ist bewusst vage/offen gehalten, da er flexibel vom Nutzer definiert und angepasst werden können soll. Im Vordergrund steht nicht der aktuelle Zustand dieser Sensoren, sondern die Korrelation zwischen diesen Situationen und der tatsächlichen Gerätenutzung

### 2.5 Schnittstelle zu HAEO (Home Assistant Energy Optimizer)
Geprüft gegen die aktuelle HAEO-Dokumentation (haeo.io, Stand 2026-09):
- Der Prognose-Sensor liefert die **aktuelle Last als State** (Einheit wird automatisch von HAEO übernommen, sofern `unit_of_measurement` am Sensor gesetzt ist)
- Die **Vorschau** wird als `forecast`-Attribut bereitgestellt: eine Liste von Objekten `{"time": <ISO-8601-Zeitstempel inkl. Zeitzone>, "value": <numerischer Wert>}`
- Beispiel:
  ```json
  [
    { "time": "2026-09-10T14:00:00+02:00", "value": 1200 },
    { "time": "2026-09-10T14:05:00+02:00", "value": 1150 }
  ]
  ```
- Die Auflösung im `forecast`-Attribut kann frei gewählt werden (HAEO-Beispiele nutzen stündlich, unsere Prognose läuft im 5-Minuten-Raster) – muss aber konsistent zum Optimierungshorizont von HAEO liegen
- HAEO benötigt ausschließlich diese beiden Attribute (`state` und `forecast`) – keine weitere HAEO-spezifische Registrierung nötig
- Die `device_class` des Sensors soll passend zu einem Leistungssensor gewählt werden (`device_class: power`, `state_class: measurement`, `unit_of_measurement: W`)

### 2.6 Dashboard
- Umsetzung möglichst nah am HA-Standard: Standard-Lovelace-Cards und von der Integration bereitgestellte Entities/Attribute (keine Custom Card, keine zusätzlichen Systemanforderungen/Abhängigkeiten)
- Für den Betrieb: aktuelles Profil sichtbar
  - Name
  - Voraussichtliches Ende
  - Verbrauch aktuell / gesamt
  - ggf. ein Diagramm, das die aktuelle Lastkurve über die geplante legt (über Standard-History/Statistics-Graph-Card auf Basis der bereitgestellten Entities)
- Für die Pflege (umgesetzt über HA-Standardmechanismen wie Options Flow / Services + Standard-Entities, sowie eine Custom Frontend Card für die Profil-Visualisierung, siehe unten)
  - Mehrere Profile werden als Liste je Gerät verwaltet
  - Anzeige der gefundenen Profile, inkl. Visualisierung des jeweiligen Profilverlaufs (Lastkurve): Da Profile über eine relative Zeitachse (Sekunden seit Laufstart) verlaufen statt über eine Wanduhrzeit, kann das nicht unmittelbar über Standard-History/Statistics-Graph-Cards abgebildet werden. Umsetzung in zwei Stufen:
    - Umgesetzt: Die Profil-Vorschau legt die relative Zeitachse eines ausgewählten Profils auf die Wanduhrzeit um. Der Service `preview_profile` wählt das Profil, der Sensor "Profil-Vorschau" stellt dessen Band im selben Punktformat wie das HAEO-`forecast`-Attribut bereit (`time`, `value` = `mean`, zusätzlich `min`/`max` je Punkt), verankert am Zeitpunkt der Auswahl. Damit zeichnet jede Diagramm-Card mit Zeitachse die Lastkurve "so sieht dieses Programm aus, wenn es jetzt startet". Die Auswahl ist reiner Anzeigezustand und wird bewusst nicht persistiert; die Bucket-Auflösung wird auf eine diagrammtaugliche Punktzahl heruntergerechnet, wobei `min`/`max` als Hüllkurve des zusammengefassten Fensters erhalten bleiben (das Band wird also nie zu schmal dargestellt).
    - **Status (Custom Card): noch nicht umgesetzt** – zusätzlich vorgesehen ist eine schlanke Custom Lovelace Card (Frontend-Ressource), die die Bänder direkt auf der relativen Zeitachse zeichnet und die Profilauswahl in der Card selbst anbietet, also ohne Helfer/Automation im Dashboard. Es handelt sich weiterhin um eine native HA-Integration (kein Add-on, siehe "Technische Anforderungen") – die Card wäre nur eine zusätzliche Frontend-Ressource derselben Integration.
  - Die Profilliste selbst stellt der Sensor "Bekannte Profile" als Attribut bereit (ID, Name, Dauer, Energie, Zeitstempel)
  - Benennen von Profilen
  - Zusammenführen ("Mergen") von zwei oder mehr Profilen zu einem – der Name des resultierenden Profils wird beim Mergen abgefragt
  - Löschen einzelner Profile: entfernt nur das gelernte Band, nicht die Rohdaten, aus denen es gelernt wurde. Da die Profilsuche die Liste komplett aus der Rohdaten-Historie neu aufbaut, kann ein gelöschtes Profil dabei wieder entstehen – Löschen ist damit eine Korrektur der aktuellen Liste, keine dauerhafte Ausschlussregel
  - Suche nach neuen Profilen: zusätzlich zum Service als Standard-Button-Entity pro Gerät bereitgestellt, damit sie sich mit einem Klick über eine Dashboard-Karte oder die Geräteseite auslösen lässt (keine Custom Card, `button`-Domain)

## 3. Nicht-funktionale Anforderungen

- Keine YAML-Konfiguration nötig – vollständige Bedienung über die HA-UI.
- Robustheit: Fehler in Nutzereingaben destabilisieren Home Assistant nie.
- Lokalisierte, feldgenaue Fehlermeldungen.
- Testbarkeit ohne reale HA-Instanz plus UI-Rendering-Absicherung im echten Browser.
- Automatisiertes Releasing (Conventional Commits, semantic-release) mit Test-Gate.

## 4. Technische Aspekte (optional beim Neuerstellen)

### 4.1 Technische Anforderungen
- Alle Langzeitdaten sollen so gespeichert werden, dass sie
  - mit einem Mal gelöscht werden können
  - im HA-Backup enthalten sind und daraus wiederhergestellt werden können
  - zwischen verschiedenen Versionen migrierbar sind – daher speichert jeder Datensatz eine Versionsnummer des Schnittstellenformats
- Die konkrete Speichertechnologie (z. B. eigene SQLite-DB, `.storage`-JSON, Graphdatenbank) ist bewusst nicht vorgegeben, sondern soll passend zum Problem (Ähnlichkeitssuche über Zeitreihen/Muster) gewählt werden
- Unterstützte Sprachen für Config-Flow-/Dashboard-UI: Deutsch und Englisch
- Skalierung: bis zu ca. 10 Geräte gleichzeitig verwaltbar
- Architektur: native HA-Integration (Custom Component), kein HA-Add-on – u. a. damit die Lösung auf allen Installationsarten (Core/Container, nicht nur OS/Supervised) läuft, nativen Zugriff auf Recorder/History und die Entity-Registry hat und über HACS verteilt werden kann
- Einrichtung über **einen** Config-Entry (Hub): Der Nutzer richtet die Integration einmalig ein; jedes zu überwachende Gerät wird darin als **Config-Subentry** ("+ Gerät hinzufügen" auf der Integrationsseite) angelegt, bearbeitet und entfernt – es sind keine mehrfachen Integrationsinstanzen für mehrere Geräte nötig

### 4.2 Plattform & Aufbau

- `custom_components/haeo_device_forecast/` mit den Plattformen `sensor` und `button`; Profilverwaltung über die Services `rename_profile`, `merge_profiles`, `delete_profile`, `search_profiles` sowie `preview_profile` für die Profil-Vorschau.
- Speicherung: je Gerät zwei HA-`Store`-Dateien unter `.storage/` (Rohdaten und Profile), jeweils mit eigener Formatversion; Profile tragen zusätzlich eine `schema_version`.
- Rohdaten-Basis: Recorder-History des Leistungssensors (beim ersten Start die letzten 30 Tage), danach fortlaufend in die eigene Langzeitspeicherung übernommen.
- Analyse in `analysis/` (Segmentierung, Banding, Clustering, DTW, Prognose), Abhängigkeit `numpy`.
- Mindestversion Home Assistant laut `hacs.json`; die in `requirements_test.txt` gepinnte HA-Version gibt die Python-Version für CI und Devcontainer vor.

### 4.3 Tests

- `tests/`: gemocktes HA über `pytest-homeassistant-custom-component`, schnell; Aufruf immer mit `python -m pytest`.
- `tests/test_translations.py`: ICU-Syntax, kein Markdown in Section-Überschriften, en/de-Gleichstand, Laden über HAs echten Translation-Loader.
- `tests_e2e/`: echte, wegwerfbare `hass`-Instanz mit echtem Frontend, gesteuert per Playwright/Chromium; eigene `pytest.ini` (deaktiviert HA-Mock- und Socket-Plugin) und eigene `requirements_e2e.txt`.

### 4.4 CI/CD

- `.github/workflows/test.yml`: Unit-Tests auf jedem Pull Request.
- `.github/workflows/test-e2e.yml`: Browser-E2E-Tests auf jedem Pull Request (kein Release-Gate).
- `.github/workflows/release.yml`: auf `master` – Tests als Gate (`needs: test`), dann semantic-release (`.releaserc.json`); `scripts/bump_version.py` schreibt die Version in `manifest.json`, `CHANGELOG.md` und Release-Commit `chore(release): x.y.z [skip ci]` entstehen nur in CI.

## 5. Offene Punkte
- **Mustererkennungs-Algorithmus**: Festgelegt: Dynamic Time Warping (DTW) auf Basis der Profil-Bänder (siehe Abschnitt "Analyse von Lastprofilen"). Die rohen States werden auf ein 5–10-s-Raster mit `min`/`mean`/`max` je Bucket heruntergerechnet; DTW richtet den (ggf. unvollständigen) Live-Verlauf anhand der `mean`-Reihe zeitversatz-tolerant am Profil aus; als lokale Kostenfunktion wird statt der üblichen Euklidischen Distanz eine bandbewusste Funktion verwendet (Kosten 0 innerhalb `[min, max]`, sonst proportional zum Abstand zum Band). Offen ist noch die konkrete Parametrisierung (genaue Bucket-Größe, exakte Formel zur Umrechnung der DTW-Gesamtkosten in den %-Konfidenzwert, Begrenzung der DTW-Bandbreite/Fensterung für die Performance) – das ist Implementierungsdetail und muss die Spec nicht weiter vorgeben.
- **Mehrere Profile pro Gerät / Mergen**: Geklärt (siehe Dashboard/Pflege sowie "Analyse von Lastprofilen"): Profile werden als Liste je Gerät mit Visualisierung verwaltet; das Mergen zweier Profile ist eine manuelle Korrektur der automatischen Erkennung, vergrößert das Band (`min`/`max` je Zeit-Bucket) entsprechend der Streuung der zusammengeführten Läufe und fragt den Namen des resultierenden Profils beim Nutzer ab.
- **Abbruch/Pause eines Laufs**: Geklärt (siehe "Erkennen von Lastprofilen während der Nutzung" bzw. "Analyse von Lastprofilen"): geplante Pausen sind Teil des Profils; die Zeitschwelle, ab der eine Pause als Abbruch gilt, ist nicht fix, sondern wird aus der längsten bekannten Pausendauer der infrage kommenden Profile abgeleitet, um zu verhindern, dass profilinterne Pausen fälschlich als Abbruch erkannt und zusammengehörige Läufe in mehrere Profile aufgesplittet werden.
