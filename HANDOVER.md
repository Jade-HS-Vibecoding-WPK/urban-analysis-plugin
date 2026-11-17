# Projektübergabe: Urban Analysis Plugin

## Ziel des Plugins

Das QGIS-Plugin unterstützt einen geführten Urban-Analysis-Workflow: GeoPackage-Daten
werden importiert, geprüft, harmonisiert und für erste Kartenthemen vorbereitet.
Die Benutzerführung soll Prüfhinweise, Attributzuordnungen, Kategorien und optionale
Ausgaben nachvollziehbar und bestätigbar machen.

## Technik

- **QGIS:** Zielversion mindestens 3.44; manuell getestet mit QGIS 3.44.15
  (Solothurn).
- **Python:** QGIS verwendet Python 3.12.11. Die lokale Testumgebung verwendet
  Python 3.10, ist aber wegen inkompatibler Test-Abhängigkeiten nicht vollständig
  geeignet.
- **Betriebssystem:** Entwicklung und manueller QGIS-Test auf macOS. Das Plugin
  ist als QGIS-Python-Plugin grundsätzlich für unterstützte QGIS-Systeme gedacht;
  Windows und Linux wurden bisher nicht manuell verifiziert.
- **Datenformat:** GeoPackage über SQLite-Metadaten und lokale Dateien.

## Dateistruktur des Plugins

```text
urban-analysis-plugin/
├── metadata.txt
├── __init__.py
├── urban_analysis/
│   ├── __init__.py
│   ├── contracts.py
│   ├── data_pipeline.py
│   ├── guided_dialog.py
│   ├── outputs.py
│   ├── ui_contract.py
│   ├── urban_analysis_plugin.py
│   └── user_guidance.py
└── tests/
    ├── test_contracts.py
    ├── test_data_pipeline.py
    ├── test_outputs.py
    ├── test_plugin_integration.py
    └── test_user_guidance.py
```

Zusätzliche Übergabe- und Statusdokumente liegen im Repository:
`INTEGRATION_HANDOFF.md`, `STATUS_DATENPIPELINE.md`, `PLAN.md` und `README.md`.

## Was funktioniert bereits

- GeoPackage-Import über lokale SQLite-Metadaten.
- Erkennung von Feature-Layern, Geometrietypen und Quell-CRS.
- Prüfung von Projekt-CRS, Untersuchungsgebiet und Puffer.
- Räumliche Begrenzung über das Untersuchungsgebiet mit Standardpuffer von 500 m.
- Erkennung fachlicher Kategorien und sichtbare Attribut-Mapping-Vorschläge.
- Harmonisierung in das gemeinsame Schema:
  `source_name`, `object_type`, `category`, `status`, `area_m2`, `year`, `source`.
- Erkennung und Entfernung exakter Duplikate.
- Übergabe der Ergebnisse über `PipelineResult`.
- Gemeinsame Benutzerführung mit neun MVP-Schritten:
  Projekt-CRS, Untersuchungsgebiet, Daten laden, Layer prüfen,
  Attributzuordnung, Harmonisierung, Kartenthema, Ausgabe und Verarbeitung.
- Bestätigbare Attributvorschläge und dynamische Kategorien.
- Auswahl eines Kartenthemas mit expliziter Bestätigung fehlender Kategorien.
- Planung optionaler GeoPackage- und PDF-Ausgaben.
- Die direkte Pipeline-/UI-Integration ist durch `UrbanAnalysisPlugin.start_workflow`
  und den gemeinsamen Vertrag grundsätzlich vorhanden.
- Der aktuelle lokale Fix fasst Duplikat-Warnungen pro Layer zusammen. Dadurch wird
  die QGIS-Seite „Layer prüfen“ nicht mehr durch tausende Einzelmeldungen überladen.

## Was gerade in Arbeit ist

- **Aktueller Branch:** `main`, synchron mit `origin/main` auf Commit `c78c4e6`.
- **Lokale Änderung:** `urban_analysis/data_pipeline.py` enthält einen noch nicht
  gepushten lokalen Fix für zusammengefasste Duplikat-Warnungen.
