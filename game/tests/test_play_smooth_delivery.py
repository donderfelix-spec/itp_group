"""To-do M2-1.14 "Walking stalls regularly on the deployed site", as repeatable tests.

On a real connection the `positions` messages arrive bunched: about every
410 ms one message is held back about 105 ms and arrives together with the
next one. With a glide of 110 ms from each arrival, the character and the
camera stood still about twice a second. client/js/world/world.js now puts
every position into a short queue per player and plays the queue back at the
server's pace, one tick per position, a little later: about one largest gap
behind the arrivals.

Like test_play_walking_glide.py, these tests run the page's own world.js in
Node (tests/world_glide_in_node.js): a test decides exactly when a message
arrives and when a frame is drawn, and reads where the camera looks and where
every character is drawn. Without Node the tests are skipped; CI has Node.
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
WORLD_IN_NODE = TESTS / "world_glide_in_node.js"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

CAMPUS = app.state.campus
SPAWN = (CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"])
USE_RANGE = CAMPUS["use_range"]

TICK = 1000 / TICKS_PER_SECOND  # ms between two positions messages of the server
FRAME = 1000 / 60  # ms between two frames of a 60 Hz screen
FRAME_OFFSET = 5  # the frames start a little after the first message

# Measured by the lead on Felix's connection to the deployed site: the server
# sent a message every 68.2 ms, 6.1 map units apart, and each one arrived this
# many ms later than the one before it would have on time (in a loop).
FELIX_TICK = 68.2
FELIX_STEP = 6.1
FELIX_DELAYS = [8.9, 1.7, 6.5, 3.3, 37.1, 2.0, 2.8, 0.6, 2.4, 37.2, 0.0, 105.8,
                37.6, 2.4, 1.2, 2.0, 2.9, 103.7, 37.5, 14.3, 2.1, 1.9, 1.7, 103.5]

# The playback delay is at most this long, so a position is drawn at the latest
# this long plus one tick after it arrived (see schedulePosition in world.js).
LONGEST_DELAY = 250
STRIDE_FADES = 150  # STRIDE_FADES_MILLISECONDS in world.js

# Less than this, in map units, is the same position: far below one pixel.
EXACT = 1e-6

# The i-th player of a lobby gets the i-th character: Mara the first, Tiago the second.
MARA = CHARACTERS[0]
TIAGO = CHARACTERS[1]


# ---- Helpers ---------------------------------------------------------------


def run_world(messages, until, players, own, start_of_round=None, usable=None):
    """Play `messages` [(t, [{name, x, y}, ...])] into world.js and draw frames until `until` ms.

    `players` are the names in the lobby; each gets its own character.
    Returns one dict per frame: {t, camera, glow, useButtonOn, characters}.
    """
    events = [(t, 0, ["positions", t, places]) for t, places in messages]
    if start_of_round is not None:
        events.append((start_of_round, 0, ["start_of_round", start_of_round]))
    t = FRAME_OFFSET
    while t <= until:
        events.append((t, 1, ["frames", t, t]))
        t += FRAME
    # A message that arrives at the same moment as a frame comes first.
    events.sort(key=lambda event: (event[0], event[1]))
    lobby = [{"name": name, "character": CHARACTERS[i]} for i, name in enumerate(players)]
    program = {"own": own, "players": lobby, "usable": usable, "steps": [event[2] for event in events]}
    finished = subprocess.run(
        [NODE, str(WORLD_IN_NODE)],
        input=json.dumps(program),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def delivered(places_per_message, tick, extra_delay):
    """Messages produced every `tick` ms; message k arrives `extra_delay(k)` ms later.

    A held-back message never overtakes an earlier one (TCP keeps the order).
    """
    messages = []
    last = -math.inf
    for k, places in enumerate(places_per_message):
        arrives = max(k * tick + extra_delay(k), last)
        messages.append((arrives, places))
        last = arrives
    return messages


def felix(places_per_message):
    """The messages as they arrived on Felix's connection."""
    return delivered(places_per_message, FELIX_TICK, lambda k: FELIX_DELAYS[k % len(FELIX_DELAYS)])


