"""QGIS-free behaviour of the fishing scene (tested with plain pytest).

Phases of the rabbit's line:
    idle     float rests in front of the rabbit, bobs now and then
    cast     rod swings back and forward; the long cast lands far right
    loading  the rabbit pulls the float in: it follows the REAL progress
             from the right (0 %) to the rabbit (100 %)
    catch    at 100 % a fish bites, jumps out and hangs wriggling on the
             line; the rabbit is happy (ears wiggle, a twinkle), then it
             lets the fish go: it glides back into the water, splashes and
             swims away; the float rests again
    reel     after an error the float is pulled back without a catch
The rabbit never loses a fish – it only releases it on purpose.

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

# Catch, frame by frame (about 1.9 s)
CATCH_DIP = (3, 6)         # float dips twice (px under water)
CATCH_JUMP = 2             # first frame of the jump (float disappears)
CATCH_HANG = 4             # from here the fish hangs on the line
CATCH_SPARKLE = (5, 10)    # twinkle above the rabbit (inclusive)
CATCH_RELEASE = 12         # the rabbit lets the fish go: it glides back ...
CATCH_SWIM = 15            # ... splashes in and swims away under water
CATCH_FRAMES = 19          # then the float rests again
RELEASE_DX = 16            # the fish enters the water right of the float
SWIM_DISTANCE = 28         # px the released fish swims before it is gone

REEL_FRAMES = 4
SPLASH_FRAMES = 3          # ripples after the float lands
TWITCH = (2, -1, 1)        # float twitches (px) when something fails
BUBBLE_FRAMES = 30         # "…" bubble stays about 3 s
IDLE_BOB_EVERY = 30        # float bobs 1 px every ~3 s
# While QGIS works the float bobs up and down steadily (px per 2 frames).
LOADING_BOB = (0, 1, 2, 1, 0, -1)
LOADING_BOB_FRAMES = 2
CLOUD_STEP_EVERY = 8       # clouds move 1 px every 0.8 s
WATER_STEP_EVERY = 5       # light lines on the water drift 1 px every 0.5 s
FISH_SPEED = 3             # px per frame when the step fish swims
FISH_TAIL_EVERY = 4        # tail flaps every 0.4 s
WAKE_LINES = ((-10, 1, 7), (-20, 4, 6), (-30, 0, 5), (-40, 3, 4), (-48, 1, 3))

# Celebration jump of the step fish after the result layers were created:
# a looping.  Per frame: (x offset, centre y, angle).  Angle = turn of the
# side view on screen (0 = nose right, -90 = nose up, 180 = upside down
# heading left, 90 = nose down).  The fish shoots out nose first, flies a
# full circle (upside down at the top), comes out level at the bottom of
# the loop and dives back in.  No roll around its long axis.
_W = art.WATER_Y
_UNDER = art.FISH_Y + 3
JUMP_PATH = (
    (0, _UNDER - 8, -45),
    (4, _W + 6, -45),
    (8, _W - 8, -60),
    (12, _W - 20, -90),
    (10, _W - 31, -135),
    (2, _W - 35, 180),
    (-6, _W - 31, 135),
    (-9, _W - 21, 90),
    (-5, _W - 11, 45),
    (2, _W - 8, 0),
    (9, _W - 6, 30),
    (14, _W + 6, 45),
    (18, _UNDER - 6, 30),
    (20, _UNDER, 0),
)
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
        self.water_offset = 0    # drift of the light lines (stays 0 without animations)
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
        if self.animations and self.ticks % WATER_STEP_EVERY == 0:
            self.water_offset += 1
        self._move_fish()
        self._advance_jump()
        self.frame += 1
        if self.phase == "cast" and self.frame >= len(CAST_FRAMES):
            self.splash = SPLASH_FRAMES
            self._enter(self.after_cast)
            self.float_x = bobber_x(self.progress, self.width)
        elif self.phase == "catch" and self.frame == CATCH_SWIM:
            self.splashes.append([self.release_x(), SPLASH_LIFE])  # fish dives in
        elif self.phase == "catch" and self.frame >= CATCH_FRAMES:
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
            self.fish_x += JUMP_PATH[-1][0]  # lands a bit further on, then swims back
            return
        if before != self._in_air(self.jump_frame):  # leaves or enters the water
            self.splashes.append([self.jump_view()[0], SPLASH_LIFE])

    @staticmethod
    def _in_air(frame):
        return JUMP_PATH[frame][1] < art.WATER_Y

    def jump_view(self):
        """None or (centre x, centre y, angle, in_air) of the looping fish."""
        if self.jump_frame is None:
            return None
        dx, y, angle = JUMP_PATH[self.jump_frame]
        return round(self.fish_x) + dx, y, angle, y < art.WATER_Y

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
            if CATCH_HANG <= self.frame < CATCH_RELEASE:
                return ROD_BENT
        return ROD_REST

    def float_state(self):
        """(x, dy, visible, sunk_px) of the float; dy = small vertical offset."""
        if self.phase == "cast":
            return self.float_x, 0, False, 0
        if self.phase == "catch":
            if self.frame < CATCH_JUMP:
                return self.float_x, 0, True, CATCH_DIP[self.frame]
            if self.frame < CATCH_RELEASE:
                return self.float_x, 0, False, 0
        x = self.float_x
        if self.phase == "reel":
            t = min(self.frame / REEL_FRAMES, 1)
            x = round(self.reel_from + (art.BOBBER_REST_X - self.reel_from) * t)
        dy = 0
        if self.twitch > 0:
            dy = TWITCH[len(TWITCH) - self.twitch]
        elif self.phase == "loading" and self.animations:
            dy = LOADING_BOB[(self.ticks // LOADING_BOB_FRAMES) % len(LOADING_BOB)]
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
            if self.frame < CATCH_RELEASE:
                return "fish"
        if self.phase in ("loading", "reel"):
            return "tight"
        return "slack"

    def release_x(self):
        """Where the released fish dives back into the water."""
        return art.BOBBER_REST_X + RELEASE_DX

    def catch_view(self):
        """Where the caught fish is: None, ('jump', t), ('hang', tail_left),
        ('release', t) or ('swim', t) with t running 0..1."""
        if self.phase != "catch" or not CATCH_JUMP <= self.frame < CATCH_FRAMES:
            return None
        if self.frame < CATCH_HANG:
            return ("jump", (self.frame - CATCH_JUMP + 1) / (CATCH_HANG - CATCH_JUMP + 1))
        if self.frame < CATCH_RELEASE:
            return ("hang", self.frame % 2 == 0)
        if self.frame < CATCH_SWIM:
            return ("release", (self.frame - CATCH_RELEASE + 1) / (CATCH_SWIM - CATCH_RELEASE + 1))
        return ("swim", (self.frame - CATCH_SWIM + 1) / (CATCH_FRAMES - CATCH_SWIM))

    def rabbit_happy(self):
        """Second rabbit frame (ear tipped) every other frame while it is happy."""
        return self.phase == "catch" and CATCH_HANG <= self.frame < CATCH_SWIM \
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
