"""Qt side of the layer icons, in the current style, cached.

Pixel style: the 16 px tiles doubled without smoothing (stay sharp).
Classic style: flat vector shapes (``classic_icons``) drawn smooth.
"""

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
            badge = QRectF(0.5, 0.5, size - 1, size - 1)
            p.setBrush(QColor(shape[1]))
            p.setPen(QPen(QColor("#d3d8de"), 1))
            p.drawRoundedRect(badge, 2 * k, 2 * k)
            # everything after the badge is cut off at its rounded edge, so
            # e.g. a path can run out of the icon cleanly
            clip = QPainterPath()
            clip.addRoundedRect(badge.adjusted(0.5, 0.5, -0.5, -0.5), 2 * k, 2 * k)
            p.setClipPath(clip)
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


PALETTE_DOTS = ("#2f6fb0", "#e8655a", "#4f9a4a")  # blue, red-orange, green
TITLE_ICON_PX = 16              # shown size of the title bar icons (logical px)
TITLE_STROKE = 1.5              # the same line weight for all three
TITLE_INK = "#3d4650"
SCREEN_SCALES = (1.0, 1.25, 1.5, 1.75, 2.0)   # Windows display scaling


def _draw_palette(p):
    shape = QPainterPath()
    shape.addEllipse(QPointF(8, 8.3), 6.6, 5.6)
    thumb = QPainterPath()
    thumb.addEllipse(QPointF(10.6, 10.4), 1.5, 1.4)
    notch = QPainterPath()
    notch.addEllipse(QPointF(14.6, 10.6), 2.0, 1.7)
    p.setPen(QPen(QColor(TITLE_INK), TITLE_STROKE))
    p.setBrush(QColor("#f1ece2"))
    p.drawPath(shape.subtracted(thumb).subtracted(notch))
    p.setPen(Qt.PenStyle.NoPen)
    for colour, (x, y) in zip(PALETTE_DOTS, ((4.9, 6.9), (8.0, 5.0), (11.1, 6.2))):
        p.setBrush(QColor(colour))
        p.drawEllipse(QPointF(x, y), 1.45, 1.45)


def _draw_float(p):
    """'Lösen / andocken': two overlapping windows."""
    pen = QPen(QColor(TITLE_INK), TITLE_STROKE)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(5.25, 2.75, 8, 7), 1, 1)
    p.setBrush(QColor("#ffffff"))
    p.drawRoundedRect(QRectF(2.75, 6.25, 8, 7), 1, 1)


def _draw_close(p):
    pen = QPen(QColor(TITLE_INK), TITLE_STROKE)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(3.5, 3.5), QPointF(12.5, 12.5))
    p.drawLine(QPointF(12.5, 3.5), QPointF(3.5, 12.5))


_TITLE_DRAWERS = {"palette": _draw_palette, "float": _draw_float, "close": _draw_close}


def title_icon(kind):
    """Own title bar icon ('palette', 'float', 'close'): drawn at the shown
    size for every screen scaling, so lines stay equally strong and sharp."""
    icon = QIcon()
    for scale in SCREEN_SCALES:
        side = round(TITLE_ICON_PX * scale)
        pixmap = QPixmap(side, side)
        pixmap.fill(QColor(0, 0, 0, 0))
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.scale(side / TITLE_ICON_PX, side / TITLE_ICON_PX)
        _TITLE_DRAWERS[kind](p)
        p.end()
        pixmap.setDevicePixelRatio(scale)
        icon.addPixmap(pixmap)
    return icon


def palette_icon():
    """The button that switches the look of the side panel."""
    return title_icon("palette")


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
