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


def extra_field_names(records) -> Dict[str, str]:
    """Kept source columns of a layer: {name in the records: field name}.

    Order of first appearance; a name that clashes with a target field gets
    the prefix 'Quelle: ' so nothing is overwritten."""
    names: Dict[str, str] = {}
    used = {name.casefold() for name in TARGET_FIELDS}
    for record in records:
        for key in (getattr(record, "extra_attributes", None) or {}):
            if key in names:
                continue
            field_name = key if key.casefold() not in used else f"Quelle: {key}"
            used.add(field_name.casefold())
            names[key] = field_name
    return names


# Vertretung Mac (19.11.2026, QGIS-Test): order and choice of the columns of
# a result layer.  Objekt-ID first, then what it is, where it is, its
# properties, the other source columns, and where the data come from last.
# Target fields outside ALWAYS_FIELDS and source columns appear only if at
# least one object of the layer has a value.
ALWAYS_FIELDS = ("object_id", "object_type", "category", "source")
NAME_COLUMNS = ("Name",)  # readable name of the source column 'name'
COLUMN_ORDER_FRONT = ("object_id",)
COLUMN_ORDER_WHAT = ("object_type", "category", "object_detail")
COLUMN_ORDER_WHERE = ("address",)
COLUMN_ORDER_PROPERTIES = ("floors", "area_m2", "year", "status")
COLUMN_ORDER_ORIGIN = ("source", "source_name")


def result_columns(records) -> List[Tuple[str, str, str, str]]:
    """Columns of one result layer in their order: ``(where, key, field
    name, kind)`` with ``where`` = "target" (``record.attributes``) or
    "extra" (``record.extra_attributes``); kind is text/double/int."""
    records = list(records)
    kinds = dict(result_field_specs())
    extras = extra_field_names(records)

    def filled_target(name):
        return name in ALWAYS_FIELDS or any(
            (record.attributes or {}).get(name) not in (None, "") for record in records)

    def filled_extra(key):
        return any((getattr(record, "extra_attributes", None) or {}).get(key) not in (None, "")
                   for record in records)

    def targets(names):
        return [("target", name, name, kinds[name]) for name in names if filled_target(name)]

    named = [key for key in extras if extras[key] in NAME_COLUMNS and filled_extra(key)]
    others = [key for key in extras if key not in named and filled_extra(key)]
    return (
        targets(COLUMN_ORDER_FRONT)
        + [("extra", key, extras[key], "text") for key in named]
        + targets(COLUMN_ORDER_WHAT)
        + targets(COLUMN_ORDER_WHERE)
        + targets(COLUMN_ORDER_PROPERTIES)
        + [("extra", key, extras[key], "text") for key in others]
        + targets(COLUMN_ORDER_ORIGIN)
    )


def column_value(column, record):
    """Value of one ``result_columns`` entry for one record."""
    where, key, _field_name, kind = column
    values = record.attributes if where == "target" else getattr(record, "extra_attributes", None)
    return field_value(kind, (values or {}).get(key))


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


GEOMETRY_KINDS = ("point", "line", "polygon")  # order of the ticks in 'Ausgabe'


# ALKIS exports often declare only "GEOMETRY"; their tables are known.
ALKIS_TABLE_KINDS = {
    "gebaeude": "polygon", "nutzung": "polygon", "flurstuecke": "polygon",
    "bodenschaetzung": "polygon", "bewertung": "polygon", "grenzpunkte": "point",
    "bauwerke_f": "polygon", "bauwerke_l": "line", "bauwerke_p": "point",
}


def geometry_kind_of(descriptor: LayerDescriptor) -> str:
    """'point', 'line', 'polygon' or '' (unknown) of a result layer."""
    word = geometry_word(descriptor)
    kind = next((kind for kind, name in GEOMETRY_WORDS.items() if name == word), "")
    if kind:
        return kind
    layer_id = descriptor.layer_id.lower()
    if layer_id.startswith("nutzung_"):  # split land-use layers (areas)
        return "polygon"
    return ALKIS_TABLE_KINDS.get(layer_id, "")


def geometry_counts(descriptors: Iterable[LayerDescriptor]) -> Dict[str, int]:
    """Number of layers per geometry kind (for the ticks 'Punkte (3)' …)."""
    counts = {kind: 0 for kind in GEOMETRY_KINDS}
    for descriptor in descriptors:
        kind = geometry_kind_of(descriptor)
        if kind:
            counts[kind] += 1
    return counts


