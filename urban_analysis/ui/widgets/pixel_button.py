"""PixelButton: a button drawn in the pixel style with a hard shadow.

States (see ``pixel_motion.BUTTON_STATES``):
- normal: the face sits 3 px above its hard shadow,
- hover: 1 px higher, shadow 4 px,
- pressed: the face sinks onto the shadow position, the shadow disappears
  and the face is lighter for one frame ("click flash"),
- release of a primary button: a small burst of square pixels,
- disabled: desaturated, no shadow, no animation,
- focus: dashed 1 px pixel frame (keyboard use).

Only enums in their full form (``Qt.CursorShape.…``) are used, so the widget
runs with Qt5 (QGIS 3) and Qt6 (QGIS 4).
"""

import random

from qgis.PyQt.QtCore import QRect, QSize, Qt, QTimer, pyqtSignal
from qgis.PyQt.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from qgis.PyQt.QtWidgets import QAbstractButton, QSizePolicy

from ...theme import COLORS, PIXEL_PX
from .. import pixel_motion as pm

VARIANTS = ("primary", "secondary")


class PixelButton(QAbstractButton):
    """Button with a pixel face, a hard shadow and stepped animations."""

    # Emitted right on release (like ``clicked``); animations never delay it.
    confirmed = pyqtSignal()
    # Switched off by "Animationen reduzieren": no particles, press feedback stays.
    animations_enabled = True

    def __init__(self, text="", variant="secondary", parent=None):
        super().__init__(parent)
        if variant not in VARIANTS:
            raise ValueError(f"Unbekannte Knopf-Variante: {variant}")
        self.variant = variant
        self.setText(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Focus (and its dashed frame) only via the Tab key, not after a click.
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._hover = False
        self._flash = 0
        self._particles = []
        self._preview_state = None
        self._rng = random.Random()
        # One timer per button, running only while an effect is visible.
        self._timer = QTimer(self)
        self._timer.setInterval(pm.FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self.pressed.connect(self._on_pressed)
        self.clicked.connect(self._on_clicked)

    # --- size -------------------------------------------------------------

    def _text_font(self):
        font = QFont(self.font())
        font.setBold(self.variant == "primary")
        return font

    def sizeHint(self):
        metrics = QFontMetrics(self._text_font())
        pad_x, pad_y = pm.BUTTON_PADDING
        margin = pm.BURST_MARGIN_PX
        width = metrics.horizontalAdvance(self.text()) + 2 * pad_x + 2 * margin
        height = metrics.height() + 2 * pad_y + pm.BUTTON_LIFT_PX + 2 * margin
        return QSize(width, height)

    def minimumSizeHint(self):
        return self.sizeHint()

    # --- state ------------------------------------------------------------

    def state(self):
        """Current look: normal / hover / pressed / disabled."""
        if self._preview_state is not None:
            return self._preview_state
        return pm.button_state(self.isEnabled(), self.isDown(), self._hover)

    def preview_state(self, state):
        """Force a look (demo and rendered previews); ``None`` = live again."""
        if state is not None and state not in pm.BUTTON_STATES:
            raise ValueError(f"Unbekannter Knopf-Zustand: {state}")
        self._preview_state = state
        self.update()

    def face_rect(self):
        """Rectangle of the button face in the current state."""
        margin = pm.BURST_MARGIN_PX
        area = self.rect().adjusted(margin, margin, -margin, -margin)
        top, face_height, _shadow = pm.face_geometry(self.state(), area.height())
        return QRect(area.x(), area.y() + top, area.width(), face_height)

    # --- events -----------------------------------------------------------

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.animateClick()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        self._particles = []
        self._flash = 0
        super().hideEvent(event)

    def _on_pressed(self):
        # Press feedback is immediate and stays even with reduced animations.
        self._flash = pm.FLASH_FRAMES
        self._start()
        self.update()

    def _on_clicked(self):
        self.confirmed.emit()  # first the action, then the cosmetics
        if self.variant == "primary" and self.animations_enabled and self.isVisible():
            face = self.face_rect()
            self._particles += pm.spawn_burst(
                face.center().x(), face.center().y(), self._rng,
                half_width=face.width() // 2, half_height=face.height() // 2,
            )
            self._start()

    def _start(self):
        if not self._timer.isActive():
            self._timer.start()

    def _tick(self):
        if self._flash > 0:
            self._flash -= 1
        self._particles = pm.step_burst(self._particles)
        if not self._particles and self._flash == 0:
            self._timer.stop()
        self.update()

    # --- painting ---------------------------------------------------------

    def _colors(self, state):
        c = COLORS
        if self.variant == "primary":
            face, shadow, text, outline = c["accent"], c["accent_dark"], c["text_on_accent"], None
        else:
            face, shadow, text, outline = c["surface"], c["outline"], c["text"], c["outline"]
            if state == "hover":
                face = c["button_hover"]
        if state == "disabled":
            face = pm.desaturate(face)
            text = c["disabled_text"] if self.variant == "secondary" else pm.lighten(face, 0.6)
            outline = c["disabled_text"] if outline else None
        if self._flash > 0:
            face = pm.lighten(face, pm.FLASH_AMOUNT)
        return face, shadow, text, outline

    def _fill_stair(self, painter, rect, color):
        for x, y, w, h in pm.stair_rects(rect.x(), rect.y(), rect.width(), rect.height(), PIXEL_PX):
            painter.fillRect(x, y, w, h, QColor(color))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        state = self.state()
        face_color, shadow_color, text_color, outline = self._colors(state)
        face = self.face_rect()
        _top, _height, shadow = pm.face_geometry(state, face.height() + pm.BUTTON_LIFT_PX)

        if shadow > 0:
            self._fill_stair(painter, face.translated(0, shadow), shadow_color)
        if outline:
            self._fill_stair(painter, face, outline)
            inner = face.adjusted(PIXEL_PX, PIXEL_PX, -PIXEL_PX, -PIXEL_PX)
            self._fill_stair(painter, inner, face_color)
        else:
            self._fill_stair(painter, face, face_color)

        painter.setFont(self._text_font())
        painter.setPen(QColor(text_color))
        painter.drawText(face, Qt.AlignmentFlag.AlignCenter, self.text())

        if self.hasFocus() and state != "disabled":
            pen = QPen(QColor(COLORS["outline"]))
            pen.setWidth(1)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(face.adjusted(-3, -3, 2, 2 + shadow))

        for x, y, _vx, _vy, size, color, _left in self._particles:
            painter.fillRect(int(x), int(y), size, size, QColor(COLORS[color]))
        painter.end()
