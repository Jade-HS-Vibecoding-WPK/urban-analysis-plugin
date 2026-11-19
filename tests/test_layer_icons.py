"""Own pixel icons per layer and category (ui/layer_icons.py)."""

import json
from pathlib import Path

import pytest

from urban_analysis.ui import layer_icons as icons

RULES = json.loads((Path(icons.__file__).parents[1] / "mapping_rules.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("key", icons.ICON_KEYS)
def test_every_icon_is_a_16x16_tile_with_stepped_corners(key):
    pixels = icons.icon_pixels(key)
    assert all(0 <= x < 16 and 0 <= y < 16 for x, y in pixels)
    for corner in ((0, 0), (15, 0), (0, 15), (15, 15)):
        assert corner not in pixels  # stepped corner stays empty
    assert pixels[(0, 7)] == pixels[(7, 0)] == icons.PALETTE["o"]  # dark outline
    assert len(set(pixels.values())) >= 3  # a real motif, not an empty tile


def test_icons_differ_from_each_other():
    shapes = {key: tuple(sorted(icons.icon_pixels(key).items())) for key in icons.ICON_KEYS}
    assert len(set(shapes.values())) == len(shapes)


def test_every_pipeline_category_and_alkis_layer_has_its_own_icon():
    profile = RULES["profiles"][0]
    categories = {rule["category"] for rule in profile["layers"]["nutzung"]["category_rules"]}
    categories |= {profile["layers"]["nutzung"]["default_rule"]["category"], "Gebäude"}
    for category in categories:
        assert icons.icon_key(category=category) != icons.UNKNOWN, category
    for layer in profile["layers"]:
        assert icons.icon_key(layer) != icons.UNKNOWN, layer
    suffixes = {rule["layer_suffix"] for rule in profile["layers"]["nutzung"]["category_rules"]}
    for suffix in suffixes:
        assert icons.icon_key(f"nutzung_{suffix}") != icons.UNKNOWN, suffix


def test_icon_choice():
    assert icons.icon_key(category="Gebäude") == "gebaeude"
    assert icons.icon_key("nutzung_wasser") == "wasser"
    assert icons.icon_key("nutzung_gruen", "Grünflächen") == "gruen"
    assert icons.icon_key("irgendwas") == icons.UNKNOWN
    assert icons.icon_key() == icons.UNKNOWN


# --- F6b: target point icons; step 4 icons for every titled hint -------------

from types import SimpleNamespace

from urban_analysis.ui.layer_icons import UNKNOWN, icon_key


def test_target_categories_and_own_targets_have_their_own_icons():
    from urban_analysis.ui.classic_icons import CLASSIC_ICONS
    from urban_analysis.ui.layer_icons import ICON_KEYS

    for category in ("Gesundheit", "Nahversorgung", "Bildung und Betreuung",
                     "Freizeit und Grün", "ÖPNV-Haltestellen", "Sonstige OSM-Punkte", "Eigene Ziele"):
        key = icon_key(category=category)
        assert key != UNKNOWN, category
        assert key in ICON_KEYS and key in CLASSIC_ICONS
    assert icon_key("points") == "punkte"  # OSM points are no boundary stones
    assert icon_key("points_haltestellen") == "haltestellen"


def _flow(*layers):
    descriptors = [SimpleNamespace(layer_id=layer_id, category=category) for layer_id, category in layers]
    return SimpleNamespace(result=SimpleNamespace(layers=descriptors))


def test_step_4_hints_get_icons_for_layers_sources_and_categories():
    from urban_analysis.guided_dialog import issue_icon_key

    flow = _flow(("flurstuecke", None), ("gebaeude", "Gebäude"), ("multipolygons_gruen", "Grünflächen"),
                 ("nutzung_strassen", "Straßen"))

    def key(message):
        return issue_icon_key(flow, SimpleNamespace(message=message))

    assert key("ALKIS – Flurstücke: 567 von 61 311 Objekten liegen im Gebiet.") == "flurstuecke"
    assert key("ALKIS – Gebäude: 31 Gebäude haben mehrere Adressen.") == "gebaeude"
    assert key("OpenStreetMap – OSM – Punkte: 53 von 239 Objekten liegen im Gebiet.") == "punkte"
    assert key("Grünflächen: 7 Objekte sind wahrscheinlich in ALKIS und OSM doppelt vorhanden.") == "gruen"
    assert key("Straßen: 8 Objekte sind wahrscheinlich doppelt vorhanden.") == "strassen"
    assert key("ALKIS – Datenquelle fehlt: In der Datei steht nicht, woher die Daten stammen.") is None


def test_category_of_a_hint():
    from urban_analysis.user_guidance import issue_category

    names = ["Grünflächen", "Straßen", "Gebäude"]
    assert issue_category("Grünflächen: 7 Objekte", names) == "Grünflächen"
    assert issue_category("Bei den Straßen fehlt etwas", names) == "Straßen"
    assert issue_category("Straßen und Gebäude", names) == "Straßen"   # start of the text wins
    assert issue_category("Bei Straßen und Gebäuden", names) == "Straßen"
    assert issue_category("Nichts davon", names) is None

