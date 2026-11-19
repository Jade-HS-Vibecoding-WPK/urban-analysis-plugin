"""Accessibility in the guidance (W16, E26, E34): its own area in the last step.

The calculation (distance as the crow flies) is ``accessibility.py`` of
Person Mac.  This module turns the user's choices into ``TargetChoice``
objects and draws the result in QGIS: the targets as points (copies of the
loaded objects with their whole attribute table) and, per ring, a dashed
line around them; the area between two rings can be filled with a chosen
opacity.  Own targets (set in the map or picked from a layer) form the extra
target "Eigene Ziele".  The helpers at the top are QGIS-free.

Radii are shared by all targets (rings with tick boxes); the usual planning
values per target ("Richtwerte", ``GUIDE_VALUES``) are shown as hints.
"""

from dataclasses import dataclass, field, replace
from typing import Dict, List, Tuple

DEFAULT_RADII = (300, 500)
# preset ring colours (inside → outside): green, yellow, red, then more
DEFAULT_COLORS = ("#3fa34d", "#e6c229", "#d64545", "#7b5cc4", "#3b7fc4")
FILL_OPACITY = 0.15
MAX_RADII = 5
MAX_RADIUS_M = 5000
RING_FIELD = "Radius"
# rings of the form: (ticked, metres, colour); the user changes all three
DEFAULT_RINGS = tuple(
    (on, metres, color) for (on, metres), color in zip(
        ((True, 300), (True, 500), (False, 1000), (False, 1500), (False, 2000)), DEFAULT_COLORS))
OWN_TARGETS = "Eigene Ziele"
OWN_LAYER_PREFIX = "eigene_ziele"

# Usual planning values (air distance, no binding norm).  Key: category or
# subtype; a subtype value wins if all chosen subtypes share it.
GUIDE_VALUES = {
    "ÖPNV-Haltestellen": ((300, 500), "Bus/Straßenbahn: 300 m in dichter Bebauung, sonst 500 m "
                                      "(übliche Werte in Nahverkehrsplänen)."),
    "Bushaltestelle": ((300, 500), "Bus: 300 m in dichter Bebauung, sonst 500 m "
                                   "(übliche Werte in Nahverkehrsplänen)."),
    "Straßenbahnhaltestelle": ((300, 500), "Straßenbahn: 300–500 m (übliche Werte in Nahverkehrsplänen)."),
    "Bahnhof": ((600, 1000), "Bahn: 600–1000 m (übliche Werte in Nahverkehrsplänen)."),
    "Bahnhaltepunkt": ((600, 1000), "Bahn: 600–1000 m (übliche Werte in Nahverkehrsplänen)."),
    "Nahversorgung": ((500, 1000), "Fußläufige Nahversorgung: 500–1000 m, etwa 10 Minuten zu Fuß."),
    "Gesundheit": ((500, 1000), "Arztpraxis/Apotheke: 500–1000 m fußläufig (üblicher Planungswert)."),
    "Bildung und Betreuung": ((500, 1000), "Kita/Grundschule: 500–1000 m fußläufig (üblicher Planungswert)."),
    "Freizeit und Grün": ((300, 500), "Grünfläche/Spielplatz: höchstens 300 m "
                                      "(Empfehlung der WHO Europa für Grünflächen)."),
}
GUIDE_NOTE = "Richtwert, keine Norm – gemessen wird die Luftlinie, echte Wege sind meist 20–30 % länger."


class RadiusError(ValueError):
    """The radius input cannot be used; the message says how to fix it."""


@dataclass
class OwnTarget:
    """A target set by the user: a point or a picked object (WKT in the project CRS)."""

    wkt: str
    label: str
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class AccessibilityChoice:
    """What the user set under 'Erreichbarkeit' (kept on the workflow)."""

    # category -> chosen subtypes; an empty tuple means the whole category
    targets: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    rings: Tuple[Tuple[bool, int, str], ...] = DEFAULT_RINGS
    fill: bool = True
    opacity: float = FILL_OPACITY
    own_targets: List[OwnTarget] = field(default_factory=list)

    def active_rings(self):
        """Ticked rings, inside → outside: ((metres, colour), …)."""
        return tuple(sorted((metres, color) for on, metres, color in self.rings if on))

    @property
    def radii(self):
        return tuple(metres for metres, _color in self.active_rings())

    @property
    def colors(self):
        return tuple(color for _metres, color in self.active_rings())


