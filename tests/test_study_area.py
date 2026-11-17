"""Text helpers for the study area step (ARBEITSPLAN W3); QGIS parts are tested live."""

from urban_analysis.study_area import (
    DRAW_INSTRUCTIONS,
    StudyAreaError,
    area_summary_text,
    format_hectares,
)


def test_hectares_use_german_decimal_comma():
    assert format_hectares(843_000) == "84,3"
    assert format_hectares(12_345_678) == "1 234,6"


def test_area_summary_names_count_area_and_crs():
    assert area_summary_text(1, 843_000, "EPSG:25832") == (
        "Gebiet: 1 Polygon, 84,3 ha (im CRS EPSG:25832)"
    )
    assert area_summary_text(3, 10_000, "EPSG:25832").startswith("Gebiet: 3 Polygone, 1,0 ha")


def test_draw_instructions_explain_all_mouse_and_key_actions():
    for word in ("Linksklick", "Rechtsklick", "Esc", "Rücktaste"):
        assert word in DRAW_INSTRUCTIONS


def test_study_area_errors_are_value_errors():
    assert issubclass(StudyAreaError, ValueError)
