# Zusammenfassung
Ich habe Geräte, die nur selten verwendet werden (Waschmaschine, Geschirrspüler). Deren Nutzung ist schlecht planbar. Da sie aber immer ein bestimmtes Programm abarbeiten, haben sie je nach eingestelltem Programm immer wieder die gleiche Lastkurve, meist für mehr als eine Stunde.
Es sollen mehrere Geräte verwaltet werden können.

# Ziel
Ziel ist es, eine Prognose-Lösung zu entwickeln mit folgenden Eigenschaften. Die Lösung wird als native HA-Integration (Custom Component) umgesetzt; ein HA-Add-on (in der HA-UI unter "Apps" geführt) ist ausgeschlossen, u. a. weil es nur auf HA OS/Supervised läuft, nicht auf Core/Container-Installationen.

## Analyse von Lastprofilen über Muster in der Lastverteilung
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

## Erkennen von Lastprofilen während der Nutzung
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

## Benachrichtigung
- Die Benachrichtigung selbst ist **nicht** Teil des Kernprogramms, sondern ein optionales Feature, das über eine HA-Automation ausgelöst wird, die vom Nutzer auf Basis der bereitgestellten Sensoren erstellt wird
- Das Programm stellt dafür pro Gerät folgende Sensoren bereit:
  - Aktueller Gerätestatus: `sleeping` / `running`
  - Wahrscheinlichster Programmname
- Die eigentliche Benachrichtigung erfolgt über den HA `notify`-Service; jedes konfigurierte Gerät kann eine eigene Notification-Konfiguration erhalten (Text, Ziel)

## Ermitteln einer wahrscheinlichen nächsten Nutzung für die langfristige Forecast-Planung von HAEO
- Es geht hierbei nicht um klassische Anwesenheitserkennung ("ist jemand da"), sondern um das Erkennen wiederkehrender Alltagssituationen (Wochentag, Wochenende, Feiertag, Ferien, Urlaub), die mit der Gerätenutzung korrelieren
- Diese Situationen sollen aus verschiedenen, vom Nutzer frei wählbaren Sensoren des Hauses abgeleitet werden können, z. B.:
  - Türsensoren
  - Allgemeiner Hausstromverbrauch
  - Zeitpunkt der letzten Meldung des E-Autos
- Dieser Bereich ist bewusst vage/offen gehalten, da er flexibel vom Nutzer definiert und angepasst werden können soll. Im Vordergrund steht nicht der aktuelle Zustand dieser Sensoren, sondern die Korrelation zwischen diesen Situationen und der tatsächlichen Gerätenutzung

## Schnittstelle zu HAEO (Home Assistant Energy Optimizer)
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

## Dashboard
- Umsetzung möglichst nah am HA-Standard: Standard-Lovelace-Cards und von der Integration bereitgestellte Entities/Attribute (keine Custom Card, keine zusätzlichen Systemanforderungen/Abhängigkeiten)
- Für den Betrieb: aktuelles Profil sichtbar
  - Name
  - Voraussichtliches Ende
  - Verbrauch aktuell / gesamt
  - ggf. ein Diagramm, das die aktuelle Lastkurve über die geplante legt (über Standard-History/Statistics-Graph-Card auf Basis der bereitgestellten Entities)
- Für die Pflege (umgesetzt über HA-Standardmechanismen wie Options Flow / Services + Standard-Entities, keine Custom Card)
  - Mehrere Profile werden als Liste je Gerät verwaltet
  - Anzeige der gefundenen Profile, inkl. Visualisierung des jeweiligen Profilverlaufs (Lastkurve)
  - Benennen von Profilen
  - Zusammenführen ("Mergen") von zwei oder mehr Profilen zu einem – der Name des resultierenden Profils wird beim Mergen abgefragt
  - Suche nach neuen Profilen

# Technische Anforderungen
- Alle Langzeitdaten sollen so gespeichert werden, dass sie
  - mit einem Mal gelöscht werden können
  - im HA-Backup enthalten sind und daraus wiederhergestellt werden können
  - zwischen verschiedenen Versionen migrierbar sind – daher speichert jeder Datensatz eine Versionsnummer des Schnittstellenformats
- Die konkrete Speichertechnologie (z. B. eigene SQLite-DB, `.storage`-JSON, Graphdatenbank) ist bewusst nicht vorgegeben, sondern soll passend zum Problem (Ähnlichkeitssuche über Zeitreihen/Muster) gewählt werden
- Unterstützte Sprachen für Config-Flow-/Dashboard-UI: Deutsch und Englisch
- Skalierung: bis zu ca. 10 Geräte gleichzeitig verwaltbar
- Architektur: native HA-Integration (Custom Component), kein HA-Add-on – u. a. damit die Lösung auf allen Installationsarten (Core/Container, nicht nur OS/Supervised) läuft, nativen Zugriff auf Recorder/History und die Entity-Registry hat und über HACS verteilt werden kann

# Offene Punkte
- **Mustererkennungs-Algorithmus**: Festgelegt: Dynamic Time Warping (DTW) auf Basis der Profil-Bänder (siehe Abschnitt "Analyse von Lastprofilen"). Die rohen States werden auf ein 5–10-s-Raster mit `min`/`mean`/`max` je Bucket heruntergerechnet; DTW richtet den (ggf. unvollständigen) Live-Verlauf anhand der `mean`-Reihe zeitversatz-tolerant am Profil aus; als lokale Kostenfunktion wird statt der üblichen Euklidischen Distanz eine bandbewusste Funktion verwendet (Kosten 0 innerhalb `[min, max]`, sonst proportional zum Abstand zum Band). Offen ist noch die konkrete Parametrisierung (genaue Bucket-Größe, exakte Formel zur Umrechnung der DTW-Gesamtkosten in den %-Konfidenzwert, Begrenzung der DTW-Bandbreite/Fensterung für die Performance) – das ist Implementierungsdetail und muss die Spec nicht weiter vorgeben.
- **Mehrere Profile pro Gerät / Mergen**: Geklärt (siehe Dashboard/Pflege sowie "Analyse von Lastprofilen"): Profile werden als Liste je Gerät mit Visualisierung verwaltet; das Mergen zweier Profile ist eine manuelle Korrektur der automatischen Erkennung, vergrößert das Band (`min`/`max` je Zeit-Bucket) entsprechend der Streuung der zusammengeführten Läufe und fragt den Namen des resultierenden Profils beim Nutzer ab.
- **Abbruch/Pause eines Laufs**: Geklärt (siehe "Erkennen von Lastprofilen während der Nutzung" bzw. "Analyse von Lastprofilen"): geplante Pausen sind Teil des Profils; die Zeitschwelle, ab der eine Pause als Abbruch gilt, ist nicht fix, sondern wird aus der längsten bekannten Pausendauer der infrage kommenden Profile abgeleitet, um zu verhindern, dass profilinterne Pausen fälschlich als Abbruch erkannt und zusammengehörige Läufe in mehrere Profile aufgesplittet werden.
