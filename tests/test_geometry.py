import math
import struct

import pytest

from urban_analysis.geometry import (
    GeometryError,
    distance,
    parse_gpkg_geometry,
    parse_wkt,
    read_geometry,
    validate_study_area,
    within_distance,
)


def wkb_point(x, y):
    return struct.pack("<BIdd", 1, 1, x, y)


def wkb_polygon(*rings):
    data = struct.pack("<BII", 1, 3, len(rings))
    for ring in rings:
        data += struct.pack("<I", len(ring))
        for x, y in ring:
            data += struct.pack("<dd", x, y)
    return data


def gpkg_blob(wkb, envelope=None):
    flags = 0b1  # little endian header
    header = b"GP\x00"
    if envelope is not None:
        flags |= 0b10
        return header + bytes([flags]) + struct.pack("<i", 25832) + struct.pack("<dddd", *envelope) + wkb
    return header + bytes([flags]) + struct.pack("<i", 25832) + wkb


SQUARE = parse_wkt("POLYGON ((0 0, 100 0, 100 100, 0 100, 0 0))")


def test_parses_wkt_variants_written_by_qgis():
    assert parse_wkt("Point (1 2)").points == ((1.0, 2.0),)
    assert parse_wkt("POINT Z (1 2 3)").points == ((1.0, 2.0),)
    multi = parse_wkt("MultiPolygonZ (((0 0 1, 1 0 1, 1 1 1, 0 0 1)), ((5 5 0, 6 5 0, 6 6 0, 5 5 0)))")
    assert len(multi.polygons) == 2
    collection = parse_wkt("GEOMETRYCOLLECTION (POINT (1 1), LINESTRING (0 0, 2 2))")
    assert collection.points == ((1.0, 1.0),)
    assert collection.lines == (((0.0, 0.0), (2.0, 2.0)),)
    assert parse_wkt("MULTIPOINT (1 2, 3 4)").points == parse_wkt("MULTIPOINT ((1 2), (3 4))").points
    assert parse_wkt("POLYGON EMPTY").is_empty
    assert parse_wkt("SRID=25832;POINT (1 2)").points == ((1.0, 2.0),)


@pytest.mark.parametrize("text", ["POLYGON ((0 0, 1 0", "CIRCULARSTRING (0 0, 1 1, 2 0)", "POINT (1)", "kein wkt"])
def test_rejects_unreadable_wkt(text):
    with pytest.raises(GeometryError):
        parse_wkt(text)


def test_reads_geopackage_binary_with_and_without_envelope():
    blob = gpkg_blob(wkb_polygon([(0, 0), (1, 0), (1, 1), (0, 0)]), envelope=(0, 1, 0, 1))
    assert parse_gpkg_geometry(blob).polygons[0][0][2] == (1.0, 1.0)
    assert read_geometry(gpkg_blob(wkb_point(3, 4))).points == ((3.0, 4.0),)
    assert read_geometry(None) is None
    with pytest.raises(GeometryError):
        read_geometry(b"GP\x00\x01" + b"\x00" * 6)


def test_distance_between_geometries():
    assert distance(parse_wkt("POINT (50 50)"), SQUARE) == 0
    assert distance(parse_wkt("POINT (130 50)"), SQUARE) == pytest.approx(30)
    assert distance(parse_wkt("POINT (130 140)"), SQUARE) == pytest.approx(50)
    assert distance(parse_wkt("LINESTRING (-10 50, 110 50)"), SQUARE) == 0
    big = parse_wkt("POLYGON ((-500 -500, 500 -500, 500 500, -500 500, -500 -500))")
    assert distance(big, SQUARE) == 0


def test_point_in_hole_is_outside_the_polygon():
    with_hole = parse_wkt(
        "POLYGON ((0 0, 100 0, 100 100, 0 100, 0 0), (40 40, 60 40, 60 60, 40 60, 40 40))"
    )
    assert distance(parse_wkt("POINT (50 50)"), with_hole) == pytest.approx(10)


def test_within_distance_uses_real_polygon_not_bounding_box():
    triangle = parse_wkt("POLYGON ((0 0, 100 0, 0 100, 0 0))")
    corner = parse_wkt("POINT (90 90)")
    expected = (90 + 90 - 100) / math.sqrt(2)
    assert distance(corner, triangle) == pytest.approx(expected)
    assert not within_distance(corner, triangle, 50)
    assert within_distance(corner, triangle, 60)


def test_validates_study_area_polygon():
    assert validate_study_area(SQUARE) is None
    assert validate_study_area(parse_wkt("LINESTRING (0 0, 1 1)"))
    assert validate_study_area(parse_wkt("POLYGON ((0 0, 1 0, 1 1, 0 1))"))
