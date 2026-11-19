"""Vertretung Mac (19.11.2026): result layers in sub-groups (QGIS-free part
of outputs.py), so the layer list stays short and the map calm."""

import json

from urban_analysis.mapping import RULES_FILE
from urban_analysis.outputs import (
    HIDDEN_LAYER_GROUPS,
    LAYER_GROUPS,
    OTHER_LAYER_GROUP,
    layer_group_name,
    layer_groups,
)


def all_categories():
    rules = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    found = set()
    for profile in rules["profiles"]:
        for layer in profile["layers"].values():
            found.add(layer.get("category"))
            found.update(rule["category"] for rule in layer.get("category_rules", ()))
            found.add((layer.get("default_rule") or {}).get("category"))
    return found - {None}


def test_every_known_category_has_a_group():
    assert {category for category in all_categories() if layer_group_name(category) == OTHER_LAYER_GROUP} == set()


def test_each_category_is_in_one_group_only():
    listed = [category for _name, categories in LAYER_GROUPS for category in categories]
    assert len(listed) == len(set(listed))


def test_groups_in_fixed_order_and_layers_keep_their_order():
    categories = {
        "zaun": "Zäune und Mauern",
        "gebaeude": "Gebäude",
        "strassen_l": "Straßen",
        "eigen": "Kartierung",
        "gruen": "Grünflächen",
        "schulen": "Bildung und Betreuung",
        "wege": "Fuß- und Radwege",
    }
    groups = layer_groups(list(categories), categories)
    assert groups == [
        ("Einrichtungen", ["schulen"]),
        ("Verkehr", ["strassen_l", "wege"]),
        ("Bebauung", ["gebaeude"]),
        ("Grün & Wasser", ["gruen"]),
        (OTHER_LAYER_GROUP, ["eigen"]),
        ("Sonstiges", ["zaun"]),
    ]


def test_only_small_things_are_hidden():
    assert HIDDEN_LAYER_GROUPS == ("Sonstiges",)
    assert layer_group_name("Sonstige OSM-Punkte") == "Sonstiges"
    assert layer_group_name("Gebäude") not in HIDDEN_LAYER_GROUPS
    assert layer_group_name(None) == OTHER_LAYER_GROUP
