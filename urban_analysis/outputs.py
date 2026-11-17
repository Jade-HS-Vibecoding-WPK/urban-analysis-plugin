"""User-controlled QGIS and PDF outputs for the guided workflow."""

from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional

from .contracts import LayerDescriptor
from .user_guidance import OutputPlan


def load_qgis_layers(iface, selected_layers: Iterable[LayerDescriptor], layer_objects):
    """Load confirmed result layers without changing the input layer list."""
    if iface is None or not hasattr(iface, "addMapLayer"):
        raise RuntimeError(
            "Die Ergebnis-Layer können nur innerhalb von QGIS geladen werden "
            "(QGIS-Oberfläche nicht verfügbar)."
        )

    loaded = []
    for descriptor in selected_layers:
        try:
            layer = layer_objects[descriptor.layer_id]
        except (KeyError, TypeError):
            raise KeyError(
                f"Für den Layer „{descriptor.layer_id}“ wurde kein QGIS-Layer erzeugt; "
                "er kann daher nicht geladen werden."
            )
        iface.addMapLayer(layer)
        loaded.append(descriptor.layer_id)
    return tuple(loaded)


def _pdf_escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_minimal_pdf(path, *, title: str, study_area_wkt: str, buffer_meters: float,
                      legend: Iterable[str], data_source: str) -> str:
    """Write a dependency-free, one-page PDF containing the required metadata."""
    lines = [
        title,
        "Untersuchungsgebiet: " + study_area_wkt,
        "Puffer: " + str(buffer_meters) + " m",
        "Legende: " + ", ".join(legend),
        "Datenquelle: " + data_source,
    ]
    commands = ["BT", "/F1 10 Tf", "50 780 Td"]
    for index, line in enumerate(lines):
        if index:
            commands.append("0 -18 Td")
        commands.append("(" + _pdf_escape(line) + ") Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, content in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(("%d 0 obj\n" % number).encode("ascii"))
        output.extend(content)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(("xref\n0 %d\n" % (len(objects) + 1)).encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(("%010d 00000 n \n" % offset).encode("ascii"))
    output.extend(
        ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
         % (len(objects) + 1, xref_offset)).encode("ascii")
    )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output)
    return str(target)


def export_pdf(path, output_plan: OutputPlan) -> str:
    """Export the selected workflow metadata as the optional PDF output."""
    metadata = output_plan.pdf_metadata
    if not output_plan.pdf_requested or metadata is None:
        raise ValueError(
            "Die PDF-Ausgabe ist nicht ausgewählt. Bitte in Schritt 8 „PDF erzeugen“ "
            "ankreuzen."
        )
    return write_minimal_pdf(
        path,
        title="Urban Analysis - Siedlungsstruktur",
        study_area_wkt=metadata["study_area_wkt"],
        buffer_meters=metadata["buffer_meters"],
        legend=metadata["legend"],
        data_source=metadata["data_source"],
    )


def export_selected_outputs(
    iface,
    output_plan: OutputPlan,
    selected_layers: Iterable[LayerDescriptor],
    *,
    layer_objects: Optional[Mapping[str, object]] = None,
    geopackage_path: Optional[str] = None,
    pdf_path: Optional[str] = None,
) -> Dict[str, object]:
    """Execute selected outputs while keeping pipeline data outside this module."""
    result = {"qgis_layer_ids": output_plan.qgis_layer_ids}
    if layer_objects is not None:
        result["loaded_qgis_layer_ids"] = load_qgis_layers(
            iface, selected_layers, layer_objects
        )
    if output_plan.geopackage_requested:
        if not geopackage_path:
            raise ValueError(
                "Für das bereinigte GeoPackage fehlt der Speicherort. Bitte einen "
                "Dateinamen wählen."
            )
        if layer_objects is None:
            raise ValueError(
                "Das GeoPackage kann nicht gespeichert werden, weil noch keine "
                "Ergebnis-Layer erzeugt wurden."
            )
        from qgis.core import QgsCoordinateTransformContext, QgsVectorFileWriter

        writer_errors = []
        for index, descriptor in enumerate(selected_layers):
            layer = layer_objects[descriptor.layer_id]
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = descriptor.name or descriptor.layer_id
            if index:
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
            else:
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
            error, message = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                geopackage_path,
                QgsCoordinateTransformContext(),
                options,
            )
            if error != QgsVectorFileWriter.NoError:
                writer_errors.append(message or descriptor.layer_id)
        if writer_errors:
            raise RuntimeError(
                "Das GeoPackage konnte nicht gespeichert werden: "
                + "; ".join(writer_errors)
            )
        result["geopackage_path"] = str(geopackage_path)
    if output_plan.pdf_requested:
        if not pdf_path:
            raise ValueError(
                "Für das PDF fehlt der Speicherort. Bitte einen Dateinamen wählen."
            )
        result["pdf_path"] = export_pdf(pdf_path, output_plan)
    return result