def parse_radii(text):
    """'300, 500' -> (300, 500): whole metres, sorted, without doubles."""
    parts = [part.strip() for part in str(text or "").replace(";", ",").split(",") if part.strip()]
    if not parts:
        raise RadiusError("Bitte mindestens einen Radius in Metern eintragen, z. B. „300, 500“.")
    radii = set()
    for part in parts:
        try:
            value = int(float(part.replace("m", "").strip()))
        except ValueError:
            raise RadiusError(f"„{part}“ ist keine Zahl. Bitte Radien in Metern eintragen, z. B. „300, 500“.")
        if not 0 < value <= MAX_RADIUS_M:
            raise RadiusError(f"Radien müssen zwischen 1 und {MAX_RADIUS_M} m liegen („{part}“).")
        radii.add(value)
    if len(radii) > MAX_RADII:
        raise RadiusError(f"Bitte höchstens {MAX_RADII} Radien eintragen.")
    return tuple(sorted(radii))


def radii_text(radii):
    return ", ".join(str(radius) for radius in radii)


def rings_problem(rings):
    """First problem of the ring settings as user text, or None."""
    active = [metres for on, metres, _color in rings if on]
    if not active:
        return "Bitte mindestens einen Ring ankreuzen."
    if any(not 0 < metres <= MAX_RADIUS_M for metres in active):
        return f"Radien müssen zwischen 1 und {MAX_RADIUS_M} m liegen."
    if len(set(active)) != len(active):
        return "Zwei angekreuzte Ringe haben denselben Radius. Bitte einen ändern oder abwählen."
    return None


def rings_with_guide(rings, guide_radii):
    """Rings after 'Richtwert übernehmen': the first rings get the guide
    values and are ticked, the others are unticked; colours stay."""
    result = []
    for index, (_on, metres, color) in enumerate(rings):
        if index < len(guide_radii):
            result.append((True, int(guide_radii[index]), color))
        else:
            result.append((False, metres, color))
    return tuple(result)


def guide_value(category, subtypes=()):
    """(radii, explanation) for a target: the subtype value if all chosen
    subtypes share one, else the category value, else the default."""
    values = {GUIDE_VALUES[s] for s in subtypes if s in GUIDE_VALUES}
    if subtypes and len(values) == 1 and all(s in GUIDE_VALUES for s in subtypes):
        return values.pop()
    if category in GUIDE_VALUES:
        return GUIDE_VALUES[category]
    return DEFAULT_RADII, "Kein Richtwert bekannt – bitte selbst festlegen."


def ring_colors(radii, colors=()):
    """One colour per radius: the chosen ones first, then the presets."""
    colors = list(colors)
    for index in range(len(radii)):
        if index >= len(colors):
            colors.append(DEFAULT_COLORS[index % len(DEFAULT_COLORS)])
    return tuple(colors[: len(radii)])


def target_choices_from(selection):
    """{category: subtypes} -> list of ``TargetChoice`` (one per category)."""
    from .accessibility import TargetChoice

    return [TargetChoice(category, tuple(subtypes)) for category, subtypes in selection.items()]


def ring_label(inner, outer):
    """Legend text of one ring: 'bis 300 m' or '300–500 m'."""
    return f"bis {outer} m" if not inner else f"{inner}–{outer} m"


def choice_problem(choice):
    """First problem of the accessibility settings as user text, or None."""
    if not choice.targets and not choice.own_targets:
        return ("Bitte mindestens ein Ziel ankreuzen, z. B. „ÖPNV-Haltestellen“ oder "
                "einzelne Arten wie „Supermarkt“, oder eigene Ziele in der Karte setzen.")
    return rings_problem(choice.rings)


def own_target_label(number, attributes):
    """'Eigenes Ziel 3' or the name of a picked object."""
    for key in ("Name", "name", "Bezeichnung"):
        if attributes.get(key):
            return str(attributes[key])
    return f"Eigenes Ziel {number}"


def own_layer_id(wkt):
    """Own points and picked areas go into different layers (one geometry type each)."""
    head = wkt.strip().upper()
    kind = "flaechen" if "POLYGON" in head else "linien" if "LINE" in head else "punkte"
    return f"{OWN_LAYER_PREFIX}_{kind}"


