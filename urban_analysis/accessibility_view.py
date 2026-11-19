"""Accessibility in the guidance (W16, E26, E34): choice in step 7, layers in step 9.

The calculation (distance as the crow flies) is ``accessibility.py`` of
Person Mac.  This module turns the user's choices into ``TargetChoice``
objects and draws the result in QGIS: the targets as points and, per
radius, a dashed ring around them; the area between two rings can be
filled with 15 % opacity.  The helpers at the top are QGIS-free.
"""

from dataclasses import dataclass, field, replace
from typing import Dict, List, Sequence, Tuple

DEFAULT_RADII = (300, 500)
# preset ring colours (inside → outside): green, yellow, red, then more
DEFAULT_COLORS = ("#3fa34d", "#e6c229", "#d64545", "#7b5cc4", "#3b7fc4")
FILL_OPACITY = 0.15
MAX_RADII = 5
MAX_RADIUS_M = 5000


class RadiusError(ValueError):
    """The radius input cannot be used; the message says how to fix it."""


@dataclass
class AccessibilityChoice:
    """What the user set in step 7 (kept on the workflow between steps)."""

    enabled: bool = False
    # category -> chosen subtypes; an empty tuple means the whole category
    targets: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    radii: Tuple[int, ...] = DEFAULT_RADII
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
    """First problem of the step-7 accessibility settings as user text, or None."""
    if not choice.enabled:
        return None
    if not choice.targets:
        return ("Für die Erreichbarkeit bitte mindestens ein Ziel ankreuzen, z. B. "
                "„ÖPNV-Haltestellen“ oder einzelne Arten wie „Supermarkt“.")
    if not choice.radii:
        return "Bitte mindestens einen Radius eintragen."
    return None


def summary_lines(issues):
    """Short result lines for step 9 from the pipeline's hints."""
    return [issue.message for issue in issues]


# --- QGIS part -----------------------------------------------------------------


def calculate(records, choice, settings=None):
    """Distances for every chosen target (pipeline, M20).  Returns the
    updated records, the hints and the target records per choice."""
    from .accessibility import add_air_distance, load_settings, target_records

    settings = replace(settings or load_settings(), radii_m=tuple(choice.radii))
    issues, targets = [], {}
    for target in target_choices_from(choice.targets):
        records, found = add_air_distance(records, target, settings)
        issues.extend(found)
        targets[target.label] = target_records(records, target, settings)
    return records, issues, targets


def build_layers(targets, choice, crs_authid):
    """Per target: a point layer and a ring layer (dashed radii, optional
    15 % fill).  Returns ``[(group label, [layers])]``."""
    from qgis.core import (
        QgsCategorizedSymbolRenderer, QgsFeature, QgsField, QgsFillSymbol, QgsGeometry,
        QgsMarkerSymbol, QgsPointXY, QgsRendererCategory, QgsSingleSymbolRenderer,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QMetaType
    from qgis.PyQt.QtGui import QColor

    from .accessibility import _point

    meta = getattr(QMetaType, "Type", QMetaType)
    colors = ring_colors(choice.radii, choice.colors)
    result = []
    for label, records in targets.items():
        points = [p for p in map(_point, records) if p is not None]
        if not points:
            continue
        point_layer = QgsVectorLayer(f"Point?crs={crs_authid}", f"Ziele: {label}", "memory")
        features = []
        for x, y in points:
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            features.append(feature)
        point_layer.dataProvider().addFeatures(features)
        point_layer.setRenderer(QgsSingleSymbolRenderer(QgsMarkerSymbol.createSimple(
            {"name": "circle", "color": "#2f2f2f", "size": "2.2", "outline_color": "#ffffff"})))

        ring_layer = QgsVectorLayer(f"Polygon?crs={crs_authid}", f"Radien: {label}", "memory")
        ring_layer.dataProvider().addAttributes([QgsField("ring", meta.QString)])
        ring_layer.updateFields()
        inner_geometry, inner = None, 0
        rings, categories = [], []
        for radius, color in zip(choice.radii, colors):
            disc = QgsGeometry.unaryUnion(
                [QgsGeometry.fromPointXY(QgsPointXY(x, y)).buffer(radius, 24) for x, y in points])
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
        ring_layer.setRenderer(QgsCategorizedSymbolRenderer("ring", categories))
        result.append((f"Erreichbarkeit – {label}", [point_layer, ring_layer]))
    return result
