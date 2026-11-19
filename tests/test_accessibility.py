"""Accessibility stage 1: distance as the crow flies (M20, E26, E34)."""

from urban_analysis.accessibility import (
    AccessibilitySettings,
    TargetChoice,
    add_air_distance,
    load_settings,
    target_choices,
    target_records,
)
from urban_analysis.data_pipeline import HarmonizedRecord
from urban_analysis.geometry import parse_wkt, representative_point

SETTINGS = AccessibilitySettings(
    radii_m=(300, 500),
    origin_categories=("Gebäude",),
    target_categories=("Nahversorgung", "Gesundheit"),
    area_targets={"Krankenhausgelände": ("Gesundheit", "Krankenhaus")},
)


def record(row_id, category, object_type, wkt):
    return HarmonizedRecord(
        layer_id="test",
        source_row_id=row_id,
        attributes={"category": category, "object_type": object_type},
        geometry=wkt,
        source_layer="test",
    )


def square(x, y, size=10):
    return f"POLYGON (({x} {y}, {x + size} {y}, {x + size} {y + size}, {x} {y + size}, {x} {y}))"


RECORDS = [
    record(1, "Gebäude", "Wohnhaus", square(0, 0)),  # centre (5, 5)
    record(2, "Gebäude", "Wohnhaus", square(1000, 0)),  # centre (1005, 5)
    record(3, "Nahversorgung", "Supermarkt", "POINT (5 405)"),  # 400 m from house 1
    record(4, "Nahversorgung", "Bäckerei", "POINT (1005 105)"),  # 100 m from house 2
    record(5, "Nutzungsflächen", "Krankenhausgelände", square(0, 2000, 100)),
    record(6, "Straßen", "Wohnstraße", "LINESTRING (0 50, 1000 50)"),
]


def extra(records, row_id):
    return next(r for r in records if r.source_row_id == row_id).extra_attributes


def test_centre_of_an_area_and_of_a_point():
    assert representative_point(parse_wkt(square(0, 0))) == (5.0, 5.0)
    assert representative_point(parse_wkt("POINT (3 4)")) == (3.0, 4.0)
    assert representative_point(parse_wkt("LINESTRING (0 0, 10 0)")) == (5.0, 0.0)


def test_choices_list_the_targets_in_the_data_including_areas():
    assert target_choices(RECORDS, SETTINGS) == {
        "Nahversorgung": [("Bäckerei", 1), ("Supermarkt", 1)],
        "Gesundheit": [("Krankenhaus", 1)],
    }
    hospital = target_records(RECORDS, TargetChoice("Gesundheit", ("Krankenhaus",)), SETTINGS)
    assert [r.source_row_id for r in hospital] == [5]


def test_distance_to_the_nearest_target_of_the_whole_category():
    records, issues = add_air_distance(RECORDS, TargetChoice("Nahversorgung"), SETTINGS)

    assert extra(records, 1) == {
        "Abstand Nahversorgung (m)": 400,
        "Nahversorgung bis 300 m": "nein",
        "Nahversorgung bis 500 m": "ja",
    }
    assert extra(records, 2)["Abstand Nahversorgung (m)"] == 100
    assert extra(records, 2)["Nahversorgung bis 300 m"] == "ja"
    assert extra(records, 3) == {} and extra(records, 6) == {}  # only buildings get columns
    (summary,) = issues
    assert summary.code == "accessibility-summary" and summary.severity == "info"
    assert summary.message == (
        "Erreichbarkeit „Nahversorgung“ (Luftlinie): 50 % höchstens 300 m; 100 % höchstens 500 m "
        "vom nächsten Ziel entfernt."
    )
    assert "Luftlinie" in summary.details


def test_only_the_chosen_subtypes_count():
    records, _ = add_air_distance(RECORDS, TargetChoice("Nahversorgung", ("Supermarkt",)), SETTINGS)
    # the bakery 100 m away does not count: (1005, 5) -> (5, 405) = 1077 m
    assert extra(records, 2)["Abstand Supermarkt (m)"] == 1077


def test_hospital_area_counts_with_its_centre_and_choices_add_up():
    records, _ = add_air_distance(RECORDS, TargetChoice("Nahversorgung"), SETTINGS)
    records, _ = add_air_distance(records, TargetChoice("Gesundheit", ("Krankenhaus",)), SETTINGS)
    columns = extra(records, 1)
    assert columns["Abstand Krankenhaus (m)"] == 2045  # from (5, 5) to (50, 2050)
    assert "Abstand Nahversorgung (m)" in columns


def test_no_targets_is_a_visible_warning_and_nothing_changes():
    records, issues = add_air_distance(RECORDS, TargetChoice("Gesundheit", ("Apotheke",)), SETTINGS)
    assert records == RECORDS
    (issue,) = issues
    assert issue.severity == "warning" and "keine Ziele „Apotheke“" in issue.message
    assert issue.action


def test_coordinates_in_degrees_are_refused():
    in_degrees = [
        record(1, "Gebäude", "Wohnhaus", "POLYGON ((8.2 53.1, 8.201 53.1, 8.201 53.101, 8.2 53.1))"),
        record(2, "Nahversorgung", "Supermarkt", "POINT (8.21 53.11)"),
    ]
    records, issues = add_air_distance(in_degrees, TargetChoice("Nahversorgung"), SETTINGS)
    assert records == in_degrees
    assert issues[0].severity == "error" and "Metern" in issues[0].message


def test_settings_come_from_the_rules_file():
    settings = load_settings()
    assert settings.radii_m == (300, 500)
    assert settings.origin_categories == ("Gebäude",)
    assert "ÖPNV-Haltestellen" in settings.target_categories
    assert settings.area_targets["Krankenhausgelände"] == ("Gesundheit", "Krankenhaus")
