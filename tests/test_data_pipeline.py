import sqlite3
import struct

import pytest

from urban_analysis.data_pipeline import GeoPackageImportError, GeoPackageImporter


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
    assert duplicate.message.startswith("1 exakte")
