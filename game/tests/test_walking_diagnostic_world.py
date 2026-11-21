"""What world.js offers the walking diagnostic (M2-1.15), with the real world.js.

The diagnostic (js/world/diagnostic.js) reads two things from the world:

- `Game.world.ownDrawnPosition(now)`: where the frame at `now` draws the own
  character. The diagnostic asks in its own frame callback, which runs
  *before* the world draws the frame and starts the queued glides whose time
  has come (M2-1.14). The answer must already be what that frame will draw,
  and asking must change nothing.
- `Game.world.walkingDirection()`: the direction the server heard last and
  `since`, the time of the key that started this walk.

The page's own world.js and diagnostic.js run in Node
(tests/world_diagnostic_in_node.js): a test decides when a message arrives,
when a key is pressed and when a frame is drawn. Without Node the tests are
skipped; CI has Node.
"""

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from server.main import TICKS_PER_SECOND, app
from server.protocol import CHARACTERS

TESTS = Path(__file__).resolve().parent
WORLD_IN_NODE = TESTS / "world_diagnostic_in_node.js"
FELIX_TRACE = TESTS / "network_trace" / "felix_2026-11-20.json"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

SPAWN = (app.state.campus["spawn"]["x"], app.state.campus["spawn"]["y"])
TICK = 1000 / TICKS_PER_SECOND  # ms between two positions messages of the server
STEP = 6  # map units per tick at the server's walking speed of 90 units per second
FRAME = 1000 / 60
FRAME_OFFSET = 5  # the frames start a little after the first message

# The extra delay of each `positions` message on Felix's connection, in ms.
FELIX_DELAYS = json.loads(FELIX_TRACE.read_text(encoding="utf-8"))

# Less than this, in map units, is the same position: far below one pixel.
EXACT = 1e-6

# As in diagnostic.js: a frame is judged 400 ms into a walk, and it is
# "uneven" when the character is drawn slower than 45 or faster than 135 units/s.
WALK_SETTLE_MS = 400
SLOW_SPEED = 45
FAST_SPEED = 135

OWN = "Mara"
KEY_RIGHT = "KeyD"
KEY_LEFT = "KeyA"
KEY_UP = "KeyW"


# ---- Helpers ---------------------------------------------------------------


