"""Vertretung Mac (19.11.2026): buildings from ALKIS and OSM become one
result layer „Gebäude“ (``combine_source_layers`` from #61, used in step 9).
QGIS-free parts of guided_dialog.py."""

import copy

from urban_analysis.contracts import LayerDescriptor, PipelineResult
from urban_analysis.data_pipeline import HarmonizedRecord
from urban_analysis.guided_dialog import ReadableNames, planned_layer_rows, shown_result
from urban_analysis.user_guidance import GuidedWorkflow


def two_sources():
    return PipelineResult(
        contract_version="1.0",
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
        layers=[
            LayerDescriptor("gebaeude", "gebaeude", "MULTIPOLYGON", "alkis.gpkg", category="Gebäude",
                            selected_for_topic=True, source_kind="ALKIS"),
            LayerDescriptor("multipolygons_gebaeude", "Gebäude", "MULTIPOLYGON", "osm.gpkg",
                            category="Gebäude", selected_for_topic=True, source_kind="OSM"),
            LayerDescriptor("lines_strassen", "Straßen", "MULTILINESTRING", "osm.gpkg",
                            category="Straßen", selected_for_topic=True, source_kind="OSM"),
        ],
        harmonized_records=[
            HarmonizedRecord("gebaeude", 1, {"object_id": "a1", "category": "Gebäude"}),
            HarmonizedRecord("gebaeude", 2, {"object_id": "a2", "category": "Gebäude"}),
            HarmonizedRecord("multipolygons_gebaeude", 3, {"object_id": "way/3", "category": "Gebäude"}),
            HarmonizedRecord("lines_strassen", 4, {"object_id": "way/4", "category": "Straßen"}),
        ],
    )


NAMES = ReadableNames(layer={"gebaeude": "Gebäude"}.get)


def test_buildings_from_alkis_and_osm_are_one_layer():
    result = two_sources()
    before = copy.deepcopy(result)

    shown = shown_result(result)

    buildings = [layer for layer in shown.layers if layer.category == "Gebäude"]
    assert len(buildings) == 1 and buildings[0].selected_for_topic
    assert buildings[0].source_kind == ""
    building_records = [r for r in shown.harmonized_records if r.attributes["category"] == "Gebäude"]
    assert {r.layer_id for r in building_records} == {buildings[0].layer_id}
    assert {r.attributes["object_id"] for r in building_records} == {"a1", "a2", "way/3"}
    assert [layer.layer_id for layer in shown.layers if layer.category == "Straßen"] == ["lines_strassen"]
    assert result == before  # steps 4–6 keep the layers per source


def test_step_9_plans_one_building_layer():
    planned = planned_layer_rows(GuidedWorkflow(two_sources()), NAMES)
    rows = [row[1] for row in planned]
    assert rows == ["Gebäude – 3 Objekte", "Straßen – 1 Objekt"]
    assert planned[0][2] == "gebaeude"  # layer icon


def test_one_source_stays_as_it_is():
    result = two_sources()
    result.layers = result.layers[:1]
    result.harmonized_records = result.harmonized_records[:2]
    shown = shown_result(result)
    assert [layer.layer_id for layer in shown.layers] == ["gebaeude"]
    assert [r.layer_id for r in shown.harmonized_records] == ["gebaeude", "gebaeude"]
