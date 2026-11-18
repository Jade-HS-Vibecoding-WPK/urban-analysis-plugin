# Arbeitsplan Phase 2: Deutschlandweit mit OSM und ALKIS

Stand: 18.11.2026 – **E5–E15 von Person Windows bestätigt (G5), ergänzt um
E16–E19. Person Mac stimmt E16, E17 und E19 zu; E18 auf Wunsch der Person
Mac geändert (jedes Mal fragen, letzter Ordner als Vorschlag).**

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
| E11 | **Bundesland wird automatisch erkannt und ist änderbar:** Das Plugin bringt vereinfachte Ländergrenzen mit (offene Daten des Bundes, Lizenz in M9 prüfen), schlägt das Land vor, die Nutzerin kann es ändern. |
| E12 | **Abgleich ALKIS ↔ OSM:** Mittelpunkt des einen liegt im anderen **und** die Flächen weichen höchstens **20 %** ab → wahrscheinlich gleich. Liegt der Mittelpunkt drin, aber die Abweichung ist größer → unsicher, wird zur Entscheidung angezeigt. Der Wert steht in einer Einstellungsdatei und ist änderbar. |
| E13 | **Gebietsgröße höchstens 25 km²** (Gebiet inklusive Puffer, gemessen am umgebenden Rechteck, das heruntergeladen wird). Darüber erscheint eine klare Meldung, und es wird nichts geladen. |
| E14 | **Speicherort:** Vor jedem Download fragt das Plugin, in welchen Ordner die Daten sollen. Dateiname enthält Quelle und Datum. |
| E15 | **Ohne Internet / Dienst antwortet nicht:** nur eine verständliche Meldung, der Download wird abgebrochen. Keine automatische Wiederverwendung alter Downloads. Ein früherer Download kann aber von Hand als „Eigene Datei“ geladen werden. |

Ergänzungen von Person Windows in G5:

| Nr. | Entscheidung |
| --- | --- |
| E16 | **Eigener ALKIS-Export als Datei (ergänzt E6, E10):** Unter „Eigene Datei“ darf auch ein eigener ALKIS-Export geladen werden (z. B. `lkr_03403_Stadt_Oldenburg_kon.gpkg`). Das Plugin erkennt ihn am Profil und behandelt ihn als Quelle `"ALKIS"`. So bleiben Phase-1-Ablauf und Tests mit der lokalen Datei erhalten. |
| E17 | **Gebietsgröße schon in Schritt 2 (ergänzt E13):** Schritt 2 zeigt beim Wählen oder Zeichnen die Größe von Gebiet + Puffer (umgebendes Rechteck), z. B. „6,1 km² von höchstens 25 km²“. Über der Grenze erscheint dort schon ein Hinweis; die verbindliche Prüfung bleibt in S9. |
| E18 | **Zielordner jedes Mal fragen, mit Vorschlag (ergänzt E14):** Vor jedem Download fragt das Plugin nach dem Ordner (E14 bleibt). Im Auswahlfenster ist der zuletzt gewählte Ordner schon vorausgewählt; beim allerersten Download der Ordner des QGIS-Projekts. Die Nutzerin bestätigt oder wählt einen anderen. Dateiname weiter mit Quelle und Datum. *(geändert von Person Mac nach dem G5-Review)* |
| E19 | **Vorgeschlagener Vorrang (ergänzt E7):** Schritt 6 schlägt je Kategorie eine Quelle vor – Gebäude und Nutzungsflächen: ALKIS; Straßen und Grünflächen: OSM. Die Nutzerin bestätigt oder ändert; erst dann gilt die Auswahl. Der Vorschlag steht in einer Einstellungsdatei und ist änderbar. |

Vorschläge von Person Mac nach dem QGIS-Test (18.11.2026, in G9 gemeinsam zu
bestätigen):

