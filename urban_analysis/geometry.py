"""QGIS-free geometry reading and distance checks for the data pipeline.

The pipeline clips GeoPackage features to the study area without the QGIS API
and without external packages such as shapely.  This module therefore reads
the geometry encodings found in GeoPackages (GeoPackage binary, plain WKB and
WKT text) into simple coordinate tuples and answers one question: is a feature
within ``buffer`` metres of the study-area polygon?

All coordinates are expected in the same projected CRS (metres).  Reprojection
is intentionally not supported; the importer reports CRS mismatches instead.
"""

from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass
from typing import Iterator, List, Optional, Sequence, Tuple


Point = Tuple[float, float]
Ring = Tuple[Point, ...]
Polygon = Tuple[Ring, ...]
BBox = Tuple[float, float, float, float]
Segment = Tuple[Point, Point]


class GeometryError(ValueError):
    """Raised when a geometry value cannot be read."""


@dataclass(frozen=True)
class Geometry:
    """Flattened geometry: standalone points, line strings and polygons."""

    points: Tuple[Point, ...] = ()
    lines: Tuple[Tuple[Point, ...], ...] = ()
    polygons: Tuple[Polygon, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.points or self.lines or self.polygons)

    def vertices(self) -> Iterator[Point]:
        yield from self.points
        for line in self.lines:
            yield from line
        for polygon in self.polygons:
            for ring in polygon:
                yield from ring

    def bbox(self) -> Optional[BBox]:
        xs: List[float] = []
        ys: List[float] = []
        for x, y in self.vertices():
            xs.append(x)
            ys.append(y)
        if not xs:
            return None
        return min(xs), min(ys), max(xs), max(ys)


def _combine(parts: Sequence[Geometry]) -> Geometry:
    return Geometry(
        points=tuple(point for part in parts for point in part.points),
        lines=tuple(line for part in parts for line in part.lines),
        polygons=tuple(polygon for part in parts for polygon in part.polygons),
    )


# ---------------------------------------------------------------------------
# WKB / GeoPackage binary
# ---------------------------------------------------------------------------

_WKB_BASE_TYPES = {
    1: "POINT",
    2: "LINESTRING",
    3: "POLYGON",
    4: "MULTIPOINT",
    5: "MULTILINESTRING",
    6: "MULTIPOLYGON",
    7: "GEOMETRYCOLLECTION",
}


class _WkbReader:
    def __init__(self, data: bytes, offset: int = 0):
        self.data = data
        self.offset = offset

    def _unpack(self, fmt: str, size: int):
        end = self.offset + size
        if end > len(self.data):
            raise GeometryError("WKB-Geometrie ist unvollständig")
        values = struct.unpack(fmt, self.data[self.offset : end])
        self.offset = end
        return values

    def read_geometry(self) -> Geometry:
        (byte_order,) = self._unpack("B", 1)
        if byte_order not in (0, 1):
            raise GeometryError("Ungültige WKB-Byte-Reihenfolge")
        prefix = "<" if byte_order == 1 else ">"
        (raw_type,) = self._unpack(prefix + "I", 4)
        # ISO WKB encodes Z/M as +1000/+2000/+3000, EWKB as high bit flags.
        has_z = bool(raw_type & 0x80000000)
        has_m = bool(raw_type & 0x40000000)
        raw_type &= 0x0FFFFFFF
        base_type, dimension_code = raw_type % 1000, raw_type // 1000
        if dimension_code in (1, 3):
            has_z = True
        if dimension_code in (2, 3):
            has_m = True
        type_name = _WKB_BASE_TYPES.get(base_type)
        if type_name is None:
            raise GeometryError(f"Nicht unterstützter WKB-Geometrietyp {raw_type}")
        dimensions = 2 + int(has_z) + int(has_m)
        coord_fmt = prefix + "d" * dimensions
        coord_size = 8 * dimensions

        def read_point() -> Point:
            values = self._unpack(coord_fmt, coord_size)
            return float(values[0]), float(values[1])

        def read_points() -> Tuple[Point, ...]:
            (count,) = self._unpack(prefix + "I", 4)
            return tuple(read_point() for _ in range(count))

        def read_polygon() -> Polygon:
            (ring_count,) = self._unpack(prefix + "I", 4)
            return tuple(read_points() for _ in range(ring_count))

        if type_name == "POINT":
            point = read_point()
            if math.isnan(point[0]) or math.isnan(point[1]):
                return Geometry()
            return Geometry(points=(point,))
        if type_name == "LINESTRING":
            line = read_points()
            return Geometry(lines=(line,) if line else ())
        if type_name == "POLYGON":
            polygon = read_polygon()
            return Geometry(polygons=(polygon,) if polygon else ())
        (count,) = self._unpack(prefix + "I", 4)
        return _combine([self.read_geometry() for _ in range(count)])


