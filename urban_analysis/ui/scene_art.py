"""Own pixel art of the fishing scene, QGIS-free (tested with plain pytest).

Every figure is built from simple shapes (ellipses, tiers) on a 1 px grid and
returned as a ``Sprite``: a list of coloured cells plus anchor points.  The
widget turns sprites into images once and only moves them around.

Inspired by the mood of a calm pixel landscape (mint sky, pines, water); all
figures are drawn here from scratch.
"""

from dataclasses import dataclass, field

from ..theme import COLORS

# Scene layout (logical px). The scene is as wide as the panel; the island
# stays on the left and the water grows with the width.
SCENE_HEIGHT = 120
WATER_Y = 62
ISLAND_WIDTH = 104
RABBIT_POS = (70, WATER_Y - 33)       # top-left of the rabbit sprite
BOBBER_REST_X = 150                   # float in front of the rabbit
BOBBER_RIGHT_MARGIN = 30              # float stops this far from the right edge
FISH_Y = SCENE_HEIGHT - 20
STEP_LEFT, STEP_RIGHT_MARGIN = 24, 40  # where the step fish swims

SCENE_COLORS = {
    "sky": COLORS["background"],
    "cloud": COLORS["cloud"],
    "cloud_sh": "#E3E4DA",
    "water": COLORS["water"],
    "water_hi": "#B7D3CC",
    "water_2": "#82AEA5",
    "ripple": "#D6E8E3",
    "shadow": "#5E8A81",
    "pine": COLORS["pine"],
    "pine_dark": COLORS["pine_dark"],
    "pine_light": "#8DB8A6",
    "pine_line": "#3D6156",
    "trunk": COLORS["trunk"],
    "trunk_dark": "#5C3829",
    "grass": "#7FAE95",
    "grass_dark": "#5F8F78",
    "dirt": "#8E6A55",
    "outline": COLORS["outline"],
    "fur": COLORS["cloud"],
    "fur_sh": "#DCD6CA",
    "pink": "#E9A9A2",
    "accent": COLORS["accent"],
    "accent_dark": COLORS["accent_dark"],
    "accent_hi": "#F29A90",
    "line": COLORS["text_muted"],
    "line_tight": "#FFFFFF",
    "bubble": "#FFFFFF",
}


@dataclass
class Sprite:
    """Coloured cells (x, y, colour name) with the top-left corner at 0, 0."""

    cells: list
    width: int
    height: int
    anchors: dict = field(default_factory=dict)


def make_sprite(cells, anchors=None):
    """Move cells so the sprite starts at 0, 0; anchors move with them."""
    if not cells:
        return Sprite([], 0, 0, dict(anchors or {}))
    min_x = min(x for x, _y, _c in cells)
    min_y = min(y for _x, y, _c in cells)
    moved = [(x - min_x, y - min_y, c) for x, y, c in cells]
    width = max(x for x, _y, _c in moved) + 1
    height = max(y for _x, y, _c in moved) + 1
    shifted = {name: (ax - min_x, ay - min_y) for name, (ax, ay) in (anchors or {}).items()}
    return Sprite(moved, width, height, shifted)


def ellipse(cx, cy, rx, ry):
    """Cells inside an ellipse (pixel-art circle without soft edges)."""
    return {
        (x, y)
        for x in range(int(cx - rx) - 1, int(cx + rx) + 2)
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2)
        if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1
    }


def paint(shape, fill, outline=None, shade=None):
    """Colour a set of cells; optional 1 px outline around it."""
    cells = []
    if outline:
        ring = {(x + dx, y + dy) for x, y in shape for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}
        cells += [(x, y, outline) for x, y in ring - set(shape)]
    for x, y in shape:
        cells.append((x, y, (shade(x, y) if shade else None) or fill))
    return cells


def line_cells(x0, y0, x1, y1):
    """Bresenham line: hard 1 px pixels without anti-aliasing."""
    cells = []
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        cells.append((x0, y0))
        if x0 == x1 and y0 == y1:
            return cells
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


# --- figures ----------------------------------------------------------------

