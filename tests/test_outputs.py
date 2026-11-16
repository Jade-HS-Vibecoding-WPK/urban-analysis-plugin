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
