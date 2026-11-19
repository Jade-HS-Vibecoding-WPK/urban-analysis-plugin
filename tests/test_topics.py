"""Tests for the map topics catalog and classification (M25, E36, S16).

All data is artificial: a few records per topic, built in the test code.
"""

import copy
import json

import pytest

from urban_analysis.contracts import (
    TOPIC_CLASS_EMPTY,
    TOPIC_GEOMETRIES,
    TOPIC_LIMIT,
    PipelineResult,
    TopicSelection,
    ValidationIssue,
)
from urban_analysis.data_pipeline import HarmonizedRecord
from urban_analysis.topics import (
    CATALOG_FILE,
    classify_topics,
    geometry_kind,
    parse_rule,
    record_values,
    topic_catalog,
)
from urban_analysis.ui_contract import TOPIC_NAMES

AREA = "POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))"
LINE = "LINESTRING(0 0, 50 0)"
POINT = "POINT(5 5)"


def osm(tags, geometry=AREA, layer="multipolygons", category=None, other=None):
    """An OSM record: ``tags`` are columns, ``other`` goes into other_tags."""
    row = dict(tags)
    if other:
        row["other_tags"] = ",".join(f'"{key}"=>"{value}"' for key, value in other.items())
    return HarmonizedRecord(
        layer_id=layer,
        source_row_id=len(row),
        attributes={"category": category},
        geometry=geometry,
        source_layer=layer,
        source_attributes=row,
        source_kind="OSM",
    )


def alkis(columns, geometry=AREA, layer="Nutzung", category=None):
    return HarmonizedRecord(
        layer_id=layer,
        source_row_id=1,
        attributes={"category": category},
        geometry=geometry,
        source_layer=layer,
        source_attributes=dict(columns),
        source_kind="ALKIS",
    )


def result_with(records, issues=()):
    return PipelineResult(
        contract_version="test",
        project_crs="EPSG:25832",
        study_area_wkt=AREA,
        harmonized_records=list(records),
        issues=list(issues),
    )


def all_classes(topic_id):
    (info,) = [info for info in topic_catalog() if info.topic_id == topic_id]
    return TopicSelection(topic_id, class_ids=tuple(item.class_id for item in info.classes))


def classes_of(records, topic_id, selection=None):
    result = classify_topics(result_with(records), [selection or all_classes(topic_id)])
    return [record.topic_classes.get(topic_id) for record in result.harmonized_records]


# --- catalog ----------------------------------------------------------------


def test_catalog_has_all_seven_topics_with_the_contract_ids_and_names():
    catalog = topic_catalog()
    assert [info.topic_id for info in catalog] == list(TOPIC_NAMES)
    for info in catalog:
        assert info.name == TOPIC_NAMES[info.topic_id]
        assert info.description and info.classes and info.limits and info.source_tips


def test_every_class_is_complete_and_readable():
    raw = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    for topic in raw["themen"]:
        for item in topic["klassen"]:
            assert item["geometrie"] in TOPIC_GEOMETRIES
            assert item["farbe"].startswith("#") and len(item["farbe"]) == 7
            assert set(item["regeln"]) == {"osm", "alkis"}
            assert item["regeln"]["osm"] or item["regeln"]["alkis"], item["id"]
            for text in item["regeln"]["osm"] + item["regeln"]["alkis"]:
                parse_rule(text)


def test_uncertain_classes_are_marked_vermutlich():
    uncertain = {(info.topic_id, item.class_id) for info in topic_catalog() for item in info.classes if item.uncertain}
    assert ("freiraum", "treffpunkte") in uncertain
    assert ("gruen_wasser_klima", "versiegelt") in uncertain
    assert ("geschichte_stadtbild", "markante_gebaeude") in uncertain
    assert ("nutzungen", "wohnen") not in uncertain


def test_scales_read_from_the_catalog():
    (bebauung,) = [info for info in topic_catalog() if info.topic_id == "bebauung"]
    scale = next(item for item in bebauung.scales if item.scale_id == "geschosse_alkis")
    assert scale.field == "Geschosszahl (ALKIS)"
    assert scale.steps[0].lower is None and scale.steps[-1].upper is None
    (versorgung,) = [info for info in topic_catalog() if info.topic_id == "versorgung"]
    assert any(item.field == "Abstand Nahversorgung (m)" for item in versorgung.scales)


