import sqlite3
import struct
from dataclasses import replace

import pytest

from urban_analysis.mapping import default_mapping_rules
from urban_analysis.data_pipeline import (
    GeoPackageImportError,
    GeoPackageImporter,
    apply_attribute_decisions,
    apply_data_source,
    merge_confirmed_duplicates,
)


def wkb_point(x, y):
    return struct.pack("<BIdd", 1, 1, x, y)


def wkb_polygon(ring):
    data = struct.pack("<BIII", 1, 3, 1, len(ring))
    for x, y in ring:
        data += struct.pack("<dd", x, y)
    return data


def gpkg_blob(wkb):
    return b"GP\x00\x01" + struct.pack("<i", 25832) + wkb


def gpkg_point(x, y):
    return gpkg_blob(wkb_point(x, y))


def gpkg_polygon(ring):
    return gpkg_blob(wkb_polygon(ring))


def make_geopackage(path):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE gpkg_spatial_ref_sys (
                srs_name TEXT, srs_id INTEGER PRIMARY KEY,
                organization TEXT, organization_coordsys_id INTEGER
            );
            INSERT INTO gpkg_spatial_ref_sys VALUES
                ('WGS 84 / UTM zone 32N', 25832, 'EPSG', 25832);
            CREATE TABLE gpkg_geometry_columns (
                table_name TEXT, column_name TEXT, geometry_type_name TEXT,
                srs_id INTEGER
            );
            INSERT INTO gpkg_geometry_columns VALUES
                ('buildings', 'geom', 'POLYGON', 25832);
            CREATE TABLE buildings (
                fid INTEGER PRIMARY KEY, geom BLOB, type TEXT, area TEXT,
                category TEXT, year TEXT
            );
            """
        )
        house = gpkg_polygon([(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)])
        connection.executemany(
            "INSERT INTO buildings VALUES (?, ?, 'house', '12,5', 'Gebäude', '2020')",
            [(1, house), (2, house)],
        )


def test_imports_geopackage_and_harmonizes_duplicate_rows(tmp_path):
    path = tmp_path / "sample.gpkg"
    make_geopackage(path)

    result = GeoPackageImporter().import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 10 0, 10 10, 0 0))",
        buffer_meters=250,
    )

    assert result.buffer_meters == 250
    assert result.layers[0].geometry_type == "POLYGON"
    assert result.layers[0].category == "Gebäude"
    assert len(result.harmonized_records) == 1
    assert result.harmonized_records[0].attributes["area_m2"] == 12.5
    assert result.harmonized_records[0].attributes["year"] == 2020
    assert any(issue.code == "duplicate-row" for issue in result.issues)


def test_import_requires_valid_geopackage_and_project_setup(tmp_path):
    with pytest.raises(GeoPackageImportError):
        GeoPackageImporter().import_file(
            tmp_path / "missing.gpkg",
            project_crs="EPSG:25832",
            study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
        )

    invalid_path = tmp_path / "invalid.gpkg"
    invalid_path.write_bytes(b"not sqlite")
    with pytest.raises(GeoPackageImportError):
        GeoPackageImporter().import_file(
            invalid_path,
            project_crs="EPSG:25832",
            study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
        )

    path = tmp_path / "valid.gpkg"
    make_geopackage(path)
    with pytest.raises(ValueError, match="must not be negative"):
        GeoPackageImporter().import_file(
            path,
            project_crs="EPSG:25832",
            study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
            buffer_meters=-1,
        )


def test_maps_denial_tower_fields_to_common_schema(tmp_path):
    path = tmp_path / "denial.gpkg"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE gpkg_spatial_ref_sys (
                srs_name TEXT, srs_id INTEGER PRIMARY KEY,
                organization TEXT, organization_coordsys_id INTEGER
            );
            INSERT INTO gpkg_spatial_ref_sys VALUES
                ('WGS 84 / UTM zone 32N', 25832, 'EPSG', 25832);
            CREATE TABLE gpkg_geometry_columns (
                table_name TEXT, column_name TEXT, geometry_type_name TEXT,
                srs_id INTEGER
            );
            INSERT INTO gpkg_geometry_columns VALUES
                ('towers', 'wkt_geom', 'POINT', 25832);
            CREATE TABLE towers (
                fid INTEGER PRIMARY KEY, objid TEXT, ken TEXT, ken__bez TEXT,
                bwf TEXT, bwf__bez TEXT, untermerkmal TEXT, wkt_geom TEXT
            );
            INSERT INTO towers VALUES
                (1, 'DENIAL1100003tFJ', '51001', 'Turm', '1002',
                 'Kirchturm, Glockenturm', 'xxx', 'POINT (0 0)');
            """
        )

    result = GeoPackageImporter().import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
    )

    mapping = {
        suggestion.source_field: suggestion.target_field
        for suggestion in result.attribute_suggestions
    }
    assert mapping["ken__bez"] == "object_type"
    assert mapping["bwf__bez"] == "category"
    assert mapping["untermerkmal"] == "status"
    assert result.harmonized_records[0].attributes["object_type"] == "Turm"
    assert result.harmonized_records[0].attributes["category"] == "Kirchturm, Glockenturm"
    assert result.harmonized_records[0].attributes["status"] == "xxx"