| Nr. | Vorschlag |
| --- | --- |
| E20 | **Zielschema um Objekt-ID und Adresse erweitern:** Die Ergebnis-Layer bekommen zwei neue Felder: `object_id` (Original-ID der Quelle, z. B. ALKIS `objid`, später OSM `osm_id`) und `address` (Straße und Hausnummer, je Adresse zusammengesetzt, mehrere Adressen getrennt mit „; “, z. B. „Hauptstraße 2; Nebenweg 1“). Bisher kennen die Ergebnis-Layer nur die 8 Felder aus `PLAN.md` §3.4; IDs, Straßen und Hausnummern sind dort nicht zu finden, obwohl die Pipeline sie im Hintergrund behält. |
| E21 | **Schritt 5 verständlich machen:** Schritt 5 soll klar sagen, *was* die Nutzerin entscheidet und *warum*. Heute sieht man nur einzelne vorgeschlagene Spalten, kann nur eines der 8 Zielfelder wählen und versteht Begriffe wie „Nutzungsdetail“ oder „Status“ nicht. Wie Schritt 5 künftig aussieht, legen wir in G9 gemeinsam fest. |

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
- Eingabe: Untersuchungsgebiet (WKT, Projekt-CRS), Puffer, optional ein von
  der Nutzerin geändertes Bundesland.
- `suggest_state(...)` schlägt das Bundesland vor (E11), aus vereinfachten
  Ländergrenzen, die als Datei im Plugin liegen.
- Ausgabe: Liste von Download-Aufträgen, je Quelle: Adresse (URL) oder
  Abfragetext, Format, CRS der Lieferung, Lizenz, Quellenvermerk (z. B.
  „© OpenStreetMap-Mitwirkende, ODbL“).
- Für Bundesländer ohne frei nutzbaren ALKIS-Dienst: kein Auftrag, sondern ein
  Hinweis.
- Ist das Rechteck aus Gebiet + Puffer größer als 25 km² (E13): keine
  Aufträge, sondern eine Fehlermeldung mit der tatsächlichen Größe.

### S10 – Herunterladen und umprojizieren *(Windows)*

- Läuft in QGIS als `QgsTask` (blockiert die Oberfläche nicht) und nutzt das
  Netzwerk von QGIS (damit Proxy-Einstellungen der Hochschule greifen).
- Fragt vor jedem Download nach dem Zielordner (E14).
- Schreibt je Quelle ein GeoPackage **im Projekt-CRS**, Dateiname mit Quelle
  und Datum (z. B. `osm_2026-11-18.gpkg`).
- Fehler (kein Internet, Dienst antwortet nicht) werden als verständliche
  Meldung angezeigt, der Download bricht ab (E15).

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

---

## 5. Gemeinsame Schritte

### G5 – Regeln anpassen (zuerst!)

- **Absicht:** `CLAUDE.md` und `PLAN.md` sagen noch „Download erst nach dem
  MVP“. Beide Claude-Sessions halten sich daran, solange es dort steht.
- **Ziel:** Ein PR ändert `CLAUDE.md` (Abschnitt Daten, Getroffene
  Entscheidungen E5–E19, Dateitabelle um `sources.py`,
  `sources_catalog.json`, `mapping.py`, `mapping_rules.json`, `geometry.py`)
  und `PLAN.md` (§2, §3.2, §6). Beide haben zugestimmt.
- **Warten auf:** nichts.

### G6 – Vertrag erweitern (S11, S13)

- **Absicht:** Neue Felder `source_kind` und `details` gehören in die
  gemeinsame Datei `contracts.py`.
- **Ziel:** Eigener PR nur für `contracts.py` und `tests/test_contracts.py`;
  die andere Person prüft und mergt.
- **Warten auf:** G5.

### G7 – Zwischentest in zwei Bundesländern

- **Absicht:** „Deutschlandweit“ beweisen wir nur, wenn es nicht nur in
  Oldenburg klappt.
- **Ziel:** Donnerschwee (Niedersachsen, EPSG:25832) **und** ein Gebiet im
  Osten (EPSG:25833, z. B. Sachsen oder Brandenburg) laufen von Schritt 1 bis 9
  durch, einmal auf Mac, einmal auf Windows.
- **Warten auf:** M11, M13, W11.

### G8 – Abnahme Phase 2

- **Ziel:** Abnahmekriterien aus `PLAN.md` §9 gelten weiter, zusätzlich:
  OSM und (wo verfügbar) ALKIS werden automatisch geholt; Quellenvermerke
  stehen in der Ausgabe; Vorrang je Kategorie funktioniert; keine falschen
  Dubletten-Rückfragen bei nur einer Quelle.
