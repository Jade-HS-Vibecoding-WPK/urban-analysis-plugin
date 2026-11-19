"""Accessibility in the guidance (W16, E26, E34): its own area in step 9.

The calculation (distance as the crow flies) is ``accessibility.py`` of
Person Mac.  This module turns the user's choices into ``TargetChoice``
objects and draws the result in QGIS: the targets as points (copies of the
loaded objects with their whole attribute table) and, per radius, a dashed
ring around them; the area between two rings can be filled with 15 %
opacity.  The helpers at the top are QGIS-free.

Radii are suggested per target from usual planning values ("Richtwerte",
see ``GUIDE_VALUES``); the user can always change them.
"""

from dataclasses import dataclass, field, replace
from typing import Dict, Optional, Tuple

DEFAULT_RADII = (300, 500)
# preset ring colours (inside → outside): green, yellow, red, then more
DEFAULT_COLORS = ("#3fa34d", "#e6c229", "#d64545", "#7b5cc4", "#3b7fc4")
FILL_OPACITY = 0.15
MAX_RADII = 5
MAX_RADIUS_M = 5000
RING_FIELD = "Radius"

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
class AccessibilityChoice:
    """What the user set in step 9 'Erreichbarkeitsanalyse' (kept on the workflow)."""

    # category -> chosen subtypes; an empty tuple means the whole category
    targets: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    # category -> own radii; missing categories use the guide value
    radii: Dict[str, Tuple[int, ...]] = field(default_factory=dict)
    fill: bool = True
    colors: Tuple[str, ...] = DEFAULT_COLORS[:2]


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


def guide_value(category, subtypes=()):
    """(radii, explanation) for a target: the subtype value if all chosen
    subtypes share one, else the category value, else the default."""
    values = {GUIDE_VALUES[s] for s in subtypes if s in GUIDE_VALUES}
    if subtypes and len(values) == 1 and all(s in GUIDE_VALUES for s in subtypes):
        return values.pop()
    if category in GUIDE_VALUES:
        return GUIDE_VALUES[category]
    return DEFAULT_RADII, "Kein Richtwert bekannt – bitte selbst festlegen."


def radii_for(choice, category):
    """The radii used for one target category."""
    own = choice.radii.get(category)
    return own if own else guide_value(category, choice.targets.get(category, ()))[0]


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
    if not choice.targets:
        return ("Bitte mindestens ein Ziel ankreuzen, z. B. „ÖPNV-Haltestellen“ oder "
                "einzelne Arten wie „Supermarkt“.")
    return None


def summary_lines(issues):
    """Short result lines from the pipeline's hints."""
    return [issue.message for issue in issues]


# --- QGIS part -----------------------------------------------------------------


def calculate(records, choice, settings=None):
    """Distances for every chosen target (pipeline, M20), each with its own
    radii.  Returns the updated records, the hints and, per target label,
    ``(category, radii, target records)``."""
    from .accessibility import add_air_distance, load_settings, target_records

    base = settings or load_settings()
    issues, targets = [], {}
    for target in target_choices_from(choice.targets):
        radii = radii_for(choice, target.category)
        own = replace(base, radii_m=tuple(radii))
        records, found = add_air_distance(records, target, own)
        issues.extend(found)
        targets[target.label] = (target.category, tuple(radii), target_records(records, target, own))
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
    result = []
    for label, (_category, radii, records) in targets.items():
        point_layer = target_point_layer(f"Ziele: {label}", records, descriptors or {}, crs_authid, readable)
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
            fill.setAlphaF(FILL_OPACITY if choice.fill else 0.0)
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
