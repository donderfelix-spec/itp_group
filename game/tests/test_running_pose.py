"""The pose of a running character (M2-1.13), part by part.

test_running.py checks when a character is in which moment of its run (the
cycle follows the drawn way) and that nothing rises into its name. These
tests check what one moment of the run looks like. They draw every
character with the page's own characters.js in Node
(tests/running_pose_in_node.js, a recording canvas) in many moments of the
run, facing right and mirrored, and read where the parts are drawn:

- each leg hangs from a hip point on the body, which rises and leans with
  it, and the top of the leg stays under the torso with no gap;
- a foot is on the ground for half of a step and moves backwards steadily
  while it is down; the rest of the step both feet are in the air, and the
  back foot kicks up; a planted foot slides about 2.7 map units per step;
- the body hops at most BODY_BOB (3 design units), lowest while a foot is
  down and highest in the air, and leans forward;
- free hands are held higher and pump against the legs; a hand that holds
  something alone pumps a third as far and its object goes with it; what
  is held with both hands only moves with the body;
- steps of size 0 are drawn exactly as standing, small steps close to it,
  and the run has no jump from one moment to the next.

Without Node the tests are skipped; CI has Node.
"""

import json
import math
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
POSE_IN_NODE = TESTS / "running_pose_in_node.js"
WORLD_JS = TESTS.parent / "client" / "js" / "world" / "world.js"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

OUTLINE = "#2E2A3B"
SKIN = "#F6E7D0"
DESIGN_HEIGHT = 112  # design units of a character's height
BODY_BOB = 3  # the highest the body may rise, in design units
HIPS = (-7.5, 74)  # left hip (x, y) on the body; the right one is at +7.5
TORSO_BOTTOM = 80
LEG_WIDTH = 11
SHOE = (14, 8)  # width and height of a shoe

FREE_HANDS = ["exchange_student", "surfer"]
HELD_IN_ONE_HAND = ["consultant", "finance_bro", "overachiever", "latecomer"]
HELD_WITH_BOTH_HANDS = ["founder", "library_local"]
EVERYONE = FREE_HANDS + HELD_IN_ONE_HAND + HELD_WITH_BOTH_HANDS

SAME = 1e-6
MOMENTS = 64  # moments of one cycle that are drawn


def world_js_number(name):
    """A number written as `var NAME = number;` in world.js."""
    match = re.search(rf"var {name} = ([\d.]+);", WORLD_JS.read_text(encoding="utf-8"))
    assert match, name
    return float(match.group(1))


CYCLE_LENGTH = world_js_number("WALK_CYCLE_LENGTH")  # map units per cycle of two steps
MAP_UNITS_PER_DESIGN_UNIT = world_js_number("CHARACTER_HEIGHT") / DESIGN_HEIGHT


# ---- Drawing in Node ---------------------------------------------------------


@lru_cache(maxsize=None)
def drawn(mirrored, stride, moments=MOMENTS):
    """{character: [drawings at phase (k + 0.5) / moments for k in 0..moments-1]} plus the standing pose last.

    The moments lie between the edges of the k-th part of the cycle, so none
    falls exactly on the moment a foot lands or takes off.
    """
    poses = [{"mirrored": mirrored, "walkPhase": (k + 0.5) / moments, "stride": stride} for k in range(moments)]
    poses.append({"mirrored": mirrored, "walkPhase": None, "stride": 0})
    finished = subprocess.run(
        [NODE, str(POSE_IN_NODE)], input=json.dumps(poses), capture_output=True, text=True, timeout=120, check=True
    )
    return json.loads(finished.stdout)


def running(character, mirrored, stride=1):
    return drawn(mirrored, stride)[character][:-1]


def standing(character, mirrored):
    return drawn(mirrored, 1)[character][-1]


# ---- 2D transforms [a, b, c, d, e, f] as on a canvas --------------------------


def apply(m, point):
    x, y = point
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


def inverse(m):
    det = m[0] * m[3] - m[1] * m[2]
    return [m[3] / det, -m[1] / det, -m[2] / det, m[0] / det,
            (m[2] * m[5] - m[3] * m[4]) / det, (m[1] * m[4] - m[0] * m[5]) / det]


