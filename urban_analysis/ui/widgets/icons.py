"""Qt side of the layer icons: sharp pixmaps (doubled, no smoothing), cached."""

import math

from qgis.PyQt.QtCore import QPointF, QSize, Qt
from qgis.PyQt.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPixmap, QPolygonF
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


def gear_icon(color="#5b6470", size=32, teeth=8):
    """Own simple gear (drawn, smooth edges) for the 'Darstellung' button."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    centre = size / 2
    outer, inner, hole = size * 0.46, size * 0.33, size * 0.15
    points = []
    steps = teeth * 4
    for i in range(steps):
        angle = 2 * math.pi * (i + 0.5) / steps
        radius = outer if i % 4 in (1, 2) else inner
        points.append(QPointF(centre + radius * math.cos(angle), centre + radius * math.sin(angle)))
    gear = QPainterPath()
    gear.addPolygon(QPolygonF(points))
    gear.closeSubpath()
    middle = QPainterPath()
    middle.addEllipse(QPointF(centre, centre), hole, hole)
    painter.fillPath(gear.subtracted(middle), QColor(color))
    painter.end()
    return QIcon(pixmap)


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
