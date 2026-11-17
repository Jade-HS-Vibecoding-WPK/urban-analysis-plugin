"""Shared style of the plugin (theme.py)."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from urban_analysis.theme import (
    BODY_FONTS,
    CHECK_ICON_FILE,
    COLORS,
    HEADING_FONTS,
    RADIO_FILES,
    RADIUS_PX,
    ROLES,
    choose_family,
    icon_path,
    panel_stylesheet,
    set_role,
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