def on_time(places_per_message):
    return delivered(places_per_message, TICK, lambda k: 0)


def walk(name, messages, start, direction, step):
    """Positions of `name` walking from `start` in `direction` (dx, dy), one step per message."""
    return [{"name": name, "x": start[0] + direction[0] * step * k, "y": start[1] + direction[1] * step * k}
            for k in range(messages)]


def camera(frame):
    return (frame["camera"]["x"], frame["camera"]["y"])


def drawn(frame, character):
    """The character as drawn in this frame, or None."""
    return next((c for c in frame["characters"] if c["character"] == character), None)


def drawn_place(frame, character):
    c = drawn(frame, character)
    return (c["x"], c["middleY"])


def moves_per_frame(frames, position_of, start, end=math.inf):
    """How far `position_of(frame)` moved from the frame before, for frames with start <= t <= end."""
    return [math.dist(position_of(before), position_of(frame))
            for before, frame in zip(frames, frames[1:]) if start <= frame["t"] <= end]


def frames_between(frames, start, end=math.inf):
    return [frame for frame in frames if start <= frame["t"] <= end]


# ---- The bunched messages of the deployed site -----------------------------


@needs_node
def test_with_felix_bunched_messages_the_camera_never_stalls_after_the_first_three_seconds():
    count = 160  # 160 x 68.2 ms: almost 11 s of walking
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), FELIX_STEP)]
    messages = felix(places)
    frames = run_world(messages, until=messages[-1][0], players=["Mara"], own="Mara")

    normal = FELIX_STEP / FELIX_TICK * FRAME  # about 1.5 units per frame
    moves = moves_per_frame(frames, camera, 3000)
    assert len(moves) > 400
    # Never standing still, never slower than half the normal speed.
    assert min(moves) >= normal / 2, min(moves)
    # And never a jump: at most the fastest playback (1.25 x) plus a little.
    assert max(moves) < 1.5 * normal, max(moves)


@needs_node
def test_with_felix_bunched_messages_the_camera_never_moves_backwards():
    count = 100
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), FELIX_STEP)]
    messages = felix(places)
    frames = run_world(messages, until=messages[-1][0] + 500, players=["Mara"], own="Mara")

    xs = [frame["camera"]["x"] for frame in frames]
    assert all(a <= b + EXACT for a, b in zip(xs, xs[1:]))
    # The drawn character is where the camera looks, from the first position on.
    shown = frames_between(frames, messages[0][0])
    assert all(abs(drawn(frame, MARA)["x"] - frame["camera"]["x"]) < EXACT for frame in shown)


@needs_node
def test_eight_players_walking_with_bunched_messages_all_move_in_every_frame():
    names = ["Mara", "Tiago", "Ines", "Rui", "Ana", "Joao", "Rita", "Luis"]
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)]
    count = 100  # almost 7 s
    walks = [walk(name, count, (300 + 40 * i, 300 + 30 * i), direction, FELIX_STEP / math.hypot(*direction))
             for i, (name, direction) in enumerate(zip(names, directions))]
    messages = felix([list(places) for places in zip(*walks)])
    frames = run_world(messages, until=messages[-1][0], players=names, own="Mara")

    normal = FELIX_STEP / FELIX_TICK * FRAME
    for character in CHARACTERS[:len(names)]:
        moves = moves_per_frame(frames, lambda frame: drawn_place(frame, character), 3000)
        assert len(moves) > 200
        assert min(moves) >= normal / 2, (character, min(moves))


# ---- Messages on time ------------------------------------------------------


@needs_node
def test_with_messages_on_time_the_camera_moves_the_same_distance_in_every_frame():
    count = 60
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), 6)]
    messages = on_time(places)
    frames = run_world(messages, until=messages[-1][0], players=["Mara"], own="Mara")

    # After the start: the first step is drawn over one whole delay (110 ms).
    moves = moves_per_frame(frames, camera, messages[1][0] + 110 + FRAME)
    normal = 6 / TICK * FRAME
    assert all(abs(move - normal) <= 0.1 * normal for move in moves), (min(moves), max(moves))