- **Warten auf:** alles.

### G9 – Zielschema und Schritt 5 gemeinsam neu denken (E20, E21)

- **Absicht:** Im QGIS-Test fehlten in den Ergebnis-Layern die Objekt-IDs,
  Straßen und Hausnummern, und Schritt 5 (Attributzuordnung) war nicht
  verständlich. Beides hängt am Zielschema, das in `PLAN.md` gemeinsam
  festgelegt ist.
- **Ziel:** Gemeinsam entschieden und in `PLAN.md` §3.4 nachgetragen:
  1. Welche Felder haben die Ergebnis-Layer? (Vorschlag E20: zusätzlich
     `object_id` und `address`.)
  2. Was entscheidet die Nutzerin in Schritt 5? Diskussionsstart: Alle
     Spalten eines Layers werden mit Beispielwerten gezeigt; je Spalte wählt
     man „→ Zielfeld“, „als Originalspalte behalten“ oder „weglassen“.
     Vorschläge der Pipeline sind vorausgewählt.
  3. Verständliche deutsche Namen und eine Ein-Satz-Erklärung je Zielfeld.
- **Warten auf:** nichts. Vor M16 und W14.

---

## 6. Schritte Person Mac – Datenpipeline

### M8 – Gebäude mit mehreren Adressen *(erledigt, PR #21 gemergt)*

- Siehe E8. **Noch offen:** in QGIS mit echten ALKIS-Daten prüfen.
- **Bekannte Schwäche:** Straße (`bez`) und Hausnummer (`hnr`) werden
  getrennt zusammengefasst. Bei einem Eckhaus steht dann „Hauptstraße,
  Nebenweg“ und „2, 1“ – welche Nummer zu welcher Straße gehört, ist nicht
  mehr eindeutig. Wird in M16 behoben.

### M16 – Objekt-ID und Adresse in die Ergebnis-Layer (E20)

- **Absicht:** Nutzende müssen jedes Objekt bis zur Quelle zurückverfolgen
  und Adressen finden können. Die ID braucht außerdem M14 (Abgleich ALKIS ↔
  OSM).
- **Ziel:** Neue Zielfelder `object_id` und `address` in `TARGET_FIELDS`,
  mit deutschen Namen in `mapping_rules.json`. `address` wird **je Zeile**
  aus Straße und Hausnummer gebildet („Hauptstraße 2“) und erst danach beim
  Zusammenfassen (M8) mit „; “ verbunden. Welche Spalten ID, Straße und
  Hausnummer sind, steht im Profil in `mapping_rules.json`. Tests, auch für
  das Eckhaus.
- **Dateien:** `data_pipeline.py`, `mapping.py`, `mapping_rules.json`,
  `tests/test_data_pipeline.py`. Branch z. B. `feature/pipeline-id-adresse`.
- **Achtung:** `tests/test_result_layers.py` (Windows) prüft fest „genau 8
  Felder“. Die Ergebnis-Layer übernehmen neue Felder automatisch; nur dieser
  Test muss im selben Zug von Person Windows angepasst werden → Absprache.
- **Warten auf:** G9 (Punkt 1).

### M9 – Recherche: ALKIS-Dienste der 16 Bundesländer

- **Absicht:** Bevor wir Code schreiben, müssen wir wissen, welches Land was
  anbietet. Das entscheidet, wo es ALKIS gibt (E6).
- **Ziel:** Tabelle je Land: Gibt es einen frei nutzbaren Dienst (WFS,
  INSPIRE „Gebäude“/„Flurstücke“, Download-Paket)? Lizenz und
  Quellenvermerk? Format und Feldnamen? CRS? Daraus wird
  `sources_catalog.json` (nur Adressen und Regeln, **keine Daten**).
  Außerdem: Lizenz und Quelle für vereinfachte Ländergrenzen (E11) und die
  Nutzungsregeln des öffentlichen Overpass-Servers.
- **Dateien:** `sources_catalog.json`, Abschnitt in `STATUS_DATENPIPELINE.md`.
- **Warten auf:** G5.

### M10 – Quellen für ein Gebiet bestimmen (S9)

