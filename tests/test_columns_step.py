"""W14: step 5 with all columns (QGIS-free parts)."""

from types import SimpleNamespace

from urban_analysis.contracts import ColumnInfo, PipelineResult
from urban_analysis.guided_dialog import (
    column_choices,
    column_decisions_of,
    column_header_text,
    decision_from_value,
    decision_value,
)
from urban_analysis.outputs import extra_field_names

COLUMNS = [
    ColumnInfo("gebaeude", "oid", "Objekt-ID", True, ("DENI1",), "object_id", 1.0),
    ColumnInfo("gebaeude", "anzahlgs", "Geschosszahl", True, ("2", "3")),
    ColumnInfo("gebaeude", "xyz", "", False, ("a",)),
]


def flow_with_columns():
    result = PipelineResult(contract_version="1.0", project_crs="EPSG:25832",
                            study_area_wkt="POLYGON EMPTY", columns=list(COLUMNS))
    return SimpleNamespace(result=result)


def test_preselection_core_keep_drop():
    decisions = column_decisions_of(flow_with_columns())
    values = [decision_value(decisions[("gebaeude", c.source_field)]) for c in COLUMNS]
    assert values == ["target:object_id", "keep", "drop"]
    assert column_header_text("Gebäude", COLUMNS, decisions) == (
        "Gebäude – 1 Kernfelder, 1 behalten, 1 nicht geladen")


def test_overview_lines_and_always_kept_columns():
    from urban_analysis.guided_dialog import column_summary, summary_lines

    columns = COLUMNS + [ColumnInfo("gebaeude", "baujahr", "Baujahr", False, ("1912",))]
    flow = flow_with_columns()
    flow.result.columns = columns
    decisions = column_decisions_of(flow)
    assert decision_value(decisions[("gebaeude", "baujahr")]) == "keep"  # always kept
    lines = summary_lines(column_summary(columns, decisions))
    assert lines[1] == "Behalten: Geschosszahl, Baujahr"
    assert lines[2] == "Ignoriert: 1 technische Spalte"


def test_objects_are_cut_at_the_border_for_drawing():
    from urban_analysis.map_styles import category_colors, cut_expressions

    inside, outside = cut_expressions("POLYGON ((0 0, 1 0, 1 1, 0 0))")
    assert inside == "intersection($geometry, geom_from_wkt('POLYGON ((0 0, 1 0, 1 1, 0 0))'))"
    assert outside.startswith("difference($geometry")
    fill = category_colors("Gebäude", "aussen")[0]
    assert fill[1:3] == fill[3:5] == fill[5:7]  # grey
    assert int(fill[1:3], 16) > int(category_colors("Gebäude", "graustufen")[0][1:3], 16)  # weaker


def test_label_click_cycles_and_preview_order():
    from urban_analysis.guided_dialog import counts_text, next_value, preview_columns, state_of

    oid, floors, other = COLUMNS
    assert next_value("target:object_id", oid) == "keep"
    assert next_value("keep", oid) == "drop"
    assert next_value("drop", oid) == "target:object_id"  # back to its suggestion
    assert state_of("target:address") == "target"
    values = {("gebaeude", "anzahlgs"): "keep", ("gebaeude", "oid"): "target:object_id",
              ("gebaeude", "xyz"): "drop"}
    headers = [(h, s) for h, s, _f in preview_columns(COLUMNS, values)]
    assert [s for _h, s in headers] == ["target", "keep"]  # core fields first
    assert headers[1][0] == "Geschosszahl"
    assert counts_text(COLUMNS, values) == "1 Kernfelder · 1 behalten · 1 ignoriert"


def test_choice_values_round_trip():
    for value in ("target:address", "keep", "drop"):
        assert decision_value(decision_from_value(COLUMNS[1], value)) == value
    kept = decision_from_value(COLUMNS[1], "keep")
    assert kept.name == "Geschosszahl"


def test_choices_offer_core_fields_keep_and_drop():
    values = [value for value, _text, _help in column_choices()]
    assert values[-2:] == ["keep", "drop"]
    assert "target:address" in values and "target:object_id" in values


def test_kept_columns_become_fields_without_clashes():
    records = [SimpleNamespace(extra_attributes={"Geschosszahl": "2", "source": "x"}),
               SimpleNamespace(extra_attributes={"Dachform": "Satteldach"})]
    assert extra_field_names(records) == {
        "Geschosszahl": "Geschosszahl", "source": "Quelle: source", "Dachform": "Dachform"}