- **Offene UI-Funktion:** Der Menüeintrag startet den Assistenten erst, wenn ein
  `PipelineResult` über die QGIS-Python-Konsole übergeben wurde. Ein integrierter
  Datei-Auswahldialog und ein automatischer GeoPackage-Import aus der UI fehlen.
- **Offene QGIS-Ausgabe:** Die reale Zuordnung von `layer_id` zu QGIS-Layerobjekten
  und die vollständige Ausgabe in das QGIS-Projekt müssen noch mit echten QGIS-Layern
  verifiziert werden.
- **Testumgebung:** Der lokale Python-3.10-Testlauf hat eine inkompatible Kombination
  aus `typing_extensions`/`exceptiongroup`. Mit einem temporären Kompatibilitäts-Workaround
  bestehen 12 relevante Tests; ein bestehender Testfehler betrifft das Überschreiben
  einer absichtlich ungültigen SQLite-Datei im Test-Fixture.
- Die korrigierte ZIP-Datei muss nach dem lokalen Fix neu erstellt und in QGIS
  installiert werden.

## Getroffene Entscheidungen

- Datenpipeline und Benutzerführung kommunizieren über den versionierten
  `PipelineResult`-Vertrag.
- Rohdaten werden nicht überschrieben; bestätigte Ergebnisse werden separat
  weiterverarbeitet.
- Kategorien werden aus den Eingangsdaten vorgeschlagen und nicht fest in der UI
  vorausgesetzt.
- Unsichere Zuordnungen und fehlende Kategorien bleiben als sichtbare Prüfhinweise
  erhalten und werden nicht still korrigiert.
- Die Datenpipeline bleibt unabhängig von QGIS testbar, soweit dies ohne QGIS-API
  möglich ist.
- GeoPackage-Dateien werden über vorhandene SQLite-/GeoPackage-Metadaten gelesen.
- Lange oder blockierende QGIS-Berechnungen sollen bei einer späteren Erweiterung
  über `QgsTask` geprüft werden; eine asynchrone Umsetzung ist noch nicht vorhanden.

## Nächste Schritte

1. Den lokalen Duplikat-Warnungsfix entscheiden, committen und bei Bedarf nach
   `origin/main` pushen.
2. Die Plugin-ZIP aus dem gewünschten Stand ohne `__MACOSX`, `.DS_Store` und
   `__pycache__` neu erstellen.
3. Das Plugin in QGIS 3.44.15 neu installieren und den GeoPackage-Import über die
   Python-Konsole erneut testen.
4. Einen Datei-Auswahldialog und den automatischen Pipeline-Start in die
   Benutzerführung integrieren.
5. Den Workflow mit dem echten Oldenburg-GeoPackage vollständig durchlaufen:
   Import, Prüfhinweise, Attributbestätigung, Kartenthema und Ausgabe.
6. Die bestehende Test-Fixture für ungültige GeoPackage-Dateien korrigieren.
7. QGIS-spezifische Tests für echte Layerobjekte und Ausgabe in das Projekt ergänzen.
8. Die UI-Arbeit in einem separaten Feature-Branch fortsetzen, damit Pipeline- und
   UI-Änderungen unabhängig entwickelt und später zusammengeführt werden können.

## Regeln

- Bestehende Projektstruktur, gemeinsame Verträge und Benennungen beibehalten.
- Code-Stil und Formatierung an den vorhandenen Python-Dateien ausrichten.
- Keine stillen Fallbacks: Eingabefehler, ungültige Daten und fehlende Zuordnungen
  müssen sichtbar gemeldet werden.
- Änderungen möglichst klein und thematisch getrennt halten.
- Rohdaten nicht überschreiben.
- Nur PyQGIS-Methoden verwenden, die in **QGIS 3.44** tatsächlich vorhanden sind.
- QGIS-spezifischen Code von unabhängig testbarer Pipeline- und Vertragslogik
  trennen.
- Für lange Berechnungen keine blockierende UI-Logik ergänzen; vor der Umsetzung
  `QgsTask` und die QGIS-3.44-API prüfen.
- Vor dem manuellen QGIS-Test eine saubere ZIP-Struktur sicherstellen:
  `metadata.txt` und `__init__.py` müssen direkt im Plugin-Ordner liegen.