def multiply(m, n):
    return [m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1],
            m[0] * n[2] + m[2] * n[3], m[1] * n[2] + m[3] * n[3],
            m[0] * n[4] + m[2] * n[5] + m[4], m[1] * n[4] + m[3] * n[5] + m[5]]


def centre(drawing):
    """The middle of a drawing's box, on the canvas (mirrored back)."""
    x0, y0, x1, y1 = drawing["local"]
    return apply(drawing["matrix"], ((x0 + x1) / 2, (y0 + y1) / 2))


def size(drawing):
    x0, y0, x1, y1 = drawing["local"]
    return (round(x1 - x0, 6), round(y1 - y0, 6))


# ---- The parts of one drawing --------------------------------------------------


def body_index(drawings):
    """The torso: the first fill that reaches from y = 38 to 80 where it is drawn."""
    return next(i for i, d in enumerate(drawings)
                if d["op"] == "fill" and abs(d["local"][1] - 38) < SAME and abs(d["local"][3] - TORSO_BOTTOM) < SAME)


def body(drawings):
    return drawings[body_index(drawings)]


def legs(drawings):
    """The two legs, left first: fills before the torso, 11 wide, hanging from y = 0 where they are drawn."""
    before = drawings[: body_index(drawings)]
    found = [d for d in before if d["op"] == "fill" and size(d)[0] == LEG_WIDTH and abs(d["local"][1]) < SAME]
    assert len(found) == 2
    return found


def shoes(drawings):
    """The two shoes, left first."""
    before = drawings[: body_index(drawings)]
    found = [d for d in before if d["op"] == "fill" and size(d) == SHOE]
    assert len(found) == 2
    return found


def hand_indices(drawings):
    """Where the two hands are in the list: skin-coloured circles 10 across, after the torso."""
    start = body_index(drawings)
    found = [i for i, d in enumerate(drawings)
             if i > start and d["op"] == "fill" and d["colour"] == SKIN and size(d) == (10, 10)]
    assert len(found) == 2
    return found


def object_indices(drawings):
    """What the character holds: drawn after the last arm and before the last hand, hands left out."""
    arms = [i for i, d in enumerate(drawings) if d["op"] == "stroke" and d["colour"] == OUTLINE and d["width"] == 10.5]
    last_hand = hand_indices(drawings)[-1]
    first = arms[-1] + 2  # an arm is an outline and the body colour on top
    return [i for i in range(first, last_hand) if size(drawings[i]) != (10, 10)]


def on_body(drawings, point):
    """A point on the canvas in the coordinates of the torso, which hops and leans."""
    return apply(inverse(body(drawings)["matrix"]), point)


def foot(drawings, side, standing_drawings):
    """(how far forward, how high) a foot is against standing, in design units. side 0 left, 1 right."""
    shoe, still = shoes(drawings)[side], shoes(standing_drawings)[side]
    return (shoe["local"][0] - still["local"][0], still["local"][1] - shoe["local"][1])


def raised(drawings):
    """How far the torso is lifted above the frame the feet are drawn in (which only leans)."""
    lean_frame = shoes(drawings)[0]["matrix"]
    return -multiply(inverse(lean_frame), body(drawings)["matrix"])[5]


def lean(drawings):
    """How far the figure is turned forward, in radians (the side it faces is +x)."""
    m = shoes(drawings)[0]["matrix"]
    return math.atan2(m[1], m[0])


def on_the_ground(drawings, standing_drawings):
    return [foot(drawings, side, standing_drawings)[1] < SAME for side in (0, 1)]


def correlation(xs, ys):
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))


both_ways = pytest.mark.parametrize("mirrored", [False, True], ids=["right", "mirrored"])


# ---- Legs fixed at the hips -------------------------------------------------------


@both_ways
@pytest.mark.parametrize("stride", [0.35, 1])
@pytest.mark.parametrize("character", EVERYONE)
def test_each_leg_hangs_from_its_hip_on_the_body_and_its_top_stays_under_the_torso(character, mirrored, stride):
    for k, drawings in enumerate(running(character, mirrored, stride)):
        torso_left, _, torso_right, _ = body(drawings)["local"]
        for side, leg in enumerate(legs(drawings)):
            hip = on_body(drawings, apply(leg["matrix"], (0, 0)))
            assert hip == pytest.approx(((2 * side - 1) * -HIPS[0], HIPS[1]), abs=SAME), (k, side)
            # Both top corners of the leg lie under the torso: no gap, no block beside it.
            for corner in ((-LEG_WIDTH / 2, 0), (LEG_WIDTH / 2, 0)):
                x, y = on_body(drawings, apply(leg["matrix"], corner))
                assert torso_left < x < torso_right and y < TORSO_BOTTOM, (k, side, x, y)


