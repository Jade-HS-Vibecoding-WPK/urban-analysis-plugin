"""Uncertain duplicates explain themselves with a real example (M24, E31)."""

import sqlite3

from urban_analysis.data_pipeline import HarmonizedRecord, describe_duplicate_groups
from tests.test_data_pipeline import (
    gpkg_polygon,
    import_alkis,
    import_houses,
    make_alkis_geopackage,
    make_house_number_geopackage,
)


def test_different_objects_at_one_place_get_differences_and_example(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path, same_object=False)

    result = import_houses(path)

    assert len(result.duplicate_groups) == 1
    group = result.duplicate_groups[0]
    assert group.group_id == "gebaeude:1"
    assert group.layer_id == "gebaeude"
    assert group.record_count == 2
    assert group.reason == "gleiche Form"
    assert [(d.source_field, d.readable_name, d.values) for d in group.differences] == [
        ("objid", "ALKIS-Objekt-ID", ("DENIAL1", "DENIAL3")),
        ("hnr", "Hausnummer", ("39", "41")),
    ]
    assert group.example_text == (
        "Hier liegen 2 Einträge „Wohngebäude“ mit genau gleicher Form übereinander. "
        "Unterschied: ALKIS-Objekt-ID „DENIAL1“ / „DENIAL3“; Hausnummer „39“ / „41“."
    )


def test_same_object_id_is_named_as_reason(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)
    area = gpkg_polygon([(20, 1), (21, 1), (21, 2), (20, 2), (20, 1)])
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE nutzung ADD COLUMN flaeche TEXT")
        connection.executemany(
            "INSERT INTO nutzung (fid, geom, objid, tn__bez, flaeche) VALUES (?, ?, 'P1', 'Weg', ?)",
            [(201, area, "100"), (202, area, "120")],
        )

    result = import_alkis(path)

    group = next(g for g in result.duplicate_groups if g.layer_id == "nutzung")
    assert group.reason == "gleiche Form und gleiche Objekt-ID"
    assert [(d.source_field, d.values) for d in group.differences] == [("flaeche", ("100", "120"))]


def test_key_column_is_hidden_behind_its_readable_twin(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path, same_object=False)
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE gebaeude ADD COLUMN gfk TEXT")
        connection.execute("UPDATE gebaeude SET gfk = CAST(fid AS TEXT), gfk__bez = 'Funktion ' || fid")

    result = import_houses(path)

    fields = [d.source_field for d in result.duplicate_groups[0].differences]
    assert "gfk__bez" in fields and "gfk" not in fields


def test_address_is_shown_only_if_all_entries_share_it():
    def record(row_id, objid, address):
        return HarmonizedRecord(
            layer_id="gebaeude",
            source_row_id=row_id,
            attributes={"object_type": "Garage", "address": address, "object_id": objid},
            duplicate_group="gebaeude:1",
            source_layer="gebaeude",
            source_attributes={"fid": row_id, "geom": b"\x00", "objid": objid},
        )

    same = describe_duplicate_groups([record(1, "A", "Hauptstraße 2"), record(2, "B", "Hauptstraße 2")])
    assert same[0].example_text.startswith("Hier liegen 2 Einträge „Garage“ (Hauptstraße 2) mit")

    other = describe_duplicate_groups([record(1, "A", "Hauptstraße 2"), record(2, "B", "Weg 1")])
    assert "(" not in other[0].example_text.split("übereinander")[0]


def test_no_groups_without_uncertain_duplicates(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path)  # corner house: combined, nothing to ask

    result = import_houses(path)

    assert result.duplicate_groups == []


def test_empty_values_are_shown_as_leer():
    rows = [("A", "3"), ("B", None)]
    records = [
        HarmonizedRecord(
            layer_id="gebaeude",
            source_row_id=index,
            attributes={"object_type": "Garage", "object_id": objid},
            duplicate_group="gebaeude:1",
            source_layer="gebaeude",
            source_attributes={"objid": objid, "anzahlgs": floors},
        )
        for index, (objid, floors) in enumerate(rows, start=1)
    ]
    group = describe_duplicate_groups(records)[0]
    assert group.differences[1].readable_name == "Geschosszahl (ALKIS)"
    assert group.differences[1].values == ("3", "(leer)")
