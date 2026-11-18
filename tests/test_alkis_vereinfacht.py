"""M12: profile for "ALKIS vereinfacht" from the WFS services of 11 Länder.

The test GeoPackage looks like the download (W11) saves it: layers
GebaeudeBauwerk, Nutzung and Flurstueck without the ``ave:`` prefix, columns
as delivered by the services (checked with a real sample on 2026-11-18).
"""

import sqlite3

from urban_analysis.data_pipeline import GeoPackageImporter
from urban_analysis.mapping import default_mapping_rules

from test_data_pipeline import square


def make_ave_geopackage(path):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE gpkg_spatial_ref_sys (
                srs_name TEXT, srs_id INTEGER PRIMARY KEY,
                organization TEXT, organization_coordsys_id INTEGER
            );
            INSERT INTO gpkg_spatial_ref_sys VALUES ('ETRS89 / UTM zone 32N', 25832, 'EPSG', 25832);
            CREATE TABLE gpkg_geometry_columns (
                table_name TEXT, column_name TEXT, geometry_type_name TEXT, srs_id INTEGER
            );
            INSERT INTO gpkg_geometry_columns VALUES
                ('GebaeudeBauwerk', 'geom', 'MULTIPOLYGON', 25832),
                ('Nutzung', 'geom', 'MULTIPOLYGON', 25832),
                ('Flurstueck', 'geom', 'MULTIPOLYGON', 25832);
            CREATE TABLE GebaeudeBauwerk (
                fid INTEGER PRIMARY KEY, geom BLOB, oid TEXT, aktualit TEXT,
                gebnutzbez TEXT, funktion TEXT, gfkzshh TEXT, anzahlgs INTEGER,
                gmdschl TEXT, lagebeztxt TEXT
            );
            CREATE TABLE Nutzung (
                fid INTEGER PRIMARY KEY, geom BLOB, oid TEXT, aktualit TEXT,
                nutzart TEXT, bez TEXT, name TEXT
            );
            CREATE TABLE Flurstueck (
                fid INTEGER PRIMARY KEY, geom BLOB, oid TEXT, flstkennz TEXT, flaeche REAL
            );
            """
        )
        connection.executemany(
            "INSERT INTO GebaeudeBauwerk (fid, geom, oid, gebnutzbez, funktion, anzahlgs, lagebeztxt) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, square(1, 1), "DENI01", "Gebäude", "Wohngebäude", 3, "Hauptstraße 2"),
                (2, square(3, 1), "DENI02", "Gebäude", "Garage", None, None),
                (3, square(5, 1), "DENI03", "Gebäude", "Wohngebäude", 2, "Eckweg 4, 6"),
                (4, square(7, 1), "DENI04", "Sonstiges Bauwerk oder sonstige Einrichtung", "Überdachung", None, None),
                (5, square(1, 3), "DENI05", "Bauteil", "Durchfahrt im Gebäude", None, None),
            ],
        )
        connection.executemany(
            "INSERT INTO Nutzung (fid, geom, oid, nutzart, bez) VALUES (?, ?, ?, ?, ?)",
            [
                (1, square(1, 5), "DENU01", "Weg", "Rad- und Fußweg"),
                (2, square(3, 5), "DENU02", "Straßenverkehr", None),
                (3, square(5, 5), "DENU03", "Straßenverkehr", "Begleitfläche Straßenverkehr"),
                (4, square(7, 5), "DENU04", "Sport-, Freizeit- und Erholungsfläche", "Park"),
                (5, square(1, 7), "DENU05", "Wohnbaufläche", None),
                (6, square(3, 7), "DENU06", "Fließgewässer", None),
                (7, square(5, 7), "DENU07", "Industrie- und Gewerbefläche", "Handel und Dienstleistung"),
            ],
        )
        connection.execute("INSERT INTO Flurstueck VALUES (1, ?, 'DEFL01', '0300001', 120.0)", (square(1, 9),))


def import_ave(path):
    return GeoPackageImporter().import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))",
        buffer_meters=0,
    )


def records(result, table):
    return {record.source_row_id: record for record in result.harmonized_records if record.source_layer == table}


def test_profile_is_found_by_layer_name_and_oid():
    rules = default_mapping_rules()
    building = rules.profile_for("GebaeudeBauwerk", ("oid", "funktion", "gebnutzbez"))
    assert building is not None and building.profile_name == "ALKIS vereinfacht"
    assert rules.profile_for("GebaeudeBauwerk", ("funktion",)) is None
    # the own ALKIS export keeps its profile
    assert rules.profile_for("gebaeude", ("objid", "gfk__bez")).profile_name == "ALKIS"


def test_buildings_are_separated_from_roofs_and_building_parts(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_ave_geopackage(path)

    buildings = records(import_ave(path), "GebaeudeBauwerk")

    summary = {fid: (r.layer_id, r.attributes["category"], r.attributes["object_type"]) for fid, r in buildings.items()}
    assert summary == {
        1: ("GebaeudeBauwerk_gebaeude", "Gebäude", "Wohngebäude"),
        2: ("GebaeudeBauwerk_gebaeude", "Gebäude", "Garage"),
        3: ("GebaeudeBauwerk_gebaeude", "Gebäude", "Wohngebäude"),
        4: ("GebaeudeBauwerk_bauwerke", "Bauwerke und Überdachungen", "Überdachung"),
        5: ("GebaeudeBauwerk_gebaeudeteile", "Gebäudeteile", "Durchfahrt im Gebäude"),
    }


def test_object_id_address_and_floors_come_from_the_service_columns(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_ave_geopackage(path)

    result = import_ave(path)
    buildings = records(result, "GebaeudeBauwerk")

    first = buildings[1].attributes
    assert (first["object_id"], first["address"], first["floors"]) == ("DENI01", "Hauptstraße 2", 3)
    assert buildings[3].attributes["address"] == "Eckweg 4, 6"  # several numbers stay together
    assert (buildings[2].attributes["address"], buildings[2].attributes["floors"]) == (None, None)
    targets = {(s.layer_id, s.target_field): s.source_field for s in result.attribute_suggestions}
    assert targets[("GebaeudeBauwerk", "floors")] == "anzahlgs"
    assert ("GebaeudeBauwerk", "address") not in targets  # the profile builds it


def test_land_use_type_and_detail_from_two_columns(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_ave_geopackage(path)

    land_use = records(import_ave(path), "Nutzung")

    summary = {
        fid: (r.attributes["category"], r.attributes["object_type"], r.attributes["object_detail"])
        for fid, r in land_use.items()
    }
    assert summary == {
        1: ("Fuß- und Radwege", "Weg", "Rad- und Fußweg"),
        2: ("Straßen", "Straßenverkehr", None),
        3: ("Straßen", "Straßenverkehr", "Begleitfläche Straßenverkehr"),
        4: ("Grünflächen", "Sport-, Freizeit- und Erholungsfläche", "Park"),
        5: ("Nutzungsflächen", "Wohnbaufläche", None),
        6: ("Wasserflächen", "Fließgewässer", None),
        7: ("Nutzungsflächen", "Industrie- und Gewerbefläche", "Handel und Dienstleistung"),
    }


def test_no_false_hints_for_a_clean_service_download(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_ave_geopackage(path)

    codes = {issue.code for issue in import_ave(path).issues}

    assert "missing-category" not in codes
    assert "uncertain-duplicate" not in codes
