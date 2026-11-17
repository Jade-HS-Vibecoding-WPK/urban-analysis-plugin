"""Own 16x16 pixel icons per layer and category, QGIS-free (tested with pytest).

Every icon is a small tile in the style of the fishing scene: dark outline
with stepped corners, a background and a simple motif.  ``icon_key`` finds
the right icon for a result category or an input layer; unknown layers get
the folded map with a question mark.
"""

import math

from ..theme import COLORS

SIZE = 16

PALETTE = {
    "o": COLORS["outline"], "w": COLORS["cloud"], "s": "#DCD6CA",
    "r": COLORS["accent"], "d": COLORS["accent_dark"],
    "t": COLORS["trunk"], "T": "#5C3829", "g": "#7FAE95", "G": "#5F8F78",
    "p": COLORS["pine"], "P": COLORS["pine_dark"], "l": "#8DB8A6",
    "a": COLORS["water"], "A": "#B7D3CC", "h": "#5E8A81",
    "k": "#6F7F7B", "K": "#A9B5B2", "y": "#D9C7A0", "Y": "#BFA87C",
    "m": COLORS["background"], "n": "#C9D9D3",
}

# Result categories (pipeline names) -> icon
CATEGORY_ICONS = {
    "Gebäude": "gebaeude",
    "Grünflächen": "gruen",
    "Wasserflächen": "wasser",
    "Straßen": "strassen",
    "Fuß- und Radwege": "wege",
    "Plätze": "plaetze",
    "Bahnflächen": "bahn",
    "Schiffsverkehrsflächen": "schiff",
    "Nutzungsflächen": "nutzung",
}
# Input layers (ALKIS table names) -> icon
LAYER_ICONS = {
    "gebaeude": "gebaeude",
    "nutzung": "nutzung",
    "flurstuecke": "flurstuecke",
    "grenzpunkte": "grenzpunkte",
    "bauwerke_f": "bauwerke",
    "bauwerke_p": "bauwerke",
    "bauwerke_l": "bauwerke",
    "bodenschaetzung": "boden",
    "bewertung": "bewertung",
}
# Split result layers of 'nutzung' (layer_suffix in mapping_rules.json)
SUFFIX_ICONS = {
    "fuss_radwege": "wege", "strassen": "strassen", "plaetze": "plaetze",
    "gruen": "gruen", "wasser": "wasser", "bahn": "bahn", "schiff": "schiff",
    "flaechen": "nutzung",
}
UNKNOWN = "unbekannt"


def icon_key(layer_id=None, category=None):
    """Icon for a result category or a layer id; 'unbekannt' if nothing fits."""
    if category in CATEGORY_ICONS:
        return CATEGORY_ICONS[category]
    if layer_id:
        if layer_id in LAYER_ICONS:
            return LAYER_ICONS[layer_id]
        for suffix, key in SUFFIX_ICONS.items():
            if layer_id.endswith("_" + suffix):
                return key
    return UNKNOWN


