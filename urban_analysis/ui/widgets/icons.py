"""Qt side of the layer icons: sharp pixmaps (doubled, no smoothing), cached."""

from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QColor, QIcon, QImage, QPixmap
from qgis.PyQt.QtWidgets import QHBoxLayout, QLabel, QWidget

from .. import layer_icons

SCALE = 2                       # 16 px art shown at 32 px, every pixel doubled
ICON_PX = layer_icons.SIZE * SCALE
_cache = {}


def layer_pixmap(key, scale=SCALE):
    """Pixmap of a layer icon, scaled by whole pixels (stays crisp)."""
    if (key, scale) not in _cache:
        image = QImage(layer_icons.SIZE, layer_icons.SIZE, QImage.Format.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 0))
        for (x, y), colour in layer_icons.icon_pixels(key).items():
            image.setPixelColor(x, y, QColor(colour))
        size = layer_icons.SIZE * scale
        image = image.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.FastTransformation)
        _cache[(key, scale)] = QPixmap.fromImage(image)
    return _cache[(key, scale)]


def layer_icon(key):
    """QIcon for list entries (use ``QSize(ICON_PX, ICON_PX)`` as icon size)."""
    return QIcon(layer_pixmap(key))


def icon_size():
    return QSize(ICON_PX, ICON_PX)


def with_icon(key, widget, spacing=8):
    """Row with the layer icon on the left and ``widget`` (e.g. a title) next to it."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    icon = QLabel()
    icon.setPixmap(layer_pixmap(key))
    icon.setFixedSize(ICON_PX, ICON_PX)
    layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
    # No layout alignment for the text (that would break wrapped heights);
    # a short label centres itself next to the icon instead.
    if isinstance(widget, QLabel):
        widget.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        widget.setMinimumHeight(ICON_PX)
    layout.addWidget(widget, 1)
    return row
