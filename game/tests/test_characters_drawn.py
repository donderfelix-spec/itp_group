"""The drawn characters after the touch-ups of to-do M2-1.11.

The page's own world/characters.js runs in Node (tests/characters_in_node.js)
with a canvas that only writes down where every fill, stroke and text lands.
Each character is drawn as a portrait, standing turned to the right and to
the left, and in eight moments of a step in both directions. The tests read
those records in the design's units (y = -12 is the top of the design, the
middle of the portrait's body is x = 0) or in the frame of the body box,
in which the body never moves.

What a test cannot see (the look of a shape, that two outlines meet without
a seam) was checked in a browser with several players; these tests guard
the measurable part: what is centred, what stays, what is gone.

Without Node these tests are skipped; CI has Node.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from server import protocol

TESTS = Path(__file__).resolve().parent
CHARACTERS_IN_NODE = TESTS / "characters_in_node.js"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

DESIGN_TOP = -12
PORTRAIT_MIDDLE = 0.0
TURNED_MIDDLE = -0.5  # the turned body reaches from x = -18 to 17
SAME = 0.01  # units; the records are exact to a thousandth

OUTLINE = "#2E2A3B"
SKIN = "#F6E7D0"
SURFER_HAIR = "#F2D36B"
HAT_YELLOW = "#FFD23F"
SUITCASE_GREEN = "#2BB3A3"
HEADPHONE_CORAL = "#F2695C"
CHEEK = "#F2A99B"
FOLDER_TAB_COLOURS = {"#F2695C", "#FFD23F", "#6FA8F0"}

STANDING = ["portrait", "right", "left"]
TURNED = ["right", "left"] + [f"walk {side} {k}/8" for side in ("right", "left") for k in range(8)]
WALKING = [pose for pose in TURNED if pose.startswith("walk")]


@pytest.fixture(scope="module")
def drawn():
    finished = subprocess.run([NODE, str(CHARACTERS_IN_NODE)], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(finished.stdout)


# Small helpers


def middle_x(box):
    return (box[0] + box[2]) / 2


def width(box):
    return box[2] - box[0]


def height(box):
    return box[3] - box[1]


def union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def clothes(drawings):
    """What is drawn on the front of the upper body, without the Surfer's long hair and its outline."""
    on_body = [d for d in drawings if d["part"] == "clothes"]
    hair = [d["body"] for d in on_body if d["colour"] == SURFER_HAIR]
    return [d for d in on_body if d["body"] not in hair]


def hands(drawings):
    """The two hands: skin-coloured circles 10 units wide, left one first (in the body's frame)."""
    found = [d for d in drawings if d["op"] == "fill" and d["colour"] == SKIN
             and abs(width(d["body"]) - 10) < SAME and abs(height(d["body"]) - 10) < SAME]
    assert len(found) == 2, found
    return sorted(found, key=lambda d: middle_x(d["body"]))


def head_index(drawings):
    """Where the bare head (a skin circle 36 units wide) is drawn."""
    return next(i for i, d in enumerate(drawings)
                if d["op"] == "fill" and d["colour"] == SKIN and abs(width(d["body"]) - 36) < SAME)


# All eight


def test_every_character_is_drawn_in_every_pose(drawn):
    assert sorted(drawn) == sorted(protocol.CHARACTERS)
    for character, poses in drawn.items():
        for pose, drawings in poses.items():
            assert any(d["part"] == "before" for d in drawings), (character, pose)
            assert any(d["part"] == "after" for d in drawings), (character, pose)


@pytest.mark.parametrize("character", protocol.CHARACTERS)
@pytest.mark.parametrize("pose", STANDING)
def test_nothing_is_drawn_above_the_top_of_the_design(drawn, character, pose):
    # A line reaches half its width beyond its path.
    highest = min(d["design"][1] - d["width"] / 2 for d in drawn[character][pose])
    assert highest >= DESIGN_TOP - 1e-6, (character, pose, highest)


