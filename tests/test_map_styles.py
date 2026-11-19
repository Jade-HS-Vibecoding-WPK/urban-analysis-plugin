"""F5 / W18: map styles and PDF layout (QGIS-free parts)."""

from datetime import date

from urban_analysis.map_styles import (
    BUILDINGS,
    MAP_STYLES,
    category_colors,
    draw_rank,
)
from urban_analysis.outputs import page_size_mm, scale_label, sources_text


def test_three_map_styles():
    assert set(MAP_STYLES) == {"nutzung", "schwarzplan", "graustufen"}


def test_plan_colours_follow_the_user_wishes():
    fill = category_colors("Bahnflächen")[0]
    assert fill[1:3] == fill[3:5] or abs(int(fill[1:3], 16) - int(fill[5:7], 16)) < 12  # grey
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


def _overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw - 0.01 and bx < ax + aw - 0.01 and ay < by + bh - 0.01 and by < ay + ah - 0.01


SOURCES = ("Maßstab 1:5.000\n\nDatenquellen und Lizenzen\n© OpenStreetMap-Mitwirkende, ODbL "
           "(https://opendatacommons.org/licenses/odbl/1-0/)\n© GeoBasis-DE/LGLN 2026, CC BY 4.0 "
           "(https://creativecommons.org/licenses/by/4.0/deed.de)\nDaten verändert (zugeschnitten, "
           "harmonisiert) mit dem QGIS-Plugin Urban Analysis.\nStand: 19.11.2026")


def test_page_sizes_and_plan_without_overlaps():
    from urban_analysis.outputs import page_plan

    assert page_size_mm("A3", "quer") == (420, 297)
    assert page_size_mm("A0", "hoch") == (841, 1189)
    for page in ("A4", "A3", "A2", "A1", "A0"):
        for orientation in ("quer", "hoch"):
            plan = page_plan(page, orientation, title="Innenstadt", subtitle="UDO",
                             info_text=SOURCES)
            parts = [plan[k] for k in ("map", "title", "subtitle", "symbols", "text", "legend")]
            for i, first in enumerate(parts):
                for second in parts[i + 1:]:
                    assert not _overlap(first, second), (page, orientation, first, second)
            width, height = plan["width"], plan["height"]
            for x, y, w, h in parts:
                assert x >= 0 and y >= 0 and x + w <= width + 0.01 and y + h <= height + 0.01
            assert plan["fits"]
    quer = page_plan("A3", "quer")
    assert quer["legend"][0] > quer["map"][0] + quer["map"][2]  # panel right of the map
    hoch = page_plan("A3", "hoch")
    assert hoch["legend"][1] > hoch["map"][1] + hoch["map"][3]  # panel below the map


def test_font_sizes_grow_with_the_paper():
    from urban_analysis.outputs import font_sizes

    assert font_sizes("A4") == (14, 12)
    assert font_sizes("A0") == (24, 20)
    sizes = [font_sizes(page) for page in ("A4", "A3", "A2", "A1", "A0")]
    assert sizes == sorted(sizes)


def test_suggested_scale_and_warnings_for_own_scales():
    from urban_analysis.outputs import scale_problem, suggested_scale

    small_paper = suggested_scale(1200, 900, "A4", "quer")
    assert small_paper > suggested_scale(1200, 900, "A0", "quer")  # bigger paper, larger scale
    assert scale_problem(small_paper, small_paper) is None
    assert "passt das Gebiet nicht" in scale_problem(small_paper // 2, small_paper)
    assert "sehr klein" in scale_problem(small_paper * 5, small_paper)
    assert scale_problem(None, small_paper) is None


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


def test_fitting_scale_is_always_a_usual_one():
    from urban_analysis.outputs import SCALES, fitting_scale

    assert fitting_scale(7342) == 7500  # in-between steps: the map fills the paper better
    assert fitting_scale(2400) == 2500
    assert fitting_scale(2000) == 2000
    assert fitting_scale(40) == 50
    assert fitting_scale(345000) == 350000
    assert SCALES[0] is None and 50 in SCALES and 20000 in SCALES
    text = sources_text("© OpenStreetMap-Mitwirkende, ODbL", date(2026, 11, 19))
    assert text.startswith("Datenquellen und Lizenzen")
    assert "ODbL" in text and "verändert" in text and "19.11.2026" in text
