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


# --- G13: Kartenthemen (E36, S16) -------------------------------------------

from urban_analysis.contracts import (  # noqa: E402
    TOPIC_CLASS_EMPTY,
    TOPIC_GEOMETRIES,
    TOPIC_LIMIT,
    TopicClass,
    TopicInfo,
    TopicScale,
    TopicSelection,
    TopicStep,
)
from urban_analysis.data_pipeline import HarmonizedRecord  # noqa: E402
from urban_analysis.ui_contract import TOPIC_LABELS, TOPIC_NAMES  # noqa: E402


def test_seven_general_topics_with_readable_names():
    assert list(TOPIC_NAMES) == [
        "bebauung", "nutzungen", "versorgung", "freiraum",
        "mobilitaet", "gruen_wasser_klima", "geschichte_stadtbild",
    ]
    assert TOPIC_NAMES["bebauung"] == "Bebauung & Stadtstruktur"
    assert TOPIC_LABELS["uncertain"] == "vermutlich"
    assert TOPIC_LIMIT == "topic-limit" and TOPIC_CLASS_EMPTY == "topic-class-empty"


def test_topic_info_with_classes_scales_limits_and_tips():
    topic = TopicInfo(
        "nutzungen",
        TOPIC_NAMES["nutzungen"],
        description="Wofür Gebäude und Flächen genutzt werden.",
        classes=(
            TopicClass("wohnen", "Wohnen", "Fläche", colour="#e8b04b"),
            TopicClass("eg_nutzung", "Erdgeschossnutzung", "Punkt", uncertain=True),
        ),
        scales=(
            TopicScale("geschosse", "Geschosszahl", "floors", steps=(
                TopicStep("1–2", 1, 3), TopicStep("3–5", 3, 6), TopicStep("ab 6", 6, None),
            )),
        ),
        limits=("Leerstand steht kaum in OSM.",),
        source_tips=("Gewerbemeldungen der Stadt als Eigene Datei.",),
    )

    assert topic.class_by_id("wohnen").colour == "#e8b04b"
    assert topic.class_by_id("eg_nutzung").uncertain
    assert topic.class_by_id("fehlt") is None
    assert topic.scales[0].steps[2].upper is None  # open upper end
    assert set(TOPIC_GEOMETRIES) == {"Fläche", "Linie", "Punkt"}


def test_topic_class_rejects_unknown_geometry():
    with pytest.raises(ValueError):
        TopicClass("wohnen", "Wohnen", "Polygon")


def test_topic_selection_needs_a_topic_and_one_class_or_step():
    selection = TopicSelection("mobilitaet", class_ids=["radwege", "haltestellen"])
    assert selection.class_ids == ("radwege", "haltestellen")
    assert TopicSelection("bebauung", scale_ids=["geschosse"]).scale_ids == ("geschosse",)
    with pytest.raises(ValueError):
        TopicSelection("mobilitaet")
    with pytest.raises(ValueError):
        TopicSelection("", class_ids=("radwege",))


def test_result_and_records_carry_the_chosen_topics():
    result = PipelineResult("1.0", "EPSG:25832", "POLYGON ((0 0, 1 0, 1 1, 0 0))")
    assert result.selected_topics == [] and result.as_summary()["selected_topics"] == []

    result.selected_topics = [
        TopicSelection("nutzungen", ("wohnen",)),
        TopicSelection("freiraum", ("parks",)),  # overlaid in one map
    ]
    assert result.as_summary()["selected_topics"] == ["nutzungen", "freiraum"]

    record = HarmonizedRecord("gebaeude", 1, {"category": "Gebäude"})
    assert record.topic_classes == {}  # old code keeps working
    cafe = HarmonizedRecord("punkte", 2, {}, topic_classes={"nutzungen": "gastronomie", "freiraum": "treffpunkte"})
    assert cafe.topic_classes["freiraum"] == "treffpunkte"  # one object, several topics
