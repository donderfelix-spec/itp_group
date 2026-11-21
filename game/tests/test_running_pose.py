"""Regression checks for the requested mascot walk cycles.

Each leg stays attached to its hip, arms oppose the legs, mirrored poses agree,
and small strides settle into the standing pose without a discontinuity.
"""
import json
import math
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest
from server import protocol

NODE = shutil.which("node")
TESTS = Path(__file__).resolve().parent
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")
CHARACTERS = list(protocol.CHARACTERS)


@lru_cache(maxsize=None)
def draw(phase, stride=1, mirrored=False, facing=None, time=0):
    pose = {"mirrored": mirrored, "walkPhase": phase, "stride": stride}
    if facing is not None:
        pose["animation"] = {"facing": facing, "time": time}
    result = subprocess.run([NODE, str(TESTS / "running_pose_in_node.js")],
                            input=json.dumps([pose]), text=True, capture_output=True,
                            timeout=60, check=True)
    return {name: drawings[0] for name, drawings in json.loads(result.stdout).items()}


def legs(parts):
    return [d for d in parts if d["op"] == "fill"
            and d["local"] == pytest.approx([-5, 0, 5, 14], abs=0.01)]


def arms(parts):
    return [d for d in parts if d["op"] == "fill"
            and d["local"] == pytest.approx([-4.5, 0, 4.5, 22], abs=0.01)]


def relative_origin(part, torso):
    a, b, c, d, e, f = torso["matrix"]
    x = part["matrix"][4] - e
    y = part["matrix"][5] - f
    determinant = a * d - b * c
    return ((d * x - c * y) / determinant, (-b * x + a * y) / determinant)


def torso_of(parts):
    return next(d for d in parts if d["op"] == "fill"
                and 48 <= d["local"][1] <= 52 and d["local"][3] - d["local"][1] > 25)


def angle(part):
    return math.atan2(part["matrix"][1], part["matrix"][0])


@pytest.mark.parametrize("character", CHARACTERS)
@pytest.mark.parametrize("mirrored", [False, True])
def test_both_legs_and_arms_remain_attached_and_swing_in_opposite_directions(character, mirrored):
    for phase in [0, 0.125, 0.25, 0.375, 0.5, 0.75]:
        parts = draw(phase, mirrored=mirrored)[character]
        feet, hands = legs(parts), arms(parts)
        assert len(feet) == len(hands) == 2
        torso = torso_of(parts)
        assert relative_origin(feet[0], torso) == pytest.approx((-10, 77))
        assert relative_origin(feet[1], torso) == pytest.approx((10, 77))
        assert relative_origin(hands[0], torso) == pytest.approx((-23, 55))
        assert relative_origin(hands[1], torso) == pytest.approx((23, 55))
        # Hip anchors stay 20 design units apart, shoulders 46 units apart.
        assert math.dist(feet[0]["matrix"][4:], feet[1]["matrix"][4:]) == pytest.approx(20 * 112 / 104)
        assert math.dist(hands[0]["matrix"][4:], hands[1]["matrix"][4:]) == pytest.approx(46 * 112 / 104)
        assert angle(feet[0]) + angle(feet[1]) == pytest.approx(angle(hands[0]) + angle(hands[1]))
        assert (angle(feet[0]) - angle(feet[1])) * (angle(hands[0]) - angle(hands[1])) <= 1e-8


@pytest.mark.parametrize("character", CHARACTERS)
def test_the_two_halves_of_the_cycle_reverse_the_leg_swing(character):
    first = legs(draw(0.25)[character])
    second = legs(draw(0.75)[character])
    assert angle(first[0]) - angle(first[1]) == pytest.approx(-(angle(second[0]) - angle(second[1])))
    assert abs(angle(first[0]) - angle(first[1])) > 0.1


def test_the_characters_have_individual_walk_amplitudes():
    amplitudes = [round(angle(legs(draw(0.25)[c])[0]) - angle(legs(draw(0.25)[c])[1]), 3)
                  for c in CHARACTERS]
    assert len(set(amplitudes)) >= 6


