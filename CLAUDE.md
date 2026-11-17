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
- Im MVP lädt der Nutzer eigene lokale GeoPackages. Der Download von
  OSM-/WMS-Daten aus dem Plugin ist eine spätere Erweiterung und wird erst
  nach der MVP-Abnahme umgesetzt.

## Dateibesitz (nicht gleichzeitig in beiden Sessions ändern)

| Bereich | Wer | Dateien |
| --- | --- | --- |
| Datenpipeline | macOS-Person | `urban_analysis/data_pipeline.py`, `tests/test_data_pipeline.py` |
| Benutzerführung & Integration | Windows-Person | `urban_analysis/urban_analysis_plugin.py`, `urban_analysis/guided_dialog.py`, `urban_analysis/outputs.py`, `urban_analysis/user_guidance.py`, zugehörige Tests |
| Gemeinsam (nur nach Absprache, eigener PR) | beide | `urban_analysis/contracts.py`, `urban_analysis/ui_contract.py`, `metadata.txt`, `CLAUDE.md`, `PLAN.md`, `.gitignore` |

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