# ---- Start, stop and standing ----------------------------------------------


@needs_node
def test_a_walk_starts_in_the_first_frame_after_the_first_step_and_never_goes_backwards():
    # Placed on the spawn, standing for a second (the server sends nothing),
    # then walking right.
    count = 30
    steps = walk("Mara", count, SPAWN, (1, 0), 6)
    first_step_at = 1000
    messages = [(0, [steps[0]])] + [(first_step_at + k * TICK, [place]) for k, place in enumerate(steps[1:])]
    frames = run_world(messages, until=messages[-1][0] + 500, players=["Mara"], own="Mara")

    before = frames_between(frames, 0, first_step_at - EXACT)
    assert all(math.dist(camera(frame), SPAWN) < EXACT for frame in before)
    first_after = frames_between(frames, first_step_at)[0]
    assert first_after["t"] - first_step_at < FRAME
    # No added wait: the camera has already left the spawn in this frame.
    assert first_after["camera"]["x"] > SPAWN[0] + 0.01
    xs = [frame["camera"]["x"] for frame in frames]
    assert all(a <= b + EXACT for a, b in zip(xs, xs[1:]))


@needs_node
def test_a_stop_reaches_the_last_server_position_exactly_in_time_without_overshooting():
    count = 80
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), FELIX_STEP)]
    messages = felix(places)
    last_at = messages[-1][0]
    last = (places[-1][0]["x"], places[-1][0]["y"])
    frames = run_world(messages, until=last_at + 1500, players=["Mara"], own="Mara")

    # Never past the last server position.
    assert all(frame["camera"]["x"] <= last[0] + EXACT for frame in frames)
    # There at the latest the longest delay plus one tick after the last message.
    reached = [frame for frame in frames if math.dist(camera(frame), last) < EXACT]
    assert reached and reached[0]["t"] <= last_at + LONGEST_DELAY + TICK
    # And from then on it stays there.
    assert all(math.dist(camera(frame), last) < EXACT for frame in frames_between(frames, reached[0]["t"]))
    # The feet stop once the steps have faded.
    still = [drawn(frame, MARA) for frame in frames_between(frames, reached[0]["t"] + STRIDE_FADES + FRAME)]
    assert still and all(c["stride"] == 0 and c["walkPhase"] is None for c in still)
    # While the character still moved, its feet did too.
    moving = [drawn(frame, MARA) for frame in frames_between(frames, 3000, reached[0]["t"] - FRAME)]
    assert moving and all(c["stride"] > 0 for c in moving)


@needs_node
def test_without_messages_for_two_seconds_nothing_moves():
    # Mara and Tiago are placed; then the server sends nothing for 2 s.
    placed = [(0, [{"name": "Mara", "x": SPAWN[0], "y": SPAWN[1]}, {"name": "Tiago", "x": 400, "y": 500}])]
    frames = run_world(placed, until=2000, players=["Mara", "Tiago"], own="Mara")

    for frame in frames:
        assert math.dist(camera(frame), SPAWN) < EXACT
        assert drawn(frame, TIAGO)["x"] == 400
        assert all(c["stride"] == 0 and c["walkPhase"] is None for c in frame["characters"])


@needs_node
def test_after_a_walk_and_two_seconds_without_messages_nothing_moves():
    count = 30
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), FELIX_STEP)]
    messages = felix(places)
    last_at = messages[-1][0]
    frames = run_world(messages, until=last_at + 2000, players=["Mara"], own="Mara")

    settled = frames_between(frames, last_at + LONGEST_DELAY + TICK + STRIDE_FADES)
    assert len(settled) > 90
    assert all(camera(frame) == camera(settled[0]) for frame in settled)
    assert all(drawn(frame, MARA)["stride"] == 0 for frame in settled)


# ---- Stations -----------------------------------------------------------------


