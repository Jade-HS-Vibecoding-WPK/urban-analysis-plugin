import pytest

from urban_analysis.contracts import (
    AttributeSuggestion,
    LayerDescriptor,
    PipelineResult,
)
from urban_analysis.user_guidance import GuidedWorkflow


def make_result():
    return PipelineResult(
        contract_version="1.0",
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
        layers=[
            LayerDescriptor("b", "Gebäude", "Polygon", "input.gpkg", category="Gebäude"),
            LayerDescriptor("r", "Straßen", "LineString", "input.gpkg", category="Straßen"),
        ],
        attribute_suggestions=[
            AttributeSuggestion("type", "object_type", 0.9),
        ],
    )


def test_guidance_confirms_mapping_and_selects_dynamic_categories():
    workflow = GuidedWorkflow(make_result())

    workflow.configure_project(
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
        buffer_meters=250,
    )
    workflow.confirm_attribute_suggestions({"type": "building_type"})
    selected = workflow.select_topic(
        "Siedlungsstruktur",
        categories=("Gebäude", "Straßen"),
    )

    assert workflow.attribute_suggestions()[0].user_value == "building_type"
    assert [layer.layer_id for layer in selected] == ["b", "r"]
    assert workflow.result.issues == []
    assert workflow.result.buffer_meters == 250


def test_project_setup_rejects_invalid_buffer_and_exposes_contract_steps():
    workflow = GuidedWorkflow(make_result())

    assert workflow.current_step == "Projekt-CRS"
    assert workflow.advance() == "Untersuchungsgebiet"
    with pytest.raises(ValueError, match="darf nicht negativ sein"):
        workflow.configure_project(
            project_crs="EPSG:25832",
            study_area_wkt="POLYGON EMPTY",
            buffer_meters=-1,
        )


def test_topic_needs_no_fixed_categories_any_more():
    # W19: 'Mobilität' without Grünflächen/Nutzungsflächen is fine
    workflow = GuidedWorkflow(make_result())

    selected = workflow.select_topic("Mobilität", categories=("Straßen",))

    assert [layer.layer_id for layer in selected] == ["r"]
    assert workflow.result.issues == []


def test_topic_needs_at_least_one_category():
    workflow = GuidedWorkflow(make_result())

    with pytest.raises(ValueError, match="keine Kategorie angehakt") as error:
        workflow.select_topic("Mobilität", categories=())

    assert "Was tun" in str(error.value)


def test_preselection_follows_the_topic_and_the_data(monkeypatch):
    import urban_analysis.topics as topics

    suggestions = {
        "Mobilität": ("Straßen", "ÖPNV-Haltestellen"),
        "Leer": ("Bahnstrecken",),
    }

    def fake(topic, path=None):
        if topic not in suggestions:
            raise ValueError(f"Unbekanntes Thema: {topic}")
        return suggestions[topic]

    monkeypatch.setattr(topics, "topic_categories", fake)
    workflow = GuidedWorkflow(make_result())

    # only categories that are in the data
    assert workflow.topic_preselection("Mobilität") == ("Straßen",)
    assert workflow.topic_preselection("Leer") == ()
    assert workflow.topic_preselection("Unbekannt") is None


def test_preselection_from_the_real_catalogue():
    workflow = GuidedWorkflow(make_result())

    assert workflow.topic_preselection("Mobilität & Erschließung") == ("Gebäude", "Straßen")
    # names from the catalogue = names in the step-7 list
    from urban_analysis.guided_dialog import topic_entries

    for name, _description in topic_entries():
        assert workflow.topic_preselection(name) is not None


def test_output_plan_keeps_qgis_layers_and_describes_optional_exports():
    workflow = GuidedWorkflow(make_result())
    workflow.select_topic(
        "Siedlungsstruktur",
        categories=("Gebäude", "Straßen"),
    )
    workflow.choose_output(
        save_cleaned_geopackage=True,
        create_pdf=True,
        data_source="OpenStreetMap, 2026-01",
    )

    plan = workflow.output_plan()

    assert plan.qgis_layer_ids == ("b", "r")
    assert plan.geopackage_requested is True
    assert plan.pdf_metadata["buffer_meters"] == 500
    assert plan.pdf_metadata["legend"] == ["Gebäude", "Straßen"]


def test_pdf_requires_editable_data_source():
    workflow = GuidedWorkflow(make_result())

    with pytest.raises(ValueError, match="Datenquelle"):
        workflow.choose_output(create_pdf=True)


def test_empty_target_field_explains_how_to_fix_it():
    workflow = GuidedWorkflow(make_result())

    with pytest.raises(ValueError, match="kein Zielfeld eingetragen") as error:
        workflow.confirm_attribute_suggestions({"type": "  "})

    assert "Häkchen entfernen" in str(error.value)
