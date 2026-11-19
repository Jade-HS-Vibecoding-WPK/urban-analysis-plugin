# Urban Analysis Plugin – Arbeitsregeln für Claude Code

Zwei Personen arbeiten parallel mit je einer eigenen Claude-Code-Session,
einem eigenen lokalen Ordner und einem eigenen Branch. Hintergrund und Ziele
stehen in `PLAN.md`, der aktuelle Stand in `HANDOVER.md`, die Schnittstelle in
`INTEGRATION_HANDOFF.md`.

## Ziel

QGIS-Plugin für Urban-Design-Studierende: geführter 9-Schritte-Workflow
(Projekt-CRS → Untersuchungsgebiet → Daten laden → Layer prüfen →
Attributzuordnung → Harmonisierung → Kartenthema → Ausgabe → Verarbeitung
starten). Pilot: Donnerschwee (Oldenburg), Kartenthema Siedlungsstruktur.
Das Plugin selbst bleibt gebietsunabhängig – Donnerschwee ist nur Testgebiet.

## Technik

- QGIS ≥ 3.44 (Python 3.12). Nur PyQGIS-APIs verwenden, die es in 3.44 gibt.
- QGIS-spezifischen Code (`guided_dialog.py`, `outputs.py`,
  `urban_analysis_plugin.py`) von QGIS-freier, testbarer Logik
  (`contracts.py`, `data_pipeline.py`, `user_guidance.py`) trennen.
- Lange Berechnungen nicht blockierend umsetzen; vorher `QgsTask` prüfen.
- Keine hardcodierten Windows- oder macOS-Pfade; ein Teammitglied nutzt
  Windows, eines macOS.
- Tests: `python -m pytest tests`

## Fachliche Regeln

- Rohdaten nie überschreiben; bereinigte Daten und Ergebnisse als neue Layer.
- Keine stillen Korrekturen oder Fallbacks: Fehler, unsichere Zuordnungen und
  fehlende Kategorien als `ValidationIssue` sichtbar machen.
- Automatische Vorschläge (Attribute, Kategorien) sind nie endgültig, bevor
  die Nutzerin oder der Nutzer sie bestätigt hat.
- Exakte Duplikate automatisch entfernen; unsichere Fälle nur anzeigen.
- UI-Begriffe aus `ui_contract.py` verwenden, keine neuen Bezeichnungen erfinden.

## Daten und Testdaten

- Die ALKIS-Daten (z. B. `lkr_03403_Stadt_Oldenburg_kon.gpkg`) sind
  lizenzpflichtig und bleiben **nur lokal**. Sie werden nie committed, auch
  keine Ausschnitte daraus. Lokale Daten liegen im Ordner `daten/`, den
  `.gitignore` ausschließt.
- Automatische Tests erzeugen ihre GeoPackages selbst (künstliche Geometrien
  im Testcode) und brauchen keine echten Daten.
- Manuelle Abnahme: ALKIS-Ausschnitt Donnerschwee plus Puffer, lokal bei
  beiden unter demselben Dateinamen in `daten/`.
- **Phase 2 (seit 18.11.2026):** Das Plugin holt Daten selbst – OSM für ganz
  Deutschland und ALKIS automatisch von den Diensten der Bundesländer, wo
  diese frei nutzbar sind. Details und Entscheidungen E5–E19 stehen in
  `ARBEITSPLAN_DEUTSCHLANDWEIT.md`.
- Heruntergeladene Daten werden **nie committed**. Sie landen im Ordner, den
  die Nutzerin wählt, oder im gitignorierten `daten/`.
- Eigene lokale GeoPackages bleiben möglich („Eigene Datei“), auch ein
  eigener ALKIS-Export wie `…_kon.gpkg` (E16).

## Dateibesitz (nicht gleichzeitig in beiden Sessions ändern)

| Bereich | Wer | Dateien |
| --- | --- | --- |
| Datenpipeline | macOS-Person | `urban_analysis/data_pipeline.py`, `urban_analysis/geometry.py`, `urban_analysis/mapping.py`, `urban_analysis/mapping_rules.json`, `urban_analysis/sources.py` und `urban_analysis/sources_catalog.json` (beide neu in Phase 2), `urban_analysis/osm_cache.py` (Niedersachsen-Cache, E35), `urban_analysis/accessibility.py` (Erreichbarkeit, E26/E34), `urban_analysis/source_matching.py` (Quellenabgleich, S12), `urban_analysis/topics.py` und `urban_analysis/topics_catalog.json` (allgemeine Kartenthemen, E36, geplant), `STATUS_DATENPIPELINE.md`, Tests `test_data_pipeline.py`, `test_geometry.py`, `test_mapping.py`, `test_sources.py`, `test_sources_catalog.py`, `test_alkis_vereinfacht.py`, `test_alkis_auftraege.py`, `test_columns.py`, `test_duplicate_groups.py`, `test_ziel_punkte.py`, `test_osm_cache.py`, `test_accessibility.py`, `test_source_matching.py`, `test_topics.py` (geplant) |
| Benutzerführung & Integration | Windows-Person | `urban_analysis/urban_analysis_plugin.py`, `urban_analysis/guided_dialog.py`, `urban_analysis/outputs.py`, `urban_analysis/user_guidance.py`, `urban_analysis/study_area.py`, `urban_analysis/theme.py`, `urban_analysis/osm_download.py`, `urban_analysis/map_styles.py`, `urban_analysis/icons/`, `urban_analysis/ui/**`, Tests `test_plugin_menu.py`, `test_user_guidance.py`, `test_outputs.py`, `test_study_area.py`, `test_theme.py`, `test_data_loading.py`, `test_review_step.py`, `test_mapping_step.py`, `test_harmonization_step.py`, `test_result_layers.py`, `test_summary_step.py`, `test_pixel_motion.py`, `test_scene.py`, `test_layer_icons.py`, `test_style_switch.py`, `test_osm_download.py`, `test_source_choice.py`, `test_more_info.py`, `test_map_styles.py`, `test_columns_step.py` |
| Gemeinsam (nur nach Absprache, eigener PR) | beide | `urban_analysis/contracts.py`, `urban_analysis/ui_contract.py`, `metadata.txt`, `CLAUDE.md`, `PLAN.md`, `ARBEITSPLAN*.md`, `.gitignore`, `tests/test_contracts.py`, `tests/test_plugin_integration.py` |