- **Absicht:** Aus Gebiet + Bundesland die passenden Download-Aufträge bauen.
- **Ziel:** `sources.py` mit Tests: OSM-Abfrage (Overpass) für das Rechteck um
  Gebiet + Puffer, umgerechnet in Längen-/Breitengrade; ALKIS-Auftrag aus dem
  Katalog; Bundesland-Vorschlag aus den Ländergrenzen (E11); Fehlermeldung
  über 25 km² (E13); verständlicher Hinweis, wenn ein Land kein ALKIS
  anbietet.
- **Warten auf:** M9 (für ALKIS und Ländergrenzen); OSM-Teil und
  Größenprüfung können sofort starten.

### M11 – OSM-Profil für die Kategorien

- **Absicht:** OSM benennt Dinge anders als ALKIS (`building=*`,
  `highway=*`, `landuse=*`, `leisure=park` …).
- **Ziel:** Zweites Profil „OSM“ in `mapping_rules.json` mit Objekt-ID
  (`osm_id`) und Kategorie-Regeln; Tests mit einem künstlichen GeoPackage, das
  so aussieht, wie QGIS OSM-Daten speichert.
- **Warten auf:** nichts.

### M12 – ALKIS-Profil(e) für die Dienst-Daten

- **Absicht:** Die Felder aus den Diensten der Länder heißen anders als im
  bisherigen Export (`…_kon.gpkg`).
- **Ziel:** Je Lieferformat aus M9 ein Profil in `mapping_rules.json`, mit
  Tests.
- **Warten auf:** M9.

### M13 – Mehrere Quellen in einem Lauf (S11)

- **Ziel:** `import_sources` mit Tests; Hinweise nennen die Quelle
  („OSM – Gebäude: …“).
- **Warten auf:** G6.

### M14 – Quellen abgleichen (S12)

- **Ziel:** Abgleich ALKIS ↔ OSM je Kategorie nach E12 (20 %, Wert in einer
  Einstellungsdatei), `apply_source_priority`, Tests mit künstlichen, leicht
  verschobenen Gebäuden (unter und über 20 % Abweichung).
- **Warten auf:** M13.

### M6 – Fehlende Werte prüfen *(aus Phase 1)*

- **Ziel:** Je Layer und Quelle ein kurzer Hinweis, z. B. „OSM – Gebäude:
  312 Gebäude ohne Gebäudeart“.
- **Warten auf:** nichts.

### M15 – Hinweistexte kürzen und „Mehr erfahren“ füllen (S13)

- **Ziel:** Alle Pipeline-Hinweise haben eine kurze `message` und eine
  ausführliche `details`. Außerdem (E21): verständliche Namen und eine
  Ein-Satz-Erklärung je Zielfeld in `mapping_rules.json`, damit Schritt 5
  sie anzeigen kann.
- **Warten auf:** G6; Zielfeld-Texte: G9.

### M7 – Ende-zu-Ende-Test ohne QGIS *(aus Phase 1, erweitert)*

- **Ziel:** künstliches ALKIS- und OSM-GeoPackage → `import_sources` →
  Abgleich → Vorrang → `output_plan()`.
- **Warten auf:** M14, Absprache zur gemeinsamen Testdatei.

---

## 7. Schritte Person Windows – Benutzerführung und Integration

### W8b – Ausgabe GeoPackage/PDF *(aus Phase 1)*

- **Ziel:** Bereinigtes GeoPackage und PDF werden erzeugt;
  `apply_data_source` wird aufgerufen. Neu: Der Quellenvermerk wird aus S9
  vorausgefüllt (z. B. „© OpenStreetMap-Mitwirkende“).
- **Warten auf:** nichts (Vorausfüllen: M10).

### W10 – Schritt 3 „Daten laden“ umbauen

- **Absicht:** Statt einer Datei wählt man Quellen.
- **Ziel:** Kästchen „OSM“, „ALKIS“ und „Eigene Datei“ (E10, mit dem
  bisherigen Dateiauswahl-Feld); Bundesland wird vorgeschlagen und ist
  änderbar (E11); ALKIS ist ausgegraut mit Erklärung, wenn das Land keinen
  Dienst hat; Meldung, wenn das Gebiet größer als 25 km² ist (E13);
  ein eigener ALKIS-Export
  wird als ALKIS erkannt (E16). Außerdem in Schritt 2: Anzeige der
  Gebietsgröße (E17).
