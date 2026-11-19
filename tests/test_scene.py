"""Fishing scene: own pixel art and its behaviour (ui/scene_art.py, ui/scene_motion.py)."""

import pytest

from urban_analysis.ui import scene_art as art
from urban_analysis.ui.scene_motion import (
    CAST_FRAMES,
    CATCH_FRAMES,
    REEL_FRAMES,
    ROD_REST,
    FishingScene,
    bobber_x,
    far_x,
    step_positions,
)


def run(scene, frames):
    for _ in range(frames):
        scene.tick()


# --- art --------------------------------------------------------------------

@pytest.mark.parametrize("sprite", [
    art.pine(50, 22), art.cloud(), art.rabbit(), art.rabbit(happy=True), art.island(),
    art.bobber(), art.fish(), art.fish(False, tail_up=True), art.bubble(),
    art.caught_fish(), art.caught_fish(tail_left=True), art.sparkle(),
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
    for sprite in (art.caught_fish(), art.caught_fish(True), art.fish(color="catch")):
        assert not {c for _x, _y, c in sprite.cells} & {"accent", "accent_dark", "accent_hi"}
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

def test_rabbit_pulls_the_float_in_from_far_right():
    assert bobber_x(0, 420) == far_x(420) == 420 - art.BOBBER_RIGHT_MARGIN
    assert bobber_x(100, 420) == art.BOBBER_REST_X
    assert bobber_x(50, 420) == round((art.BOBBER_REST_X + far_x(420)) / 2)
    assert bobber_x(150, 420) == bobber_x(100, 420)
    assert bobber_x(30, 420) > bobber_x(60, 420)  # comes closer with progress


def test_loading_casts_far_out_then_moves_with_progress():
    scene = FishingScene()
    scene.start_loading()
    assert scene.phase == "cast" and scene.float_state()[2] is False  # float in the air
    run(scene, len(CAST_FRAMES))
    assert scene.phase == "loading" and scene.splash > 0
    assert scene.float_state()[0] == far_x(420)  # landed far right
    scene.set_progress(60)
    assert scene.float_state()[0] == bobber_x(60, 420)
    assert scene.line_mode() == "tight"


def test_done_always_ends_with_a_caught_fish():
    scene = FishingScene()
    scene.start_loading()
    run(scene, len(CAST_FRAMES))
    scene.set_progress(100)
    scene.finish()
    assert scene.phase == "catch" and scene.catches == 1
    seen = []
    happy = sparkle = dived_in = False
    for _ in range(CATCH_FRAMES):
        view = scene.catch_view()
        if view and view[0] not in seen:
            seen.append(view[0])
        happy |= scene.rabbit_happy()
        sparkle |= scene.sparkle()
        scene.tick()
        dived_in |= any(x == scene.release_x() for x, _left in scene.splashes)
    # fish jumps out, hangs on the line, is let go and swims away
    assert seen == ["jump", "hang", "release", "swim"]
    assert happy and sparkle
    assert dived_in  # splash where the released fish enters the water
    assert scene.phase == "idle" and scene.catch_view() is None
    assert scene.float_state()[0] == art.BOBBER_REST_X
    assert scene.rod_tip() == ROD_REST and scene.line_mode() == "slack"


def test_bite_dips_the_float_before_the_jump():
    scene = FishingScene()
    scene.start_loading()
    run(scene, len(CAST_FRAMES))
    scene.finish()
    dips = [scene.float_state()[3]]
    scene.tick()
    dips.append(scene.float_state()[3])
    assert 0 < dips[0] < dips[1]


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


def test_reduced_animations_skip_cast_and_catch_animation():
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


def test_fish_flies_a_looping_after_the_result_layers():
    from urban_analysis.ui.scene_motion import JUMP_PATH

    scene = FishingScene()
    scene.set_step(8)
    scene.celebrate()
    assert scene.jump_view() is None  # first it swims to the last step
    while scene.jump_view() is None:
        scene.tick()
    assert not scene.fish_moving()
    angles, in_air, splashes = [], [], 0
    while scene.jump_view() is not None:
        _x, _y, angle, air = scene.jump_view()
        angles.append(angle)
        in_air.append(air)
        scene.tick()
        splashes = max(splashes, len(scene.splashes))
    # full circle: nose up, upside down at the top, nose down, level again
    assert {-90, 180, 90, 0} <= set(angles)
    assert angles.index(-90) < angles.index(180) < angles.index(90) < angles.index(0)
    assert in_air[0] is False and in_air[-1] is False and any(in_air)  # out and back in
    assert splashes >= 1
    assert len(in_air) == len(JUMP_PATH)
    for _ in range(20):
        scene.tick()
    assert not scene.busy()  # back to calm swimming


def test_no_jump_with_reduced_animations():
    scene = FishingScene(animations=False)
    scene.celebrate()
    scene.tick()
    assert scene.jump_view() is None and not scene.busy()


def test_leap_fish_is_calm_and_turns_with_hard_pixels():
    fish = art.leap_fish()
    assert {c for _x, _y, c in fish.cells} <= {"catch", "catch_belly", "outline"}
    for angle in (-90, 180, 45):
        turned = art.rotate_sprite(fish, angle)
        # same colours, roughly the same number of pixels, nothing blended
        assert {c for _x, _y, c in turned.cells} <= {c for _x, _y, c in fish.cells}
        assert 0.8 < len(turned.cells) / len(fish.cells) < 1.3
    upright = art.rotate_sprite(fish, -90)
    assert upright.height > upright.width  # nose up = tall
    flipped = art.rotate_sprite(fish, 180)
    assert flipped.width >= fish.width - 1


def test_resting_scene_needs_no_event_animation():
    scene = FishingScene()
    run(scene, 5)
    assert not scene.busy()


def test_float_bobs_up_and_down_while_qgis_works():
    from urban_analysis.ui.scene_motion import LOADING_BOB

    scene = FishingScene()
    scene.start_loading()
    for _ in range(len(CAST_FRAMES)):
        scene.tick()
    assert scene.phase == "loading"
    heights = set()
    for _ in range(len(LOADING_BOB) * 2):
        scene.tick()
        heights.add(scene.float_state()[1])
    assert min(heights) < 0 < max(heights)


def test_float_stays_still_while_loading_with_reduced_animations():
    scene = FishingScene(animations=False)
    scene.start_loading()
    heights = set()
    for _ in range(20):
        scene.tick()
        heights.add(scene.float_state()[1])
    assert heights == {0}
