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
NUTZUNG_COLORS = {
    "Gebäude": ("#b5533f", "#7a3426"),
    "Gebäudeteile": ("#d08a7a", "#9c5a4c"),
    "Bauwerke und Überdachungen": ("#a39a93", "#6f6862"),
    "Straßen": ("#f4f2ee", "#8a9097"),
    "Fuß- und Radwege": ("#d9b77e", "#a8834f"),
    "Plätze": ("#e8dcc4", "#b9a988"),
    "Grünflächen": ("#9fcf8f", "#5f9a55"),
    "Hecken und Baumreihen": ("#4f8f46", "#3b6e34"),
    "Wasserflächen": ("#a9cfee", "#5b93c4"),
    "Gewässer": ("#3b7fc4", "#2d6399"),
    "Schiffsverkehrsflächen": ("#7fb2de", "#4a82b3"),
    "Bahnflächen": ("#8c9196", "#5c6166"),
    "Bahnstrecken": ("#3d4246", "#2a2e31"),
    "Nutzungsflächen": ("#f1dfc0", "#c9b48f"),
    "Zäune und Mauern": ("#8a6446", "#6a4a33"),
    "Sonstige OSM-Linien": ("#9aa0a6", "#7d838a"),
    "Sonstige OSM-Flächen": ("#e3e5e7", "#b7bcc1"),
}
FALLBACK_COLORS = ("#dcdcdc", "#a0a0a0")

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


def category_colors(category, style=DEFAULT_MAP_STYLE):
    """(fill, outline) of a category in a map style."""
    fill, outline = NUTZUNG_COLORS.get(category, FALLBACK_COLORS)
    if style == "schwarzplan":
        if category in BUILDINGS:
            return ("#000000", "#000000")
        return ("#f7f7f7", "#d6d6d6")
    if style == "graustufen":
        return (_grey(fill), _grey(outline))
    return (fill, outline)


def draw_rank(category):
    return DRAW_RANK.get(category, 5)


def outside_filter(area_wkt):
    """QGIS expression: object lies outside the study area (no overlap)."""
    wkt = area_wkt.replace("'", "")
    return f"NOT intersects($geometry, geom_from_wkt('{wkt}'))"


def apply_style(layer, category, style=DEFAULT_MAP_STYLE, grey_outside_wkt=None):
    """Give a result layer the colours of ``style`` (QGIS).

    With ``grey_outside_wkt`` (the study area) everything outside the area is
    drawn in grey values, inside in the colours of ``style``."""
    from qgis.core import QgsRuleBasedRenderer, QgsSingleSymbolRenderer

    inside = _symbol(layer, category, style)
    if inside is None:
        return
    if grey_outside_wkt and style != "graustufen":
        root = QgsRuleBasedRenderer.Rule(None)
        outside = QgsRuleBasedRenderer.Rule(_symbol(layer, category, "graustufen"),
                                            filterExp=outside_filter(grey_outside_wkt))
        outside.setLabel("außerhalb des Gebiets")
        rest = QgsRuleBasedRenderer.Rule(inside, label="im Untersuchungsgebiet")
        rest.setIsElse(True)
        root.appendChild(outside)
        root.appendChild(rest)
        layer.setRenderer(QgsRuleBasedRenderer(root))
    else:
        layer.setRenderer(QgsSingleSymbolRenderer(inside))
    layer.triggerRepaint()


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