- **Warten auf:** M10 (kann mit Platzhalter-Daten beginnen).

### W11 – Herunterladen in QGIS (S10)

- **Ziel:** Vor jedem Download den Ordner abfragen, zuletzt gewählter Ordner
  als Vorschlag vorausgewählt (E14, E18), Download als `QgsTask`
  mit Fortschritt (Schrittleiste/Ladebalken im klassischen Stil, Angel-Szene
  im Pixel-Stil) und dem vorhandenen „Laden abbrechen“, Speichern als GeoPackage mit Quelle und Datum im Namen,
  Umprojektion ins Projekt-CRS, verständliche Fehler und Abbruch ohne
  Internet (E15).
- **Warten auf:** M10.

### W12 – Vorrang je Kategorie (S12)

- **Ziel:** In Schritt 6 je Kategorie eine Auswahl „ALKIS / OSM“ mit Anzahl
  der betroffenen Objekte, vorausgewählt nach E19; Ergebnis erst nach
  Bestätigung an `apply_source_priority`.
- **Warten auf:** M14.

### W13 – „Mehr erfahren“ anzeigen (S13)

- **Ziel:** Hinweise zeigen nur den kurzen Text; „Mehr erfahren“ klappt
  `details` auf.
- **Warten auf:** G6.

### W14 – Schritt 5 „Attributzuordnung“ umbauen (E21)

- **Absicht:** Schritt 5 war im QGIS-Test nicht verständlich.
- **Ziel:** Schritt 5 so umgebaut, wie in G9 (Punkt 2) beschlossen: klare
  Erklärung oben, alle Spalten mit Beispielwerten, verständliche Zielfeld-
  Namen mit Erklärung (aus M15). Dazu `tests/test_result_layers.py` an die
  neuen Zielfelder aus M16 anpassen.
- **Warten auf:** G9; Zielfeld-Texte: M15.

### W9 – Plugin-ZIP und Test auf Windows *(aus Phase 1)*

- **Warten auf:** W11.

---

## 8. Reihenfolge auf einen Blick

```text
Etappe   Person Mac                     Gemeinsam              Person Windows
──────   ───────────────────────────    ───────────────────    ──────────────────────────
1        M8 in QGIS prüfen + PR         G5 Regeln anpassen     W8b Ausgabe GPKG/PDF
         M9 Recherche Länder            G6 Vertrag (S11/S13)   Review M8
         M11 OSM-Profil                 G9 Zielschema+Schritt 5
         M16 Objekt-ID + Adresse                               W14 Schritt 5 umbauen
2        M10 Quellen bestimmen (S9)                            W10 Schritt 3 umbauen
         M12 ALKIS-Profile                                     W13 „Mehr erfahren“
         M13 Mehrere Quellen (S11)                             W11 Download in QGIS (S10)
3        M14 Quellen abgleichen (S12)   G7 Test 2 Länder       W12 Vorrang je Kategorie
         M6, M15 Hinweise                                      W9 ZIP-Test
         M7 Ende-zu-Ende-Test           G8 Abnahme
```

**Wer auf wen wartet:** G5 vor allem anderen · G6 vor M13, M15, W13 · M9 vor
M12 und dem ALKIS-Teil von M10 · M10 vor W10/W11 · M14 vor W12 · G9 vor M16
und W14 · M16 vor M14 (Abgleich braucht die Objekt-ID).

---

## 9. Offene Fragen

Die Fragen F1–F6 sind am 18.11.2026 von Person Mac entschieden worden
(→ E10–E15). Person Windows hat sie in G5 bestätigt und um E16–E19 ergänzt.

Noch offen und erst nach M9 entscheidbar:

- In welchen Bundesländern gibt es frei nutzbares ALKIS (und damit überhaupt
  ALKIS im Plugin)?
- Reichen die Inhalte der frei nutzbaren Dienste (oft nur Gebäude und
  Flurstücke) für die Kategorien Nutzungsflächen, Straßen und Grünflächen,
  oder kommen diese dann nur aus OSM?