def pine(height, width):
    """Tall pine: stacked tiers with jagged lower edges, light tips upper left,
    darker right side, dark outline.  Anchor 'base' = foot of the trunk."""
    shape, light = set(), set()
    x0 = width // 2
    tiers = max(3, height // 11)
    tier_h = height // tiers + 4
    for t in range(tiers):
        top = t * (height // tiers)
        max_half = 2 + (width / 2 - 2) * (t + 1) / tiers
        for r in range(tier_h):
            half = int(1 + max_half * r / tier_h)
            for x in range(x0 - half, x0 + half + 1):
                shape.add((x, top + r))
                if r < tier_h // 2 and x < x0 and (x * 3 + r) % 4 == 0:
                    light.add((x, top + r))
        half = int(1 + max_half)
        for x in range(x0 - half, x0 + half + 1):  # drooping, jagged edge
            for d in range(1, 2 + ((x - x0) % 3 == 0)):
                shape.add((x, top + tier_h - 1 + d))
    bottom = max(y for _x, y in shape)

    def shade(x, y):
        if (x, y) in light:
            return "pine_light"
        if x > x0 + 1 and (x + y) % 3 != 0:
            return "pine_dark"
        return None

    trunk = []
    for y in range(bottom - 1, bottom + 6):
        trunk += [(x0 - 1, y, "trunk"), (x0, y, "trunk"), (x0 + 1, y, "trunk_dark")]
    return make_sprite(trunk + paint(shape, "pine", "pine_line", shade), {"base": (x0, bottom + 6)})


def cloud(scale=1.0):
    """Big soft cumulus: round top, flat bottom, darker underside, no outline."""
    shape = set()
    for cx, cy, r in ((10, 22, 9), (22, 14, 12), (36, 9, 14), (52, 15, 11), (64, 21, 8),
                      (30, 24, 9), (46, 24, 9)):
        shape |= ellipse(cx * scale, cy * scale, r * scale, r * scale)
    bottom = int(28 * scale)
    shape = {(x, y) for x, y in shape if y <= bottom}
    return make_sprite(paint(
        shape, "cloud", None,
        lambda x, y: "cloud_sh" if y >= bottom - 2 or (y >= bottom - 5 and (x + y) % 2 == 0) else None,
    ))


def rabbit():
    """Own sitting rabbit facing right, with a small red-orange scarf.
    Anchor 'grip' = paw that holds the rod."""
    body = ellipse(9, 20, 7, 7)
    head = ellipse(13, 11, 5, 4.2)
    ear1 = ellipse(10.5, 4, 1.6, 4.5)
    ear2 = ellipse(14, 4.5, 1.6, 4.5)
    tail = ellipse(2, 21, 2, 2)
    shape = body | head | ear1 | ear2 | tail

    def shade(x, y):
        if (x, y) in body and x > 11 and y > 21:
            return "fur_sh"
        if ((x, y) in ear1 and abs(x + 0.5 - 10.5) < 1 or (x, y) in ear2 and abs(x + 0.5 - 14) < 1) \
                and 2 <= y <= 6:
            return "pink"
        if (x, y) in ellipse(11, 15.5, 6, 1.6):
            return "accent" if y < 16 else "accent_dark"
        return None

    cells = paint(shape, "fur", "outline", shade)
    cells += [(6, y, "accent") for y in range(16, 20)] + [(7, y, "accent") for y in range(16, 19)]
    cells += [(15, 10, "outline"), (15, 11, "outline"), (18, 12, "pink"), (15, 14, "pink"),
              (16, 14, "pink")] + [(x, 23, "fur_sh") for x in (13, 14, 15)]
    return make_sprite(cells, {"grip": (15, 19), "head": (13, 3)})


def island(width=ISLAND_WIDTH):
    """Grass edge with tufts and small flowers, thin earth edge, outline.
    The top of the grass is at y = 5 inside the sprite."""
    cells = []
    top = 5
    for x in range(width):
        cells += [(x, top, "grass"), (x, top + 1, "grass"), (x, top + 2, "grass_dark"),
                  (x, top + 3, "dirt"), (x, top + 4, "dirt"), (x, top + 5, "outline")]
    cells += [(width, y, "outline") for y in range(top, top + 6)]
    for x in range(2, width - 2, 5):  # tufts
        h = 2 + (x * 7) % 3
        cells += [(x, top - k, "grass_dark") for k in range(1, h + 1)]
        cells += [(x + 1, top - k, "grass") for k in range(1, h)]
    for x in (18, 47, 70):  # small flowers
        cells += [(x, top - k, "grass_dark") for k in range(1, 4)]
        cells += [(x - 1, top - 5, "accent"), (x, top - 5, "accent_hi"), (x + 1, top - 5, "accent"),
                  (x - 1, top - 4, "accent"), (x, top - 4, "accent"), (x + 1, top - 4, "accent")]
    return make_sprite(cells)


def bobber():
    """Own float: antenna, red top with highlight, white bottom, outline.
    Anchor 'eye' = top of the antenna (line attaches here), 'water' = waterline."""
    shape = ellipse(3, 6, 3, 4)
    cells = paint(shape, "accent", "outline",
                  lambda x, y: "cloud" if y >= 7 else ("accent_hi" if x < 2 and y <= 4 else None))
    cells += [(3, 0, "outline"), (3, 1, "outline")]
    return make_sprite(cells, {"eye": (3, 0), "water": (3, 7)})


def fish(facing_right=True, size=1.2, tail_up=False):
    """Dark fish shadow under water, with a small tail.  Two tail frames."""
    body = ellipse(7 * size, 3 * size, 6 * size, 2.6 * size)
    tail = set()
    mid = 3 * size + (-0.6 if tail_up else 0.6)
    for i in range(int(4 * size)):
        for y in range(int(mid - i * 0.8), int(mid + i * 0.8) + 1):
            tail.add((1 - i, y))
    shape = body | tail
    if not facing_right:
        span = max(x for x, _y in shape)
        shape = {(span - x, y) for x, y in shape}
    return make_sprite(paint(shape, "shadow"))


def bubble():
    """Speech bubble with three dots ('…') for errors."""
    shape = {(x, y) for x in range(1, 14) for y in range(1, 8)} - {(1, 1), (13, 1), (1, 7), (13, 7)}
    cells = paint(shape, "bubble", "outline")
    cells += [(4, 4, "outline"), (7, 4, "outline"), (10, 4, "outline")]
    cells += [(3, 9, "outline"), (2, 10, "outline"), (3, 8, "bubble")]
    return make_sprite(cells, {"tail": (2, 10)})
