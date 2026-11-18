"""Qt side of the layer icons, in the current style, cached.

Pixel style: the 16 px tiles doubled without smoothing (stay sharp).
Classic style: flat vector shapes (``classic_icons``) drawn smooth.
"""

import math

from qgis.PyQt.QtCore import QPointF, QRectF, QSize, Qt
from qgis.PyQt.QtGui import (
    QColor, QFont, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
)
from qgis.PyQt.QtWidgets import QHBoxLayout, QLabel, QWidget

from .. import layer_icons
from .. import style as ui_style
from ..classic_icons import classic_shapes

SCALE = 2                       # 16 px art shown at 32 px, every pixel doubled
ICON_PX = layer_icons.SIZE * SCALE
_cache = {}


def _classic_pixmap(key, size):
    """Flat, smooth icon from the classic shape list."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    k = size / layer_icons.SIZE

    def pts(points):
        return QPolygonF([QPointF(x * k, y * k) for x, y in points])

    for shape in classic_shapes(key):
        kind = shape[0]
        p.setPen(Qt.PenStyle.NoPen)
        if kind == "badge":
            p.setBrush(QColor(shape[1]))
            p.setPen(QPen(QColor("#d3d8de"), 1))
            p.drawRoundedRect(QRectF(0.5, 0.5, size - 1, size - 1), 4 * k / 2, 4 * k / 2)
        elif kind == "rect":
            _, x, y, w, h, fill, *radius = shape
            p.setBrush(QColor(fill))
            r = (radius[0] if radius else 0) * k
            p.drawRoundedRect(QRectF(x * k, y * k, w * k, h * k), r, r)
        elif kind == "ellipse":
            _, cx, cy, rx, ry, fill = shape
            p.setBrush(QColor(fill))
            p.drawEllipse(QPointF(cx * k, cy * k), rx * k, ry * k)
        elif kind == "poly":
            p.setBrush(QColor(shape[2]))
            p.drawPolygon(pts(shape[1]))
        elif kind in ("line", "dash"):
            pen = QPen(QColor(shape[2]), shape[3] * k)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            if kind == "dash":
                pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolyline(pts(shape[1]))
        elif kind == "text":
            font = QFont()
            font.setBold(True)
            font.setPixelSize(int(size * 0.6))
            p.setFont(font)
            p.setPen(QColor(shape[2]))
            p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, shape[1])
    p.end()
    return pixmap


def layer_pixmap(key, scale=SCALE):
    """Pixmap of a layer icon in the current style (pixel: whole-pixel scaling)."""
    style = ui_style.current()
    if style == "classic":
        size = layer_icons.SIZE * scale
        if ("classic", key, size) not in _cache:
            _cache[("classic", key, size)] = _classic_pixmap(key, size)
        return _cache[("classic", key, size)]
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
