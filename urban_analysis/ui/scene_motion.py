"""QGIS-free behaviour of the fishing scene (tested with plain pytest).

Phases of the rabbit's line:
    idle     float rests in front of the rabbit, bobs now and then
    cast     rod swings back and forward; the long cast lands far right
    loading  the rabbit pulls the float in: it follows the REAL progress
             from the right (0 %) to the rabbit (100 %)
    catch    at 100 % a fish bites, jumps out and hangs wriggling on the
             line; the rabbit is happy (ears wiggle, a twinkle), then the
             fish is put away and the float rests again
    reel     after an error the float is pulled back without a catch
The rabbit never loses a fish.

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
ROD_LIFT = (31, -25)       # rod pulled up when the fish jumps
ROD_BENT = (27, -15)       # rod bends under the weight of the fish

# Catch, frame by frame (about 1.4 s)
CATCH_DIP = (3, 6)         # float dips twice (px under water)
CATCH_JUMP = 2             # first frame of the jump (float disappears)
CATCH_HANG = 4             # from here the fish hangs on the line
CATCH_SPARKLE = (5, 10)    # twinkle above the rabbit (inclusive)
CATCH_FRAMES = 14          # last two frames: fish put away, float rests

REEL_FRAMES = 4
SPLASH_FRAMES = 3          # ripples after the float lands
TWITCH = (2, -1, 1)        # float twitches (px) when something fails
BUBBLE_FRAMES = 30         # "…" bubble stays about 3 s
IDLE_BOB_EVERY = 30        # float bobs 1 px every ~3 s
CLOUD_STEP_EVERY = 8       # clouds move 1 px every 0.8 s
FISH_SPEED = 3             # px per frame when the step fish swims
FISH_TAIL_EVERY = 4        # tail flaps every 0.4 s
WAKE_LINES = ((-10, 1, 7), (-20, 4, 6), (-30, 0, 5), (-40, 3, 4), (-48, 1, 3))

# Celebration jump of the step fish after the result layers were created:
# per frame (top y of the fish, pose).  It leaves the water, flips over in
# the air (shows its light belly) and dives back in.
_W = art.WATER_Y
JUMP_PATH = (
    (art.FISH_Y - 12, "right"), (_W + 6, "right"), (_W - 10, "right"), (_W - 20, "belly"),
    (_W - 24, "left"), (_W - 20, "belly"), (_W - 10, "right"), (_W + 6, "right"),
    (art.FISH_Y - 12, "right"), (art.FISH_Y, "right"),
)
JUMP_STEP_X = 2            # px forward per frame
SPLASH_LIFE = 3            # frames a splash stays visible


def step_positions(width, total):
    """x positions of the steps along the bottom (left to right)."""
    left, right = art.STEP_LEFT, width - art.STEP_RIGHT_MARGIN
    if total <= 1:
        return [left]
    return [round(left + (right - left) * i / (total - 1)) for i in range(total)]


def far_x(width):
    """Where the long cast lands (right side of the water)."""
    return max(art.BOBBER_REST_X, width - art.BOBBER_RIGHT_MARGIN)


def bobber_x(progress, width):
    """Float position for a real progress value 0-100: the rabbit pulls the
    float in from far right (0 %) to the front of the rabbit (100 %)."""
    start, end = far_x(width), art.BOBBER_REST_X
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
        self.catches = 0
        self.ticks = 0
        self.cloud_offset = 0
        self.step = 0
        self.fish_x = float(step_positions(width, total_steps)[0])
        self.fish_facing_right = True
        self.jump_pending = False
        self.jump_frame = None   # index in JUMP_PATH while the fish jumps
        self.splashes = []       # [x, frames left] on the water line

    # --- commands from the panel -------------------------------------------

    def resize(self, width):
        self.width = width
        if self.phase == "loading":
            self.float_x = bobber_x(self.progress, width)
        if not self.animations:
            self.fish_x = float(self.fish_target())

    def set_step(self, index):
        """Current step (0-based); index >= total means 'all done' (last step)."""
        self.step = max(0, min(index, self.total_steps - 1))
        if not self.animations:
            self.fish_x = float(self.fish_target())

    def start_loading(self):
        """Rabbit casts far out; then pulls the float in with the progress."""
        self.progress = 0
        self.bubble = 0
        self.after_cast = "loading"
        if self.animations:
            self._enter("cast")
        else:
            self._enter("loading")
            self.float_x = bobber_x(0, self.width)

    def set_progress(self, percent):
        self.progress = min(max(float(percent), 0.0), 100.0)
        if self.phase == "loading":
            self.float_x = bobber_x(self.progress, self.width)

    def finish(self):
        """Loading done: a fish bites and is caught."""
        if self.phase not in ("loading", "cast"):
            return
        self.progress = 100
        self.float_x = art.BOBBER_REST_X
        self.catches += 1
        self._enter("catch" if self.animations else "idle")

    def fail(self):
        """Something went wrong: float twitches, '…' bubble, line is reeled in."""
        self.twitch = len(TWITCH) if self.animations else 0
        self.bubble = BUBBLE_FRAMES
        if self.phase in ("loading", "cast"):
            self.reel_from = self.float_x if self.phase == "loading" else far_x(self.width)
            self._enter("reel" if self.animations else "idle")
            if not self.animations:
                self.float_x = art.BOBBER_REST_X

    def celebrate(self):
        """Result layers created: the step fish jumps once with a flip
        (as soon as it has reached its step).  Skipped with reduced animations."""
        if self.animations:
            self.jump_pending = True

    def cancel(self):
        """Back to rest at once (reset, aborted loading)."""
        self._enter("idle")
        self.float_x = art.BOBBER_REST_X
        self.progress = 0
        self.twitch = 0
        self.bubble = 0
        self.jump_pending = False
        self.jump_frame = None
        self.splashes = []

    # --- animation ---------------------------------------------------------

    def _enter(self, phase):
        self.phase = phase
        self.frame = 0

    def fish_target(self):
        return step_positions(self.width, self.total_steps)[self.step]

    def fish_moving(self):
        return abs(self.fish_target() - self.fish_x) >= 1

    def busy(self):
        """True while a short, event-driven animation still runs."""
        return (self.phase in ("cast", "catch", "reel") or self.splash > 0
                or self.twitch > 0 or self.bubble > 0 or self.fish_moving()
                or self.jump_pending or self.jump_frame is not None or bool(self.splashes))

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
        self._advance_jump()
        self.frame += 1
        if self.phase == "cast" and self.frame >= len(CAST_FRAMES):
            self.splash = SPLASH_FRAMES
            self._enter(self.after_cast)
            self.float_x = bobber_x(self.progress, self.width)
        elif self.phase == "catch" and self.frame >= CATCH_FRAMES:
            self.splash = SPLASH_FRAMES
            self._enter("idle")
        elif self.phase == "reel" and self.frame >= REEL_FRAMES:
            self.float_x = art.BOBBER_REST_X
            self._enter("idle")

    def _advance_jump(self):
        self.splashes = [[x, left - 1] for x, left in self.splashes if left > 1]
        if self.jump_frame is None:
            if self.jump_pending and not self.fish_moving():
                self.jump_pending = False
                self.jump_frame = 0
            return
        before = self._in_air(self.jump_frame)
        self.jump_frame += 1
        if self.jump_frame >= len(JUMP_PATH):
            self.jump_frame = None
            return
        if before != self._in_air(self.jump_frame):  # leaves or enters the water
            self.splashes.append([self.jump_view()[0], SPLASH_LIFE])

    @staticmethod
    def _in_air(frame):
        return JUMP_PATH[frame][0] < art.WATER_Y

    def jump_view(self):
        """None or (centre x, top y, pose, in_air) of the jumping fish."""
        if self.jump_frame is None:
            return None
        y, pose = JUMP_PATH[self.jump_frame]
        x = round(self.fish_x) + JUMP_STEP_X * self.jump_frame
        return x, y, pose, y < art.WATER_Y

    def _move_fish(self):
        if self.jump_frame is not None:
            return  # the fish is in the middle of its jump
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
        if self.phase == "catch":
            if CATCH_JUMP <= self.frame < CATCH_HANG:
                return ROD_LIFT
            if CATCH_HANG <= self.frame < CATCH_FRAMES - 2:
                return ROD_BENT
        return ROD_REST

    def float_state(self):
        """(x, dy, visible, sunk_px) of the float; dy = small vertical offset."""
        if self.phase == "cast":
            return self.float_x, 0, False, 0
        if self.phase == "catch":
            if self.frame < CATCH_JUMP:
                return self.float_x, 0, True, CATCH_DIP[self.frame]
            if self.frame < CATCH_FRAMES - 2:
                return self.float_x, 0, False, 0
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
        """'slack' (resting), 'tight' (loading, reeling, bite), 'fish' (line
        ends at the caught fish) or None (line in the air while casting)."""
        if self.phase == "cast":
            return None
        if self.phase == "catch":
            if self.frame < CATCH_JUMP:
                return "tight"
            if self.frame < CATCH_FRAMES - 2:
                return "fish"
        if self.phase in ("loading", "reel"):
            return "tight"
        return "slack"

    def catch_view(self):
        """Where the caught fish is: None, ('jump', t 0..1) or ('hang', tail_left)."""
        if self.phase != "catch" or not CATCH_JUMP <= self.frame < CATCH_FRAMES - 2:
            return None
        if self.frame < CATCH_HANG:
            return ("jump", (self.frame - CATCH_JUMP + 1) / (CATCH_HANG - CATCH_JUMP + 1))
        return ("hang", self.frame % 2 == 0)

    def rabbit_happy(self):
        """Second rabbit frame (ear tipped) every other frame while it is happy."""
        return self.phase == "catch" and CATCH_HANG <= self.frame < CATCH_FRAMES - 2 \
            and self.frame % 2 == 1

    def sparkle(self):
        return self.phase == "catch" and CATCH_SPARKLE[0] <= self.frame <= CATCH_SPARKLE[1]

    def fish_state(self):
        """(x, facing_right, tail_up, wake) for the step fish."""
        tail_up = self.animations and (self.ticks // FISH_TAIL_EVERY) % 2 == 1
        wake = WAKE_LINES if self.fish_moving() else WAKE_LINES[:2]
        if not self.fish_facing_right:
            wake = tuple((-dx + 14, dy, w) for dx, dy, w in wake)
        return round(self.fish_x), self.fish_facing_right, tail_up, wake
