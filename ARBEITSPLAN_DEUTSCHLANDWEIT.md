# Arbeitsplan Phase 2: Deutschlandweit mit OSM und ALKIS

Stand: 18.11.2026 – **E5–E15 von Person Windows bestätigt (G5), ergänzt um
E16–E19. Person Mac stimmt E16, E17 und E19 zu; E18 auf Wunsch der Person
Mac geändert (jedes Mal fragen, letzter Ordner als Vorschlag).**
Neu als Entwurf von Person Mac: soziale Daten und Erreichbarkeit (E22–E27),
Beschluss in Aufgabe 5 (G10).

**Stand Ende 18.11.2026:** Erledigtes steht in §5, alle offenen Aufgaben
stehen in §6 **in der Reihenfolge, in der sie erledigt werden**. Auf `main`
sind alle 234 Tests grün.

**Stand 19.11.2026 (Feature Freeze):** Nach dem Live-Test hat Person Mac
E29–E34 vorgeschlagen (Attributtabelle, Dubletten, PDF, Kartenstile,
Erreichbarkeit). Die Aufgaben bis zum Feature Freeze stehen in §6 als
**Etappe F – heute, vor allem anderen**. Auf `main` sind 278 Tests grün.

**Stand 19.11.2026 nachmittags (G12):** Person Mac hat ihren Teil der Etappe F
fertig (F0, F1, F3 gemergt; F6, F7 sowie E35 Niedersachsen-Cache und M10b
ALKIS-Aufträge im PR „Pipeline: Ziel-Punkte, Niedersachsen-Cache,
Erreichbarkeit, ALKIS-Aufträge“). Person Windows: F5 gemergt (#45), F2 (W14)
auf dem Branch `feature/ui-schritt5-spalten`; offen F4, F8 und die neuen
Aufgaben W11b (Cache in QGIS) und W10 Teil 2 (ALKIS-Download in QGIS).
Neue Entscheidungen: E35 (Cache), E11 geändert (Bundesland von Hand).

Der erste Arbeitsplan (`ARBEITSPLAN.md`) ist im Wesentlichen erledigt: Das
Plugin läuft in QGIS von Schritt 1 bis 9 mit einer lokalen GeoPackage-Datei.
Dieser Plan beschreibt den nächsten Ausbau. Die Regeln aus `CLAUDE.md` und
`ARBEITSPLAN.md` §2 (täglicher Ablauf, kleine Schritte, Push und PR nur nach
Rückfrage, Dateibesitz) gelten unverändert weiter.

- **Person Mac** = Datenpipeline (QGIS-frei, macOS)
- **Person Windows** = Benutzerführung und Integration in QGIS (Windows)
- **Gemeinsam** = beide zusammen, eigener PR für gemeinsame Dateien

> **Für die Claude-Code-Session der jeweiligen Person:** Lies zuerst
> `CLAUDE.md`, dann diesen Plan. Arbeite nur an den Schritten deiner Person und
> nur an den dort genannten Dateien. Immer nur **einen** Schritt, Ergebnis
> zeigen, vor Commit, Push und Pull Request fragen. Braucht ein Schritt eine
> Datei der anderen Person oder eine gemeinsame Datei: anhalten und nachfragen.

---

## 1. Ziel

Das Plugin soll für **jedes Untersuchungsgebiet in Deutschland** funktionieren
und die Daten **selbst holen**:

- **OSM** (OpenStreetMap) für ganz Deutschland,
- **ALKIS** (amtliches Liegenschaftskataster) automatisch von den Diensten der
  Bundesländer.

Beide Quellen werden wie bisher zugeschnitten, geprüft und den Kategorien
Gebäude, Straßen, Grünflächen und Nutzungsflächen zugeordnet. Zeigen beide
Quellen dasselbe Objekt, wählt die Nutzerin **je Kategorie**, welche Quelle
gilt.

## 2. Getroffene Entscheidungen (18.11.2026)

| Nr. | Entscheidung |
| --- | --- |
| E5 | Automatischer Download wird **jetzt** Teil des Plugins. Die bisherige Regel „Download erst nach der MVP-Abnahme“ in `CLAUDE.md` und `PLAN.md` wird geändert (→ G5). Die offenen MVP-Reste (M6, W8 Teil 2) werden im Rahmen dieses Ausbaus erledigt. |
| E6 | ALKIS wird **nur automatisch** über Dienste der Bundesländer geholt. Bietet ein Land keinen frei nutzbaren Dienst an, gibt es dort kein ALKIS; das Plugin sagt das deutlich und arbeitet mit OSM weiter. |
| E7 | Zeigen ALKIS und OSM dasselbe Objekt, wählt die Nutzerin **je Kategorie** (Gebäude, Straßen, Grünflächen, Nutzungsflächen), welche Quelle gilt. |
| E8 | Zeilen mit gleicher Objekt-ID und gleicher Form, die sich **nur in der Adresse** unterscheiden (z. B. Eckhaus mit zwei Hausnummern), sind ein Objekt und werden automatisch zusammengefasst; alle Adressen bleiben erhalten. Alles andere bleibt eine Entscheidung der Nutzerin. *(umgesetzt in M8)* |
| E9 | Echte Dubletten gibt es nur **zwischen Quellen**. Sie werden über „liegt fast deckungsgleich übereinander“ erkannt, nicht über identische Geometrie. |
| E10 | **Eigene Dateien bleiben möglich:** Neben OSM und ALKIS kann man zusätzlich eigene GeoPackages laden (z. B. Kartierungen). ALKIS selbst kommt trotzdem nur automatisch (E6). |
| E11 | ~~**Bundesland wird automatisch erkannt und ist änderbar**~~ → **geändert am 19.11.2026 (M10b): Die Nutzerin wählt das Bundesland von Hand** aus einer Liste in Schritt 3 (`alkis_states()`, mit Stand je Land: verfügbar / kommt später / gesperrt). Keine Ländergrenzen-Datei im Plugin. Die Lizenz der BKG-Grenzen (VG2500) ist trotzdem geklärt: dl-de/by-2.0, kostenfrei, Quellenvermerk und Veränderungshinweis Pflicht – falls wir den Vorschlag später doch wollen. |
| E12 | **Abgleich ALKIS ↔ OSM:** Mittelpunkt des einen liegt im anderen **und** die Flächen weichen höchstens **20 %** ab → wahrscheinlich gleich. Liegt der Mittelpunkt drin, aber die Abweichung ist größer → unsicher, wird zur Entscheidung angezeigt. Der Wert steht in einer Einstellungsdatei und ist änderbar. |
| E13 | **Gebietsgröße: Warnung ab 25 km², Grenze 50 km²** (Gebiet inklusive Puffer, gemessen am umgebenden Rechteck, das heruntergeladen wird). Über 25 km² eine Warnung („kann lange dauern, Dateien werden groß“) mit „Trotzdem fortfahren?“; über 50 km² eine klare Meldung, und OSM/ALKIS werden nicht geladen (eigene Dateien bleiben möglich). *(geändert am 18.11.2026 auf Vorschlag von Person Windows nach dem Live-Test, PR #33; vorher harte Grenze 25 km²)* |
| E14 | **Speicherort:** Vor jedem Download fragt das Plugin, in welchen Ordner die Daten sollen. Dateiname enthält Quelle und Datum. |
| E15 | **Ohne Internet / Dienst antwortet nicht:** nur eine verständliche Meldung, der Download wird abgebrochen. Keine automatische Wiederverwendung alter Downloads. Ein früherer Download kann aber von Hand als „Eigene Datei“ geladen werden. |

Ergänzungen von Person Windows in G5:

| Nr. | Entscheidung |
| --- | --- |
| E16 | **Eigener ALKIS-Export als Datei (ergänzt E6, E10):** Unter „Eigene Datei“ darf auch ein eigener ALKIS-Export geladen werden (z. B. `lkr_03403_Stadt_Oldenburg_kon.gpkg`). Das Plugin erkennt ihn am Profil und behandelt ihn als Quelle `"ALKIS"`. So bleiben Phase-1-Ablauf und Tests mit der lokalen Datei erhalten. |
| E17 | **Gebietsgröße schon in Schritt 2 (ergänzt E13):** Schritt 2 zeigt beim Wählen oder Zeichnen die Größe von Gebiet + Puffer (umgebendes Rechteck), z. B. „6,1 km² von höchstens 50 km²“. Über der Grenze erscheint dort schon ein Hinweis; die verbindliche Prüfung bleibt in S9. |
| E18 | **Zielordner jedes Mal fragen, mit Vorschlag (ergänzt E14):** Vor jedem Download fragt das Plugin nach dem Ordner (E14 bleibt). Im Auswahlfenster ist der zuletzt gewählte Ordner schon vorausgewählt; beim allerersten Download der Ordner des QGIS-Projekts. Die Nutzerin bestätigt oder wählt einen anderen. Dateiname weiter mit Quelle und Datum. *(geändert von Person Mac nach dem G5-Review)* |
| E19 | **Vorgeschlagener Vorrang (ergänzt E7):** Schritt 6 schlägt je Kategorie eine Quelle vor – Gebäude und Nutzungsflächen: ALKIS; Straßen und Grünflächen: OSM. Die Nutzerin bestätigt oder ändert; erst dann gilt die Auswahl. Der Vorschlag steht in einer Einstellungsdatei und ist änderbar. |

Vorschläge von Person Mac nach dem QGIS-Test (18.11.2026, in G9 gemeinsam zu
bestätigen):

| Nr. | Vorschlag |
| --- | --- |
| E20 | **Zielschema um Objekt-ID und Adresse erweitern:** Die Ergebnis-Layer bekommen zwei neue Felder: `object_id` (Original-ID der Quelle, z. B. ALKIS `objid`, später OSM `osm_id`) und `address` (Straße und Hausnummer, je Adresse zusammengesetzt, mehrere Adressen getrennt mit „; “, z. B. „Hauptstraße 2; Nebenweg 1“). Bisher kennen die Ergebnis-Layer nur die 8 Felder aus `PLAN.md` §3.4; IDs, Straßen und Hausnummern sind dort nicht zu finden, obwohl die Pipeline sie im Hintergrund behält. |
| E21 | **Schritt 5 verständlich machen:** Schritt 5 soll klar sagen, *was* die Nutzerin entscheidet und *warum*. Heute sieht man nur einzelne vorgeschlagene Spalten, kann nur eines der 8 Zielfelder wählen und versteht Begriffe wie „Nutzungsdetail“ oder „Status“ nicht. Wie Schritt 5 künftig aussieht, legen wir in G9 gemeinsam fest. |

Vorschläge von Person Mac: soziale Daten und Erreichbarkeit (18.11.2026, in
G10 gemeinsam zu bestätigen). Hintergrund: Für eine Urban-Design-Analyse
reichen Gebäude und Flächen nicht; man braucht auch, wo Ärzte, Schulen oder
Haltestellen sind, wie oft der Bus fährt und wie gut man sie erreicht.

| Nr. | Vorschlag |
| --- | --- |
| E22 | **Soziale Infrastruktur aus OSM-Punkten:** Neue Kategorien **Gesundheit** (z. B. Arztpraxis, Apotheke), **Bildung und Betreuung** (Schule, Kita), **Nahversorgung** (Supermarkt, Bäckerei), **Freizeit** (Spielplatz, Sportplatz, Bibliothek) und **ÖPNV-Haltestellen**. Sie kommen ohne eigenen Download aus der OSM-Abfrage (M10), die dafür um diese Punkte erweitert wird. Die Zuordnung steht in `mapping_rules.json`. |
| E23 | **Zusatzfelder je Kategorie:** Die 11 Zielfelder bleiben die gemeinsame Basis für alle Kategorien. Felder, die nur für eine Kategorie Sinn ergeben, kommen **nur dort** dazu (z. B. „Abfahrten pro Stunde“ nur bei Haltestellen, „Weg zur nächsten Haltestelle“ nur bei Gebäuden). Das braucht eine Änderung am Vertrag (→ G10). |
| E24 | **Takt aus Fahrplandaten (GTFS):** Wie oft ein Bus fährt, steht nicht in OSM. Dafür wird der offene, deutschlandweite GTFS-Fahrplan (DELFI) als neue Quelle geladen. Kennzahl je Haltestelle: **Abfahrten pro Stunde, werktags 6–20 Uhr**. Tag und Zeitfenster stehen in einer Einstellungsdatei und sind änderbar. Quelle, Lizenz und Größe klärt M18. |
| E25 | **Ausnahme von E15 für große Deutschland-Dateien:** Dateien, die es nur für ganz Deutschland gibt (GTFS, evtl. Zensus), sind zu groß, um sie bei jedem Lauf neu zu laden. Sie werden **einmal** in den gewählten Ordner geladen. Beim nächsten Lauf zeigt das Plugin das Datum der vorhandenen Datei und fragt: „Diese Datei verwenden oder neu laden?“ Ohne Bestätigung wird nichts wiederverwendet (keine stille Wiederverwendung). |
| E26 | **Erreichbarkeit in drei Stufen**, in dieser Reihenfolge: **1. Luftlinie** – Abstand jedes Gebäudes zum nächsten Ziel (z. B. Haltestelle) und ob es im 300-m- oder 500-m-Radius liegt. **2. Fußweg** – echter Weg über das OSM-Wegenetz, dazu Einzugsbereiche als Flächen („in 5 Minuten zu Fuß“). **3. ÖV-Güteklassen** – Abstand und Takt zusammen, Klassen A (sehr gut) bis F (schlecht), nach der bekannten Methode aus der Raumplanung. Die Rechnung ist für andere Ziele übertragbar (nächster Arzt, nächste Schule, nächster Supermarkt). Radien, Gehgeschwindigkeit und Klassengrenzen stehen in einer Einstellungsdatei. |
| E27 | **Einwohnerdaten aus dem Zensus 2022** (100-m-Raster) als spätere Quelle, z. B. für „Wie viele Menschen wohnen im Einzugsbereich einer Haltestelle?“. Erst nach der Recherche in M18 entscheiden, ob und wie. |

Vorschlag von Person Mac nach der Recherche M9 (18.11.2026, gemeinsam zu
bestätigen):

| Nr. | Vorschlag |
| --- | --- |
| E28 | **Lizenzen und Quellenvermerke korrekt angeben.** Alle Quellen sind frei nutzbar, verlangen aber (bis auf dl-de/zero) eine Namensnennung: **dl-de/by-2.0** (BW, BB, HH, RP, SL, SN, ST, BKG-Ländergrenzen) und **CC BY 4.0** (NI, SH, MV, TH, HB, BY) verlangen Quellenvermerk, Lizenzname mit Link und einen **Hinweis, dass die Daten verändert wurden** (Zuschnitt, Zusammenführung); **dl-de/zero-2.0** (NW, HE, BE) verlangt nichts, wir nennen die Quelle trotzdem. **OSM (ODbL):** „© OpenStreetMap-Mitwirkende“; Karten und PDFs brauchen nur diesen Vermerk, ein **öffentlich weitergegebenes GeoPackage** mit OSM-Objekten steht für den OSM-Teil unter ODbL (Share-Alike). Umsetzung: (1) Lizenz und Quellenvermerk je Quelle stehen in `sources_catalog.json`; (2) das Feld „Datenquelle“ jedes Objekts wird daraus vorausgefüllt; (3) beim Download werden Quelle, Datum, Lizenz und Adresse als Metadaten gespeichert, Rohdaten bleiben unverändert; (4) GeoPackage und PDF enthalten einen Block **„Datenquellen und Lizenzen“** mit allen tatsächlich genutzten Quellen, Jahr, Lizenz mit Link, dem Satz „Daten zugeschnitten und zusammengeführt (verändert)“ und – wenn OSM dabei ist – dem ODbL-Hinweis; (5) nie abgefragt werden Eigentümerdaten, Flurstücke in Bayern (nicht frei) und Sachsen-Anhalt, solange die Lizenz nicht bestätigt ist; (6) bei eigenen Dateien bleibt die Nutzerin verantwortlich, das Plugin fragt die Datenquelle ab (Schritt 8); (7) heruntergeladene Daten werden nie committed. |

Vorschläge von Person Mac nach dem Live-Test (19.11.2026, im PR zu diesem
Plan von Person Windows zu bestätigen). Sie gelten für den Feature Freeze
(Etappe F in §6):

| Nr. | Vorschlag |
| --- | --- |
| E29 | **Attributtabelle: Kernfelder plus Originalspalten.** Bisher schreiben die Ergebnis-Layer nur die 11 festen Zielfelder; alle anderen Spalten gehen verloren. Künftig gibt es nur noch wenige **Kernfelder**, die Karte und Legende brauchen: `object_id`, `address`, `object_type`, `category`, `source`, `source_name`. Dazu kommen **alle bekannten Originalspalten mit lesbarem Namen** (z. B. `hnr` → „Hausnummer“, `anzahlgs` → „Geschosszahl“). `object_detail`, `status`, `area_m2`, `year` und `floors` sind keine Pflichtfelder mehr, sondern normale Spalten, wenn die Quelle sie hat. Ersetzt in E23 „die 11 Zielfelder bleiben die Basis“; `PLAN.md` §3.4 wird in G11 angepasst. |
| E30 | **Nur bekannte Spalten werden geladen, der Rest ist zuschaltbar.** Für jede Quelle (ALKIS-Export, ALKIS vereinfacht, OSM) gibt es eine **Namensliste** in `mapping_rules.json`. Spalten aus der Liste sind in Schritt 5 angehakt und lesbar benannt; den Namen kann man ändern. Unbekannte Spalten stehen eingeklappt unter **„Nicht geladen (nicht lesbar)“**, können aber angehakt werden. Ein Info-Hinweis nennt sie („7 Spalten nicht geladen, weil das Plugin sie nicht lesen kann: …“). **OSM:** bekannte Tags aus `other_tags` (z. B. Name, Geschosse, Höhe, Dachform, Baujahr, Adresse) werden eigene Spalten; unbekannte Tags werden wie unbekannte Spalten behandelt. |
| E31 | **Dubletten: weiter fragen, aber mit Beispiel.** Objekte, die in einer Datei genau übereinanderliegen und sich in einzelnen Spalten unterscheiden, bleiben eine Entscheidung (CLAUDE.md). Der Hinweis nennt die Spalten mit **lesbarem Namen** und zeigt ein **echtes Beispiel** mit beiden Werten („Stelle 1: Nutzung = Wohnen / Gewerbe“); die Oberfläche kann auf die Stelle zoomen. Punkte, Linien und Flächen sind nie Dubletten voneinander (es wird nur innerhalb eines Layers und bei gleicher Geometrie verglichen). |
| E32 | **PDF-Aufbau.** Immer dabei: Karte, Legende, Block „Datenquellen und Lizenzen“ (E28), Datum. **Wählbar:** Maßstabsleiste, Nordpfeil, Titel und Untertitel (selbst eintippen), Namen/Gruppe/Hochschule/Kurs, Umriss des Untersuchungsgebiets mit Puffer, Übersichtskarte zur Lage. **Formate:** A4, A3, A2, A1, A0, jeweils hoch und quer. **Keine Online-Hintergrundkarte;** stattdessen kann ein **Schwarzplan aus den geladenen Gebäuden** als Hintergrund zugeschaltet werden. Nicht im PDF: Kennzahlen-Tabelle, Prüfprotokoll. |
| E33 | **Kartenstile für die Analysekarte:** **Schwarzplan** (Gebäude schwarz), **Nutzungskarte farbig** (je Kategorie eine Planfarbe), **Graustufen** (für Druck). **Pixel** passend zum Plugin-Stil nur, wenn es wenig Mehraufwand ist. Der Stil gilt für die Ergebnis-Layer in QGIS und für das PDF. |
| E34 | **Erreichbarkeit mit wählbaren Startpunkten** (präzisiert E22 und E26): Startpunkte sind nicht nur Haltestellen. Wählbar sind **Kategorie und Unterart**: Gesundheit (Krankenhaus, Arztpraxis, Apotheke), Nahversorgung (Supermarkt, Bäckerei, Drogerie), Bildung und Betreuung (Schule, Kita, Hochschule), Freizeit und Grün (Spielplatz, Sportplatz, Park, Bibliothek), ÖPNV-Haltestellen. **Ergebnis wählbar:** Radien (300 m / 500 m) um die Startpunkte und/oder Gebäude eingefärbt nach Abstand zum nächsten Ziel. Bis zum Feature Freeze nur **Stufe 1 (Luftlinie)**; Fußweg und ÖV-Güteklassen danach. |
| E35 | **Niedersachsen-Cache als Notlösung (ergänzt E15):** Scheitert Overpass nach allen Wiederholungen, holt das Plugin OSM aus dem Niedersachsen-Cache des Teams (https://github.com/Jade-HS-Vibecoding-WPK/niedersachsen-cache, wöchentlich aus dem Geofabrik-Auszug gebaut) – nur, wenn das ganze Download-Rechteck im Cache liegt. Der Cache ist eine eigene, frische Quelle, kein alter Download (E15 bleibt). Ein Info-Hinweis sagt es immer, mit Datenstand und den Merkmalen, die im Cache fehlen (Hecken/Zäune/Mauern, Gebäudeteile, Strom). Lizenz ODbL wie OSM. Umsetzung: `osm_cache.py` (Mac), W11b (Windows). *(Wunsch Person Mac, 19.11.2026)* |

Weiter gilt unverändert:

- `data_pipeline.py` bleibt QGIS-frei und ohne Zusatzpakete (kein shapely,
  pyproj, requests).
- **Keine Umprojektion in der Pipeline.** Daten, die nicht im Projekt-CRS
  vorliegen (OSM kommt in EPSG:4326), werden in QGIS umprojiziert, bevor die
  Pipeline sie liest.
- Rohdaten nie überschreiben. Heruntergeladene Daten werden unverändert mit
  Datum und Quelle gespeichert; bereinigte Daten sind neue Layer.
- Heruntergeladene Daten (vor allem ALKIS) werden **nie committed**. Sie
  landen im Projektordner der Nutzerin oder im gitignorierten `daten/`.
- Keine stillen Fallbacks: Ist ein Dienst nicht erreichbar oder liefert er
  nichts, wird das als `ValidationIssue` angezeigt.

## 3. So hängt alles zusammen

```text
Schritt 2 Gebiet ─▶ [S9] Quellen bestimmen ─▶ [S10] Herunterladen + umprojizieren
   (Windows)          (Mac: welches Land,        (Windows: QGIS lädt, schreibt
                       welche Dienste/URLs)        je Quelle ein GeoPackage)
                                                          │
                                                          ▼
                       [S11] Mehrere Quellen importieren (Mac: import_file je
                             Quelle, ein gemeinsames PipelineResult)
                                                          │
                                                          ▼
                       [S12] Quellen abgleichen (Mac: ALKIS ↔ OSM vergleichen)
                                                          │
                                                          ▼
Schritt 6: Vorrang je Kategorie wählen (Windows) ─▶ Schritt 7–9 wie bisher
```

## 4. Neue Schnittstellen

### S9 – Quellen für ein Gebiet bestimmen *(Mac)*

- Datei: `urban_analysis/sources.py` (neu) und
  `urban_analysis/sources_catalog.json` (neu, wie `mapping_rules.json` ohne
  Code änderbar).
- Eingabe: Untersuchungsgebiet (WKT, Projekt-CRS), Puffer, das
  **Download-Rechteck (Gebiet + Puffer) in EPSG:4326**, das QGIS vorher
  umrechnet (so bleibt die Pipeline ohne Umprojektion; vereinbart in PR #34),
  optional ein von der Nutzerin geändertes Bundesland.
- Umgesetzt (M10a): `plan_osm_download(study_area_wkt, buffer_meters,
  lonlat_box)` liefert einen `SourcePlan` mit `requests`
  (`DownloadRequest`: URL, Overpass-Abfrage, Lieferungs-KBS, Dateinamen für
  Rohdatei und GeoPackage, Lizenz mit Link, Quellenvermerk, Zeitlimit),
  `issues` und `area_km2`.
- `suggest_state(...)` schlägt das Bundesland vor (E11), aus vereinfachten
  Ländergrenzen, die als Datei im Plugin liegen.
- Ausgabe: Liste von Download-Aufträgen, je Quelle: Adresse (URL) oder
  Abfragetext, Format, CRS der Lieferung, Lizenz, Quellenvermerk (z. B.
  „© OpenStreetMap-Mitwirkende, ODbL“).
- Für Bundesländer ohne frei nutzbaren ALKIS-Dienst: kein Auftrag, sondern ein
  Hinweis.
- Ist das Rechteck aus Gebiet + Puffer größer als 50 km² (E13): keine
  Aufträge, sondern eine Fehlermeldung mit der tatsächlichen Größe; über
  25 km² ein Warnhinweis.

### S10 – Herunterladen und umprojizieren *(Windows)*

- Läuft in QGIS als `QgsTask` (blockiert die Oberfläche nicht) und nutzt das
  Netzwerk von QGIS (damit Proxy-Einstellungen der Hochschule greifen).
- Fragt vor jedem Download nach dem Zielordner (E14).
- Schreibt je Quelle ein GeoPackage **im Projekt-CRS**, Dateiname mit Quelle
  und Datum (z. B. `osm_2026-11-18.gpkg`).
- Fehler (kein Internet, Dienst antwortet nicht) werden als verständliche
  Meldung angezeigt, der Download bricht ab (E15).
- **Overpass ist oft überlastet** (Test am 18.11.: erst HTTP 502 „alle Plätze
  belegt“, dann 504, nach 60 s erfolgreich). Deshalb bei 429/502/504 höchstens
  2–3 Wiederholungen mit wachsender Pause (z. B. 30 s, 60 s) und sichtbarem
  Hinweis („Server ausgelastet, neuer Versuch in …“), danach verständlicher
  Abbruch – keine endlose Schleife.
- OSM: Die Abfrage (POST-Feld `data`) liefert eine `.osm`-Datei in EPSG:4326;
  sie wird unverändert als Rohdatei gespeichert, dann mit GDAL/QGIS gelesen
  (Layer `points`, `lines`, `multipolygons`) und ins Projekt-CRS umgerechnet.
- ALKIS „vereinfacht“ (11 Länder): Die WFS-Layer `ave:GebaeudeBauwerk`,
  `ave:Nutzung`, `ave:Flurstueck` werden **ohne Präfix** als
  `GebaeudeBauwerk`, `Nutzung`, `Flurstueck` ins GeoPackage geschrieben,
  Spaltennamen wie geliefert (`oid`, `funktion`, `nutzart`, `bez`,
  `lagebeztxt`, `anzahlgs` …) – so erkennt das Profil aus M12 die Daten.

### S11 – Mehrere Quellen in einem Lauf *(Mac, Vertrag gemeinsam)*

- `import_sources([...])` ruft `import_file` je Quelle auf und liefert **ein**
  `PipelineResult`.
- Jeder Datensatz weiß, aus welcher Quelle er stammt (`source_kind`:
  `"ALKIS"`, `"OSM"` oder `"Eigene Datei"`, E10). Das braucht ein neues Feld in `contracts.py`
  → gemeinsamer PR (G6).

### S12 – Quellen abgleichen *(Mac, Oberfläche Windows)*

- Zwei Objekte aus verschiedenen Quellen gelten als **wahrscheinlich gleich**,
  wenn der Mittelpunkt des einen im anderen liegt und die Flächen höchstens
  20 % abweichen (E12). Reines Python, keine Zusatzpakete.
- Ergebnis: Gruppen mit Hinweis `cross-source-duplicate` je Kategorie;
  Mittelpunkt drin, aber Abweichung über 20 % → unsichere Gruppe, die
  bestätigt werden muss.
- `apply_source_priority(records, {"Gebäude": "ALKIS", "Grünflächen": "OSM", …})`
  behält je Gruppe nur das Objekt der gewählten Quelle. Objekte ohne Partner
  in der anderen Quelle bleiben immer erhalten.

### S13 – Kurzer Hinweis mit „Mehr erfahren“ *(gemeinsam)*

- `ValidationIssue` bekommt ein optionales Feld `details` (längere
  Erklärung). `message` bleibt kurz (ein bis zwei Sätze).
- Die Oberfläche zeigt `message` und bei Bedarf einen Link „Mehr erfahren“,
  der `details` aufklappt.
- Änderung an `contracts.py` → gemeinsamer PR (G6).

### S14 – Takt aus GTFS *(Download Windows, Rechnung Mac)*

- GTFS ist eine ZIP-Datei mit Tabellen (CSV): Haltestellen (`stops.txt`) mit
  Längen-/Breitengrad, Abfahrten (`stop_times.txt`), Fahrtage
  (`calendar.txt`).
- **Windows** lädt die ZIP-Datei (E25) und schreibt die Haltestellen im
  Gebiet als GeoPackage **im Projekt-CRS** (Umprojektion in QGIS, wie bei
  OSM).
- **Mac:** `departures_per_hour(gtfs_zip, stop_ids, settings)` in
  `urban_analysis/gtfs.py` (neu) zählt die Abfahrten je Haltestelle im
  Zeitfenster aus E24. Reines Python (`zipfile`, `csv`), liest die große
  Abfahrten-Tabelle Zeile für Zeile und behält nur die Haltestellen im
  Gebiet.

### S15 – Erreichbarkeit *(Mac, Oberfläche Windows)*

- Eingabe: Ausgangsobjekte (z. B. Gebäude), Ziele (z. B. Haltestellen) und
  Einstellungen (Radien, Gehgeschwindigkeit, Klassengrenzen) aus E26.
- Stufe 1 (Luftlinie) und Stufe 3 (Güteklassen) in reinem Python in
  `urban_analysis/accessibility.py` (neu). Abstände in Metern; dafür muss das
  Projekt-CRS metrisch sein (z. B. EPSG:25832), sonst sichtbarer Fehler.
- Stufe 2 (Fußweg): **wo gerechnet wird, ist offen** (→ §7) – entweder mit
  den Netzwerk-Werkzeugen von QGIS (Windows) oder mit einer eigenen
  Wegsuche über die OSM-Linien (Mac).
- Ausgabe: Zusatzfelder an den Ausgangsobjekten (E23), Stufe 2 außerdem
  Einzugsbereiche als neue Flächen-Layer.

---

## 5. Erledigt

| Schritt | Wer | Ergebnis | PR |
| --- | --- | --- | --- |
| G5 Regeln anpassen | gemeinsam | `CLAUDE.md` und `PLAN.md` erlauben den Download (E5–E19) | #23, #24 |
| G9 Zielschema und Schritt 5 | gemeinsam | 11 Felder (neu `object_id`, `address`, `floors`), Schritt 5 mit Ausklappmenüs und ⓘ-Symbol (`PLAN.md` §3.4) | #27 |
| M8 Gebäude mit mehreren Adressen | Mac | Eckhaus = ein Gebäude mit allen Adressen; in QGIS mit dem ALKIS-Export geprüft | #21 |
| M16 Objekt-ID, Adresse, Geschosszahl | Mac | neue Zielfelder, Adresse je Zeile; in QGIS geprüft | #28 |
| M15 Teil 1: Zielfeld-Texte | Mac | deutscher Name und ein Erklärungssatz je Zielfeld (`target_field_explanation()`) | #28 |
| M11 OSM-Profil | Mac | OSM-Flächen und -Linien in Kategorien, lesbare Objektart; mit echten Daten (Donnerschwee) geprüft: „Sonstige“ Flächen 165 → 25, Linien 1 380 → 171 | #29, #31 |
| W8b Ausgabe GeoPackage/PDF | Windows | Speichern mit Vorschlag, Datenquelle Pflicht, Eingabedatei geschützt, 11 Felder, Geschosszahl als Ganzzahl | #26 |
| M9 Recherche ALKIS-Dienste | Mac | alle 16 Länder offen; 11 im einheitlichen Format „ALKIS vereinfacht“; Katalog `sources_catalog.json`, Details in `STATUS_DATENPIPELINE.md`; daraus E28 (Lizenzen) | dieser PR |
| Planentwurf soziale Daten | Mac | E22–E27 als Entwurf im Plan (Beschluss in Aufgabe 5) | #30 |
| M12 Teil 1 „ALKIS vereinfacht“ | Mac | Profil für die Dienste von 11 Ländern | #38 |
| W11 Herunterladen in QGIS | Windows | OSM-Download mit Ordnerwahl, Wiederholungen, Rohdatei, GeoPackage im Projekt-KBS; lesbare Namen „Straßen (Linien)/(Flächen)“ | #40 |
| W13 Teil 1 „Mehr erfahren“ in Schritt 4 | Windows | Kurzfassung je Hinweis, Rest aufklappbar; Mausrad verstellt keine Auswahllisten | #39 |
| G6 Vorschlag Schritt 4–6 | Windows | Vertragsfelder für verständliche Schritte (Umsetzung in F0) | #41 |
| Plan Feature Freeze | Mac | E29–E34, Etappe F | #42 |
| F0 G11 Vertrag | gemeinsam | Kernfelder, `ColumnInfo`, `ColumnDecision`, Dubletten-Erklärung, `details`/`action`/`layer_id`, `source_kind` | #43 |
| F1 M23 Spalten lesen | Mac | Namensliste, bekannte Spalten mit lesbarem Namen in `extra_attributes`, Hinweis „nicht übernommen“; in QGIS mit ALKIS-Export und OSM-Download geprüft | #44 |
| F5 W18 Kartenstile und PDF-Karte | Windows | Nutzungskarte, Schwarzplan, Graustufen; PDF A4–A0 mit Legende, Maßstab, Nordpfeil, Gebiet, Lizenzblock; Feedback aus dem Live-Test | #45 |
| F3 M24 Dubletten mit Beispiel | Mac | `duplicate_groups` mit Grund, Unterschieden und Beispielsatz; in QGIS geprüft | #46 |
| F6, E35, F7, M10b | Mac | Ziel-Punkte; Niedersachsen-Cache; Erreichbarkeit Luftlinie; ALKIS-Aufträge für 10 Länder (WFS in 1-km-Kacheln) – live geprüft | PR offen |

**Entfallen:** M22 „Fläche aus der Geometrie in `area_m2`“ (Wunsch Person
Mac). Die Flächenberechnung selbst braucht nur der Abgleich ALKIS ↔ OSM (E12)
und steckt deshalb in Aufgabe 15 (M14). `area_m2` bleibt leer, wenn die Quelle
keine Fläche angibt. Das weicht von G9 (`PLAN.md` §3.4) ab → mit Person
Windows abstimmen (§7).

## 6. Offene Aufgaben in der Reihenfolge, in der sie erledigt werden

Die Nummer ist die Reihenfolge. Aufgaben einer Etappe, die nicht aufeinander
warten, können Mac und Windows gleichzeitig erledigen. Die Kürzel (M9, W11 …)
bleiben, damit Verweise in PRs und Commits weiter stimmen.

| Nr. | Aufgabe | Wer | Wartet auf |
| --- | --- | --- | --- |
| | **Etappe F – Feature Freeze, heute (19.11.) vor allem anderen** | | |
| F0 | G11 Vertrag für Spalten, Hinweise und Dubletten (= G6 + E29–E31) ✓ #43 | gemeinsam | – |
| F1 | M23 Spalten lesen und lesbar benennen ✓ #44 | Mac | F0 |
| F2 | W14 Schritt 5 neu: Spaltenliste (Branch `feature/ui-schritt5-spalten`) | Windows | F0, F1 |
| F3 | M24 Dubletten mit Beispiel erklären ✓ #46 | Mac | F0 |
| F4 | W17 Dubletten-Dialog mit Beispiel und Zoom | Windows | F3 |
| F5 | W18 PDF-Layout und Kartenstile (mit 14a Lizenzblock) ✓ #45 | Windows | – |
| F6 | M17 Teil 1: Startpunkte als OSM-Punkte ✓ (PR offen) | Mac | – |
| F6b | Farben, Zeichen-Rang und Icons für die Punkt-Kategorien aus F6 | Windows | F6 |
| F7 | M20 Erreichbarkeit Stufe 1: Luftlinie ✓ (PR offen) | Mac | F6 |
| F8 | W16 Erreichbarkeit in der Benutzerführung | Windows | F7 |
| F8b | W11b Niedersachsen-Cache in QGIS, wenn Overpass scheitert (E35; `osm_cache.py` ✓, PR offen) | Windows | – |
| F9 | G12 Plan nachziehen, alles in QGIS testen; Feature Freeze erst danach entscheiden | gemeinsam | F0–F8b |
| | **Etappe A – jetzt starten** | | |
| 1 | G6 Vertrag erweitern (→ in F0 aufgegangen) | gemeinsam | – |
| 2 | M9 Recherche ALKIS-Dienste der Länder ✓ | Mac | – |
| 3 | M10a OSM-Abfrage und Größenprüfung ✓ | Mac | – |
| 4 | W14 Schritt 5 umbauen | Windows | Teil 2: 1 |
| 5 | G10 Soziale Daten beschließen | gemeinsam | – |
| 6 | M18 Recherche GTFS und Zensus | Mac | – |
| 7 | M6 Fehlende Werte melden | Mac | – |
| | **Etappe B – Download und mehrere Quellen** | | |
| 8 | W10 Schritt 3 „Daten laden“ umbauen (Teil 1 ✓ #33; Teil 2: Länderliste aus `alkis_states()` und ALKIS-Download in 1-km-Kacheln, Zusammenfügen über `oid`) | Windows | Teil 2: 3, 10 |
| 9 | W11 Herunterladen in QGIS ✓ (OSM, #40) | Windows | 3 |
| 10 | M10b ALKIS-Aufträge ✓ (PR offen; Bundesland von Hand, E11 geändert) | Mac | 2 |
| 11 | M12 ALKIS-Profile für die Dienst-Daten (Teil 1 ✓ „ALKIS vereinfacht“) | Mac | 2 |
| 12 | M13 Mehrere Quellen in einem Lauf | Mac | 1 |
| 13 | M15 Teil 2: „Mehr erfahren“-Texte | Mac | 1 |
| 14 | W13 „Mehr erfahren“ anzeigen | Windows | 1, 13 |
| 14a | W8c Block „Datenquellen und Lizenzen“ in der Ausgabe | Windows | 12 |
| | **Etappe C – Abgleich und Abnahme** | | |
| 15 | M14 Quellen abgleichen (mit Flächenberechnung) | Mac | 12 |
| 16 | W12 Vorrang je Kategorie | Windows | 15 |
| 17 | M7 Ende-zu-Ende-Test ohne QGIS | Mac | 15 |
| 18 | W9 Plugin-ZIP und Test auf Windows | Windows | 9 |
| 19 | G7 Zwischentest in zwei Bundesländern | gemeinsam | 9, 10, 12 |
| 20 | G8 Abnahme Phase 2 | gemeinsam | 1–19 |
| | **Etappe D – soziale Daten und Erreichbarkeit** | | |
| 21 | M17 Soziale Infrastruktur aus OSM-Punkten | Mac | 3, 5 |
| 22 | M19 Takt je Haltestelle aus GTFS | Mac | 5, 6 |
| 23 | W15 GTFS herunterladen, Haltestellen-Layer | Windows | 6, 9 |
| 24 | M20 Erreichbarkeit Stufe 1: Luftlinie | Mac | 21 |
| 25 | W16 Erreichbarkeit in der Benutzerführung | Windows | 24 |
| 26 | M21 Erreichbarkeit Stufe 3: ÖV-Güteklassen | Mac | 22, 24 |

Etappe D braucht den Beschluss aus Aufgabe 5 (G10). Die Recherche (6) und
der Beschluss (5) laufen schon in Etappe A, damit Etappe D danach ohne
Wartezeit starten kann.

### Etappe F – Feature Freeze (19.11.2026)

> **Geändert am 19.11.2026 nachmittags (Wunsch Person Mac):** Der Feature
> Freeze kommt **nicht** automatisch nach Etappe F. Zuerst testen wir
> **alles in QGIS** (F9); ob und wann der Feature Freeze gilt, entscheiden
> wir danach gemeinsam. Ein Datum steht noch nicht fest.

Nach dem Feature Freeze kommen keine neuen Funktionen mehr dazu, nur noch
Fehlerbehebung und Test. **Kern** (muss heute fertig werden): F0, F1, F2,
F3, F5. **Wenn die Zeit knapp wird, streichen in dieser Reihenfolge:**
Pixel-Kartenstil → Übersichtskarte im PDF → F8 (Oberfläche Erreichbarkeit;
die Rechnung aus F7 bleibt) → F4 (Dubletten-Text aus F3 genügt) → F6/F7.

#### F0. G11 – Vertrag für Spalten, Hinweise und Dubletten *(gemeinsam)*

- **Absicht:** Ein Vertrag für alles, was Schritt 4–6 und die
  Attributtabelle brauchen. Liskas Vorschlag (G6, oben) plus E29–E31.
- **Ziel:** Eigener PR nur für `contracts.py`, `tests/test_contracts.py` und
  `PLAN.md` §3.4 (Kernfelder statt 11 Pflichtfelder). Neu, alles optional
  mit leerem Standardwert: `ValidationIssue.details`, `.action`,
  `.layer_id`; `ColumnInfo` (`layer_id`, `source_field`, `readable_name`,
  `known`, `examples`, `suggested_target`, `confidence`); Entscheidung je
  Spalte `"target:<kernfeld>"` / `"keep"` (mit Namen) / `"drop"`;
  Dubletten-Beispiel (`example_text`, `reason`, `differences`);
  `source_kind`.
- **Wer:** Person Mac schreibt den Entwurf, Person Windows prüft und mergt.

#### F1. M23 – Spalten lesen und lesbar benennen (E29, E30) *(Mac)*

- **Ziel:** Namensliste je Profil in `mapping_rules.json` (ALKIS-Export,
  ALKIS vereinfacht, OSM-Tags). Die Pipeline liefert `ColumnInfo` für jede
  Spalte jedes Layers, die Kernfelder und die übernommenen Spalten mit ihren
  Werten je Objekt, OSM-Tags aus `other_tags` als eigene Spalten und einen
  Info-Hinweis zu nicht geladenen Spalten.
- **Dateien:** `data_pipeline.py`, `mapping.py`, `mapping_rules.json`,
  Tests.

#### F2. W14 – Schritt 5 neu: Spaltenliste (E29, E30) *(Windows)*

- **Ziel:** Oben die drei Zeilen „Was siehst du? / Was entscheidest du? /
  Was passiert dann?“. Je Layer eine Liste: Häkchen, lesbarer Name
  (änderbar), Beispielwerte. Auswahllisten nur noch für die Kernfelder.
  „Nicht geladen (nicht lesbar)“ eingeklappt. `outputs.py` schreibt
  Kernfelder plus gewählte Spalten in die Ergebnis-Layer.

#### F3. M24 – Dubletten mit Beispiel erklären (E31) *(Mac)*

- **Ziel:** Je Dubletten-Gruppe `example_text`, `reason` und `differences`
  mit lesbaren Spaltennamen. Danach mit dem ALKIS-Export (`_kon`) in QGIS
  prüfen, **welche** Spalten die vielen Dubletten verursachen (Person Mac
  testet, Daten bleiben lokal) – ggf. Folgevorschlag.

#### F4. W17 – Dubletten-Dialog mit Beispiel und Zoom (E31) *(Windows)*

- **Ziel:** Schritt 6 zeigt je Layer den Satz, was „Zusammenführen“
  bewirkt, das Beispiel aus F3 und einen Knopf, der auf die Stelle zoomt.

#### F5. W18 – PDF-Layout und Kartenstile (E32, E33, E28) *(Windows)*

- **Ziel:** Echtes Kartenlayout statt Text-PDF: Karte, Legende, Datum,
  Block „Datenquellen und Lizenzen“ (übernimmt 14a); wählbar Maßstab,
  Nordpfeil, Titel/Untertitel, Namen/Kurs, Gebietsumriss mit Puffer,
  Übersichtskarte; Formate A4–A0 hoch/quer; Kartenstile Schwarzplan,
  Nutzungskarte farbig, Graustufen (Pixel optional); Schwarzplan aus den
  geladenen Gebäuden als Hintergrund zuschaltbar.

#### F6. M17 Teil 1 – Startpunkte als OSM-Punkte (E22, E34) *(Mac)*

- **Ziel:** Overpass-Abfrage (`sources_catalog.json`) holt auch Punkte;
  `mapping_rules.json` ordnet sie den Kategorien und Unterarten aus E34 zu
  (inkl. Krankenhaus, Drogerie, Hochschule, Park). Flächen-Objekte wie
  Krankenhausgelände zählen über ihren Mittelpunkt.

#### F7. M20 – Erreichbarkeit Stufe 1: Luftlinie (E26, E34) *(Mac)*

- **Ziel:** QGIS-freie Funktion: für jedes Gebäude Abstand zum nächsten
  gewählten Startpunkt (Kategorie/Unterart) in Metern und „im 300-m- /
  500-m-Radius“ (ja/nein). Radien in einer Einstellungsdatei.

#### F8. W16 – Erreichbarkeit in der Benutzerführung (E34) *(Windows)*

- **Ziel:** Kategorie wählen, dann Häkchen bei Unterarten; Ergebnis
  wählbar: Radien um die Startpunkte (QGIS-Puffer) und/oder Gebäude
  eingefärbt nach Abstand (Werte aus F7).

#### F9. G12 – Plan nachziehen, alles in QGIS testen *(gemeinsam)*

- **Ziel:** §5 Erledigt und §6 aktualisieren, `PLAN.md`/`CLAUDE.md`
  anpassen, dann **alles in QGIS testen** (beide, auf dem gemeinsamen Stand).
  Erst danach entscheiden wir, ob und wann der Feature Freeze gilt.

### Etappe A – jetzt starten

#### 1. G6 – Vertrag erweitern *(gemeinsam)*

- **Absicht:** Neue Felder `source_kind` (S11) und `details` (S13) gehören in
  die gemeinsame Datei `contracts.py`. Außerdem braucht Schritt 5 nach G9
  mehr als heute: „Weitere Spalten (12)“ und „als Originalspalte behalten /
  weglassen“ gehen mit dem heutigen Vertrag nicht (die Pipeline liefert nur
  Spalten **mit** Vorschlag, `AttributeSuggestion` kennt kein „behalten“).
- **Ziel:** Eigener PR nur für `contracts.py` und `tests/test_contracts.py`;
  die andere Person prüft und mergt. Festgelegt wird auch, wie die Pipeline
  **alle** Spalten eines Layers mit Beispielwerten liefert und wie
  „behalten“ / „weglassen“ zurückkommt.
- **Wartet auf:** nichts. Der wichtigste gemeinsame Schritt: 4 (Teil 2),
  12, 13 und 14 warten darauf.

##### Vorschlag Person Windows (19.11.2026) – zur Abstimmung im PR

**Anlass:** Im Live-Test (OSM und ALKIS) waren Schritt 4, 5 und 6 nicht
verständlich: Man sieht Informationen, weiß aber nicht, was sie bedeuten,
was man entscheiden soll und was ein Klick bewirkt. Jeder der drei Schritte
bekommt deshalb oben drei feste Zeilen – **„Was siehst du?“, „Was
entscheidest du?“, „Was passiert dann?“** – und nur noch Bedienelemente, die
etwas bewirken. Dafür braucht die Oberfläche von der Pipeline:

| Schritt | Was die Nutzerin sehen soll | Was die Pipeline dafür liefert (neu) |
| --- | --- | --- |
| **4 Layer prüfen** | Je Hinweis **ein Satz** „was ist los“ und **ein Satz** „was tun“ (oder „nichts zu tun“); Rest unter „Mehr erfahren“. Hinweise ohne Handlungsbedarf zusammengefasst („12 Infos, nichts zu tun“). | `ValidationIssue.details` (langer Text), `ValidationIssue.action` (kurzer Satz „was tun“, leer = nichts zu tun), `ValidationIssue.layer_id` (statt Layername aus dem Text zu lesen). |
| **5 Attributzuordnung** | Je Layer ein Ausklappmenü; im Kopf „4 zugeordnet, 12 weitere“. **Alle** Spalten mit 2–3 Beispielwerten; je Spalte „→ Zielfeld“ / „als Originalspalte behalten“ / „weglassen“; ⓘ-Erklärung je Zielfeld (aus M15). | Neue Struktur `ColumnInfo` je Layer und Spalte: `layer_id`, `source_field`, `examples` (2–3), `suggested_target` (leer = kein Vorschlag), `confidence`. Rückweg: Entscheidung je Spalte `"target:<feld>"`, `"keep"` oder `"drop"`. |
| **6 Harmonisierung** | Je Layer **ein Satz**, was „Zusammenführen“ konkret bewirkt („645 Gruppen → 645 Gebäude statt 1 675 Zeilen“), dazu ein **Beispiel in Alltagssprache** („Eckhaus Hauptstraße 2 / Nebenweg 1 erscheint zweimal mit gleicher Form“) statt technischer Werte. | Je Dubletten-Gruppe ein lesbares Beispiel (`example_text`) und der Grund (`reason`: gleiche Form / gleiche ID / nur Adresse anders). Texte inhaltlich: Person Mac (M15). |

Außerdem `source_kind` je Datensatz (S11, wie oben). Alle neuen Felder sind
**optional mit leerem Standardwert**, damit bestehende Tests und Daten
weiterlaufen. Die Oberfläche (W13, W14, Schritt 6) nutzt sie, sobald sie da
sind; bis dahin bleibt der heutige Stand.

**Offene Fragen an Person Mac:** (1) Passen Namen und Form der Felder?
(2) Kann die Pipeline Beispielwerte für *alle* Spalten liefern, ohne bei
großen Layern langsam zu werden (z. B. nur die ersten 200 Zeilen ansehen)?
(3) Gibt es Hinweise, für die „was tun“ schwer zu formulieren ist?

##### Antwort Person Mac (19.11.2026)

Der Vorschlag wird übernommen und mit E29–E31 zu **G11** (Etappe F)
zusammengeführt.

1. **Namen und Form passen.** `ColumnInfo` bekommt zusätzlich
   `readable_name` (vorgeschlagener lesbarer Name aus der Namensliste, E30)
   und `known` (steht in der Namensliste → in Schritt 5 angehakt; sonst unter
   „Nicht geladen (nicht lesbar)“). `"target:<feld>"` gibt es nur noch für
   die Kernfelder (E29). Rückweg bei `"keep"` zusätzlich mit dem Namen, den
   die Nutzerin gewählt hat. Dubletten-Gruppen bekommen neben `example_text`
   und `reason` auch `differences`: je abweichender Spalte der lesbare Name
   und die Werte (für die Anzeige „Nutzung = Wohnen / Gewerbe“, E31).
2. **Beispielwerte für alle Spalten: ja, ohne Mehraufwand.** Die Pipeline
   liest beim Zuschnitt ohnehin jede Zeile im Gebiet; dabei werden je Spalte
   die ersten 3 verschiedenen, nicht leeren Werte gemerkt. Eine Grenze von
   200 Zeilen ist nicht nötig.
3. **„Was tun“ ist schwer** nur bei: abweichendem Koordinatensystem (hängt
   davon ab, wie die Datei in QGIS geladen wurde → „Datei in QGIS ins
   Projekt-KBS umprojizieren und neu laden“), unsicheren Dubletten (→ „in
   Schritt 6 entscheiden“) und Objekten ohne lesbare Geometrie (→ „nichts zu
   tun, diese Objekte fehlen im Ergebnis“). Reine Infos bekommen `action`
   leer.

#### 2. M9 – Recherche: ALKIS-Dienste der 16 Bundesländer *(Mac)*

- **Absicht:** Bevor wir Code schreiben, müssen wir wissen, welches Land was
  anbietet. Das entscheidet, wo es ALKIS gibt (E6).
- **Ziel:** Tabelle je Land: Gibt es einen frei nutzbaren Dienst (WFS,
  INSPIRE „Gebäude“/„Flurstücke“, Download-Paket)? Lizenz und
  Quellenvermerk? Format und Feldnamen (auch: gibt es eine Geschosszahl)?
  CRS? Daraus wird `sources_catalog.json` (nur Adressen und Regeln, **keine
  Daten**). Außerdem: Lizenz und Quelle für vereinfachte Ländergrenzen (E11)
  und die Nutzungsregeln des öffentlichen Overpass-Servers.
- **Dateien:** `sources_catalog.json`, Abschnitt in `STATUS_DATENPIPELINE.md`.
- **Wartet auf:** nichts. Der größte Blocker für „deutschlandweit“: 10 und
  11 warten darauf.

#### 3. M10a – OSM-Abfrage und Größenprüfung (S9, Teil 1) *(Mac)* – *erledigt*

- **Stand:** `sources.py` mit `plan_osm_download`; Grenzwerte (25/50 km²)
  und Abfrage-Regeln in `sources_catalog.json`; 10 Tests in
  `tests/test_sources.py` (u. a. hält ein Test die abgefragten OSM-Merkmale
  mit dem OSM-Profil in Einklang). Die erzeugte Abfrage wurde am 18.11. echt
  an Overpass geschickt: Antwort korrekt (300 × 300 m: 116 Gebäude, ca.
  100 KB). **Für Person Windows:** `study_area.py` kann die Grenzwerte aus
  dem Katalog lesen (`sources.area_limits(sources.load_catalog())`).

- **Absicht:** Erster Baustein für den automatischen Download, damit Person
  Windows mit 8 und 9 beginnen kann.
- **Ziel:** `sources.py` mit Tests: OSM-Abfrage (Overpass) für das Rechteck
  um Gebiet + Puffer, umgerechnet in Längen-/Breitengrade; Warnung über
  25 km², Fehlermeldung über 50 km² mit der tatsächlichen Größe (E13); die
  beiden Grenzwerte in `sources_catalog.json`, damit `study_area.py`
  (Schritt 2) dieselben Zahlen liest; Quellenvermerk
  „© OpenStreetMap-Mitwirkende, ODbL“ im Auftrag (damit füllt die Ausgabe die
  Datenquelle vor).
- **Wartet auf:** nichts.

#### 4. W14 – Schritt 5 „Attributzuordnung“ umbauen (E21) *(Windows)*

- **Absicht:** Schritt 5 war im QGIS-Test nicht verständlich.
- **Ziel:** Schritt 5 wie in G9 beschlossen: klare Erklärung oben,
  Ausklappmenü je Layer, verständliche Zielfeld-Namen mit ⓘ-Symbol
  (`target_field_explanation()`). **Teil 1** sofort mit den vorhandenen
  Vorschlägen; **Teil 2** („Weitere Spalten“, „behalten / weglassen“) nach 1.
  Achtung Mausrad: Beim Scrollen über ein Auswahlfeld darf sich das Zielfeld
  nicht versehentlich ändern.
- **Wartet auf:** Teil 2: 1.

#### 5. G10 – Soziale Daten und Erreichbarkeit beschließen (E22–E27) *(gemeinsam)*

- **Absicht:** Die Vorschläge E22–E27 erweitern das Plugin deutlich. Beide
  müssen zustimmen, bevor dafür Code entsteht.
- **Ziel:** E22–E27 bestätigt oder geändert; die Zusatzfelder je Kategorie
  (E23) in `PLAN.md` §3.4 und, falls nötig, in `contracts.py` festgelegt
  (eigener PR wie 1); Antwort auf die offenen Fragen zu Stufe 2 und den
  Haltestellen (§7).
- **Wartet auf:** nichts (G9 ist erledigt).

#### 6. M18 – Recherche: GTFS und Zensus *(Mac)*

- **Absicht:** Vor dem Code wissen, woher Fahrplan- und Einwohnerdaten kommen.
- **Ziel:** Für GTFS (DELFI) und Zensus 2022: Adresse, Lizenz und
  Quellenvermerk, Größe der Datei, wie oft aktualisiert, gibt es einen Dienst
  nur für ein Gebiet? Ergebnis als Einträge in `sources_catalog.json` und
  Abschnitt in `STATUS_DATENPIPELINE.md`.
- **Wartet auf:** nichts (kann parallel zu 2 laufen).

#### 7. M6 – Fehlende Werte melden *(Mac, aus Phase 1)*

- **Ziel:** Je Layer und Quelle ein kurzer Hinweis, z. B. „OSM – Gebäude:
  312 Gebäude ohne Gebäudeart“.
- **Wartet auf:** nichts. Gut für zwischendurch.

### Etappe B – Download und mehrere Quellen

#### 8. W10 – Schritt 3 „Daten laden“ umbauen *(Windows)* – *Teil 1 erledigt, PR #33*

- **Absicht:** Statt einer Datei wählt man Quellen.
- **Ziel:** Kästchen „OSM“, „ALKIS“ und „Eigene Datei“ (E10, mit dem
  bisherigen Dateiauswahl-Feld); Bundesland wird vorgeschlagen und ist
  änderbar (E11); ALKIS ist ausgegraut mit Erklärung, wenn das Land keinen
  Dienst hat; Warnung über 25 km², Meldung über 50 km² (E13); ein eigener
  ALKIS-Export wird als ALKIS erkannt (E16). Außerdem in Schritt 2: Anzeige
  der Gebietsgröße (E17).
- **Stand:** Teil 1 (mit Platzhaltern) ist in PR #33 gemergt: Gebietsgröße
  in Schritt 2, Quellenwahl mit Länderliste in Schritt 3, klare Meldung,
  dass der Download noch fehlt. **Teil 2:** Bundesland-Vorschlag und
  Einschränkungen je Land aus `sources_catalog.json` (Bayern ohne Flurstücke,
  Berlin und Saarland ohne Nutzung, Sachsen-Anhalt bis zur Lizenzklärung).
- **Wartet auf:** Teil 2: 3 und 10.

#### 9. W11 – Herunterladen in QGIS (S10) *(Windows)*

- **Ziel:** Vor jedem Download den Ordner abfragen, zuletzt gewählter Ordner
  als Vorschlag vorausgewählt (E14, E18), Download als `QgsTask` mit
  Fortschritt (Schrittleiste/Ladebalken im klassischen Stil, Angel-Szene im
  Pixel-Stil) und dem vorhandenen „Laden abbrechen“, Speichern als
  GeoPackage mit Quelle und Datum im Namen, Umprojektion ins Projekt-CRS,
  verständliche Fehler und Abbruch ohne Internet (E15).
- **OSM-Format:** Das OSM-Profil (M11) erwartet das GDAL-Standardformat:
  Layer genau `multipolygons`, `lines`, `points`, Spalten `osm_id`,
  `osm_way_id`, `other_tags`, alles im Projekt-CRS. Bitte in S10 bestätigen.
- **Lizenz (E28):** Quelle, Abrufdatum, Lizenz, Quellenvermerk und Adresse
  aus dem Download-Auftrag als Metadaten ins GeoPackage schreiben.
- **Wartet auf:** 3.

#### 10. M10b – ALKIS-Aufträge und Bundesland (S9, Teil 2) *(Mac)*

- **Ziel:** ALKIS-Auftrag aus dem Katalog; Bundesland-Vorschlag aus den
  Ländergrenzen (E11); verständlicher Hinweis, wenn ein Land kein ALKIS
  anbietet. Tests.
- **Wartet auf:** 2.

#### 11. M12 – ALKIS-Profil(e) für die Dienst-Daten *(Mac)* – *Teil 1 erledigt*

- **Absicht:** Die Felder aus den Diensten der Länder heißen anders als im
  bisherigen Export (`…_kon.gpkg`).
- **Ziel:** Je Lieferformat aus 2 ein Profil in `mapping_rules.json` (mit
  Objekt-ID, Adresse und – wenn vorhanden – Geschosszahl), mit Tests.
- **Stand Teil 1:** Profil **„ALKIS vereinfacht“** für die 11 Länder mit
  diesem Format. Gebäude werden von Überdachungen/Bauwerken und
  Gebäudeteilen getrennt (Spalte `gebnutzbez`), Objektart aus `funktion`;
  Nutzung mit Hauptart (`nutzart`) und Detail (`bez`); Adresse aus
  `lagebeztxt`, Geschosszahl aus `anzahlgs` (Niedersachsen liefert keine).
  Mit einer echten Stichprobe aus Niedersachsen (500 × 500 m Donnerschwee)
  geprüft: 648 Gebäude, 62 Bauwerke, 15 Gebäudeteile, 139 Nutzungsflächen,
  keine falschen Hinweise.
- **Teil 2 (offen):** Profile für BW (eigenes Schema), HB (AAA-Vollschema),
  Berlin, Saarland (INSPIRE) und Bayern (Downloads).
- **Wartet auf:** Teil 2: nichts.

#### 12. M13 – Mehrere Quellen in einem Lauf (S11) *(Mac)*

- **Ziel:** `import_sources` mit Tests; jeder Datensatz kennt seine Quelle
  (`source_kind`); Hinweise nennen die Quelle („OSM – Gebäude: …“). Für E28:
  eine Liste der **tatsächlich genutzten** Quellen mit Lizenz, Link und
  Quellenvermerk für den Lizenz-Block der Ausgabe (14a).
- **Wartet auf:** 1.

#### 13. M15 Teil 2 – „Mehr erfahren“-Texte (S13) *(Mac)*

- **Ziel:** Alle Pipeline-Hinweise haben eine kurze `message` (ein bis zwei
  Sätze) und eine ausführliche `details`.
- **Wartet auf:** 1.

#### 14. W13 – „Mehr erfahren“ anzeigen (S13) *(Windows)*

- **Ziel:** Hinweise zeigen nur den kurzen Text; „Mehr erfahren“ klappt
  `details` auf.
- **Wartet auf:** 1; Texte aus 13.

#### 14a. W8c – Block „Datenquellen und Lizenzen“ in der Ausgabe (E28) *(Windows)*

- **Absicht:** Die Lizenzen verlangen Quellenvermerk, Lizenz und einen
  Hinweis auf Veränderungen – sichtbar dort, wo die Daten weitergegeben
  werden.
- **Ziel:** GeoPackage (als Metadaten) und PDF enthalten einen Block mit
  allen tatsächlich genutzten Quellen (Quellenvermerk mit Jahr, Lizenz mit
  Link), dem Satz „Daten zugeschnitten und zusammengeführt (verändert)“ und,
  wenn OSM dabei ist, „Abgeleitete Daten aus OpenStreetMap unterliegen der
  ODbL“. Test in `test_output_step.py`.
- **Wartet auf:** 12 (Liste der genutzten Quellen).

### Etappe C – Abgleich und Abnahme

#### 15. M14 – Quellen abgleichen (S12) *(Mac)*

- **Ziel:** Abgleich ALKIS ↔ OSM je Kategorie nach E12 (Mittelpunkt liegt im
  anderen Objekt und Flächen weichen höchstens 20 % ab; Wert in einer
  Einstellungsdatei), `apply_source_priority`. Dafür eine **Flächenberechnung
  für Polygone** in reinem Python (Löcher abgezogen, Projekt-CRS in Metern).
  Tests mit künstlichen, leicht verschobenen Gebäuden (unter und über 20 %
  Abweichung).
- **Wartet auf:** 12.

#### 16. W12 – Vorrang je Kategorie (S12) *(Windows)*

- **Ziel:** In Schritt 6 je Kategorie eine Auswahl „ALKIS / OSM“ mit Anzahl
  der betroffenen Objekte, vorausgewählt nach E19; Ergebnis erst nach
  Bestätigung an `apply_source_priority`.
- **Wartet auf:** 15.

#### 17. M7 – Ende-zu-Ende-Test ohne QGIS *(Mac, aus Phase 1, erweitert)*

- **Ziel:** künstliches ALKIS- und OSM-GeoPackage → `import_sources` →
  Abgleich → Vorrang → `output_plan()`.
- **Wartet auf:** 15, Absprache zur gemeinsamen Testdatei.

#### 18. W9 – Plugin-ZIP und Test auf Windows *(Windows, aus Phase 1)*

- **Wartet auf:** 9.

#### 19. G7 – Zwischentest in zwei Bundesländern *(gemeinsam)*

- **Absicht:** „Deutschlandweit“ beweisen wir nur, wenn es nicht nur in
  Oldenburg klappt.
- **Ziel:** Donnerschwee (Niedersachsen, EPSG:25832) **und** ein Gebiet im
  Osten (EPSG:25833, z. B. Sachsen oder Brandenburg) laufen von Schritt 1 bis 9
  durch, einmal auf Mac, einmal auf Windows.
- **Wartet auf:** 9, 10, 12.

#### 20. G8 – Abnahme Phase 2 *(gemeinsam)*

- **Ziel:** Abnahmekriterien aus `PLAN.md` §9 gelten weiter, zusätzlich:
  OSM und (wo verfügbar) ALKIS werden automatisch geholt; **alle genutzten
  Quellen stehen mit Quellenvermerk, Lizenz und Veränderungshinweis in
  GeoPackage und PDF (E28)**; Vorrang je Kategorie funktioniert; keine
  falschen Dubletten-Rückfragen bei nur einer Quelle.
- **Wartet auf:** 1–19.

### Etappe D – soziale Daten und Erreichbarkeit (nach dem Beschluss in 5)

#### 21. M17 – Soziale Infrastruktur aus OSM-Punkten (E22) *(Mac)*

- **Absicht:** Ärzte, Schulen, Supermärkte, Spielplätze und Haltestellen
  liegen schon in den OSM-Punkten, werden aber noch keiner Kategorie
  zugeordnet.
- **Ziel:** Kategorie-Regeln und verständliche Namen für den OSM-Layer
  `points` (und passende Flächen, z. B. Schulgelände) in `mapping_rules.json`;
  die OSM-Abfrage aus 3 holt diese Punkte mit. Tests mit künstlichen Punkten.
- **Dateien:** `mapping_rules.json`, `sources.py`, `tests/test_mapping.py`,
  `tests/test_data_pipeline.py`.
- **Wartet auf:** 3, 5.

#### 22. M19 – Takt je Haltestelle aus GTFS (S14, E24) *(Mac)*

- **Ziel:** `gtfs.py` mit `departures_per_hour`, Tests mit einer kleinen,
  im Testcode erzeugten GTFS-ZIP-Datei (Werktag/Wochenende, Zeitfenster,
  Haltestelle ohne Abfahrten). Ergebnis als Zusatzfeld an den Haltestellen.
- **Wartet auf:** 5, 6.

#### 23. W15 – GTFS herunterladen und Haltestellen-Layer (S14, E25) *(Windows)*

- **Ziel:** GTFS-ZIP laden wie in 9 (Ordner fragen, Fortschritt,
  Abbrechen); ist schon eine Datei im Ordner, Datum zeigen und „verwenden
  oder neu laden?“ fragen (E25). Haltestellen im Gebiet als GeoPackage im
  Projekt-CRS schreiben.
- **Wartet auf:** 6, 9.

#### 24. M20 – Erreichbarkeit Stufe 1: Luftlinie (S15, E26) *(Mac)*

- **Ziel:** `accessibility.py`: je Gebäude Abstand zum nächsten Ziel und
  „im 300-m- / 500-m-Radius ja/nein“, für jede Ziel-Kategorie aus 21
  nutzbar. Fehler, wenn das Projekt-CRS nicht metrisch ist. Tests.
- **Wartet auf:** 21.

#### 25. W16 – Erreichbarkeit in der Benutzerführung (S15, E26) *(Windows)*

- **Ziel:** Auswahl, welche Ziele ausgewertet werden (Haltestellen, Ärzte,
  Schulen …); Zusatzfelder in Ergebnis-Layern, GeoPackage und PDF;
  Einzugsbereiche als eigene Layer mit gut lesbarer Darstellung. Falls in 5
  so entschieden: Stufe 2 (Fußweg) mit den Netzwerk-Werkzeugen von QGIS.
- **Wartet auf:** 24.

#### 26. M21 – Erreichbarkeit Stufe 3: ÖV-Güteklassen (S15, E26) *(Mac)*

- **Ziel:** Güteklasse A–F je Gebäude aus Abstand (Stufe 1 oder 2) und Takt
  (22); Klassengrenzen in einer Einstellungsdatei. Tests. Später, nach 6:
  Einwohner im Einzugsbereich aus dem Zensus (E27).
- **Wartet auf:** 22, 24 (bzw. Stufe 2).

---

## 7. Offene Fragen

Die Fragen F1–F6 sind am 18.11.2026 von Person Mac entschieden worden
(→ E10–E15). Person Windows hat sie in G5 bestätigt und um E16–E19 ergänzt.

Jetzt mit Person Windows zu klären:

- **Fläche (`area_m2`):** G9 hat beschlossen, die Fläche aus der Geometrie zu
  berechnen, wenn die Quelle keine angibt. Person Mac möchte das nicht als
  eigenen Schritt umsetzen; die Berechnung entsteht ohnehin in 15 (M14) für
  den Abgleich. Vorschlag: `area_m2` vorerst nur aus der Quelle, `PLAN.md`
  §3.4 entsprechend anpassen. Später kann die Berechnung aus 15 das Feld mit
  wenig Aufwand füllen, falls es doch gebraucht wird.
- ~~**Gleiche Layernamen** bei Linien und Flächen~~ → **gelöst (PR #40):**
  „Straßen (Linien)“ / „Straßen (Flächen)“.
- **Übereinanderliegende Objekte aus einer Quelle** mit verschiedener ID
  (z. B. Straße und Radweg in OSM): überhaupt nachfragen? (siehe PR #29)

Durch 2 (M9) beantwortet:

- *In welchen Bundesländern gibt es frei nutzbares ALKIS?* In **allen 16**
  (ohne Eigentümer). Bayern nur als Download und ohne Flurstücke.
- *Reichen die Inhalte für Nutzungsflächen, Straßen und Grünflächen?* In 14
  Ländern ja (Tatsächliche Nutzung ist dabei). **Berlin und Saarland** bieten
  keine Nutzung als Dienst an – dort kommen diese Kategorien aus OSM.

Neu aus M9, mit Person Windows zu klären:

- ~~Rechteck für die OSM-Abfrage in Längen-/Breitengraden~~ → **entschieden
  (PR #34):** QGIS rechnet das Rechteck in EPSG:4326 um und übergibt es an
  `sources.py`; die Pipeline rechnet nicht um.
- **Lizenz Sachsen-Anhalt** am Landesportal bestätigen, bis dahin kein
  ALKIS-Abruf für ST (E28).
- ~~E28 bestätigen~~ → **bestätigt** von Person Windows in PR #34.

Zu sozialen Daten und Erreichbarkeit (in 5 klären):

- **Stufe 2 (Fußweg):** Rechnen wir mit den Netzwerk-Werkzeugen von QGIS
  (Windows, schneller fertig, braucht QGIS) oder mit einer eigenen Wegsuche
  in der Pipeline (Mac, ohne QGIS testbar, mehr Aufwand)?
- **Haltestellen doppelt:** Haltestellen gibt es in OSM **und** in GTFS.
  Nehmen wir nur GTFS (hat den Takt) oder gleichen wir beide über Name und
  Abstand ab?
- **Welche Zusatzfelder genau** (E23), und wie heißen sie für die Nutzenden?
- **Größe von GTFS:** Reicht die Rechenzeit, wenn die deutschlandweite
  Abfahrten-Tabelle Zeile für Zeile gelesen wird? Wird in 6 und 22 gemessen.
