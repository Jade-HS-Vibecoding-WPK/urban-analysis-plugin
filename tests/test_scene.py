"""Fishing scene: own pixel art and its behaviour (ui/scene_art.py, ui/scene_motion.py)."""

import pytest

from urban_analysis.ui import scene_art as art
from urban_analysis.ui.scene_motion import (
    CAST_FRAMES,
    REEL_FRAMES,
    ROD_REST,
    SNAP_FRAMES,
    FishingScene,
    bobber_x,
    step_positions,
)


def run(scene, frames):
    for _ in range(frames):
        scene.tick()


# --- art --------------------------------------------------------------------

@pytest.mark.parametrize("sprite", [
    art.pine(50, 22), art.cloud(), art.rabbit(), art.island(), art.bobber(),
    art.fish(), art.fish(False, tail_up=True), art.bubble(),
])
def test_sprites_start_at_zero_and_use_only_scene_colours(sprite):
    xs = [x for x, _y, _c in sprite.cells]
    ys = [y for _x, y, _c in sprite.cells]
    assert min(xs) == 0 and min(ys) == 0
    assert max(xs) < sprite.width and max(ys) < sprite.height
    assert {c for _x, _y, c in sprite.cells} <= set(art.SCENE_COLORS)


def test_fish_and_bobber_are_never_red_except_the_float_top():
    for sprite in (art.fish(), art.fish(False)):
        assert {c for _x, _y, c in sprite.cells} == {"shadow"}
    colours = {c for _x, _y, c in art.bobber().cells}
    assert "accent" in colours and "cloud" in colours  # red top, white bottom


def test_rabbit_has_a_paw_for_the_rod_and_a_scarf():
    rabbit = art.rabbit()
    assert "grip" in rabbit.anchors and "head" in rabbit.anchors
    assert "accent" in {c for _x, _y, c in rabbit.cells}


def test_line_has_hard_pixels_and_connects_both_ends():
    cells = art.line_cells(0, 0, 7, -3)
    assert cells[0] == (0, 0) and cells[-1] == (7, -3)
    for (x0, y0), (x1, y1) in zip(cells, cells[1:]):
        assert abs(x1 - x0) <= 1 and abs(y1 - y0) <= 1


# --- float follows the REAL progress ---------------------------------------

def test_float_follows_progress_from_the_rabbit_to_the_right():
    assert bobber_x(0, 420) == art.BOBBER_REST_X
    assert bobber_x(100, 420) == 420 - art.BOBBER_RIGHT_MARGIN
    assert bobber_x(50, 420) == round((art.BOBBER_REST_X + 390) / 2)
    assert bobber_x(150, 420) == bobber_x(100, 420)


def test_loading_casts_first_then_moves_with_progress():
    scene = FishingScene()
    scene.start_loading()
    assert scene.phase == "cast" and scene.float_state()[2] is False  # float in the air
    run(scene, len(CAST_FRAMES))
    assert scene.phase == "loading" and scene.splash > 0
    scene.set_progress(60)
    assert scene.float_state()[0] == bobber_x(60, 420)
    assert scene.line_mode() == "tight"


def test_done_breaks_the_line_and_the_rabbit_casts_again():
    scene = FishingScene()
    scene.start_loading()
    run(scene, len(CAST_FRAMES))
    scene.set_progress(100)
    scene.finish()
    assert scene.phase == "snap" and scene.line_mode() == "broken"
    sunk = [scene.float_state()[3]]
    run(scene, 1)
    sunk.append(scene.float_state()[3])
    assert sunk[1] > sunk[0]  # float sinks
    run(scene, SNAP_FRAMES - 1)
    assert scene.phase == "cast"  # new cast
    run(scene, len(CAST_FRAMES))
    assert scene.phase == "idle"
    assert scene.float_state()[0] == art.BOBBER_REST_X
    assert scene.rod_tip() == ROD_REST and scene.line_mode() == "slack"


def test_error_twitches_shows_bubble_and_reels_in():
    scene = FishingScene()
    scene.start_loading()
    run(scene, len(CAST_FRAMES))
    scene.set_progress(40)
    scene.fail()
    assert scene.bubble > 0 and scene.twitch > 0 and scene.phase == "reel"
    run(scene, REEL_FRAMES)
    assert scene.phase == "idle" and scene.float_state()[0] == art.BOBBER_REST_X
    assert scene.bubble > 0  # bubble stays a while longer
    run(scene, 40)
    assert scene.bubble == 0 and not scene.busy()


def test_cancel_returns_to_rest_at_once():
    scene = FishingScene()
    scene.start_loading()
    scene.cancel()
    assert scene.phase == "idle" and scene.float_state()[0] == art.BOBBER_REST_X


def test_reduced_animations_skip_cast_and_snap():
    scene = FishingScene(animations=False)
    scene.start_loading()
    assert scene.phase == "loading"
    scene.set_progress(100)
    scene.finish()
    assert scene.phase == "idle" and not scene.busy()


# --- step fish ---------------------------------------------------------------

def test_steps_are_spread_over_the_width():
    xs = step_positions(420, 9)
    assert len(xs) == 9 and xs[0] == art.STEP_LEFT and xs[-1] == 420 - art.STEP_RIGHT_MARGIN
    assert xs == sorted(xs)


def test_fish_swims_in_pixel_steps_to_the_current_step():
    scene = FishingScene()
    scene.set_step(4)
    target = step_positions(420, 9)[4]
    positions = []
    while scene.fish_moving():
        scene.tick()
        positions.append(scene.fish_x)
    assert positions[-1] == target
    assert all(b - a <= 3 for a, b in zip([step_positions(420, 9)[0]] + positions, positions))
    assert scene.fish_state()[1] is True  # facing right
    scene.set_step(1)
    scene.tick()
    assert scene.fish_state()[1] is False  # turns around when swimming back


def test_all_done_puts_the_fish_on_the_last_step():
    scene = FishingScene(animations=False)
    scene.set_step(9)
    assert scene.fish_x == step_positions(420, 9)[-1]


def test_resting_scene_needs_no_event_animation():
    scene = FishingScene()
    run(scene, 5)
    assert not scene.busy()