def own_records(own_targets):
    """The own targets as pipeline records of the category 'Eigene Ziele'."""
    from .data_pipeline import HarmonizedRecord

    records = []
    for number, target in enumerate(own_targets, start=1):
        extra = {"Bezeichnung": target.label}
        extra.update({key: value for key, value in target.attributes.items()
                      if key not in ("object_id", "category", "object_type")})
        records.append(HarmonizedRecord(
            layer_id=own_layer_id(target.wkt), source_row_id=number,
            attributes={"category": OWN_TARGETS, "object_type": "Eigenes Ziel",
                        "object_id": f"eigen/{number}"},
            geometry=target.wkt, extra_attributes=extra))
    return records


def own_descriptors(own_targets):
    """Layer descriptions for the own targets (for their attribute table)."""
    from .contracts import LayerDescriptor

    kinds = {own_layer_id(target.wkt) for target in own_targets}
    return {layer_id: LayerDescriptor(layer_id, OWN_TARGETS, "Polygon" if layer_id.endswith("flaechen")
                                      else "LineString" if layer_id.endswith("linien") else "Point",
                                      "", category=OWN_TARGETS)
            for layer_id in kinds}


def summary_lines(issues):
    """Short result lines from the pipeline's hints."""
    return [issue.message for issue in issues]


# --- QGIS part -----------------------------------------------------------------


def calculate(records, choice, settings=None):
    """Distances for every chosen target and the own targets (pipeline, M20),
    all with the same rings.  Returns the updated records, the hints and,
    per target label, ``(category, radii, target records)``."""
    from .accessibility import TargetChoice, add_air_distance, load_settings, target_records

    base = settings or load_settings()
    radii = choice.radii
    rings = replace(base, radii_m=tuple(radii))
    issues, targets = [], {}
    for target in target_choices_from(choice.targets):
        records, found = add_air_distance(records, target, rings)
        issues.extend(found)
        targets[target.label] = (target.category, tuple(radii), target_records(records, target, rings))
    if choice.own_targets:
        extra = own_records(choice.own_targets)
        own_ids = {record.layer_id for record in extra}
        with_own = replace(rings, target_categories=tuple(rings.target_categories) + (OWN_TARGETS,))
        target = TargetChoice(OWN_TARGETS)
        combined, found = add_air_distance(list(records) + extra, target, with_own)
        issues.extend(found)
        targets[OWN_TARGETS] = (OWN_TARGETS, tuple(radii), target_records(combined, target, with_own))
        records = [record for record in combined if record.layer_id not in own_ids]
    return records, issues, targets


def distance_columns(records, labels, origin_categories=("Gebäude",)):
    """{object_id: {column: value}} of the accessibility columns of the
    origin objects (for adding them to the layers already in QGIS)."""
    prefixes = tuple(f"Abstand {label} (m)" for label in labels)
    endings = tuple(f"{label} bis " for label in labels)
    values = {}
    for record in records:
        if record.attributes.get("category") not in origin_categories:
            continue
        key = record.attributes.get("object_id")
        if key in (None, ""):
            continue
        columns = {name: value for name, value in (record.extra_attributes or {}).items()
                   if name in prefixes or name.startswith(endings)}
        if columns:
            values[str(key)] = columns
    return values


def add_columns_to_layer(layer, values, id_field="object_id"):
    """Write ``values`` ({object_id: {column: value}}) into an existing
    memory layer; new columns are added.  Returns the number of objects
    that got values and the number of objects without a match."""
    from qgis.core import QgsField
    from qgis.PyQt.QtCore import QMetaType

    meta = getattr(QMetaType, "Type", QMetaType)
    if layer.fields().indexOf(id_field) < 0:
        return 0, layer.featureCount()
    columns = []
    for columns_of_object in values.values():
        for name in columns_of_object:
            if name not in columns:
                columns.append(name)
    provider = layer.dataProvider()
    new = [QgsField(name, meta.Int if name.startswith("Abstand ") else meta.QString)
           for name in columns if layer.fields().indexOf(name) < 0]
    if new:
        provider.addAttributes(new)
        layer.updateFields()
    index = {name: layer.fields().indexOf(name) for name in columns}
    changes, missing = {}, 0
    for feature in layer.getFeatures():
        found = values.get(str(feature[id_field]))
        if not found:
            missing += 1
            continue
        changes[feature.id()] = {index[name]: value for name, value in found.items()}
    if changes:
        provider.changeAttributeValues(changes)
    layer.triggerRepaint()
    return len(changes), missing


