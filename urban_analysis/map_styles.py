"""Map styles for the result layers and the PDF (F5 / W18, E33).

Three styles: 'nutzung' (land-use map in plan colours), 'schwarzplan'
(buildings black, everything else very light) and 'graustufen' (the land-use
colours as grey values, for printing).  The colour tables are QGIS-free and
tested with pytest; ``apply_style`` needs QGIS.
"""

MAP_STYLES = {
    "nutzung": "Nutzungskarte (farbig)",
    "schwarzplan": "Schwarzplan",
    "graustufen": "Graustufen (für Druck)",
}
DEFAULT_MAP_STYLE = "nutzung"

BUILDINGS = ("Gebäude", "Gebäudeteile", "Bauwerke und Überdachungen")

# Plan colours per category: (fill, outline).  Lines use the fill colour.
# Soft plan colours (19.11.: gentler tones, same colour families).
NUTZUNG_COLORS = {
    "Gebäude": ("#c97f70", "#a5645a"),
    "Gebäudeteile": ("#dcaa9e", "#bb8a7f"),
    "Bauwerke und Überdachungen": ("#bdb6b0", "#99928c"),
    "Straßen": ("#f8f7f4", "#b8bcc0"),
    "Fuß- und Radwege": ("#e6cfa6", "#c7ab7e"),
    "Plätze": ("#efe7d8", "#cfc2a9"),
    "Grünflächen": ("#c2e0b6", "#93bf88"),
    "Hecken und Baumreihen": ("#89b281", "#6e9466"),
    "Wasserflächen": ("#c7e0f3", "#93b9da"),
    "Gewässer": ("#82acd6", "#6990ba"),
    "Schiffsverkehrsflächen": ("#accbe6", "#86abcd"),
    "Bahnflächen": ("#a9adb1", "#868a8f"),
    "Bahnstrecken": ("#6e7378", "#585c61"),
    "Nutzungsflächen": ("#f5ead5", "#dccdae"),
    "Zäune und Mauern": ("#ab8f78", "#8e745f"),
    "Sonstige OSM-Linien": ("#b7bbbf", "#9ca1a6"),
    "Sonstige OSM-Flächen": ("#ecedef", "#c7cbcf"),
}
FALLBACK_COLORS = ("#e3e3e3", "#b5b5b5")
OUTSIDE_LIGHTEN = 0.55  # outside the study area: grey, mixed with white

# Drawing order: small numbers at the bottom (large land-use areas), large
# numbers on top (lines, buildings), so nothing important is hidden.
DRAW_RANK = {
    "Nutzungsflächen": 0, "Sonstige OSM-Flächen": 1, "Grünflächen": 2,
    "Wasserflächen": 3, "Schiffsverkehrsflächen": 3, "Bahnflächen": 4,
    "Plätze": 5, "Straßen": 6, "Fuß- und Radwege": 7, "Gewässer": 8,
    "Bahnstrecken": 9, "Hecken und Baumreihen": 10, "Zäune und Mauern": 10,
    "Sonstige OSM-Linien": 10, "Bauwerke und Überdachungen": 11,
    "Gebäudeteile": 12, "Gebäude": 13,
}


def _grey(hex_color):
    """Same brightness as ``hex_color``, without colour."""
    red, green, blue = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    value = round(0.299 * red + 0.587 * green + 0.114 * blue)
    return f"#{value:02x}{value:02x}{value:02x}"


def _lighten(hex_color, amount):
    """Mix ``hex_color`` with white (0 = unchanged, 1 = white)."""
    channels = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
    mixed = [round(c + (255 - c) * amount) for c in channels]
    return "#" + "".join(f"{c:02x}" for c in mixed)


def category_colors(category, style=DEFAULT_MAP_STYLE):
    """(fill, outline) of a category in a map style; style 'aussen' is the
    weak grey used outside the study area."""
    fill, outline = NUTZUNG_COLORS.get(category, FALLBACK_COLORS)
    if style == "schwarzplan":
        if category in BUILDINGS:
            return ("#000000", "#000000")
        return ("#f7f7f7", "#d6d6d6")
    if style == "graustufen":
        return (_grey(fill), _grey(outline))
    if style == "aussen":
        return (_lighten(_grey(fill), OUTSIDE_LIGHTEN), _lighten(_grey(outline), OUTSIDE_LIGHTEN))
    return (fill, outline)


def draw_rank(category):
    return DRAW_RANK.get(category, 5)


CATEGORY_PROPERTY = "urban_analysis/category"
STYLE_PROPERTY = "urban_analysis/map_style"
CUT_PROPERTY = "urban_analysis/cut_at_area"