def make_clipping_geopackage(path, *, srs_rows=None, srs_id=25832):
    """Points around a triangular study area plus edge cases for clipping."""
    srs_rows = srs_rows or [("ETRS89 / UTM zone 32N", 25832, "EPSG", 25832, "undefined")]
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE gpkg_spatial_ref_sys (
                srs_name TEXT, srs_id INTEGER PRIMARY KEY,
                organization TEXT, organization_coordsys_id INTEGER, definition TEXT
            );
            CREATE TABLE gpkg_geometry_columns (
                table_name TEXT, column_name TEXT, geometry_type_name TEXT,
                srs_id INTEGER
            );
            CREATE TABLE places (fid INTEGER PRIMARY KEY, geom BLOB, typ TEXT);
            """
        )
        connection.executemany("INSERT INTO gpkg_spatial_ref_sys VALUES (?, ?, ?, ?, ?)", srs_rows)
        connection.execute(
            "INSERT INTO gpkg_geometry_columns VALUES ('places', 'geom', 'GEOMETRY', ?)",
            (srs_id,),
        )
        connection.executemany(
            "INSERT INTO places VALUES (?, ?, ?)",
            [
                (1, gpkg_point(10, 10), "innen"),
                (2, gpkg_point(-30, 10), "im Puffer"),
                (3, gpkg_point(-80, 10), "außerhalb"),
                (4, gpkg_point(90, 90), "Rechteck-Ecke"),
                (5, gpkg_polygon([(80, -20), (120, -20), (120, 20), (80, 20), (80, -20)]), "über der Grenze"),
                (6, None, "ohne Geometrie"),
                (7, b"GP\x00\x01" + b"\x00" * 4, "kaputt"),
            ],
        )


TRIANGLE = "POLYGON ((0 0, 100 0, 0 100, 0 0))"


def import_places(path, **kwargs):
    options = {"project_crs": "EPSG:25832", "study_area_wkt": TRIANGLE, "buffer_meters": 50}
    options.update(kwargs)
    return GeoPackageImporter().import_file(path, **options)


def issue_codes(result):
    return {issue.code for issue in result.issues}


def test_clips_to_study_area_polygon_with_buffer(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(path)

    result = import_places(path)

    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 5]
    assert {"missing-geometry", "unreadable-geometry", "clip-summary"} <= issue_codes(result)
    assert "crs-mismatch" not in issue_codes(result)
    summary = next(issue for issue in result.issues if issue.code == "clip-summary")
    assert "3 von 7" in summary.message


def test_buffer_zero_keeps_only_touching_features(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(path)

    result = import_places(path, buffer_meters=0)

    assert [record.source_row_id for record in result.harmonized_records] == [1, 5]


def test_crs_mismatch_is_an_error_and_layer_is_not_clipped(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(
        path,
        srs_rows=[("DHDN / 3-degree Gauss-Kruger zone 3", 31467, "EPSG", 31467, "undefined")],
        srs_id=31467,
    )

    result = import_places(path)

    assert result.harmonized_records == []
    mismatch = next(issue for issue in result.issues if issue.code == "crs-mismatch")
    assert mismatch.severity == "error"
    assert [layer.layer_id for layer in result.layers] == ["places"]


def test_identifies_epsg_from_definition_when_organization_is_none(tmp_path):
    path = tmp_path / "places.gpkg"
    definition = (
        'PROJCS["ETRS89 / UTM zone 32N",GEOGCS["ETRS89",DATUM["European_Terrestrial_Reference_System_1989",'
        'SPHEROID["GRS 1980",6378137,298.257222101]]],PROJECTION["Transverse_Mercator"],UNIT["metre",1]]'
    )
    make_clipping_geopackage(
        path,
        srs_rows=[("ETRS89 / UTM zone 32N", 100000, "NONE", 100000, definition)],
        srs_id=100000,
    )

    result = import_places(path)

    assert {"crs-mismatch", "crs-unverified"}.isdisjoint(issue_codes(result))
    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 5]


def test_unknown_crs_is_clipped_but_requires_confirmation(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(
        path,
        srs_rows=[("Undefined Cartesian SRS", -1, "NONE", -1, "undefined")],
        srs_id=-1,
    )

    result = import_places(path)

    unverified = next(issue for issue in result.issues if issue.code == "crs-unverified")
    assert unverified.requires_confirmation
    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 5]


def test_geographic_crs_with_metre_buffer_is_rejected(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(
        path,
        srs_rows=[("WGS 84", 4326, "EPSG", 4326, 'GEOGCS["WGS 84",DATUM["WGS_1984"]]')],
        srs_id=4326,
    )

    result = import_places(path, project_crs="EPSG:4326")

    assert result.harmonized_records == []
    assert "geographic-crs-buffer" in issue_codes(result)


def test_invalid_study_area_is_reported_and_nothing_is_imported(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(path)

    result = import_places(path, study_area_wkt="LINESTRING (0 0, 10 10)")

    assert result.harmonized_records == []
    issue = next(issue for issue in result.issues if issue.code == "invalid-study-area")
    assert issue.severity == "error"


def test_same_attributes_with_different_geometry_are_not_duplicates(tmp_path):
    path = tmp_path / "sample.gpkg"
    make_geopackage(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO buildings VALUES (3, ?, 'house', '12,5', 'Gebäude', '2020')",
            (gpkg_polygon([(5, 1), (7, 1), (7, 3), (5, 3), (5, 1)]),),
        )

    result = GeoPackageImporter().import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 10 0, 10 10, 0 0))",
    )

    assert [record.source_row_id for record in result.harmonized_records] == [1, 3]
    duplicate = next(issue for issue in result.issues if issue.code == "duplicate-row")
    assert duplicate.message == "buildings: 1 Eintrag war doppelt (komplett gleich) und wurde automatisch entfernt."


def make_house_number_geopackage(path, *, same_object=True):
    """One building stored once per house number, as in ALKIS exports.

    With ``same_object=False`` the rows at the same place carry different
    object IDs, i.e. they really are different objects lying on top of each
    other.
    """
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
                ('gebaeude', 'geom', 'MULTIPOLYGON', 25832);
            CREATE TABLE gebaeude (
                fid INTEGER PRIMARY KEY, geom BLOB, objid TEXT, gfk__bez TEXT, hnr TEXT
            );
            """
        )
        house = gpkg_polygon([(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)])
        other = gpkg_polygon([(5, 1), (7, 1), (7, 3), (5, 3), (5, 1)])
        connection.executemany(
            "INSERT INTO gebaeude VALUES (?, ?, ?, 'Wohngebäude', ?)",
            [
                (1, house, "DENIAL1", "39"),
                (2, house, "DENIAL1" if same_object else "DENIAL3", "41"),
                (3, house, "DENIAL1" if same_object else "DENIAL3", "41"),
                (4, other, "DENIAL2", "1"),
            ],
        )


