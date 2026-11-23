"""M4-2.2: which devices get the notice "Group Project needs a keyboard.".

The plain function looksTouchOnly() of client/js/keyboard_notice.js runs in
Node (skipped without Node). Touch-only means the primary pointer is coarse
and cannot hover, with at least one touch point; a laptop with a touchscreen
keeps a fine pointer that hovers and must never be caught.
"""

import json
import subprocess
from pathlib import Path

import pytest

from test_play_campus_detail import NODE

IN_NODE = Path(__file__).with_name("keyboard_notice_in_node.js")

needs_node = pytest.mark.skipif(NODE is None, reason="Node is needed")

PHONE = {"(pointer: coarse)": True, "(hover: none)": True}
DESKTOP = {"(pointer: coarse)": False, "(hover: none)": False}
TOUCH_LAPTOP = {"(pointer: coarse)": False, "(hover: none)": False}


def answers(cases):
    finished = subprocess.run(
        [NODE, str(IN_NODE)], input=json.dumps(cases), capture_output=True, text=True, timeout=30, check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


# ---- Accepted: phones and tablets get the notice ----


@needs_node
@pytest.mark.parametrize("touch_points", [1, 5, 10])
def test_a_phone_or_tablet_is_touch_only(touch_points):
    assert answers([{"signals": [True, True, touch_points]}]) == [True]


@needs_node
def test_a_phone_window_is_touch_only():
    assert answers([{"window": {"media": PHONE, "maxTouchPoints": 5}}]) == [True]


# ---- Rejected: computers never get it ----


@needs_node
def test_a_desktop_with_a_mouse_is_not_touch_only():
    assert answers([
        {"signals": [False, False, 0]},
        {"window": {"media": DESKTOP, "maxTouchPoints": 0}},
    ]) == [False, False]


@needs_node
def test_a_laptop_with_a_touchscreen_is_not_touch_only():
    assert answers([
        {"signals": [False, False, 10]},
        {"window": {"media": TOUCH_LAPTOP, "maxTouchPoints": 10}},
    ]) == [False, False]


@needs_node
def test_without_matchmedia_nobody_gets_the_notice():
    assert answers([
        {"window": {"media": None, "maxTouchPoints": 5}},
        {"signals": [None, None, 5]},
    ]) == [False, False]


@needs_node
def test_a_failing_matchmedia_counts_as_no_answer():
    assert answers([{"window": {"media": PHONE, "maxTouchPoints": 5, "throws": True}}]) == [False]


# ---- Edge cases ----


@needs_node
def test_touch_points_with_a_fine_pointer_are_not_enough():
    # A fine primary pointer (mouse or trackpad) with a touchscreen beside it.
    assert answers([{"signals": [False, True, 5]}, {"signals": [False, False, 1]}]) == [False, False]


@needs_node
def test_a_coarse_pointer_that_hovers_is_not_touch_only():
    # For example a TV remote or a game pad that moves a pointer.
    assert answers([{"signals": [True, False, 5]}]) == [False]


@needs_node
@pytest.mark.parametrize("touch_points", [0, None, "5"])
def test_a_coarse_pointer_without_touch_points_is_not_touch_only(touch_points):
    assert answers([{"signals": [True, True, touch_points]}]) == [False]
