"""Shared style for every window of the plugin.

All plugin UI (side panel now, later dialogs and the PDF layout) takes its
colours and widget roles from here, so the look stays consistent and can be
changed in one place.  The style only applies to widgets of this plugin; the
rest of QGIS keeps its own look.

Look: light and neutral (white/grey surfaces, calm blue accent, system
font).  Buttons give visible feedback on hover and when pressed.

Roles: widgets get a dynamic property ``uaRole`` (see ``ROLES``) and the
stylesheet below styles each role.  Use ``set_role()`` to change a role at
runtime so Qt re-applies the style.
"""

from pathlib import Path

# --- Design tokens --------------------------------------------------------

COLORS = {
    "background": "#f6f7f9",
    "surface": "#ffffff",
    "border": "#c9ced6",
    "border_strong": "#9aa3ae",
    "text": "#1f2328",
    "text_muted": "#5b6470",
    "text_on_accent": "#ffffff",
    # accent: main action, progress, focus
    "accent": "#2f6fb0",
    "accent_hover": "#245a91",
    "accent_pressed": "#1b4672",
    "accent_light": "#e6f0fa",
    # neutral buttons
    "button": "#eef1f4",
    "button_hover": "#e1e6eb",
    "button_pressed": "#d0d7df",
    "disabled": "#e9ecef",
    "disabled_text": "#9aa3ae",
    # states
    "success": "#2e7d32",
    "error": "#b42318",
    "error_bg": "#fdecea",
    "warning": "#8a5a00",
    "warning_bg": "#fff4e0",
    "info": "#1f5f99",
    "info_bg": "#e8f1fb",
    # step lamps and busy bar (warm lamp light)
    "lamp_dark": "#f08c24",
    "lamp": "#ffc845",
    "lamp_light": "#fff6c2",
}

# Step lamps (own pixel design): off = not done, dim = current, on = done.
LAMP_FILES = {
    "off": "lampe_off.svg",
    "dim": "lampe_dim.svg",
    "on": "lampe_on.svg",
}
LAMP_SIZE_PX = 24

RADIUS_PX = 4

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


def icon_path(name=TOOLBAR_ICON_FILE):
    """Absolute path of an icon shipped with the plugin."""
    return str(ICON_DIR / name)


