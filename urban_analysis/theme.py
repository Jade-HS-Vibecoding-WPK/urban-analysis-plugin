"""Shared style for every window of the plugin.

All plugin UI (side panel now, later dialogs and the PDF layout) takes its
colours and widget roles from here, so the look stays consistent and can be
changed in one place.  The style only applies to widgets of this plugin; the
rest of QGIS keeps its own look.

Look "Cozy Pixel": calm pastel mint, dark petrol text, monospace text and
small pixel-art details.  Hard edges (no rounded corners, no soft shadows);
red-orange is the only loud colour and is kept for the main action.

Roles: widgets get a dynamic property ``uaRole`` (see ``ROLES``) and the
stylesheet below styles each role.  Use ``set_role()`` to change a role at
runtime so Qt re-applies the style.
"""

from pathlib import Path

# --- Design tokens --------------------------------------------------------

# Palette "Cozy Pixel"
BG = "#D3E6DF"           # mint, main background
SURFACE = "#EEF4F1"      # cards, inputs, secondary buttons
TEXT = "#1E3B38"         # dark petrol, headings and text
TEXT_MUTED = "#4F6B66"
ACCENT = "#E8655A"       # red-orange: ONLY main / important actions
ACCENT_DARK = "#B8463D"  # hard pixel shadow below ACCENT
WATER = "#8DB6AE"
PINE = "#6E9C8C"
PINE_DARK = "#4C7466"
TRUNK = "#7A4E3A"
CLOUD = "#F6F3EC"
OUTLINE = "#1E3B38"      # 1-2 px pixel outline

COLORS = {
    "background": BG,
    "surface": SURFACE,
    "border": "#9FBDB4",
    "border_strong": OUTLINE,
    "outline": OUTLINE,
    "text": TEXT,
    "text_muted": TEXT_MUTED,
    "text_on_accent": "#FFFFFF",
    # accent: main action and input focus
    "accent": ACCENT,
    "accent_hover": "#EE7A70",
    "accent_pressed": ACCENT_DARK,
    "accent_dark": ACCENT_DARK,
    "accent_light": "#F9DDD9",
    # chosen state of check boxes, radio buttons and choices (calm, not loud)
    "selected": TEXT,
    "selected_light": "#DCEAE5",
    # neutral buttons
    "button": SURFACE,
    "button_hover": "#E2EDE8",
    "button_pressed": "#CFE0D9",
    "disabled": "#DDE6E2",
    "disabled_text": "#8FA39E",
    # scene colours (pixel details)
    "water": WATER,
    "pine": PINE,
    "pine_dark": PINE_DARK,
    "trunk": TRUNK,
    "cloud": CLOUD,
    # states
    "success": "#2F6E57",
    "error": "#B42318",
    "error_bg": "#FBE3DF",
    "warning": "#8A5A00",
    "warning_bg": "#FBF0D9",
    "info": TEXT,
    "info_bg": SURFACE,
    # step lamps and busy bar (warm lamp light)
    "lamp_dark": "#f08c24",
    "lamp": "#ffc845",
    "lamp_light": "#fff6c2",
}

# Spacing in a 4 px grid; one "pixel block" of the pixel details is 2 px.
GRID_PX = 4
PIXEL_PX = 2
SHADOW_PX = 3            # hard shadow offset below raised elements

# --- Fonts ----------------------------------------------------------------
# Optional font files (OFL) in ui/assets/fonts/; without them the system
# monospace font is used.  The pixel font is only for headings.
FONT_DIR = Path(__file__).resolve().parent / "ui" / "assets" / "fonts"
HEADING_FONTS = ("Pixelify Sans", "Silkscreen")
BODY_FONTS = ("JetBrains Mono", "IBM Plex Mono", "Consolas", "Menlo",
              "DejaVu Sans Mono", "Courier New")
HEADING_SIZE_PT = 13
BODY_SIZE_PT = 9


def choose_family(candidates, available):
    """First of ``candidates`` that is installed (case-insensitive), else None."""
    installed = {name.lower(): name for name in available}
    for name in candidates:
        if name.lower() in installed:
            return installed[name.lower()]
    return None