def import_houses(path):
    return GeoPackageImporter().import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))",
    )


def test_building_with_several_addresses_is_one_building(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path)

    result = import_houses(path)

    assert [record.source_row_id for record in result.harmonized_records] == [1, 4]
    assert all(record.duplicate_group is None for record in result.harmonized_records)
    house = result.harmonized_records[0]
    assert house.source_attributes["hnr"] == "39, 41"
    assert house.source_attributes["objid"] == "DENIAL1"
    assert house.attributes["object_type"] == "Wohngebäude"
    codes = {issue.code for issue in result.issues}
    assert "uncertain-duplicate" not in codes
    exact = next(issue for issue in result.issues if issue.code == "duplicate-row")
    assert exact.message == "Gebäude: 1 Eintrag war doppelt (komplett gleich) und wurde automatisch entfernt."
    combined = next(issue for issue in result.issues if issue.code == "several-addresses")
    assert combined.severity == "info"
    assert not combined.requires_confirmation
    assert combined.message == "Gebäude: 1 Gebäude hat mehrere Adressen (z. B. Eckhaus). Alle Adressen bleiben erhalten."


def test_same_id_with_other_differences_is_not_combined(tmp_path):
    """Only addresses are combined; any other difference is left to the user."""
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

    kept = [record for record in result.harmonized_records if record.source_row_id in (201, 202)]
    assert [record.source_attributes["flaeche"] for record in kept] == ["100", "120"]
    assert kept[0].duplicate_group is not None and kept[0].duplicate_group == kept[1].duplicate_group
    assert "several-addresses" not in {issue.code for issue in result.issues}


def test_same_id_but_different_object_type_is_not_combined(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE gebaeude SET gfk__bez = 'Garage' WHERE fid = 1")

    result = import_houses(path)

    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 4]
    assert "several-addresses" not in {issue.code for issue in result.issues}
    assert any(issue.code == "uncertain-duplicate" for issue in result.issues)


def test_rows_are_not_combined_without_object_id_rule(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path)
    rules = default_mapping_rules()
    rules = replace(rules, profiles=tuple(replace(profile, object_id_field=None) for profile in rules.profiles))

    result = GeoPackageImporter(mapping_rules=rules).import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))",
    )

    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 4]
    assert "several-addresses" not in {issue.code for issue in result.issues}