# ---- Feet on the ground and in the air ---------------------------------------------


@both_ways
@pytest.mark.parametrize("character", EVERYONE)
def test_one_foot_at_most_is_down_and_half_of_each_step_both_are_in_the_air(character, mirrored):
    still = standing(character, mirrored)
    feet_down = [sum(on_the_ground(d, still)) for d in running(character, mirrored)]
    assert max(feet_down) == 1
    assert feet_down.count(0) / MOMENTS == pytest.approx(0.5, abs=1.5 / MOMENTS)
    # Each foot is down for half of its own step: a quarter of the cycle.
    for side in (0, 1):
        down = [on_the_ground(d, still)[side] for d in running(character, mirrored)]
        assert sum(down) / MOMENTS == pytest.approx(0.25, abs=1.5 / MOMENTS)


@both_ways
@pytest.mark.parametrize("character", EVERYONE)
def test_a_foot_on_the_ground_moves_backwards_steadily(character, mirrored):
    still = standing(character, mirrored)
    for side in (0, 1):
        places = [foot(d, side, still)[0] for d in running(character, mirrored) if on_the_ground(d, still)[side]]
        moves = [after - before for before, after in zip(places, places[1:])]
        assert moves and all(move < 0 for move in moves), (side, places)
        assert max(moves) - min(moves) < SAME, (side, moves)  # the same speed all the time


@pytest.mark.parametrize("character", EVERYONE)
def test_a_planted_foot_slides_about_2_7_map_units_per_step(character):
    still = standing(character, False)
    for side in (0, 1):
        places = [foot(d, side, still)[0] for d in running(character, False) if on_the_ground(d, still)[side]]
        speed = (places[0] - places[-1]) / (len(places) - 1)  # design units backwards per moment
        ground_share = len(places) / MOMENTS
        # While the foot is down the runner moves on by ground_share of a
        # cycle; the foot moves back under it by less than that.
        foot_moves_back = speed * len(places) * MAP_UNITS_PER_DESIGN_UNIT
        slide = ground_share * CYCLE_LENGTH - foot_moves_back
        assert slide == pytest.approx(2.7, abs=0.3), (side, slide)


@both_ways
@pytest.mark.parametrize("character", EVERYONE)
def test_the_back_foot_kicks_up_behind_the_runner(character, mirrored):
    still = standing(character, mirrored)
    for side in (0, 1):
        moments = [foot(d, side, still) for d in running(character, mirrored)]
        forward, highest = max(moments, key=lambda moment: moment[1])
        assert highest > 5 and forward < 0, (side, forward, highest)


# ---- The body: hop and lean ---------------------------------------------------------


@both_ways
@pytest.mark.parametrize("character", EVERYONE)
def test_the_body_hops_at_most_body_bob_lowest_on_a_foot_highest_in_the_air(character, mirrored):
    still = standing(character, mirrored)
    moments = running(character, mirrored)
    rises = [raised(d) for d in moments]
    assert min(rises) > -SAME and max(rises) < BODY_BOB + SAME
    assert max(rises) > BODY_BOB - 0.1  # it really hops
    lowest, highest = rises.index(min(rises)), rises.index(max(rises))
    assert any(on_the_ground(moments[lowest], still))
    assert not any(on_the_ground(moments[highest], still))


@pytest.mark.parametrize("character", EVERYONE)
def test_the_runner_leans_forward_the_same_way_in_both_directions(character):
    for mirrored in (False, True):
        leans = [lean(d) for d in running(character, mirrored)]
        assert min(leans) > 0.05 and max(leans) - min(leans) < SAME, leans
        assert lean(standing(character, mirrored)) == pytest.approx(0, abs=SAME)


# ---- Hands and what they hold ---------------------------------------------------------


