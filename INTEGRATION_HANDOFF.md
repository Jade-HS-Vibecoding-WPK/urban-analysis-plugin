# Integrationsübergabe: Datenpipeline und Benutzerführung

## Aktueller Stand

Der Branch `feature/benutzerfuehrung` enthält:

- einen QGIS-Assistenten mit den neun MVP-Schritten,
- Eingaben für Projekt-CRS, Untersuchungsgebiet und Puffer,
- sichtbare Prüfhinweise,
- bestätigbare und änderbare Attributvorschläge,
- dynamische Kartenthemen und Kategorien,
- eine explizite Bestätigung für fehlende Zielkategorien,
- QGIS-Layer-Ausgabe,
- optionalen GeoPackage-Export,
- einen minimalen PDF-Export mit Untersuchungsgebiet, Puffer, Legende und Datenquelle.

Der Assistent wurde in QGIS 3.44 mit einem Testdatensatz manuell durchlaufen.
Die automatisierten Tests bestehen. Die echte Datenpipeline ist noch nicht an
den Assistenten angeschlossen.

## Übergabeschnittstelle

Die Datenpipeline übergibt ein `PipelineResult`:

```python
from urban_analysis.contracts import PipelineResult

result = PipelineResult(
    contract_version="1.0",
    project_crs="EPSG:25832",
    study_area_wkt="POLYGON ((...))",
    buffer_meters=500,
    layers=[],
    attribute_suggestions=[],
    issues=[],
)
```

### Pflichtfelder

| Feld | Typ | Bedeutung |
| --- | --- | --- |
| `contract_version` | `str` | Version des gemeinsamen Datenvertrags |
| `project_crs` | `str` | Vorausgewähltes oder ermitteltes Projekt-CRS |
| `study_area_wkt` | `str` | Untersuchungsgebiet als Polygon in WKT |
| `layers` | `list[LayerDescriptor]` | Geladene und geprüfte Layer |
| `attribute_suggestions` | `list[AttributeSuggestion]` | Sichtbare Mapping-Vorschläge |
| `issues` | `list[ValidationIssue]` | Prüfhinweise, Warnungen und offene Probleme |

`buffer_meters` ist optional und verwendet standardmäßig `500`.

## Layerbeschreibung

Für jeden Layer wird ein `LayerDescriptor` benötigt:

```python
LayerDescriptor(
    layer_id="buildings",
    name="Gebäude",
    geometry_type="Polygon",
    source_name="donnerschwee.gpkg",
    category="Gebäude",
)
```

Wichtige Regeln:

- `layer_id` muss innerhalb des Ergebnisses eindeutig sein.
- `category` enthält die von der Pipeline vorgeschlagene fachliche Kategorie.
- Die Kategorien werden nicht fest vorgegeben. Die Benutzerführung zeigt die
  erkannten Kategorien zur Bestätigung an.
- `selected_for_topic` wird erst nach der Themenauswahl durch die
  Benutzerführung gesetzt.
- Rohdaten dürfen nicht überschrieben werden.

## Attributvorschläge

```python
AttributeSuggestion(
    source_field="type",
    target_field="object_type",
    confidence=0.9,
)
```

Die Pipeline liefert Vorschläge. Sie darf sie nicht als endgültige Zuordnung
behandeln. Die Benutzerführung kann `accepted` und `user_value` nach der
Bestätigung oder Änderung aktualisieren.

## Prüfhinweise

```python
ValidationIssue(
    code="missing-topic-category",
    message="Nutzungsflächen fehlen",
    severity="warning",
    requires_confirmation=True,
    rule="MVP-Zielkategorien",
)
```

Prüfhinweise müssen nachvollziehbar bleiben. Unsichere Fälle dürfen nicht
still korrigiert werden. Fehlende Kartenthema-Kategorien werden nach einer
bewussten Bestätigung als Warnung in der Zusammenfassung erhalten.

## Übergabe an den Workflow

Der Plugin-Einstiegspunkt erstellt die Benutzerführung:

```python
from urban_analysis.urban_analysis_plugin import UrbanAnalysisPlugin

plugin = UrbanAnalysisPlugin(iface)
workflow = plugin.start_workflow(result)
```

Der QGIS-Assistent kann anschließend über die Plugin-Aktion geöffnet werden.
Für die Integration soll die Pipeline den `PipelineResult` an den vorhandenen
Workflow übergeben, statt eigene UI- oder Exportlogik zu implementieren.

## Ausgabe nach der Bestätigung

Die Benutzerführung erzeugt einen `OutputPlan`:

```python
plan = workflow.output_plan()
```

Der Plan enthält:

- `qgis_layer_ids`: bestätigte Layer-IDs,
- `geopackage_requested`: Auswahl der optionalen GeoPackage-Ausgabe,
- `pdf_requested`: Auswahl der optionalen PDF-Ausgabe,
- `pdf_metadata`: Untersuchungsgebiet, Puffer, Legende und Datenquelle bei
  aktivierter PDF-Ausgabe.

Für reale QGIS-Ausgaben benötigt das Plugin zusätzlich eine Zuordnung von
Layer-IDs zu den echten QGIS-Layerobjekten:

```python
layer_objects = {
    "buildings": buildings_qgis_layer,
    "roads": roads_qgis_layer,
}

plugin.export_outputs(
    layer_objects=layer_objects,
    geopackage_path=r"C:\Temp\bereinigt.gpkg",
    pdf_path=r"C:\Temp\siedlungsstruktur.pdf",
)
```

`layer_objects` darf nur bestätigte Ergebnislayer enthalten oder muss
mindestens alle ausgewählten `layer_id`-Werte auflösen können. Die Eingabelayer
bleiben in QGIS erhalten; die Ausgabe lädt nur die thematisch bestätigten
Ergebnislayer.

## Noch nicht Bestandteil der Übergabe

- Automatisches Laden von GeoPackage-Dateien durch die Benutzerführung
- Erzeugung oder Validierung der Pipeline-Ergebnisse
- reale Geometrieprüfung im Dialog
- grafischer QGIS-Kartenexport im PDF
- weitere Kartenthemen oder externe Datenquellen

Diese Punkte gehören zur Datenpipeline oder zu späteren Erweiterungen und
werden nicht stillschweigend in die Benutzerführung integriert.
