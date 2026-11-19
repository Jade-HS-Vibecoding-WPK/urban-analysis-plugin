"""Columns are read and named readably (M23, E29, E30)."""

import sqlite3

import pytest

from urban_analysis.contracts import ColumnDecision
from urban_analysis.data_pipeline import (
    GeoPackageImporter,
    apply_column_decisions,
    default_column_decisions,
)
from tests.test_data_pipeline import gpkg_polygon, import_osm, make_osm_geopackage


def make_columns_geopackage(path):
    """An ALKIS-like building layer and an own mapping layer without profile."""
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE gpkg_spatial_ref_sys (
                srs_name TEXT, srs_id INTEGER PRIMARY KEY,
                organization TEXT, organization_coordsys_id INTEGER
            );
            INSERT INTO gpkg_spatial_ref_sys VALUES
                ('ETRS89 / UTM zone 32N', 25832, 'EPSG', 25832);
            CREATE TABLE gpkg_geometry_columns (
                table_name TEXT, column_name TEXT, geometry_type_name TEXT,
                srs_id INTEGER
            );
            INSERT INTO gpkg_geometry_columns VALUES
                ('gebaeude', 'geom', 'MULTIPOLYGON', 25832),
                ('kartierung', 'geom', 'MULTIPOLYGON', 25832);
            CREATE TABLE gebaeude (
                fid INTEGER PRIMARY KEY, geom BLOB, objid TEXT, gfk__bez TEXT,
                hnr TEXT, anzahlgs INTEGER, xyz_intern TEXT
            );
            CREATE TABLE kartierung (
                fid INTEGER PRIMARY KEY, geom BLOB, Zustand TEXT, Bemerkung TEXT
            );
            """
        )
        first = gpkg_polygon([(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)])
        second = gpkg_polygon([(5, 1), (7, 1), (7, 3), (5, 3), (5, 1)])
        connection.executemany(
            "INSERT INTO gebaeude VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, first, "DENIAL1", "Wohngebäude", "2", 3, "a17"),
                (2, second, "DENIAL2", "Garage", "4a", 1, "b18"),
            ],
        )
        connection.execute(
            "INSERT INTO kartierung VALUES (1, ?, 'gut', 'Fassade neu')", (first,)
        )


def import_columns(path):
    return GeoPackageImporter().import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))",
        buffer_meters=0,
    )


@pytest.fixture
def result(tmp_path):
    path = tmp_path / "columns.gpkg"
    make_columns_geopackage(path)
    return import_columns(path)


def by_field(columns):
    return {column.source_field: column for column in columns}


def test_every_column_is_described_without_geometry_and_row_number(result):
    columns = by_field(result.columns_of("gebaeude"))
    assert list(columns) == ["objid", "gfk__bez", "hnr", "anzahlgs", "xyz_intern"]
    assert columns["hnr"].readable_name == "Hausnummer"
    assert columns["hnr"].examples == ("2", "4a")
    assert columns["gfk__bez"].suggested_target == "object_type"
    assert columns["objid"].suggested_target == "object_id"


def test_alkis_columns_in_the_name_list_are_known_others_are_not(result):
    columns = by_field(result.columns_of("gebaeude"))
    assert columns["hnr"].known and columns["anzahlgs"].known
    assert not columns["xyz_intern"].known
    assert columns["xyz_intern"].readable_name == "xyz_intern"


def test_own_file_without_profile_keeps_every_column(result):
    columns = by_field(result.columns_of("kartierung"))
    assert list(columns) == ["Zustand", "Bemerkung"]
    assert all(column.known for column in columns.values())


def test_unknown_columns_are_named_in_an_info_hint(result):
    hints = [issue for issue in result.issues if issue.code == "columns-not-loaded"]
    assert len(hints) == 1
    hint = hints[0]
    assert hint.severity == "info" and hint.layer_id == "gebaeude"
    assert "xyz_intern" in hint.message and "1 Spalte" in hint.message
    assert "Schritt 5" in hint.details and "xyz_intern" in hint.details
    assert hint.action == ""
    assert hint not in result.visible_issues()


def test_known_columns_are_taken_over_with_readable_names(result):
    houses = [r for r in result.harmonized_records if r.source_layer == "gebaeude"]
    assert houses[0].extra_attributes == {"Hausnummer": "2", "Geschosszahl (ALKIS)": 3}
    own = [r for r in result.harmonized_records if r.source_layer == "kartierung"][0]
    assert own.extra_attributes == {"Zustand": "gut", "Bemerkung": "Fassade neu"}
    # core fields are unchanged
    assert houses[0].attributes["object_type"] == "Wohngebäude"
    assert houses[0].attributes["object_id"] == "DENIAL1"


def test_user_can_rename_add_and_drop_columns(result):
    decisions = default_column_decisions(result.columns)
    changed = []
    for decision in decisions:
        if decision.source_field == "hnr":
            decision = ColumnDecision("gebaeude", "hnr", "keep", name="Hausnr.")
        elif decision.source_field == "xyz_intern":
            decision = ColumnDecision("gebaeude", "xyz_intern", "keep", name="Interne Nummer")
        elif decision.source_field == "anzahlgs":
            decision = ColumnDecision("gebaeude", "anzahlgs", "drop")
        changed.append(decision)

    records = apply_column_decisions(result.harmonized_records, result.columns, changed)

    house = [r for r in records if r.source_layer == "gebaeude"][1]
    assert house.extra_attributes == {"Hausnr.": "4a", "Interne Nummer": "b18"}


def test_dropping_a_suggested_column_empties_its_core_field(result):
    decisions = [
        ColumnDecision("gebaeude", "gfk__bez", "drop")
        if decision.source_field == "gfk__bez" else decision
        for decision in default_column_decisions(result.columns)
    ]
    records = apply_column_decisions(result.harmonized_records, result.columns, decisions)
    house = [r for r in records if r.source_layer == "gebaeude"][0]
    assert house.attributes["object_type"] is None
    assert house.attributes["category"] == "Gebäude"


def test_another_column_can_fill_a_core_field(result):
    decisions = [
        ColumnDecision("gebaeude", "xyz_intern", "target", target_field="object_id")
        if decision.source_field == "xyz_intern"
        else ColumnDecision("gebaeude", "objid", "keep")
        if decision.source_field == "objid"
        else decision
        for decision in default_column_decisions(result.columns)
    ]
    records = apply_column_decisions(result.harmonized_records, result.columns, decisions)
    house = [r for r in records if r.source_layer == "gebaeude"][0]
    assert house.attributes["object_id"] == "a17"
    assert house.extra_attributes["ALKIS-Objekt-ID"] == "DENIAL1"


def test_a_name_chosen_twice_is_an_error_not_silently_fixed(result):
    decisions = [
        ColumnDecision("gebaeude", "xyz_intern", "keep", name="hausnummer")
        if decision.source_field == "xyz_intern" else decision
        for decision in default_column_decisions(result.columns)
    ]
    with pytest.raises(ValueError, match="zweimal"):
        apply_column_decisions(result.harmonized_records, result.columns, decisions)


def test_osm_known_tags_become_columns_and_other_tags_is_not_loaded(tmp_path):
    path = tmp_path / "osm.gpkg"
    make_osm_geopackage(path)
    result = import_osm(path)

    columns = by_field(result.columns_of("multipolygons"))
    assert not columns["other_tags"].known
    assert columns["building"].readable_name == "Gebäudeart (OSM)" and columns["building"].known
    assert columns["shop"].known  # taken out of other_tags

    house = next(
        r for r in result.harmonized_records
        if r.source_layer == "multipolygons" and r.source_row_id == 1
    )
    assert house.extra_attributes["Straße"] == "Hauptstraße"
    assert house.extra_attributes["Geschosszahl (OSM)"] == "3"
    assert "Weitere OSM-Merkmale" not in house.extra_attributes

    line_columns = by_field(result.columns_of("lines"))
    assert line_columns["maxspeed"].readable_name == "Höchstgeschwindigkeit"