def with_geometry_kinds(descriptors: Iterable[LayerDescriptor], kinds) -> List[LayerDescriptor]:
    """Only the layers of the ticked geometry kinds; layers of unknown
    geometry always stay (nothing disappears unseen)."""
    wanted = set(kinds)
    return [d for d in descriptors if geometry_kind_of(d) in wanted or not geometry_kind_of(d)]


def result_layer_names(descriptors: Iterable[LayerDescriptor], readable=None) -> Dict[str, str]:
    """Readable, unique names for the result layers (layer_id -> name).

    The same category from lines and areas (e.g. OSM streets) gets the
    geometry in brackets – 'Straßen (Linien)', 'Straßen (Flächen)' – instead
    of a technical id."""
    descriptors = list(descriptors)
    names = {d.layer_id: result_layer_name(d, readable) for d in descriptors}

    def doubled():
        counts: Dict[str, int] = {}
        for name in names.values():
            counts[name] = counts.get(name, 0) + 1
        return {name for name, count in counts.items() if count > 1}

    # several sources (M13): 'Gebäude (ALKIS)', 'Gebäude (OSM)'
    kinds = {getattr(d, "source_kind", "") for d in descriptors} - {""}
    if len(kinds) > 1:
        twice = doubled()
        for d in descriptors:
            if names[d.layer_id] in twice and getattr(d, "source_kind", ""):
                names[d.layer_id] = f"{names[d.layer_id]} ({d.source_kind})"
    twice = doubled()
    for d in descriptors:
        if names[d.layer_id] in twice and geometry_word(d):
            name = names[d.layer_id]
            if name.endswith(")"):  # 'Straßen (OSM)' -> 'Straßen (OSM, Linien)'
                names[d.layer_id] = f"{name[:-1]}, {geometry_word(d)})"
            else:
                names[d.layer_id] = f"{name} ({geometry_word(d)})"
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
        # W14/E29: source columns kept in step 5 follow the target fields
        # Objekt-ID first, then what/where/properties, origin last; empty
        # columns are left out (result_columns, Vertretung Mac)
        columns = result_columns(record for record, _geometry in geometries)
        provider.addAttributes(
            [QgsField(field_name, field_types[kind]) for _where, _key, field_name, kind in columns])
        layer.updateFields()
        if readable is not None:
            _set_field_aliases(layer, [(key, kind) for where, key, _name, kind in columns
                                       if where == "target"])

        features = []
        for record, geometry in geometries:
            if geometry.wkbType() != wkb_type:
                report.skip(SKIP_OTHER_TYPE)
                continue
            feature = QgsFeature(layer.fields())
            feature.setGeometry(geometry)
            feature.setAttributes([column_value(column, record) for column in columns])
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
    for field_name, _kind in specs:
        index = layer.fields().indexOf(field_name)
        if index < 0:
            continue
        try:
            layer.setFieldAlias(index, readable_target_field(field_name))
        except Exception:  # an alias is only cosmetic
            pass


def time_text():
    from datetime import datetime

    return datetime.now().strftime("%H:%M")


def run_group_name(base, existing_names, time):
    """'Urban Analysis – Thema' for the first run, then with the time
    ('… (10:42)') and, if needed, a number, so no group is replaced."""
    if base not in existing_names:
        return base
    name = f"{base} ({time})"
    number = 2
    while name in existing_names:
        name = f"{base} ({time}, {number})"
        number += 1
    return name


# Vertretung Mac (19.11.2026): sub-groups of the result group, so the layer
# list stays short.  Order = order in the layer tree (top draws on top):
# points first, areas of use last.  "Sonstiges" is hidden and folded – the
# small things are there, but not in the map unless the user ticks them.
LAYER_GROUPS = (
    ("Einrichtungen", ("Gesundheit", "Nahversorgung", "Bildung und Betreuung", "Freizeit und Grün")),
    ("Verkehr", ("Straßen", "Fuß- und Radwege", "Plätze", "Bahnstrecken", "Bahnflächen",
                 "ÖPNV-Haltestellen", "Schiffsverkehrsflächen")),
    ("Bebauung", ("Gebäude", "Gebäudeteile", "Bauwerke und Überdachungen")),
    ("Grün & Wasser", ("Grünflächen", "Wasserflächen", "Gewässer", "Hecken und Baumreihen")),
    ("Nutzung", ("Nutzungsflächen",)),
    ("Sonstiges", ("Sonstige OSM-Punkte", "Sonstige OSM-Linien", "Sonstige OSM-Flächen",
                   "Zäune und Mauern")),
)
OTHER_LAYER_GROUP = "Weitere Layer"  # categories not listed above, e.g. from own files
HIDDEN_LAYER_GROUPS = ("Sonstiges",)


