"""The play test of to-do M2-1.12 "The picture stutters while walking", as repeatable tests.

Each character glides from where it is drawn to every new server position
over GLIDE_MILLISECONDS (client/js/world/world.js), and the camera follows the
own drawn character. The tester played this in several browsers behind a proxy
that delays the messages like the internet does. What was checked there is
checked here without a browser and without a proxy:

- The page's own world.js runs in Node (tests/world_glide_in_node.js). The clock,
  the frames and the canvas are stand-ins, so a test decides exactly when a
  `positions` message arrives and when a frame is drawn, and reads where the
  camera looks and where every character is drawn.
- A walk recorded from the real server, with the real tick, is played into
  the same world.js.

test_walking_glide.py checks the number itself; these tests check what the
page draws with it: the camera keeps moving when a message is up to 40 ms
late, two messages at once make no jump, a stop ends exactly on the last
server position, the start of a round puts characters on the spawn in one
frame, and a station glows from the server position, not the drawn one.

Without Node the tests are skipped; CI has Node.
"""

import contextlib
import json
from world_tracking import with_tracked_player

import math
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.main import TICKS_PER_SECOND, app

TESTS = Path(__file__).resolve().parent
WORLD_IN_NODE = TESTS / "world_glide_in_node.js"
WORLD_JS = TESTS.parent / "client" / "js" / "world" / "world.js"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

