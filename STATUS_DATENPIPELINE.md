# Aktueller Stand der Datenpipeline (Person Mac)

Stand: 18.11.2026, Ende des Tages. Plan und Entscheidungen stehen in
`ARBEITSPLAN_DEUTSCHLANDWEIT.md`.

## Was die Pipeline kann

- GeoPackages QGIS-frei lesen (sqlite3 + WKB, ohne shapely/pyproj), auf
  Untersuchungsgebiet + Puffer zuschneiden, CRS prüfen (keine Umprojektion).
- Quellen am **Profil** erkennen (`mapping_rules.json`): **ALKIS**
  (`…_kon.gpkg`) und **OSM** (wie QGIS/GDAL eine `.osm`-Datei speichert:
  Layer `multipolygons`, `lines`, `points` mit `other_tags`).
- Objekte in Kategorien einordnen, mit lesbarer Objektart
  (z. B. „Wohnhaus“ statt `building=house`).
- Zielschema mit **11 Feldern** (M16): `object_id`, `address`, `floors`,
  `source_name`, `object_type`, `object_detail`, `category`, `status`,
  `area_m2`, `year`, `source`.
- Exakte Duplikate entfernen; Gebäude mit mehreren Adressen (Eckhaus) als ein
  Objekt mit allen Adressen (M8); unsichere Fälle als Rückfrage.
- Zu jedem Zielfeld ein deutscher Name und ein Erklärungssatz (M15),
  abrufbar über `target_field_explanation()`.

## Branches und PRs

| Branch | Inhalt | Stand |
| --- | --- | --- |
| `feature/pipeline-id-adresse` | M16 Objekt-ID, Adresse, Geschosszahl · M15 Erklärungen | in QGIS mit ALKIS getestet |
| `feature/pipeline-osm-profil` | M11 OSM-Profil, baut auf dem Branch darüber auf | in QGIS mit echten OSM-Daten (Donnerschwee) getestet; die letzten Linien-Regeln nur mit der Pipeline geprüft |
| `docs/soziale-daten-erreichbarkeit` | Planentwurf E22–E27 (soziale Daten, Erreichbarkeit) | Entwurf, braucht G10 |

**Reihenfolge beim Mergen:** erst M16 + M15, dann M11. Der Planentwurf ist
unabhängig, wird aber erst nach G9 besprochen.

## Was Person Windows dafür tun muss

1. `tests/test_result_layers.py` erwartet noch **8** Felder, jetzt sind es
   **11** → Test anpassen (einziger roter Test).
2. `outputs.py`: `floors` (Geschosszahl) wie `year` als **Ganzzahl** schreiben
   (`INTEGER_FIELDS`).
3. W14: In Schritt 5 die Erklärung je Zielfeld aus
   `target_field_explanation(field)` anzeigen.
4. S10/W11: bestätigen, dass der OSM-Download das GDAL-Standardformat schreibt
   (Layer `multipolygons`, `lines`, `points`, Spalten `osm_id`, `osm_way_id`,
   `other_tags`) **im Projekt-CRS** – genau das erkennt das OSM-Profil.

## Ergebnis des OSM-Tests (Donnerschwee, 500 m Puffer)

- 3 689 Flächen und 3 473 Linien im Gebiet. „Sonstige OSM-Flächen“ von 165
  auf 25 gesenkt, „Sonstige OSM-Linien“ von 1 380 auf 171.
- Neu bei den Linien: eigene Layer **Gebäudeteile** (Umrisse aus dem
  3D-Gebäudemodell, ca. 900), **Hecken und Baumreihen**, **Zäune und
  Mauern**. GDAL legt diese geschlossenen Wege als Linien ab.
- Stellplätze → Straßen, Hecken/Gebüsch → Grünflächen, Schul- und
  Kitagelände → Nutzungsflächen (zieht nach G10 evtl. in „Bildung und
  Betreuung“ um).

## Offene Fragen an Person Windows

