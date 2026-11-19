"""Niedersachsen-Cache as fallback for Overpass (E35)."""

import base64

from urban_analysis.mapping import parse_tags
from urban_analysis.osm_cache import (
    cache_issue,
    covered_tiles,
    elements_to_layers,
    manifest_url,
    merge_tiles,
    plan_cache_download,
    tile_of,
    tiles_in_box,
)
from urban_analysis.sources import load_catalog

CATALOG = load_catalog()
KEYS = CATALOG["osm"]["abfrage"]["schluessel"]
BOX = (8.24, 53.15, 8.25, 53.155)  # a few hundred metres in Oldenburg


def manifest_covering(tiles, extra_keys=()):
    """A manifest whose one place covers exactly ``tiles`` (z15)."""
    xs, ys = [x for x, _ in tiles], [y for _, y in tiles]
    x0, y0 = min(xs), min(ys)
    width, height = max(xs) - x0 + 1, max(ys) - y0 + 1
    bits = bytearray((width * height + 7) // 8)
    for x, y in tiles:
        index = (y - y0) * width + (x - x0)
        bits[index // 8] |= 1 << (index % 8)
    return {
        "datenstand": "2026-11-17T21:24:30Z",
        "kacheln": {"zoom": 15, "pfad": "osm/15/{x}/{y}.json.gz"},
        "gross": {"zoom": 12, "pfad": "osm-gross/12/{x}/{y}.json.gz"},
        "schluessel": ["building", "highway", "amenity", "shop", "leisure", "landuse", "natural",
                       "water", "waterway", "railway", "public_transport", "healthcare",
                       "man_made", "place", "boundary=administrative", *extra_keys],
        "staedte": [{
            "id": "test",
            "kacheln": {"x0": x0, "y0": y0, "breite": width, "hoehe": height,
                        "bits": base64.b64encode(bytes(bits)).decode()},
        }],
    }


def test_tiles_of_a_box_and_the_cache_mask():
    tiles = tiles_in_box(BOX, 15)
    assert tile_of(8.24, 53.155, 15) == tiles[0]
    assert covered_tiles(manifest_covering(tiles)) == set(tiles)


def test_plan_lists_small_and_big_tiles_and_missing_keys():
    tiles = tiles_in_box(BOX, 15)
    plan = plan_cache_download(BOX, manifest_covering(tiles), CATALOG)

    assert plan.usable and plan.reason == ""
    base = CATALOG["osm_cache"]["basis_url"]
    small = [url for url in plan.tile_urls if "/osm/15/" in url]
    big = [url for url in plan.tile_urls if "/osm-gross/12/" in url]
    assert len(small) == len(tiles) and all(url.startswith(base) for url in plan.tile_urls)
    assert big == [base + f"osm-gross/12/{tiles[0][0] >> 3}/{tiles[0][1] >> 3}.json.gz"]
    # M25: the topic keys are not in this cache manifest yet, so they are named too.
    assert plan.missing_keys == (
        "barrier", "building:part", "power", "craft", "heritage", "historic", "office", "tourism"
    )
    assert plan.attribution.startswith("© OpenStreetMap-Mitwirkende")
    assert manifest_url(CATALOG).endswith("/daten/manifest.json")


def test_area_only_partly_in_the_cache_is_not_used():
    tiles = tiles_in_box(BOX, 15)
    plan = plan_cache_download(BOX, manifest_covering(tiles[:-1]), CATALOG)
    assert not plan.usable
    assert "nicht vollständig im Niedersachsen-Cache" in plan.reason
    assert plan.tile_urls == ()


def test_objects_in_several_tiles_are_taken_once():
    node = {"type": "node", "id": 1, "lat": 53.1, "lon": 8.2, "tags": {"shop": "bakery"}}
    merged = merge_tiles([{"elements": [node]}, {"elements": [dict(node)]}])
    assert merged == [node]


def ring(x, y, size=0.001):
    return [{"lon": x, "lat": y}, {"lon": x + size, "lat": y}, {"lon": x + size, "lat": y + size},
            {"lon": x, "lat": y + size}, {"lon": x, "lat": y}]


def test_elements_become_gdal_like_layers():
    elements = [
        {"type": "node", "id": 1, "lat": 53.1, "lon": 8.2,
         "tags": {"shop": "supermarket", "name": 'Markt "Mitte"', "opening_hours": "Mo-Sa"}},
        {"type": "node", "id": 2, "lat": 53.1, "lon": 8.2, "tags": {"vending": "parcel"}},  # not asked for
        {"type": "way", "id": 10, "geometry": ring(8.2, 53.1), "tags": {"building": "house", "building:levels": "2"}},
        {"type": "way", "id": 11, "geometry": ring(8.3, 53.1), "tags": {"highway": "residential"}},
        {"type": "way", "id": 12, "geometry": ring(8.4, 53.1), "tags": {"highway": "pedestrian", "area": "yes"}},
        {"type": "way", "id": 13, "geometry": ring(8.5, 53.1)[:3], "tags": {"highway": "footway"}},
    ]
    layers, skipped = elements_to_layers(elements, KEYS)

    assert skipped == 0
    (point,) = layers["points"]["features"]
    assert point["geometry"] == {"type": "Point", "coordinates": [8.2, 53.1]}
    props = point["properties"]
    assert props["osm_id"] == "1" and props["name"] == 'Markt "Mitte"'
    assert parse_tags(props["other_tags"]) == {"shop": "supermarket", "opening_hours": "Mo-Sa"}

    areas = {f["properties"]["osm_way_id"]: f for f in layers["multipolygons"]["features"]}
    assert set(areas) == {"10", "12"}
    assert areas["10"]["properties"]["building"] == "house"
    assert areas["10"]["properties"]["osm_id"] is None
    assert parse_tags(areas["10"]["properties"]["other_tags"]) == {"building:levels": "2"}

    lines = {f["properties"]["osm_id"]: f for f in layers["lines"]["features"]}
    assert set(lines) == {"11", "13"}  # closed street stays a line without area=yes
    assert lines["11"]["properties"]["highway"] == "residential"


def test_multipolygon_relations_are_joined_from_way_pieces():
    outer = ring(8.2, 53.1, 0.01)
    first, second = outer[:3], outer[2:]
    hole = ring(8.203, 53.103, 0.001)
    relation = {
        "type": "relation", "id": 99, "tags": {"type": "multipolygon", "landuse": "grass"},
        "members": [
            {"type": "way", "ref": 1, "role": "outer", "geometry": first},
            {"type": "way", "ref": 2, "role": "outer", "geometry": list(reversed(second))},
            {"type": "way", "ref": 3, "role": "inner", "geometry": hole},
        ],
    }
    broken = {
        "type": "relation", "id": 100, "tags": {"type": "multipolygon", "landuse": "forest"},
        "members": [{"type": "way", "ref": 4, "role": "outer", "geometry": first}],
    }
    layers, skipped = elements_to_layers([relation, broken], KEYS)

    assert skipped == 1
    (area,) = layers["multipolygons"]["features"]
    assert area["properties"]["osm_id"] == "99" and area["properties"]["type"] == "multipolygon"
    (polygon,) = area["geometry"]["coordinates"]
    assert len(polygon) == 2  # outer ring and the hole
    assert polygon[0][0] == polygon[0][-1] and len(polygon[0]) == 5


def test_hint_names_the_missing_features_readably():
    tiles = tiles_in_box(BOX, 15)
    plan = plan_cache_download(BOX, manifest_covering(tiles), CATALOG)
    issue = cache_issue(plan, CATALOG, skipped_relations=2)

    assert issue.code == "osm-from-cache" and issue.severity == "info"
    assert issue.message == (
        "OSM-Daten kommen aus dem Niedersachsen-Cache (Stand 17.11.2026), weil der OSM-Server "
        "nicht geantwortet hat. Nicht enthalten: Hecken, Zäune und Mauern, Gebäudeteile, "
        "Stromleitungen und -anlagen, Handwerksbetriebe, Denkmalschutz, Historische Orte, Büros, "
        "Tourismus und Aussichtspunkte."
    )
    assert "2 große Fläche(n)" in issue.details
