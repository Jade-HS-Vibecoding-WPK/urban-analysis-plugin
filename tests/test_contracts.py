"""Focused checks for the shared data and UI contracts."""

import pytest

from urban_analysis.contracts import (
    CORE_FIELDS,
    MVP_DEFAULT_BUFFER_METERS,
    AttributeSuggestion,
    ColumnDecision,
    ColumnInfo,
    DuplicateGroupInfo,
    LayerDescriptor,
    PipelineResult,
    ValidationIssue,
    ValueDifference,
)
from urban_analysis.data_pipeline import TARGET_FIELDS
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


# --- G11: columns, hints and duplicates (E29–E31) ---


def test_core_fields_are_target_fields_of_the_pipeline():
    assert set(CORE_FIELDS) <= set(TARGET_FIELDS)
    assert "category" in CORE_FIELDS and "object_id" in CORE_FIELDS


def test_new_fields_are_optional_so_old_code_keeps_working():
    issue = ValidationIssue("crs", "Anderes KBS")
    assert (issue.details, issue.action, issue.layer_id) == ("", "", None)
    layer = LayerDescriptor("gebaeude", "Gebäude", "Polygon", "a.gpkg")
    assert layer.source_kind == ""
    result = PipelineResult("1.0", "EPSG:25832", "POLYGON EMPTY")
    assert result.columns == [] and result.duplicate_groups == []


def test_issue_with_short_text_action_and_details():
    issue = ValidationIssue(
        "uncertain-duplicate",
        "An 3 Stellen liegen Gebäude genau übereinander.",
        action="In Schritt 6 entscheiden.",
        details="Gleiche Form, aber unterschiedliche Nutzung.",
        layer_id="gebaeude",
    )
    assert issue.action and issue.details and issue.layer_id == "gebaeude"


def test_columns_of_one_layer_keep_the_source_order():
    result = PipelineResult(
        "1.0",
        "EPSG:25832",
        "POLYGON EMPTY",
        columns=[
            ColumnInfo("gebaeude", "hnr", "Hausnummer", known=True, examples=("2", "4a")),
            ColumnInfo("strassen", "name", "Name", known=True),
            ColumnInfo("gebaeude", "xyz_intern", examples=("17",)),
            ColumnInfo("gebaeude", "gfk__bez", "Gebäudefunktion", True, suggested_target="object_type", confidence=1.0),
        ],
    )
    columns = result.columns_of("gebaeude")
    assert [column.source_field for column in columns] == ["hnr", "xyz_intern", "gfk__bez"]
    assert [column.known for column in columns] == [True, False, True]
    assert columns[2].suggested_target == "object_type"


def test_column_decisions():
    assert ColumnDecision("gebaeude", "gfk__bez", "target", target_field="object_type").target_field == "object_type"
    assert ColumnDecision("gebaeude", "hnr", "keep", name="Hausnr.").name == "Hausnr."
    assert ColumnDecision("gebaeude", "xyz_intern", "drop").action == "drop"


@pytest.mark.parametrize(
    "action, target",
    [("behalten", ""), ("target", ""), ("target", "floors")],
)
def test_column_decision_rejects_unknown_actions_and_non_core_targets(action, target):
    with pytest.raises(ValueError):
        ColumnDecision("gebaeude", "hnr", action, target_field=target)


def test_duplicate_group_explains_itself():
    group = DuplicateGroupInfo(
        "gebaeude:1",
        "gebaeude",
        2,
        reason="gleiche Form",
        example_text="Ein Gebäude ist zweimal eingetragen: einmal als Wohnen, einmal als Gewerbe.",
        differences=(ValueDifference("nutzung", "Nutzung", ("Wohnen", "Gewerbe")),),
    )
    assert group.differences[0].readable_name == "Nutzung"
    assert group.differences[0].values == ("Wohnen", "Gewerbe")
