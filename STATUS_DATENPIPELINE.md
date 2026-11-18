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

## Tests

`.venv/bin/python -m pytest tests` (Python 3.9 im Projekt-venv; das
System-`python3` hat ein kaputtes pytest). Stand 18.11.2026 abends: 262 grün.

## Als Nächstes (Person Mac)

Reihenfolge laut `ARBEITSPLAN_DEUTSCHLANDWEIT.md` §6: 10 M10b
ALKIS-Aufträge und Bundesland · 6 M18 Recherche GTFS/Zensus · 7 M6 fehlende
Werte · M12 Teil 2 (weitere Länderformate).
