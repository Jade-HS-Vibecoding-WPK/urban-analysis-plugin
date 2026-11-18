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


def test_classic_header_marker_glides_to_the_current_step():
    from urban_analysis.ui.classic_motion import ClassicHeaderState

    state = ClassicHeaderState()
    state.set_step(4)
    positions = []
    while state.busy():
        state.tick()
        positions.append(state.marker)
    assert positions == sorted(positions) and positions[-1] == 4.0
    assert [state.point_state(i) for i in (3, 4, 5)] == ["done", "current", "open"]


def test_classic_bar_follows_progress_then_green_or_red():
    from urban_analysis.ui.classic_motion import DONE_FRAMES, ClassicHeaderState

    state = ClassicHeaderState()
    state.start_loading()
    state.set_progress(60)
    for _ in range(20):
        state.tick()
    assert state.bar == "loading" and abs(state.shown - 60) < 0.6
    state.finish()
    assert state.bar == "done" and state.shown == 100
    for _ in range(DONE_FRAMES):
        state.tick()
    assert state.bar is None  # hides again
    state.start_loading()
    state.fail()
    assert state.bar == "error" and state.shake_offset() != 0


def test_classic_celebration_fills_all_points_and_pops_the_last():
    from urban_analysis.ui.classic_motion import POP, ClassicHeaderState

    state = ClassicHeaderState()
    state.set_step(9)
    state.celebrate()
    assert all(state.point_state(i) == "done" for i in range(9))
    scales = []
    while state.pop_frame is not None:
        scales.append(state.pop_scale())
        state.tick()
    assert max(scales) > 1.2 and len(scales) == len(POP)


def test_reduced_animations_jump_directly():
    from urban_analysis.ui.classic_motion import ClassicHeaderState

    state = ClassicHeaderState(animations=False)
    state.set_step(6)
    assert state.marker == 6.0
    state.celebrate()
    assert state.pop_frame is None


def test_every_layer_icon_has_a_flat_classic_twin_without_pixels():
    from urban_analysis.ui.classic_icons import CLASSIC_ICONS, classic_shapes, missing_twins

    assert missing_twins() == set()
    kinds = {"badge", "rect", "ellipse", "poly", "line", "dash", "text"}
    for key, shapes in CLASSIC_ICONS.items():
        assert shapes[0][0] == "badge", key
        assert {shape[0] for shape in shapes} <= kinds, key
        assert len(shapes) >= 2, key
    assert classic_shapes("gibt-es-nicht") == CLASSIC_ICONS["unbekannt"]


def test_toolbar_icon_changes_with_the_style():
    from pathlib import Path
    import xml.etree.ElementTree as ET

    from urban_analysis.theme import toolbar_icon_path

    classic = Path(toolbar_icon_path("classic"))
    pixel = Path(toolbar_icon_path("pixel"))
    assert classic.name == "hase_karte_klassisch.svg" and pixel.name == "hase_karte.svg"
    root = ET.parse(classic).getroot()
    assert root.get("shape-rendering") != "crispEdges"  # smooth, no pixels
    assert root.findall("{http://www.w3.org/2000/svg}rect") == []
    assert toolbar_icon_path("rainbow") == str(classic)


def test_classic_release_ring_grows_and_fades_out():
    states = [pm.ring_state(left) for left in range(pm.RING_FRAMES, 0, -1)]
    grows = [grow for grow, _opacity in states]
    opacities = [opacity for _grow, opacity in states]
    assert grows == sorted(grows) and opacities == sorted(opacities, reverse=True)
    assert pm.ring_state(0) is None
    assert max(grows) <= pm.CLASSIC_MARGIN_PX  # stays inside the button area
