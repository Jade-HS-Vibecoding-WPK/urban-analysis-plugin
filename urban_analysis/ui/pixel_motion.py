"""QGIS-free logic of the pixel widgets: positions per state, particles, colours.

All animations run in discrete frames ("stepped", like real pixel art), not
smoothly.  Values here are in logical pixels; the widgets only draw them.
"""

# --- PixelButton geometry ---------------------------------------------------
# The button face sits above its hard shadow.  The bottom edge of the shadow
# never moves, so hover lifts the face and pressing lets it sink onto the
# shadow position.
#   state      face offset from top   shadow depth below the face
BUTTON_STATES = {
    "hover": (0, 4),
    "normal": (1, 3),
    "pressed": (4, 0),
    "disabled": (1, 0),
}
BUTTON_LIFT_PX = 4          # room for face offset + shadow (constant bottom)
BUTTON_PADDING = (12, 6)    # text padding inside the face (x, y)
BURST_MARGIN_PX = 8         # room around the face for the release particles

FRAME_MS = 40               # one animation frame of the button effects
FLASH_FRAMES = 1            # "click flash": face lighter for one frame
FLASH_AMOUNT = 0.25
BURST_COUNT = (5, 8)        # particles per release (primary only)
BURST_FRAMES = (4, 6)       # life of a particle in frames (~200 ms)
BURST_SIZES = (2, 3)        # square particle size in px


def button_state(enabled, down, hover):
    """Which of BUTTON_STATES a button shows."""
    if not enabled:
        return "disabled"
    if down:
        return "pressed"
    if hover:
        return "hover"
    return "normal"


def face_geometry(state, height):
    """(face_top, face_height, shadow_depth) for a button area of ``height`` px."""
    offset, shadow = BUTTON_STATES[state]
    face_height = max(height - BUTTON_LIFT_PX, 1)
    return offset, face_height, shadow


def spawn_burst(center_x, center_y, rng, colors=("accent", "cloud"), half_width=0, half_height=0):
    """Particles flying out of the button on release.

    Each particle: [x, y, vx, vy, size, colour name, frames left].  They start
    on the edge of the face (``half_width``/``half_height`` around the centre),
    so they are visible outside the button.  Directions are spread evenly
    around the circle with a little randomness, so the burst never looks
    lopsided.
    """
    count = rng.randint(*BURST_COUNT)
    particles = []
    for index in range(count):
        # 8 compass directions, rotated by a random step
        dx, dy = _DIRECTIONS[(index + rng.randint(0, 7)) % len(_DIRECTIONS)]
        speed = rng.choice((2, 3, 3, 4))
        start_x = center_x + dx * (half_width + 1)
        start_y = center_y + dy * (half_height + 1)
        if dx == 0:  # straight up/down: spread along the top/bottom edge
            start_x += rng.randint(-(half_width // 2), half_width // 2)
        particles.append([
            float(start_x), float(start_y),
            dx * speed, dy * speed,
            rng.choice(BURST_SIZES),
            colors[index % len(colors)],
            rng.randint(*BURST_FRAMES),
        ])
    return particles


_DIRECTIONS = ((1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1))


def step_burst(particles):
    """Advance particles one frame; slow down, shrink at the end, drop dead ones."""
    alive = []
    for x, y, vx, vy, size, color, left in particles:
        left -= 1
        if left <= 0:
            continue
        if left == 1 and size > 1:
            size -= 1  # fade out: the last frame is smaller
        alive.append([x + vx, y + vy, vx * 0.7, vy * 0.7, size, color, left])
    return alive


# --- Classic style (like QGIS) ------------------------------------------------
# Same feel without pixels: pressed = 1 px lower and darker; release of the
# main button = a soft ring that grows and fades out.
CLASSIC_MARGIN_PX = 5
CLASSIC_PADDING = (14, 6)
RING_FRAMES = 5


def ring_state(frames_left):
    """(grow in px, opacity 0..1) of the release ring; None when it is over."""
    if frames_left <= 0:
        return None
    step = RING_FRAMES - frames_left  # 0 .. RING_FRAMES-1
    return step + 1, round(0.6 * frames_left / RING_FRAMES, 3)


# --- Colours ---------------------------------------------------------------

def _rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(v))):02X}" for v in rgb)


def lighten(color, amount):
    """Mix ``color`` with white; amount 0 = unchanged, 1 = white."""
    return _hex(v + (255 - v) * amount for v in _rgb(color))


def desaturate(color, amount=0.8):
    """Move ``color`` towards its grey value (for disabled buttons)."""
    r, g, b = _rgb(color)
    grey = 0.299 * r + 0.587 * g + 0.114 * b
    return _hex(v + (grey - v) * amount for v in (r, g, b))


def stair_rects(x, y, width, height, step):
    """Two rectangles that together form a box with stepped pixel corners.

    The corners are cut by one pixel block (``step``), which looks like a
    rounded corner in pixel art without any soft edge.
    """
    if width <= 2 * step or height <= 2 * step:
        return ((x, y, width, height),)
    return (
        (x + step, y, width - 2 * step, height),
        (x, y + step, width, height - 2 * step),
    )