`tests/test_data_loading.py` nutzt Hilfsfunktionen aus
`tests/test_data_pipeline.py` nur lesend.

Wenn eine Änderung eine Datei des anderen Bereichs oder eine gemeinsame Datei
erfordert: anhalten und nachfragen, statt sie selbst zu ändern.

## Git-Workflow

- Nie direkt auf `main` arbeiten. Start: `git switch main && git pull`, dann
  eigenen Feature-Branch anlegen oder wechseln.
- Kleine, thematisch getrennte Commits; Push und Pull Request erst nach
  Rückfrage. Die andere Person prüft den PR vor dem Merge.
- Merge-Konflikte nie durch Weglassen einer Seite lösen; im Zweifel stoppen
  und im Team klären.

## Plugin-ZIP für den manuellen QGIS-Test

`metadata.txt` und `__init__.py` müssen direkt im Plugin-Ordner liegen;
keine `__MACOSX`-, `.DS_Store`- oder `__pycache__`-Einträge.

## Offene Entscheidungen

Siehe `PLAN.md` §6. Getroffene Entscheidungen hier kurz nachtragen.

## Getroffene Entscheidungen

- **Räumlicher Zuschnitt QGIS-frei (2026-11-17):** `data_pipeline.py` bleibt
  ohne QGIS-API testbar. Zuschnitt und Puffer werden in reinem Python aus den
  GeoPackage-Geometrien (WKB) berechnet, ohne externe Pakete wie shapely oder
  pyproj, da diese in QGIS nicht überall vorhanden sind.
  - Ein Objekt gehört dazu, wenn sein Abstand zum Untersuchungsgebiets-Polygon
    höchstens dem Puffer entspricht (nicht nur das umgebende Rechteck).
  - Keine Umprojektion in der Pipeline: Weicht das CRS einer Quelle vom
    Projekt-CRS ab, wird das als sichtbarer Fehler gemeldet und nicht still
    verglichen.
  - Objekte ohne lesbare Geometrie werden nicht still übernommen, sondern als
    Prüfhinweis gemeldet.
  - Die Benutzerführung liefert das Untersuchungsgebiet als WKT im Projekt-CRS
    an die Pipeline (z. B. aus einem in QGIS gewählten Polygon).
- **Phase 2 – deutschlandweit mit OSM und ALKIS (2026-11-18):** Die Regel
  „Download erst nach der MVP-Abnahme“ entfällt (E5). Alle Entscheidungen
  E5–E19 stehen in `ARBEITSPLAN_DEUTSCHLANDWEIT.md` §2. Kurz:
  - ALKIS automatisch von Landesdiensten, wo frei nutzbar; sonst nur OSM mit
    deutlichem Hinweis (E6). Eigene Dateien, auch eigene ALKIS-Exporte, bleiben
    möglich (E10, E16).
  - Bei gleichen Objekten aus ALKIS und OSM wählt die Nutzerin je Kategorie
    die Quelle; das Plugin schlägt einen Vorrang vor (E7, E19).
  - Gebiet + Puffer: Warnung über 25 km², kein Download über 50 km²; Größe
    schon in Schritt 2 sichtbar (E13 geändert am 18.11.2026, E17).
  - Umprojektion (z. B. OSM aus EPSG:4326) passiert in QGIS vor der Pipeline;
    die Pipeline selbst projiziert weiterhin nicht um.
- **Beschlüsse vom 2026-11-19 (Etappe F):** E29–E35 in
  `ARBEITSPLAN_DEUTSCHLANDWEIT.md` §2. Zuerst testen wir alles in QGIS; ob
  und wann ein Feature Freeze gilt, entscheiden wir danach. Kurz:
  - Ergebnis-Layer haben wenige Kernfelder plus alle bekannten
    Originalspalten mit lesbarem Namen; unbekannte Spalten sind zuschaltbar
    und werden in einem Hinweis genannt (E29, E30, G11).
  - Das Bundesland für ALKIS wählt die Nutzerin von Hand (E11 geändert).
  - Scheitert Overpass, springt der Niedersachsen-Cache ein, wenn das Gebiet
    ganz darin liegt – immer mit sichtbarem Hinweis (E35).
  - ALKIS-WFS liefern höchstens 10 000 Objekte je Abfrage: Download in
    Kacheln von etwa 1 km, Zusammenfügen über die Objekt-ID (M10b).