def test_catalog_with_unknown_topic_id_is_refused(tmp_path):
    path = tmp_path / "topics.json"
    path.write_text(json.dumps({"themen": [{"id": "erfunden", "klassen": []}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="TOPIC_NAMES"):
        topic_catalog(path)


def test_unreadable_rule_is_refused():
    with pytest.raises(ValueError, match="nicht lesbar"):
        parse_rule("building")


# --- rules and values -------------------------------------------------------


def test_rules_see_columns_other_tags_and_own_keys():
    record = osm({"highway": "residential"}, LINE, "lines", category="Straßen", other={"bridge": "yes"})
    values = record_values(record)
    assert values["highway"] == "residential" and values["bridge"] == "yes"
    assert values["kategorie"] == "Straßen" and values["ebene"] == "lines"


def test_geometry_kind():
    assert geometry_kind(osm({}, AREA)) == "Fläche"
    assert geometry_kind(osm({}, LINE)) == "Linie"
    assert geometry_kind(osm({}, POINT)) == "Punkt"
    assert geometry_kind(osm({}, None)) is None


# --- one test per topic -----------------------------------------------------


def test_bebauung():
    records = [
        osm({"building": "garage"}),
        osm({"building": "yes"}),
        alkis({"gebnutzbez": "Gebäude", "funktion": "Wohnhaus"}, layer="GebaeudeBauwerk", category="Gebäude"),
        osm({"highway": "primary"}, LINE, "lines", other={"bridge": "viaduct"}),
        osm({"highway": "primary"}, LINE, "lines", other={"bridge": "no"}),
        alkis({"flstkennz": "x"}, layer="Flurstueck"),
    ]
    assert classes_of(records, "bebauung") == [
        "nebengebaeude", "hauptgebaeude", "hauptgebaeude", "bruecken", None, "flurstuecke",
    ]


def test_nutzungen_from_osm_and_alkis():
    records = [
        osm({"shop": "bakery"}, POINT, "points"),
        osm({"amenity": "cafe"}, POINT, "points"),
        osm({}, POINT, "points", other={"office": "lawyer"}),
        osm({}, POINT, "points", other={"craft": "carpenter"}),
        osm({"building": "apartments"}),
        alkis({"nutzart": "Wohnbaufläche"}),
        alkis({"tn__bez": "Fläche gemischter Nutzung, Geschäftsgebiet"}),
        osm({"building": "yes"}),
    ]
    assert classes_of(records, "nutzungen") == [
        "einzelhandel", "gastronomie", "dienstleistungen", "gewerbe_industrie",
        "wohnen", "wohnen", "gemischt", None,
    ]


def test_versorgung_uses_pipeline_category_and_areas_count_as_points():
    records = [
        osm({"shop": "supermarket"}, POINT, "points", category="Nahversorgung"),
        osm({"amenity": "pharmacy"}, POINT, "points"),
        osm({"amenity": "school"}, AREA),  # school grounds as area
        osm({"amenity": "library"}, POINT, "points"),
        osm({"leisure": "pitch"}),
        osm({"shop": "clothes"}, POINT, "points"),
    ]
    assert classes_of(records, "versorgung") == [
        "nahversorgung", "gesundheit", "bildung_betreuung", "kultur", "sport", None,
    ]


def test_freiraum():
    records = [
        osm({"place": "square"}),
        alkis({"nutzart": "Platz", "bez": "Parkplatz"}),
        alkis({"nutzart": "Platz", "bez": "Marktplatz"}),
        osm({"leisure": "playground"}),
        osm({"leisure": "park"}),
        osm({"amenity": "bench"}, POINT, "points"),
        osm({"man_made": "pier"}, LINE, "lines"),  # a pier drawn as line is not a point
        osm({"amenity": "fountain"}, POINT, "points"),
    ]
    assert classes_of(records, "freiraum") == [
        "plaetze_fussgaengerzonen", None, "plaetze_fussgaengerzonen", "spielplaetze", "parks",
        "sitzgelegenheiten", None, "treffpunkte",
    ]


def test_mobilitaet_checks_side_tags_on_street_lines():
    records = [
        osm({"highway": "footway"}, LINE, "lines"),
        osm({"highway": "secondary"}, LINE, "lines", other={"cycleway:right": "lane"}),
        osm({"highway": "secondary"}, LINE, "lines", other={"cycleway": "no"}),
        osm({"highway": "tertiary_link"}, LINE, "lines"),
        osm({"highway": "living_street"}, LINE, "lines"),
        osm({"railway": "tram"}, LINE, "lines"),
        osm({"highway": "bus_stop"}, POINT, "points", category="ÖPNV-Haltestellen"),
        osm({"highway": "crossing"}, POINT, "points"),
        osm({"amenity": "parking"}),
        alkis({"nutzart": "Straßenverkehr"}),
        osm({"highway": "residential"}, AREA),  # a street area is not a line class
    ]
    assert classes_of(records, "mobilitaet") == [
        "fuss_radwege", "radverkehr_strasse", "hauptstrassen", "sammelstrassen", "wohnstrassen",
        "bahn", "haltestellen", "querungen", "stellplaetze", "verkehrsflaechen", None,
    ]


def test_gruen_wasser_klima():
    records = [
        osm({"natural": "wood"}),
        alkis({"nutzart": "Friedhof"}),
        osm({"landuse": "farmland"}),
        osm({"natural": "water"}),
        alkis({"tn__bez": "Fliessgewässer"}),
        osm({"waterway": "river"}, LINE, "lines"),
        osm({"natural": "tree_row"}, LINE, "lines"),
        osm({}, POINT, "points", other={"natural": "tree"}),
        osm({"building": "house"}),
    ]
    assert classes_of(records, "gruen_wasser_klima") == [
        "wald", "gruenflaechen", "landwirtschaft", "gewaesser", "gewaesser", "wasserlaeufe",
        "baumreihen_hecken", "baeume", "versiegelt",
    ]


def test_geschichte_stadtbild():
    records = [
        osm({"building": "yes"}, other={"heritage": "4"}),
        osm({}, POINT, "points", other={"historic": "memorial"}),
        osm({}, POINT, "points", other={"historic": "ruins"}),
        osm({}, POINT, "points", other={"tourism": "viewpoint"}),
        osm({}, POINT, "points", other={"tourism": "artwork"}),
        osm({"building": "church"}),
        alkis({"funktion": "Kirche"}, layer="GebaeudeBauwerk", category="Gebäude"),
        osm({"building": "yes"}, other={"heritage": "no"}),
    ]
    assert classes_of(records, "geschichte_stadtbild") == [
        "baudenkmale", "denkmaeler_gedenkorte", "historische_orte", "aussichtspunkte",
        "sehenswuerdigkeiten", "markante_gebaeude", "markante_gebaeude", None,
    ]


# --- selection, overlay and hints -------------------------------------------


def test_one_object_in_several_topics_but_one_class_per_topic():
    cafe = osm({"amenity": "cafe"}, POINT, "points")
    result = classify_topics(result_with([cafe]), [all_classes("nutzungen"), all_classes("freiraum")])
    assert result.harmonized_records[0].topic_classes == {"nutzungen": "gastronomie", "freiraum": "treffpunkte"}


def test_unticked_class_does_not_fall_through_to_the_next_rule():
    church_heritage = osm({"building": "church"}, other={"heritage": "2"})
    selection = TopicSelection("geschichte_stadtbild", class_ids=("markante_gebaeude",))
    assert classes_of([church_heritage], "geschichte_stadtbild", selection) == [None]


def test_input_is_not_changed_and_old_classes_are_replaced():
    record = osm({"shop": "bakery"}, POINT, "points")
    record = HarmonizedRecord(**{**record.__dict__, "topic_classes": {"bebauung": "hauptgebaeude"}})
    original = result_with([record], [ValidationIssue("andere", "bleibt")])
    before = copy.deepcopy(original)

    first = classify_topics(original, [all_classes("nutzungen")])
    again = classify_topics(first, [all_classes("nutzungen")])

    assert original == before
    assert first.harmonized_records[0].topic_classes == {"nutzungen": "einzelhandel"}
    assert first.selected_topics == [all_classes("nutzungen")]
    assert [issue.code for issue in again.issues].count(TOPIC_LIMIT) == 1
    assert again.issues[0].code == "andere"


def test_selection_defaults_to_result_selected_topics():
    result = result_with([osm({"shop": "bakery"}, POINT, "points")])
    result.selected_topics = [TopicSelection("nutzungen", class_ids=("einzelhandel",))]
    classified = classify_topics(result)
    assert classified.harmonized_records[0].topic_classes == {"nutzungen": "einzelhandel"}


def test_limit_hint_per_topic_with_vermutlich_and_tips():
    result = classify_topics(result_with([]), [all_classes("freiraum"), all_classes("bebauung")])
    limits = [issue for issue in result.issues if issue.code == TOPIC_LIMIT]
    assert [issue.rule for issue in limits] == [TOPIC_NAMES["freiraum"], TOPIC_NAMES["bebauung"]]
    assert all(issue.severity == "info" for issue in limits)
    assert "Aufenthaltsqualität" in limits[0].details
    assert "vermutlich" in limits[0].details and "Treffpunkte" in limits[0].details
    assert "vermutlich" not in limits[1].details
    assert limits[0].action


def test_empty_class_and_empty_scale_hints():
    records = [osm({"building": "yes"})]
    selection = TopicSelection(
        "bebauung", class_ids=("hauptgebaeude", "bruecken"), scale_ids=("geschosse_osm",)
    )
    result = classify_topics(result_with(records), [selection])
    empty = [issue for issue in result.issues if issue.code == TOPIC_CLASS_EMPTY]
    assert len(empty) == 2
    assert "„Brücken“" in empty[0].message and empty[0].severity == "info"
    assert "Geschosszahl (OSM)" in empty[1].message

    with_floors = HarmonizedRecord(**{**records[0].__dict__, "extra_attributes": {"Geschosszahl (OSM)": 3}})
    result = classify_topics(result_with([with_floors]), [selection])
    assert [issue for issue in result.issues if issue.code == TOPIC_CLASS_EMPTY][0].message.count("Brücken") == 1
    assert len([issue for issue in result.issues if issue.code == TOPIC_CLASS_EMPTY]) == 1


def test_unknown_ids_in_the_selection_are_refused():
    with pytest.raises(ValueError, match="Unbekanntes Thema"):
        classify_topics(result_with([]), [TopicSelection("erfunden", class_ids=("x",))])
    with pytest.raises(ValueError, match="unbekannte Klasse"):
        classify_topics(result_with([]), [TopicSelection("bebauung", class_ids=("x",))])
    with pytest.raises(ValueError, match="unbekannte Stufe"):
        classify_topics(result_with([]), [TopicSelection("bebauung", scale_ids=("x",))])
