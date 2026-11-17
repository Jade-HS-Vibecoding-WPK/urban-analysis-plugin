"""W7: step 5 'Attributzuordnung' per layer (E2) – QGIS-free parts."""

import pytest

from urban_analysis import data_pipeline
from urban_analysis.contracts import AttributeSuggestion, PipelineResult
from urban_analysis.guided_dialog import ReadableNames, mapping_detail_text
from urban_analysis.user_guidance import GuidedWorkflow


def make_workflow():
    return GuidedWorkflow(
        PipelineResult(
            contract_version="1.0",
            project_crs="EPSG:25832",
            study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
            attribute_suggestions=[
                AttributeSuggestion("gfk__bez", "object_type", 1.0, layer_id="gebaeude",
                                    examples=("Wohngebäude", "Garage")),
                AttributeSuggestion("bwf__bez", "object_type", 1.0, layer_id="bauwerke_f"),
                AttributeSuggestion("bwf__bez", "object_type", 1.0, layer_id="bauwerke_p"),
                AttributeSuggestion("untermerkmal", "status", 0.8, layer_id="bauwerke_p"),
            ],
        )
    )


def test_suggestions_are_grouped_by_layer_in_data_order():
    groups = make_workflow().suggestions_by_layer()
    assert list(groups) == ["gebaeude", "bauwerke_f", "bauwerke_p"]
    assert [s.source_field for s in groups["bauwerke_p"]] == ["bwf__bez", "untermerkmal"]


def test_equal_column_names_in_two_layers_are_decided_separately():
    flow = make_workflow()
    flow.confirm_attribute_suggestions({
        ("bauwerke_f", "bwf__bez"): "category",
        ("bauwerke_p", "bwf__bez"): False,
    })
    by_layer = {(s.layer_id, s.source_field): s for s in flow.attribute_suggestions()}
    assert by_layer[("bauwerke_f", "bwf__bez")].user_value == "category"
    assert by_layer[("bauwerke_f", "bwf__bez")].accepted is True
    assert by_layer[("bauwerke_p", "bwf__bez")].accepted is False
    assert by_layer[("gebaeude", "gfk__bez")].accepted is None  # untouched


def test_unknown_layer_and_column_are_reported():
    with pytest.raises(KeyError, match="bwf__bez \\(flurstuecke\\)"):
        make_workflow().confirm_attribute_suggestions({("flurstuecke", "bwf__bez"): True})


def test_decisions_only_apply_when_the_pipeline_supports_it(monkeypatch):
    flow = make_workflow()
    monkeypatch.delattr(data_pipeline, "apply_attribute_decisions", raising=False)
    assert flow.apply_attribute_decisions() is False

    monkeypatch.setattr(data_pipeline, "apply_attribute_decisions", lambda result: ["neu"],
                        raising=False)
    assert flow.apply_attribute_decisions() is True
    assert flow.result.harmonized_records == ["neu"]


def test_detail_line_shows_examples_and_column():
    assert mapping_detail_text("gfk__bez", ("Wohngebäude", "Garage")) == (
        "z. B. „Wohngebäude“, „Garage“ · Spalte gfk__bez"
    )
    assert mapping_detail_text("untermerkmal", ()) == "Spalte untermerkmal"


def test_readable_names_fall_back_to_technical_names():
    names = ReadableNames(layer={"gebaeude": "Gebäude"}.get, field=lambda f: 1 / 0)
    assert names.layer("gebaeude") == "Gebäude"
    assert names.layer("unbekannt") == "unbekannt"
    assert names.field("gfk__bez") == "gfk__bez"  # error in lookup -> technical name
    assert names.target("object_type") == "object_type"