- **Gleiche Layernamen:** „Straßen“ und „Fuß- und Radwege“ gibt es als Linien
  und als Flächen; heute erscheint dann `(multipolygons_strassen)` im Namen.
  Vorschlag: Die Oberfläche hängt „– Linien“ / „– Flächen“ an. Die Kategorie
  selbst bleibt gleich, weil ALKIS dieselben Namen nutzt und der Vorrang je
  Kategorie (E19) daran hängt.
- **Rückfrage bei übereinanderliegenden Objekten aus einer Quelle:** OSM-Linien
  mit verschiedener OSM-ID liegen an 4 Stellen genau übereinander (z. B.
  Straße und Radweg), ALKIS hat ähnliche Fälle. Sollen verschiedene IDs aus
  *einer* Quelle überhaupt nachgefragt werden?
- **Mausrad in Schritt 5 (Vermutung):** Einmal stand bei „OSM – Punkte“
  „Datenquelle“ statt des vorgeschlagenen „Geschosszahl“. Möglicherweise
  ändert das Mausrad beim Scrollen über ein Auswahlfeld den Wert.

## M9 – ALKIS-Dienste der 16 Länder (Recherche 18.11.2026)

Ergebnis steht maschinenlesbar in `urban_analysis/sources_catalog.json`
(nur Adressen, Lizenzen, Regeln – keine Daten). Jede WFS-Adresse wurde per
GetCapabilities geprüft; `tests/test_sources_catalog.py` hält den Katalog
vollständig.

**Alle 16 Länder bieten ALKIS offen an** (ohne Eigentümer), aber nicht
überall gleich:

| Land | Weg | Format | Gebäude | Flurstücke | Nutzung | CRS | Lizenz |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NI, NW, SH, HE, HH | WFS | ALKIS vereinfacht | ✓ | ✓ | ✓ | 25832 | CC BY 4.0 / dl-de/zero / dl-de/by |
| SN, MV, BB | WFS | ALKIS vereinfacht | ✓ | ✓ | ✓ | 25833 | dl-de/by / CC BY 4.0 |
| RP, ST, TH | WFS | ALKIS vereinfacht (weniger Layer, TH ältere Version 1.0) | ✓ | ✓ | ✓ | 25832 | dl-de/by / CC BY 4.0 |
| BW | WFS | eigenes Schema (31 Layer) | ✓ | ✓ | ✓ | 25832 | dl-de/by |
| HB | WFS (Server LGLN) | AAA-Vollschema (139 Layer) | ✓ | ✓ | ✓ | 25832 | CC BY 4.0 |
| BE | WFS je Thema | eigenes Schema | ✓ | ✓ | – (nicht gefunden) | 25833 | dl-de/zero |
| SL | WFS | nur INSPIRE | ✓ | ✓ | – | 4258 (geografisch) | dl-de/by |
| BY | Download (Shape-ZIP) | Hausumringe, Tatsächliche Nutzung | nur Umrisse | – (nicht frei) | ✓ je Landkreis | 25832 | CC BY 4.0 |

**Was daraus folgt:**

- **11 Länder liefern das bundesweit gleiche Format „ALKIS vereinfacht“**
  (Layer `GebaeudeBauwerk`, `Flurstueck`, `Nutzung`). Ein Profil in M12
  deckt sie alle ab. Danach kommen BW, HB, BE, SL und BY mit eigenen
  Profilen oder als Lücke (dann OSM).
- **Geschosszahl:** Im Format gibt es das Feld `anzahlgs`, ebenso
  `lagebeztxt` (Adresse als Text). Beide sind optional und nicht in jedem
  Land gefüllt → in M12 mit echten Gebieten prüfen.
- **CRS:** Die Dienste liefern in 25832 oder 25833, Saarland geografisch
  (4258). Die Umprojektion ins Projekt-CRS macht weiterhin QGIS (W11).
- **Ländergrenzen** (E11): VG2500 des BKG, GeoPackage ca. 3 MB, nur in
  EPSG:25832, dl-de/by-2-0. Für Projekte in 25833 muss der Bundesland-
  Vorschlag das Gebiet erst umrechnen → in M10b klären (siehe unten).