@pytest.mark.parametrize("character", CHARACTERS)
@pytest.mark.parametrize("mirrored", [False, True])
def test_zero_stride_is_the_standing_pose_at_every_phase(character, mirrored):
    standing = draw(None, 0, mirrored)[character]
    for phase in [0, 0.25, 0.5, 0.75, 1]:
        assert draw(phase, 0, mirrored)[character] == standing


@pytest.mark.parametrize("character", CHARACTERS)
def test_small_steps_settle_continuously_and_the_cycle_has_no_seam(character):
    standing = draw(None, 0)[character]
    tiny = draw(0.25, 0.0001)[character]
    assert len(standing) == len(tiny)
    for a, b in zip(standing, tiny):
        assert a["matrix"] == pytest.approx(b["matrix"], abs=0.005)
    for a, b in zip(draw(0)[character], draw(1)[character]):
        assert a["matrix"] == pytest.approx(b["matrix"], abs=1e-8)


@pytest.mark.parametrize("character", CHARACTERS)
def test_mirrored_running_keeps_the_same_local_motion(character):
    for a, b in zip(draw(0.25)[character], draw(0.25, mirrored=True)[character]):
        assert a["local"] == pytest.approx(b["local"], abs=1e-8)
        assert a["matrix"] == pytest.approx(b["matrix"], abs=1e-8)


def eye_boxes(parts):
    return [d for d in parts if d["op"] == "fill" and d["colour"] == "#20212A"
            and abs(d["local"][2] - d["local"][0] - 8) < 0.01
            and d["local"][1] < 45 and d["local"][3] < 45]


@pytest.mark.parametrize("character", CHARACTERS)
def test_front_has_two_eyes_but_rear_has_a_backpack_and_no_face(character):
    front = draw(None, facing="front")[character]
    back = draw(None, facing="back")[character]
    assert len(eye_boxes(front)) == 2
    assert eye_boxes(back) == []
    assert any(d["op"] == "fill" and d["local"] == [-13, 54, 13, 78] for d in back)


@pytest.mark.parametrize("character", CHARACTERS)
def test_each_character_blinks_at_its_own_offset(character):
    index = CHARACTERS.index(character)
    blink_time = (80 - index * 347) % 3900
    open_time = (1000 - index * 347) % 3900
    blinking = eye_boxes(draw(None, facing="front", time=blink_time)[character])
    opened = eye_boxes(draw(None, facing="front", time=open_time)[character])
    assert len(blinking) == len(opened) == 2
    assert all(d["local"][3] - d["local"][1] == pytest.approx(2, abs=1e-8) for d in blinking)
    assert all(d["local"][3] - d["local"][1] > 2 for d in opened)


@pytest.mark.parametrize("character", ["finance_bro", "founder", "overachiever", "latecomer", "library_local"])
def test_idle_actions_change_the_drawing_while_the_legs_stay_at_rest(character):
    early = draw(None, facing="front", time=400)[character]
    later = draw(None, facing="front", time=1000)[character]
    assert early != later
    # Idle sway may move the whole torso, but neither leg swings relative to its partner.
    for parts in (early, later):
        feet = legs(parts)
        assert angle(feet[0]) == pytest.approx(angle(feet[1]))


@lru_cache(maxsize=1)
def dense_cycle():
    poses = [{"walkPhase": index / 128, "stride": 1, "mirrored": False}
             for index in range(129)]
    result = subprocess.run([NODE, str(TESTS / "running_pose_in_node.js")],
                            input=json.dumps(poses), text=True, capture_output=True,
                            timeout=60, check=True)
    return json.loads(result.stdout)


def transformed_centre(part):
    left, top, right, bottom = part["local"]
    x, y = (left + right) / 2, (top + bottom) / 2
    a, b, c, d, e, f = part["matrix"]
    return (a * x + c * y + e, b * x + d * y + f)


@pytest.mark.parametrize("character", CHARACTERS)
def test_no_part_jumps_between_adjacent_frames_anywhere_in_the_cycle(character):
    frames = dense_cycle()[character]
    assert len(frames) == 129
    for before, after in zip(frames, frames[1:]):
        assert len(before) == len(after)
        for a, b in zip(before, after):
            assert a["op"] == b["op"] and a["colour"] == b["colour"]
            assert math.dist(transformed_centre(a), transformed_centre(b)) < 1.75
