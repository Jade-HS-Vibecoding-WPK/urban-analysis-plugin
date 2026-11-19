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
