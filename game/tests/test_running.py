"""The run of the characters on the map (M2-1.13).

The running cycle runs on the way the drawn character covers, not on the
time (client/js/world/world.js, walkPhase): one cycle every 36 map units.
These tests play positions messages into the page's own world.js
(tests/world_glide_in_node.js) and read, frame by frame, where each character
is drawn and which walkPhase it is drawn with:

- the phase is the drawn way since the character started walking, divided
  by 36, with messages on time and with messages that arrive irregularly;
- a jump (a change too long for a step) and a placement at the start of a
  round add nothing to that way, and the walk after them starts at phase 0.

A running character rises on every step and the name above it keeps room
for 3 design units (BODY_BOB in characters.js, HEAD_ROOM_BELOW_NAME in
world.js). The last test draws every character with the page's own
characters.js (tests/character_heights_in_node.js) in many moments of the run
and checks that nothing reaches higher than that.

Without Node the tests are skipped; CI has Node.
"""

import json
import math
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from server import protocol
from server.main import TICKS_PER_SECOND

TESTS = Path(__file__).resolve().parent
WORLD_IN_NODE = TESTS / "world_glide_in_node.js"
HEIGHTS_IN_NODE = TESTS / "character_heights_in_node.js"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

# Map units the drawn character covers in one running cycle (two steps).
CYCLE_LENGTH = 36
TICK = 1000 / TICKS_PER_SECOND  # ms between two positions messages
FRAME = 1000 / 60  # ms between two frames of a 60 Hz screen
STEP = 6  # map units a walking player moves in one tick (90 units per second)
START = (300, 300)

# The highest a running character may reach, in design units: the top of a
# standing character (-12) and the 3 units the name above it leaves free.
HIGHEST_ALLOWED = -12 - 3

SAME = 1e-9


# ---- Helpers ---------------------------------------------------------------


def run_world(messages, until, start_of_round=None):
    """Play `messages` [(t, x, y)] for one player into world.js; draw frames until `until` ms.

    Returns one (t, drawn x, drawn y, walkPhase) per frame.
    """
    events = [(t, 0, ["positions", t, [{"name": "Mara", "x": x, "y": y}]]) for t, x, y in messages]
    if start_of_round is not None:
        events.append((start_of_round, 0, ["start_of_round", start_of_round]))
    t = 5.0  # the frames start a little after the first message
    while t <= until:
        events.append((t, 1, ["frames", t, t]))
        t += FRAME
    events.sort(key=lambda event: (event[0], event[1]))
    program = {
        "own": "Mara",
        "players": [{"name": "Mara", "character": "student"}],
        "usable": None,
        "steps": [event[2] for event in events],
    }
    finished = subprocess.run(
        [NODE, str(WORLD_IN_NODE)], input=json.dumps(program), capture_output=True, text=True, timeout=60, check=False
    )
    assert finished.returncode == 0, finished.stderr
    frames = []
    for frame in json.loads(finished.stdout):
        (drawn,) = frame["characters"]
        frames.append((frame["t"], drawn["x"], drawn["middleY"], drawn["walkPhase"]))
    return frames


def walking_right(ticks, start_x=START[0], first_tick=0):
    """Places one tick apart, STEP further right each: [(tick number, x, y)]."""
    return [(first_tick + k, start_x + STEP * k, START[1]) for k in range(ticks + 1)]


def sent(places, late=lambda k: 0):
    """Messages for `places`: place k arrives at its tick plus late(k) ms, never before the one before it."""
    messages = []
    last = -math.inf
    for tick, x, y in places:
        arrives = max(tick * TICK + late(tick), last)
        messages.append((arrives, x, y))
        last = arrives
    return messages


def phase_of_way(way):
    """The phase after `way` map units: one cycle every CYCLE_LENGTH."""
    return (way / CYCLE_LENGTH) % 1


def same_phase(a, b):
    """True if two phases are the same moment of the cycle (0.999999 and 0 are)."""
    difference = abs(a - b) % 1
    return min(difference, 1 - difference) < SAME


def assert_phase_follows_the_way(frames, walk_starts_at_x):
    """Every frame with a phase shows the way walked right from walk_starts_at_x, divided by 36."""
    for t, x, _, phase in frames:
        assert phase is not None, t
        assert same_phase(phase, phase_of_way(x - walk_starts_at_x)), (t, x, phase)


