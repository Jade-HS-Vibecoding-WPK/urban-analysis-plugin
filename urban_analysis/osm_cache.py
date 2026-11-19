"""Niedersachsen-Cache as fallback when Overpass fails (E35).

The team's cache (https://github.com/Jade-HS-Vibecoding-WPK/niedersachsen-cache)
holds OpenStreetMap data of the large cities of Lower Saxony and the area
around Oldenburg as small tiles in the format of an Overpass ``out geom``
answer.  It is rebuilt every week.

This module is QGIS-free and uses only the standard library, like
``sources.py``.  It

1. checks whether the download rectangle lies completely in the cache and
   lists the tile files to fetch (``plan_cache_download``),
2. turns the fetched tiles into the three layers ``points``, ``lines`` and
   ``multipolygons`` with the same columns GDAL writes for an ``.osm`` file
   (``osm_id``, ``osm_way_id``, ``name`` …, ``other_tags``), so the OSM
   profile in ``mapping_rules.json`` works unchanged (``elements_to_layers``),
3. builds the visible hint that the data came from the cache and which
   features are missing there (``cache_issue``).

Fetching the files, writing them and converting to the project CRS happen in
QGIS (W11b, Person Windows).  The cache is only used when Overpass failed
after all retries; nothing is reused silently (E15, E35).
"""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .contracts import ValidationIssue
from .sources import LonLatBox, check_lonlat_box

Tile = Tuple[int, int]
Coordinate = Tuple[float, float]  # (lon, lat)

# Columns GDAL's OSM driver writes per layer (osmconf.ini, default).
GDAL_COLUMNS: Mapping[str, Tuple[str, ...]] = {
    "points": ("osm_id", "name", "barrier", "highway", "ref", "address", "is_in", "place", "man_made"),
    "lines": ("osm_id", "name", "highway", "waterway", "aerialway", "barrier", "man_made", "railway", "z_order"),
    "multipolygons": (
        "osm_id", "osm_way_id", "name", "type", "aeroway", "amenity", "admin_level", "barrier",
        "boundary", "building", "craft", "geological", "historic", "land_area", "landuse",
        "leisure", "man_made", "military", "natural", "office", "place", "shop", "sport", "tourism",
    ),
}
# Closed ways with one of these keys are areas (GDAL osmconf.ini default).
AREA_KEYS = (
    "aeroway", "amenity", "boundary", "building", "craft", "geological", "historic", "landuse",
    "leisure", "military", "natural", "office", "place", "shop", "sport", "tourism",
)
_COMPUTED = {"osm_id", "osm_way_id", "z_order"}


@dataclass(frozen=True)
class CachePlan:
    """Whether the cache can stand in for Overpass, and what to fetch."""

    usable: bool
    reason: str  # why the cache cannot be used (empty if usable)
    tile_urls: Tuple[str, ...] = ()
    data_date: str = ""  # "datenstand" of the cache, ISO time
    missing_keys: Tuple[str, ...] = ()  # asked for, but not in the cache
    raw_file_name: str = ""
    geopackage_name: str = ""
    geojson_name: str = ""  # with "{layer}" placeholder
    attribution: str = ""
    licence: str = ""
    licence_url: str = ""


def manifest_url(catalog: Mapping[str, Any]) -> str:
    """Address of the cache's ``manifest.json`` (QGIS fetches it first)."""
    cache = catalog["osm_cache"]
    return cache["basis_url"] + cache["manifest"]


def tile_of(lon: float, lat: float, zoom: int) -> Tile:
    """Web-Mercator tile (x, y) that contains the point."""
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def tiles_in_box(box: LonLatBox, zoom: int) -> List[Tile]:
    """All tiles touching the rectangle (west, south, east, north)."""
    west, south, east, north = box
    x_min, y_min = tile_of(west, north, zoom)
    x_max, y_max = tile_of(east, south, zoom)
    return [(x, y) for y in range(y_min, y_max + 1) for x in range(x_min, x_max + 1)]