def run_world(steps, ask=None, debug=False):
    """Play the steps into world.js (see the harness). Returns its output."""
    program = {
        "own": OWN,
        "players": [{"name": OWN, "character": CHARACTERS[0]}],
        "ask": ask,
        "debug": debug,
        "steps": steps,
    }
    finished = subprocess.run(
        [NODE, str(WORLD_IN_NODE)], input=json.dumps(program), capture_output=True, text=True, timeout=60, check=False
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def arrival_times(count, first, delays):
    """When `count` messages arrive that the server sends every tick from `first` on.

    Message k arrives delays[k] ms late (the list is used in a loop). A
    held-back message never overtakes an earlier one (TCP keeps the order).
    """
    times = []
    last = -math.inf
    for k in range(count):
        last = max(first + k * TICK + delays[k % len(delays)], last)
        times.append(last)
    return times


def walk_right(times):
    """One `positions` step per arrival time: the own player walks right from the spawn."""
    return [["positions", t, [{"name": OWN, "x": SPAWN[0] + STEP * k, "y": SPAWN[1]}]] for k, t in enumerate(times)]


def with_frames(steps, until):
    """The steps in the order of their times, with a frame every 1000/60 ms up to `until`.

    A message or a key at the same moment as a frame comes first.
    """
    events = [(step[1], 0, step) for step in steps]
    t = FRAME_OFFSET
    while t <= until:
        events.append((t, 1, ["frames", t, t]))
        t += FRAME
    events.sort(key=lambda event: (event[0], event[1]))
    return [event[2] for event in events]


DELIVERIES = {"on time": [0], "as on Felix's connection": FELIX_DELAYS}
SIX_SECONDS = 90  # messages


def six_second_walk(delays, first=0):
    """Steps of a walk of six seconds, and the time of its last message."""
    times = arrival_times(SIX_SECONDS, first, delays)
    return walk_right(times), times[-1]


def first_arrival(messages):
    return messages[0][1]


def drawn_player(frame):
    point = frame.get("drawn") or frame["camera"]
    return (point["x"], point["y"])


def place(asked):
    return (asked["x"], asked["y"])


# ---- ownDrawnPosition: what the frame draws ---------------------------------


@pytest.mark.parametrize("delays", DELIVERIES.values(), ids=DELIVERIES.keys())
def test_asked_before_a_frame_the_own_position_is_what_that_frame_draws(delays):
    messages, end = six_second_walk(delays)
    frames = run_world(with_frames(messages, until=end + 500), ask=[0])["frames"]

    assert len(frames) > 360  # six and a half seconds of frames
    # Until the first message there is no own position (and the camera looks at the spawn).
    early = [frame for frame in frames if frame["t"] < first_arrival(messages)]
    assert all(frame["asked"] == [None] for frame in early)
    # From then on the camera looks at the own character, so it is where the frame drew it.
    for frame in frames[len(early):]:
        assert math.dist(place(frame["asked"][0]), drawn_player(frame)) < EXACT, frame["t"]
    # The walk was drawn: the test did not compare a character that stood.
    assert drawn_player(frames[-1])[0] == pytest.approx(SPAWN[0] + STEP * (SIX_SECONDS - 1))


def test_without_a_position_the_own_position_is_null():
    frames = run_world(with_frames([], until=200), ask=[0, 1000])["frames"]
    assert len(frames) > 10
    assert all(frame["asked"] == [None, None] for frame in frames)


def test_asked_for_a_later_time_it_is_where_a_frame_at_that_time_draws():
    # Asked 50 ms ahead, before every frame; the frame three frames later is
    # 50 ms later. No message arrives after `end`, so nothing new is queued
    # between the question and that frame.
    messages, end = six_second_walk([0])
    frames = run_world(with_frames(messages, until=end + 1000), ask=[3 * FRAME])["frames"]
    late = [(a, b) for a, b in zip(frames, frames[3:]) if a["t"] > end]
    assert len(late) > 50
    for asked_in, drawn_in in late:
        assert math.dist(place(asked_in["asked"][0]), drawn_player(drawn_in)) < EXACT


# ---- ownDrawnPosition: a queued position a jump away ----------------------------

JUMP_DISTANCE = 60  # as in world.js: further than this on an axis is a jump, not a glide
BIG_STEP = 50  # map units; one of them is no jump, two of them are


def jump_out_of_the_queue():
    """Steps in which a position waits in the queue a jump away from the drawn character.

    The server moves the player by 50 units per message, three times. The
    second and third position are queued. Before the third is drawn, a round
    starts, which empties the queue: the drawing stops at the second
    position while the world knows the third. More than a second later (so
    it is no placement any more) a fourth position comes. It is 50 units
    from the third, so it is queued like a step, but 100 units from the
    place the character is drawn.
    Returns the steps, the place the glide before the queued entry ends, the
    place of the queued entry, and the time it arrives.
    """
    at = [{"name": OWN, "x": SPAWN[0] + BIG_STEP * k, "y": SPAWN[1]} for k in range(4)]
    arrives_at = 2000
    steps = [
        ["positions", 0, [at[0]]],
        ["positions", 500, [at[1]]],
        ["positions", 501, [at[2]]],
        ["start_of_round", 505],
        ["positions", arrives_at, [at[3]]],
    ]
    return steps, (at[1]["x"], at[1]["y"]), (at[3]["x"], at[3]["y"]), arrives_at


def test_a_queued_position_a_jump_away_is_drawn_at_its_place_and_asked_before_the_frame_too():
    steps, glide_ends, queued, arrives_at = jump_out_of_the_queue()
    frames = run_world(with_frames(steps, until=arrives_at + 500), ask=[0])["frames"]
    assert abs(queued[0] - glide_ends[0]) > JUMP_DISTANCE

    # Right before the position arrives, the character is drawn where the glide before ended.
    before = [frame for frame in frames if 1500 < frame["t"] < arrives_at]
    assert len(before) > 20
    assert all(math.dist(drawn_player(frame), glide_ends) < EXACT for frame in before)
    # The first frame after it draws the character at the new place at once: a jump, not a glide.
    after = [frame for frame in frames if frame["t"] >= arrives_at]
    assert len(after) > 20
    assert math.dist(drawn_player(after[0]), queued) < EXACT
    # Asked before each frame, also before the one that takes the position
    # out of the queue, the answer is what that frame drew.
    for frame in frames:
        if frame["t"] >= first_arrival(steps):
            assert math.dist(place(frame["asked"][0]), drawn_player(frame)) < EXACT, frame["t"]


def test_asking_about_a_queued_jump_leaves_every_frame_as_it_was():
    steps, _, _, arrives_at = jump_out_of_the_queue()
    with_all_frames = with_frames(steps, until=arrives_at + 500)
    never_asked = run_world(with_all_frames)["frames"]
    asked = run_world(with_all_frames, ask=[0, 40, 500, -30])["frames"]
    assert [frame["camera"] for frame in asked] == [frame["camera"] for frame in never_asked]


def test_a_queued_position_just_inside_the_jump_distance_glides_and_is_followed_too():
    # The same, with the fourth position 10 units on instead of 50: 60 units
    # from the drawn character, which is exactly the jump distance and so no jump.
    steps, glide_ends, _, arrives_at = jump_out_of_the_queue()
    near = (SPAWN[0] + 2 * BIG_STEP + 10, SPAWN[1])
    steps[-1] = ["positions", arrives_at, [{"name": OWN, "x": near[0], "y": near[1]}]]
    frames = run_world(with_frames(steps, until=arrives_at + 500), ask=[0])["frames"]
    assert abs(near[0] - glide_ends[0]) == JUMP_DISTANCE

    after = [frame for frame in frames if frame["t"] >= arrives_at]
    # It glides: the first frames are drawn on the way, and the last one at the new place.
    assert glide_ends[0] < drawn_player(after[0])[0] < glide_ends[0] + 15
    assert glide_ends[0] < drawn_player(after[1])[0] < near[0]
    assert math.dist(drawn_player(after[-1]), near) < EXACT
    for frame in after:
        assert math.dist(place(frame["asked"][0]), drawn_player(frame)) < EXACT, frame["t"]


# ---- ownDrawnPosition: asking changes nothing --------------------------------


@pytest.mark.parametrize("delays", DELIVERIES.values(), ids=DELIVERIES.keys())
def test_asking_for_the_own_position_leaves_every_frame_as_it_was(delays):
    messages, end = six_second_walk(delays)
    steps = with_frames(messages, until=end + 500)
    never_asked = run_world(steps)["frames"]
    # Asked for the time of the frame, for later times (a playQueue() with
    # these would start glides too early) and for an earlier one.
    asked = run_world(steps, ask=[0, 40, 500, 5000, -30])["frames"]

    assert len(never_asked) > 360
    assert [frame["t"] for frame in asked] == [frame["t"] for frame in never_asked]
    assert [frame["camera"] for frame in asked] == [frame["camera"] for frame in never_asked]


@pytest.mark.parametrize("delays", DELIVERIES.values(), ids=DELIVERIES.keys())
def test_the_diagnostic_itself_leaves_every_frame_as_it_was(delays):
    messages, end = six_second_walk(delays)
    steps = with_frames(messages, until=end + 500)
    without = run_world(steps)
    with_debug = run_world(steps, debug=True)

    assert without["numbers"] is None
    assert with_debug["numbers"]["frames"]["count"] > 360
    assert with_debug["frames"] == without["frames"]


# ---- The real diagnostic on the real world -----------------------------------


def really_drawn(frames, key_at):
    """Speeds between judged frames, in units/s, worked out from where the camera really was."""
    speeds = []
    for before, frame in zip(frames, frames[1:]):
        if frame["t"] - key_at >= WALK_SETTLE_MS:
            speeds.append(math.dist(drawn_player(before), drawn_player(frame)) / ((frame["t"] - before["t"]) / 1000))
    return speeds


def uneven_percent(speeds):
    return 100 * sum(1 for speed in speeds if speed < SLOW_SPEED or speed > FAST_SPEED) / len(speeds)


def key_then_walk(delays):
    """The player stands a second, presses "right", and walks six seconds in the open.

    Returns the steps, the time of the key and the time of the last message.
    """
    key_at = 1000
    # The server's first answer to the key comes one tick later.
    messages, end = six_second_walk(delays, first=key_at + TICK)
    standing = [["positions", 0, [{"name": OWN, "x": SPAWN[0], "y": SPAWN[1]}]]]
    steps = standing + [["key", key_at, "down", KEY_RIGHT]] + messages
    return steps, key_at, end


def test_with_messages_on_time_the_diagnostic_reports_an_even_walk():
    # Before the fix the diagnostic reported about a third of these frames
    # as uneven: in a frame that starts a queued glide it read too short a
    # step, and in the next one too long a step.
    steps, key_at, end = key_then_walk([0])
    result = run_world(with_frames(steps, until=end), debug=True)
    walking = result["numbers"]["walking"]

    assert walking["frames"] > 300
    assert walking["unevenPercent"] == 0
    assert walking["frozenFrames"] == 0
    assert walking["stalls"] == 0
    assert walking["speed"]["median"] == pytest.approx(90, rel=0.02)
    assert uneven_percent(really_drawn(result["frames"], key_at)) == 0


@pytest.mark.parametrize("delays", DELIVERIES.values(), ids=DELIVERIES.keys())
def test_the_diagnostic_reports_the_speeds_that_were_really_drawn(delays):
    steps, key_at, end = key_then_walk(delays)
    result = run_world(with_frames(steps, until=end), debug=True)
    walking = result["numbers"]["walking"]
    speeds = sorted(really_drawn(result["frames"], key_at))

    assert walking["frames"] == len(speeds)
    assert walking["unevenPercent"] == pytest.approx(uneven_percent(speeds))
    assert walking["speed"]["median"] == pytest.approx(speeds[len(speeds) // 2], rel=0.01)
    assert walking["frozenFrames"] == sum(1 for speed in speeds if speed < 0.01 / (FRAME / 1000))


def test_the_start_delay_of_the_diagnostic_runs_from_the_key_to_the_first_frame_that_moved():
    steps, key_at, end = key_then_walk([0])
    result = run_world(with_frames(steps, until=end), debug=True)
    frames = result["frames"]
    first_moved = next(b["t"] for a, b in zip(frames, frames[1:]) if math.dist(drawn_player(a), drawn_player(b)) >= 0.01)

    assert result["numbers"]["startDelay"]["count"] == 1
    assert result["numbers"]["startDelay"]["median"] == pytest.approx(first_moved - key_at)
    # The key, the server's tick and the playback delay: some frames, not one.
    assert first_moved - key_at > 60


# ---- walkingDirection: `since` -----------------------------------------------


def directions_after(*keys):
    """Game.world.walkingDirection() after each of the keys (time, "down" or "up", code)."""
    steps = []
    for time, up_or_down, code in keys:
        steps += [["key", time, up_or_down, code], ["direction", time]]
    return run_world(steps)["directions"]


def test_while_standing_the_direction_has_no_since():
    assert run_world([["direction", 500]])["directions"] == [{"dx": 0, "dy": 0, "since": None}]


def test_since_is_the_time_of_the_key_that_started_the_walk():
    assert directions_after((1000, "down", KEY_RIGHT)) == [{"dx": 1, "dy": 0, "since": 1000}]


def test_turning_keeps_since_and_releasing_all_keys_forgets_it():
    directions = directions_after(
        (1000, "down", KEY_RIGHT),
        (1500, "down", KEY_UP),  # a diagonal: the same walk
        (1600, "up", KEY_RIGHT),  # only up now: still the same walk
        (2000, "up", KEY_UP),
    )
    assert directions == [
        {"dx": 1, "dy": 0, "since": 1000},
        {"dx": 1, "dy": -1, "since": 1000},
        {"dx": 0, "dy": -1, "since": 1000},
        {"dx": 0, "dy": 0, "since": None},
    ]


def test_a_release_and_the_opposite_key_within_one_frame_is_a_new_walk():
    # 3 ms of (0, 0): no frame and no message falls into it, but `since` moves.
    directions = directions_after((1000, "down", KEY_RIGHT), (2000, "up", KEY_RIGHT), (2003, "down", KEY_LEFT))
    assert directions[0]["since"] == 1000
    assert directions[1] == {"dx": 0, "dy": 0, "since": None}
    assert directions[2] == {"dx": -1, "dy": 0, "since": 2003}


def test_opposite_keys_held_together_are_standing_and_end_the_walk():
    directions = directions_after(
        (1000, "down", KEY_RIGHT),
        (1500, "down", KEY_LEFT),  # 1 - 1 = 0: the server hears (0, 0)
        (1800, "up", KEY_RIGHT),  # left alone: a new walk
    )
    assert directions[1] == {"dx": 0, "dy": 0, "since": None}
    assert directions[2] == {"dx": -1, "dy": 0, "since": 1800}


def test_a_key_that_repeats_or_changes_nothing_keeps_since():
    directions = directions_after((1000, "down", KEY_RIGHT), (1400, "down", KEY_RIGHT), (1500, "down", "ArrowRight"))
    assert [direction["since"] for direction in directions] == [1000, 1000, 1000]


def test_stopping_the_world_forgets_since_and_the_next_walk_gets_its_own():
    steps = [
        ["key", 1000, "down", KEY_RIGHT],
        ["stop", 1500],
        ["direction", 1500],
        ["start", 1600],
        ["direction", 1600],
        ["key", 1700, "down", KEY_RIGHT],
        ["direction", 1700],
    ]
    standing = {"dx": 0, "dy": 0, "since": None}
    assert run_world(steps)["directions"] == [standing, standing, {"dx": 1, "dy": 0, "since": 1700}]


def test_the_server_still_hears_every_change_of_direction_once():
    steps = [
        ["key", 1000, "down", KEY_RIGHT],
        ["key", 1400, "down", KEY_RIGHT],  # the key repeats: nothing new
        ["key", 1500, "down", KEY_UP],
        ["key", 2000, "up", KEY_RIGHT],
        ["key", 2100, "up", KEY_UP],
    ]
    assert run_world(steps)["moves"] == [[1, 0], [1, -1], [0, -1], [0, 0]]


def test_the_diagnostic_sees_a_zero_shorter_than_a_frame_as_two_walks():
    # The player walks right, then lets go and presses "left" 3 ms later,
    # between two frames and between two messages. The messages go on at the
    # server's pace. Sampled only at frames and messages, this was one walk.
    key_at = 1000
    count = 60
    times = arrival_times(count, key_at + TICK, [0])
    turn_at = (times[29] + times[30]) / 2
    steps = [["positions", 0, [{"name": OWN, "x": SPAWN[0], "y": SPAWN[1]}]], ["key", key_at, "down", KEY_RIGHT]]
    steps += walk_right(times)
    steps += [["key", turn_at, "up", KEY_RIGHT], ["key", turn_at + 3, "down", KEY_LEFT]]
    result = run_world(with_frames(steps, until=times[-1]), debug=True)
    numbers = result["numbers"]

    # 60 messages: 29 gaps in the first walk, 29 in the second, and the one
    # across the turn does not count.
    assert numbers["walkingGaps"]["count"] == count - 2
    # The second walk began while the character was still moving: only the
    # first one is a start from standing.
    assert numbers["startDelay"]["count"] == 1
    # The first 400 ms of the second walk are not judged either.
    frames = result["frames"]
    judged = [f for f in frames[1:] if f["t"] - key_at >= WALK_SETTLE_MS and not turn_at + 3 <= f["t"] < turn_at + 3 + WALK_SETTLE_MS]
    assert numbers["walking"]["frames"] == len(judged)


def test_camera_stays_inside_map_while_the_player_keeps_moving():
    messages, end = six_second_walk(next(iter(DELIVERIES.values())))
    frames = run_world(with_frames(messages, until=end + 500), ask=[0])["frames"]
    drawn = [frame for frame in frames if frame.get("drawn")]
    assert drawn[-1]["drawn"]["x"] > drawn[-1]["camera"]["x"]
    assert all(130 <= frame["camera"]["x"] <= 550 for frame in drawn)


@pytest.mark.parametrize("x,y,expected", [
    (5, 5, (130, 81.25)),
    (675, 5, (550, 81.25)),
    (5, 663, (130, 586.75)),
    (675, 663, (550, 586.75)),
])
def test_camera_clamps_at_each_campus_corner_without_moving_the_player(x, y, expected):
    # The harness uses 800 x 500 pixels: a 260 x 162.5 map-unit view.
    steps = [["positions", 0, [{"name": OWN, "x": x, "y": y}]]]
    frames = run_world(with_frames(steps, until=200), ask=[0])["frames"]
    assert frames[-1]["camera"]["x"] == pytest.approx(expected[0])
    assert frames[-1]["camera"]["y"] == pytest.approx(expected[1])
    assert drawn_player(frames[-1]) == pytest.approx((x, y))
    assert place(frames[-1]["asked"][0]) == pytest.approx((x, y))