- **Overpass** (OSM): höchstens ca. 10 000 Abfragen und unter 1 GB pro Tag,
  Standard-Zeitlimit 180 s, bei Überlast HTTP 429. Ein Gebiet bis 25 km² ist
  eine Abfrage – unkritisch.

**Offen für M10b:**

- Lizenz Sachsen-Anhalt am Landesportal bestätigen (Dienst verweist auf die
  Kostenverordnung; Seite war am 18.11. nicht erreichbar).
- Berlin: WFS für die Tatsächliche Nutzung nicht gefunden.
- Bayern: Download-Adresse der Hausumringe je Regierungsbezirk.
- Ländergrenzen nur in EPSG:25832: Für den Bundesland-Vorschlag reicht das
  Rechteck in EPSG:4326, das QGIS ohnehin liefert – Grenzen dafür einmalig
  als vereinfachte 4326-Datei ins Plugin legen.

## M10a – OSM-Abfrage und Größenprüfung (18.11.2026)

Neues Modul `urban_analysis/sources.py` (QGIS-frei, ohne Zusatzpakete):

- `plan_osm_download(study_area_wkt, buffer_meters, lonlat_box)` →
  `SourcePlan` mit `requests`, `issues`, `area_km2`.
- **Größe (E13):** Rechteck aus Gebiet + Puffer im Projekt-KBS – gleiche
  Rechnung wie Schritt 2. Über 25 km² Warnung (`area-large`, mit
  Bestätigung), über 50 km² Fehler (`area-too-large`) und kein Auftrag.
  Grenzwerte stehen in `sources_catalog.json` (`gebiet`), damit Schritt 2
  dieselben Zahlen lesen kann.