# ---- The phase is the drawn way divided by 36 -------------------------------


def test_the_phase_is_the_drawn_way_divided_by_the_cycle_length():
    places = walking_right(30)
    frames = run_world(sent(places), until=30 * TICK)
    # The player walks from the second message on (the first one only places it).
    walking = [frame for frame in frames if frame[0] > TICK]
    assert walking[-1][1] - START[0] > 4 * CYCLE_LENGTH  # several whole cycles were walked
    assert_phase_follows_the_way(walking, START[0])


def test_the_phase_follows_the_drawn_way_also_when_messages_arrive_irregularly():
    shuffle = random.Random(113)
    # Up to 80 ms late. A message more than one tick late arrives together
    # with the next one (they never overtake each other).
    delays = {k: shuffle.choice([0, 0, 15, 30, 45, 60, 80]) for k in range(41)}
    places = walking_right(40)
    messages = sent(places, late=lambda k: delays[k])
    assert len({t for t, _, _ in messages}) < len(messages)  # some arrive together
    frames = run_world(messages, until=messages[-1][0])
    walking = [frame for frame in frames if frame[0] > messages[1][0]]
    assert_phase_follows_the_way(walking, START[0])


# ---- A jump or a placement adds no way; the walk after it starts at 0 -------


def test_a_jump_adds_no_way_and_the_walk_after_it_starts_at_phase_0():
    before = walking_right(10)
    jump_x = before[-1][1] + 100  # more than a step: the server put the player there
    after = walking_right(10, start_x=jump_x, first_tick=11)
    messages = sent(before + after)
    frames = run_world(messages, until=messages[-1][0])
    jumped_at = messages[len(before)][0]
    walks_again_at = messages[len(before) + 1][0]
    # Between the jump and the next step the character stands.
    assert all(phase is None for t, _, _, phase in frames if jumped_at <= t < walks_again_at)
    walking_again = [frame for frame in frames if frame[0] >= walks_again_at]
    # Its first frame comes a moment after that step: the phase has only just left 0.
    assert walking_again[0][3] is not None and walking_again[0][3] < STEP / CYCLE_LENGTH
    assert_phase_follows_the_way(walking_again, jump_x)


def test_a_placement_at_the_start_of_a_round_adds_no_way_and_the_walk_after_it_starts_at_phase_0():
    before = walking_right(10)
    # Only 12 units back: as a change of position this would be a step, but
    # it comes right after the start of a round, so it is a placement.
    placed_x = before[-1][1] - 12
    after = walking_right(10, start_x=placed_x, first_tick=11)
    messages = sent(before + after)
    round_starts_at = messages[len(before)][0] - 10
    frames = run_world(messages, until=messages[-1][0], start_of_round=round_starts_at)
    placed_at = messages[len(before)][0]
    walks_again_at = messages[len(before) + 1][0]
    assert all(phase is None for t, _, _, phase in frames if placed_at <= t < walks_again_at)
    walking_again = [frame for frame in frames if frame[0] >= walks_again_at]
    # Its first frame comes a moment after that step: the phase has only just left 0.
    assert walking_again[0][3] is not None and walking_again[0][3] < STEP / CYCLE_LENGTH
    assert_phase_follows_the_way(walking_again, placed_x)


# ---- Nothing reaches higher than the room under the name ----------------------


def test_no_running_pose_reaches_higher_than_the_room_under_the_name():
    poses = [
        {"mirrored": mirrored, "walkPhase": k / 48, "stride": stride}
        for mirrored in (False, True)
        for stride in (0.5, 1)
        for k in range(49)  # phases 0 to 1, both included
    ]
    finished = subprocess.run(
        [NODE, str(HEIGHTS_IN_NODE)], input=json.dumps(poses), capture_output=True, text=True, timeout=60, check=True
    )
    highest = json.loads(finished.stdout)
    assert sorted(highest) == sorted(protocol.CHARACTERS)
    for character, heights in highest.items():
        for pose, height in zip(poses, heights):
            assert height >= HIGHEST_ALLOWED - SAME, (character, pose, height)
    # The measurement works: running does rise above a standing character.
    assert min(min(heights) for heights in highest.values()) < -12
