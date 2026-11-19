"""W10 part 2 / M13 / M14: ALKIS download, several sources, licence block (QGIS-free parts)."""

from types import SimpleNamespace

from urban_analysis.guided_dialog import (
    source_choice_hint_text,
    source_title_text,
    sources_applied_text,
    uncertain_sources_label,
)
from urban_analysis.osm_download import (
    alkis_error_text,
    alkis_progress_text,
    truncated_text,
    wfs_exception_text,
)
from urban_analysis.outputs import data_source_text, licence_lines


def test_wfs_error_report_is_recognised():
    report = (b'<?xml version="1.0"?><ows:ExceptionReport><ows:Exception>'
              b'<ows:ExceptionText>BBOX ungueltig</ows:ExceptionText></ows:Exception>'
              b'</ows:ExceptionReport>')
    assert wfs_exception_text(report) == "BBOX ungueltig"
    assert wfs_exception_text(b"<wfs:FeatureCollection/>") is None


def test_alkis_messages_say_what_to_do():
    assert "Was tun" in alkis_error_text(0, "timeout", 4)
    assert "überlastet" in alkis_error_text(503, "busy", 4)
    assert "Was tun" in alkis_error_text(400, "bad", 1)
    text = truncated_text("GebaeudeBauwerk", 3, 12, 10000)
    assert "Gebäude" in text and "Teil 3 von 12" in text and "verkleinern" in text
    assert alkis_progress_text("Nutzung", 1, 4) == "ALKIS – Nutzung wird geladen (Teil 1 von 4) …"


def used(name, attribution, licence, url, count=5):
    return SimpleNamespace(name=name, attribution=attribution, licence=licence,
                           licence_url=url, record_count=count)


def test_licence_block_lists_every_used_source():
    sources = [
        used("OpenStreetMap", "© OpenStreetMap-Mitwirkende", "ODbL", "https://osm.org/copyright"),
        used("ALKIS Niedersachsen", "© GeoBasis-DE/LGLN 2026, CC BY 4.0", "CC-BY-4.0",
             "https://creativecommons.org/licenses/by/4.0/deed.de"),
    ]
    lines = licence_lines(sources)
    assert lines[0] == "© OpenStreetMap-Mitwirkende (ODbL) (https://osm.org/copyright)".replace(
        " (ODbL)", ", ODbL")
    # the licence is not repeated when the attribution already names it
    assert lines[1] == ("© GeoBasis-DE/LGLN 2026, CC BY 4.0 "
                        "(https://creativecommons.org/licenses/by/4.0/deed.de)")
    assert licence_lines([used("X", "© Amt", "dl-de/by-2-0", "")]) == ["© Amt, dl-de/by-2-0"]
    # the pre-filled text is not repeated, an own note is added
    auto = "© OpenStreetMap-Mitwirkende; © GeoBasis-DE/LGLN 2026, CC BY 4.0"
    assert data_source_text(sources, auto).count("\n") == 1
    assert data_source_text(sources, "Eigene Kartierung 2026").endswith("Eigene Kartierung 2026")
    assert data_source_text([], "Nur Text") == "Nur Text"


def test_same_layer_name_from_two_sources_names_the_source():
    from urban_analysis.contracts import LayerDescriptor
    from urban_analysis.outputs import result_layer_names

    layers = [
        LayerDescriptor("multipolygons_gebaeude", "x", "MultiPolygon", "osm.gpkg",
                        category="Gebäude", source_kind="OSM"),
        LayerDescriptor("GebaeudeBauwerk_gebaeude", "y", "MultiPolygon", "alkis.gpkg",
                        category="Gebäude", source_kind="ALKIS"),
    ]
    assert set(result_layer_names(layers).values()) == {"Gebäude (OSM)", "Gebäude (ALKIS)"}


def test_source_choice_texts():
    choice = SimpleNamespace(group_count=10, uncertain_count=3)
    assert source_title_text("Gebäude", 812, ("ALKIS", "OSM")) == "Gebäude: 812 in ALKIS und OSM"
    assert source_choice_hint_text(choice) == (
        "7 sichere Paare werden auf die gewählte Quelle reduziert, 3 sind unsicher.")
    assert uncertain_sources_label(3) == "Auch die 3 unsicheren Fälle so entscheiden"
    assert "nichts" in sources_applied_text(0)
    assert "12" in sources_applied_text(12)


def test_maintenance_page_of_the_alkis_service_is_an_error():
    from urban_analysis.osm_download import wfs_exception_text

    page = b"<!DOCTYPE html><html><head><title>Wartung</title></head><body>Wartung</body></html>"
    assert "Wartung" in wfs_exception_text(page)
    assert wfs_exception_text(b'<?xml version="1.0"?><wfs:FeatureCollection/>') is None