def panel_stylesheet():
    """Stylesheet for a plugin window; set it on the window's top widget."""
    c = COLORS
    r = RADIUS_PX
    padding = "padding: 6px 14px;"
    # Pressed: the label moves 1 px down, so the button feels pushed in.
    pressed_padding = "padding: 7px 14px 5px 14px;"
    return f"""
QWidget {{
    background-color: {c['background']};
    color: {c['text']};
}}
QDockWidget::title {{
    background-color: {c['button']};
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
    font-weight: bold;
    font-size: 11pt;
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
    border: 1px solid {c['error']};
    border-radius: {r}px;
    padding: 6px;
}}
QLabel[uaRole="info"] {{
    background-color: {c['info_bg']};
    color: {c['info']};
    border: 1px solid {c['info']};
    border-radius: {r}px;
    padding: 6px;
}}

/* Buttons: hover darkens and frames, pressed darkens more and shifts down. */
QPushButton {{
    background-color: {c['button']};
    color: {c['text']};
    border: 1px solid {c['border_strong']};
    border-radius: {r}px;
    {padding}
}}
QPushButton:hover {{
    background-color: {c['button_hover']};
    border-color: {c['accent']};
}}
QPushButton:pressed {{
    background-color: {c['button_pressed']};
    border-color: {c['accent_pressed']};
    {pressed_padding}
}}
QPushButton[uaRole="primary"] {{
    background-color: {c['accent']};
    color: {c['text_on_accent']};
    border: 1px solid {c['accent_hover']};
    font-weight: bold;
}}
QPushButton[uaRole="primary"]:hover {{
    background-color: {c['accent_hover']};
    border-color: {c['accent_pressed']};
}}
QPushButton[uaRole="primary"]:pressed {{
    background-color: {c['accent_pressed']};
    {pressed_padding}
}}
/* Choice buttons: full width, left aligned; the chosen one is highlighted
   and its panel opens directly below it. */
QPushButton[uaRole="choice"] {{
    background-color: {c['surface']};
    border: 1px solid {c['border_strong']};
    text-align: left;
    padding: 10px 12px;
    font-weight: bold;
}}
QPushButton[uaRole="choice"]:hover {{
    background-color: {c['accent_light']};
    border-color: {c['accent']};
}}
QPushButton[uaRole="choice"]:pressed {{
    background-color: {c['button_pressed']};
    padding: 11px 12px 9px 12px;
}}
QPushButton[uaRole="choice"]:checked {{
    background-color: {c['accent_light']};
    border: 2px solid {c['accent']};
    border-bottom-left-radius: 0px;
    border-bottom-right-radius: 0px;
    color: {c['accent_pressed']};
}}
QFrame[uaRole="panel"] {{
    background-color: {c['surface']};
    border: 2px solid {c['accent']};
    border-top: none;
    border-bottom-left-radius: {r}px;
    border-bottom-right-radius: {r}px;
}}
QFrame[uaRole="panel"] QLabel, QFrame[uaRole="panel"] QWidget {{
    background-color: {c['surface']};
}}

QPushButton:disabled, QPushButton[uaRole="primary"]:disabled {{
    background-color: {c['disabled']};
    color: {c['disabled_text']};
    border-color: {c['border']};
}}

/* Inputs */
QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox, QListWidget {{
    background-color: {c['surface']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: {r}px;
    padding: 3px;
    selection-background-color: {c['accent']};
    selection-color: {c['text_on_accent']};
}}
QLineEdit:hover, QAbstractSpinBox:hover, QComboBox:hover {{
    border-color: {c['border_strong']};
}}
QLineEdit:focus, QPlainTextEdit:focus, QAbstractSpinBox:focus, QComboBox:focus,
QListWidget:focus {{
    border-color: {c['accent']};
}}
QComboBox QAbstractItemView {{
    background-color: {c['surface']};
    selection-background-color: {c['accent_light']};
    selection-color: {c['text']};
}}
QRadioButton, QCheckBox {{
    background: transparent;
    spacing: 6px;
}}
/* Clearly visible circles and boxes, filled blue when chosen. */
QRadioButton::indicator, QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    background-color: {c['surface']};
    border: 2px solid {c['border_strong']};
}}
QRadioButton::indicator {{
    border-radius: 9px;
}}
QCheckBox::indicator {{
    border-radius: 3px;
}}
QRadioButton::indicator:hover, QCheckBox::indicator:hover {{
    border-color: {c['accent']};
}}
QRadioButton::indicator:checked {{
    background-color: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 {c['accent']}, stop:0.55 {c['accent']}, stop:0.65 {c['surface']},
        stop:1 {c['surface']});
    border-color: {c['accent']};
}}
QCheckBox::indicator:checked {{
    background-color: {c['accent']};
    border-color: {c['accent']};
}}
QRadioButton::indicator:disabled, QCheckBox::indicator:disabled {{
    background-color: {c['disabled']};
    border-color: {c['border']};
}}
QRadioButton:disabled, QCheckBox:disabled {{
    color: {c['disabled_text']};
}}

/* One review hint per card, coloured edge by severity */
QFrame[uaRole="issue-error"], QFrame[uaRole="issue-warning"], QFrame[uaRole="issue-info"] {{
    background-color: {c['surface']};
    border: 1px solid {c['border']};
    border-left-width: 5px;
    border-radius: {r}px;
}}
QFrame[uaRole="issue-error"] {{ border-left-color: {c['error']}; }}
QFrame[uaRole="issue-warning"] {{ border-left-color: #d99a00; }}
QFrame[uaRole="issue-info"] {{ border-left-color: {c['border_strong']}; }}
QFrame[uaRole="issue-error"] QWidget, QFrame[uaRole="issue-warning"] QWidget,
QFrame[uaRole="issue-info"] QWidget {{
    background-color: {c['surface']};
    border: none;
}}

/* Busy bar: fills once with the real progress in lamp colours */
QProgressBar {{
    background-color: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {r}px;
    min-height: 12px;
    max-height: 12px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {c['lamp']};
    border-radius: {r - 1}px;
}}
QToolTip {{
    background-color: {c['surface']};
    color: {c['text']};
    border: 1px solid {c['border_strong']};
}}
"""


def busy_chunk_stylesheet(phase):
    """Stylesheet for the filled part of the busy bar with a moving shine.

    ``phase`` runs from 0 to 1; the bright band moves across the part that is
    already loaded, so only finished progress "shimmers".
    """
    c = COLORS
    centre = min(max(phase, 0.0), 1.0)
    left = max(centre - 0.15, 0.0)
    right = min(centre + 0.15, 1.0)
    return (
        "QProgressBar::chunk {"
        f"border-radius: {RADIUS_PX - 1}px;"
        "background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        f"stop:0 {c['lamp_dark']}, stop:{left:.3f} {c['lamp']}, "
        f"stop:{centre:.3f} {c['lamp_light']}, stop:{right:.3f} {c['lamp']}, "
        f"stop:1 {c['lamp_dark']});"
        "}"
    )


def set_role(widget, role):
    """Give ``widget`` a style role and make Qt re-apply the stylesheet."""
    if role is not None and role not in ROLES:
        raise ValueError(f"Unbekannte Stilrolle: {role}")
    widget.setProperty("uaRole", role)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
