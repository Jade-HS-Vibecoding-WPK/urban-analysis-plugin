"""W6: QGIS-free parts of building the result layers (S6)."""

from urban_analysis.contracts import LayerDescriptor
from urban_analysis.data_pipeline import TARGET_FIELDS
from urban_analysis.outputs import (
    SKIP_NO_GEOMETRY,
    SKIP_UNREADABLE,
    ResultLayerReport,
    field_value,
    result_field_specs,
    result_group_name,
    result_layer_name,
    result_layers_text,
)


def test_result_layers_get_all_eight_target_fields_with_types():
    specs = dict(result_field_specs())
    assert tuple(specs) == TARGET_FIELDS
    assert len(specs) == 8
    assert specs["area_m2"] == "double"
    assert specs["year"] == "int"
    assert specs["object_detail"] == "text"


def test_field_values_keep_empty_as_null_and_convert_numbers():
    assert field_value("text", "") is None
    assert field_value("text", None) is None
    assert field_value("double", "12.5") == 12.5
    assert field_value("int", 2020.0) == 2020
    assert field_value("text", 5) == "5"


def test_layer_names_prefer_readable_names_then_category():
    readable = {"gebaeude": "Gebäude"}.get
    buildings = LayerDescriptor("gebaeude", "gebaeude", "MULTIPOLYGON", "a.gpkg", category="Gebäude")
    roads = LayerDescriptor("nutzung_strassen", "nutzung – Straßen", "MULTIPOLYGON", "a.gpkg",
                            category="Straßen")
    plain = LayerDescriptor("x", "x-name", "POINT", "a.gpkg")
    assert result_layer_name(buildings, readable) == "Gebäude"
    assert result_layer_name(roads, lambda layer_id: layer_id) == "Straßen"
    assert result_layer_name(plain) == "x-name"


def test_feedback_names_count_and_every_skipped_object():
    ok = ResultLayerReport("gebaeude", "Gebäude", feature_count=18930)
    gaps = ResultLayerReport("nutzung_gruen", "Grünflächen", feature_count=260)
    gaps.skip(SKIP_NO_GEOMETRY)
    gaps.skip(SKIP_NO_GEOMETRY)
    gaps.skip(SKIP_UNREADABLE)

    text = result_layers_text([ok, gaps])

    assert text.splitlines()[0] == "2 Ergebnis-Layer in QGIS angelegt (19 190 Objekte)."
    assert "Grünflächen: 2 Objekt(e) nicht übernommen – ohne Geometrie." in text
    assert "Grünflächen: 1 Objekt(e) nicht übernommen – Geometrie nicht lesbar." in text


def test_result_group_is_named_after_the_topic():
    assert result_group_name("Siedlungsstruktur") == "Urban Analysis – Siedlungsstruktur"
    assert result_group_name(None) == "Urban Analysis – Ergebnis"
