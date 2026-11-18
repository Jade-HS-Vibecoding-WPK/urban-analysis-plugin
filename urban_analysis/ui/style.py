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


ANIMATIONS_KEY = "urban_analysis/animations"
REDUCE_ANIMATIONS_LABEL = "Animationen reduzieren"


def animations_enabled():
    """True unless 'Animationen reduzieren' was chosen (kept in QGIS settings)."""
    try:
        from qgis.core import QgsSettings

        value = QgsSettings().value(ANIMATIONS_KEY, True)
    except ImportError:  # outside QGIS (tests)
        return True
    return str(value).lower() not in ("false", "0", "no")


def save_animations(enabled):
    try:
        from qgis.core import QgsSettings

        QgsSettings().setValue(ANIMATIONS_KEY, bool(enabled))
    except ImportError:
        pass
    return bool(enabled)


def save(style):
    """Remember the chosen style in the QGIS settings."""
    style = set_current(style)
    try:
        from qgis.core import QgsSettings

        QgsSettings().setValue(SETTING_KEY, style)
    except ImportError:
        pass
    return style
