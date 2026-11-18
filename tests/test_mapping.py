import json

import pytest

from urban_analysis.mapping import (
    MappingRulesError,
    default_mapping_rules,
    load_mapping_rules,
    readable_field,
    readable_layer,
    readable_target_field,
    target_field_explanation,
)
from urban_analysis.data_pipeline import TARGET_FIELDS


def test_every_target_field_has_a_name_and_a_short_explanation():
    """Schema and texts stay in sync: a new target field needs both (M15)."""
    rules = default_mapping_rules()
    for field in TARGET_FIELDS:
        assert rules.target_field_name(field) != field, field
        explanation = rules.target_field_explanation(field)
        assert explanation, field
        assert explanation.endswith("."), field
        assert len(explanation) <= 120, field


def test_explanations_for_the_user_guidance():
    assert readable_target_field("object_id") == "Objekt-ID"
    assert readable_target_field("floors") == "Geschosszahl"
    assert target_field_explanation("object_type").startswith("Was das Objekt genau ist")
    assert target_field_explanation("unbekannt") is None


def test_rules_file_loads_and_knows_alkis_layers():
    rules = default_mapping_rules()

    assert rules.profile_for("gebaeude", ["objid", "gfk__bez"]).category == "Gebäude"
    assert rules.profile_for("gebaeude", ["gfk__bez"]) is None
    assert rules.profile_for("unbekannt", ["objid"]) is None
    assert rules.label("hnr") == "Hausnummer (hnr)"
    assert rules.label("xyz") == "xyz"


def test_category_from_layer_name_only():
    rules = default_mapping_rules()

    assert rules.category_from_name("buildings") == "Gebäude"
    assert rules.category_from_name("Strassen_2024") == "Straßen"
    assert rules.category_from_name("bodenschaetzung") is None


def test_split_type_uses_known_main_types():
    nutzung = default_mapping_rules().profile_for("nutzung", ["objid", "tn__bez"])

    assert nutzung.split_type("Wohnbaufläche, Offen") == ("Wohnbaufläche", "Offen")
    assert nutzung.split_type("Hafenbecken") == ("Hafenbecken", None)
    assert nutzung.split_type("Etwas Neues, Detail") == ("Etwas Neues, Detail", None)


def test_broken_rules_file_is_reported(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text("{ kein json", encoding="utf-8")
    with pytest.raises(MappingRulesError):
        load_mapping_rules(path)

    path.write_text(json.dumps({"profiles": [{"layers": {"x": {"category_rules": [{"category": "A"}]}}}]}), encoding="utf-8")
    with pytest.raises(MappingRulesError):
        load_mapping_rules(path)


def test_readable_names_for_the_user_guidance():
    assert readable_field("gfk__bez") == "Gebäudefunktion"
    assert readable_field("unbekannt") == "unbekannt"
    assert readable_layer("bauwerke_f") == "Bauwerke (Flächen)"
    assert readable_layer("eigener_layer") == "eigener_layer"
    assert readable_target_field("object_detail") == "Nutzungsdetail"
    assert readable_target_field("area_m2") == "Fläche (m²)"
