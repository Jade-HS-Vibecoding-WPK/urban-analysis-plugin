"""Shared style of the plugin (theme.py)."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from urban_analysis.theme import COLORS, ROLES, icon_path, panel_stylesheet, set_role


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


def test_toolbar_icon_is_an_own_16x16_pixel_svg():
    path = Path(icon_path())
    assert path.name == "erdblock.svg"
    root = ET.parse(path).getroot()
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.get("width") == "16" and root.get("height") == "16"
    assert root.get("shape-rendering") == "crispEdges"
    rects = root.findall("{http://www.w3.org/2000/svg}rect")
    assert sum(int(rect.get("width")) for rect in rects) == 16 * 16
