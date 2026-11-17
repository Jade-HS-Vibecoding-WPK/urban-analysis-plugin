"""PixelScene: banner with the fishing rabbit, the float and the step fish.

- Rest: the float lies in front of the rabbit and bobs now and then.
- Loading: the rabbit casts far out and pulls the float in with the real
  progress (right -> rabbit).
- Done: a fish bites, jumps out and hangs wriggling on the line; the rabbit
  is happy.  It never loses a fish.
- Error: the float twitches, a '…' bubble appears, the line is reeled in.
- The step fish swims along the bottom to the current step.
- The plugin title stands in the sky.

Performance: sky/water and the island with trees are drawn once into cached
pixmaps (again only when the width changes); per frame only the moving parts
are painted.  One timer (100 ms) runs only while the scene is visible; it
stops in ``hideEvent``.  Qt enums in full form (Qt5 and Qt6).
"""

import math

from qgis.PyQt.QtCore import QSize, Qt, QTimer
from qgis.PyQt.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from qgis.PyQt.QtWidgets import QSizePolicy, QWidget

from .. import scene_art as art
from ..scene_motion import FRAME_MS, FishingScene, step_positions

CLOUDS = ((4, 24, 1.0), (250, 12, 0.75), (345, 34, 0.55))  # x, y, scale (x for 420 px)
PINES = ((14, 50, 22), (34, 42, 18), (52, 30, 14))       # x, height, width


