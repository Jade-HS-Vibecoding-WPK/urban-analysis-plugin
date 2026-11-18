"""M10a: size check (E13) and the OSM download job (S9, part 1)."""

import json
from datetime import date
from pathlib import Path

import pytest

from urban_analysis.sources import (
    SourcesCatalogError,
    area_limits,
    check_area_size,
    download_box_km2,
    format_km2,
    load_catalog,
    osm_query,
    plan_osm_download,
)

# Donnerschwee-sized rectangle in EPSG:25832: 2041 m x 2582 m
AREA = "POLYGON ((446950 5888700, 448991 5888700, 448991 5891282, 446950 5891282, 446950 5888700))"
LONLAT = (8.21, 53.14, 8.26, 53.17)  # west, south, east, north
DAY = date(2026, 11, 18)
RULES_PATH = Path(__file__).resolve().parents[1] / "urban_analysis" / "mapping_rules.json"


def square_km(side_km):
    side = side_km * 1000
    return f"POLYGON ((0 0, {side} 0, {side} {side}, 0 {side}, 0 0))"


def test_size_is_the_rectangle_around_area_and_buffer_like_step_2():
    km2 = download_box_km2(AREA, 500)
    # same numbers as study_area.download_box_km2 in step 2: 3041 m x 3582 m
    assert round(km2, 1) == 10.9
    assert format_km2(km2) == "10,9"


def test_limits_come_from_the_catalog():
    assert area_limits(load_catalog()) == (25.0, 50.0)
    with pytest.raises(SourcesCatalogError):
        area_limits({"gebiet": {"warnung_km2": 60, "max_km2": 50}})


def test_warning_above_25_and_stop_above_50_km2():
    catalog = load_catalog()
    assert check_area_size(25.0, catalog) is None
    warning = check_area_size(36.0, catalog)
    assert warning.severity == "warning" and warning.requires_confirmation
    assert "36,0 km²" in warning.message
    error = check_area_size(60.0, catalog)
    assert error.severity == "error" and "60,0 km²" in error.message and "50,0 km²" in error.message
    assert check_area_size(50.0, catalog).severity == "warning"


def test_small_area_gives_one_osm_job_with_licence_and_file_names():
    plan = plan_osm_download(AREA, 500, LONLAT, today=DAY)

    assert plan.issues == [] and not plan.blocked
    (job,) = plan.requests
    assert job.source_kind == "OSM"
    assert job.url == "https://overpass-api.de/api/interpreter"
    assert job.delivery_crs == "EPSG:4326"
    assert job.raw_file_name == "osm_2026-11-18.osm"
    assert job.geopackage_name == "osm_2026-11-18.gpkg"
    assert job.attribution == "© OpenStreetMap-Mitwirkende, ODbL"
    assert job.licence == "ODbL-1.0" and job.licence_url.startswith("https://")


def test_large_area_warns_but_still_plans_the_download():
    plan = plan_osm_download(square_km(5), 500, LONLAT, today=DAY)  # 6 km x 6 km
    assert [issue.code for issue in plan.issues] == ["area-large"]
    assert len(plan.requests) == 1


def test_too_large_area_gives_no_job_and_a_clear_error():
    plan = plan_osm_download(square_km(7), 500, LONLAT, today=DAY)  # 8 km x 8 km = 64 km²
    assert plan.blocked and plan.requests == []
    assert plan.issues[0].code == "area-too-large"
    assert "64,0 km²" in plan.issues[0].message


def test_rectangle_not_in_degrees_is_refused():
    plan = plan_osm_download(AREA, 500, (446450, 5888200, 449491, 5891782), today=DAY)
    assert plan.blocked and plan.requests == []
    assert plan.issues[0].code == "download-box-invalid"
    assert "EPSG:4326" in plan.issues[0].message
    swapped = plan_osm_download(AREA, 500, (8.26, 53.14, 8.21, 53.17), today=DAY)
    assert swapped.issues[0].code == "download-box-invalid"


def test_unreadable_study_area_is_an_error():
    plan = plan_osm_download("kein wkt", 500, LONLAT, today=DAY)
    assert plan.blocked and plan.issues[0].code == "area-unreadable"


def test_overpass_query_asks_for_all_profile_keys_in_the_box():
    query = osm_query(LONLAT, ["building", "building:part"], 300)
    assert query.startswith("[out:xml][timeout:300][bbox:53.140000,8.210000,53.170000,8.260000];")
    assert 'nw["building"];' in query and 'nw["building:part"];' in query
    assert 'rel["type"="multipolygon"];' in query
    assert "(._;>;);" in query and query.rstrip().endswith("out body qt;")


def test_query_keys_match_the_osm_profile():
    """Everything the OSM profile sorts by is downloaded (except boundary)."""
    settings = load_catalog()["osm"]["abfrage"]
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    (osm,) = [profile for profile in rules["profiles"] if profile["name"] == "OSM"]
    profile_keys = set()
    for layer in osm["layers"].values():
        profile_keys |= set(layer.get("tag_fields", []))
    assert profile_keys - set(settings["ohne_schluessel"]) == set(settings["schluessel"])
