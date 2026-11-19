from pathlib import Path

from urban_analysis.contracts import LayerDescriptor
from urban_analysis.outputs import write_minimal_pdf


def test_minimal_pdf_contains_required_output_metadata(tmp_path: Path):
    target = tmp_path / "siedlungsstruktur.pdf"

    write_minimal_pdf(
        target,
        title="Urban Analysis - Siedlungsstruktur",
        study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
        buffer_meters=500,
        legend=("Gebäude", "Straßen"),
        data_source="Lokales GeoPackage",
    )

    content = target.read_bytes()
    assert content.startswith(b"%PDF-1.4")
    assert b"Urban Analysis - Siedlungsstruktur" in content
    assert b"Puffer: 500 m" in content
    assert b"Datenquelle: Lokales GeoPackage" in content


def test_selected_layer_descriptors_are_data_only():
    descriptor = LayerDescriptor("buildings", "Gebäude", "Polygon", "input.gpkg")
    assert descriptor.layer_id == "buildings"


# --- Ausgabe: ticks Punkte · Linien · Flächen ----------------------------------

def _descriptor(layer_id, geometry_type):
    from urban_analysis.contracts import LayerDescriptor

    return LayerDescriptor(layer_id=layer_id, name=layer_id, geometry_type=geometry_type, source_name="test")


def test_layers_are_counted_per_geometry_kind():
    from urban_analysis.outputs import geometry_counts

    layers = [_descriptor("points_gesundheit", "Point"), _descriptor("lines_strassen", ""),
              _descriptor("gebaeude", "MultiPolygon"), _descriptor("nutzung_gruen", "MultiPolygon")]
    assert geometry_counts(layers) == {"point": 1, "line": 1, "polygon": 2}


def test_only_ticked_geometry_kinds_are_created_unknown_ones_stay():
    from urban_analysis.outputs import with_geometry_kinds

    layers = [_descriptor("points_gesundheit", "Point"), _descriptor("lines_strassen", "LineString"),
              _descriptor("gebaeude", "MultiPolygon"), _descriptor("sonstiges", "")]
    kept = [d.layer_id for d in with_geometry_kinds(layers, ("point", "polygon"))]
    assert kept == ["points_gesundheit", "gebaeude", "sonstiges"]
    assert [d.layer_id for d in with_geometry_kinds(layers, ())] == ["sonstiges"]


def test_alkis_layers_with_generic_geometry_are_counted_by_their_table():
    from urban_analysis.outputs import geometry_counts

    layers = [_descriptor("gebaeude", "GEOMETRY"), _descriptor("nutzung_strassen", "GEOMETRY"),
              _descriptor("bauwerke_l", "GEOMETRY"), _descriptor("grenzpunkte", "GEOMETRY")]
    assert geometry_counts(layers) == {"point": 1, "line": 1, "polygon": 2}


# --- Schritt 8: Quellenangabe je Datenquelle ----------------------------------

def _sources():
    from urban_analysis.data_pipeline import SourceFile

    return [SourceFile("osm.gpkg", "OSM", "OpenStreetMap", attribution="© OpenStreetMap-Mitwirkende"),
            SourceFile("eigene.gpkg", "Eigene Datei", "eigene.gpkg")]


def test_own_files_must_get_their_own_source_text():
    from urban_analysis.outputs import (
        combined_source_text, default_source_texts, missing_source_texts)

    sources = _sources()
    texts = default_source_texts(sources)
    assert texts == {"osm.gpkg": "© OpenStreetMap-Mitwirkende", "eigene.gpkg": ""}
    assert missing_source_texts(sources, texts) == ["eigene.gpkg"]
    texts["eigene.gpkg"] = "Kartierung Studio, 2026"
    assert missing_source_texts(sources, texts) == []
    assert combined_source_text(sources, texts) == "© OpenStreetMap-Mitwirkende; Kartierung Studio, 2026"


def test_every_object_gets_the_source_text_of_its_own_source():
    from types import SimpleNamespace

    from urban_analysis.outputs import apply_source_texts, with_source_texts
    from urban_analysis.data_pipeline import HarmonizedRecord, UsedSource

    records = [HarmonizedRecord("a", 1, {"source": "© OpenStreetMap-Mitwirkende"}, source_file="osm.gpkg"),
               HarmonizedRecord("b", 2, {"source": "Eigene Datei: eigene.gpkg"}, source_file="eigene.gpkg")]
    texts = {"osm.gpkg": "© OpenStreetMap-Mitwirkende", "eigene.gpkg": "Kartierung Studio, 2026"}
    updated = apply_source_texts(records, texts)
    assert [r.attributes["source"] for r in updated] == ["© OpenStreetMap-Mitwirkende",
                                                         "Kartierung Studio, 2026"]
    assert records[1].attributes["source"] == "Eigene Datei: eigene.gpkg"  # input unchanged
    used = [UsedSource("Eigene Datei", "eigene.gpkg", "", "", "", 1)]
    assert with_source_texts(used, _sources(), texts)[0].attribution == "Kartierung Studio, 2026"