def load_fonts():
    """Register bundled fonts and return {'heading': family, 'body': family}.

    Needs Qt; call it once before building the panel.  Missing font files are
    no error: the heading then uses the body font.
    """
    from qgis.PyQt.QtGui import QFontDatabase

    if FONT_DIR.is_dir():
        for path in sorted(FONT_DIR.glob("*.[ot]tf")):
            QFontDatabase.addApplicationFont(str(path))
    try:
        available = QFontDatabase.families()  # Qt6: static
    except TypeError:
        available = QFontDatabase().families()  # Qt5
    body = choose_family(BODY_FONTS, available) or "monospace"
    heading = choose_family(HEADING_FONTS, available) or body
    return {"heading": heading, "body": body}

# Step lamps (own pixel design): off = not done, dim = current, on = done.
LAMP_FILES = {
    "off": "lampe_off.svg",
    "dim": "lampe_dim.svg",
    "on": "lampe_on.svg",
}
LAMP_SIZE_PX = 24

RADIUS_PX = 0  # pixel style: hard corners

ROLES = (
    "primary",    # one main action per page
    "secondary",  # other buttons
    "choice",     # large choice button that opens a panel below it
    "panel",      # panel that opens below a choice button
    "heading",    # step title
    "hint",       # explanatory text
    "status",     # live feedback such as the area summary
    "error",      # message: something must be fixed
    "info",       # message: neutral information
    "issue-error",    # one review hint (step 4), by severity
    "issue-warning",
    "issue-info",
)

# Map drawing (study area) uses the accent colour.
DRAW_STROKE_RGBA = (47, 111, 176, 230)
DRAW_FILL_RGBA = (47, 111, 176, 60)

ICON_DIR = Path(__file__).resolve().parent / "icons"
# Toolbar button: own 16x16 pixel design of an earth block with grass.
TOOLBAR_ICON_FILE = "erdblock.svg"
# Ticked check boxes: own white pixel check mark on the blue box.
CHECK_ICON_FILE = "haken.svg"
# Radio buttons: own pixel circles (7x7 blocks of 2 px).
RADIO_FILES = {
    "off": "radio_off.svg",
    "on": "radio_on.svg",
    "disabled": "radio_disabled.svg",
}
RADIO_RING = ("..###..", ".#...#.", "#.....#", "#.....#", "#.....#", ".#...#.", "..###..")
RADIO_DOT = ((2, 2), (3, 2), (4, 2), (2, 3), (3, 3), (4, 3), (2, 4), (3, 4), (4, 4))


def icon_path(name=TOOLBAR_ICON_FILE):
    """Absolute path of an icon shipped with the plugin."""
    return str(ICON_DIR / name)


