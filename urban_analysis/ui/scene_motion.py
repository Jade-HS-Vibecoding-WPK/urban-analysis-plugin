"""QGIS-free behaviour of the fishing scene (tested with plain pytest).

Phases of the rabbit's line:
    idle     float rests in front of the rabbit, bobs now and then
    cast     rod swings back and forward, the float lands (then -> next phase)
    loading  float follows the REAL progress from left to right
    snap     line breaks: float sinks, loose end whips back to the rod
    reel     after an error the float is pulled back (no sinking)
After snap/reel the rabbit casts again and the scene returns to idle.

The step fish swims along the bottom to the current step (1 of 9 ... 9 of 9),
in pixel steps, with light current lines behind it.

Everything advances in discrete frames (``tick``); nothing here waits or
blocks the work of the plugin.
"""

from . import scene_art as art

FRAME_MS = 100

# Rod tip relative to the paw, per frame of the cast (back over the shoulder,
# then forward).  The last entry is the resting position.
ROD_REST = (30, -20)
CAST_FRAMES = ((22, -30), (6, -34), (-8, -28), (8, -34), (26, -28), (33, -17), ROD_REST)
SNAP_FRAMES = 4            # float sinks and the loose end flies back
SNAP_ROD = ((30, -24), (31, -18), (30, -21), ROD_REST)
REEL_FRAMES = 4
SPLASH_FRAMES = 3          # ripples after the float lands
TWITCH = (2, -1, 1)        # float twitches (px) when something fails
BUBBLE_FRAMES = 30         # "…" bubble stays about 3 s
IDLE_BOB_EVERY = 30        # float bobs 1 px every ~3 s
CLOUD_STEP_EVERY = 8       # clouds move 1 px every 0.8 s
FISH_SPEED = 3             # px per frame when the step fish swims
FISH_TAIL_EVERY = 4        # tail flaps every 0.4 s
WAKE_LINES = ((-10, 1, 7), (-20, 4, 6), (-30, 0, 5), (-40, 3, 4), (-48, 1, 3))


def step_positions(width, total):
    """x positions of the steps along the bottom (left to right)."""
    left, right = art.STEP_LEFT, width - art.STEP_RIGHT_MARGIN
    if total <= 1:
        return [left]
    return [round(left + (right - left) * i / (total - 1)) for i in range(total)]


def bobber_x(progress, width):
    """Float position for a real progress value 0-100."""
    start = art.BOBBER_REST_X
    end = max(start, width - art.BOBBER_RIGHT_MARGIN)
    fraction = min(max(progress, 0), 100) / 100
    return round(start + (end - start) * fraction)


