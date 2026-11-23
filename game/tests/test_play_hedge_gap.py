"""The play test of to-do M1-1.5 "hedge gap", as repeatable tests.

`test_hedge_gap.py` checks the map and the walking rules on their own. Here
the same walks are played over WebSocket connections against the real server
with the real tick, the way a tester played them in two browser tabs: one
player walks into the place where the hedge meets the deck's right wall, a
second player in the same lobby watches. Both must be told the same
positions, and in no message may the walker stand inside the hedge, inside
the wall or in the 10-unit strip between them. (Until M3-1.7 the hedge lay
left to right and met tree 3; since S-196 it stands upright along the right
wall, and the closed gap moved with it.)

Walking from the spawn to the hedge with keys would take seconds and land on
a different spot each time, so each test puts the walker where the walk
starts (as `task_helpers.put` does for the stations) and then walks with
real `move` messages.

Like `test_hedge_gap.py`, these tests are about a solid hedge (S-87). Since
M3-1.4 the hedge is a walkable hiding place (S-98), so the server runs them
on a copy of the real map with the hedge made solid again. Walking into the
walkable hedge is tested in `test_hiding_visibility.py`.
"""

import contextlib
import copy
import time

import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.world.movement import PLAYER_HALF_SIZE, is_free, overlaps
from task_helpers import put

PASSWORD = "password123"
# Historical closed-hedge scenario; current hiding has separate live-map tests.
CAMPUS = copy.deepcopy(app.state.campus)
next(solid for solid in CAMPUS["solids"] if solid["id"] == "deck-hedge")["walkable"] = False
SOLIDS = CAMPUS["solids"]
WALL = next(item for item in SOLIDS if item["id"] == "deck-wall-right")
HEDGE = next(item for item in SOLIDS if item["id"] == "deck-hedge")

# The strip a hedge 10 units narrower would leave at the wall: from x 647 to
# the wall (x 657), as high as the hedge (y 255 to 323).
WALL_GAP = {"x": 647, "y": 255, "w": 10, "h": 68}
# The middle of that strip: the one x where a player would fit into it,
# touching the wall.
GAP_MIDDLE_X = WALL_GAP["x"] + WALL_GAP["w"] / 2

# Generous: every walk here takes less than two seconds.
DEADLINE_SECONDS = 15.0
# Long enough for several ticks. Used only to see that nothing more arrives.
QUIET_SECONDS = 0.4


@pytest.fixture(autouse=True)
def quiet_tick():
    """Replaces the fixture of the same name in conftest.py: here the real tick runs."""


@pytest.fixture(autouse=True)
def closed_hedge_scenario():
    original = app.state.campus
    app.state.campus = CAMPUS
    try:
        yield
    finally:
        app.state.campus = original


@pytest.fixture
def client():
    # As a context manager the test client starts the server properly, so the tick loop runs.
    with TestClient(app) as shared_client:
        yield shared_client


@pytest.fixture
def connect(client):
    """A function that opens one more connection. All of them are closed after the test."""
    with contextlib.ExitStack() as open_connections:
        yield lambda: open_connections.enter_context(client.websocket_connect("/ws"))


# Helpers


def ask(connection, message):
    """Send one message and return the next message the server sends."""
    connection.send_json(message)
    return connection.receive_json()


def waiting_messages(connection):
    """Everything the server has sent this connection and the test has not read yet.

    A hello is sent and everything up to its answer is collected, so this
    never waits forever, even when nothing was sent.
    """
    connection.send_json({"type": "hello", "name": "Reader"})
    messages = []
    while True:
        message = connection.receive_json()
        if message["type"] == "welcome":
            return messages
        messages.append(message)


def as_positions(messages):
    """The `positions` messages among these, as {name: (x, y)} dicts."""
    return [
        {listed["name"]: (listed["x"], listed["y"]) for listed in message["players"]}
        for message in messages
        if message["type"] == "positions"
    ]


def read_until_quiet(connection):
    """Read this player's positions until none arrive any more. Returns all of them, in order."""
    deadline = time.monotonic() + DEADLINE_SECONDS
    everything = as_positions(waiting_messages(connection))
    while True:
        time.sleep(QUIET_SECONDS)
        arrived_meanwhile = as_positions(waiting_messages(connection))
        if not arrived_meanwhile:
            return everything
        everything.extend(arrived_meanwhile)
        assert time.monotonic() < deadline, "the positions did not stop arriving"


def move(connection, dx, dy):
    connection.send_json({"type": "move", "dx": dx, "dy": dy})


def walker_and_watcher(connect):
    """Mara creates a lobby and a guest joins it. Returns (mara, watcher), both told everything so far."""
    mara = connect()
    assert ask(mara, {"type": "sign_up", "name": "Mara", "password": PASSWORD})["type"] == "signed_in"
    watcher = connect()
    assert ask(watcher, {"type": "guest"})["type"] == "signed_in"
    code = ask(mara, {"type": "create_lobby"})["code"]
    watcher.send_json({"type": "join_lobby", "code": code})
    # Both have been placed on the spawn once the first positions arrive.
    read_until_quiet(mara)
    read_until_quiet(watcher)
    return mara, watcher


def walk_from(connect, start, dx, dy):
    """Mara starts at `start` and walks in one direction until she is stuck.

    Returns the trail of Mara's positions as each of the two players was told it.
    """
    mara, watcher = walker_and_watcher(connect)
    put("Mara", start)
    move(mara, dx, dy)
    trails = []
    for connection in (mara, watcher):
        trails.append([positions["Mara"] for positions in read_until_quiet(connection)])
    move(mara, 0, 0)
    return trails