def target_point_layer(name, records, descriptors, crs_authid, readable=None):
    """Copies of the target objects as points, with the whole attribute
    table of the loaded layers (all columns of all source layers).  Areas
    (e.g. hospital grounds) become a point inside the area."""
    from types import SimpleNamespace

    from qgis.core import QgsFeature, QgsVectorLayer

    from .outputs import build_result_layers

    layer_ids = []
    for record in records:
        if record.layer_id not in layer_ids:
            layer_ids.append(record.layer_id)
    chosen = [descriptors[layer_id] for layer_id in layer_ids if layer_id in descriptors]
    sources, _reports = build_result_layers(
        SimpleNamespace(harmonized_records=list(records), project_crs=crs_authid), chosen, readable)
    points = QgsVectorLayer(f"Point?crs={crs_authid}", name, "memory")
    provider = points.dataProvider()
    seen = set()
    fields = []
    for source in sources.values():
        for source_field in source.fields():
            if source_field.name() not in seen:
                seen.add(source_field.name())
                fields.append(source_field)
    provider.addAttributes(fields)
    points.updateFields()
    for source in sources.values():  # keep the readable column names
        for index, source_field in enumerate(source.fields()):
            alias = source.attributeAlias(index)
            if alias:
                points.setFieldAlias(points.fields().indexOf(source_field.name()), alias)
    features = []
    for source in sources.values():
        names = source.fields().names()
        for original in source.getFeatures():
            geometry = original.geometry()
            if geometry.isNull() or geometry.isEmpty():
                continue
            point = geometry.pointOnSurface()
            if point.isNull() or point.isEmpty():
                continue
            feature = QgsFeature(points.fields())
            feature.setGeometry(point)
            for field_name in names:
                feature[field_name] = original[field_name]
            features.append(feature)
    provider.addFeatures(features)
    points.updateExtents()
    return points