def parse_wkb(data: bytes, offset: int = 0) -> Geometry:
    """Parse plain (ISO or extended) WKB."""
    return _WkbReader(data, offset).read_geometry()


_GPKG_ENVELOPE_SIZES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


def gpkg_envelope(blob: bytes) -> Optional[BBox]:
    """Return the bounding box stored in a GeoPackage binary header, if any."""
    if len(blob) < 8 or blob[:2] != b"GP":
        return None
    flags = blob[3]
    envelope_size = _GPKG_ENVELOPE_SIZES.get((flags >> 1) & 0b111)
    if not envelope_size or len(blob) < 8 + envelope_size:
        return None
    prefix = "<" if flags & 1 else ">"
    min_x, max_x, min_y, max_y = struct.unpack(prefix + "dddd", blob[8:40])
    return min_x, min_y, max_x, max_y


def parse_gpkg_geometry(blob: bytes) -> Geometry:
    """Parse a GeoPackage binary geometry (``GP`` header followed by WKB)."""
    if len(blob) < 8 or blob[:2] != b"GP":
        raise GeometryError("Kein GeoPackage-Geometrie-Header")
    flags = blob[3]
    envelope_size = _GPKG_ENVELOPE_SIZES.get((flags >> 1) & 0b111)
    if envelope_size is None:
        raise GeometryError("Ungültiger GeoPackage-Envelope")
    if flags & 0b10000:
        return Geometry()
    return parse_wkb(blob, 8 + envelope_size)


# ---------------------------------------------------------------------------
# WKT
# ---------------------------------------------------------------------------

_WKT_TOKEN = re.compile(r"\s*(?:([A-Za-z]+)|([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)|([(),]))")
_WKT_TYPES = (
    "GEOMETRYCOLLECTION",
    "MULTIPOLYGON",
    "MULTILINESTRING",
    "MULTIPOINT",
    "POLYGON",
    "LINESTRING",
    "POINT",
)