def _pixmap(sprite):
    image = QImage(max(sprite.width, 1), max(sprite.height, 1), QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    for x, y, color in sprite.cells:
        image.setPixelColor(x, y, QColor(art.SCENE_COLORS[color]))
    return QPixmap.fromImage(image)


class PixelScene(QWidget):
    """Fishing scene banner; the side panel only calls the public methods."""

    def __init__(self, parent=None, total_steps=9, animations=True, title=""):
        super().__init__(parent)
        self.setFixedHeight(art.SCENE_HEIGHT)
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.state = FishingScene(420, total_steps, animations)
        self.title = title
        self.title_font = QFont(self.font())
        self.title_font.setBold(True)
        self.title_font.setPointSize(13)
        self._colors = {name: QColor(value) for name, value in art.SCENE_COLORS.items()}
        # Sprites are turned into pixmaps once.
        self._rabbit_sprite = art.rabbit()
        self._bobber_sprite = art.bobber()
        self._caught_sprite = art.caught_fish()
        self._sprites = {
            "rabbit": _pixmap(self._rabbit_sprite),
            "rabbit_happy": _pixmap(art.rabbit(happy=True)),
            "bobber": _pixmap(self._bobber_sprite),
            "bubble": _pixmap(art.bubble()),
            "island": _pixmap(art.island()),
            "sparkle": _pixmap(art.sparkle()),
            "caught": _pixmap(self._caught_sprite),
            "caught_2": _pixmap(art.caught_fish(tail_left=True)),
            "jumping": _pixmap(art.fish(False, size=1.0, color="catch")),
        }
        self._clouds = [(x, y, _pixmap(art.cloud(scale))) for x, y, scale in CLOUDS]
        self._pines = [(x, art.pine(height, width)) for x, height, width in PINES]
        self._pine_maps = [_pixmap(sprite) for _x, sprite in self._pines]
        self._fish = {
            (right, tail): _pixmap(art.fish(right, tail_up=tail))
            for right in (True, False) for tail in (True, False)
        }
        self._back = None   # sky and water for the current width
        self._front = None  # island, trees and rabbit (transparent)
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)

    # --- public API (used by the side panel) -------------------------------

    def set_step(self, index):
        self.state.set_step(index)
        self._wake()

    def start_loading(self):
        self.state.start_loading()
        self._wake()

    def set_progress(self, percent):
        self.state.set_progress(percent)
        self.update()

    def finish(self):
        self.state.finish()
        self._wake()

    def fail(self):
        self.state.fail()
        self._wake()

    def cancel(self):
        self.state.cancel()
        self._wake()

    def set_animations(self, enabled):
        """'Animationen reduzieren': no ambient motion, no cast; press feedback elsewhere stays."""
        self.state.animations = bool(enabled)
        self.state.set_step(self.state.step)
        self._wake()

    def stop(self):
        self._timer.stop()

    def set_title_font(self, family, point_size=13):
        """Font of the title in the sky (the plugin's heading font)."""
        self.title_font = QFont(family)
        self.title_font.setBold(True)
        self.title_font.setPointSize(point_size)
        self.update()

    # --- Qt events ----------------------------------------------------------

    def sizeHint(self):
        return QSize(420, art.SCENE_HEIGHT)

    def showEvent(self, event):
        self._wake()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def resizeEvent(self, event):
        self._back = self._front = None
        self.state.resize(self.width())
        super().resizeEvent(event)

    def _wake(self):
        if self.isVisible() and self._needs_timer():
            if not self._timer.isActive():
                self._timer.start()
        self.update()

    def _needs_timer(self):
        # Ambient motion (clouds, bobbing, tail) only with animations on.
        return self.state.animations or self.state.busy()

    def _tick(self):
        self.state.tick()
        if not self.isVisible() or not self._needs_timer():
            self._timer.stop()
        self.update()

    # --- painting -----------------------------------------------------------

    def _dot(self, painter, x, y, color, w=1, h=1):
        painter.fillRect(int(x), int(y), w, h, self._colors[color])

    def _build_layers(self):
        width, height = max(self.width(), 1), art.SCENE_HEIGHT
        water_y = art.WATER_Y
        back = QPixmap(width, height)
        back.fill(self._colors["sky"])
        p = QPainter(back)
        self._dot(p, 0, water_y, "water", width, height - water_y)
        self._dot(p, 0, water_y, "outline", width, 1)
        self._dot(p, 0, water_y + 1, "water_hi", width, 1)
        for row in range(4):  # calm horizontal light lines
            for i, x in enumerate(range(10 + row * 23, width, 61)):
                self._dot(p, x, water_y + 8 + row * 13, "water_hi", 6 + (i + row) % 4 * 3, 1)
        self._dot(p, 1, water_y + 1, "water_2", art.ISLAND_WIDTH, 2)  # reflection under the edge
        p.end()

        front = QPixmap(width, height)
        front.fill(QColor(0, 0, 0, 0))
        p = QPainter(front)
        for (x, sprite), pixmap in zip(self._pines, self._pine_maps):
            # the pine's foot stands on the grass
            base_x, base_y = sprite.anchors["base"]
            p.drawPixmap(x - base_x, water_y - 4 - base_y, pixmap)
        p.drawPixmap(0, water_y - 10, self._sprites["island"])
        p.end()
        self._back, self._front = back, front

    def paintEvent(self, _event):
        if self._back is None:
            self._build_layers()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.drawPixmap(0, 0, self._back)
        self._paint_clouds(p)
        self._paint_title(p)
        p.drawPixmap(0, 0, self._front)
        rabbit = "rabbit_happy" if self.state.rabbit_happy() else "rabbit"
        p.drawPixmap(art.RABBIT_POS[0], art.RABBIT_POS[1], self._sprites[rabbit])
        self._paint_steps(p)
        self._paint_rod_and_float(p)
        hx, hy = self._rabbit_sprite.anchors["head"]
        if self.state.sparkle():
            p.drawPixmap(art.RABBIT_POS[0] + hx - 12, art.RABBIT_POS[1] + hy - 6, self._sprites["sparkle"])
        if self.state.bubble > 0:
            p.drawPixmap(art.RABBIT_POS[0] + hx + 4, art.RABBIT_POS[1] + hy - 10, self._sprites["bubble"])
        p.end()

    def _paint_title(self, p):
        if not self.title:
            return
        p.save()
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        p.setFont(self.title_font)
        p.setPen(self._colors["title"])
        # Always centred in the current panel width.
        p.drawText(0, art.TITLE_TOP, self.width(), art.TITLE_HEIGHT,
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, self.title)
        p.restore()

    def _paint_clouds(self, p):
        width = self.width()
        scale = width / 420
        for x, y, pixmap in self._clouds:
            span = width + pixmap.width()
            cx = (round(x * scale) + self.state.cloud_offset) % span
            if cx > width:
                cx -= span
            p.drawPixmap(int(cx), y, pixmap)

    def _paint_steps(self, p):
        state = self.state
        bottom = art.SCENE_HEIGHT - 6
        for index, x in enumerate(step_positions(self.width(), state.total_steps)):
            self._dot(p, x - 1, bottom, "water_hi" if index <= state.step else "water_2", 3, 1)
        fx, right, tail_up, wake = state.fish_state()
        pixmap = self._fish[(right, tail_up)]
        left = fx - pixmap.width() // 2
        for k, (dx, dy, w) in enumerate(wake):
            start = left + dx if right else left + dx - w
            self._dot(p, start, art.FISH_Y + dy, "ripple" if k < 2 else "water_hi", w, 1)
        p.drawPixmap(left, art.FISH_Y, pixmap)

    def _pixels(self, p, points, color):
        for a, b in zip(points, points[1:]):
            for x, y in art.line_cells(a[0], a[1], b[0], b[1]):
                self._dot(p, x, y, color)

    def _paint_rod_and_float(self, p):
        state = self.state
        gx, gy = self._rabbit_sprite.anchors["grip"]
        grip = (art.RABBIT_POS[0] + gx, art.RABBIT_POS[1] + gy)
        dx, dy = state.rod_tip()
        tip = (grip[0] + dx, grip[1] + dy)
        rod = art.line_cells(grip[0], grip[1], tip[0], tip[1])
        for index, (x, y) in enumerate(rod):
            self._dot(p, x, y, "trunk")
            if index < len(rod) // 3:
                self._dot(p, x, y + 1, "trunk_dark")
        self._dot(p, tip[0], tip[1], "cloud")

        float_x, float_dy, visible, sunk = state.float_state()
        eye_x, eye_y = self._bobber_sprite.anchors["eye"]
        water_dy = self._bobber_sprite.anchors["water"][1]
        top = art.WATER_Y - water_dy + float_dy + sunk
        eye = (float_x, top)
        mode = state.line_mode()
        if mode == "slack":
            points = []
            for i in range(9):
                t = i / 8
                points.append((round(tip[0] + (eye[0] - tip[0]) * t),
                               round(tip[1] + (eye[1] - tip[1]) * t + 10 * math.sin(math.pi * t))))
            self._pixels(p, points, "line")
        elif mode == "tight":
            self._pixels(p, [tip, eye], "line_tight")
        self._paint_catch(p, tip, float_x)
        if not visible:
            return
        p.save()
        p.setClipRect(0, 0, self.width(), art.WATER_Y + 4)  # dipping float disappears
        p.drawPixmap(float_x - eye_x, top, self._sprites["bobber"])
        p.restore()
        spread = 2 if state.splash > 0 or sunk > 0 else 0
        for rx, ry, w in ((-9 - spread, 2, 4), (6 + spread, 2, 4), (-5, 5, 3), (3, 5, 3)):
            self._dot(p, float_x + rx, art.WATER_Y + ry, "ripple", w, 1)
        if state.phase == "loading":  # the float is pulled to the left: wake on the right
            for k, (rx, ry, w) in enumerate(((10, 3, 6), (20, 1, 5), (30, 4, 4))):
                self._dot(p, float_x + rx, art.WATER_Y + ry, "ripple" if k == 0 else "water_hi", w, 1)

    def _paint_catch(self, p, tip, float_x):
        """The caught fish: jumps out of the water, then hangs on the line."""
        view = self.state.catch_view()
        if view is None:
            return
        mouth_x, mouth_y = self._caught_sprite.anchors["mouth"]
        hang = (tip[0] - mouth_x, tip[1] + 8)
        if view[0] == "jump":
            t = view[1]
            jumping = self._sprites["jumping"]
            start = (float_x - jumping.width() // 2, art.WATER_Y - 8)
            x = round(start[0] + (hang[0] - start[0]) * t)
            y = round(start[1] + (hang[1] - start[1]) * t - 12 * math.sin(math.pi * t))
            self._pixels(p, [tip, (x + 1, y + 3)], "line_tight")
            p.drawPixmap(x, y, jumping)
            for rx, w in ((-6, 4), (4, 4), (-2, 3)):  # splash where it jumped out
                self._dot(p, float_x + rx, art.WATER_Y - 2 - abs(rx) // 3, "ripple", w, 1)
            return
        pixmap = self._sprites["caught_2" if view[1] else "caught"]
        self._pixels(p, [tip, (hang[0] + mouth_x, hang[1] + mouth_y)], "line")
        p.drawPixmap(hang[0], hang[1], pixmap)
