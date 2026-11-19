"""W16: accessibility settings in step 9 (QGIS-free parts)."""

from types import SimpleNamespace

import pytest

from urban_analysis.accessibility_view import (
    DEFAULT_COLORS,
    AccessibilityChoice,
    RadiusError,
    choice_problem,
    distance_columns,
    guide_value,
    parse_radii,
    radii_for,
    radii_text,
    ring_colors,
    ring_label,
    target_choices_from,
)


def test_radii_are_sorted_whole_metres_without_doubles():
    assert parse_radii("500, 300; 300 m") == (300, 500)
    assert radii_text((300, 500)) == "300, 500"


@pytest.mark.parametrize("text", ["", "abc", "0", "9000", "1,2,3,4,5,6"])
def test_unusable_radii_say_what_to_do(text):
    with pytest.raises(RadiusError):
        parse_radii(text)


def test_ring_colours_default_green_yellow_red_and_keep_own_choice():
    assert ring_colors((300, 500, 800)) == DEFAULT_COLORS[:3]
    assert ring_colors((300, 500), ("#000000",)) == ("#000000", DEFAULT_COLORS[1])


def test_ring_labels():
    assert ring_label(0, 300) == "bis 300 m"
    assert ring_label(300, 500) == "300–500 m"


def test_targets_whole_categories_or_single_kinds():
    choices = target_choices_from({"ÖPNV-Haltestellen": (), "Nahversorgung": ("Supermarkt",)})
    assert [(c.category, c.subtypes, c.label) for c in choices] == [
        ("ÖPNV-Haltestellen", (), "ÖPNV-Haltestellen"),
        ("Nahversorgung", ("Supermarkt",), "Supermarkt"),
    ]


def test_without_targets_is_explained():
    assert "Ziel" in choice_problem(AccessibilityChoice())
    assert choice_problem(AccessibilityChoice(targets={"Gesundheit": ()})) is None


def test_guide_values_per_target():
    assert guide_value("ÖPNV-Haltestellen")[0] == (300, 500)
    assert guide_value("ÖPNV-Haltestellen", ("Bahnhof", "Bahnhaltepunkt"))[0] == (600, 1000)
    # mixed bus and rail: the value of the category
    assert guide_value("ÖPNV-Haltestellen", ("Bahnhof", "Bushaltestelle"))[0] == (300, 500)
    assert guide_value("Nahversorgung", ("Supermarkt",))[0] == (500, 1000)
    radii, text = guide_value("Unbekannt")
    assert radii == (300, 500) and "selbst" in text


def test_own_radii_win_over_the_guide_value():
    choice = AccessibilityChoice(targets={"Nahversorgung": (), "Gesundheit": ()},
                                 radii={"Nahversorgung": (400,)})
    assert radii_for(choice, "Nahversorgung") == (400,)
    assert radii_for(choice, "Gesundheit") == (500, 1000)


def test_distance_columns_only_of_buildings_with_object_id():
    def record(category, object_id, extra):
        return SimpleNamespace(attributes={"category": category, "object_id": object_id},
                               extra_attributes=extra)

    records = [
        record("Gebäude", "b1", {"Abstand Supermarkt (m)": 120, "Supermarkt bis 300 m": "ja",
                                 "Name": "Haus"}),
        record("Gebäude", "", {"Abstand Supermarkt (m)": 50}),
        record("Nahversorgung", "s1", {"Abstand Supermarkt (m)": 0}),
    ]
    assert distance_columns(records, ["Supermarkt"]) == {
        "b1": {"Abstand Supermarkt (m)": 120, "Supermarkt bis 300 m": "ja"}}