def make_street_geopackage(path):
    """ALKIS-like buildings with street (bez), house number (hnr) and floors."""
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
                ('gebaeude', 'geom', 'MULTIPOLYGON', 25832);
            CREATE TABLE gebaeude (
                fid INTEGER PRIMARY KEY, geom BLOB, objid TEXT, gfk__bez TEXT,
                bez TEXT, hnr TEXT, geschosse TEXT
            );
            """
        )
        corner = gpkg_polygon([(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)])
        single = gpkg_polygon([(5, 1), (7, 1), (7, 3), (5, 3), (5, 1)])
        shed = gpkg_polygon([(8, 1), (9, 1), (9, 2), (8, 2), (8, 1)])
        connection.executemany(
            "INSERT INTO gebaeude VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, corner, "ECK", "Wohngebäude", "Hauptstraße", "2", "3"),
                (2, corner, "ECK", "Wohngebäude", "Nebenweg", "1", "3"),
                (3, single, "EINZEL", "Wohngebäude", "Hauptstraße", "4", "2,0"),
                (4, shed, "SCHUPPEN", "Schuppen", None, None, "1,5"),
            ],
        )


def test_object_id_comes_from_the_profile_and_is_suggested(tmp_path):
    path = tmp_path / "streets.gpkg"
    make_street_geopackage(path)

    result = import_houses(path)

    ids = [record.attributes["object_id"] for record in result.harmonized_records]
    assert ids == ["ECK", "EINZEL", "SCHUPPEN"]
    suggestion = next(s for s in result.attribute_suggestions if s.target_field == "object_id")
    assert (suggestion.source_field, suggestion.confidence) == ("objid", 1.0)


def test_address_keeps_street_and_number_together_for_a_corner_house(tmp_path):
    path = tmp_path / "streets.gpkg"
    make_street_geopackage(path)

    result = import_houses(path)

    addresses = {record.attributes["object_id"]: record.attributes["address"] for record in result.harmonized_records}
    assert addresses == {
        "ECK": "Hauptstraße 2; Nebenweg 1",
        "EINZEL": "Hauptstraße 4",
        "SCHUPPEN": None,
    }
    assert any(issue.code == "several-addresses" for issue in result.issues)


def test_floors_are_whole_numbers_or_stay_empty(tmp_path):
    path = tmp_path / "streets.gpkg"
    make_street_geopackage(path)

    result = import_houses(path)

    floors = {record.attributes["object_id"]: record.attributes["floors"] for record in result.harmonized_records}
    assert floors == {"ECK": 3, "EINZEL": 2, "SCHUPPEN": None}
    suggestion = next(s for s in result.attribute_suggestions if s.target_field == "floors")
    assert suggestion.source_field == "geschosse"


def test_new_target_fields_follow_step_5_decisions(tmp_path):
    path = tmp_path / "streets.gpkg"
    make_street_geopackage(path)
    result = import_houses(path)
    for suggestion in result.attribute_suggestions:
        if suggestion.target_field == "object_id":
            suggestion.accepted = False

    records = apply_attribute_decisions(result)

    assert all(record.attributes["object_id"] is None for record in records)
    assert records[0].attributes["address"] == "Hauptstraße 2; Nebenweg 1"
    assert records[0].attributes["floors"] == 3


def test_different_objects_at_the_same_place_need_confirmation(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path, same_object=False)

    result = import_houses(path)

    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 4]
    assert [record.duplicate_group for record in result.harmonized_records] == [
        "gebaeude:1",
        "gebaeude:1",
        None,
    ]
    exact = next(issue for issue in result.issues if issue.code == "duplicate-row")
    assert exact.message == "Gebäude: 1 Eintrag war doppelt (komplett gleich) und wurde automatisch entfernt."
    uncertain = next(issue for issue in result.issues if issue.code == "uncertain-duplicate")
    assert uncertain.requires_confirmation
    assert uncertain.severity == "warning"
    assert uncertain.message.startswith(
        "Gebäude: An einer Stelle liegen mehrere Objekte genau übereinander (2 Objekte). "
        "Sie unterscheiden sich nur in Hausnummer und ALKIS-Objekt-ID – z. B. ein Haus mit mehreren Hausnummern."
    )
    assert uncertain.message.endswith("Sollen sie je Stelle zu einem Objekt zusammengefasst werden?")
    assert "Alle wurden behalten" in uncertain.message


def test_merge_confirmed_duplicates_keeps_first_record_per_group(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path, same_object=False)
    records = import_houses(path).harmonized_records

    assert merge_confirmed_duplicates(records, []) == records
    merged = merge_confirmed_duplicates(records, ["gebaeude:1"])
    assert [record.source_row_id for record in merged] == [1, 4]


def switch_to_wal_mode(path):
    """Store the GeoPackage like QGIS does while editing (journal mode WAL)."""
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    connection.close()
    assert path.read_bytes()[18:20] == b"\x02\x02"


def test_reads_wal_mode_geopackage_without_side_files(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(path)
    switch_to_wal_mode(path)
    original = path.read_bytes()

    result = import_places(path)

    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 5]
    assert path.read_bytes() == original


def test_reads_wal_mode_geopackage_while_another_program_writes(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(path)
    switch_to_wal_mode(path)
    writer = sqlite3.connect(path)
    try:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("INSERT INTO places VALUES (8, ?, 'neu gezeichnet')", (gpkg_point(20, 20),))
        writer.commit()
        assert (tmp_path / "places.gpkg-wal").exists()

        result = import_places(path)
    finally:
        writer.close()

    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 5, 8]


def test_reads_wal_mode_geopackage_with_unsaved_changes_and_no_shared_memory_file(tmp_path):
    source = tmp_path / "source.gpkg"
    make_clipping_geopackage(source)
    switch_to_wal_mode(source)
    writer = sqlite3.connect(source)
    writer.execute("PRAGMA wal_autocheckpoint=0")
    writer.execute("INSERT INTO places VALUES (8, ?, 'neu gezeichnet')", (gpkg_point(20, 20),))
    writer.commit()
    copy_dir = tmp_path / "copy"
    copy_dir.mkdir()
    path = copy_dir / "places.gpkg"
    path.write_bytes(source.read_bytes())
    (copy_dir / "places.gpkg-wal").write_bytes((tmp_path / "source.gpkg-wal").read_bytes())
    writer.close()
    original = path.read_bytes()

    result = import_places(path)

    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 5, 8]
    assert path.read_bytes() == original


def test_source_name_is_only_the_file_name_and_source_stays_empty(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path)

    result = import_houses(path)

    assert result.layers[0].source_name == "houses.gpkg"
    assert {record.attributes["source_name"] for record in result.harmonized_records} == {"houses.gpkg"}
    assert {record.attributes["source"] for record in result.harmonized_records} == {None}
    hint = next(issue for issue in result.issues if issue.code == "missing-data-source")
    assert hint.severity == "warning"
    assert hint.message.startswith("Datenquelle fehlt: In der Datei steht nicht, woher die Daten stammen.")
    assert "z. B. „ALKIS, © LGLN 2025“" in hint.message
    assert str(tmp_path) not in hint.message


def test_source_column_in_data_is_used_and_no_hint_is_shown(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path)
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE gebaeude ADD COLUMN quelle TEXT")
        connection.execute("UPDATE gebaeude SET quelle = 'ALKIS, LGLN 2025'")

    result = import_houses(path)

    assert {record.attributes["source"] for record in result.harmonized_records} == {"ALKIS, LGLN 2025"}
    assert "missing-data-source" not in {issue.code for issue in result.issues}


def test_apply_data_source_fills_only_empty_sources(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path)
    records = import_houses(path).harmonized_records
    records[0] = records[0].__class__(
        layer_id=records[0].layer_id,
        source_row_id=records[0].source_row_id,
        attributes={**records[0].attributes, "source": "aus den Daten"},
        geometry=records[0].geometry,
        duplicate_group=records[0].duplicate_group,
    )

    filled = apply_data_source(records, "  ALKIS, LGLN 2025 ")

    assert [record.attributes["source"] for record in filled] == [
        "aus den Daten",
        "ALKIS, LGLN 2025",
    ]
    assert records[1].attributes["source"] is None
    with pytest.raises(ValueError):
        apply_data_source(records, "   ")


NUTZUNG_ROWS = [
    ("Strassenverkehr, Begleitfläche Straßenverkehr", "Straßen", "nutzung_strassen"),
    ("Platz, Parkplatz", "Straßen", "nutzung_strassen"),
    ("Weg, Rad- und Fußweg", "Fuß- und Radwege", "nutzung_fuss_radwege"),
    ("Weg", "Fuß- und Radwege", "nutzung_fuss_radwege"),
    ("Strassenverkehr, Fußgängerzone", "Fuß- und Radwege", "nutzung_fuss_radwege"),
    ("Platz, Marktplatz", "Plätze", "nutzung_plaetze"),
    ("Sport-, Freizeit- und Erholungsfläche, Park", "Grünflächen", "nutzung_gruen"),
    ("Landwirtschaft, Grünland", "Grünflächen", "nutzung_gruen"),
    ("Unland, Vegetationslose Fläche, Sukzessionsfläche", "Grünflächen", "nutzung_gruen"),
    ("Fliessgewässer, Graben", "Wasserflächen", "nutzung_wasser"),
    ("Bahnverkehr", "Bahnflächen", "nutzung_bahn"),
    ("Schiffsverkehr, Hafenanlage (Landfläche)", "Schiffsverkehrsflächen", "nutzung_schiff"),
    ("Wohnbaufläche, Offen", "Nutzungsflächen", "nutzung_flaechen"),
    ("Sport-, Freizeit- und Erholungsfläche, Sportanlage", "Nutzungsflächen", "nutzung_flaechen"),
    ("Landwirtschaft, Ackerland", "Nutzungsflächen", "nutzung_flaechen"),
]


def make_alkis_geopackage(path, *, with_objid=True):
    """Small ALKIS-like GeoPackage: nutzung, gebaeude and an unrelated layer."""
    objid = "objid TEXT," if with_objid else ""
    with sqlite3.connect(path) as connection:
        connection.executescript(
            f"""
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
                ('nutzung', 'geom', 'MULTIPOLYGON', 25832),
                ('gebaeude', 'geom', 'MULTIPOLYGON', 25832),
                ('bodenschaetzung', 'geom', 'MULTIPOLYGON', 25832);
            CREATE TABLE nutzung (fid INTEGER PRIMARY KEY, geom BLOB, {objid} tn__bez TEXT);
            CREATE TABLE gebaeude (fid INTEGER PRIMARY KEY, geom BLOB, {objid} gfk__bez TEXT);
            CREATE TABLE bodenschaetzung (fid INTEGER PRIMARY KEY, geom BLOB, {objid} kul__bez TEXT);
            """
        )
        columns = "(fid, geom, objid, tn__bez)" if with_objid else "(fid, geom, tn__bez)"
        for index, (value, _category, _layer) in enumerate(NUTZUNG_ROWS, start=1):
            square = gpkg_polygon([(index, 1), (index + 0.5, 1), (index + 0.5, 2), (index, 2), (index, 1)])
            values = (index, square, f"N{index}", value) if with_objid else (index, square, value)
            marks = ", ".join("?" * len(values))
            connection.execute(f"INSERT INTO nutzung {columns} VALUES ({marks})", values)
        house = gpkg_polygon([(1, 5), (2, 5), (2, 6), (1, 6), (1, 5)])
        if with_objid:
            connection.execute("INSERT INTO gebaeude VALUES (1, ?, 'G1', 'Wohngebäude')", (house,))
            connection.execute("INSERT INTO bodenschaetzung VALUES (1, ?, 'B1', 'Grünland')", (house,))
        else:
            connection.execute("INSERT INTO gebaeude VALUES (1, ?, 'Wohngebäude')", (house,))
            connection.execute("INSERT INTO bodenschaetzung VALUES (1, ?, 'Grünland')", (house,))


def import_alkis(path):
    return GeoPackageImporter().import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 30 0, 30 10, 0 10, 0 0))",
        buffer_meters=0,
    )


def test_alkis_nutzung_is_split_into_one_result_layer_per_category(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)

    result = import_alkis(path)

    by_row = {
        record.source_row_id: record
        for record in result.harmonized_records
        if record.layer_id.startswith("nutzung")
    }
    for index, (value, category, layer_id) in enumerate(NUTZUNG_ROWS, start=1):
        assert by_row[index].attributes["category"] == category, value
        assert by_row[index].layer_id == layer_id, value
    nutzung_layers = {layer.layer_id: layer.category for layer in result.layers if layer.layer_id.startswith("nutzung")}
    assert nutzung_layers == {layer_id: category for _value, category, layer_id in NUTZUNG_ROWS}
    assert "nutzung" not in {layer.layer_id for layer in result.layers}


def test_alkis_values_keep_main_type_and_detail(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)

    result = import_alkis(path)

    def attributes_for(value):
        index = [row[0] for row in NUTZUNG_ROWS].index(value) + 1
        return next(
            record.attributes for record in result.harmonized_records
            if record.layer_id.startswith("nutzung") and record.source_row_id == index
        )

    assert attributes_for("Wohnbaufläche, Offen")["object_type"] == "Wohnbaufläche"
    assert attributes_for("Wohnbaufläche, Offen")["object_detail"] == "Offen"
    park = attributes_for("Sport-, Freizeit- und Erholungsfläche, Park")
    assert (park["object_type"], park["object_detail"]) == ("Sport-, Freizeit- und Erholungsfläche", "Park")
    unland = attributes_for("Unland, Vegetationslose Fläche, Sukzessionsfläche")
    assert (unland["object_type"], unland["object_detail"]) == ("Unland, Vegetationslose Fläche", "Sukzessionsfläche")
    assert attributes_for("Bahnverkehr")["object_detail"] is None


def test_alkis_buildings_and_unrelated_layers(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)

    result = import_alkis(path)

    categories = {layer.layer_id: layer.category for layer in result.layers}
    assert categories["gebaeude"] == "Gebäude"
    assert categories["bodenschaetzung"] is None
    building = next(record for record in result.harmonized_records if record.layer_id == "gebaeude")
    assert building.attributes["object_type"] == "Wohngebäude"
    assert building.attributes["category"] == "Gebäude"
    assert "missing-category" not in {issue.code for issue in result.issues}
    suggestion = next(s for s in result.attribute_suggestions if s.source_field == "gfk__bez")
    assert (suggestion.target_field, suggestion.confidence) == ("object_type", 1.0)


def test_without_alkis_profile_only_the_layer_name_decides(tmp_path):
    path = tmp_path / "other.gpkg"
    make_alkis_geopackage(path, with_objid=False)

    result = import_alkis(path)

    categories = {layer.layer_id: layer.category for layer in result.layers}
    assert categories == {"nutzung": "Nutzungsflächen", "gebaeude": "Gebäude", "bodenschaetzung": None}
    hint = next(issue for issue in result.issues if issue.code == "missing-category")
    assert hint.message.startswith("Bodenschätzung: Für diesen Layer ist unklar, was er darstellt")
    assert all(record.attributes["object_detail"] is None for record in result.harmonized_records)


def test_data_source_hint_names_only_the_layers_without_source(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE gebaeude ADD COLUMN quelle TEXT")
        connection.execute("UPDATE gebaeude SET quelle = 'ALKIS, LGLN 2025'")

    result = import_alkis(path)

    hint = next(issue for issue in result.issues if issue.code == "missing-data-source")
    assert hint.message.startswith("Datenquelle fehlt für Nutzung und Bodenschätzung:")


def test_uncertain_duplicate_hint_skips_key_column_when_readable_twin_differs(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path)
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE gebaeude ADD COLUMN gfk TEXT")
        connection.execute("UPDATE gebaeude SET gfk = CAST(fid AS TEXT), gfk__bez = 'Funktion ' || fid")

    result = import_houses(path)

    uncertain = next(issue for issue in result.issues if issue.code == "uncertain-duplicate")
    assert "nur in Gebäudefunktion und Hausnummer" in uncertain.message
    assert "Gebäudefunktionsschlüssel" not in uncertain.message
    assert "(" not in uncertain.message.split("(3 Objekte)")[1].split("–")[0]


def test_attribute_suggestions_name_their_layer_and_show_examples(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)

    result = import_alkis(path)

    by_layer = {(s.layer_id, s.source_field): s for s in result.attribute_suggestions}
    nutzung = by_layer[("nutzung", "tn__bez")]
    assert nutzung.target_field == "object_type"
    assert nutzung.examples == ("Strassenverkehr, Begleitfläche Straßenverkehr", "Platz, Parkplatz")
    assert by_layer[("gebaeude", "gfk__bez")].examples == ("Wohngebäude",)


def test_same_geometry_in_different_categories_is_not_an_uncertain_duplicate(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)
    area = gpkg_polygon([(20, 1), (21, 1), (21, 2), (20, 2), (20, 1)])
    path_area = gpkg_polygon([(24, 1), (25, 1), (25, 2), (24, 2), (24, 1)])
    with sqlite3.connect(path) as connection:
        connection.executemany(
            "INSERT INTO nutzung VALUES (?, ?, ?, ?)",
            [
                (101, area, "X1", "Strassenverkehr"),
                (102, area, "X2", "Sport-, Freizeit- und Erholungsfläche, Park"),
                (103, path_area, "X3", "Weg"),
                (104, path_area, "X4", "Weg, Fußweg"),
            ],
        )

    result = import_alkis(path)

    groups = {
        record.source_row_id: record.duplicate_group
        for record in result.harmonized_records
        if record.source_row_id in (101, 102, 103, 104) and record.layer_id.startswith("nutzung")
    }
    assert groups[101] is None and groups[102] is None
    assert groups[103] is not None and groups[103] == groups[104]
    uncertain = next(issue for issue in result.issues if issue.code == "uncertain-duplicate")
    assert uncertain.message.startswith("Nutzung: An einer Stelle liegen mehrere Objekte")
    overlap = next(issue for issue in result.issues if issue.code == "overlap-different-category")
    assert overlap.severity == "info"
    assert overlap.message == (
        "Nutzung: An einer Stelle liegen Flächen mit unterschiedlicher Kategorie genau übereinander. "
        "Sie sind keine Dubletten und bleiben in ihrer jeweiligen Kategorie erhalten."
    )


def make_many_points_geopackage(path, count):
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
            INSERT INTO gpkg_geometry_columns VALUES ('points', 'geom', 'POINT', 25832);
            CREATE TABLE points (fid INTEGER PRIMARY KEY, geom BLOB, typ TEXT);
            """
        )
        connection.executemany(
            "INSERT INTO points VALUES (?, ?, ?)",
            [(index, gpkg_point(index % 100, index // 100), f"p{index}") for index in range(1, count + 1)],
        )


def test_progress_rises_from_zero_to_one(tmp_path):
    path = tmp_path / "points.gpkg"
    make_many_points_geopackage(path, 5000)
    reported = []

    GeoPackageImporter().import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 100 0, 100 100, 0 100, 0 0))",
        buffer_meters=0,
        progress=reported.append,
    )

    assert reported[0] == 0.0
    assert reported[-1] == 1.0
    assert reported == sorted(reported)
    assert any(0.1 < value < 0.9 for value in reported)
    assert len(reported) <= 102