class _Tile:
    """16x16 tile: outline with stepped corners, background, motif inside."""

    def __init__(self, background):
        self.px = {}
        for y in range(SIZE):
            for x in range(SIZE):
                if x in (0, 15) and y in (0, 15):
                    continue  # stepped corner
                edge = x in (0, 15) or y in (0, 15) or (x in (1, 14) and y in (1, 14))
                self.px[(x, y)] = "o" if edge else background

    def set(self, x, y, c):
        if 1 <= x <= 14 and 1 <= y <= 14 and not (x in (1, 14) and y in (1, 14)):
            self.px[(x, y)] = c

    def rect(self, x, y, w, h, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.set(xx, yy, c)

    def art(self, x0, y0, rows):
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                if ch != ".":
                    self.set(x0 + dx, y0 + dy, ch)


def _gebaeude():
    i = _Tile("m")
    i.art(2, 2, ["....oo....", "...orro...", "..orrrro..", ".orrrrrro.", "orrrrrrrro", "oddddddddo"])
    i.art(3, 8, ["wwwwwwww", "waawwaaw", "waawwaaw", "wwwttwww", "wwwttwww", "wwwttwww"])
    i.rect(2, 8, 1, 6, "o")
    i.rect(11, 8, 1, 6, "o")
    i.rect(1, 14, 14, 1, "g")
    return i


def _gruen():
    i = _Tile("m")
    i.art(3, 1, [
        "....o....",
        "...olo...",
        "..olppo..",
        "..lpppP..",
        ".olpppPo.",
        ".lppppPP.",
        "olppppPPo",
        "lpppppPPP",
        "ooooooooo",
    ])
    i.rect(7, 10, 1, 2, "t")
    i.rect(8, 10, 1, 2, "T")
    i.rect(1, 12, 14, 3, "g")
    for x in (2, 5, 11, 13):
        i.set(x, 11, "G")
    i.set(12, 10, "r")
    i.set(12, 11, "G")
    i.rect(1, 14, 14, 1, "G")
    return i


def _wasser():
    i = _Tile("a")
    i.rect(1, 1, 14, 3, "m")
    i.rect(1, 4, 14, 1, "o")
    i.rect(1, 5, 14, 1, "A")
    for x, y, w in ((3, 7, 3), (10, 8, 3), (2, 13, 4), (9, 12, 3)):
        i.rect(x, y, w, 1, "A")
    i.art(4, 9, [".hhh.h", "hhhhhh", ".hhh.h"])
    return i


def _strassen():
    i = _Tile("g")
    i.rect(1, 1, 14, 3, "m")
    i.rect(1, 4, 14, 1, "K")
    i.rect(1, 5, 14, 6, "k")
    i.rect(1, 11, 14, 1, "K")
    for x in (2, 7, 12):
        i.rect(x, 8, 3, 1, "w")
    return i


def _wege():
    i = _Tile("g")
    for y in range(1, 15):
        cx = round(6 + 3 * math.sin(y / 2.6))
        i.rect(cx - 1, y, 4, 1, "y")
        i.set(cx - 2, y, "Y")
        i.set(cx + 3, y, "Y")
    for x, y in ((7, 3), (8, 5), (6, 9), (5, 11)):
        i.set(x, y, "t")
    for x, y in ((2, 4), (12, 3), (13, 10), (11, 13)):
        i.set(x, y, "G")
    return i


def _plaetze():
    i = _Tile("y")
    for y in range(1, 15):
        for x in range(1, 15):
            if (x // 3 + y // 3) % 2 == 0:
                i.set(x, y, "Y")
    i.art(8, 2, [".ooo.", "ooooo", ".rrr."])   # lamp: cap on top, light below
    i.rect(10, 5, 1, 8, "o")
    i.rect(9, 13, 3, 1, "o")
    return i


def _bahn():
    i = _Tile("y")
    for x in range(2, 15, 3):
        i.rect(x, 3, 2, 10, "t")
        i.set(x + 1, 3, "T")
    i.rect(1, 5, 14, 1, "k")
    i.rect(1, 6, 14, 1, "K")
    i.rect(1, 10, 14, 1, "k")
    i.rect(1, 11, 14, 1, "K")
    return i


def _schiff():
    i = _Tile("a")
    i.rect(1, 1, 14, 8, "m")
    i.rect(1, 9, 14, 1, "o")
    i.rect(1, 10, 14, 1, "A")
    i.art(3, 2, ["....o....", "....or...", "....orr..", "....orrr.", "....o....",
                 "oooooooooo", ".owwwwwwo", "..oooooo."])
    i.rect(3, 12, 3, 1, "A")
    i.rect(10, 13, 3, 1, "A")
    return i


def _nutzung():
    i = _Tile("g")
    i.rect(1, 1, 6, 6, "y")
    i.rect(8, 1, 7, 4, "l")
    i.rect(8, 6, 7, 1, "g")
    i.rect(1, 8, 4, 7, "a")
    i.rect(6, 8, 9, 7, "s")
    i.rect(1, 7, 14, 1, "o")
    i.rect(7, 1, 1, 6, "o")
    i.rect(8, 5, 7, 1, "o")
    i.rect(5, 8, 1, 7, "o")
    return i


def _flurstuecke():
    i = _Tile("n")
    for x in range(2, 14, 2):
        i.set(x, 3, "o")
        i.set(x, 12, "o")
    for y in range(4, 12, 2):
        for x in (2, 8, 13):
            i.set(x, y, "o")
    for x, y in ((2, 3), (13, 3), (2, 12), (13, 12), (8, 3), (8, 12)):
        i.set(x, y, "r")
    return i


def _grenzpunkte():
    i = _Tile("g")
    i.rect(1, 1, 14, 6, "m")
    i.art(5, 3, [".oooo.", "orrrro", "owwwwo", "owsswo", "owwwso", "owwwso", "owwsso", "oooooo"])
    i.rect(1, 11, 14, 4, "g")
    i.rect(1, 12, 14, 1, "G")
    return i


def _bauwerke():
    i = _Tile("m")
    i.art(5, 1, ["..oo..", ".orro.", "orrrro", "oddddo", ".owwo.", ".owaw.", ".owwo.",
                 ".owwo.", "owwwwo", "owaawo", "owwwwo", "owwtwo", "owwtwo"])
    i.rect(1, 14, 14, 1, "g")
    return i


def _boden():
    i = _Tile("m")
    i.rect(1, 4, 14, 1, "G")
    i.rect(1, 5, 14, 1, "g")
    i.rect(1, 6, 14, 3, "t")
    i.rect(1, 9, 14, 3, "Y")
    i.rect(1, 12, 14, 3, "K")
    for x, y, c in ((3, 7, "T"), (10, 8, "T"), (6, 10, "t"), (12, 11, "t"), (4, 13, "k"), (9, 13, "k")):
        i.set(x, y, c)
    i.rect(11, 1, 1, 4, "t")   # spade
    i.rect(10, 4, 3, 2, "K")
    return i


def _bewertung():
    i = _Tile("m")
    i.art(3, 1, ["...oooo...", "ooottttooo", "owwwwwwwwo", "owooowwwwo", "owwwwwwrwo",
                 "owooowwrwo", "owwwwwrwwo", "owooowrwwo", "owwwwrrwwo", "owooowwwwo",
                 "owwwwwwwwo", "owooowwwwo", "oooooooooo"])
    return i


def _unbekannt():
    i = _Tile("w")
    i.rect(1, 1, 4, 14, "A")
    i.rect(5, 1, 1, 14, "s")
    i.rect(6, 1, 4, 14, "l")
    i.rect(10, 1, 1, 14, "s")
    i.rect(11, 1, 4, 14, "A")
    i.art(5, 3, [".ooo.", "oo.oo", "...oo", "..oo.", "..oo.", ".....", "..oo.", "..oo."])
    return i


_MAKERS = {
    "gebaeude": _gebaeude, "gruen": _gruen, "wasser": _wasser, "strassen": _strassen,
    "wege": _wege, "plaetze": _plaetze, "bahn": _bahn, "schiff": _schiff,
    "nutzung": _nutzung, "flurstuecke": _flurstuecke, "grenzpunkte": _grenzpunkte,
    "bauwerke": _bauwerke, "boden": _boden, "bewertung": _bewertung, UNKNOWN: _unbekannt,
}
ICON_KEYS = tuple(_MAKERS)


def icon_pixels(key):
    """{(x, y): '#RRGGBB'} of an icon (unknown keys give the question-mark map)."""
    tile = _MAKERS.get(key, _unbekannt)()
    return {position: PALETTE[c] for position, c in tile.px.items()}