def layer_group_name(category: Optional[str]) -> str:
    """Sub-group of a result layer by its category."""
    for name, categories in LAYER_GROUPS:
        if category in categories:
            return name
    return OTHER_LAYER_GROUP


def layer_groups(layer_ids: Iterable[str], categories: Mapping[str, Optional[str]]) -> List[Tuple[str, List[str]]]:
    """``[(group name, [layer ids])]`` in the order of ``LAYER_GROUPS``, the
    layers in their given order; empty groups are left out."""
    order = [name for name, _categories in LAYER_GROUPS]
    order.insert(order.index("Sonstiges"), OTHER_LAYER_GROUP)
    members: Dict[str, List[str]] = {name: [] for name in order}
    for layer_id in layer_ids:
        members[layer_group_name(categories.get(layer_id))].append(layer_id)
    return [(name, members[name]) for name in order if members[name]]


def add_result_layers(layer_objects: Mapping[str, object], group_name: str, project=None,
                      categories: Optional[Mapping[str, Optional[str]]] = None):
    """Put the result layers into their own group at the top of the layer tree.

    Every run gets a new group (with the time in its name from the second
    run on); earlier results are kept.  With ``categories`` (layer_id ->
    category) the layers go into sub-groups (``LAYER_GROUPS``); the group
    „Sonstiges“ is hidden and folded.  Returns the group.
    """
    from qgis.core import QgsProject

    project = project or QgsProject.instance()
    root = project.layerTreeRoot()
    # Every run gets its own group; earlier results stay for comparison.
    existing = {group.name() for group in root.findGroups()}
    group_name = run_group_name(group_name, existing, time_text())
    group = root.insertGroup(0, group_name)
    group.setCustomProperty(RESULT_GROUP_PROPERTY, True)
    from .map_styles import fix_legend

    if categories is None:
        for layer in layer_objects.values():
            project.addMapLayer(layer, False)
            fix_legend(group.addLayer(layer))  # clean symbol in the layer panel
        return group
    for name, layer_ids in layer_groups(layer_objects, categories):
        sub = group.addGroup(name)
        for layer_id in layer_ids:
            layer = layer_objects[layer_id]
            project.addMapLayer(layer, False)
            fix_legend(sub.addLayer(layer))
        if name in HIDDEN_LAYER_GROUPS:
            sub.setItemVisibilityChecked(False)
            sub.setExpanded(False)
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


def write_result_geopackage(path, layers: Sequence[object], used_sources=()) -> str:
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
    if used_sources:
        _write_sources_table(target, used_sources, set(names))
    return str(target)


SOURCES_TABLE = "Datenquellen und Lizenzen"


