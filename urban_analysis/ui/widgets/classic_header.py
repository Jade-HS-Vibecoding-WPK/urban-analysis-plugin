"""ClassicHeader: the header of the style 'Klassisch' (like QGIS, no pixel art).

Title, a row of step points (done = filled with a check mark, current = blue
ring, open = grey ring; a soft halo glides to the current step) and a smooth
loading bar (blue while loading, green with a check mark when done, red and
shaking on errors).  Same public methods as ``PixelScene``, so the side panel
can drive both.  One timer, only while something moves and the header is
visible.  Qt enums in full form (Qt5 and Qt6).
"""

from qgis.PyQt.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from qgis.PyQt.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from qgis.PyQt.QtWidgets import QSizePolicy, QWidget

from ...theme import CLASSIC_COLORS
from ..classic_motion import BEAM_WIDTH, FRAME_MS, ClassicHeaderState

HEIGHT = 92
SIDE = 22                  # left/right margin of the step row
STEP_Y = 52
BAR_Y = 74
BAR_H = 8


class ClassicHeader(QWidget):
    def __init__(self, parent=None, total_steps=9, animations=True, title=""):
        super().__init__(parent)
        self.setFixedHeight(HEIGHT)
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.state = ClassicHeaderState(total_steps, animations)
        self.title = title
        self.title_font = QFont(self.font())
        self.title_font.setBold(True)
        self.title_font.setPointSize(12)
        self.c = {name: QColor(value) for name, value in CLASSIC_COLORS.items()}
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)

    # --- public API (same as PixelScene) -------------------------------------

    def set_step(self, index):
        self.state.set_step(index)
        self._wake()

    def start_loading(self):
        self.state.start_loading()
        self._wake()

    def set_progress(self, percent):
        self.state.set_progress(percent)
        self._wake()

    def finish(self):
        self.state.finish()
        self._wake()

    def fail(self):
        self.state.fail()
        self._wake()

    def cancel(self):
        self.state.cancel()
        self._wake()

    def celebrate(self):
        self.state.celebrate()
        self._wake()

    def set_animations(self, enabled):
        self.state.animations = bool(enabled)
        self._wake()

    def set_title_font(self, family, point_size=12):
        pass  # the classic header keeps the QGIS font

    def stop(self):
        self._timer.stop()

    # --- Qt events ----------------------------------------------------------

    def sizeHint(self):
        return QSize(420, HEIGHT)

    def showEvent(self, event):
        self._wake()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def _wake(self):
        if self.isVisible() and self.state.busy() and not self._timer.isActive():
            self._timer.start()
        self.update()

    def _tick(self):
        self.state.tick()
        if not self.isVisible() or not self.state.busy():
            self._timer.stop()
        self.update()

    # --- painting -----------------------------------------------------------

    def _step_x(self, index):
        total = self.state.total_steps
        if total <= 1:
            return self.width() / 2
        return SIDE + (self.width() - 2 * SIDE) * index / (total - 1)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        c = self.c
        p.fillRect(self.rect(), c["surface"])
        p.fillRect(0, self.height() - 1, self.width(), 1, c["border"])
        if self.title:
            p.setFont(self.title_font)
            p.setPen(c["text"])
            p.drawText(QRectF(0, 8, self.width(), 24), Qt.AlignmentFlag.AlignHCenter
                       | Qt.AlignmentFlag.AlignVCenter, self.title)
        self._paint_steps(p)
        self._paint_bar(p)
        p.end()

    def _paint_steps(self, p):
        state, c = self.state, self.c
        total = state.total_steps
        # line: grey, blue up to the marker
        p.setPen(QPen(c["border"], 2))
        p.drawLine(QPointF(self._step_x(0), STEP_Y), QPointF(self._step_x(total - 1), STEP_Y))
        done_to = total - 1 if state.all_done else state.marker
        p.setPen(QPen(c["accent"], 2))
        p.drawLine(QPointF(self._step_x(0), STEP_Y),
                   QPointF(self._step_x(0) + (self._step_x(1) - self._step_x(0)) * done_to, STEP_Y))
        # soft halo gliding to the current step
        if not state.all_done:
            halo = QColor(c["accent"])
            halo.setAlphaF(0.18)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            mx = self._step_x(0) + (self._step_x(1) - self._step_x(0)) * state.marker
            p.drawEllipse(QPointF(mx, STEP_Y), 11, 11)
        for index in range(total):
            x = self._step_x(index)
            kind = state.point_state(index)
            radius = 6.0
            if index == total - 1 and state.pop_frame is not None:
                radius *= state.pop_scale()
            if kind == "done":
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c["accent"])
                p.drawEllipse(QPointF(x, STEP_Y), radius, radius)
                self._check(p, x, STEP_Y, radius * 0.55, c["text_on_accent"])
            elif kind == "current":
                p.setPen(QPen(c["accent"], 2.5))
                p.setBrush(c["surface"])
                p.drawEllipse(QPointF(x, STEP_Y), 7, 7)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c["accent"])
                p.drawEllipse(QPointF(x, STEP_Y), 3, 3)
            else:
                p.setPen(QPen(c["border_strong"], 1.5))
                p.setBrush(c["surface"])
                p.drawEllipse(QPointF(x, STEP_Y), 5, 5)

    def _paint_beam(self, p, fill):
        """A soft light runs through the filled part (only while loading)."""
        position = self.state.beam_position()
        if position is None or fill.width() < BEAM_WIDTH / 2:
            return
        x = fill.left() - BEAM_WIDTH + (fill.width() + BEAM_WIDTH) * position
        gradient = QLinearGradient(x, 0, x + BEAM_WIDTH, 0)
        clear, light = QColor(255, 255, 255, 0), QColor(255, 255, 255, 150)
        gradient.setColorAt(0.0, clear)
        gradient.setColorAt(0.5, light)
        gradient.setColorAt(1.0, clear)
        clip = QPainterPath()
        clip.addRoundedRect(fill, BAR_H / 2, BAR_H / 2)
        p.save()
        p.setClipPath(clip)
        p.fillRect(QRectF(x, fill.top(), BEAM_WIDTH, fill.height()), gradient)
        p.restore()

    def _check(self, p, x, y, size, color):
        path = QPainterPath()
        path.moveTo(x - size, y)
        path.lineTo(x - size * 0.25, y + size * 0.75)
        path.lineTo(x + size, y - size * 0.7)
        pen = QPen(color, 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

    def _paint_bar(self, p):
        state, c = self.state, self.c
        if state.bar is None:
            return
        left = SIDE + state.shake_offset()
        width = self.width() - 2 * SIDE - 34
        track = QRectF(left, BAR_Y, width, BAR_H)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c["button"])
        p.drawRoundedRect(track, BAR_H / 2, BAR_H / 2)
        color = {"loading": c["accent"], "done": c["success"], "error": c["error"]}[state.bar]
        shown = 100.0 if state.bar == "error" else state.shown
        fill = QRectF(left, BAR_Y, max(width * shown / 100, BAR_H), BAR_H)
        p.setBrush(color)
        p.drawRoundedRect(fill, BAR_H / 2, BAR_H / 2)
        self._paint_beam(p, fill)
        label_x = left + width + 6
        if state.bar == "done":
            p.setBrush(c["success"])
            p.drawEllipse(QPointF(label_x + 9, BAR_Y + BAR_H / 2), 8, 8)
            self._check(p, label_x + 9, BAR_Y + BAR_H / 2, 4.5, c["text_on_accent"])
        else:
            p.setPen(color)
            font = QFont(self.font())
            font.setPointSize(8)
            p.setFont(font)
            text = "!" if state.bar == "error" else f"{int(round(state.shown))} %"
            p.drawText(QRectF(label_x, BAR_Y - 5, 34, BAR_H + 10),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