class _WktReader:
    def __init__(self, text: str):
        self.tokens: List[str] = []
        position = 0
        text = text.strip()
        if text.upper().startswith("SRID="):
            text = text.split(";", 1)[-1]
        while position < len(text):
            match = _WKT_TOKEN.match(text, position)
            if not match or match.end() == position:
                if text[position:].strip():
                    raise GeometryError("WKT-Geometrie enthält ungültige Zeichen")
                break
            self.tokens.append(next(group for group in match.groups() if group is not None))
            position = match.end()
        self.index = 0

    def _peek(self) -> Optional[str]:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _next(self) -> str:
        token = self._peek()
        if token is None:
            raise GeometryError("WKT-Geometrie ist unvollständig")
        self.index += 1
        return token

    def _expect(self, token: str) -> None:
        if self._next() != token:
            raise GeometryError(f"WKT-Geometrie: '{token}' erwartet")

    def _is_number(self, token: Optional[str]) -> bool:
        return token is not None and token not in "()," and not token[0].isalpha()

    def _type_name(self) -> str:
        word = self._next().upper()
        for type_name in _WKT_TYPES:
            if word.startswith(type_name) and word[len(type_name) :] in ("", "Z", "M", "ZM"):
                if word == type_name and self._peek() and self._peek().upper() in ("Z", "M", "ZM"):
                    self.index += 1
                return type_name
        raise GeometryError(f"Nicht unterstützter WKT-Geometrietyp {word}")

    def _empty(self) -> bool:
        token = self._peek()
        if token is not None and token.upper() == "EMPTY":
            self.index += 1
            return True
        return False

    def _point(self) -> Point:
        values = []
        while self._is_number(self._peek()):
            values.append(float(self._next()))
        if not 2 <= len(values) <= 4:
            raise GeometryError("WKT-Koordinate braucht 2 bis 4 Werte")
        return values[0], values[1]

    def _point_list(self) -> Tuple[Point, ...]:
        self._expect("(")
        points = [self._point()]
        while self._peek() == ",":
            self.index += 1
            points.append(self._point())
        self._expect(")")
        return tuple(points)

    def _polygon(self) -> Polygon:
        self._expect("(")
        rings = [self._point_list()]
        while self._peek() == ",":
            self.index += 1
            rings.append(self._point_list())
        self._expect(")")
        return tuple(rings)

    def _sequence(self, read_item) -> list:
        self._expect("(")
        items = [read_item()]
        while self._peek() == ",":
            self.index += 1
            items.append(read_item())
        self._expect(")")
        return items

    def read_geometry(self) -> Geometry:
        type_name = self._type_name()
        if self._empty():
            return Geometry()
        if type_name == "POINT":
            self._expect("(")
            point = self._point()
            self._expect(")")
            return Geometry(points=(point,))
        if type_name == "LINESTRING":
            return Geometry(lines=(self._point_list(),))
        if type_name == "POLYGON":
            return Geometry(polygons=(self._polygon(),))
        if type_name == "MULTIPOINT":

            def read_member() -> Point:
                if self._peek() == "(":
                    self.index += 1
                    point = self._point()
                    self._expect(")")
                    return point
                return self._point()

            return Geometry(points=tuple(self._sequence(read_member)))
        if type_name == "MULTILINESTRING":
            return Geometry(lines=tuple(self._sequence(self._point_list)))
        if type_name == "MULTIPOLYGON":
            return Geometry(polygons=tuple(self._sequence(self._polygon)))
        return _combine(self._sequence(self.read_geometry))

    def read(self) -> Geometry:
        geometry = self.read_geometry()
        if self._peek() is not None:
            raise GeometryError("WKT-Geometrie enthält zusätzliche Zeichen")
        return geometry


def parse_wkt(text: str) -> Geometry:
    """Parse WKT/EWKT, including QGIS spellings such as ``MultiPolygonZ``."""
    return _WktReader(text).read()


def read_geometry(value: object) -> Optional[Geometry]:
    """Read a GeoPackage column value; ``None`` means no geometry stored.

    Raises ``GeometryError`` when a value is present but cannot be read.
    """
    if value is None:
        return None
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, (bytes, bytearray)):
        data = bytes(value)
        if data[:2] == b"GP":
            return parse_gpkg_geometry(data)
        return parse_wkb(data)
    if isinstance(value, str):
        if not value.strip():
            return None
        return parse_wkt(value)
    raise GeometryError(f"Nicht lesbarer Geometriewert vom Typ {type(value).__name__}")


def validate_study_area(geometry: Geometry) -> Optional[str]:
    """Return an error message if ``geometry`` is not a usable area polygon."""
    if geometry.is_empty or not geometry.polygons:
        return "Das Untersuchungsgebiet muss ein Polygon oder MultiPolygon sein."
    if geometry.points or geometry.lines:
        return "Das Untersuchungsgebiet darf nur Polygone enthalten."
    for polygon in geometry.polygons:
        for ring in polygon:
            if len(ring) < 4 or ring[0] != ring[-1]:
                return "Jeder Polygonring braucht mindestens vier Punkte und muss geschlossen sein."
    return None


# ---------------------------------------------------------------------------
# Distance
# ---------------------------------------------------------------------------


def _segments(geometry: Geometry) -> Iterator[Segment]:
    for point in geometry.points:
        yield point, point
    for line in geometry.lines:
        if len(line) == 1:
            yield line[0], line[0]
        for index in range(len(line) - 1):
            yield line[index], line[index + 1]
    for polygon in geometry.polygons:
        for ring in polygon:
            for index in range(len(ring) - 1):
                yield ring[index], ring[index + 1]


