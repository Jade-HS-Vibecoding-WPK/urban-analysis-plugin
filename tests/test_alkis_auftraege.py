"""ALKIS download jobs per federal state (M10b, S9 part 2)."""

from datetime import date

from urban_analysis.sources import (
    STATE_BLOCKED,
    STATE_LATER,
    STATE_READY,
    alkis_states,
    load_catalog,
    plan_alkis_download,
    split_box,
    wfs_getfeature_url,
)

CATALOG = load_catalog()
# 2 km x 2 km in the project CRS, buffer 0 -> 4 km²; the box in degrees
AREA = "POLYGON ((447000 5888000, 449000 5888000, 449000 5890000, 447000 5890000, 447000 5888000))"
BOX = (8.215, 53.135, 8.245, 53.153)
TODAY = date(2026, 11, 19)


def plan(state, box=BOX, area=AREA):
    return plan_alkis_download(area, 0, box, state, catalog=CATALOG, today=TODAY)


def test_states_list_shows_what_works_where():
    states = {state.code: state for state in alkis_states(CATALOG)}
    assert len(states) == 16
    assert [s.name for s in alkis_states(CATALOG)][:2] == ["Baden-Württemberg", "Bayern"]
    ready = {code for code, state in states.items() if state.status == STATE_READY}
    assert ready == {"BB", "HH", "HE", "MV", "NI", "NW", "RP", "SN", "SH", "TH"}
    assert states["ST"].status == STATE_BLOCKED and "Lizenz" in states["ST"].note
    for later in ("BW", "BY", "BE", "HB", "SL"):
        assert states[later].status == STATE_LATER and states[later].note


def test_box_is_cut_into_tiles_of_about_one_kilometre():
    tiles = split_box(BOX, 1000)
    # about 2.0 km wide and 2.0 km high -> 3 x 2 tiles
    assert len(tiles) == 6
    west, south, east, north = BOX
    assert min(t[0] for t in tiles) == west and max(t[2] for t in tiles) == east
    assert min(t[1] for t in tiles) == south and max(t[3] for t in tiles) == north


def test_wfs_url_selects_in_degrees_and_delivers_in_the_service_crs():
    url = wfs_getfeature_url("https://example.org/wfs", "ave:Nutzung", (8.2, 53.1, 8.3, 53.2), "EPSG:25833")
    assert url == (
        "https://example.org/wfs?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=ave:Nutzung"
        "&SRSNAME=urn:ogc:def:crs:EPSG::25833"
        "&BBOX=53.100000,8.200000,53.200000,8.300000,urn:ogc:def:crs:EPSG::4326"
    )


def test_lower_saxony_gets_buildings_land_use_and_parcels_per_tile():
    result = plan("NI")

    assert result.issues == []
    layers = [request.layer_name for request in result.requests]
    tiles = len(split_box(BOX, 1000))
    assert layers == ["GebaeudeBauwerk"] * tiles + ["Nutzung"] * tiles + ["Flurstueck"] * tiles
    first = result.requests[0]
    assert first.source_kind == "ALKIS" and first.query == ""
    assert first.delivery_crs == "EPSG:25832"
    assert (first.part, first.parts) == (1, tiles)
    assert first.raw_file_name == "alkis_NI_GebaeudeBauwerk_01_2026-11-19.gml"
    assert first.geopackage_name == "alkis_NI_2026-11-19.gpkg"
    assert first.max_features == 10000 and first.id_field == "oid"
    assert first.attribution == "© GeoBasis-DE/LGLN 2026, CC BY 4.0"
    assert first.licence_url.startswith("https://creativecommons.org/licenses/by/4.0")
    assert "TYPENAMES=ave:GebaeudeBauwerk" in first.url


def test_eastern_states_deliver_in_their_own_crs():
    assert plan("SN").requests[0].delivery_crs == "EPSG:25833"


def test_states_not_ready_get_a_hint_and_no_jobs():
    berlin = plan("BE")
    assert berlin.requests == []
    (hint,) = berlin.issues
    assert hint.code == "alkis-not-available" and hint.severity == "warning"
    assert hint.message.startswith("ALKIS für Berlin kommt später:")
    assert hint.message.endswith("Das Plugin verwendet OSM.")
    assert hint.action

    saxony_anhalt = plan("ST")
    assert saxony_anhalt.requests == []
    assert saxony_anhalt.issues[0].message.startswith("ALKIS für Sachsen-Anhalt ist gesperrt:")

    bavaria = plan("BY")
    assert bavaria.requests == []  # never parcels in Bavaria (E28)


def test_unknown_state_and_too_large_area_are_errors():
    unknown = plan("XX")
    assert unknown.requests == [] and unknown.issues[0].severity == "error"

    huge = "POLYGON ((400000 5800000, 410000 5800000, 410000 5810000, 400000 5810000, 400000 5800000))"
    too_large = plan("NI", area=huge)
    assert too_large.requests == []
    assert too_large.issues[0].code == "area-too-large"
