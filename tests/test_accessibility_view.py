"""W16: accessibility settings in step 7 (QGIS-free parts)."""

import pytest

from urban_analysis.accessibility_view import (
    DEFAULT_COLORS,
    AccessibilityChoice,
    RadiusError,
    choice_problem,
    parse_radii,
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


def test_enabled_without_targets_is_explained():
    assert choice_problem(AccessibilityChoice(enabled=False)) is None
    assert "Ziel" in choice_problem(AccessibilityChoice(enabled=True))
    assert choice_problem(AccessibilityChoice(enabled=True, targets={"Gesundheit": ()})) is None
