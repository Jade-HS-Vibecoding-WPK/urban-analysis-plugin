"""W11: QGIS-free parts of the OSM download."""

from urllib.parse import parse_qs

from urban_analysis.osm_download import (
    RETRY_PAUSES_S,
    download_error_text,
    post_body,
    retry_text,
    unique_path,
)
from urban_analysis.study_area import LARGE_AREA_KM2, MAX_DOWNLOAD_KM2


def test_raw_files_are_never_overwritten(tmp_path):
    first = unique_path(tmp_path, "osm_2026-11-18.osm")
    assert first.name == "osm_2026-11-18.osm"
    first.write_text("alt")
    second = unique_path(tmp_path, "osm_2026-11-18.osm")
    assert second.name == "osm_2026-11-18_2.osm"
    second.write_text("auch alt")
    assert unique_path(tmp_path, "osm_2026-11-18.osm").name == "osm_2026-11-18_3.osm"


def test_query_is_sent_as_form_field_data():
    body = post_body('[out:xml];nw["building"];out;')
    assert parse_qs(body.decode("utf-8"))["data"] == ['[out:xml];nw["building"];out;']


def test_busy_server_is_tried_again_a_few_times_with_growing_pauses():
    assert list(RETRY_PAUSES_S) == sorted(RETRY_PAUSES_S) and len(RETRY_PAUSES_S) == 3
    assert retry_text(30, 2, 4) == (
        "Der OSM-Server ist gerade überlastet – neuer Versuch in 30 s (2 von 4)."
    )


def test_error_texts_say_what_to_do():
    offline = download_error_text(0, "Host not found", 1)
    assert "keine Verbindung" in offline and "Was tun" in offline and "Proxy" in offline
    busy = download_error_text(504, "Gateway Timeout", 4)
    assert "überlastet" in busy and "4" in busy and "Was tun" in busy
    other = download_error_text(400, "Bad Request", 1)
    assert "400" in other and "Was tun" in other


def test_same_category_from_lines_and_areas_gets_readable_names():
    from urban_analysis.contracts import LayerDescriptor
    from urban_analysis.outputs import result_layer_names

    layers = [
        LayerDescriptor("lines_strassen", "x", "LINESTRING", "osm.gpkg", category="Straßen"),
        LayerDescriptor("multipolygons_strassen", "x", "MULTIPOLYGON", "osm.gpkg", category="Straßen"),
        LayerDescriptor("multipolygons_gebaeude", "x", "MULTIPOLYGON", "osm.gpkg", category="Gebäude"),
    ]
    assert result_layer_names(layers) == {
        "lines_strassen": "Straßen (Linien)",
        "multipolygons_strassen": "Straßen (Flächen)",
        "multipolygons_gebaeude": "Gebäude",
    }


def test_osm_categories_have_own_icons():
    from urban_analysis.ui.classic_icons import missing_twins
    from urban_analysis.ui.layer_icons import icon_key

    for category in ("Hecken und Baumreihen", "Zäune und Mauern", "Sonstige OSM-Linien",
                     "Sonstige OSM-Flächen", "Gewässer", "Bahnstrecken"):
        assert icon_key(category=category) != "unbekannt", category
    assert not missing_twins()


def test_area_limits_come_from_the_catalog():
    assert (LARGE_AREA_KM2, MAX_DOWNLOAD_KM2) == (25.0, 50.0)
