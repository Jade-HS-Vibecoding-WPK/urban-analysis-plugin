"""QGIS-free logic of the pixel widgets (ui/pixel_motion.py)."""

import random

import pytest

from urban_analysis.ui import pixel_motion as pm


def test_button_state_priorities():
    assert pm.button_state(enabled=False, down=True, hover=True) == "disabled"
    assert pm.button_state(enabled=True, down=True, hover=True) == "pressed"
    assert pm.button_state(enabled=True, down=False, hover=True) == "hover"
    assert pm.button_state(enabled=True, down=False, hover=False) == "normal"


@pytest.mark.parametrize("state", ["normal", "hover", "pressed"])
def test_shadow_bottom_stays_put_so_the_face_moves_onto_it(state):
    top, face_height, shadow = pm.face_geometry(state, 40)
    assert top + face_height + shadow == 40


def test_states_match_the_design():
    assert pm.face_geometry("normal", 40)[2] == 3  # 3 px above its shadow
    hover, normal = pm.face_geometry("hover", 40), pm.face_geometry("normal", 40)
    assert hover[0] == normal[0] - 1 and hover[2] == 4  # 1 px higher, shadow 4
    assert pm.face_geometry("pressed", 40)[2] == 0  # no shadow when pressed
    assert pm.face_geometry("disabled", 40)[2] == 0


def test_burst_has_5_to_8_square_particles_that_end_in_about_200_ms():
    for seed in range(20):
        particles = pm.spawn_burst(50, 20, random.Random(seed))
        assert 5 <= len(particles) <= 8
        assert all(p[4] in pm.BURST_SIZES for p in particles)
        assert {p[5] for p in particles} <= {"accent", "cloud"}
        frames = 0
        while particles:
            particles = pm.step_burst(particles)
            frames += 1
        assert pm.BURST_FRAMES[0] - 1 <= frames <= pm.BURST_FRAMES[1]
    assert pm.BURST_FRAMES[1] * pm.FRAME_MS <= 250


def test_particles_fly_outwards():
    particles = pm.spawn_burst(50, 20, random.Random(3))
    later = pm.step_burst(particles)
    for before, after in zip(particles, later):
        assert abs(after[0] - 50) + abs(after[1] - 20) > 0


def test_colour_helpers():
    assert pm.lighten("#000000", 1) == "#FFFFFF"
    assert pm.lighten("#E8655A", 0) == "#E8655A"
    grey = pm.desaturate("#E8655A", 1)
    assert grey[1:3] == grey[3:5] == grey[5:7]


def test_stepped_corners_leave_the_corner_block_empty():
    rects = pm.stair_rects(0, 0, 20, 10, 2)
    covered = {(x, y) for rx, ry, w, h in rects for x in range(rx, rx + w) for y in range(ry, ry + h)}
    assert (0, 0) not in covered and (19, 9) not in covered
    assert (2, 0) in covered and (0, 2) in covered and (10, 5) in covered
