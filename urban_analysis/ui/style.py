"""Which look the side panel uses: 'classic' (like QGIS, default) or 'pixel'.

The choice is kept in the QGIS settings, so it survives a restart.  Widgets
ask ``current()`` while painting; the panel calls ``set_current()`` when the
user picks a style with the gear button.
"""

from ..theme import DEFAULT_STYLE, STYLES

SETTING_KEY = "urban_analysis/style"
STYLE_LABELS = {
    "classic": "Klassisch (QGIS-Stil)",
    "pixel": "Pixel-Stil",
}

_current = DEFAULT_STYLE


def normalize(value):
    """A valid style name; anything unknown becomes the default ('classic')."""
    return value if value in STYLES else DEFAULT_STYLE


def current():
    return _current


def set_current(style):
    global _current
    _current = normalize(style)
    return _current


def load():
    """Read the saved style from the QGIS settings (default: classic)."""
    try:
        from qgis.core import QgsSettings

        value = QgsSettings().value(SETTING_KEY, DEFAULT_STYLE)
    except ImportError:  # outside QGIS (tests)
        value = DEFAULT_STYLE
    return set_current(value)


def save(style):
    """Remember the chosen style in the QGIS settings."""
    style = set_current(style)
    try:
        from qgis.core import QgsSettings

        QgsSettings().setValue(SETTING_KEY, style)
    except ImportError:
        pass
    return style