def panel_stylesheet(fonts=None):
    """Stylesheet for a plugin window; set it on the window's top widget.

    ``fonts`` comes from ``load_fonts()``; without it the first body font
    candidate is named and Qt falls back to its default font if missing.
    """
    c = COLORS
    r = RADIUS_PX
    fonts = fonts or {"heading": BODY_FONTS[0], "body": BODY_FONTS[0]}
    body_font = fonts["body"]
    heading_font = fonts["heading"]
    # Qt stylesheets need forward slashes, also on Windows.
    check_icon = Path(icon_path(CHECK_ICON_FILE)).as_posix()
    radio = {state: Path(icon_path(name)).as_posix() for state, name in RADIO_FILES.items()}
    # Flat pixel buttons: 2 px outline, a thicker bottom edge as hard shadow.
    padding = "padding: 5px 12px 4px 12px;"
    pressed_padding = "padding: 7px 12px 4px 12px;"
    return f"""
QWidget {{
    background-color: {c['background']};
    color: {c['text']};
    font-family: "{body_font}";
    font-size: {BODY_SIZE_PT}pt;
}}
QDockWidget::title {{
    background-color: {c['surface']};
    padding: 4px;
    text-align: left;
}}
QScrollArea {{
    border: none;
}}
QLabel {{
    background: transparent;
}}
QLabel[uaRole="heading"] {{
    font-family: "{heading_font}";
    font-weight: bold;
    font-size: {HEADING_SIZE_PT}pt;
}}
QLabel[uaRole="hint"] {{
    color: {c['text_muted']};
}}
QLabel[uaRole="status"] {{
    color: {c['success']};
    font-weight: bold;
}}
QLabel[uaRole="error"] {{
    background-color: {c['error_bg']};
    color: {c['error']};
    border: 2px solid {c['error']};
    border-radius: {r}px;
    padding: 6px;
}}
QLabel[uaRole="info"] {{
    background-color: {c['info_bg']};
    color: {c['info']};
    border: 2px solid {c['outline']};
    border-radius: {r}px;
    padding: 6px;
}}

/* Buttons that are not drawn as PixelButton: flat, 2 px outline,
   thicker bottom edge as hard shadow; pressed sinks onto the shadow. */
QPushButton {{
    background-color: {c['button']};
    color: {c['text']};
    border: 2px solid {c['outline']};
    border-bottom-width: {2 + SHADOW_PX}px;
    border-radius: {r}px;
    {padding}
}}
QPushButton:hover {{
    background-color: {c['button_hover']};
}}
QPushButton:pressed {{
    background-color: {c['button_pressed']};
    border-bottom-width: 2px;
    {pressed_padding}
}}
QPushButton[uaRole="primary"] {{
    background-color: {c['accent']};
    color: {c['text_on_accent']};
    border-color: {c['accent_dark']};
    font-weight: bold;
}}
QPushButton[uaRole="primary"]:hover {{
    background-color: {c['accent_hover']};
}}
QPushButton[uaRole="primary"]:pressed {{
    background-color: {c['accent_pressed']};
    border-bottom-width: 2px;
    {pressed_padding}
}}
/* Choice buttons: full width, left aligned; the chosen one is highlighted
   and its panel opens directly below it. */
QPushButton[uaRole="choice"] {{
    background-color: {c['surface']};
    text-align: left;
    padding: 9px 12px 8px 12px;
    font-weight: bold;
}}
QPushButton[uaRole="choice"]:hover {{
    background-color: {c['selected_light']};
}}
QPushButton[uaRole="choice"]:pressed {{
    background-color: {c['button_pressed']};
    border-bottom-width: 2px;
    padding: 11px 12px 8px 12px;
}}
QPushButton[uaRole="choice"]:checked {{
    background-color: {c['selected_light']};
    border-bottom-width: 2px;
    color: {c['selected']};
}}
QFrame[uaRole="panel"] {{
    background-color: {c['surface']};
    border: 2px solid {c['outline']};
    border-top: none;
    border-radius: {r}px;
}}
QFrame[uaRole="panel"] QLabel, QFrame[uaRole="panel"] QWidget {{
    background-color: {c['surface']};
}}

QPushButton:disabled, QPushButton[uaRole="primary"]:disabled {{
    background-color: {c['disabled']};
    color: {c['disabled_text']};
    border-color: {c['disabled_text']};
    border-bottom-width: 2px;
}}

/* Inputs: surface, 2 px outline, red-orange outline while typing */
QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox, QListWidget {{
    background-color: {c['surface']};
    color: {c['text']};
    border: 2px solid {c['outline']};
    border-radius: {r}px;
    padding: 3px;
    selection-background-color: {c['selected']};
    selection-color: {c['surface']};
}}
QLineEdit:focus, QPlainTextEdit:focus, QAbstractSpinBox:focus, QComboBox:focus,
QListWidget:focus {{
    border-color: {c['accent']};
}}
QComboBox QAbstractItemView {{
    background-color: {c['surface']};
    border: 2px solid {c['outline']};
    selection-background-color: {c['selected_light']};
    selection-color: {c['text']};
}}
QRadioButton, QCheckBox {{
    background: transparent;
    spacing: 6px;
}}
/* Square pixel boxes; ticked = petrol with an own white pixel check mark. */
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    background-color: {c['surface']};
    border: 2px solid {c['outline']};
    border-radius: {r}px;
}}
QCheckBox::indicator:hover {{
    background-color: {c['selected_light']};
}}
QCheckBox::indicator:checked {{
    background-color: {c['selected']};
    border-color: {c['selected']};
    image: url("{check_icon}");
}}
QCheckBox::indicator:disabled {{
    background-color: {c['disabled']};
    border-color: {c['disabled_text']};
}}
/* Round choices as own pixel circles (no soft edges). */
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: none;
    background: transparent;
    image: url("{radio['off']}");
}}
QRadioButton::indicator:checked {{
    image: url("{radio['on']}");
}}
QRadioButton::indicator:disabled {{
    image: url("{radio['disabled']}");
}}
QRadioButton:disabled, QCheckBox:disabled {{
    color: {c['disabled_text']};
}}

/* One review hint per card, coloured edge by severity */
QFrame[uaRole="issue-error"], QFrame[uaRole="issue-warning"], QFrame[uaRole="issue-info"] {{
    background-color: {c['surface']};
    border: 2px solid {c['outline']};
    border-left-width: 6px;
    border-radius: {r}px;
}}
QFrame[uaRole="issue-error"] {{ border-left-color: {c['error']}; }}
QFrame[uaRole="issue-warning"] {{ border-left-color: #d99a00; }}
QFrame[uaRole="issue-info"] {{ border-left-color: {c['pine']}; }}
QFrame[uaRole="issue-error"] QWidget, QFrame[uaRole="issue-warning"] QWidget,
QFrame[uaRole="issue-info"] QWidget {{
    background-color: {c['surface']};
    border: none;
}}

/* Busy bar: fills once with the real progress in lamp colours */
QProgressBar {{
    background-color: {c['surface']};
    border: 2px solid {c['outline']};
    border-radius: {r}px;
    min-height: 12px;
    max-height: 12px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {c['lamp']};
}}
QToolTip {{
    background-color: {c['surface']};
    color: {c['text']};
    border: 2px solid {c['outline']};
}}
QScrollBar:vertical, QScrollBar:horizontal {{
    background: {c['background']};
    border: none;
    width: 10px;
    height: 10px;
}}
QScrollBar::handle {{
    background: {c['pine']};
    border: 2px solid {c['background']};
    min-height: 20px;
    min-width: 20px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
}}
"""