def _point_in_ring(point: Point, ring: Ring) -> bool:
    x, y = point
    inside = False
    count = len(ring)
    for index in range(count):
        x1, y1 = ring[index]
        x2, y2 = ring[(index + 1) % count]
        if (y1 > y) != (y2 > y):
            crossing_x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < crossing_x:
                inside = not inside
    return inside


def _point_in_polygon(point: Point, polygon: Polygon) -> bool:
    if not polygon or not _point_in_ring(point, polygon[0]):
        return False
    return not any(_point_in_ring(point, hole) for hole in polygon[1:])


def _part_start_points(geometry: Geometry) -> Iterator[Point]:
    yield from geometry.points
    for line in geometry.lines:
        if line:
            yield line[0]
    for polygon in geometry.polygons:
        if polygon and polygon[0]:
            yield polygon[0][0]


def _contains_any_part(container: Geometry, other: Geometry) -> bool:
    """True if one part of ``other`` starts inside a polygon of ``container``.

    Parts that only partly overlap are detected by the segment test instead.
    """
    return any(
        _point_in_polygon(point, polygon)
        for point in _part_start_points(other)
        for polygon in container.polygons
    )


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, c: Point) -> bool:
    return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])


def _segments_intersect(p1: Point, p2: Point, q1: Point, q2: Point) -> bool:
    d1 = _orientation(q1, q2, p1)
    d2 = _orientation(q1, q2, p2)
    d3 = _orientation(p1, p2, q1)
    d4 = _orientation(p1, p2, q2)
    if ((d1 > 0 > d2) or (d1 < 0 < d2)) and ((d3 > 0 > d4) or (d3 < 0 < d4)):
        return True
    return (
        (d1 == 0 and _on_segment(q1, q2, p1))
        or (d2 == 0 and _on_segment(q1, q2, p2))
        or (d3 == 0 and _on_segment(p1, p2, q1))
        or (d4 == 0 and _on_segment(p1, p2, q2))
    )


def _point_segment_distance(point: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return math.hypot(point[0] - a[0], point[1] - a[1])
    t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length_squared
    t = max(0.0, min(1.0, t))
    return math.hypot(point[0] - (a[0] + t * dx), point[1] - (a[1] + t * dy))


def _segment_distance(first: Segment, second: Segment) -> float:
    (p1, p2), (q1, q2) = first, second
    if _segments_intersect(p1, p2, q1, q2):
        return 0.0
    return min(
        _point_segment_distance(p1, q1, q2),
        _point_segment_distance(p2, q1, q2),
        _point_segment_distance(q1, p1, p2),
        _point_segment_distance(q2, p1, p2),
    )


def distance(first: Geometry, second: Geometry, *, stop_at: float = 0.0) -> float:
    """Minimum planar distance between two geometries (0 if they overlap).

    The search stops early once a distance ``<= stop_at`` is found.
    """
    if first.is_empty or second.is_empty:
        raise GeometryError("Abstand zu einer leeren Geometrie ist nicht definiert")
    if _contains_any_part(second, first) or _contains_any_part(first, second):
        return 0.0
    second_segments = list(_segments(second))
    best = math.inf
    for segment in _segments(first):
        for other in second_segments:
            best = min(best, _segment_distance(segment, other))
            if best <= stop_at:
                return best
    return best


def bboxes_within(first: BBox, second: BBox, max_distance: float) -> bool:
    """Quick reject: True if the boxes are at most ``max_distance`` apart."""
    return not (
        first[2] < second[0] - max_distance
        or first[0] > second[2] + max_distance
        or first[3] < second[1] - max_distance
        or first[1] > second[3] + max_distance
    )


def within_distance(feature: Geometry, area: Geometry, max_distance: float) -> bool:
    """True if ``feature`` lies within ``max_distance`` of ``area``."""
    feature_bbox, area_bbox = feature.bbox(), area.bbox()
    if feature_bbox is None or area_bbox is None:
        return False
    if not bboxes_within(feature_bbox, area_bbox, max_distance):
        return False
    return distance(feature, area, stop_at=max_distance) <= max_distance