- **Koordinaten:** Das Rechteck für Overpass kommt von QGIS schon in
  EPSG:4326 (vereinbart in PR #34). Werte, die nicht nach Grad aussehen
  (z. B. UTM-Meter) oder vertauscht sind, werden als Fehler gemeldet.
- **Auftrag** (`DownloadRequest`): Overpass-URL, Abfrage in Overpass QL,
  Lieferung EPSG:4326, Dateinamen `osm_<Datum>.osm` (Rohdatei) und
  `osm_<Datum>.gpkg`, Lizenz ODbL mit Link, Quellenvermerk (E28),
  Zeitlimit 300 s.
- **Abfrage:** alle Knoten und Wege mit einem der Merkmale, nach denen das
  OSM-Profil einordnet (ohne `boundary`), plus Flächen-Relationen; ein Test
  hält Katalog und Profil in Einklang.
- **Echt geprüft:** Die erzeugte Abfrage lieferte für 300 × 300 m in
  Donnerschwee 704 Punkte, 144 Wege, 1 Relation (116 Gebäude, ca. 100 KB).
  Der öffentliche Server war zunächst überlastet (HTTP 502, dann 504),
  nach 60 s erfolgreich → W11 braucht wenige Wiederholungen mit Pause.

## M12 Teil 1 – Profil „ALKIS vereinfacht“ (18.11.2026)

Neues Profil in `mapping_rules.json` für die 11 Länder mit dem
AdV-Format (NI, NW, SH, HE, HH, SN, MV, BB, RP, ST, TH). Erkannt an den
Layernamen `GebaeudeBauwerk`, `Nutzung`, `Flurstueck` (ohne `ave:`-Präfix,
so speichert W11) und der Spalte `oid`.

- **Gebäude:** Objektart aus `funktion` (z. B. Wohngebäude, Garage). Der
  Layer enthält auch Überdachungen, Arkaden und Gebäudeteile; die Spalte
  `gebnutzbez` trennt sie in **Gebäude**, **Gebäudeteile** und **Bauwerke
  und Überdachungen**.
- **Nutzung:** Hauptart aus `nutzart` („Weg“), Detail aus `bez` („Rad- und
  Fußweg“). Die Regeln entsprechen dem ALKIS-Export, aber mit ß
  („Straßenverkehr“, „Fließgewässer“), wie die Dienste es schreiben.
- **Objekt-ID** aus `oid`, **Adresse** fertig aus `lagebeztxt` (auch
  mehrere Nummern wie „Weg 4, 6“), **Geschosszahl** aus `anzahlgs`.
- Kleine Erweiterung in `mapping.py`: `detail_field`, `category_field`,
  `address_field` im Profil (bestehende Profile unverändert).
- **Echt geprüft** mit einer Stichprobe aus dem Niedersachsen-Dienst
  (500 × 500 m Donnerschwee, nur im Scratch-Ordner, nicht im Repo):
  648 Gebäude, 62 Bauwerke/Überdachungen, 15 Gebäudeteile, 139
  Nutzungsflächen (53 Rad-/Fußwege, 27 Straßen, 59 Nutzungsflächen),
  keine falschen Hinweise. Alle Gebäude mit Objekt-ID, 365 von 725 mit
  Adresse; **Niedersachsen liefert keine Geschosszahl**.
- Tests: `tests/test_alkis_vereinfacht.py` (5).

Offen (Teil 2): Profile für BW, HB, Berlin, Saarland, Bayern.

## F1 / M23 – Spalten lesen und lesbar benennen (19.11.2026)

Setzt E29/E30 mit dem Vertrag aus G11 (#43) um.

- **`PipelineResult.columns`:** je Eingabe-Layer und Spalte eine
  `ColumnInfo` (ohne Geometrie und Zeilennummer) mit lesbarem Namen, bis zu
  3 Beispielwerten und dem vorgeschlagenen Kernfeld.
- **Bekannt oder nicht:** Bei ALKIS und OSM ist eine Spalte bekannt, wenn sie
  in der Namensliste `field_labels` in `mapping_rules.json` steht (jetzt auch
  ALKIS-vereinfacht-Flurstücke und viele OSM-Merkmale) oder ein Kernfeld
  füllt. OSM-`other_tags` gilt als nicht bekannt (enthält die unlesbaren
  Tags). **Eigene Dateien ohne Profil behalten alle Spalten.**
- **Hinweis** `columns-not-loaded` (Info, je Layer, mit `layer_id` und
  `details`): nennt die nicht übernommenen Spalten.
- **OSM:** Mehr Tags werden aus `other_tags` als Spalten ausgepackt (Name,
  PLZ, Ort, Höhe, Dachform, Baujahr, Oberfläche, Höchstgeschwindigkeit,
  Rollstuhl …). Nebenwirkung: Flächen mit z. B. `shop` nur in `other_tags`
  bekommen jetzt eine Objektart („Geschäft“); die Kategorie ändert sich nicht.
- **Werte je Objekt:** `HarmonizedRecord.extra_attributes` = übernommene
  Spalten mit lesbarem Namen. Der Import füllt sie mit der Vorauswahl.
- **Für Schritt 5 (W14):** `default_column_decisions(columns)` liefert die
  Vorauswahl; `apply_column_decisions(records, columns, decisions)` setzt die
  Entscheidungen um (umbenennen, dazuholen, weglassen, anderes Kernfeld).
  Doppelte Namen oder Kernfelder geben einen `ValueError` mit verständlichem
  Text. Aufruf **nach** `apply_attribute_decisions`.
- **Für die Ausgabe (W14, `outputs.py`):** Kernfelder aus `attributes`, dazu
  die Spalten aus `extra_attributes` schreiben.
- **Offen:** Die Namensliste für den eigenen ALKIS-Export (`_kon`) kennt nur
  die Spalten aus den Tests. Beim QGIS-Test zeigt der neue Hinweis, welche
  Spalten fehlen – die dann nachtragen.
- Tests: `tests/test_columns.py` (10).

## F3 / M24 – Dubletten mit Beispiel erklären (19.11.2026)

Setzt E31 mit dem Vertrag aus G11 um. Baut auf F1 auf (Branch
`feature/pipeline-dubletten-beispiel` liegt auf `feature/pipeline-spalten`).

- **`PipelineResult.duplicate_groups`:** je Gruppe übereinanderliegender
  Objekte eine `DuplicateGroupInfo` mit `reason` („gleiche Form“ oder
  „gleiche Form und gleiche Objekt-ID“), `differences` (abweichende
  Spalten mit lesbarem Namen und Werten, leere Werte als „(leer)“) und
  `example_text`, z. B. „Hier liegen 2 Einträge „Gebäudeteil“ mit genau
  gleicher Form übereinander. Unterschied: Baumaterial „glass“ / „(leer)“;
  Höhe (m) „18“ / „4“.“ Die Adresse steht nur dabei, wenn alle Einträge
  dieselbe haben. Schlüsselspalten (`gfk`) werden hinter ihrem lesbaren
  Zwilling (`gfk__bez`) versteckt, OSM-`other_tags` wird weggelassen.
- **Hinweis `uncertain-duplicate`:** kurzer Text („An 4 Stellen … Sie
  unterscheiden sich nur in …“), `action` („In Schritt 6 entscheiden …“),
  `details` mit dem ersten echten Beispiel des Layers, `layer_id`.
- **Für W17 (Schritt 6):** `describe_duplicate_groups(records)` kann auch
  nach Entscheidungen neu aufgerufen werden.
- Tests: `tests/test_duplicate_groups.py` (6).

## F6 / M17 Teil 1 – Ziel-Punkte für die Erreichbarkeit (19.11.2026)

Setzt E22/E34 um. Branch `feature/pipeline-ziel-punkte` liegt auf
`feature/pipeline-dubletten-beispiel` (F3) und damit auf F1.

- **OSM-Punkte** (`points`) haben jetzt Kategorien und eigene
  Ergebnis-Layer: **Gesundheit** (Krankenhaus, Klinik, Arztpraxis,
  Zahnarztpraxis, Apotheke, weitere `healthcare=*`), **Nahversorgung**
  (Supermarkt, Lebensmittelladen, Bäckerei, Metzgerei, Obst- und
  Gemüseladen, Drogerie, Wochenmarkt), **Bildung und Betreuung** (Schule,
  Kita, Kinderbetreuung, Hochschule), **Freizeit und Grün** (Spielplatz,
  Sportplatz, Sportanlage, Park, Bibliothek), **ÖPNV-Haltestellen**
  (Bus-, Straßenbahnhaltestelle, Haltestelle, Haltepunkt, Bahnhof,
  Bahnhaltepunkt). Alles andere: „Sonstige OSM-Punkte“.
- **Unterart** = Objektart (`object_type`), z. B. „Arztpraxis“. Damit
  wählt W16 „Kategorie + Unterart“ (E34).
- Layer können eigene Namen für Merkmale haben (`tag_labels` je Layer):
  Punkt „Krankenhaus“, Fläche weiter „Krankenhausgelände“.
- **Overpass-Abfrage** holt zusätzlich `healthcare`; alle anderen Merkmale
  wurden schon geladen.
- **Für Person Windows:** sechs neue Kategorien → Icons (W11-Icons) und
  Auswahl beim Kartenthema.
- Noch nicht mit echten OSM-Punkten geprüft (lokale `OSM.gpkg` hat keine).
- Tests: `tests/test_ziel_punkte.py` (5).

## E35 – Niedersachsen-Cache, wenn Overpass scheitert (19.11.2026)

Wunsch Person Mac: Ist Overpass nach allen Wiederholungen überlastet,
holt das Plugin OSM aus dem Niedersachsen-Cache des Teams
(https://github.com/Jade-HS-Vibecoding-WPK/niedersachsen-cache). Nur als
Notlösung, nie still: ein Info-Hinweis sagt es. Branch
`feature/pipeline-osm-cache` (liegt auf F6).

- **Katalog:** Abschnitt `osm_cache` in `sources_catalog.json` (Adresse,
  Dateinamen, Lizenz ODbL, Quellenvermerk, lesbare Namen fehlender
  Merkmale).
- **Neu `urban_analysis/osm_cache.py`** (QGIS-frei, nur Standardbibliothek):
  - `manifest_url(catalog)` → Adresse von `manifest.json`.
  - `plan_cache_download(box, manifest, catalog)` → `CachePlan`: nutzbar
    nur, wenn **jede** z15-Kachel des Download-Rechtecks im Cache liegt
    (sonst `reason` für die Fehlermeldung); `tile_urls` (z15-Kacheln plus
    z12-Kacheln für große Objekte), `missing_keys` (heute `barrier`,
    `building:part`, `power`), Dateinamen, Lizenz, Quellenvermerk.
  - `merge_tiles(tiles)` → Objekte ohne Doppelte (ein Objekt liegt in jeder
    Kachel, die es berührt).
  - `elements_to_layers(elements, keys)` → GeoJSON `points`, `lines`,
    `multipolygons` in EPSG:4326 mit **denselben Spalten wie GDAL** bei einer
    `.osm`-Datei (`osm_id`, `osm_way_id`, `name`, …, `other_tags`);
    geschlossene Wege mit Flächen-Merkmal → Fläche, Multipolygon-Relationen
    aus Wegstücken zusammengesetzt (mit Löchern). Nicht schließbare
    Relationen werden gezählt (`skipped`), nicht still verworfen.
  - `cache_issue(plan, catalog, skipped)` → Info-Hinweis „OSM-Daten kommen
    aus dem Niedersachsen-Cache (Stand …), weil der OSM-Server nicht
    geantwortet hat. Nicht enthalten: Hecken, Zäune und Mauern,
    Gebäudeteile, Stromleitungen und -anlagen.“
- **Live geprüft** (Donnerschwee, Cache-Stand 17.11.2026): 32 Kacheln
  (2 MB), 25 685 Objekte → 7 212 Punkte, 6 435 Linien, 11 353 Flächen,
  keine Relation verloren. Durch die Pipeline: keine Fehler, dieselben
  Kategorien wie beim Overpass-Download, Ziel-Punkte aus F6 erkannt
  (z. B. REWE, PENNY als „Supermarkt“). München → „nicht im Cache“.
- **Für Person Windows (W11b, `osm_download.py`):** Wenn `fetch` nach allen
  Versuchen mit `DownloadError` (überlastet/keine Antwort) endet:
  1. `manifest.json` über das QGIS-Netz laden, `plan_cache_download` mit
     demselben 4326-Rechteck aufrufen.
  2. Nicht nutzbar → bisherige Fehlermeldung plus `plan.reason`.
  3. Nutzbar → alle `tile_urls` laden (gzip, mit `gzip.decompress` und
     `json.loads` lesen), `merge_tiles`, Rohdatei `plan.raw_file_name`
     unverändert speichern (`{"elements": …}`), `elements_to_layers` mit
     `catalog["osm"]["abfrage"]["schluessel"]`, die drei GeoJSON
     (`plan.geojson_name` mit `{layer}`) schreiben und wie bisher als
     `points`/`lines`/`multipolygons` ins GeoPackage `plan.geopackage_name`
     im Projekt-KBS umwandeln.
  4. `cache_issue(...)` an die Hinweise anhängen; Datenquelle mit
     `plan.attribution` vorausfüllen.
- **Gemeinsam:** E35 in den Plan aufnehmen (ergänzt E15: der Cache ist eine
  eigene, wöchentlich neue Quelle, kein alter Download); `osm_cache.py` in
  die Dateitabelle von `CLAUDE.md` (Person Mac).
- Tests: `tests/test_osm_cache.py` (7).

## F7 / M20 – Erreichbarkeit Stufe 1: Luftlinie (19.11.2026)

Setzt E26 (Stufe 1) und E34 um. Branch `feature/pipeline-erreichbarkeit`
liegt auf dem Cache-Branch (Kette F1 → F3 → F6 → Cache → F7).

- **Neu `urban_analysis/accessibility.py`** (QGIS-frei):
  - `target_choices(records)` → was im Gebiet als Ziel vorkommt, je
    Kategorie mit Unterarten und Anzahl, z. B. `{"Nahversorgung":
    [("Bäckerei", 20), ("Supermarkt", 11), …]}` – für die Auswahl in W16.
  - `TargetChoice(category, subtypes)` – Kategorie, optional Unterarten.
  - `add_air_distance(records, choice)` → je Gebäude in
    `extra_attributes`: „Abstand Supermarkt (m)“ (ganze Meter) und
    „Supermarkt bis 300 m“ / „… bis 500 m“ = „ja“/„nein“; dazu ein
    Info-Hinweis „Erreichbarkeit „Supermarkt“ (Luftlinie): 32 % höchstens
    300 m; 57 % höchstens 500 m vom nächsten Ziel entfernt.“ Mehrfach
    aufrufbar (eine Wahl je Aufruf, Spaltennamen trennen sie).
  - `target_records(records, choice)` → die Ziel-Objekte, z. B. für die
    Radien-Kreise in QGIS.
  - Warnung statt stiller Lücke, wenn es keine Ziele oder keine Gebäude
    gibt; Fehler, wenn die Koordinaten in Grad statt Metern sind.
- **Gemessen** vom Mittelpunkt des Gebäudes (`representative_point` in
  `geometry.py`) zum nächsten Ziel. **Flächen als Ziele** über ihren
  Mittelpunkt (`flaechen_als_ziele`): Krankenhausgelände → Gesundheit /
  Krankenhaus, Schulgelände, Kita, Hochschulgelände, Park, Spielplatz,
  Sportplatz, Sportanlage. Viele davon sind in OSM nur als Fläche drin.
- **Einstellungen** in `mapping_rules.json` → `erreichbarkeit`: Radien
  (300/500 m), Ausgangs-Kategorien (Gebäude), Ziel-Kategorien, Flächen als
  Ziele.
- **Live geprüft** mit den Cache-Daten Donnerschwee (nach UTM 32N
  umgerechnet): ÖPNV 79 % ≤ 300 m, 98 % ≤ 500 m; Supermarkt 32 % / 57 %;
  Krankenhaus 4 % / 13 %; Park oder Spielplatz 82 % / 97 %. Drei
  Auswertungen über rund 2 600 Gebäude in 0,24 s.
- **Grenzen:** Luftlinie, nicht Fußweg (Stufe 2 später). Ziele außerhalb
  des geladenen Gebiets fehlen → am Rand zu große Abstände (steht im
  Hinweis). Bei großen Parks zählt der Mittelpunkt, nicht der Eingang.
  Supermärkte, die nur als Gebäude mit `shop=supermarket` eingetragen sind,
  heißen heute „Einzelhandel“ und zählen noch nicht.
- **Für Person Windows (W16):** Auswahl aus `target_choices` (Kategorie,
  dann Häkchen bei Unterarten) → je Wahl `add_air_distance`; Ergebnis
  wählbar: Radien als QGIS-Puffer um `target_records` und/oder Gebäude
  nach „Abstand … (m)“ eingefärbt. Die neuen Spalten stehen in
  `extra_attributes` und kommen mit W14 in die Attributtabelle.
- Tests: `tests/test_accessibility.py` (8).

## Tests

`.venv/bin/python -m pytest tests` (Python 3.9 im Projekt-venv; das
System-`python3` hat ein kaputtes pytest). Stand 19.11.2026: 323 grün.

## Als Nächstes (Person Mac)

Etappe F ist für Person Mac erledigt (F0, F1, F3, F6, F7 und E35). Offen:
PRs nacheinander öffnen (F3, F6, Cache, F7 – jeweils nach dem Merge des
vorherigen), gemeinsam G12 (Plan, E35, `CLAUDE.md`-Dateitabelle mit
`osm_cache.py` und `accessibility.py`). Danach: M10b, M18, M6, M12 Teil 2.
