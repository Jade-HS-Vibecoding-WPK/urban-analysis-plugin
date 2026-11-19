"""QGIS-free behaviour of the classic header (style 'Klassisch').

The same moments as the fishing scene, without pixel art:
- step progress: a row of 9 points; the marker glides to the current step,
- loading: a smooth bar follows the REAL progress (shown value eases in),
- done: the bar turns green with a check mark for a moment, then hides,
- error: the bar turns red and shakes briefly, then hides,
- result layers created: all points are filled and the last one 'pops'.
Everything advances in frames of FRAME_MS; nothing here blocks the plugin.
"""

FRAME_MS = 40
MARKER_EASE = 0.35          # share of the remaining way per frame
BAR_EASE = 0.3
DONE_FRAMES = 30            # green bar with check mark (~1.2 s)
ERROR_FRAMES = 30           # red bar (~1.2 s)
SHAKE = (3, -3, 2, -2, 1, -1)
POP = (1.0, 1.25, 1.45, 1.3, 1.1, 1.0)   # scale of the last point when all is done
# 'Beam': a soft light runs through the filled part of the bar while loading
BEAM_STEP = 0.025           # share of the filled part per frame (~1.6 s per run)
BEAM_PAUSE = 0.6            # pause after each run (in the same units)
BEAM_WIDTH = 36             # px


class ClassicHeaderState:
    """State of the classic header; the widget asks it what to draw."""

    def __init__(self, total_steps=9, animations=True):
        self.total_steps = total_steps
        self.animations = animations
        self.step = 0
        self.all_done = False
        self.marker = 0.0          # shown marker position (float step index)
        self.bar = None            # None (hidden), 'loading', 'done', 'error'
        self.target = 0.0          # real progress 0-100
        self.shown = 0.0           # displayed progress (eases towards target)
        self.frames_left = 0
        self.shake_frame = None
        self.pop_frame = None
        self.beam = 0.0            # 0..1 runs through the fill, above 1 = pause

    # --- commands from the panel -------------------------------------------

    def set_step(self, index):
        self.all_done = index >= self.total_steps
        self.step = max(0, min(index, self.total_steps - 1))
        if not self.animations:
            self.marker = float(self.step)

    def start_loading(self):
        self.bar = "loading"
        self.target = self.shown = 0.0
        self.shake_frame = None
        self.beam = 0.0

    def set_progress(self, percent):
        self.target = min(max(float(percent), 0.0), 100.0)
        if not self.animations:
            self.shown = self.target

    def finish(self):
        if self.bar is None:
            return
        self.bar = "done"
        self.target = self.shown = 100.0
        self.frames_left = DONE_FRAMES

    def fail(self):
        self.bar = "error"
        self.frames_left = ERROR_FRAMES
        self.shake_frame = 0 if self.animations else None

    def cancel(self):
        self.bar = None
        self.target = self.shown = 0.0
        self.shake_frame = None

    def celebrate(self):
        self.all_done = True
        self.pop_frame = 0 if self.animations else None

    # --- animation ---------------------------------------------------------

    def busy(self):
        return (abs(self.marker - self.step) > 0.01 or self.bar is not None
                or self.shake_frame is not None or self.pop_frame is not None)

    def tick(self):
        distance = self.step - self.marker
        self.marker = float(self.step) if abs(distance) < 0.02 else self.marker + distance * MARKER_EASE
        if self.bar == "loading":
            gap = self.target - self.shown
            self.shown = self.target if abs(gap) < 0.5 else self.shown + gap * BAR_EASE
            if self.animations:
                self.beam += BEAM_STEP
                if self.beam > 1.0 + BEAM_PAUSE:
                    self.beam = 0.0
        elif self.bar in ("done", "error"):
            self.frames_left -= 1
            if self.frames_left <= 0:
                self.bar = None
        if self.shake_frame is not None:
            self.shake_frame += 1
            if self.shake_frame >= len(SHAKE):
                self.shake_frame = None
        if self.pop_frame is not None:
            self.pop_frame += 1
            if self.pop_frame >= len(POP):
                self.pop_frame = None

    # --- what to draw ------------------------------------------------------

    def point_state(self, index):
        """'done', 'current' or 'open' for step point ``index``."""
        if self.all_done or index < self.step:
            return "done"
        return "current" if index == self.step else "open"

    def beam_position(self):
        """None (no beam) or 0..1: where the light is in the filled part."""
        if self.bar != "loading" or not self.animations or self.beam > 1.0:
            return None
        return self.beam

    def shake_offset(self):
        return SHAKE[self.shake_frame] if self.shake_frame is not None else 0

    def pop_scale(self):
        return POP[self.pop_frame] if self.pop_frame is not None else 1.0