CAMPUS = app.state.campus
SPAWN = (CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"])
USE_RANGE = CAMPUS["use_range"]

TICK = 1000 / TICKS_PER_SECOND  # ms between two positions messages of the server
FRAME = 1000 / 60  # ms between two frames of a 60 Hz screen
STEP = 6  # map units a walking player moves in one tick (90 units per second)
# The frames start a little after the first message, as they would in a browser.
FRAME_OFFSET = 5

# A frame in which the camera moves less than this stands still (the same
# limit the tester used in the browser).
STANDING_STILL = 0.05
# Less than this, in map units, is the same position: far below one pixel.
EXACT = 1e-6


def world_js_number(name):
    """A number written as `var NAME = number;` in world.js."""
    match = re.search(rf"var {name} = ([\d.]+);", WORLD_JS.read_text(encoding="utf-8"))
    assert match, name
    return float(match.group(1))


# How long a glide lasts, and how long the steps take to fade after it.
GLIDE = world_js_number("GLIDE_MILLISECONDS")
STRIDE_FADES = world_js_number("STRIDE_FADES_MILLISECONDS")

PLAYERS = [
    {"name": "Mara", "character": "student"},
    {"name": "Tiago", "character": "professor"},
]


# ---- Helpers ---------------------------------------------------------------


def run_world(messages, until, start_of_round=None, usable=None, own="Mara", players=None):
    """Play `messages` [(t, [{name, x, y}, ...])] into world.js and draw frames until `until` ms.

    Returns one dict per frame: {t, tracked_position, glow, useButtonOn, characters}.
    """
    events = [(t, 0, ["positions", t, players]) for t, players in messages]
    if start_of_round is not None:
        events.append((start_of_round, 0, ["start_of_round", start_of_round]))
    t = FRAME_OFFSET
    while t <= until:
        events.append((t, 1, ["frames", t, t]))
        t += FRAME
    events.sort(key=lambda event: (event[0], event[1]))
    program = {"own": own, "players": players or PLAYERS, "usable": usable, "steps": [event[2] for event in events]}
    finished = subprocess.run(
        [NODE, str(WORLD_IN_NODE)],
        input=json.dumps(program),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return with_tracked_player(json.loads(finished.stdout), program["players"], own)


def drawn(frame, name):
    """The character of `name` as drawn in this frame, or None."""
    character = next(player["character"] for player in PLAYERS if player["name"] == name)
    return next((drawn for drawn in frame["characters"] if drawn["character"] == character), None)


def walk_right(name, ticks, start_x=SPAWN[0], y=SPAWN[1]):
    """The positions of `name` walking right for `ticks` ticks: one per tick, STEP apart."""
    return [{"name": name, "x": start_x + STEP * k, "y": y} for k in range(ticks + 1)]


def on_time(places_per_tick, late=None):
    """Messages at every tick. `late(k)` gives how many ms message k arrives late (default 0).

    A late message never overtakes the next one (TCP keeps the order).
    """
    messages = []
    last = -math.inf
    for k, players in enumerate(places_per_tick):
        arrives = max(k * TICK + (late(k) if late else 0), last)
        messages.append((arrives, players))
        last = arrives
    return messages


def moves_per_frame(frames, position_of, start, end):
    """How far `position_of(frame)` moved from the frame before, for frames with start <= t <= end."""
    moves = []
    for before, frame in zip(frames, frames[1:]):
        if start <= frame["t"] <= end:
            a, b = position_of(before), position_of(frame)
            moves.append(math.hypot(b[0] - a[0], b[1] - a[1]))
    return moves


def tracked_position(frame):
    return (frame["tracked"]["x"], frame["tracked"]["y"])


# ---- The own character and the camera ----------------------------------


@needs_node
def test_the_player_moves_in_every_frame_while_the_messages_come_on_time():
    ticks = 30
    places = [[place] for place in walk_right("Mara", ticks)]
    frames = run_world(on_time(places), until=ticks * TICK)

    # From the second message on, until the last one has arrived.
    moves = moves_per_frame(frames, tracked_position, TICK + FRAME, ticks * TICK)
    assert min(moves) > STANDING_STILL, moves


@needs_node
def test_the_player_moves_in_every_frame_when_every_third_message_is_40_ms_late():
    # This is the stutter of M2-1.12: with a glide of one tick (67 ms) the
    # camera stood still for about 40 ms before each late message.
    ticks = 30
    places = [[place] for place in walk_right("Mara", ticks)]
    messages = on_time(places, late=lambda k: 40 if k % 3 == 2 else 0)
    frames = run_world(messages, until=ticks * TICK)

    moves = moves_per_frame(frames, tracked_position, TICK + FRAME, ticks * TICK)
    assert min(moves) > STANDING_STILL, moves


@needs_node
def test_two_messages_that_arrive_together_make_no_jump():
    # A message held back by a whole tick arrives together with the next one.
    ticks = 30
    places = [[place] for place in walk_right("Mara", ticks)]
    messages = on_time(places, late=lambda k: TICK if k in (8, 17, 25) else 0)
    frames = run_world(messages, until=ticks * TICK + 300)

    moves = moves_per_frame(frames, tracked_position, TICK + FRAME, ticks * TICK + 300)
    normal = STEP / TICK * FRAME  # 1.5 units per frame
    # Never a jump: the camera catches up over several frames, at most about
    # twice the normal speed, never a whole step (6 units) in one frame.
    assert max(moves) < 2.5 * normal, max(moves)
    # And it really arrives at the last position.
    assert math.dist(tracked_position(frames[-1]), (places[-1][0]["x"], places[-1][0]["y"])) < EXACT


@needs_node
def test_a_stop_ends_exactly_on_the_last_server_position_and_the_feet_stand_still():
    # Nobody else walks: after the last step no message comes any more.
    ticks = 15
    places = [[place] for place in walk_right("Mara", ticks)]
    messages = on_time(places)
    last_at = messages[-1][0]
    last = (places[-1][0]["x"], places[-1][0]["y"])
    frames = run_world(messages, until=last_at + 1000)

    after_glide = [frame for frame in frames if frame["t"] >= last_at + GLIDE]
    assert all(math.dist(tracked_position(frame), last) < EXACT for frame in after_glide)
    # The tracked position is the actual own character drawing.
    assert all(abs(drawn(frame, "Mara")["x"] - frame["tracked"]["x"]) < EXACT for frame in frames)
    # Before the glide is over it is still on the way, never past the end.
    on_the_way = [frame for frame in frames if last_at <= frame["t"] < last_at + GLIDE]
    assert on_the_way and all(frame["tracked"]["x"] < last[0] for frame in on_the_way)
    # The feet: still once the steps have faded.
    feet_still = [drawn(frame, "Mara") for frame in frames if frame["t"] >= last_at + GLIDE + STRIDE_FADES]
    assert feet_still and all(mara["stride"] == 0 and mara["walkPhase"] is None for mara in feet_still)


@needs_node
def test_a_stop_while_another_player_walks_eases_onto_the_last_position_without_overshooting():
    # Tiago walks on, so every tick brings a message with Mara's same place:
    # each one starts a new glide from where she is drawn, a soft ease-out.
    ticks_walking, ticks_after = 15, 30
    mara = walk_right("Mara", ticks_walking)
    mara += [mara[-1]] * ticks_after
    tiago = walk_right("Tiago", ticks_walking + ticks_after, start_x=100, y=500)
    messages = on_time([[m, t] for m, t in zip(mara, tiago)])
    last_step_at = messages[ticks_walking][0]
    last = (mara[-1]["x"], mara[-1]["y"])
    frames = run_world(messages, until=messages[-1][0])

    after = [frame for frame in frames if frame["t"] >= last_step_at]
    xs = [frame["tracked"]["x"] for frame in after]
    # Always closer, never past the place the server says.
    assert all(a <= b + EXACT for a, b in zip(xs, xs[1:])), xs
    assert all(x <= last[0] + EXACT for x in xs)
    left_after = lambda ms: last[0] - next(frame["tracked"]["x"] for frame in after if frame["t"] >= last_step_at + ms)
    # About 2 units are left after one glide, half a unit after 200 ms,
    # less than a pixel (a fifth of a unit) after 300 ms.
    assert left_after(GLIDE) < 2.5
    assert left_after(300) < 0.2
    assert left_after(600) < 0.01
    # The feet stand still at the same moment as without Tiago.
    feet_still = [drawn(frame, "Mara") for frame in after if frame["t"] >= last_step_at + GLIDE + STRIDE_FADES]
    assert feet_still and all(m["stride"] == 0 and m["walkPhase"] is None for m in feet_still)


# ---- Other characters --------------------------------------------------


@needs_node
def test_another_walking_character_also_moves_in_every_frame_when_messages_are_late():
    ticks = 30
    tiago = walk_right("Tiago", ticks, start_x=420)
    places = [[{"name": "Mara", "x": SPAWN[0], "y": SPAWN[1]}, place] for place in tiago]
    messages = on_time(places, late=lambda k: 40 if k % 3 == 1 else 0)
    frames = run_world(messages, until=ticks * TICK)

    tiago_drawn = lambda frame: (drawn(frame, "Tiago")["x"], drawn(frame, "Tiago")["middleY"])
    # From the first step on (message 1 is late itself).
    moves = moves_per_frame(frames, tiago_drawn, TICK + 40 + FRAME, ticks * TICK)
    assert min(moves) > STANDING_STILL, moves
    # Mara stood still the whole time: her camera never moved.
    assert all(math.dist(tracked_position(frame), SPAWN) < EXACT for frame in frames)


# ---- The start of a round ----------------------------------------------


@needs_node
def test_the_start_of_a_round_puts_far_and_near_characters_on_the_spawn_in_one_frame_facing_right():
    # Mara walked far to the right, Tiago a little to the left (closer to the
    # spawn than a jump, 60 units), so he faces left.
    mara = walk_right("Mara", 20)  # ends 120 units right of the spawn
    tiago = [{"name": "Tiago", "x": SPAWN[0] - STEP * k, "y": SPAWN[1]} for k in range(8)]
    tiago += [tiago[-1]] * (len(mara) - len(tiago))
    messages = on_time([[m, t] for m, t in zip(mara, tiago)])
    round_at = messages[-1][0] + 1000
    back = round_at + TICK  # the next tick puts them on the spawn
    messages.append((back, [{"name": "Mara", "x": SPAWN[0], "y": SPAWN[1]},
                            {"name": "Tiago", "x": SPAWN[0], "y": SPAWN[1]}]))
    frames = run_world(messages, until=back + 500, start_of_round=round_at)

    before = [frame for frame in frames if frame["t"] < round_at]
    after = [frame for frame in frames if frame["t"] >= back]
    assert drawn(before[-1], "Tiago")["mirrored"] is True  # he faced left
    first_x = {name: drawn(before[-1], name)["x"] for name in ("Mara", "Tiago")}
    assert first_x == {"Mara": mara[-1]["x"], "Tiago": tiago[-1]["x"]}
    for frame in after:
        for name in ("Mara", "Tiago"):
            character = drawn(frame, name)
            # On the spawn from the first frame on: no frame in between.
            assert abs(character["x"] - SPAWN[0]) < EXACT, (name, frame["t"], character["x"])
            assert character["mirrored"] is False
            assert character["stride"] == 0 and character["walkPhase"] is None
    assert math.dist(tracked_position(after[0]), SPAWN) < EXACT


# ---- Stations ----------------------------------------------------------


@needs_node
def test_a_station_glows_from_the_server_position_while_the_drawn_character_still_glides():
    station = next(s for s in CAMPUS["stations"] if s["id"] == 2)
    # Mara walks left towards the station along its row, past it and stops.
    start_x = station["x"] + 60
    places = [[{"name": "Mara", "x": start_x - STEP * k, "y": station["y"]}] for k in range(21)]
    messages = on_time(places, late=lambda k: 40 if k % 3 == 2 else 0)
    frames = run_world(messages, until=messages[-1][0] + 500, usable=[station["id"]])

    def server_place(frame):
        arrived = [players for t, players in messages if t <= frame["t"]]
        return (arrived[-1][0]["x"], arrived[-1][0]["y"])

    def in_range(place):
        return (place[0] - station["x"]) ** 2 + (place[1] - station["y"]) ** 2 <= USE_RANGE ** 2

    glowing_while_drawn_outside = 0
    for frame in frames:
        server_says = in_range(server_place(frame))
        assert (frame["glow"] == station["id"]) == server_says, frame["t"]
        assert frame["useButtonOn"] == server_says, frame["t"]
        if server_says and not in_range(tracked_position(frame)):
            glowing_while_drawn_outside += 1
    # The drawn character lags behind, and the glow did not wait for it.
    assert glowing_while_drawn_outside > 0


@needs_node
def test_a_station_that_may_not_be_used_never_glows():
    station = next(s for s in CAMPUS["stations"] if s["id"] == 2)
    places = [[{"name": "Mara", "x": station["x"] + 30 - STEP * k, "y": station["y"]}] for k in range(11)]
    frames = run_world(on_time(places), until=11 * TICK, usable=[1])

    assert all(frame["glow"] is None and not frame["useButtonOn"] for frame in frames)


# ---- A walk from the real server ---------------------------------------


@pytest.fixture(autouse=True)
def quiet_tick():
    """Replaces the fixture of the same name in conftest.py: here the real tick runs."""


@pytest.fixture
def connect():
    # As a context manager the test client starts the server properly, so the tick loop runs.
    with TestClient(app) as client, contextlib.ExitStack() as open_connections:
        yield lambda: open_connections.enter_context(client.websocket_connect("/ws"))


def guest(connection):
    connection.send_json({"type": "guest"})
    while True:
        message = connection.receive_json()
        if message["type"] == "signed_in":
            return message["name"]


def next_message_of_type(connection, kind):
    while True:
        message = connection.receive_json()
        if message["type"] == kind:
            return message


@needs_node
def test_a_walk_from_the_real_server_is_drawn_without_a_jump_and_ends_on_its_last_position(connect):
    walker = connect()
    name = guest(walker)
    walker.send_json({"type": "create_lobby"})
    next_message_of_type(walker, "lobby_state")
    placed = next_message_of_type(walker, "positions")  # placed on the spawn

    # Walk right for about a second, writing down when each message arrives.
    walker.send_json({"type": "move", "dx": 1, "dy": 0})
    started = time.monotonic()
    received = [(0, placed["players"])]
    while time.monotonic() - started < 1.0:
        message = next_message_of_type(walker, "positions")
        received.append(((time.monotonic() - started) * 1000, message["players"]))
    walker.send_json({"type": "move", "dx": 0, "dy": 0})
    last = next(p for p in received[-1][1] if p["name"] == name)

    frames = run_world(received, until=received[-1][0] + 500, own=name,
                       players=[{"name": name, "character": "student"}])

    moves = moves_per_frame(frames, tracked_position, 0, received[-1][0] + 500)
    # Never a whole step in one frame, however the messages came.
    assert max(moves) < STEP, max(moves)
    assert math.dist(tracked_position(frames[-1]), (last["x"], last["y"])) < EXACT
    # The server walked one straight line to the right, in real steps.
    xs = [next(p for p in players if p["name"] == name)["x"] for _, players in received]
    assert all(0 <= b - a <= 9.11 for a, b in zip(xs, xs[1:])), xs