def test_progress_ends_at_one_even_without_usable_data(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(path)
    reported = []

    import_places(path, study_area_wkt="LINESTRING (0 0, 10 10)", progress=reported.append)

    assert reported[0] == 0.0
    assert reported[-1] == 1.0


def test_user_guidance_can_detect_progress_support():
    import inspect

    assert "progress" in inspect.signature(GeoPackageImporter().import_file).parameters


def suggestion_for(result, layer_id, source_field):
    return next(
        s for s in result.attribute_suggestions
        if s.layer_id == layer_id and s.source_field == source_field
    )


def records_of(records, source_layer):
    return [record for record in records if record.source_layer == source_layer]


def test_records_keep_original_columns_and_pipeline_values(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)

    result = import_alkis(path)

    building = records_of(result.harmonized_records, "gebaeude")[0]
    assert building.source_attributes["gfk__bez"] == "Wohngebäude"
    assert building.source_attributes["objid"] == "G1"
    assert building.pipeline_attributes["object_type"] == "Wohngebäude"
    park = next(r for r in result.harmonized_records if r.layer_id == "nutzung_gruen")
    assert park.source_layer == "nutzung"


def test_accepting_everything_keeps_the_pipeline_values(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)
    result = import_alkis(path)
    for suggestion in result.attribute_suggestions:
        suggestion.accepted = True

    updated = apply_attribute_decisions(result)

    assert [r.attributes for r in updated] == [r.attributes for r in result.harmonized_records]


def test_rejected_suggestion_empties_only_that_layers_target(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)
    result = import_alkis(path)
    suggestion_for(result, "gebaeude", "gfk__bez").accepted = False

    updated = apply_attribute_decisions(result)

    building = records_of(updated, "gebaeude")[0]
    assert building.attributes["object_type"] is None
    assert building.attributes["object_detail"] is None
    assert building.attributes["category"] == "Gebäude"
    assert building.layer_id == "gebaeude"
    nutzung = records_of(updated, "nutzung")[0]
    assert nutzung.attributes["object_type"] == "Strassenverkehr"


def test_moved_suggestion_fills_the_chosen_target(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)
    result = import_alkis(path)
    suggestion_for(result, "nutzung", "tn__bez").user_value = "Status"

    updated = apply_attribute_decisions(result)

    park = next(r for r in records_of(updated, "nutzung") if r.layer_id == "nutzung_gruen")
    assert park.attributes["status"] == "Sport-, Freizeit- und Erholungsfläche, Park"
    assert park.attributes["object_type"] is None
    assert park.attributes["object_detail"] is None
    assert park.attributes["category"] == "Grünflächen"


def test_decisions_can_be_changed_again_without_losing_data(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)
    result = import_alkis(path)
    original = [dict(r.attributes) for r in result.harmonized_records]
    suggestion = suggestion_for(result, "nutzung", "tn__bez")

    suggestion.user_value = "status"
    result.harmonized_records = apply_attribute_decisions(result)
    suggestion.user_value = None
    suggestion.accepted = True
    result.harmonized_records = apply_attribute_decisions(result)

    assert [dict(r.attributes) for r in result.harmonized_records] == original


def test_area_and_year_from_a_chosen_column_are_converted(tmp_path):
    path = tmp_path / "sample.gpkg"
    make_geopackage(path)
    result = GeoPackageImporter().import_file(
        path, project_crs="EPSG:25832", study_area_wkt="POLYGON ((0 0, 10 0, 10 10, 0 0))"
    )
    suggestion_for(result, "buildings", "area").user_value = "Jahr"
    suggestion_for(result, "buildings", "year").user_value = "area_m2"

    updated = apply_attribute_decisions(result)

    assert updated[0].attributes["area_m2"] == 2020.0
    assert updated[0].attributes["year"] is None  # "12,5" is not a year


def test_user_entered_data_source_survives_attribute_decisions(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)
    result = import_alkis(path)
    result.harmonized_records = apply_data_source(result.harmonized_records, "ALKIS, LGLN 2025")

    updated = apply_attribute_decisions(result)

    assert {r.attributes["source"] for r in updated} == {"ALKIS, LGLN 2025"}


def test_unknown_or_double_targets_are_rejected(tmp_path):
    path = tmp_path / "sample.gpkg"
    make_geopackage(path)
    result = GeoPackageImporter().import_file(
        path, project_crs="EPSG:25832", study_area_wkt="POLYGON ((0 0, 10 0, 10 10, 0 0))"
    )
    suggestion_for(result, "buildings", "type").user_value = "Gebäudehöhe"
    with pytest.raises(ValueError, match="Unbekanntes Zielfeld"):
        apply_attribute_decisions(result)

    suggestion_for(result, "buildings", "type").user_value = "year"
    with pytest.raises(ValueError, match="zweimal zugeordnet"):
        apply_attribute_decisions(result)


# --- M11: OpenStreetMap as GDAL/QGIS stores it -------------------------------


def wkb_linestring(points):
    data = struct.pack("<BII", 1, 2, len(points))
    for x, y in points:
        data += struct.pack("<dd", x, y)
    return data


def square(x, y, size=1):
    return gpkg_polygon([(x, y), (x + size, y), (x + size, y + size), (x, y + size), (x, y)])


def make_osm_geopackage(path):
    """Layers multipolygons/lines/points with the default GDAL OSM columns."""
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
                table_name TEXT, column_name TEXT, geometry_type_name TEXT, srs_id INTEGER
            );
            INSERT INTO gpkg_geometry_columns VALUES
                ('multipolygons', 'geom', 'MULTIPOLYGON', 25832),
                ('lines', 'geom', 'LINESTRING', 25832),
                ('points', 'geom', 'POINT', 25832);
            CREATE TABLE multipolygons (
                fid INTEGER PRIMARY KEY, geom BLOB, osm_id TEXT, osm_way_id TEXT, name TEXT,
                type TEXT, amenity TEXT, barrier TEXT, building TEXT, landuse TEXT, leisure TEXT,
                "natural" TEXT, place TEXT, other_tags TEXT
            );
            CREATE TABLE lines (
                fid INTEGER PRIMARY KEY, geom BLOB, osm_id TEXT, name TEXT, highway TEXT,
                waterway TEXT, barrier TEXT, railway TEXT, other_tags TEXT
            );
            CREATE TABLE points (
                fid INTEGER PRIMARY KEY, geom BLOB, osm_id TEXT, name TEXT, other_tags TEXT
            );
            """
        )
        house_tags = '"addr:street"=>"Hauptstraße","addr:housenumber"=>"2","building:levels"=>"3"'
        connection.executemany(
            "INSERT INTO multipolygons (fid, geom, osm_id, osm_way_id, building, landuse, leisure, "
            '"natural", other_tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [
                (1, square(1, 1), None, "11", "house", None, None, None, house_tags),
                (2, square(3, 1), None, "12", "yes", None, None, None, None),
                (3, square(5, 1), None, "13", None, "grass", "park", None, None),
                (4, square(7, 1), None, "14", None, "residential", None, None, None),
                (5, square(1, 4), "5", None, None, None, None, "water", '"type"=>"multipolygon"'),
                (6, square(3, 4), None, "16", None, None, None, None, '"shop"=>"bakery"'),
            ],
        )
        # Found in the first real OSM test (Donnerschwee): single parking
        # spaces, hedges, school grounds and building parts.
        connection.executemany(
            "INSERT INTO multipolygons (fid, geom, osm_way_id, amenity, barrier, other_tags) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (7, square(5, 4), "17", "parking_space", None, None),
                (8, square(7, 4), "18", None, "hedge", None),
                (9, square(1, 6), "19", "school", None, None),
                (10, square(3, 6), "20", None, None, '"building:part"=>"yes","roof:shape"=>"flat"'),
            ],
        )
        connection.executemany(
            "INSERT INTO lines (fid, geom, osm_id, highway, railway, other_tags) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, gpkg_blob(wkb_linestring([(1, 7), (5, 7)])), "21", "footway", None, None),
                (2, gpkg_blob(wkb_linestring([(1, 8), (5, 8)])), "22", "residential", None, '"maxspeed"=>"30"'),
                (3, gpkg_blob(wkb_linestring([(1, 9), (5, 9)])), "23", None, "rail", None),
            ],
        )
        # GDAL stores closed ways with building:part, barrier or tree rows as
        # lines; the real Donnerschwee test had about 1 000 of them.
        part_tags = '"building:part"=>"yes","roof:shape"=>"flat","building:levels"=>"2"'
        connection.executemany(
            "INSERT INTO lines (fid, geom, osm_id, barrier, other_tags) VALUES (?, ?, ?, ?, ?)",
            [
                (4, gpkg_blob(wkb_linestring([(6, 1), (6, 2), (7, 2), (6, 1)])), "24", None, part_tags),
                (5, gpkg_blob(wkb_linestring([(6, 3), (9, 3)])), "25", "fence", None),
                (6, gpkg_blob(wkb_linestring([(6, 4), (9, 4)])), "26", "hedge", None),
                (7, gpkg_blob(wkb_linestring([(6, 5), (9, 5)])), "27", None, '"natural"=>"tree_row"'),
            ],
        )
        connection.execute(
            "INSERT INTO points VALUES (1, ?, '31', 'Bäckerei', '\"shop\"=>\"bakery\"')", (gpkg_point(4, 5),)
        )


def import_osm(path):
    return GeoPackageImporter().import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))",
        buffer_meters=0,
    )


def osm_records(result, table):
    return {record.source_row_id: record for record in result.harmonized_records if record.source_layer == table}


def test_osm_areas_get_categories_and_readable_object_types(tmp_path):
    path = tmp_path / "osm.gpkg"
    make_osm_geopackage(path)

    areas = osm_records(import_osm(path), "multipolygons")

    summary = {
        fid: (record.layer_id, record.attributes["category"], record.attributes["object_type"])
        for fid, record in areas.items()
    }
    assert summary == {
        1: ("multipolygons_gebaeude", "Gebäude", "Wohnhaus"),
        2: ("multipolygons_gebaeude", "Gebäude", "Gebäude"),
        3: ("multipolygons_gruen", "Grünflächen", "Park"),
        4: ("multipolygons_flaechen", "Nutzungsflächen", "Wohnbaufläche"),
        5: ("multipolygons_wasser", "Wasserflächen", "Gewässer"),
        6: ("multipolygons_sonstige", "Sonstige OSM-Flächen", None),
        7: ("multipolygons_strassen", "Straßen", "Stellplatz"),
        8: ("multipolygons_gruen", "Grünflächen", "Hecke"),
        9: ("multipolygons_flaechen", "Nutzungsflächen", "Schulgelände"),
        10: ("multipolygons_sonstige", "Sonstige OSM-Flächen", "Gebäudeteil"),
    }


def test_osm_ids_address_and_floors(tmp_path):
    path = tmp_path / "osm.gpkg"
    make_osm_geopackage(path)

    result = import_osm(path)
    areas = osm_records(result, "multipolygons")

    house = areas[1].attributes
    assert (house["object_id"], house["address"], house["floors"]) == ("way/11", "Hauptstraße 2", 3)
    assert areas[5].attributes["object_id"] == "relation/5"
    assert osm_records(result, "lines")[1].attributes["object_id"] == "way/21"
    assert osm_records(result, "points")[1].attributes["object_id"] == "node/31"
    assert areas[1].source_attributes["other_tags"].startswith('"addr:street"')
    targets = {(s.layer_id, s.target_field): s.source_field for s in result.attribute_suggestions}
    assert targets[("multipolygons", "floors")] == "building:levels"
    assert ("multipolygons", "object_id") not in targets
    assert ("multipolygons", "address") not in targets
    # Building parts (lines) have levels; no point has: no empty column in step 5.
    assert targets[("lines", "floors")] == "building:levels"
    assert ("points", "floors") not in targets


def test_osm_lines_are_split_into_paths_streets_and_railways(tmp_path):
    path = tmp_path / "osm.gpkg"
    make_osm_geopackage(path)

    lines = osm_records(import_osm(path), "lines")

    summary = {fid: (record.attributes["category"], record.attributes["object_type"]) for fid, record in lines.items()}
    assert summary == {
        1: ("Fuß- und Radwege", "Fußweg"),
        2: ("Straßen", "Wohnstraße"),
        3: ("Bahnstrecken", "Bahnstrecke"),
        4: ("Gebäudeteile", "Gebäudeteil"),
        5: ("Zäune und Mauern", "Zaun"),
        6: ("Hecken und Baumreihen", "Hecke"),
        7: ("Hecken und Baumreihen", "Baumreihe"),
    }
    assert lines[4].attributes["floors"] == 2


def test_osm_import_has_no_false_hints(tmp_path):
    path = tmp_path / "osm.gpkg"
    make_osm_geopackage(path)

    codes = {issue.code for issue in import_osm(path).issues}

    assert "uncertain-duplicate" not in codes
    assert "missing-category" not in codes
    assert "several-addresses" not in codes
