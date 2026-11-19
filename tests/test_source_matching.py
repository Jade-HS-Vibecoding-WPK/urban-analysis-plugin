"""M14 / S12: Abgleich ALKIS ↔ OSM mit künstlichen, leicht verschobenen Gebäuden."""

import pytest

from urban_analysis.data_pipeline import HarmonizedRecord
from urban_analysis.geometry import parse_wkt, polygon_area
from urban_analysis.source_matching import (
    MatchSettings,
    apply_source_priority,
    load_settings,
    match_sources,
    priority_choices,
)

SETTINGS = MatchSettings(max_area_deviation=0.2, suggested_priority={"Gebäude": "ALKIS", "Grünflächen": "OSM"})


def square(x, y, size):
    return f"POLYGON (({x} {y}, {x + size} {y}, {x + size} {y + size}, {x} {y + size}, {x} {y}))"


def record(kind, wkt, category="Gebäude", row=1):
    return HarmonizedRecord(
        layer_id=f"{kind}_{category}",
        source_row_id=row,
        attributes={"category": category},
        geometry=wkt,
        source_kind=kind,
    )


def test_polygon_area_subtracts_holes():
    with_hole = parse_wkt(
        "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0), (2 2, 4 2, 4 4, 2 4, 2 2))"
    )
    assert polygon_area(with_hole) == pytest.approx(96.0)
    assert polygon_area(parse_wkt("MULTIPOLYGON (((0 0, 2 0, 2 2, 0 2, 0 0)), ((5 5, 6 5, 6 6, 5 6, 5 5)))")) == 5.0
    assert polygon_area(parse_wkt("LINESTRING (0 0, 5 5)")) == 0.0


def test_slightly_shifted_building_is_a_certain_match():
    # 10 × 10 vs. 10 × 11, um 1 m verschoben: 9 % Abweichung
    records = [record("ALKIS", square(0, 0, 10)), record("OSM", "POLYGON ((1 0, 11 0, 11 11, 1 11, 1 0))")]

    marked, matches, issues = match_sources(records, SETTINGS)

    assert len(matches) == 1 and matches[0].certain
    assert matches[0].area_deviation == pytest.approx(0.091, abs=0.001)
    assert marked[0].source_match == marked[1].source_match == "Gebäude:1"
    assert records[0].source_match is None  # input unchanged
    assert issues[0].code == "cross-source-duplicate" and not issues[0].requires_confirmation


def test_centre_inside_but_area_differs_more_is_uncertain():
    # 10 × 10 vs. 10 × 14: 29 % Abweichung
    records = [record("ALKIS", square(0, 0, 10)), record("OSM", "POLYGON ((0 0, 10 0, 10 14, 0 14, 0 0))")]

    _, matches, issues = match_sources(records, SETTINGS)

    assert len(matches) == 1 and not matches[0].certain
    assert issues[0].requires_confirmation and issues[0].severity == "warning"
    assert "unsicher" in issues[0].message


def test_no_match_for_same_source_other_category_or_far_away():
    records = [
        record("ALKIS", square(0, 0, 10)),
        record("ALKIS", square(1, 0, 10), row=2),  # same source
        record("OSM", square(0, 0, 10), category="Grünflächen"),  # other category
        record("OSM", square(500, 500, 10), row=3),  # far away
    ]

    marked, matches, issues = match_sources(records, SETTINGS)

    assert matches == [] and issues == []
    assert all(item.source_match is None for item in marked)


def test_apply_source_priority_keeps_chosen_source_and_unmatched_objects():
    records = [
        record("ALKIS", square(0, 0, 10)),
        record("OSM", square(1, 1, 10)),  # certain partner
        record("ALKIS", square(100, 0, 10), row=2),
        record("OSM", "POLYGON ((100 0, 110 0, 110 14, 100 14, 100 0))", row=2),  # uncertain
        record("OSM", square(300, 0, 10), row=3),  # only in OSM
    ]
    marked, matches, _ = match_sources(records, SETTINGS)

    kept = apply_source_priority(marked, {"Gebäude": "ALKIS"}, matches)
    assert [(item.source_kind, item.source_row_id) for item in kept] == [
        ("ALKIS", 1), ("ALKIS", 2), ("OSM", 2), ("OSM", 3)
    ]

    uncertain = next(match.group_id for match in matches if not match.certain)
    kept = apply_source_priority(marked, {"Gebäude": "OSM"}, matches, confirmed_uncertain=[uncertain])
    assert [(item.source_kind, item.source_row_id) for item in kept] == [("OSM", 1), ("OSM", 2), ("OSM", 3)]

    assert apply_source_priority(marked, {}, matches) == marked


def test_priority_choices_count_and_suggest_per_category():
    records = [
        record("ALKIS", square(0, 0, 10)),
        record("OSM", square(1, 1, 10)),
        record("ALKIS", square(0, 50, 20), category="Grünflächen"),
        record("OSM", square(0, 50, 21), category="Grünflächen"),
        record("ALKIS", square(0, 100, 10), category="Wasserflächen"),
        record("OSM", square(0, 100, 10), category="Wasserflächen"),
    ]
    _, matches, _ = match_sources(records, SETTINGS)

    choices = {choice.category: choice for choice in priority_choices(matches, SETTINGS)}
    assert choices["Gebäude"].suggested_source == "ALKIS"
    assert choices["Grünflächen"].suggested_source == "OSM"
    assert choices["Wasserflächen"].suggested_source == "ALKIS"  # no suggestion → ALKIS
    assert choices["Gebäude"].group_count == 1 and choices["Gebäude"].record_count == 2


def test_settings_come_from_rules_file():
    settings = load_settings()
    assert settings.max_area_deviation == 0.2
    assert settings.suggested_priority["Straßen"] == "OSM"