@pytest.mark.parametrize("character", protocol.CHARACTERS)
def test_what_is_on_the_upper_body_is_centred_on_the_torso(drawn, character):
    for pose in ["portrait"] + TURNED:
        expected = PORTRAIT_MIDDLE if pose == "portrait" else TURNED_MIDDLE
        by_colour = {}
        for drawing in clothes(drawn[character][pose]):
            by_colour.setdefault(drawing["colour"], []).append(drawing["body"])
        for colour, boxes in by_colour.items():
            found = middle_x(union(boxes))
            assert abs(found - expected) < SAME, (character, pose, colour, found)


@pytest.mark.parametrize("character", protocol.CHARACTERS)
def test_what_is_on_the_upper_body_stays_in_place_on_the_torso(drawn, character):
    # Standing to the right is the reference: turned to the left (mirrored)
    # and in every moment of a step it lies in the same place on the body.
    reference = [(d["op"], d["colour"], d["body"]) for d in clothes(drawn[character]["right"])]
    for pose in TURNED:
        found = [(d["op"], d["colour"], d["body"]) for d in clothes(drawn[character][pose])]
        assert len(found) == len(reference), (character, pose)
        for (op, colour, box), (op_ref, colour_ref, box_ref) in zip(found, reference):
            assert (op, colour) == (op_ref, colour_ref), (character, pose)
            assert all(abs(a - b) < SAME for a, b in zip(box, box_ref)), (character, pose, box, box_ref)


# Held objects stay in their hand: on the right of the screen in both directions.

HELD_OBJECTS = {
    "consultant": lambda d: d["op"] == "fill" and d["colour"] == "#8A5A3B",  # briefcase
    "finance_bro": lambda d: d["op"] == "stroke" and d["colour"] == "#6BD68A",  # chart on the phone
    "overachiever": lambda d: d["op"] == "text" and d["text"] == "A+",  # folder
    "latecomer": lambda d: d["op"] == "fill" and d["colour"] == "#C9A27A",  # sleeve of the cup
}


@pytest.mark.parametrize("character", sorted(HELD_OBJECTS))
def test_a_held_object_stays_on_the_same_side_of_the_screen(drawn, character):
    for pose in STANDING + WALKING:
        parts = [d for d in drawn[character][pose] if HELD_OBJECTS[character](d)]
        assert parts, (character, pose)
        assert all(d["screenMiddleX"] > 5 for d in parts), (character, pose)


# The Exchange Student


def test_the_exchange_student_has_no_suitcase(drawn):
    for pose, drawings in drawn["exchange_student"].items():
        assert not [d for d in drawings if d["colour"] == SUITCASE_GREEN], pose


def test_the_exchange_student_has_no_yellow_bar_on_the_lower_body(drawn):
    for pose, drawings in drawn["exchange_student"].items():
        yellow = [d for d in drawings if d["colour"] == HAT_YELLOW]
        assert yellow, pose  # the hat
        assert all(d["body"][3] < 20 for d in yellow), pose


def test_the_exchange_student_holds_nothing_and_both_hands_hang_beside_the_body(drawn):
    left, right = hands(drawn["exchange_student"]["portrait"])
    assert middle_x(left["body"]) == pytest.approx(-22) and middle_x(right["body"]) == pytest.approx(22)
    for pose in ["right", "left"]:
        left, right = hands(drawn["exchange_student"][pose])
        assert middle_x(left["body"]) == pytest.approx(-21) and middle_x(right["body"]) == pytest.approx(21)


@pytest.mark.parametrize("side", ["right", "left"])
def test_both_free_hands_of_the_exchange_student_swing_while_walking(drawn, side):
    lefts, rights = [], []
    for k in range(8):
        left, right = hands(drawn["exchange_student"][f"walk {side} {k}/8"])
        lefts.append(middle_x(left["body"]))
        rights.append(middle_x(right["body"]))
        # They swing against each other: one forwards as the other goes back.
        assert lefts[-1] + rights[-1] == pytest.approx(0, abs=SAME)
    assert max(lefts) - min(lefts) > 2
    assert max(rights) - min(rights) > 2


