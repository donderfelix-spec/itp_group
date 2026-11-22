"""The outfit details and the softer face of to-do M2-1.18.

Each of the eight students wears one small motif on the upper body (a tie
clip, two patches, a pin, ...), and the face got a flatter smile and paler
cheeks. As in test_characters_drawn.py, the page's own world/characters.js
runs in Node (tests/characters_in_node.js) with a canvas that only writes
down where every fill and stroke lands, its colour, line width and
globalAlpha. Each character is drawn as a portrait, standing turned to the
right and to the left, and in eight moments of a step in both directions.

The tests read the records in the frame of the body box, in which the body
never moves: x = 0 is the middle of the portrait's body, and the turned body
reaches from x = -18 to 17. A motif is found by its colour and its size,
not by its place, so that the tests of its place mean something.

Without Node these tests are skipped; CI has Node.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from server import protocol

TESTS = Path(__file__).resolve().parent
CHARACTERS_IN_NODE = TESTS / "characters_in_node.js"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

PORTRAIT_MIDDLE = 0.0
TURNED_MIDDLE = -0.5  # the turned body reaches from x = -18 to 17
SAME = 0.01  # units; the records are exact to a thousandth

OUTLINE = "#2E2A3B"
WHITE = "#FFFFFF"
GOLD = "#D9B45C"
CORAL = "#F2695C"
MINT = "#8EDCC5"
CREAM = "#F4EFE3"
LIBRARY_PURPLE = "#7A5CC2"
CHEEK = "#F2A99B"

TURNED = ["right", "left"] + [f"walk {side} {k}/8" for side in ("right", "left") for k in range(8)]
EVERY_POSE = ["portrait"] + TURNED

# The body boxes of characters.js as [left, top, right, bottom] and their radius.
PORTRAIT_BODY = [-19, 38, 19, 80]
TURNED_BODY = [-18, 38, 17, 80]
BODY_RADIUS = 11
# The Surfer's motif lies on the orange shorts, which reach below the body box.
SURFER_SHORTS = {"portrait": [-18, 68, 18, 82], "turned": [-17, 68, 16, 82]}
SHORTS_RADIUS = 5

# Each motif as its pieces: (op, colour, [width, height] of its box). A piece
# that is drawn twice (the two patches) is listed twice. Outlines of width 1
# are drawn 1.2 wide: the thinnest line characters.js draws at this size.
MOTIFS = {
    "consultant": [("fill", GOLD, [6, 2])],  # tie clip
    "finance_bro": [("fill", GOLD, [6.4, 6.4]), ("stroke", OUTLINE, [6.4, 6.4]),  # pin ...
                    ("stroke", WHITE, [3, 3])],  # ... with a white mark
    "exchange_student": [("fill", CORAL, [7, 8]), ("fill", CORAL, [7, 8]),  # two patches ...
                         ("stroke", OUTLINE, [7, 8]), ("stroke", OUTLINE, [7, 8]),
                         ("stroke", WHITE, [18, 0])],  # ... with a white stroke on each
    "surfer": [("stroke", WHITE, [24, 3]), ("stroke", WHITE, [24, 3])],  # two waves on the shorts
    "founder": [("fill", MINT, [6, 9]), ("stroke", OUTLINE, [6, 9])],  # diamond
    "overachiever": [("stroke", CREAM, [6, 5]), ("stroke", CREAM, [6, 5])],  # two check marks
    "latecomer": [("stroke", GOLD, [8, 5])],  # two gold stripes (one path)
    "library_local": [("fill", CREAM, [10, 10]), ("stroke", OUTLINE, [10, 10]),  # book ...
                      ("stroke", LIBRARY_PURPLE, [0, 8])],  # ... with its spine
}

# Ids the page does not know, some of them names that every JavaScript
# object has. Each must draw the plain grey figure without a motif.
ODD_IDS = ["unknown_student", "", "CONSULTANT", "consultant ", "__proto__", "constructor",
           "toString", "hasOwnProperty", "valueOf", 42, None]


def run_harness(ids=None):
    environment = dict(os.environ)
    if ids is not None:
        environment["CHARACTER_IDS"] = json.dumps(ids)
    finished = subprocess.run([NODE, str(CHARACTERS_IN_NODE)], capture_output=True, text=True,
                              timeout=60, check=True, env=environment)
    return json.loads(finished.stdout)


@pytest.fixture(scope="module")
def drawn():
    return run_harness()


@pytest.fixture(scope="module")
def drawn_odd():
    return run_harness(ODD_IDS)


# Small helpers


def key_of(character_id):
    """The key the harness reports an id under (JavaScript's String(id))."""
    return character_id if isinstance(character_id, str) else json.dumps(character_id)


def middle_x(box):
    return (box[0] + box[2]) / 2


def size(box):
    return [box[2] - box[0], box[3] - box[1]]


def union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def close(numbers, expected):
    return all(abs(a - b) < SAME for a, b in zip(numbers, expected))


def on_the_body(drawings):
    """What is drawn on the body box before the first arm (see characters_in_node.js)."""
    return [d for d in drawings if d["part"] == "clothes"]


def matches(drawing, piece):
    op, colour, piece_size = piece
    return drawing["op"] == op and drawing["colour"] == colour and close(size(drawing["body"]), piece_size)


def motif(drawings, character):
    """The drawings of the character's motif, in the order they were drawn."""
    pieces = MOTIFS[character]
    return [d for d in on_the_body(drawings) if any(matches(d, piece) for piece in pieces)]


def inside_rounded_box(x, y, box, radius):
    """Is the point (x, y) inside the box with rounded corners?"""
    left, top, right, bottom = box
    # The nearest point of the box shrunk by the radius must be at most the radius away.
    nearest_x = min(max(x, left + radius), right - radius)
    nearest_y = min(max(y, top + radius), bottom - radius)
    return (x - nearest_x) ** 2 + (y - nearest_y) ** 2 <= radius ** 2 + 1e-9


def outer_box(drawing):
    """The box of a drawing, a line counted with half its width on every side."""
    half = drawing["width"] / 2
    left, top, right, bottom = drawing["body"]
    return [left - half, top - half, right + half, bottom + half]


def smile(drawings):
    """The mouth: a 2 wide outline stroke that starts at y = 29 and is 8 (portrait) or 7 (turned) wide."""
    found = [d for d in drawings if d["op"] == "stroke" and d["colour"] == OUTLINE and d["width"] == 2
             and abs(d["body"][1] - 29) < SAME and any(abs(size(d["body"])[0] - w) < SAME for w in (7, 8))]
    assert len(found) == 1, found
    return found[0]


# 1. Every character wears its own motif in every pose


@pytest.mark.parametrize("character", protocol.CHARACTERS)
@pytest.mark.parametrize("pose", EVERY_POSE)
def test_every_character_wears_its_motif_in_every_pose(drawn, character, pose):
    on_body = on_the_body(drawn[character][pose])
    for piece in MOTIFS[character]:  # a piece listed twice is checked twice, which does no harm
        found = [d for d in on_body if matches(d, piece)]
        assert len(found) == MOTIFS[character].count(piece), (character, pose, piece, found)


@pytest.mark.parametrize("character", protocol.CHARACTERS)
@pytest.mark.parametrize("pose", EVERY_POSE)
def test_the_motif_lies_on_top_of_the_clothes(drawn, character, pose):
    # It is drawn after the clothes and before the arms: the last drawings on the body.
    on_body = on_the_body(drawn[character][pose])
    pieces = motif(drawn[character][pose], character)
    assert on_body[-len(pieces):] == pieces, (character, pose)


@pytest.mark.parametrize("character", protocol.CHARACTERS)
def test_no_character_wears_the_motif_of_another(drawn, character):
    for other in protocol.CHARACTERS:
        if other == character:
            continue
        for pose in EVERY_POSE:
            mine = motif(drawn[character][pose], character)
            borrowed = [d for d in on_the_body(drawn[character][pose])
                        if d not in mine and any(matches(d, piece) for piece in MOTIFS[other])]
            assert not borrowed, (character, other, pose, borrowed)


def test_the_motif_colours_are_only_worn_by_their_owners(drawn):
    owners = {GOLD: {"consultant", "finance_bro", "latecomer"}, MINT: {"founder"},
              CREAM: {"overachiever", "library_local"}}
    for colour, wearers in owners.items():
        for character in protocol.CHARACTERS:
            used = any(d["colour"] == colour for pose in EVERY_POSE for d in drawn[character][pose])
            assert used == (character in wearers), (colour, character)


def test_the_exchange_students_patches_each_carry_a_white_stroke(drawn):
    for pose in EVERY_POSE:
        pieces = motif(drawn["exchange_student"][pose], "exchange_student")
        patches = sorted((d["body"] for d in pieces if d["colour"] == CORAL), key=middle_x)
        line = next(d["body"] for d in pieces if d["colour"] == WHITE)
        # The white stroke runs at the height of the patches, from inside the
        # left one to inside the right one.
        assert patches[0][1] < line[1] < patches[0][3], pose
        assert patches[0][0] < line[0] < patches[0][2], pose
        assert patches[1][0] < line[2] < patches[1][2], pose


def test_the_surfers_waves_are_on_the_shorts(drawn):
    for pose in EVERY_POSE:
        waves = [d["body"] for d in motif(drawn["surfer"][pose], "surfer")]
        assert all(wave[1] > SURFER_SHORTS["portrait"][1] for wave in waves), pose


# 2. The motif is centred on the torso


def expected_middle(pose):
    return PORTRAIT_MIDDLE if pose == "portrait" else TURNED_MIDDLE


# The Surfer's waves have a test of their own below.
SYMMETRIC_MOTIFS = [character for character in protocol.CHARACTERS if character != "surfer"]


@pytest.mark.parametrize("character", SYMMETRIC_MOTIFS)
def test_the_motif_is_centred_on_the_torso(drawn, character):
    for pose in EVERY_POSE:
        boxes = [d["body"] for d in motif(drawn[character][pose], character)]
        found = middle_x(union(boxes))
        assert abs(found - expected_middle(pose)) < SAME, (character, pose, found)


def test_the_surfers_waves_are_centred_on_the_torso(drawn):
    for pose in EVERY_POSE:
        boxes = [d["body"] for d in motif(drawn["surfer"][pose], "surfer")]
        assert abs(middle_x(union(boxes)) - expected_middle(pose)) < SAME, pose


def test_the_exchange_students_patches_are_a_mirrored_pair(drawn):
    for pose in EVERY_POSE:
        middle = expected_middle(pose)
        pieces = motif(drawn["exchange_student"][pose], "exchange_student")
        left, right = sorted((d["body"] for d in pieces if d["colour"] == CORAL), key=middle_x)
        # Mirrored at the middle of the body, the left patch lands on the right one.
        assert close([2 * middle - left[2], left[1], 2 * middle - left[0], left[3]], right), (pose, left, right)


@pytest.mark.parametrize("character", protocol.CHARACTERS)
def test_the_turned_motif_is_the_portrait_motif_moved_to_the_turned_torso(drawn, character):
    # Also for the Surfer: the turned view draws exactly the portrait's motif,
    # moved by the difference between the two body middles.
    shift = TURNED_MIDDLE - PORTRAIT_MIDDLE
    portrait = [(d["op"], d["colour"], d["body"]) for d in motif(drawn[character]["portrait"], character)]
    for pose in TURNED:
        turned = [(d["op"], d["colour"], d["body"]) for d in motif(drawn[character][pose], character)]
        assert len(turned) == len(portrait), (character, pose)
        for (op, colour, box), (op_ref, colour_ref, box_ref) in zip(turned, portrait):
            assert (op, colour) == (op_ref, colour_ref), (character, pose)
            moved = [box_ref[0] + shift, box_ref[1], box_ref[2] + shift, box_ref[3]]
            assert close(box, moved), (character, pose, box, moved)


# 3. The motif stays on the body


def clothing_box(character, pose):
    """The box with rounded corners the motif must stay inside, and its radius."""
    view = "portrait" if pose == "portrait" else "turned"
    if character == "surfer":
        return SURFER_SHORTS[view], SHORTS_RADIUS
    return (PORTRAIT_BODY if view == "portrait" else TURNED_BODY), BODY_RADIUS


@pytest.mark.parametrize("character", protocol.CHARACTERS)
def test_the_motif_stays_inside_the_body_outline(drawn, character):
    for pose in EVERY_POSE:
        box, radius = clothing_box(character, pose)
        for drawing in motif(drawn[character][pose], character):
            left, top, right, bottom = outer_box(drawing)
            # The rounded box has no dents, so if the four corners of the
            # drawing's box are inside, the whole drawing is.
            for x, y in [(left, top), (right, top), (left, bottom), (right, bottom)]:
                assert inside_rounded_box(x, y, box, radius), (character, pose, drawing)


def test_the_surfers_waves_also_stay_inside_the_torso_sideways(drawn):
    for pose in EVERY_POSE:
        body = PORTRAIT_BODY if pose == "portrait" else TURNED_BODY
        for drawing in motif(drawn["surfer"][pose], "surfer"):
            left, _, right, _ = outer_box(drawing)
            assert body[0] < left and right < body[2], (pose, drawing)


def test_inside_rounded_box_knows_the_corners():
    # The helper itself: the corner of the box is cut off by the rounding.
    assert inside_rounded_box(0, 59, PORTRAIT_BODY, BODY_RADIUS)
    assert inside_rounded_box(-19, 59, PORTRAIT_BODY, BODY_RADIUS)
    assert not inside_rounded_box(-19, 38, PORTRAIT_BODY, BODY_RADIUS)
    assert not inside_rounded_box(-20, 59, PORTRAIT_BODY, BODY_RADIUS)


# 4. The softer face


@pytest.mark.parametrize("character", protocol.CHARACTERS)
def test_the_smile_is_flatter(drawn, character):
    for pose in EVERY_POSE:
        mouth = smile(drawn[character][pose])["body"]
        # Portrait from x = -4 to 4, turned from 1.5 to 8.5 (moved towards the face's side).
        expected_x = [-4, 4] if pose == "portrait" else [1.5, 8.5]
        assert close([mouth[0], mouth[2]], expected_x), (character, pose, mouth)
        # Both ends are at y = 29. The lowest point of a curve "Q0 c 4 29"
        # is half-way: (29 + 2c + 29) / 4, so the control point is c = 2 * lowest - 29.
        control_y = 2 * mouth[3] - 29
        assert abs(control_y - 31.5) < SAME, (character, pose, control_y)


@pytest.mark.parametrize("character", protocol.CHARACTERS)
def test_the_cheeks_are_paler(drawn, character):
    for pose in EVERY_POSE:
        drawings = drawn[character][pose]
        cheeks = [i for i, d in enumerate(drawings) if d["colour"] == CHEEK]
        assert len(cheeks) == 2, (character, pose)
        assert all(drawings[i]["op"] == "fill" and drawings[i]["alpha"] == 0.5 for i in cheeks), (character, pose)
        # The paleness ends with the cheeks: what comes next is drawn in full.
        if cheeks[-1] + 1 < len(drawings):
            assert drawings[cheeks[-1] + 1]["alpha"] == 1, (character, pose)


def test_the_cheeks_sit_where_they_did(drawn):
    portrait = sorted((d["body"] for d in drawn["consultant"]["portrait"] if d["colour"] == CHEEK), key=middle_x)
    assert close(portrait[0], [-13.6, 24.4, -8.4, 29.6]) and close(portrait[1], [8.4, 24.4, 13.6, 29.6])
    turned = sorted((d["body"] for d in drawn["consultant"]["right"] if d["colour"] == CHEEK), key=middle_x)
    assert close(turned[0], [-8.6, 24.4, -3.4, 29.6]) and close(turned[1], [11.8, 24.4, 15.2, 29.6])


def test_the_rest_of_the_body_is_drawn_without_transparency(drawn):
    # The harness records globalAlpha; only the shadow, the cheeks and the
    # Overachiever's lenses are see-through.
    see_through = {(OUTLINE, 0.14), (CHEEK, 0.5), (WHITE, 0.35)}
    for character in protocol.CHARACTERS:
        for pose in EVERY_POSE:
            for drawing in drawn[character][pose]:
                if drawing["alpha"] != 1:
                    assert (drawing["colour"], drawing["alpha"]) in see_through, (character, pose, drawing)


# 5. Unknown and odd ids


def test_every_odd_id_is_drawn_in_every_pose(drawn_odd):
    assert sorted(drawn_odd) == sorted(key_of(i) for i in ODD_IDS)
    for character, poses in drawn_odd.items():
        assert sorted(poses) == sorted(EVERY_POSE), character
        for pose, drawings in poses.items():
            assert any(d["part"] == "before" for d in drawings), (character, pose)
            assert any(d["part"] == "after" for d in drawings), (character, pose)


@pytest.mark.parametrize("character_id", ODD_IDS)
def test_an_odd_id_draws_no_motif(drawn_odd, character_id):
    for pose, drawings in drawn_odd[key_of(character_id)].items():
        # The plain figure wears nothing on its body, so a motif would be all there is.
        assert on_the_body(drawings) == [], (character_id, pose)
        assert not [d for d in drawings if d["colour"] in {GOLD, MINT, CREAM, CORAL}], (character_id, pose)


@pytest.mark.parametrize("character_id", ODD_IDS)
def test_an_odd_id_draws_the_same_plain_figure(drawn_odd, character_id):
    assert drawn_odd[key_of(character_id)] == drawn_odd["unknown_student"], character_id


def test_the_plain_figure_keeps_its_face(drawn_odd):
    for pose, drawings in drawn_odd["__proto__"].items():
        mouth = smile(drawings)["body"]
        assert abs(2 * mouth[3] - 29 - 31.5) < SAME, pose
        cheeks = [d for d in drawings if d["colour"] == CHEEK]
        assert len(cheeks) == 2 and all(d["alpha"] == 0.5 for d in cheeks), pose


def test_a_known_id_given_to_the_harness_still_wears_its_motif():
    # The harness's own check: CHARACTER_IDS with a real id draws that character.
    drawn = run_harness(["founder"])
    assert list(drawn) == ["founder"]
    assert len(motif(drawn["founder"]["portrait"], "founder")) == 2
