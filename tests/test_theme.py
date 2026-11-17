"""Shared style of the plugin (theme.py)."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import random

from urban_analysis.theme import (
    BODY_FONTS,
    CHECK_ICON_FILE,
    COLORS,
    HEADING_FONTS,
    LAMP_FILES,
    RADIO_FILES,
    RADIUS_PX,
    ROLES,
    choose_family,
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


def test_cozy_pixel_palette():
    assert COLORS["background"] == "#D3E6DF"  # mint
    assert COLORS["surface"] == "#EEF4F1"
    assert COLORS["text"] == "#1E3B38"  # dark petrol
    assert COLORS["accent"] == "#E8655A"  # red-orange, main action only
    assert COLORS["accent_dark"] == "#B8463D"


def test_red_orange_is_kept_for_main_actions_and_focus():
    css = panel_stylesheet()
    for selector in ("QCheckBox::indicator:checked", 'QPushButton[uaRole="choice"]:checked'):
        assert COLORS["accent"] not in _rule(css, selector)
    assert COLORS["accent"] in _rule(css, 'QPushButton[uaRole="primary"]')


def test_hard_pixel_edges_everywhere():
    css = panel_stylesheet()
    assert RADIUS_PX == 0
    assert re.findall(r"border-radius: (\d+)px", css) and set(
        re.findall(r"border-radius: (\d+)px", css)) == {"0"}
    assert "qradialgradient" not in css and "qlineargradient" not in css


def test_fonts_fall_back_to_what_is_installed():
    assert choose_family(BODY_FONTS, ["Arial", "consolas"]) == "consolas"
    assert choose_family(HEADING_FONTS, ["Arial"]) is None
    css = panel_stylesheet({"heading": "Pixelify Sans", "body": "Consolas"})
    assert 'font-family: "Consolas"' in _rule(css, "QWidget")
    assert 'font-family: "Pixelify Sans"' in _rule(css, 'QLabel[uaRole="heading"]')


def test_radio_buttons_are_own_pixel_circles():
    css = panel_stylesheet()
    for state, name in RADIO_FILES.items():
        path = Path(icon_path(name))
        root = ET.parse(path).getroot()
        assert root.get("shape-rendering") == "crispEdges"
        assert path.as_posix() in css, state


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


def test_ticked_check_box_shows_an_own_white_pixel_check_mark():
    path = Path(icon_path(CHECK_ICON_FILE))
    root = ET.parse(path).getroot()
    assert root.get("width") == "14" and root.get("shape-rendering") == "crispEdges"
    rects = root.findall("{http://www.w3.org/2000/svg}rect")
    assert rects and {rect.get("fill") for rect in rects} == {"#ffffff"}
    checked = _rule(panel_stylesheet(), "QCheckBox::indicator:checked")
    assert COLORS["selected"] in checked
    assert f'image: url("{path.as_posix()}")' in checked
    assert "\\" not in checked  # Qt needs forward slashes


def test_toolbar_icon_is_an_own_16x16_pixel_svg():
    path = Path(icon_path())
    assert path.name == "erdblock.svg"
    root = ET.parse(path).getroot()
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.get("width") == "16" and root.get("height") == "16"
    assert root.get("shape-rendering") == "crispEdges"
    rects = root.findall("{http://www.w3.org/2000/svg}rect")
    assert sum(int(rect.get("width")) for rect in rects) == 16 * 16
