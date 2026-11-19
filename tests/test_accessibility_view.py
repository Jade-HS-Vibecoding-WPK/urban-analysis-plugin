"""W16: accessibility settings in step 9 (QGIS-free parts)."""

from types import SimpleNamespace

import pytest

from urban_analysis.accessibility_view import (
    DEFAULT_COLORS,
    AccessibilityChoice,
    OwnTarget,
    RadiusError,
    choice_problem,
    distance_columns,
    guide_value,
    own_records,
    own_target_label,
    parse_radii,
    radii_text,
    rings_problem,
    rings_with_guide,
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


def test_ticked_rings_give_radii_and_colours_inside_out():
    choice = AccessibilityChoice(rings=((True, 500, "#b"), (True, 300, "#a"), (False, 1000, "#c")))
    assert choice.radii == (300, 500)
    assert choice.colors == ("#a", "#b")
    assert AccessibilityChoice().radii == (300, 500)  # preset: two of five rings ticked


def test_ring_problems_are_explained():
    assert "mindestens einen Ring" in rings_problem(((False, 300, "#a"),))
    assert "denselben Radius" in rings_problem(((True, 300, "#a"), (True, 300, "#b")))
    assert rings_problem(((True, 300, "#a"), (True, 500, "#b"))) is None
    assert "mindestens einen Ring" in choice_problem(
        AccessibilityChoice(targets={"Gesundheit": ()}, rings=((False, 300, "#a"),)))


def test_guide_value_sets_the_first_rings_and_keeps_the_colours():
    rings = ((True, 300, "#a"), (True, 500, "#b"), (True, 750, "#c"))
    assert rings_with_guide(rings, (600, 1000)) == (
        (True, 600, "#a"), (True, 1000, "#b"), (False, 750, "#c"))


def test_own_targets_alone_are_enough_and_become_records():
    target = OwnTarget("POINT(10 20)", "Geplanter Kiosk")
    assert choice_problem(AccessibilityChoice(own_targets=[target])) is None
    area = OwnTarget("POLYGON((0 0,1 0,1 1,0 0))", "", {"Name": "Rathaus", "Layer": "Gebäude"})
    records = own_records([target, area])
    assert [r.layer_id for r in records] == ["eigene_ziele_punkte", "eigene_ziele_flaechen"]
    assert records[0].attributes["category"] == "Eigene Ziele"
    assert records[1].extra_attributes["Name"] == "Rathaus"
    assert own_target_label(3, {"Name": "Rathaus"}) == "Rathaus"
    assert own_target_label(3, {}) == "Eigenes Ziel 3"


def test_result_layers_points_first_then_lines_then_areas():
    from urban_analysis.guided_dialog import layer_order_key

    layers = [("polygon", 9), ("point", 1), ("line", 5), ("polygon", 2), ("point", 7)]
    assert sorted(layers, key=lambda item: layer_order_key(*item)) == [
        ("point", 7), ("point", 1), ("line", 5), ("polygon", 9), ("polygon", 2)]


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
