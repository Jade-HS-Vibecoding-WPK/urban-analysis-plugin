"""Vertretung Mac (19.11.2026, QGIS-Test): columns of a result layer –
Objekt-ID first, origin last, empty columns left out (QGIS-free part of
outputs.py)."""

from urban_analysis.data_pipeline import TARGET_FIELDS, HarmonizedRecord
from urban_analysis.outputs import (
    ALWAYS_FIELDS,
    COLUMN_ORDER_FRONT,
    COLUMN_ORDER_ORIGIN,
    COLUMN_ORDER_PROPERTIES,
    COLUMN_ORDER_WHAT,
    COLUMN_ORDER_WHERE,
    column_value,
    result_columns,
)


def record(attributes, extra=None):
    return HarmonizedRecord("haltestellen", 1, attributes, extra_attributes=extra or {})


BUS_STOPS = [
    record(
        {"object_id": "node/1", "object_type": "Haltepunkt", "category": "ÖPNV-Haltestellen",
         "source": "© OpenStreetMap-Mitwirkende", "source_name": "osm.gpkg", "floors": None},
        {"Straße": None, "Name": "Trommelweg", "Betreiber": "VWG", "Hausnummer": ""},
    ),
    record(
        {"object_id": "node/2", "object_type": "Bushaltestelle", "category": "ÖPNV-Haltestellen",
         "source": "© OpenStreetMap-Mitwirkende", "source_name": "osm.gpkg"},
        {"Name": "Bogenstraße", "Betreiber": None},
    ),
]


def names(columns):
    return [field_name for _where, _key, field_name, _kind in columns]


def test_every_target_field_has_a_place_in_the_order():
    ordered = (COLUMN_ORDER_FRONT + COLUMN_ORDER_WHAT + COLUMN_ORDER_WHERE
               + COLUMN_ORDER_PROPERTIES + COLUMN_ORDER_ORIGIN)
    assert sorted(ordered) == sorted(TARGET_FIELDS)
    assert set(ALWAYS_FIELDS) <= set(ordered)


def test_id_first_name_then_what_origin_last_and_no_empty_columns():
    columns = result_columns(BUS_STOPS)
    assert names(columns) == [
        "object_id", "Name", "object_type", "category", "Betreiber", "source", "source_name",
    ]


def test_always_fields_stay_even_if_empty():
    columns = result_columns([record({"object_id": "x"})])
    assert names(columns) == ["object_id", "object_type", "category", "source"]


def test_properties_come_after_where_and_before_other_source_columns():
    columns = result_columns([record(
        {"object_id": "a", "address": "Weg 1", "floors": 3, "year": 1910},
        {"Höhe (m)": "9", "Name": "Haus"},
    )])
    assert names(columns) == [
        "object_id", "Name", "object_type", "category", "address", "floors", "year", "Höhe (m)", "source",
    ]


def test_values_follow_the_columns():
    columns = result_columns(BUS_STOPS)
    assert [column_value(column, BUS_STOPS[1]) for column in columns] == [
        "node/2", "Bogenstraße", "Bushaltestelle", "ÖPNV-Haltestellen", None,
        "© OpenStreetMap-Mitwirkende", "osm.gpkg",
    ]
