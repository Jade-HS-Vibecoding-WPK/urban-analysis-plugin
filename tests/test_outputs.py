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
