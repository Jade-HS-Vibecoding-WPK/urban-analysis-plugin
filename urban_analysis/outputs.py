"""User-controlled QGIS and PDF outputs for the guided workflow."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .contracts import LayerDescriptor
from .data_pipeline import TARGET_FIELDS
from .user_guidance import OutputPlan


# --- W6: result layers in QGIS (interface S6) ------------------------------

RESULT_LAYER_PROPERTY = "urban_analysis/result_layer"
RESULT_GROUP_PROPERTY = "urban_analysis/result_group"
DOUBLE_FIELDS = ("area_m2",)
INTEGER_FIELDS = ("year", "floors")
SKIP_NO_GEOMETRY = "ohne Geometrie"
SKIP_UNREADABLE = "Geometrie nicht lesbar"
SKIP_OTHER_TYPE = "anderer Geometrietyp als der Layer"


def result_field_specs() -> Tuple[Tuple[str, str], ...]:
    """(field name, kind) for the 8 target fields; kind is text/double/int."""
    specs = []
    for name in TARGET_FIELDS:
        if name in DOUBLE_FIELDS:
            specs.append((name, "double"))
        elif name in INTEGER_FIELDS:
            specs.append((name, "int"))
        else:
            specs.append((name, "text"))
    return tuple(specs)


def field_value(kind: str, value):
    """Value for a result field; empty values stay NULL instead of ''."""
    if value in (None, ""):
        return None
    if kind == "double":
        return float(value)
    if kind == "int":
        return int(value)
    return str(value)


def result_group_name(topic: Optional[str]) -> str:
    return f"Urban Analysis – {topic or 'Ergebnis'}"


def result_layer_name(descriptor: LayerDescriptor, readable=None) -> str:
    """Readable layer name: pipeline name, else the category, else the id."""
    if readable is not None:
        try:
            name = readable(descriptor.layer_id)
        except Exception:  # a missing name must not stop the output
            name = None
        if name and name != descriptor.layer_id:
            return str(name)
    return descriptor.category or descriptor.name or descriptor.layer_id


GEOMETRY_WORDS = {"point": "Punkte", "line": "Linien", "polygon": "Flächen"}


def geometry_word(descriptor: LayerDescriptor) -> str:
    """'Punkte', 'Linien' or 'Flächen' from the geometry type or the OSM layer id."""
    text = f"{descriptor.geometry_type or ''} {descriptor.layer_id}".lower()
    for key, word in (("polygon", "Flächen"), ("line", "Linien"), ("point", "Punkte")):
        if key in text:
            return word
    return ""


def result_layer_names(descriptors: Iterable[LayerDescriptor], readable=None) -> Dict[str, str]:
    """Readable, unique names for the result layers (layer_id -> name).

    The same category from lines and areas (e.g. OSM streets) gets the
    geometry in brackets – 'Straßen (Linien)', 'Straßen (Flächen)' – instead
    of a technical id."""
    descriptors = list(descriptors)
    names = {d.layer_id: result_layer_name(d, readable) for d in descriptors}
    counts: Dict[str, int] = {}
    for name in names.values():
        counts[name] = counts.get(name, 0) + 1
    for d in descriptors:
        if counts[names[d.layer_id]] > 1 and geometry_word(d):
            names[d.layer_id] = f"{names[d.layer_id]} ({geometry_word(d)})"
    used = set()
    for d in descriptors:  # still the same name: the layer id keeps them apart
        if names[d.layer_id] in used:
            names[d.layer_id] = f"{names[d.layer_id]} ({d.layer_id})"
        used.add(names[d.layer_id])
    return names


@dataclass
class ResultLayerReport:
    """What was written into one result layer."""

    layer_id: str
    name: str
    feature_count: int = 0
    skipped: Dict[str, int] = field(default_factory=dict)

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1


def format_count(count: int) -> str:
    """German thousands separator, e.g. 25 140."""
    return f"{count:,}".replace(",", " ")


def result_layers_text(reports: Sequence[ResultLayerReport]) -> str:
    """Feedback after 'Verarbeitung starten'; skipped objects are always named."""
    total = sum(report.feature_count for report in reports)
    lines = [
        f"{len(reports)} Ergebnis-Layer in QGIS angelegt ({format_count(total)} Objekte)."
    ]
    for report in reports:
        for reason, count in report.skipped.items():
            lines.append(
                f"{report.name}: {format_count(count)} Objekt(e) nicht übernommen – {reason}."
            )
    return "\n".join(lines)


def build_result_layers(result, selected_layers: Iterable[LayerDescriptor], readable=None):
    """Create one memory layer per selected descriptor from the harmonized records.

    Returns ``(layer_objects, reports)``: ``layer_objects`` maps layer_id to
    the new QgsVectorLayer (for S7), ``reports`` says what was written and
    what was skipped and why.  Input data and project layers stay unchanged.
    """
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsFeature,
        QgsField,
        QgsGeometry,
        QgsVectorLayer,
        QgsWkbTypes,
    )
    from qgis.PyQt.QtCore import QMetaType

    from .geometry import GeometryError, plain_geometry

    meta = getattr(QMetaType, "Type", QMetaType)
    field_types = {"text": meta.QString, "double": meta.Double, "int": meta.Int}
    specs = result_field_specs()
    crs = QgsCoordinateReferenceSystem(result.project_crs)

    records_by_layer: Dict[str, List[object]] = {}
    for record in result.harmonized_records:
        records_by_layer.setdefault(record.layer_id, []).append(record)

    layer_objects = {}
    reports: List[ResultLayerReport] = []
    selected_layers = list(selected_layers)
    unique_names = result_layer_names(selected_layers, readable)
    for descriptor in selected_layers:
        name = unique_names[descriptor.layer_id]
        report = ResultLayerReport(descriptor.layer_id, name)

        geometries = []
        for record in records_by_layer.get(descriptor.layer_id, ()):
            try:
                raw = plain_geometry(record.geometry)
            except GeometryError:
                report.skip(SKIP_UNREADABLE)
                continue
            if raw is None:
                report.skip(SKIP_NO_GEOMETRY)
                continue
            if isinstance(raw, bytes):
                geometry = QgsGeometry()
                geometry.fromWkb(raw)
            else:
                geometry = QgsGeometry.fromWkt(raw)
            if geometry.isNull() or geometry.isEmpty():
                report.skip(SKIP_UNREADABLE)
                continue
            geometry.convertToMultiType()  # one layer type for single and multi parts
            geometries.append((record, geometry))

        if geometries:
            wkb_type = QgsWkbTypes.multiType(geometries[0][1].wkbType())
        else:
            wkb_type = QgsWkbTypes.multiType(QgsWkbTypes.parseType(descriptor.geometry_type or ""))
        type_name = QgsWkbTypes.displayString(wkb_type) or "MultiPolygon"
        layer = QgsVectorLayer(f"{type_name}?crs={crs.authid()}", name, "memory")
        layer.setCrs(crs)
        provider = layer.dataProvider()
        provider.addAttributes([QgsField(field_name, field_types[kind]) for field_name, kind in specs])
        layer.updateFields()
        if readable is not None:
            _set_field_aliases(layer, specs)

        features = []
        for record, geometry in geometries:
            if geometry.wkbType() != wkb_type:
                report.skip(SKIP_OTHER_TYPE)
                continue
            feature = QgsFeature(layer.fields())
            feature.setGeometry(geometry)
            feature.setAttributes(
                [field_value(kind, record.attributes.get(field_name)) for field_name, kind in specs]
            )
            features.append(feature)
        ok, _added = provider.addFeatures(features)
        if not ok:
            raise RuntimeError(f"Der Ergebnis-Layer „{name}“ konnte nicht gefüllt werden.")
        layer.updateExtents()
        layer.setCustomProperty(RESULT_LAYER_PROPERTY, True)
        report.feature_count = layer.featureCount()
        layer_objects[descriptor.layer_id] = layer
        reports.append(report)
    return layer_objects, reports


def _set_field_aliases(layer, specs) -> None:
    """German field names (aliases) in the attribute table, if available."""
    try:
        from .mapping import readable_target_field
    except ImportError:
        return
    for index, (field_name, _kind) in enumerate(specs):
        try:
            layer.setFieldAlias(index, readable_target_field(field_name))
        except Exception:  # an alias is only cosmetic
            pass


def add_result_layers(layer_objects: Mapping[str, object], group_name: str, project=None):
    """Put the result layers into their own group at the top of the layer tree.

    A group created earlier by the plugin (and only its layers) is replaced,
    so starting the processing again does not duplicate results.
    """
    from qgis.core import QgsProject

    project = project or QgsProject.instance()
    root = project.layerTreeRoot()
    for group in list(root.findGroups()):
        if group.customProperty(RESULT_GROUP_PROPERTY):
            layer_ids = [
                node.layerId()
                for node in group.findLayers()
                if node.layer() is not None
                and node.layer().customProperty(RESULT_LAYER_PROPERTY)
            ]
            root.removeChildNode(group)
            if layer_ids:
                project.removeMapLayers(layer_ids)
    group = root.insertGroup(0, group_name)
    group.setCustomProperty(RESULT_GROUP_PROPERTY, True)
    for layer in layer_objects.values():
        project.addMapLayer(layer, False)
        group.addLayer(layer)
    return group


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


def unique_layer_names(names: Iterable[str]) -> List[str]:
    """GeoPackage layer names must be unique: 'Gebäude', 'Gebäude (2)' …"""
    used: Dict[str, int] = {}
    unique = []
    for name in names:
        name = (name or "").strip() or "Ergebnis"
        count = used.get(name.lower(), 0) + 1
        used[name.lower()] = count
        unique.append(name if count == 1 else f"{name} ({count})")
    return unique


def write_result_geopackage(path, layers: Sequence[object]) -> str:
    """Write the result layers into one new GeoPackage (W8b).

    Each layer keeps its readable name as GeoPackage layer name.  An existing
    file at ``path`` is replaced (the save dialog already asked); the input
    data are never touched.  Errors are raised with a readable reason.
    """
    from qgis.core import QgsCoordinateTransformContext, QgsVectorFileWriter

    if not layers:
        raise ValueError("Es gibt keine Ergebnis-Layer, die gespeichert werden können.")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    names = unique_layer_names(layer.name() for layer in layers)
    for index, (layer, name) in enumerate(zip(layers, names)):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.fileEncoding = "UTF-8"
        options.layerName = name
        options.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteLayer
            if index
            else QgsVectorFileWriter.CreateOrOverwriteFile
        )
        written = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, str(target), QgsCoordinateTransformContext(), options
        )
        # QGIS returns (error, message, new file, new layer); only the first
        # two matter here.
        error, message = written[0], written[1]
        if error != QgsVectorFileWriter.NoError:
            raise RuntimeError(f"Layer „{name}“: {message or 'unbekannter Fehler'}")
    return str(target)


def _pdf_escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_minimal_pdf(path, *, title: str, study_area_wkt: str, buffer_meters: float,
                      legend: Iterable[str], data_source: str) -> str:
    """Write a dependency-free, one-page PDF containing the required metadata."""
    lines = [
        title,
        # one line on an A4 page: long polygons are shortened
        "Untersuchungsgebiet: " + (study_area_wkt if len(study_area_wkt) <= 80
                                   else study_area_wkt[:79] + "…"),
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
    # Helvetica in the PDF uses WinAnsi, so German umlauts (ä, ö, ü, ß) and
    # the dash work via cp1252; only rare characters become '?'.
    stream = "\n".join(commands).encode("cp1252", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
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
    selected_layers = list(selected_layers)  # used twice below
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
        layers = [layer_objects[descriptor.layer_id] for descriptor in selected_layers]
        try:
            result["geopackage_path"] = write_result_geopackage(geopackage_path, layers)
        except RuntimeError as error:
            raise RuntimeError(f"Das GeoPackage konnte nicht gespeichert werden: {error}")
    if output_plan.pdf_requested:
        if not pdf_path:
            raise ValueError(
                "Für das PDF fehlt der Speicherort. Bitte einen Dateinamen wählen."
            )
        result["pdf_path"] = export_pdf(pdf_path, output_plan)
    return result
