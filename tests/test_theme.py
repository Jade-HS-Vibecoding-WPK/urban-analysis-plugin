"""Shared style of the plugin (theme.py)."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import random

from urban_analysis.theme import (
    COLORS,
    LAMP_FILES,
    ROLES,
    WIRE_PATTERN,
    WIRE_ROWS,
    icon_path,
    lit_columns,
    panel_stylesheet,
    set_role,
    spawn_sparks,
    step_sparks,
    wire_cells,
)


def _rule(css, selector):
    return css.split(selector + " {")[1].split("}")[0]


def test_buttons_react_to_hover_and_click_for_every_button_kind():
    css = panel_stylesheet()
    for selector in ("QPushButton", 'QPushButton[uaRole="primary"]'):
        assert f"{selector}:hover" in css
        assert f"{selector}:pressed" in css


def test_primary_action_stands_out_and_changes_on_hover_and_press():
    css = panel_stylesheet()
    normal = _rule(css, 'QPushButton[uaRole="primary"]')
    hover = _rule(css, 'QPushButton[uaRole="primary"]:hover')
    pressed = _rule(css, 'QPushButton[uaRole="primary"]:pressed')
    assert COLORS["accent"] in normal
    assert COLORS["accent_hover"] in hover
    assert COLORS["accent_pressed"] in pressed
    assert "padding" in pressed  # label shifts down when pressed


def test_light_neutral_palette():
    for name in ("background", "surface"):
        red, green, blue = (int(COLORS[name][i : i + 2], 16) for i in (1, 3, 5))
        assert min(red, green, blue) >= 0xF0, name


def test_every_role_used_in_the_stylesheet_is_known():
    used = set(re.findall(r'uaRole="([^"]+)"', panel_stylesheet()))
    assert used <= set(ROLES)


def test_unknown_role_is_rejected():
    with pytest.raises(ValueError, match="Unbekannte Stilrolle"):
        set_role(object(), "rainbow")


def test_three_own_pixel_lamps_for_the_step_progress():
    assert set(LAMP_FILES) == {"off", "dim", "on"}
    fills = {}
    for state, name in LAMP_FILES.items():
        root = ET.parse(Path(icon_path(name))).getroot()
        assert root.get("width") == "16" and root.get("shape-rendering") == "crispEdges"
        rects = root.findall("{http://www.w3.org/2000/svg}rect")
        assert sum(int(rect.get("width")) for rect in rects) == 16 * 16
        fills[state] = {rect.get("fill") for rect in rects}
    assert fills["off"] != fills["dim"] != fills["on"]


def test_wire_is_continuous_and_stays_in_its_rows():
    cells = wire_cells(40)
    columns = {x for x, _y in cells}
    assert columns == set(range(40))
    assert all(0 <= y < WIRE_ROWS for _x, y in cells)
    # where the row changes, a connecting cell exists in the same column
    for x in range(1, 40):
        before = WIRE_PATTERN[(x - 1) % len(WIRE_PATTERN)]
        assert (x, before) in cells


def test_lit_part_follows_the_real_progress_only():
    assert lit_columns(0, 100, 80) == 0
    assert lit_columns(50, 100, 80) == 40
    assert lit_columns(100, 100, 80) == 80
    assert lit_columns(150, 100, 80) == 80
    assert lit_columns(10, 0, 80) == 0


def test_sparks_start_at_the_front_rise_and_fade_out():
    sparks = spawn_sparks(120.0, 20.0, random.Random(1), count=5)
    assert len(sparks) == 5
    assert all(abs(s[0] - 120.0) <= 2 and s[3] < 0 for s in sparks)  # at the front, rising
    later = sparks
    for _ in range(20):
        later = step_sparks(later)
    assert later == []  # every spark ends


def test_toolbar_icon_is_an_own_16x16_pixel_svg():
    path = Path(icon_path())
    assert path.name == "erdblock.svg"
    root = ET.parse(path).getroot()
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.get("width") == "16" and root.get("height") == "16"
    assert root.get("shape-rendering") == "crispEdges"
    rects = root.findall("{http://www.w3.org/2000/svg}rect")
    assert sum(int(rect.get("width")) for rect in rects) == 16 * 16