@needs_node
def test_the_station_glow_follows_the_newest_server_position_while_the_drawing_is_behind():
    station = next(s for s in CAMPUS["stations"] if s["id"] == 2)
    # Mara walks left along the row of the station, past it, with the
    # bunched messages.
    start = (station["x"] + 80, station["y"])
    places = [[place] for place in walk("Mara", 30, start, (-1, 0), FELIX_STEP)]
    messages = felix(places)
    frames = run_world(messages, until=messages[-1][0] + 500, players=["Mara"], own="Mara",
                       usable=[station["id"]])

    def newest_server_place(frame):
        arrived = [places for t, places in messages if t <= frame["t"]]
        return (arrived[-1][0]["x"], arrived[-1][0]["y"]) if arrived else None

    def in_range(place):
        if place is None:
            return False  # no position yet: nothing glows
        return (place[0] - station["x"]) ** 2 + (place[1] - station["y"]) ** 2 <= USE_RANGE ** 2

    glowing_while_drawn_outside = 0
    for frame in frames:
        server_says = in_range(newest_server_place(frame))
        assert (frame["glow"] == station["id"]) == server_says, frame["t"]
        assert frame["useButtonOn"] == server_says, frame["t"]
        if server_says and not in_range(camera(frame)):
            glowing_while_drawn_outside += 1
    # The drawing is behind, and the glow did not wait for it.
    assert glowing_while_drawn_outside > 0


# ---- Jumps and the start of a round -----------------------------------------


@needs_node
def test_a_respawn_far_away_is_drawn_in_the_next_frame_without_waiting_for_the_queue():
    count = 40
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), FELIX_STEP)]
    messages = felix(places)
    respawn = (SPAWN[0] - 200, SPAWN[1] + 100)
    respawn_at = messages[-1][0] + 1  # positions of the walk are still queued
    messages.append((respawn_at, [{"name": "Mara", "x": respawn[0], "y": respawn[1]}]))
    frames = run_world(messages, until=respawn_at + 500, players=["Mara"], own="Mara")

    before = frames_between(frames, 0, respawn_at - EXACT)
    assert math.dist(camera(before[-1]), (places[-1][0]["x"], places[-1][0]["y"])) > 1  # still behind
    after = frames_between(frames, respawn_at)
    assert after[0]["t"] - respawn_at < FRAME
    for frame in after:
        assert math.dist(camera(frame), respawn) < EXACT
        mara = drawn(frame, MARA)
        assert mara["stride"] == 0 and mara["walkPhase"] is None and mara["mirrored"] is False


@needs_node
def test_the_start_of_a_round_puts_a_nearby_character_on_the_spawn_in_one_frame():
    # Tiago walks left towards the spawn and ends 18 units right of it, closer
    # than a jump. Mara walks with him. The round starts while positions are
    # still queued, and the next tick puts both on the spawn.
    count = 30
    tiago_start = (SPAWN[0] + 18 + FELIX_STEP * (count - 1), SPAWN[1])
    tiago = walk("Tiago", count, tiago_start, (-1, 0), FELIX_STEP)
    mara = walk("Mara", count, (SPAWN[0] - 40, SPAWN[1] + 30), (0, 1), FELIX_STEP)
    messages = felix([[m, t] for m, t in zip(mara, tiago)])
    round_at = messages[-1][0] + 1
    back = round_at + TICK
    messages.append((back, [{"name": "Mara", "x": SPAWN[0], "y": SPAWN[1]},
                            {"name": "Tiago", "x": SPAWN[0], "y": SPAWN[1]}]))
    frames = run_world(messages, until=back + 500, players=["Mara", "Tiago"], own="Mara",
                       start_of_round=round_at)

    before = frames_between(frames, 0, round_at - EXACT)
    assert drawn(before[-1], TIAGO)["mirrored"] is True  # Tiago faced left
    after = frames_between(frames, back)
    assert after[0]["t"] - back < FRAME
    for frame in after:
        for character in (MARA, TIAGO):
            c = drawn(frame, character)
            assert math.dist((c["x"], c["middleY"]), drawn_place(after[0], character)) < EXACT
            assert abs(c["x"] - SPAWN[0]) < EXACT
            assert c["mirrored"] is False
            assert c["stride"] == 0 and c["walkPhase"] is None
    assert math.dist(camera(after[0]), SPAWN) < EXACT
