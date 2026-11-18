"""Style switch: 'classic' (like QGIS, default) and 'pixel' (Cozy Pixel)."""

import re

from urban_analysis.theme import (
    CLASSIC_COLORS,
    COLORS,
    DEFAULT_STYLE,
    STYLES,
    panel_stylesheet,
    style_colors,
)
from urban_analysis.ui import pixel_motion as pm
from urban_analysis.ui import style as ui_style


def _rule(css, selector):
    return css.split(selector + " {")[1].split("}")[0]


def test_classic_is_the_default_and_unknown_values_fall_back_to_it():
    assert DEFAULT_STYLE == "classic"
    assert set(STYLES) == {"classic", "pixel"}
    assert ui_style.normalize("pixel") == "pixel"
    assert ui_style.normalize("rainbow") == "classic"
    assert ui_style.normalize(None) == "classic"


def test_choice_is_remembered_in_the_module():
    try:
        assert ui_style.set_current("pixel") == "pixel"
        assert ui_style.current() == "pixel"
        assert ui_style.save("nonsense") == "classic"  # also outside QGIS
        assert ui_style.current() == "classic"
    finally:
        ui_style.set_current(DEFAULT_STYLE)


def test_both_styles_have_a_readable_label_for_the_gear_menu():
    assert set(ui_style.STYLE_LABELS) == set(STYLES)
    assert "QGIS" in ui_style.STYLE_LABELS["classic"]


def test_classic_looks_like_qgis_blue_accent_soft_corners_native_boxes():
    css = panel_stylesheet(style="classic")
    assert CLASSIC_COLORS["accent"] == "#2f6fb0"  # blue
    assert style_colors("classic") is CLASSIC_COLORS and style_colors("pixel") is COLORS
    assert CLASSIC_COLORS["background"] in _rule(css, "QWidget")
    assert "font-family" not in css  # QGIS font
    assert "::indicator" not in css  # native check boxes and radio buttons
    assert "haken.svg" not in css and "radio_" not in css  # no pixel images
    assert set(re.findall(r"border-radius: (\d+)px", css)) - {"0"}  # soft corners
    assert COLORS["accent"].lower() not in css.lower()  # no red-orange


def test_pixel_style_is_unchanged():
    css = panel_stylesheet(style="pixel")
    assert COLORS["background"] in _rule(css, "QWidget")
    assert "haken.svg" in css


def test_classic_release_ring_grows_and_fades_out():
    states = [pm.ring_state(left) for left in range(pm.RING_FRAMES, 0, -1)]
    grows = [grow for grow, _opacity in states]
    opacities = [opacity for _grow, opacity in states]
    assert grows == sorted(grows) and opacities == sorted(opacities, reverse=True)
    assert pm.ring_state(0) is None
    assert max(grows) <= pm.CLASSIC_MARGIN_PX  # stays inside the button area
