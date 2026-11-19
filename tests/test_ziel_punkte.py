"""OSM points become targets for accessibility (M17 part 1, E22, E34)."""

import json
import sqlite3
from pathlib import Path

import pytest

from urban_analysis.data_pipeline import GeoPackageImporter
from tests.test_data_pipeline import gpkg_point, gpkg_polygon

# (fid, highway column, other_tags) as GDAL writes OSM points
POINTS = [
    (1, None, '"amenity"=>"hospital","name"=>"Klinikum"'),
    (2, None, '"amenity"=>"doctors","healthcare"=>"doctor"'),
    (3, None, '"healthcare"=>"physiotherapist"'),
    (4, None, '"shop"=>"supermarket"'),
    (5, None, '"shop"=>"chemist"'),
    (6, None, '"amenity"=>"kindergarten"'),
    (7, None, '"amenity"=>"university"'),
    (8, None, '"leisure"=>"playground"'),
    (9, None, '"amenity"=>"library"'),
    (10, "bus_stop", '"public_transport"=>"platform"'),
    (11, None, '"railway"=>"tram_stop"'),
    (12, "crossing", None),
    (13, None, '"shop"=>"florist"'),
]


def make_points_geopackage(path):
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
                ('points', 'geom', 'POINT', 25832),
                ('multipolygons', 'geom', 'MULTIPOLYGON', 25832);
            CREATE TABLE points (
                fid INTEGER PRIMARY KEY, geom BLOB, osm_id TEXT, name TEXT,
                highway TEXT, other_tags TEXT
            );
            CREATE TABLE multipolygons (
                fid INTEGER PRIMARY KEY, geom BLOB, osm_id TEXT, osm_way_id TEXT,
                amenity TEXT, other_tags TEXT
            );
            """
        )
        connection.executemany(
            "INSERT INTO points VALUES (?, ?, ?, NULL, ?, ?)",
            [(fid, gpkg_point(fid % 9 + 0.5, 1), str(100 + fid), highway, tags) for fid, highway, tags in POINTS],
        )
        connection.execute(
            "INSERT INTO multipolygons VALUES (1, ?, NULL, '50', 'hospital', NULL)",
            (gpkg_polygon([(1, 5), (3, 5), (3, 7), (1, 7), (1, 5)]),),
        )


@pytest.fixture
def result(tmp_path):
    path = tmp_path / "osm.gpkg"
    make_points_geopackage(path)
    return GeoPackageImporter().import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))",
        buffer_meters=0,
    )


def points(result):
    return {
        record.source_row_id: (record.attributes["category"], record.attributes["object_type"], record.layer_id)
        for record in result.harmonized_records
        if record.source_layer == "points"
    }


def test_points_get_category_and_subtype(result):
    found = points(result)
    assert found[1] == ("Gesundheit", "Krankenhaus", "points_gesundheit")
    assert found[2][:2] == ("Gesundheit", "Arztpraxis")
    assert found[3][:2] == ("Gesundheit", "Gesundheitseinrichtung")
    assert found[4][:2] == ("Nahversorgung", "Supermarkt")
    assert found[5][:2] == ("Nahversorgung", "Drogerie")
    assert found[6][:2] == ("Bildung und Betreuung", "Kita")
    assert found[7][:2] == ("Bildung und Betreuung", "Hochschule")
    assert found[8][:2] == ("Freizeit und Grün", "Spielplatz")
    assert found[9][:2] == ("Freizeit und Grün", "Bibliothek")
    assert found[10][:2] == ("ÖPNV-Haltestellen", "Bushaltestelle")
    assert found[11][:2] == ("ÖPNV-Haltestellen", "Straßenbahnhaltestelle")


def test_other_points_are_kept_but_apart(result):
    found = points(result)
    assert found[12][0] == "Sonstige OSM-Punkte"
    assert found[13][0] == "Sonstige OSM-Punkte"


def test_points_get_one_result_layer_per_category(result):
    layers = {layer.layer_id: layer.category for layer in result.layers if layer.layer_id.startswith("points")}
    assert layers == {
        "points_gesundheit": "Gesundheit",
        "points_nahversorgung": "Nahversorgung",
        "points_bildung": "Bildung und Betreuung",
        "points_freizeit": "Freizeit und Grün",
        "points_haltestellen": "ÖPNV-Haltestellen",
        "points_sonstige": "Sonstige OSM-Punkte",
    }


def test_hospital_area_keeps_its_area_name(result):
    area = next(r for r in result.harmonized_records if r.source_layer == "multipolygons")
    assert area.attributes["object_type"] == "Krankenhausgelände"
    assert area.attributes["category"] == "Nutzungsflächen"


def test_overpass_query_fetches_health_care_points():
    catalog = json.loads(
        (Path(__file__).resolve().parents[1] / "urban_analysis" / "sources_catalog.json").read_text(encoding="utf-8")
    )
    assert "healthcare" in catalog["osm"]["abfrage"]["schluessel"]
