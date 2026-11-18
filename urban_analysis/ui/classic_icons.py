"""Flat vector icons per layer for the style 'Klassisch' (QGIS-free data).

Same motifs as the pixel tiles, drawn smooth like QGIS symbols: a soft
rounded badge in a light category colour and a simple glyph on it.  Each icon
is a list of shapes in a 16 x 16 coordinate space; the widget scales them.

Shapes:
    ("badge", fill)                          rounded square background
    ("rect", x, y, w, h, fill[, radius])
    ("ellipse", cx, cy, rx, ry, fill)
    ("poly", ((x, y), ...), fill)
    ("line", ((x, y), ...), colour, width)   open polyline, round caps
    ("dash", ((x, y), ...), colour, width)   dashed polyline
    ("text", text, colour)                   centred character
"""

from .layer_icons import ICON_KEYS

INK = "#3d4650"

CLASSIC_ICONS = {
    "gebaeude": [
        ("badge", "#f6e4df"),
        ("poly", ((2.8, 8.2), (8, 3.6), (13.2, 8.2)), "#b5533f"),
        ("rect", 4.3, 8.0, 7.4, 5.6, "#ffffff"),
        ("line", ((4.3, 8.0), (4.3, 13.6), (11.7, 13.6), (11.7, 8.0)), "#b5533f", 0.9),
        ("rect", 7.1, 10.2, 1.8, 3.4, "#b5533f"),
        ("rect", 5.2, 9.2, 1.4, 1.4, "#7f9bb5"),
        ("rect", 9.4, 9.2, 1.4, 1.4, "#7f9bb5"),
    ],
    "gruen": [
        ("badge", "#e2f1df"),
        ("ellipse", 8, 6.6, 4.2, 4.0, "#4f9a4a"),
        ("ellipse", 6.6, 5.6, 1.6, 1.4, "#7cbf6f"),
        ("rect", 7.3, 9.8, 1.4, 3.6, "#7a5a3a"),
        ("line", ((2.6, 13.4), (13.4, 13.4)), "#4f9a4a", 1.2),
    ],
    "wasser": [
        ("badge", "#e1eef8"),
        ("line", ((2.5, 6), (4.3, 5), (6.1, 6), (7.9, 5), (9.7, 6), (11.5, 5), (13.3, 6)), "#3b7fc4", 1.2),
        ("line", ((2.5, 9), (4.3, 8), (6.1, 9), (7.9, 8), (9.7, 9), (11.5, 8), (13.3, 9)), "#3b7fc4", 1.2),
        ("line", ((2.5, 12), (4.3, 11), (6.1, 12), (7.9, 11), (9.7, 12), (11.5, 11), (13.3, 12)), "#3b7fc4", 1.2),
    ],
    "strassen": [
        ("badge", "#eceef0"),
        ("rect", 2, 5, 12, 6, "#7d858c", 1),
        ("rect", 3, 7.6, 2.4, 0.9, "#ffffff"),
        ("rect", 6.8, 7.6, 2.4, 0.9, "#ffffff"),
        ("rect", 10.6, 7.6, 2.4, 0.9, "#ffffff"),
    ],
    "wege": [
        ("badge", "#f4eddd"),
        ("line", ((4, 14), (6.5, 10.5), (5.5, 7.5), (9, 5), (12, 2.5)), "#c39a5b", 2.6),
        ("line", ((4, 14), (6.5, 10.5), (5.5, 7.5), (9, 5), (12, 2.5)), "#f4eddd", 0.6),
    ],
    "plaetze": [
        ("badge", "#f2ede3"),
        ("rect", 3, 3, 4.5, 4.5, "#d8cbb2", 0.6),
        ("rect", 8.5, 3, 4.5, 4.5, "#d8cbb2", 0.6),
        ("rect", 3, 8.5, 4.5, 4.5, "#d8cbb2", 0.6),
        ("rect", 8.5, 8.5, 4.5, 4.5, "#d8cbb2", 0.6),
        ("ellipse", 8, 8, 1.6, 1.6, "#b5533f"),
    ],
    "bahn": [
        ("badge", "#eceef0"),
        ("rect", 3, 4.2, 1.4, 7.6, "#9a7b5a"),
        ("rect", 6.2, 4.2, 1.4, 7.6, "#9a7b5a"),
        ("rect", 9.4, 4.2, 1.4, 7.6, "#9a7b5a"),
        ("rect", 12.4, 4.2, 1.2, 7.6, "#9a7b5a"),
        ("line", ((2, 6), (14, 6)), "#4a4f55", 1.2),
        ("line", ((2, 10), (14, 10)), "#4a4f55", 1.2),
    ],
    "schiff": [
        ("badge", "#e1eef8"),
        ("line", ((8, 3), (8, 10)), INK, 0.9),
        ("poly", ((8.4, 3.4), (8.4, 9.2), (12.2, 9.2)), "#ffffff"),
        ("line", ((8.4, 3.4), (12.2, 9.2), (8.4, 9.2)), INK, 0.7),
        ("poly", ((2.8, 10.4), (13.2, 10.4), (11.6, 13), (4.4, 13)), "#3b5f86"),
    ],
    "nutzung": [
        ("badge", "#ffffff"),
        ("rect", 2.5, 2.5, 5.2, 5.2, "#f0b8b0", 0.8),
        ("rect", 8.3, 2.5, 5.2, 5.2, "#c9ced6", 0.8),
        ("rect", 2.5, 8.3, 5.2, 5.2, "#a8d5a2", 0.8),
        ("rect", 8.3, 8.3, 5.2, 5.2, "#a9cbe8", 0.8),
    ],
    "flurstuecke": [
        ("badge", "#f4f5f7"),
        ("dash", ((3, 3.5), (13, 3.5), (13, 12.5), (3, 12.5), (3, 3.5)), INK, 0.9),
        ("dash", ((8, 3.5), (8, 12.5)), INK, 0.9),
        ("ellipse", 3, 3.5, 1, 1, "#d0473b"),
        ("ellipse", 13, 3.5, 1, 1, "#d0473b"),
        ("ellipse", 3, 12.5, 1, 1, "#d0473b"),
        ("ellipse", 13, 12.5, 1, 1, "#d0473b"),
    ],
    "grenzpunkte": [
        ("badge", "#f4f5f7"),
        ("rect", 5.6, 4.5, 4.8, 8.5, "#aab2bb", 1.2),
        ("rect", 5.6, 4.5, 4.8, 2.2, "#d0473b", 1.0),
        ("line", ((3, 13.2), (13, 13.2)), "#4f9a4a", 1.2),
    ],
    "bauwerke": [
        ("badge", "#eceef0"),
        ("poly", ((5.6, 5.4), (8, 2.2), (10.4, 5.4)), "#b5533f"),
        ("rect", 6, 5.4, 4, 8.2, "#ffffff"),
        ("line", ((6, 5.4), (6, 13.6), (10, 13.6), (10, 5.4)), INK, 0.8),
        ("rect", 7.4, 7, 1.2, 1.6, "#7f9bb5"),
        ("rect", 7.4, 10.4, 1.2, 3.2, INK),
    ],
    "boden": [
        ("badge", "#f4f5f7"),
        ("rect", 2.5, 4, 11, 2, "#6aa560", 0.6),
        ("rect", 2.5, 6.3, 11, 2.6, "#8a6446", 0.4),
        ("rect", 2.5, 9.2, 11, 2.0, "#c7a874", 0.4),
        ("rect", 2.5, 11.5, 11, 2.0, "#a3abb3", 0.6),
    ],
    "bewertung": [
        ("badge", "#e8f1fb"),
        ("rect", 3.6, 2.8, 8.8, 11, "#ffffff", 1),
        ("line", ((3.6, 3.8), (3.6, 13.8), (12.4, 13.8), (12.4, 3.8)), INK, 0.8),
        ("rect", 6.2, 2, 3.6, 1.8, INK, 0.6),
        ("line", ((5.6, 9), (7.4, 11), (10.6, 6.4)), "#2e7d32", 1.4),
    ],
    "unbekannt": [
        ("badge", "#eef0f2"),
        ("text", "?", "#5b6470"),
    ],
}

def missing_twins():
    """Pixel icons without a classic twin (should be empty; checked by a test)."""
    return set(ICON_KEYS) - set(CLASSIC_ICONS)


def classic_shapes(key):
    """Shapes of a classic icon (unknown keys give the question mark)."""
    return CLASSIC_ICONS.get(key, CLASSIC_ICONS["unbekannt"])