def covered_tiles(manifest: Mapping[str, Any]) -> Set[Tile]:
    """z15 tiles the cache holds, from the bit masks of all places."""
    covered: Set[Tile] = set()
    for place in manifest.get("staedte", ()):
        mask = place.get("kacheln") or {}
        bits = base64.b64decode(mask.get("bits", ""))
        x0, y0, width = int(mask.get("x0", 0)), int(mask.get("y0", 0)), int(mask.get("breite", 0))
        if not width:
            continue
        for index in range(len(bits) * 8):
            if bits[index // 8] >> (index % 8) & 1:
                covered.add((x0 + index % width, y0 + index // width))
    return covered


def _format_date(iso: str) -> str:
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return iso


def plan_cache_download(
    box: LonLatBox,
    manifest: Mapping[str, Any],
    catalog: Mapping[str, Any],
    today: Optional[date] = None,
) -> CachePlan:
    """Plan the fallback download from the cache for ``box`` (EPSG:4326).

    Usable only if every z15 tile of the box is in the cache; a partly
    covered area would give incomplete data without anyone noticing.
    """
    problem = check_lonlat_box(box)
    if problem:
        return CachePlan(False, problem)
    tiles = manifest.get("kacheln") or {}
    big = manifest.get("gross") or {}
    zoom = int(tiles.get("zoom", 15))
    needed = tiles_in_box(box, zoom)
    covered = covered_tiles(manifest)
    if not needed or any(tile not in covered for tile in needed):
        return CachePlan(
            False,
            "Das Gebiet liegt nicht vollständig im Niedersachsen-Cache (er enthält nur die "
            "Großstädte Niedersachsens und die Gemeinden rund um Oldenburg).",
        )
    cache = catalog["osm_cache"]
    base = cache["basis_url"]
    urls = [base + tiles["pfad"].format(x=x, y=y) for x, y in needed]
    if big.get("pfad"):
        shift = zoom - int(big.get("zoom", 12))
        big_tiles = sorted({(x >> shift, y >> shift) for x, y in needed})
        urls += [base + big["pfad"].format(x=x, y=y) for x, y in big_tiles]

    in_cache = {str(key).split("=")[0] for key in manifest.get("schluessel", ())}
    asked = catalog["osm"]["abfrage"]["schluessel"]
    day = (today or date.today()).isoformat()
    return CachePlan(
        usable=True,
        reason="",
        tile_urls=tuple(urls),
        data_date=str(manifest.get("datenstand", "")),
        missing_keys=tuple(key for key in asked if key not in in_cache),
        raw_file_name=cache["rohdatei"].format(datum=day),
        geopackage_name=cache["geopackage"].format(datum=day),
        geojson_name=cache["geojson"].replace("{datum}", day),
        attribution=cache["quellenvermerk"],
        licence=cache["lizenz"],
        licence_url=cache["lizenz_url"],
    )


def merge_tiles(tiles: Iterable[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    """All elements of the fetched tiles, each object only once.

    An object lies in every tile it touches; the first copy is kept.
    """
    seen: Set[Tuple[str, Any]] = set()
    elements: List[Mapping[str, Any]] = []
    for tile in tiles:
        for element in tile.get("elements", ()):
            key = (element.get("type"), element.get("id"))
            if key not in seen:
                seen.add(key)
                elements.append(element)
    return elements


def _hstore(tags: Mapping[str, str]) -> Optional[str]:
    """Tags as GDAL writes ``other_tags``: ``"key"=>"value",…``."""
    if not tags:
        return None
    escape = lambda text: str(text).replace("\\", "\\\\").replace('"', '\\"')  # noqa: E731
    return ",".join(f'"{escape(key)}"=>"{escape(value)}"' for key, value in tags.items())


def _properties(layer: str, tags: Mapping[str, str], ids: Mapping[str, Optional[str]]) -> Dict[str, Any]:
    columns = GDAL_COLUMNS[layer]
    properties: Dict[str, Any] = {}
    for column in columns:
        properties[column] = ids.get(column) if column in _COMPUTED else tags.get(column)
    rest = {key: value for key, value in tags.items() if key not in columns}
    properties["other_tags"] = _hstore(rest)
    return properties


def _is_area(tags: Mapping[str, str]) -> bool:
    if tags.get("area") == "no":
        return False
    return tags.get("area") == "yes" or any(key in tags for key in AREA_KEYS)


def _line(geometry: Any) -> List[Coordinate]:
    return [(float(point["lon"]), float(point["lat"])) for point in geometry or () if point]


def _join_rings(parts: Sequence[List[Coordinate]]) -> Optional[List[List[Coordinate]]]:
    """Join way pieces end to end into closed rings; ``None`` if one stays open."""
    open_parts = [list(part) for part in parts if len(part) >= 2]
    rings: List[List[Coordinate]] = []
    while open_parts:
        ring = open_parts.pop(0)
        while ring[0] != ring[-1]:
            for index, part in enumerate(open_parts):
                if part[0] == ring[-1]:
                    ring.extend(part[1:])
                elif part[-1] == ring[-1]:
                    ring.extend(reversed(part[:-1]))
                else:
                    continue
                open_parts.pop(index)
                break
            else:
                return None
        if len(ring) >= 4:
            rings.append(ring)
    return rings


def _inside(point: Coordinate, ring: Sequence[Coordinate]) -> bool:
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _multipolygon(members: Sequence[Mapping[str, Any]]) -> Optional[List[List[List[Coordinate]]]]:
    outer_parts = [_line(m.get("geometry")) for m in members if m.get("type") == "way" and m.get("role") != "inner"]
    inner_parts = [_line(m.get("geometry")) for m in members if m.get("type") == "way" and m.get("role") == "inner"]
    outers = _join_rings(outer_parts)
    inners = _join_rings(inner_parts)
    if not outers or inners is None:
        return None
    polygons = [[outer] for outer in outers]
    for inner in inners:
        for polygon in polygons:
            if _inside(inner[0], polygon[0]):
                polygon.append(inner)
                break
    return polygons


def _feature(geometry_type: str, coordinates: Any, properties: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": geometry_type, "coordinates": coordinates},
        "properties": properties,
    }


def elements_to_layers(
    elements: Sequence[Mapping[str, Any]], keys: Sequence[str]
) -> Tuple[Dict[str, Dict[str, Any]], int]:
    """GeoJSON ``FeatureCollection`` per GDAL OSM layer, plus skipped relations.

    Only objects with one of ``keys`` (the keys of the Overpass query) are
    taken, so the result matches what Overpass would have delivered.
    Coordinates stay in EPSG:4326; QGIS converts them to the project CRS.
    Multipolygon relations whose rings cannot be closed (e.g. parts outside
    Lower Saxony) are left out and counted.
    """
    wanted = set(keys)
    layers: Dict[str, List[Dict[str, Any]]] = {name: [] for name in GDAL_COLUMNS}
    skipped = 0
    for element in elements:
        tags = {str(key): str(value) for key, value in (element.get("tags") or {}).items()}
        if not wanted.intersection(tags):
            continue
        kind, osm_id = element.get("type"), str(element.get("id"))
        if kind == "node" and "lon" in element and "lat" in element:
            layers["points"].append(
                _feature(
                    "Point",
                    [float(element["lon"]), float(element["lat"])],
                    _properties("points", tags, {"osm_id": osm_id}),
                )
            )
        elif kind == "way":
            line = _line(element.get("geometry"))
            if len(line) < 2:
                continue
            if len(line) >= 4 and line[0] == line[-1] and _is_area(tags):
                layers["multipolygons"].append(
                    _feature(
                        "MultiPolygon",
                        [[[list(point) for point in line]]],
                        _properties("multipolygons", tags, {"osm_way_id": osm_id}),
                    )
                )
            else:
                layers["lines"].append(
                    _feature(
                        "LineString",
                        [list(point) for point in line],
                        _properties("lines", tags, {"osm_id": osm_id}),
                    )
                )
        elif kind == "relation" and tags.get("type") == "multipolygon":
            polygons = _multipolygon(element.get("members") or ())
            if polygons is None:
                skipped += 1
                continue
            layers["multipolygons"].append(
                _feature(
                    "MultiPolygon",
                    [[[list(point) for point in ring] for ring in polygon] for polygon in polygons],
                    _properties("multipolygons", tags, {"osm_id": osm_id}),
                )
            )
    collections = {
        name: {"type": "FeatureCollection", "features": features} for name, features in layers.items()
    }
    return collections, skipped


def cache_issue(plan: CachePlan, catalog: Mapping[str, Any], skipped_relations: int = 0) -> ValidationIssue:
    """Visible hint that OSM came from the cache, and what is missing there."""
    names = catalog["osm_cache"].get("merkmal_namen", {})
    missing = [names.get(key, key) for key in plan.missing_keys]
    message = (
        f"OSM-Daten kommen aus dem Niedersachsen-Cache (Stand {_format_date(plan.data_date)}), "
        "weil der OSM-Server nicht geantwortet hat."
    )
    if missing:
        message += " Nicht enthalten: " + ", ".join(missing) + "."
    details = (
        "Der Niedersachsen-Cache wird jede Woche aus OpenStreetMap neu gebaut. Er enthält nur "
        "einen Teil der Merkmale. Wenn du alles brauchst, lade die Daten später noch einmal, "
        "sobald der OSM-Server wieder antwortet."
    )
    if skipped_relations:
        details += (
            f" {skipped_relations} große Fläche(n) konnten nicht vollständig gebaut werden "
            "und fehlen (z. B. weil sie über Niedersachsen hinausreichen)."
        )
    return ValidationIssue(
        code="osm-from-cache",
        message=message,
        severity="info",
        rule="Niedersachsen-Cache (E35)",
        details=details,
    )
