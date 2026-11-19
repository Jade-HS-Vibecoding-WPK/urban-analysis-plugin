"""F5 / W18: map styles and PDF layout (QGIS-free parts)."""

from datetime import date

from urban_analysis.map_styles import (
    BUILDINGS,
    MAP_STYLES,
    category_colors,
    draw_rank,
)
from urban_analysis.outputs import layout_frames, page_size_mm, scale_label, sources_text


def test_three_map_styles():
    assert set(MAP_STYLES) == {"nutzung", "schwarzplan", "graustufen"}


def test_plan_colours_follow_the_user_wishes():
    assert category_colors("Bahnflächen")[0] == "#8c9196"  # dark grey
    for water in ("Wasserflächen", "Gewässer", "Schiffsverkehrsflächen"):
        red, green, blue = (int(category_colors(water)[0][i:i + 2], 16) for i in (1, 3, 5))
        assert blue > red and blue > green, water  # shades of blue
    for green_area in ("Grünflächen", "Hecken und Baumreihen"):
        red, green, blue = (int(category_colors(green_area)[0][i:i + 2], 16) for i in (1, 3, 5))
        assert green > red and green > blue, green_area


def test_schwarzplan_buildings_black_rest_light():
    for building in BUILDINGS:
        assert category_colors(building, "schwarzplan")[0] == "#000000"
    assert category_colors("Grünflächen", "schwarzplan")[0] == "#f7f7f7"


def test_greyscale_has_no_colour():
    fill, outline = category_colors("Grünflächen", "graustufen")
    assert fill[1:3] == fill[3:5] == fill[5:7]


def test_buildings_are_drawn_above_land_use():
    assert draw_rank("Gebäude") > draw_rank("Straßen") > draw_rank("Nutzungsflächen")


def test_page_sizes_and_frames():
    assert page_size_mm("A3", "quer") == (420, 297)
    assert page_size_mm("A0", "hoch") == (841, 1189)
    frames = layout_frames(420, 297, "quer")
    mx, my, mw, mh = frames["map"]
    px, py, pw, ph = frames["panel"]
    assert mw > pw and px > mx + mw  # map left, panel right
    frames = layout_frames(297, 420, "hoch")
    assert frames["panel"][1] > frames["map"][1] + frames["map"][3]  # panel below


def test_pdf_orientation_follows_the_area():
    from urban_analysis.outputs import auto_orientation

    assert auto_orientation(3000, 2000) == "quer"
    assert auto_orientation(1500, 2600) == "hoch"


def test_every_run_gets_its_own_group():
    from urban_analysis.outputs import run_group_name

    base = "Urban Analysis – Siedlungsstruktur"
    assert run_group_name(base, set(), "10:42") == base
    assert run_group_name(base, {base}, "10:42") == f"{base} (10:42)"
    assert run_group_name(base, {base, f"{base} (10:42)"}, "10:42") == f"{base} (10:42, 2)"


def test_crs_warning_and_copy_name():
    from urban_analysis.guided_dialog import crs_mismatch_text
    from urban_analysis.osm_download import reprojected_name

    text = crs_mismatch_text("EPSG:3857", "EPSG:25832")
    assert "EPSG:3857" in text and "EPSG:25832" in text and "unverändert" in text
    assert reprojected_name("C:/x/daten.gpkg", "EPSG:25832") == "daten_EPSG25832.gpkg"


def test_scale_and_sources_texts():
    assert scale_label(None) == "passend zum Gebiet"
    assert scale_label(5000) == "1:5.000"
    text = sources_text("© OpenStreetMap-Mitwirkende, ODbL", date(2026, 11, 19))
    assert text.startswith("Datenquellen und Lizenzen")
    assert "ODbL" in text and "verändert" in text and "19.11.2026" in text
