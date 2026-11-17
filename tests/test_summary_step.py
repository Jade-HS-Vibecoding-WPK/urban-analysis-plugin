"""W8 part 1: readable overview and result list in step 9 (QGIS-free parts)."""

from urban_analysis.contracts import LayerDescriptor, OutputSelection, PipelineResult, ValidationIssue
from urban_analysis.data_pipeline import HarmonizedRecord
from urban_analysis.guided_dialog import (
    ReadableNames,
    format_hectares,
    output_rows,
    overview_rows,
    planned_layer_rows,
    result_rows,
)
from urban_analysis.outputs import ResultLayerReport
from urban_analysis.user_guidance import GuidedWorkflow


def make_workflow():
    flow = GuidedWorkflow(
        PipelineResult(
            contract_version="1.0",
            project_crs="EPSG:25832",
            study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
            buffer_meters=500,
            layers=[
                LayerDescriptor("gebaeude", "gebaeude", "MULTIPOLYGON", "lkr.gpkg", category="Gebäude",
                                selected_for_topic=True),
                LayerDescriptor("nutzung_strassen", "nutzung – Straßen", "MULTIPOLYGON", "lkr.gpkg",
                                category="Straßen", selected_for_topic=True),
                LayerDescriptor("flurstuecke", "flurstuecke", "MULTIPOLYGON", "lkr.gpkg"),
            ],
            issues=[ValidationIssue("missing-data-source", "x"), ValidationIssue("clip-summary", "y", severity="info")],
            selected_topic="Siedlungsstruktur",
            output=OutputSelection(create_pdf=True, data_source="ALKIS"),
            harmonized_records=[HarmonizedRecord("gebaeude", i, {}) for i in range(1200)]
            + [HarmonizedRecord("nutzung_strassen", 1, {})],
        )
    )
    flow.duplicate_decisions = {"gebaeude": False, "nutzung": True}
    return flow


NAMES = ReadableNames(layer={"gebaeude": "Gebäude", "nutzung": "Nutzung"}.get)


def test_overview_shows_facts_instead_of_coordinates():
    rows = dict(overview_rows(make_workflow(), 1234.56, NAMES))
    assert rows["Untersuchungsgebiet"] == "1 234,6 ha"
    assert rows["Puffer"] == "500 m"
    assert rows["Datei"] == "lkr.gpkg"
    assert rows["Datenquelle"] == "ALKIS"
    assert rows["Unsichere Dubletten"] == "Gebäude behalten, Nutzung zusammengeführt"
    assert rows["Hinweise aus Schritt 4"] == "1 Warnung(en)"
    assert "POLYGON" not in str(rows)


def test_planned_layers_list_only_selected_layers_with_counts():
    planned = planned_layer_rows(make_workflow(), NAMES)
    assert [row[2] for row in planned] == ["gebaeude", "strassen"]  # layer icons
    rows = [row[1] for row in planned]
    assert rows == ["Gebäude – 1 200 Objekte", "Straßen – 1 Objekt"]


def test_outputs_say_what_is_not_connected_yet():
    rows = dict(output_rows(OutputSelection(create_pdf=True)))
    assert rows["Ergebnis-Layer in QGIS"] == "ja"
    assert rows["Bereinigtes GeoPackage"] == "nein"
    assert rows["PDF"].startswith("ja (wird mit W8")


def test_result_rows_list_created_layers_and_skipped_objects():
    report = ResultLayerReport("gebaeude", "Gebäude", feature_count=18930)
    report.skip("ohne Geometrie")
    created = result_rows([report], {"gebaeude": "Gebäude"})
    assert created[0][2] == "gebaeude"  # layer icon
    rows = [row[1] for row in created]
    assert rows == ["Gebäude – 18 930 Objekte", "Gebäude: 1 nicht übernommen (ohne Geometrie)"]


def test_hectares_with_german_comma():
    assert format_hectares(81.0) == "81,0"