def build_layers(targets, choice, crs_authid, descriptors=None, readable=None):
    """Per target: a point layer (copies with attribute table) and a ring
    layer (dashed radii, optional 15 % fill).  Returns
    ``[(group label, [layers], summary of the rings)]``."""
    from qgis.core import (
        QgsCategorizedSymbolRenderer, QgsFeature, QgsField, QgsFillSymbol, QgsGeometry,
        QgsMarkerSymbol, QgsRendererCategory, QgsSingleSymbolRenderer, QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QMetaType
    from qgis.PyQt.QtGui import QColor

    meta = getattr(QMetaType, "Type", QMetaType)
    descriptors = {**(descriptors or {}), **own_descriptors(choice.own_targets)}
    result = []
    for label, (_category, radii, records) in targets.items():
        point_layer = target_point_layer(f"Ziele: {label}", records, descriptors, crs_authid, readable)
        points = [feature.geometry() for feature in point_layer.getFeatures()]
        if not points:
            continue
        point_layer.setRenderer(QgsSingleSymbolRenderer(QgsMarkerSymbol.createSimple(
            {"name": "circle", "color": "#2f2f2f", "size": "2.2", "outline_color": "#ffffff"})))

        colors = ring_colors(radii, choice.colors)
        ring_layer = QgsVectorLayer(f"Polygon?crs={crs_authid}", f"Radien: {label}", "memory")
        ring_layer.dataProvider().addAttributes([QgsField(RING_FIELD, meta.QString)])
        ring_layer.updateFields()
        inner_geometry, inner = None, 0
        rings, categories = [], []
        for radius, color in zip(radii, colors):
            disc = QgsGeometry.unaryUnion([point.buffer(radius, 24) for point in points])
            band = disc.difference(inner_geometry) if inner_geometry is not None else disc
            name = ring_label(inner, radius)
            feature = QgsFeature(ring_layer.fields())
            feature.setGeometry(band)
            feature.setAttributes([name])
            rings.append(feature)
            fill = QColor(color)
            fill.setAlphaF(max(0.0, min(1.0, choice.opacity)) if choice.fill else 0.0)
            symbol = QgsFillSymbol.createSimple({
                "color": f"{fill.red()},{fill.green()},{fill.blue()},{fill.alpha()}",
                "outline_color": color if choice.fill else "#555555",
                "outline_width": "0.4", "outline_style": "dash"})
            categories.append(QgsRendererCategory(name, symbol, name))
            inner_geometry, inner = disc, radius
        ring_layer.dataProvider().addFeatures(rings[::-1])  # outer first, inner on top
        ring_layer.setRenderer(QgsCategorizedSymbolRenderer(RING_FIELD, categories))
        result.append((f"Erreichbarkeit – {label}", [point_layer, ring_layer]))
    return result


def pick_object_at(canvas, point, tolerance_px=6):
    """The topmost visible feature at ``point`` (canvas CRS): (geometry in
    canvas CRS, attributes) or None.  Areas must contain the point, points
    and lines must be within a few pixels."""
    from qgis.core import (
        Qgis, QgsCoordinateTransform, QgsFeatureRequest, QgsGeometry, QgsProject, QgsRectangle,
        QgsVectorLayer,
    )

    tolerance = tolerance_px * canvas.mapUnitsPerPixel()
    canvas_crs = canvas.mapSettings().destinationCrs()
    click = QgsGeometry.fromPointXY(point)
    layers = [layer for layer in canvas.layers()
              if isinstance(layer, QgsVectorLayer) and layer.isSpatial()]
    # points first, then areas (e.g. a building), lines last: a click inside a
    # building should take the building, not a line running through it
    order = {Qgis.GeometryType.Point: 0, Qgis.GeometryType.Polygon: 1}
    layers.sort(key=lambda layer: order.get(layer.geometryType(), 2))
    for layer in layers:
        to_layer = QgsCoordinateTransform(canvas_crs, layer.crs(), QgsProject.instance())
        to_canvas = QgsCoordinateTransform(layer.crs(), canvas_crs, QgsProject.instance())
        search = QgsRectangle(point.x() - tolerance, point.y() - tolerance,
                              point.x() + tolerance, point.y() + tolerance)
        try:
            search = to_layer.transformBoundingBox(search)
        except Exception:  # point outside the area this layer can use
            continue
        request = QgsFeatureRequest().setFilterRect(search)
        for feature in layer.getFeatures(request):
            geometry = QgsGeometry(feature.geometry())
            if geometry.isNull():
                continue
            geometry.transform(to_canvas)
            if geometry.type() == Qgis.GeometryType.Polygon and not geometry.contains(click):
                continue
            if geometry.type() != Qgis.GeometryType.Polygon and geometry.distance(click) > tolerance:
                continue
            names = feature.fields().names()
            attributes = {name: str(feature[name]) for name in names
                          if feature[name] is not None and str(feature[name]) not in ("", "NULL")}
            attributes["Layer"] = layer.name()
            return geometry, attributes
    return None


def create_target_pick_tool(canvas, mode, on_pick, on_finished):
    """Map tool for own targets.  ``mode`` 'point': every left click sets a
    point; 'object': a left click takes the object below it.  Right click or
    Esc ends.  ``on_pick(geometry, attributes)`` gets canvas-CRS geometries."""
    from qgis.core import QgsGeometry
    from qgis.gui import QgsMapTool
    from qgis.PyQt.QtCore import Qt

    class TargetPickTool(QgsMapTool):
        def __init__(self):
            super().__init__(canvas)
            self.setCursor(Qt.CrossCursor)

        def canvasReleaseEvent(self, event):
            if event.button() == Qt.RightButton:
                on_finished("")
                return
            if event.button() != Qt.LeftButton:
                return
            point = event.mapPoint()
            if mode == "point":
                on_pick(QgsGeometry.fromPointXY(point), {})
                return
            found = pick_object_at(canvas, point)
            if found is None:
                on_finished("Dort liegt kein Objekt. Bitte direkt auf ein Gebäude, eine Fläche "
                            "oder einen Punkt klicken.", keep=True)
                return
            on_pick(*found)

        def keyPressEvent(self, event):
            if event.key() == Qt.Key_Escape:
                on_finished("")

    return TargetPickTool()


class OwnTargetMarkers:
    """Own targets as markers in the map while 'Erreichbarkeit' is open."""

    def __init__(self, canvas):
        self.canvas = canvas
        self.band = None

    def show(self, geometries):
        from qgis.core import Qgis
        from qgis.gui import QgsRubberBand
        from qgis.PyQt.QtGui import QColor

        if self.band is None:
            self.band = QgsRubberBand(self.canvas, Qgis.GeometryType.Point)
            self.band.setColor(QColor(200, 40, 120, 230))
            self.band.setIconSize(12)
            self.band.setIcon(QgsRubberBand.ICON_CIRCLE)
            self.band.setWidth(3)
        self.band.reset(Qgis.GeometryType.Point)
        for geometry in geometries:
            self.band.addPoint(geometry.pointOnSurface().asPoint(), False)
        self.band.updatePosition()
        self.band.show()

    def hide(self):
        if self.band is not None:
            self.band.hide()

    def remove(self):
        if self.band is not None:
            self.canvas.scene().removeItem(self.band)
            self.band = None
