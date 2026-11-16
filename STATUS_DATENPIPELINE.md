# Aktueller Stand der Datenpipeline

## Branch und Synchronisation

Die Implementierung wurde ausschließlich auf dem Branch `feature/datenpipeline`
entwickelt. Der Branch ist mit
`origin/feature/datenpipeline` synchronisiert und wurde erfolgreich auf GitHub
gepusht.

## Implementierter Funktionsumfang

Die Datenpipeline unterstützt aktuell:

- Import lokaler GeoPackage-Dateien über die GeoPackage-SQLite-Metadaten
- Erkennung von Feature-Layern und Geometrietypen
- Übernahme und Prüfung des Projekt-CRS
- Definition eines Untersuchungsgebiets über WKT
- Räumliche Begrenzung über das Untersuchungsgebiet mit konfigurierbarem Puffer
- Standardpuffer von 500 Metern
- Erkennung und Vorschlag fachlicher Kategorien
- Automatisches Attributmapping mit sichtbarer Konfidenz
- Harmonisierung in ein gemeinsames Zielschema
- Erkennung und Entfernung exakter Duplikate
- Sichtbare Prüfhinweise über `ValidationIssue`
- Übergabe harmonisierter Datensätze über `PipelineResult`

Das gemeinsame Zielschema umfasst:

```text
source_name
object_type
category
status
area_m2
year
source
```

## Mapping des getesteten Oldenburg-Datensatzes

Für das getestete GeoPackage wurden folgende Regeln ergänzt:

| Quellfeld | Zielfeld | Beispielwert |
| --- | --- | --- |
| `ken__bez` | `object_type` | `Turm` |
| `bwf__bez` | `category` | `Kirchturm, Glockenturm` oder `Wasserturm` |
| `untermerkmal` | `status` | `xxx` |

Die Spalte `wkt_geom` wird als Geometriespalte erkannt.

## Teststatus

Der Import wurde in der QGIS-Python-Konsole mit dem GeoPackage
`lkr_03403_Stadt_Oldenburg_kon.gpkg` erfolgreich ausgeführt. Dabei wurden
harmonisierte Datensätze mit den erwarteten Werten für Objektart, Kategorie und
Status erzeugt.

Die lokale `pytest`-Ausführung wurde wegen einer inkompatiblen, sehr alten
Python-3.10-Alpha-Umgebung nicht verwendet. Syntaxprüfungen, direkte
Pipeline-Smoke-Tests sowie die CRS-, Validierungs- und Mapping-Prüfungen waren
erfolgreich.

## Geänderte Dateien

- `urban_analysis/data_pipeline.py`
- `urban_analysis/contracts.py`
- `tests/test_data_pipeline.py`

Die Dateien der Benutzerführung, insbesondere `urban_analysis/user_guidance.py`,
`urban_analysis/ui_contract.py` und `tests/test_user_guidance.py`, wurden nicht
geändert.

## Bekannte Einschränkungen

- `area_m2` und `year` bleiben leer, wenn die Quelldaten keine passenden Felder
  enthalten.
- Der Wert `xxx` wird als Status aus den Quelldaten übernommen und nicht
  automatisch als Platzhalter verändert.
- Die automatische Kategorieerkennung ordnet Layernamen wie `nutzung` und
  `gebaeude` anhand ihrer Bezeichnung der Kategorie `Gebäude` zu. Diese
  Zuordnung sollte fachlich noch geprüft werden.
- Die vollständige Benutzeroberfläche und die eigentliche QGIS-Layerausgabe
  gehören zum separaten Benutzerführungs-Branch.

## Commits

- `7c8fc2a` – `Implement GeoPackage data pipeline`
- `fb54dbf` – `Map source attributes during harmonization`

Dieser Statusbericht wird mit einem eigenen Commit auf
`feature/datenpipeline` veröffentlicht.
