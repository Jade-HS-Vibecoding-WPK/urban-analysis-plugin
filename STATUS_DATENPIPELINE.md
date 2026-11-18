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

## Tests

`.venv/bin/python -m pytest tests` (Python 3.9 im Projekt-venv; das
System-`python3` hat ein kaputtes pytest). Stand: 221 grün, 1 rot
(`test_result_layers.py`, siehe oben Punkt 1).

## Als Nächstes (Person Mac)

M9 Recherche ALKIS-Dienste der Länder · M10 Quellen bestimmen (OSM-Teil und
Größenprüfung können sofort starten) · M18 Recherche GTFS/Zensus · M6
fehlende Werte.