class FishingScene:
    """State of the scene; the widget asks it what to draw."""

    def __init__(self, width=420, total_steps=9, animations=True):
        self.width = width
        self.total_steps = total_steps
        self.animations = animations
        self.phase = "idle"
        self.frame = 0
        self.after_cast = "idle"
        self.progress = 0
        self.float_x = art.BOBBER_REST_X
        self.reel_from = art.BOBBER_REST_X
        self.splash = 0
        self.twitch = 0
        self.bubble = 0
        self.ticks = 0
        self.cloud_offset = 0
        self.step = 0
        self.fish_x = float(step_positions(width, total_steps)[0])
        self.fish_facing_right = True

    # --- commands from the panel -------------------------------------------

    def resize(self, width):
        self.width = width
        if self.phase == "loading":
            self.float_x = bobber_x(self.progress, width)
        if not self.animations:
            self.fish_x = float(self.fish_target())

    def set_step(self, index):
        """Current step (0-based); index == total means 'all done' (far right)."""
        self.step = max(0, min(index, self.total_steps - 1))
        if not self.animations:
            self.fish_x = float(self.fish_target())

    def start_loading(self):
        """Rabbit casts the line; then the float follows the progress."""
        self.progress = 0
        self.bubble = 0
        self._cast(then="loading")

    def set_progress(self, percent):
        self.progress = min(max(float(percent), 0.0), 100.0)
        if self.phase == "loading":
            self.float_x = bobber_x(self.progress, self.width)

    def finish(self):
        """Loading done: the line breaks, flies back, rabbit casts again."""
        if self.phase in ("loading", "cast"):
            self.float_x = bobber_x(100 if self.phase == "loading" else self.progress, self.width)
            self._enter("snap" if self.animations else "idle")
            if not self.animations:
                self.float_x = art.BOBBER_REST_X

    def fail(self):
        """Something went wrong: float twitches, '…' bubble, line is reeled in."""
        self.twitch = len(TWITCH) if self.animations else 0
        self.bubble = BUBBLE_FRAMES
        if self.phase in ("loading", "cast", "snap"):
            self.reel_from = self.float_x if self.phase != "cast" else art.BOBBER_REST_X
            self._enter("reel" if self.animations else "idle")
            if not self.animations:
                self.float_x = art.BOBBER_REST_X

    def cancel(self):
        """Back to rest at once (reset, aborted loading)."""
        self._enter("idle")
        self.float_x = art.BOBBER_REST_X
        self.progress = 0
        self.twitch = 0
        self.bubble = 0

    # --- animation ---------------------------------------------------------

    def _cast(self, then):
        self.after_cast = then
        if self.animations:
            self._enter("cast")
        else:
            self._enter(then)
            self.float_x = bobber_x(self.progress, self.width) if then == "loading" else art.BOBBER_REST_X

    def _enter(self, phase):
        self.phase = phase
        self.frame = 0

    def fish_target(self):
        return step_positions(self.width, self.total_steps)[self.step]

    def fish_moving(self):
        return abs(self.fish_target() - self.fish_x) >= 1

    def busy(self):
        """True while a short, event-driven animation still runs."""
        return (self.phase in ("cast", "snap", "reel") or self.splash > 0
                or self.twitch > 0 or self.bubble > 0 or self.fish_moving())

    def tick(self):
        """Advance one frame (about 100 ms)."""
        self.ticks += 1
        if self.twitch > 0:
            self.twitch -= 1
        if self.bubble > 0:
            self.bubble -= 1
        if self.splash > 0:
            self.splash -= 1
        if self.animations and self.ticks % CLOUD_STEP_EVERY == 0:
            self.cloud_offset += 1
        self._move_fish()
        self.frame += 1
        if self.phase == "cast" and self.frame >= len(CAST_FRAMES):
            self.splash = SPLASH_FRAMES
            self._enter(self.after_cast)
            self.float_x = (bobber_x(self.progress, self.width) if self.phase == "loading"
                            else art.BOBBER_REST_X)
        elif self.phase == "snap" and self.frame >= SNAP_FRAMES:
            self.progress = 0
            self._cast(then="idle")
        elif self.phase == "reel" and self.frame >= REEL_FRAMES:
            self.float_x = art.BOBBER_REST_X
            self._enter("idle")

    def _move_fish(self):
        target = self.fish_target()
        if not self.animations:
            self.fish_x = float(target)
            return
        distance = target - self.fish_x
        if abs(distance) < 1:
            self.fish_x = float(target)
            return
        self.fish_facing_right = distance > 0
        self.fish_x += max(-FISH_SPEED, min(FISH_SPEED, distance))

    # --- what to draw ------------------------------------------------------

    def rod_tip(self):
        """Rod tip relative to the paw."""
        if self.phase == "cast":
            return CAST_FRAMES[min(self.frame, len(CAST_FRAMES) - 1)]
        if self.phase == "snap":
            return SNAP_ROD[min(self.frame, len(SNAP_ROD) - 1)]
        return ROD_REST

    def float_state(self):
        """(x, dy, visible, sunk_px) of the float; dy = small vertical offset."""
        if self.phase == "cast":
            return self.float_x, 0, False, 0
        if self.phase == "snap":
            return self.float_x, 0, True, min(self.frame * 3, 9)
        x = self.float_x
        if self.phase == "reel":
            t = min(self.frame / REEL_FRAMES, 1)
            x = round(self.reel_from + (art.BOBBER_REST_X - self.reel_from) * t)
        dy = 0
        if self.twitch > 0:
            dy = TWITCH[len(TWITCH) - self.twitch]
        elif self.phase == "idle" and self.animations and self.ticks % IDLE_BOB_EVERY in (1, 2):
            dy = 1
        return x, dy, True, 0

    def line_mode(self):
        """'slack' (resting), 'tight' (loading, reeling), 'broken' (snap) or None."""
        if self.phase == "cast":
            return None
        if self.phase == "snap":
            return "broken"
        if self.phase in ("loading", "reel"):
            return "tight"
        return "slack"

    def broken_end(self, tip, float_point):
        """Loose line end while it flies back to the rod tip (snap phase)."""
        t = min((self.frame + 1) / SNAP_FRAMES, 1)
        return (round(float_point[0] + (tip[0] - float_point[0]) * t),
                round(float_point[1] + (tip[1] - float_point[1]) * t))

    def fish_state(self):
        """(x, facing_right, tail_up, wake) for the step fish."""
        tail_up = self.animations and (self.ticks // FISH_TAIL_EVERY) % 2 == 1
        wake = WAKE_LINES if self.fish_moving() else WAKE_LINES[:2]
        if not self.fish_facing_right:
            wake = tuple((-dx + 14, dy, w) for dx, dy, w in wake)
        return round(self.fish_x), self.fish_facing_right, tail_up, wake