def _write_sources_table(target, used_sources, taken) -> None:
    """Table without geometry in the GeoPackage: one row per used source (E28)."""
    from qgis.core import (
        QgsCoordinateTransformContext, QgsFeature, QgsField, QgsVectorFileWriter, QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QMetaType

    meta = getattr(QMetaType, "Type", QMetaType)
    table = QgsVectorLayer("None", SOURCES_TABLE, "memory")
    columns = ("Quelle", "Quellenvermerk", "Lizenz", "Link", "Objekte")
    table.dataProvider().addAttributes(
        [QgsField(name, meta.Int if name == "Objekte" else meta.QString) for name in columns])
    table.updateFields()
    rows = []
    for source in used_sources:
        feature = QgsFeature(table.fields())
        feature.setAttributes([source.name, source.attribution, source.licence,
                               source.licence_url, int(source.record_count)])
        rows.append(feature)
    table.dataProvider().addFeatures(rows)
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.fileEncoding = "UTF-8"
    options.layerName = SOURCES_TABLE if SOURCES_TABLE not in taken else f"{SOURCES_TABLE} (Plugin)"
    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    written = QgsVectorFileWriter.writeAsVectorFormatV3(
        table, str(target), QgsCoordinateTransformContext(), options)
    if written[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError(f"Tabelle „{SOURCES_TABLE}“: {written[1] or 'unbekannter Fehler'}")


# --- F5 / W18: real map PDF with a QGIS print layout -------------------------

PAGE_SIZES_MM = {"A4": (210, 297), "A3": (297, 420), "A2": (420, 594),
                 "A1": (594, 841), "A0": (841, 1189)}
# Usual scales of plans and maps; "passend zum Gebiet" takes the next one
# that shows the whole area (never an odd value like 1:7.342).
STANDARD_SCALES = (50, 100, 200, 250, 500, 750, 1000, 1250, 1500, 2000, 2500, 3000, 4000,
                   5000, 7500, 10000, 12500, 15000, 20000, 25000, 30000, 40000, 50000,
                   75000, 100000, 150000, 200000)
SCALES = (None,) + STANDARD_SCALES  # None = fits the area


def fitting_scale(scale):
    """The smallest usual scale at which the area still fits (``scale`` is
    the exact scale that fits it); beyond the list rounded up to 10 000s."""
    for value in STANDARD_SCALES:
        if value >= scale * 0.999:
            return value
    return int(-(-scale // 10000) * 10000)


def auto_orientation(width, height):
    """'quer' for wide areas, 'hoch' for tall ones (PDF format, map shape)."""
    return "quer" if width >= height else "hoch"


def page_size_mm(page="A4", orientation="quer"):
    """(width, height) in mm; 'quer' = landscape."""
    short, long_ = PAGE_SIZES_MM.get(page, PAGE_SIZES_MM["A4"])
    return (long_, short) if orientation == "quer" else (short, long_)


def scale_label(scale):
    return "passend zum Gebiet" if not scale else f"1:{int(round(scale)):,}".replace(",", ".")


# --- PDF page plan (QGIS-free, tested) ------------------------------------------
# Font sizes per paper size (title, normal text) in pt – user wish 19.11.:
# A4 14/12, growing in steps up to 24/20 for A0.
FONT_SIZES = {"A4": (14, 12), "A3": (16, 13), "A2": (18, 15), "A1": (21, 17), "A0": (24, 20)}
PT_MM = 25.4 / 72
# share of the free page for the panel (legend, title …); grows when the
# legend does not fit – the map gets a bit smaller instead of a cut legend
PANEL_SHARES = {"quer": (0.30, 0.38, 0.46), "hoch": (0.28, 0.36, 0.45)}
INFO_SHARE_HOCH = 0.40  # portrait: left part of the panel = title, symbols, sources


def font_sizes(page):
    """(title pt, text pt) for the paper size."""
    return FONT_SIZES.get(page, FONT_SIZES["A4"])


def line_mm(points):
    return points * PT_MM * 1.4


def wrapped_lines(text, width_mm, points):
    """Lines a text needs at this width (estimate on the safe side)."""
    per_line = max(8, int(width_mm / (points * PT_MM * 0.6)))
    return sum(max(1, -(-len(line) // per_line)) for line in (text or "").split("\n"))


def symbol_row_mm(text_pt):
    """Height of the row with north arrow and scale bar."""
    return text_pt * PT_MM * 3.2


def page_plan(page="A4", orientation="quer", share=None, *, title="", subtitle="",
              info_text=""):
    """Rectangles (x, y, w, h) in mm: map, title, subtitle, symbols (north
    arrow + scale bar), text (scale and sources), legend.  Heights come from
    the real font sizes and text lengths, so nothing overlaps.

    Landscape: map left, panel right (title, legend, symbols and text at the
    bottom).  Portrait: map on top, panel below – left title, symbols and
    text, right the legend."""
    width, height = page_size_mm(page, orientation)
    title_pt, text_pt = font_sizes(page)
    margin = max(8.0, width * 0.03)
    gap = text_pt * PT_MM * 1.2
    share = share or PANEL_SHARES[orientation][0]
    plan = {"width": width, "height": height, "title_pt": title_pt, "text_pt": text_pt}

    def column(x, y, w):
        title_h = wrapped_lines(title or "Urban Analysis", w, title_pt) * line_mm(title_pt)
        sub_h = wrapped_lines(subtitle, w, text_pt) * line_mm(text_pt) if subtitle else 0.0
        text_h = wrapped_lines(info_text, w, text_pt) * line_mm(text_pt)
        return title_h, sub_h, symbol_row_mm(text_pt), text_h

    if orientation == "hoch":
        free = height - 3 * margin
        inner_w = width - 2 * margin
        info_w = inner_w * INFO_SHARE_HOCH
        title_h, sub_h, sym_h, text_h = column(margin, 0, info_w)
        need = title_h + sub_h + gap + sym_h + gap + text_h
        panel_h = min(max(need, free * share), free * 0.6)
        map_h = free - panel_h
        py = 2 * margin + map_h
        y = py
        plan["map"] = (margin, margin, inner_w, map_h)
        plan["title"] = (margin, y, info_w, title_h)
        y += title_h
        plan["subtitle"] = (margin, y, info_w, sub_h) if subtitle else None
        y += sub_h + gap
        plan["symbols"] = (margin, y, info_w, sym_h)
        y += sym_h + gap
        plan["text"] = (margin, y, info_w, max(text_h, py + panel_h - y))
        legend_x = margin + info_w + gap
        plan["legend"] = (legend_x, py, width - margin - legend_x, panel_h)
        plan["fits"] = need <= panel_h + 0.5
        return plan

    free_w = width - 3 * margin
    panel_w = free_w * share
    inner_h = height - 2 * margin
    px = width - margin - panel_w
    title_h, sub_h, sym_h, text_h = column(px, margin, panel_w)
    plan["map"] = (margin, margin, free_w - panel_w, inner_h)
    y = margin
    plan["title"] = (px, y, panel_w, title_h)
    y += title_h
    plan["subtitle"] = (px, y, panel_w, sub_h) if subtitle else None
    y += sub_h + gap
    bottom = margin + inner_h
    text_y = bottom - text_h
    sym_y = text_y - gap - sym_h
    plan["symbols"] = (px, sym_y, panel_w, sym_h)
    plan["text"] = (px, text_y, panel_w, text_h)
    plan["legend"] = (px, y, panel_w, max(0.0, sym_y - gap - y))
    plan["fits"] = sym_y - gap - y >= line_mm(text_pt) * 2
    return plan


def breakable_links(text, width_mm=None, points=12):
    """Web addresses have no spaces and would not wrap in a narrow column:
    break words longer than the column after a '/' (QGIS wraps only at
    spaces)."""
    if not width_mm:
        return text or ""
    per_line = max(8, int(width_mm / (points * PT_MM * 0.6)))
    lines = []
    for line in (text or "").split("\n"):
        words = []
        for word in line.split(" "):
            while len(word) > per_line:
                cut = word.rfind("/", 0, per_line)
                cut = cut + 1 if cut > 0 else per_line
                words.append(word[:cut] + "\n")
                word = word[cut:]
            words.append(word)
        lines.append(" ".join(words).replace("\n ", "\n"))
    return "\n".join(lines)


def suggested_scale(extent_width_m, extent_height_m, page="A4", orientation="quer"):
    """The usual scale at which the extent fills the map frame of this paper
    size (the frame as it is with a short legend)."""
    plan = page_plan(page, orientation, title="Titel", info_text="\n" * 6)
    _x, _y, map_w, map_h = plan["map"]
    exact = max(extent_width_m * 1000 / max(map_w, 1), extent_height_m * 1000 / max(map_h, 1))
    return fitting_scale(exact * 1.03)


def scale_problem(chosen, suggested):
    """Hint when an own scale does not suit the area, else None."""
    if not chosen or not suggested:
        return None
    if chosen < suggested:
        return (f"Beim Maßstab {scale_label(chosen)} passt das Gebiet nicht ganz auf das Blatt – "
                f"passend wäre {scale_label(suggested)}.")
    if chosen >= suggested * 4:
        return (f"Beim Maßstab {scale_label(chosen)} wird das Gebiet sehr klein und füllt nur einen "
                f"kleinen Teil der Karte – passend wäre {scale_label(suggested)}.")
    return None


def licence_lines(used_sources):
    """One line per used source (``data_pipeline.UsedSource``) for the block
    'Datenquellen und Lizenzen': attribution, licence and link."""
    import re

    def plain(text):  # 'CC-BY-4.0' -> 'ccby', 'ODbL-1.0' -> 'odbl'
        return re.sub(r"\d+$", "", re.sub(r"[^a-z0-9]", "", text.casefold()))

    lines = []
    for source in used_sources:
        line = source.attribution or source.name
        if source.licence and plain(source.licence) not in re.sub(r"[^a-z0-9]", "", line.casefold()):
            line += f", {source.licence}"
        if source.licence_url:
            line += f" ({source.licence_url})"
        lines.append(line)
    return lines


def source_key(source) -> str:
    """Key of a loaded source (``SourceFile``): the file it came from, the
    same value the records carry in ``source_file``."""
    return str(source.path)


def default_source_texts(sources) -> Dict[str, str]:
    """Quellenangabe je Datenquelle, pre-filled from the download
    (attribution); own files start empty – the user must name them."""
    return {source_key(source): (source.attribution or "").strip() for source in sources}


def missing_source_texts(sources, texts) -> List[str]:
    """Labels of the loaded sources that still have no Quellenangabe."""
    return [source.label for source in sources if not (texts.get(source_key(source)) or "").strip()]


def combined_source_text(sources, texts) -> str:
    """All Quellenangaben in one line, e.g. for the PDF and the check."""
    parts = []
    for source in sources:
        text = (texts.get(source_key(source)) or "").strip()
        if text and text not in parts:
            parts.append(text)
    return "; ".join(parts)


def apply_source_texts(records, texts):
    """Every object gets the Quellenangabe of ITS source in ``source``
    (also an own file next to OSM/ALKIS).  Records of sources without a
    text stay unchanged; the input list is not changed."""
    from dataclasses import replace

    updated = []
    for record in records:
        text = (texts.get(getattr(record, "source_file", "") or "") or "").strip()
        if text and (record.attributes or {}).get("source") != text:
            record = replace(record, attributes={**(record.attributes or {}), "source": text})
        updated.append(record)
    return updated


def with_source_texts(used, sources, texts):
    """Used sources (licence block) with the Quellenangabe the user typed."""
    from dataclasses import replace

    by_label = {source.label: (texts.get(source_key(source)) or "").strip() for source in sources}
    return [replace(item, attribution=by_label.get(item.name) or item.attribution) for item in used]


def data_source_text(used_sources, typed=""):
    """Text for 'Datenquellen und Lizenzen': the used sources with licence,
    plus what the user typed if it says something else."""
    lines = licence_lines(used_sources)
    typed = (typed or "").strip()
    auto = "; ".join(source.attribution for source in used_sources if source.attribution)
    if typed and typed != auto and typed not in lines:
        lines.append(typed)
    return "\n".join(lines) or typed


def sources_text(data_source, day):
    """Block 'Datenquellen und Lizenzen' (E28) with the date."""
    return (
        "Datenquellen und Lizenzen\n"
        f"{data_source or '–'}\n"
        "Daten verändert (zugeschnitten, harmonisiert) mit dem QGIS-Plugin Urban Analysis.\n"
        f"Stand: {day.strftime('%d.%m.%Y')}"
    )


# Legend too long for the panel: first smaller text in one column, columns
# only when needed - (columns, text size factor), tried in this order.
LEGEND_STEPS = ((1, 1.0), (1, 0.9), (2, 0.9), (1, 0.8), (2, 0.8), (2, 0.7), (3, 0.7),
                (3, 0.6), (3, 0.5))
LEGEND_CUT_TITLE = "Legende (gekürzt – für alle Einträge ein größeres Papierformat wählen)"
PREVIEW_DPI = 45


def fit_legend(legend, width, height, text_pt=12):
    """Make the legend fit into width × height (mm): starts with the normal
    text size of the page, then smaller text and more columns step by step.
    Returns False if even the smallest step is too big (the caller then says
    so in the title)."""
    from qgis.core import QgsLayoutUtils, QgsLegendRenderer, QgsLegendStyle

    def content_size():
        """Real size of the legend content in mm (not the frame size)."""
        context = QgsLayoutUtils.createRenderContextForLayout(legend.layout(), None)
        return QgsLegendRenderer(legend.model(), legend.legendSettings()).minimumSize(context)

    styles = (QgsLegendStyle.Title, QgsLegendStyle.Group, QgsLegendStyle.Subgroup,
              QgsLegendStyle.SymbolLabel)
    symbol_w, symbol_h = text_pt * 0.55, text_pt * 0.35  # mm, grows with the text

    def apply(columns, shrink):
        for kind in styles:
            text_format = legend.rstyle(kind).textFormat()
            text_format.setSize(text_pt * shrink)
            legend.rstyle(kind).setTextFormat(text_format)
        legend.setSymbolWidth(symbol_w * shrink)
        legend.setSymbolHeight(symbol_h * shrink)
        legend.setColumnCount(columns)
        legend.setSplitLayer(True)
        legend.setEqualColumnWidth(True)
        return content_size()

    best = None  # last step that is not too wide: cut at the bottom, never at the side
    for columns, shrink in LEGEND_STEPS:
        size = apply(columns, shrink)
        if size.width() <= width:
            if size.height() <= height:
                return True
            best = (columns, shrink)
    if best is not None:
        apply(*best)
    return False


def map_extent(area, buffer_meters, show_buffer=True):
    """What the map shows: area + buffer (or a small margin without buffer)."""
    if show_buffer and buffer_meters:
        box = area.buffer(float(buffer_meters), 16).boundingBox()
        box.scale(1.05)
    else:
        box = area.boundingBox()
        box.scale(1.08)
    return box


def export_map_pdf(path, *, layers, study_area_wkt, buffer_meters, crs_authid,
                   title, subtitle="", data_source="", page="A4", orientation="quer",
                   scale=None, north_arrow=True, project=None, day=None, grey_outside=False,
                   show_buffer=True, image_path=None):
    """Write the analysis map as PDF (QGIS print layout).

    ``layers`` are the result layers, top-most first (as in the layer list).
    The study area (and, with ``show_buffer``, the buffer of
    ``buffer_meters``) is drawn as outline on top.  Title, text, legend and
    the scale bar use the font sizes of the paper size (``font_sizes``); the
    page plan keeps them apart.  With ``image_path`` a small PNG preview is
    written instead of the PDF.  Returns ``(path, scale)``."""
    from datetime import date as _date

    from qgis.core import (
        QgsFeature, QgsFillSymbol, QgsGeometry, QgsLayerTree, QgsLayoutExporter,
        QgsLayoutItemLabel, QgsLayoutItemLegend, QgsLayoutItemMap, QgsLayoutItemPicture,
        QgsLayoutItemScaleBar, QgsLayoutPoint, QgsLayoutSize, QgsPrintLayout, QgsProject,
        QgsSingleSymbolRenderer, QgsSymbolLayerUtils, QgsUnitTypes, QgsVectorLayer,
    )
    from qgis.PyQt.QtGui import QFont

    project = project or QgsProject.instance()
    day = day or _date.today()
    area = QgsGeometry.fromWkt(study_area_wkt or "")
    if area is None or area.isEmpty():
        raise ValueError("Für das PDF fehlt das Untersuchungsgebiet (Schritt 2).")
    extent = map_extent(area, buffer_meters, show_buffer)
    if orientation not in ("quer", "hoch"):  # 'auto': follow the shape of the area
        orientation = auto_orientation(extent.width(), extent.height())
    width, height = page_size_mm(page, orientation)
    title_pt, text_pt = font_sizes(page)
    scale = scale or suggested_scale(extent.width(), extent.height(), page, orientation)
    info_text = f"Maßstab {scale_label(scale)}\n\n" + sources_text(data_source, day)

    def outline_layer(geometry, name, style):
        layer = QgsVectorLayer(f"Polygon?crs={crs_authid}", name, "memory")
        feature = QgsFeature()
        feature.setGeometry(geometry)
        layer.dataProvider().addFeatures([feature])
        layer.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(style)))
        return layer

    from .study_area import AREA_OUTLINE_STYLE

    outlines = [outline_layer(area, "Untersuchungsgebiet", dict(AREA_OUTLINE_STYLE))]
    if show_buffer and buffer_meters:
        outlines.append(outline_layer(
            area.buffer(float(buffer_meters), 16), f"Puffer {format_count(int(buffer_meters))} m",
            {"color": "0,0,0,0", "outline_color": "#d0473b", "outline_width": "0.3",
             "outline_style": "dash"}))

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName("Urban Analysis")
    layout.pageCollection().page(0).setPageSize(QgsLayoutSize(width, height, QgsUnitTypes.LayoutMillimeters))

    def place(item, rect):
        x, y, w, h = rect
        layout.addLayoutItem(item)
        item.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
        item.attemptResize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutMillimeters))

    def font(points, bold=False):
        value = QFont()
        value.setPointSizeF(points)
        value.setBold(bold)
        return value

    # legend first: its size decides how much room the map leaves (no overlap)
    map_item = QgsLayoutItemMap(layout)
    map_item.setFrameEnabled(True)
    map_item.setCrs(outlines[0].crs())
    map_item.setLayers(outlines + list(layers))
    legend = QgsLayoutItemLegend(layout)
    legend.setTitle("Legende")
    legend.setAutoUpdateModel(False)
    root = QgsLayerTree()
    from .map_styles import fix_legend

    for layer in outlines + list(layers):
        fix_legend(root.addLayer(layer))  # cut layers: plain colour patch
    legend.model().setRootGroup(root)
    legend._root = root  # keep the tree alive while the layout lives
    legend.setLinkedMap(map_item)
    legend.setReferencePoint(QgsLayoutItemLegend.UpperLeft)  # starts at the top, not centred
    layout.addLayoutItem(legend)
    plan, fits = None, False
    for share in PANEL_SHARES[orientation]:
        plan = page_plan(page, orientation, share, title=title, subtitle=subtitle,
                         info_text=info_text)
        _lx, _ly, lw, lh = plan["legend"]
        if lh > 0 and fit_legend(legend, lw, lh, text_pt):
            fits = True
            break
    if not fits:
        legend.setTitle(LEGEND_CUT_TITLE)  # never cut silently

    # map: centred on the extent, at a usual scale (the chosen or the fitting one)
    place(map_item, plan["map"])
    map_item.zoomToExtent(extent)
    map_item.setScale(scale)

    title_label = QgsLayoutItemLabel(layout)
    title_label.setText(title or "Urban Analysis")
    title_label.setFont(font(title_pt, bold=True))
    place(title_label, plan["title"])
    if plan["subtitle"]:
        sub = QgsLayoutItemLabel(layout)
        sub.setText(subtitle)
        sub.setFont(font(text_pt))
        place(sub, plan["subtitle"])

    legend.setResizeToContents(False)
    lx, ly, lw, lh = plan["legend"]
    legend.attemptMove(QgsLayoutPoint(lx, ly, QgsUnitTypes.LayoutMillimeters))
    legend.attemptResize(QgsLayoutSize(lw, max(lh, 1.0), QgsUnitTypes.LayoutMillimeters))

    sx, sy, sw, sh = plan["symbols"]
    bar_x = sx
    if north_arrow:
        arrow = QgsLayoutItemPicture(layout)
        arrow.setPicturePath(QgsSymbolLayerUtils.svgSymbolNameToPath(
            "arrows/NorthArrow_02.svg", project.pathResolver()))
        place(arrow, (sx, sy, sh * 0.8, sh))
        bar_x = sx + sh * 0.8 + text_pt * PT_MM
    bar = QgsLayoutItemScaleBar(layout)
    bar.setStyle("Single Box")
    bar.setLinkedMap(map_item)
    bar.setUnits(QgsUnitTypes.DistanceMeters)
    bar.setNumberOfSegments(2)
    bar.setNumberOfSegmentsLeft(0)
    text_format = bar.textFormat()
    text_format.setSize(text_pt)
    bar.setTextFormat(text_format)
    bar.setHeight(text_pt * PT_MM * 0.6)
    bar.setMaximumBarWidth(max(20.0, sx + sw - bar_x - text_pt * PT_MM * 2))
    bar.applyDefaultSize()
    layout.addLayoutItem(bar)
    bar.attemptMove(QgsLayoutPoint(bar_x, sy + sh * 0.15, QgsUnitTypes.LayoutMillimeters))

    info = QgsLayoutItemLabel(layout)
    info.setText(breakable_links(info_text, plan["text"][2], text_pt))
    info.setFont(font(text_pt))
    place(info, plan["text"])

    target = Path(image_path or path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Grey border only in the PDF: cut style for the export, then back
    restore = []
    if grey_outside:
        from .map_styles import CATEGORY_PROPERTY, STYLE_PROPERTY, apply_style, fix_legend

        for layer in layers:
            if layer.customProperty(CATEGORY_PROPERTY) is None:
                continue  # e.g. accessibility targets and radii keep their own style
            restore.append((layer, layer.renderer().clone()))
            apply_style(layer, layer.customProperty(CATEGORY_PROPERTY) or None,
                        layer.customProperty(STYLE_PROPERTY) or "nutzung", study_area_wkt)
        for node in root.findLayers():
            fix_legend(node)
    try:
        exporter = QgsLayoutExporter(layout)
        if image_path:
            settings = QgsLayoutExporter.ImageExportSettings()
            settings.dpi = PREVIEW_DPI
            settings.generateWorldFile = False  # a picture only, no georeferencing
            settings.exportMetadata = False
            result = exporter.exportToImage(str(target), settings)
        else:
            result = exporter.exportToPdf(str(target), QgsLayoutExporter.PdfExportSettings())
    finally:
        from .map_styles import CUT_PROPERTY

        for layer, renderer in restore:
            layer.setRenderer(renderer)
            layer.setCustomProperty(CUT_PROPERTY, False)
            layer.triggerRepaint()
        # delete the layout now, while the outline layers and the legend tree
        # it points to still exist (else Python may free them first: crash)
        from qgis.PyQt import sip

        del exporter
        sip.delete(layout)
        del root
    if result != QgsLayoutExporter.Success:
        raise RuntimeError(
            "Das PDF konnte nicht geschrieben werden. Ist die Datei noch in einem "
            "PDF-Programm geöffnet? Dann bitte schließen und erneut verarbeiten."
        )
    return str(target), scale


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