# --- Busy bar: own pixel "wire" that lights up with the real progress ------

WIRE_COLORS = {
    "off": "#4d0d0d",       # wire not loaded yet (dark red)
    "off_edge": "#2e0707",
    "on": "#e8261a",        # loaded part (bright red)
    "on_light": "#ff8a6a",  # highlights on the loaded part
    "spark": "#ff4a2a",     # particles at the progress front
}
WIRE_CELL_PX = 3            # one wire "pixel" on screen
WIRE_ROWS = 5               # height of the wire pattern in cells
WIRE_PATTERN = (2, 2, 2, 1, 1, 1, 2, 3, 3, 3, 2, 2)  # own zig-zag motif (row per column)
SPARK_SPAWN = 2             # new particles per tick at the front
SPARK_LIFE = (8, 16)        # ticks a particle lives


def wire_cells(columns):
    """Cells (x, y) of the wire pattern for ``columns`` columns.

    Where the row changes, a connecting cell keeps the wire continuous.
    """
    cells = []
    previous = None
    for x in range(max(columns, 0)):
        y = WIRE_PATTERN[x % len(WIRE_PATTERN)]
        if previous is not None and previous != y:
            cells.append((x, previous))
        cells.append((x, y))
        previous = y
    return cells


def lit_columns(value, maximum, columns):
    """Number of wire columns that are lit for progress ``value``/``maximum``."""
    if maximum <= 0 or columns <= 0:
        return 0
    fraction = min(max(value / maximum, 0.0), 1.0)
    return int(round(fraction * columns))


def spawn_sparks(front_x, front_y, rng, count=SPARK_SPAWN):
    """New particles at the progress front: [x, y, vx, vy, life, max_life]."""
    sparks = []
    for _ in range(count):
        life = rng.randint(*SPARK_LIFE)
        sparks.append([
            front_x + rng.uniform(-2.0, 2.0),
            front_y + rng.uniform(-1.0, 1.0),
            rng.uniform(-0.6, 0.6),
            rng.uniform(-1.8, -0.7),  # rise upwards
            life,
            life,
        ])
    return sparks


def step_sparks(sparks):
    """Move particles one tick; drop the ones whose life is over."""
    alive = []
    for x, y, vx, vy, life, max_life in sparks:
        life -= 1
        if life <= 0:
            continue
        alive.append([x + vx, y + vy, vx * 0.95, vy * 0.92, life, max_life])
    return alive


def set_role(widget, role):
    """Give ``widget`` a style role and make Qt re-apply the stylesheet."""
    if role is not None and role not in ROLES:
        raise ValueError(f"Unbekannte Stilrolle: {role}")
    widget.setProperty("uaRole", role)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