def hand_moves(character, mirrored):
    """For each hand (back hand first): its (dx, dy) on the body against standing, per moment."""
    still = standing(character, mirrored)
    still_hands = [on_body(still, centre(still[i])) for i in hand_indices(still)]
    moves = [[], []]
    for drawings in running(character, mirrored):
        for side, i in enumerate(hand_indices(drawings)):
            x, y = on_body(drawings, centre(drawings[i]))
            moves[side].append((x - still_hands[side][0], y - still_hands[side][1]))
    return moves


def object_moves(character, mirrored):
    """For each moment: the (dx, dy) on the body of every part of the held object against standing."""
    still = standing(character, mirrored)
    still_parts = [on_body(still, centre(still[i])) for i in object_indices(still)]
    moments = []
    for drawings in running(character, mirrored):
        parts = [on_body(drawings, centre(drawings[i])) for i in object_indices(drawings)]
        assert len(parts) == len(still_parts)
        moments.append([(x - x0, y - y0) for (x, y), (x0, y0) in zip(parts, still_parts)])
    return moments


def spread(values):
    return max(values) - min(values)


@both_ways
@pytest.mark.parametrize("character", FREE_HANDS)
def test_free_hands_are_held_higher_and_pump_against_the_legs(character, mirrored):
    still = standing(character, mirrored)
    moments = running(character, mirrored)
    for side, moves in enumerate(hand_moves(character, mirrored)):
        assert all(dy < -5 for _, dy in moves), (side, moves)  # held higher
        assert spread([dx for dx, _ in moves]) > 8  # pumps
        feet = [foot(d, side, still)[0] for d in moments]
        # The hand is forward while the foot on its side is back, and the other way round.
        assert correlation([dx for dx, _ in moves], feet) < -0.5, side


@both_ways
@pytest.mark.parametrize("character", HELD_IN_ONE_HAND)
def test_a_hand_that_holds_something_alone_pumps_a_third_as_far_and_its_object_goes_with_it(character, mirrored):
    free, holding = hand_moves(character, mirrored)
    for axis in (0, 1):
        free_spread = spread([move[axis] for move in free])
        assert spread([move[axis] for move in holding]) == pytest.approx(free_spread / 3, abs=SAME), axis
    assert spread([dx for dx, _ in free]) > 8
    for moment, hand in zip(object_moves(character, mirrored), holding):
        for part in moment:
            assert part == pytest.approx(hand, abs=SAME)


@both_ways
@pytest.mark.parametrize("character", HELD_WITH_BOTH_HANDS)
def test_what_is_held_with_both_hands_only_moves_with_the_body(character, mirrored):
    for moves in hand_moves(character, mirrored):
        assert all(move == pytest.approx((0, 0), abs=SAME) for move in moves)
    for moment in object_moves(character, mirrored):
        assert all(part == pytest.approx((0, 0), abs=SAME) for part in moment)


# ---- Standing, settling, and no jumps ---------------------------------------------------


@both_ways
@pytest.mark.parametrize("character", EVERYONE)
def test_steps_of_size_0_are_drawn_exactly_as_standing_in_every_moment(character, mirrored):
    still = standing(character, mirrored)
    for drawings in running(character, mirrored, stride=0):
        assert drawings == still


def largest_difference(one, other):
    assert len(one) == len(other)
    return max(math.dist(centre(a), centre(b)) for a, b in zip(one, other))


@both_ways
@pytest.mark.parametrize("character", EVERYONE)
def test_small_steps_are_drawn_close_to_standing_so_a_stop_settles_without_a_jump(character, mirrored):
    still = standing(character, mirrored)
    for drawings in running(character, mirrored, stride=0.02):
        assert largest_difference(drawings, still) < 0.5


@both_ways
@pytest.mark.parametrize("character", EVERYONE)
def test_the_run_has_no_jump_from_one_moment_to_the_next(character, mirrored):
    moments = drawn(mirrored, 1, 128)[character][:-1]
    # A foot in the air moves at most about 0.9 design units in 1/128 of a
    # cycle; a jump would move a part much further. From the last moment
    # back to the first is a step of the cycle too.
    for before, after in zip(moments, moments[1:] + moments[:1]):
        assert largest_difference(before, after) < 1.5