@pytest.mark.parametrize("pose", STANDING)
def test_the_bucket_hat_sits_on_the_head_with_an_even_brim(drawn, pose):
    drawings = drawn["exchange_student"][pose]
    after_head = drawings[head_index(drawings):]
    crown = next(d for d in after_head if d["op"] == "fill" and d["colour"] == HAT_YELLOW)
    brim = next(d for d in after_head if d["op"] == "stroke" and d["colour"] == OUTLINE and d["width"] == 5.5)
    # The crown's sides end at the brim (y = 12), at x = -17 and 17 ...
    left, top, right, bottom = crown["body"]
    assert (left, right, bottom) == (pytest.approx(-17), pytest.approx(17), pytest.approx(12))
    # ... which lies inside the 2.5 wide outline of the head (radius 18 around
    # (0, 20)) there, so the outline runs on into the crown.
    head_edge = (18 ** 2 - (20 - 12) ** 2) ** 0.5
    assert head_edge < 17 <= head_edge + 2.5 / 2
    # The brim sticks out equally far at the front and the back.
    assert brim["body"][0] == pytest.approx(-brim["body"][2])
    assert brim["body"][2] > 17


# The Library Local


@pytest.mark.parametrize("pose", TURNED)
def test_the_library_local_has_one_ear_cup_at_the_back_of_the_head_when_turned(drawn, pose):
    drawings = drawn["library_local"][pose]
    cups = [d for d in drawings if d["op"] == "fill" and d["colour"] == HEADPHONE_CORAL]
    assert len(cups) == 1, pose
    cup = cups[0]["body"]
    cheek_at_the_back = min((d for d in drawings if d["colour"] == CHEEK), key=lambda d: d["body"][0])["body"]
    # On the side of the head at the back, clear of the cheek, nothing in front of the face.
    assert cup[0] < -18
    assert cup[2] < cheek_at_the_back[0]


@pytest.mark.parametrize("pose", TURNED)
def test_the_headphone_band_goes_behind_the_head(drawn, pose):
    drawings = drawn["library_local"][pose]
    head = head_index(drawings)
    bands = [(i, d) for i, d in enumerate(drawings) if d["op"] == "stroke" and d["colour"] == HEADPHONE_CORAL]
    # The whole band is drawn before the head, which hides its far half ...
    assert any(i < head and d["body"][2] > 10 for i, d in bands), pose
    # ... and only its near part, which ends just past the top of the head, after it.
    assert all(d["body"][2] < 5 for i, d in bands if i > head), pose


def test_the_library_local_portrait_keeps_two_ear_cups(drawn):
    cups = sorted((d["body"] for d in drawn["library_local"]["portrait"]
                   if d["op"] == "fill" and d["colour"] == HEADPHONE_CORAL), key=middle_x)
    assert len(cups) == 2
    assert cups[0] == pytest.approx([-25, 13, -16, 29]) and cups[1] == pytest.approx([16, 13, 25, 29])


# The Surfer


@pytest.mark.parametrize("pose", TURNED)
def test_the_surfers_necklace_and_print_lie_on_top_of_the_hair(drawn, pose):
    drawings = drawn["surfer"][pose]
    hair = next(i for i, d in enumerate(drawings) if d["part"] == "clothes" and d["colour"] == SURFER_HAIR)
    necklace = [i for i, d in enumerate(drawings) if d["part"] == "clothes" and d["op"] == "stroke"
                and d["colour"] == OUTLINE and d["width"] == 1.2]
    board = [i for i, d in enumerate(drawings) if d["part"] == "clothes" and d["colour"] == HAT_YELLOW]
    assert necklace and board
    assert min(necklace + board) > hair


# The Overachiever


def test_the_overachievers_folder_has_no_coloured_tabs(drawn):
    for pose, drawings in drawn["overachiever"].items():
        assert not [d for d in drawings if d["op"] == "fill" and d["colour"] in FOLDER_TAB_COLOURS], pose
