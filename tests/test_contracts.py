"""Focused checks for the shared data and UI contracts."""

from urban_analysis.contracts import (
    MVP_DEFAULT_BUFFER_METERS,
    AttributeSuggestion,
    LayerDescriptor,
    PipelineResult,
)
from urban_analysis.ui_contract import MVP_REQUIRED_TOPIC_SUGGESTIONS, validate_ui_step_order


def test_default_buffer_and_selected_layers():
    result = PipelineResult(
        contract_version="1.0",
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON EMPTY",
        layers=[
            LayerDescriptor("buildings", "Buildings", "Polygon", "sample.gpkg", selected_for_topic=True),
            LayerDescriptor("roads", "Roads", "LineString", "sample.gpkg"),
        ],
    )

    assert result.buffer_meters == MVP_DEFAULT_BUFFER_METERS
    assert [layer.layer_id for layer in result.selected_layers()] == ["buildings"]


def test_ui_contract_is_stable():
    assert validate_ui_step_order(
        (
            "Projekt-CRS",
            "Untersuchungsgebiet",
            "Daten laden",
            "Layer prüfen",
            "Attributzuordnung",
            "Harmonisierung",
            "Kartenthema",
            "Ausgabe",
            "Verarbeitung starten",
        )
    )
    assert "Gebäude" in MVP_REQUIRED_TOPIC_SUGGESTIONS


def test_attribute_suggestion_knows_its_layer_and_examples():
    old_style = AttributeSuggestion("type", "object_type", 0.9)
    assert old_style.layer_id is None
    assert old_style.examples == ()

    suggestion = AttributeSuggestion(
        "gfk__bez", "object_type", 1.0, layer_id="gebaeude", examples=("Wohngebäude", "Garage")
    )
    assert suggestion.layer_id == "gebaeude"
    assert suggestion.examples == ("Wohngebäude", "Garage")
