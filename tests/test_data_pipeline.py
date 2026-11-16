import sqlite3

import pytest

from urban_analysis.data_pipeline import GeoPackageImportError, GeoPackageImporter


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
            INSERT INTO buildings VALUES
                (1, NULL, 'house', '12,5', 'Gebäude', '2020'),
                (2, NULL, 'house', '12,5', 'Gebäude', '2020');
            """
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

    path = tmp_path / "invalid.gpkg"
    path.write_bytes(b"not sqlite")
    with pytest.raises(GeoPackageImportError):
        GeoPackageImporter().import_file(
            path,
            project_crs="EPSG:25832",
            study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
        )

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
