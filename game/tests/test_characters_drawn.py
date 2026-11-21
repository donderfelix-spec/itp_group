"""Measure the current individual campus mascots in a recording Canvas.

Updated for Hanna's requested mascot designs. These checks retain the bounds,
mirroring and accessory coverage of the former humanoid drawing tests.
"""
import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest
from server import protocol

NODE = shutil.which("node")
TESTS = Path(__file__).resolve().parent
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")
HEADS = {
    "consultant": "#D8B98A", "finance_bro": "#667C98",
    "exchange_student": "#F9B7D3", "surfer": "#F6D874",
    "founder": "#33333D", "overachiever": "#F4EFE3",
    "latecomer": "#F4EFE3", "library_local": "#BDA5E4",
}
ACCESSORIES = {
    "consultant": {"#ED5A56", "#9B653F"},
    "finance_bro": {"#344154", "#76E7AA"},
    "exchange_student": {"#FFD23F"},
    "surfer": {"#FFD23F", "#F2695C"},
    "founder": {"#C9CED6", "#F2695C"},
    "overachiever": {"#FFD23F", "#4E9F5B"},
    "latecomer": {"#9B653F", "#F08A3C"},
    "library_local": {"#FFD23F", "#E99078", "#F2695C"},
}


@pytest.fixture(scope="module")
def drawn():
    result = subprocess.run([NODE, str(TESTS / "characters_in_node.js")],
                            text=True, capture_output=True, timeout=60, check=True)
    return json.loads(result.stdout)


def head(drawings, character):
    return next(d for d in drawings if d["op"] == "fill" and d["colour"] == HEADS[character]
                and d["local"][1] < 20 and d["local"][2] - d["local"][0] >= 30
                and d["local"][3] - d["local"][1] >= 30)


def test_all_eight_characters_are_drawn_in_every_pose(drawn):
    assert list(drawn) == list(protocol.CHARACTERS)
    for poses in drawn.values():
        assert len(poses) == 19
        assert all(len(parts) >= 20 for parts in poses.values())


@pytest.mark.parametrize("character", protocol.CHARACTERS)
def test_every_pose_is_finite_and_stays_inside_the_character_envelope(drawn, character):
    for parts in drawn[character].values():
        for part in parts:
            assert all(math.isfinite(value) for value in part["design"])
            left, top, right, bottom = part["design"]
            assert -48 <= left <= right <= 48
            assert -16 <= top <= bottom <= 104


def test_each_character_has_a_distinct_head_silhouette(drawn):
    silhouettes = [tuple(head(poses["portrait"], character)["local"])
                   for character, poses in drawn.items()]
    assert len(set(silhouettes)) == 8


@pytest.mark.parametrize("character", protocol.CHARACTERS)
def test_head_and_required_student_accessories_are_visible_in_all_front_poses(drawn, character):
    for parts in drawn[character].values():
        assert head(parts, character)
        colours = {part["colour"] for part in parts if part["op"] == "fill"}
        assert ACCESSORIES[character] <= colours


@pytest.mark.parametrize("character", protocol.CHARACTERS)
def test_mirroring_preserves_the_complete_design(drawn, character):
    for phase in [""] + [f"walk {{side}} {index}/8" for index in range(8)]:
        right = drawn[character][phase.format(side="right") if phase else "right"]
        left = drawn[character][phase.format(side="left") if phase else "left"]
        assert len(right) == len(left)
        for a, b in zip(right, left):
            assert a["op"] == b["op"] and a["colour"] == b["colour"]
            assert a["local"] == pytest.approx(b["local"], abs=0.002)
            assert a["design"] == pytest.approx(b["design"], abs=0.002)


@pytest.mark.parametrize("character", protocol.CHARACTERS)
def test_every_character_keeps_two_separate_boots(drawn, character):
    for parts in drawn[character].values():
        boots = [d for d in parts if d["op"] == "fill" and d["colour"] == "#20212A"
                 and d["local"] == pytest.approx([-8, 11, 10, 18], abs=0.01)]
        assert len(boots) == 2
        assert boots[0]["matrix"] != boots[1]["matrix"]


def test_unknown_and_prototype_property_ids_draw_a_safe_grey_fallback():
    result = subprocess.run([NODE, str(TESTS / "characters_in_node.js"), str(TESTS.parent / "client/js/world/characters.js"), "--unknown"],
                            text=True, capture_output=True, timeout=60, check=True)
    unknown = json.loads(result.stdout)
    assert set(unknown) == {"missing", "toString", "__proto__"}
    for poses in unknown.values():
        for parts in poses.values():
            assert any(d["op"] == "fill" and d["colour"] == "#9296A0" for d in parts)
            assert all(math.isfinite(v) for d in parts for v in d["design"])