def assert_never_in_the_hedge_the_wall_or_the_gap(trail):
    assert trail, "the walker was never seen walking"
    for x, y in trail:
        assert is_free(x, y, SOLIDS, CAMPUS["width"], CAMPUS["height"]), (x, y)
        assert not overlaps(x, y, WALL_GAP), (x, y)


# Straight walks along the wall into the hedge


def test_walking_up_along_the_wall_stops_under_the_hedge_for_both_players(connect):
    for_mara, for_watcher = walk_from(connect, (GAP_MIDDLE_X, 360), 0, -1)
    assert for_mara == for_watcher
    assert_never_in_the_hedge_the_wall_or_the_gap(for_mara)
    assert for_mara[-1] == (GAP_MIDDLE_X, HEDGE["y"] + HEDGE["h"] + PLAYER_HALF_SIZE)


def test_walking_down_along_the_wall_stops_on_the_hedge_for_both_players(connect):
    for_mara, for_watcher = walk_from(connect, (GAP_MIDDLE_X, 205), 0, 1)
    assert for_mara == for_watcher
    assert_never_in_the_hedge_the_wall_or_the_gap(for_mara)
    assert for_mara[-1] == (GAP_MIDDLE_X, HEDGE["y"] - PLAYER_HALF_SIZE)


# Diagonal walks into the corners where the hedge and the wall meet


def test_up_and_right_from_below_left_ends_in_the_corner_under_hedge_and_wall(connect):
    for_mara, for_watcher = walk_from(connect, (590, 380), 1, -1)
    assert for_mara == for_watcher
    assert_never_in_the_hedge_the_wall_or_the_gap(for_mara)
    # Touching the bottom of the hedge and the wall.
    assert for_mara[-1] == (WALL["x"] - PLAYER_HALF_SIZE, HEDGE["y"] + HEDGE["h"] + PLAYER_HALF_SIZE)


def test_down_and_right_from_above_left_ends_in_the_corner_on_hedge_and_wall(connect):
    # A diagonal step moves x and y by the same amount, so from here she
    # reaches the top of the hedge (y 250) at x 644, over the hedge, and
    # slides along it to the wall.
    for_mara, for_watcher = walk_from(connect, (600, 206), 1, 1)
    assert for_mara == for_watcher
    assert_never_in_the_hedge_the_wall_or_the_gap(for_mara)
    # Touching the top of the hedge and the wall.
    assert for_mara[-1] == (WALL["x"] - PLAYER_HALF_SIZE, HEDGE["y"] - PLAYER_HALF_SIZE)


def test_up_and_left_from_below_the_hedge_only_passes_on_its_left_side(connect):
    for_mara, for_watcher = walk_from(connect, (650, 340), -1, -1)
    assert for_mara == for_watcher
    assert_never_in_the_hedge_the_wall_or_the_gap(for_mara)
    # She slides along under the hedge and goes up only left of it.
    for x, y in for_mara:
        if y < HEDGE["y"] + HEDGE["h"] + PLAYER_HALF_SIZE:
            assert x <= HEDGE["x"] - PLAYER_HALF_SIZE, (x, y)
    assert min(y for _, y in for_mara) < HEDGE["y"] - PLAYER_HALF_SIZE


def test_down_and_left_from_above_the_hedge_only_passes_on_its_left_side(connect):
    for_mara, for_watcher = walk_from(connect, (650, 230), -1, 1)
    assert for_mara == for_watcher
    assert_never_in_the_hedge_the_wall_or_the_gap(for_mara)
    # She slides along over the hedge and goes down only left of it.
    for x, y in for_mara:
        if y > HEDGE["y"] - PLAYER_HALF_SIZE:
            assert x <= HEDGE["x"] - PLAYER_HALF_SIZE, (x, y)
    assert max(y for _, y in for_mara) > HEDGE["y"] + HEDGE["h"] + PLAYER_HALF_SIZE


# Trying to break it


def test_pushing_on_in_the_corner_and_switching_fast_never_gets_into_the_hedge(connect):
    mara, watcher = walker_and_watcher(connect)
    corner = (WALL["x"] - PLAYER_HALF_SIZE, HEDGE["y"] + HEDGE["h"] + PLAYER_HALF_SIZE)
    put("Mara", corner)
    # Every direction that points into the hedge or the wall, many times and
    # without any pause, then the same direction twice in a row.
    for _ in range(30):
        for dx, dy in ((0, -1), (1, -1), (-1, -1), (1, 0), (0, -1), (0, -1)):
            move(mara, dx, dy)
    seen = read_until_quiet(watcher)
    move(mara, 0, 0)
    trail = [positions["Mara"] for positions in seen]
    for x, y in trail:
        assert is_free(x, y, SOLIDS, CAMPUS["width"], CAMPUS["height"]), (x, y)
        assert not overlaps(x, y, WALL_GAP), (x, y)
    # The last direction was straight up, into the hedge: she has not moved
    # past its bottom edge.
    assert all(y >= corner[1] for _, y in trail)


def test_a_move_that_names_a_position_inside_the_hedge_is_refused_and_nobody_moves(connect):
    mara, watcher = walker_and_watcher(connect)
    below = (GAP_MIDDLE_X, 340.0)
    put("Mara", below)
    # The browser only says which way to walk; a position is not a field of `move`.
    answer = ask(mara, {"type": "move", "dx": 0, "dy": -1, "x": GAP_MIDDLE_X, "y": 297})
    assert answer["type"] == "error"
    assert answer["message"] == "That message has a field the server does not expect."
    time.sleep(QUIET_SECONDS)
    assert waiting_messages(mara) == []
    assert waiting_messages(watcher) == []
    assert app.state.lobbies.lobby_of("Mara").walkers.position_of("Mara") == below