def cut_expressions(area_wkt):
    """QGIS expressions for the part inside and outside the study area: lines
    and areas are cut at the border (only for drawing, data stay whole)."""
    area = f"geom_from_wkt('{area_wkt.replace(chr(39), '')}')"
    return f"intersection($geometry, {area})", f"difference($geometry, {area})"


def apply_style(layer, category, style=DEFAULT_MAP_STYLE, grey_outside_wkt=None):
    """Give a result layer the colours of ``style`` (QGIS).

    With ``grey_outside_wkt`` (the study area) every object is cut at the
    border: the inside part in the colours of ``style``, the outside part in
    a weak grey.  The objects in the layer stay unchanged."""
    from qgis.core import QgsSingleSymbolRenderer

    inside = _symbol(layer, category, style)
    if inside is None:
        return
    layer.setCustomProperty(CATEGORY_PROPERTY, category or "")
    layer.setCustomProperty(STYLE_PROPERTY, style)
    layer.setCustomProperty(CUT_PROPERTY, bool(grey_outside_wkt))
    if grey_outside_wkt:
        symbol = _cut_symbol(layer, category, style, grey_outside_wkt)
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    else:
        layer.setRenderer(QgsSingleSymbolRenderer(inside))
    layer.triggerRepaint()


def legend_symbol(layer):
    """Plain symbol for legends (the cut symbol would show an empty patch)."""
    category = layer.customProperty(CATEGORY_PROPERTY) or None
    style = layer.customProperty(STYLE_PROPERTY) or DEFAULT_MAP_STYLE
    return _symbol(layer, category, style)


def fix_legend(tree_layer):
    """One clean legend entry for a cut layer (layer panel and PDF legend)."""
    from qgis.core import QgsMapLayerLegendUtils

    layer = tree_layer.layer()
    if layer is None or not layer.customProperty(CUT_PROPERTY):
        return
    symbol = legend_symbol(layer)
    if symbol is not None:
        QgsMapLayerLegendUtils.setLegendNodeCustomSymbol(tree_layer, 0, symbol)


def _cut_symbol(layer, category, style, area_wkt):
    """Symbol with two geometry generators: outside part (weak grey) below,
    inside part (colour) on top."""
    from qgis.core import (
        Qgis, QgsFillSymbol, QgsGeometryGeneratorSymbolLayer, QgsLineSymbol,
        QgsMarkerSymbol, QgsWkbTypes,
    )

    inside_expr, outside_expr = cut_expressions(area_wkt)
    geometry = layer.geometryType()
    if geometry == QgsWkbTypes.PolygonGeometry:
        container, kind = QgsFillSymbol(), Qgis.SymbolType.Fill
    elif geometry == QgsWkbTypes.LineGeometry:
        container, kind = QgsLineSymbol(), Qgis.SymbolType.Line
    else:
        container, kind = QgsMarkerSymbol(), Qgis.SymbolType.Marker
    container.deleteSymbolLayer(0)
    outside_style = "aussen" if style != "schwarzplan" else "schwarzplan"
    for expression, part_style in ((outside_expr, outside_style), (inside_expr, style)):
        generator = QgsGeometryGeneratorSymbolLayer.create({"geometryModifier": expression})
        generator.setSymbolType(kind)
        generator.setSubSymbol(_symbol(layer, category, part_style))
        container.appendSymbolLayer(generator)
    return container


def _symbol(layer, category, style):
    """Symbol of one category in one style (fill/outline/line width)."""
    from qgis.core import QgsSymbol, QgsWkbTypes
    from qgis.PyQt.QtGui import QColor

    fill, outline = category_colors(category, style)
    symbol = QgsSymbol.defaultSymbol(layer.geometryType())
    if symbol is None:
        return None
    geometry = layer.geometryType()
    if geometry == QgsWkbTypes.PolygonGeometry:
        symbol.setColor(QColor(fill))
        layer_symbol = symbol.symbolLayer(0)
        if hasattr(layer_symbol, "setStrokeColor"):
            layer_symbol.setStrokeColor(QColor(outline))
            layer_symbol.setStrokeWidth(0.1 if category in BUILDINGS else 0.15)
    elif geometry == QgsWkbTypes.LineGeometry:
        symbol.setColor(QColor(fill))
        symbol.setWidth(0.6 if category in ("Straßen", "Bahnstrecken", "Gewässer") else 0.3)
    else:
        symbol.setColor(QColor(fill))
        symbol.setSize(1.6)
    return symbol
