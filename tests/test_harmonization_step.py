"""Step 6 'Harmonisierung' (ARBEITSPLAN W5, part 2): uncertain duplicates per layer."""

import pytest

from urban_analysis.contracts import LayerDescriptor, PipelineResult, ValidationIssue
from urban_analysis.data_pipeline import HarmonizedRecord
from urban_analysis.guided_dialog import (
    cross_layer_warning_text,
    duplicate_title_text,
    duplicates_applied_text,
    merge_hint_text,
    more_groups_text,
)
from urban_analysis.user_guidance import GuidedWorkflow, describe_group, issue_table_name


def record(layer_id, row, group=None, **attributes):
    return HarmonizedRecord(layer_id, row, {"object_type": "Wohngebäude", **attributes},
                            duplicate_group=group)


def make_workflow():
    records = [
        record("gebaeude", 1, "gebaeude:1"),
        record("gebaeude", 2, "gebaeude:1", status="Hausnr. 5"),
        record("gebaeude", 3, "gebaeude:2"),
        record("gebaeude", 4, "gebaeude:2"),
        record("gebaeude", 5),
        record("nutzung_strassen", 6, "nutzung:1", object_type="Straßenverkehr"),
        record("nutzung_fuss_radwege", 7, "nutzung:1", object_type="Weg"),
        record("nutzung_gruen", 8),
    ]
    return GuidedWorkflow(
        PipelineResult(
            contract_version="1.0",
            project_crs="EPSG:25832",
            study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
            layers=[LayerDescriptor("gebaeude", "gebaeude", "Polygon", "a.gpkg", category="Gebäude")],
            issues=[
                ValidationIssue("uncertain-duplicate", "gebaeude: 2 Gruppe(n) ...", requires_confirmation=True),
                ValidationIssue("uncertain-duplicate", "nutzung: 1 Gruppe(n) ...", requires_confirmation=True),
            ],
            harmonized_records=records,
        )
    )


def test_groups_are_collected_per_input_layer_with_counts():
    layers = {layer.table_name: layer for layer in make_workflow().duplicate_layers()}
    assert set(layers) == {"gebaeude", "nutzung"}
    assert (layers["gebaeude"].group_count, layers["gebaeude"].record_count) == (2, 4)
    assert layers["gebaeude"].removable_count == 2


def test_groups_split_over_result_layers_are_detected():
    layers = {layer.table_name: layer for layer in make_workflow().duplicate_layers()}
    assert layers["nutzung"].cross_layer_groups() == ("nutzung:1",)
    assert layers["gebaeude"].cross_layer_groups() == ()
    assert "verschiedenen Ergebnis-Layern" in cross_layer_warning_text(1)


def test_every_layer_needs_an_explicit_decision():
    flow = make_workflow()
    assert flow.open_duplicate_decisions() == ("gebaeude", "nutzung")
    flow.set_duplicate_decision("gebaeude", True)
    with pytest.raises(ValueError, match="nutzung"):
        flow.apply_duplicate_decisions()
    with pytest.raises(KeyError):
        flow.set_duplicate_decision("flurstuecke", True)


def test_merge_keeps_one_object_per_group_and_records_the_decision():
    flow = make_workflow()
    flow.set_duplicate_decision("gebaeude", True)
    flow.set_duplicate_decision("nutzung", False)

    removed = flow.apply_duplicate_decisions()

    rows = [r.source_row_id for r in flow.result.harmonized_records]
    assert removed == 2
    assert rows == [1, 3, 5, 6, 7, 8]
    assert [i.confirmed for i in flow.result.issues] == [True, False]


def test_changing_the_decision_starts_again_from_the_original_records():
    flow = make_workflow()
    flow.set_duplicate_decision("gebaeude", True)
    flow.set_duplicate_decision("nutzung", True)
    assert flow.apply_duplicate_decisions() == 3

    flow.set_duplicate_decision("gebaeude", False)
    flow.set_duplicate_decision("nutzung", False)

    assert flow.apply_duplicate_decisions() == 0
    assert len(flow.result.harmonized_records) == 8
    assert {layer.table_name for layer in flow.duplicate_layers()} == {"gebaeude", "nutzung"}


def test_group_examples_show_differing_values_and_layers():
    flow = make_workflow()
    layers = {layer.table_name: layer for layer in flow.duplicate_layers()}
    _group, records = layers["gebaeude"].groups[0]
    assert describe_group(records) == "2 Objekte (Wohngebäude; – / Hausnr. 5) in gebaeude"
    _group, records = layers["nutzung"].groups[0]
    assert "in nutzung_fuss_radwege, nutzung_strassen" in describe_group(records)


def test_hint_is_assigned_to_a_layer_only_when_unambiguous():
    assert issue_table_name("gebaeude: 645 Gruppe(n) ...", ["gebaeude", "nutzung"]) == "gebaeude"
    assert issue_table_name("Im Layer „gebaeude“ gibt es ...", ["gebaeude"]) == "gebaeude"
    assert issue_table_name("gebaeude und nutzung", ["gebaeude", "nutzung"]) is None
    assert issue_table_name("gebaeude_alt: 1 Gruppe", ["gebaeude"]) is None


def test_hint_with_readable_layer_name_is_assigned(monkeypatch):
    import types

    import urban_analysis

    fake_mapping = types.ModuleType("urban_analysis.mapping")
    fake_mapping.readable_layer = {"gebaeude": "Gebäude", "nutzung": "Nutzung"}.get
    monkeypatch.setitem(__import__("sys").modules, "urban_analysis.mapping", fake_mapping)
    monkeypatch.setattr(urban_analysis, "mapping", fake_mapping, raising=False)

    text = "Gebäude: An 693 Stellen liegen mehrere Objekte genau übereinander."
    assert issue_table_name(text, ["gebaeude", "nutzung"]) == "gebaeude"


def test_feedback_after_applying():
    assert duplicates_applied_text(0) == "Entscheidung übernommen: Alle Objekte bleiben erhalten."
    assert duplicates_applied_text(1030).endswith("1 030 Objekte durch Zusammenführen entfernt.")
    assert duplicates_applied_text(1).endswith(": 1 Objekt durch Zusammenführen entfernt.")


def test_group_examples_use_readable_layer_names():
    flow = make_workflow()
    layers = {layer.table_name: layer for layer in flow.duplicate_layers()}
    _group, records = layers["nutzung"].groups[0]
    names = {"nutzung_fuss_radwege": "Fuß- und Radwege"}.get
    # unknown names fall back to the technical id
    assert describe_group(records, names).endswith("in Fuß- und Radwege, nutzung_strassen")


def test_step6_texts_use_readable_names_and_correct_singular_plural():
    assert duplicate_title_text("Gebäude", 645, 1675) == "Gebäude: 645 Gruppen mit 1 675 Objekten"
    assert duplicate_title_text("Bewertung", 1, 2) == "Bewertung: 1 Gruppe mit 2 Objekten"
    assert more_groups_text(1) == "… und 1 weitere Gruppe"
    assert more_groups_text(642) == "… und 642 weitere Gruppen"
    assert merge_hint_text(1) == "Je Gruppe bleibt das erste Objekt, 1 Objekt wird entfernt."
    assert merge_hint_text(1030) == "Je Gruppe bleibt das erste Objekt, 1 030 Objekte werden entfernt."
    assert cross_layer_warning_text(1).startswith("Achtung: 1 Gruppe liegt in")
    assert cross_layer_warning_text(3).startswith("Achtung: 3 Gruppen liegen in")
