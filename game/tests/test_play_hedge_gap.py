"""The play test of to-do M1-1.5 "hedge gap", as repeatable tests.

`test_hedge_gap.py` checks the map and the walking rules on their own. Here
the same walks are played over WebSocket connections against the real server
with the real tick, the way a tester played them in two browser tabs: one
player walks into the place where tree 3 and the hedge meet, a second player
in the same lobby watches. Both must be told the same positions, and in no
message may the walker stand inside the hedge, inside tree 3 or in the old
10-unit gap between them.

Walking from the spawn to the hedge with keys would take seconds and land on
a different spot each time, so each test puts the walker where the walk
starts (as `task_helpers.put` does for the stations) and then walks with
real `move` messages.

Like `test_hedge_gap.py`, these tests assume a solid hedge (S-87). When the
hedge becomes a hiding place in M3-1.4 (S-98), they must be rethought.
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
TREE = next(item for item in SOLIDS if item["id"] == "deck-tree-3")
HEDGE = next(item for item in SOLIDS if item["id"] == "deck-hedge")

# Where the gap was: between the right edge of tree 3 (x 556) and the old
# left edge of the hedge (x 566), from the top of the tree to the bottom of the hedge.
OLD_GAP = {"x": 556, "y": 238, "w": 10, "h": 24}
# The middle of the old gap: the one x where a player fitted into it.
GAP_MIDDLE_X = OLD_GAP["x"] + OLD_GAP["w"] / 2

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


def assert_never_in_the_hedge_the_tree_or_the_old_gap(trail):
    assert trail, "the walker was never seen walking"
    for x, y in trail:
        assert is_free(x, y, SOLIDS, CAMPUS["width"], CAMPUS["height"]), (x, y)
        assert not overlaps(x, y, OLD_GAP), (x, y)


# Straight walks into the place of the old gap


def test_walking_up_from_below_the_old_gap_stops_under_the_hedge_for_both_players(connect):
    for_mara, for_watcher = walk_from(connect, (GAP_MIDDLE_X, 300), 0, -1)
    assert for_mara == for_watcher
    assert_never_in_the_hedge_the_tree_or_the_old_gap(for_mara)
    assert for_mara[-1] == (GAP_MIDDLE_X, HEDGE["y"] + HEDGE["h"] + PLAYER_HALF_SIZE)


def test_walking_down_from_above_the_old_gap_stops_on_the_hedge_for_both_players(connect):
    for_mara, for_watcher = walk_from(connect, (GAP_MIDDLE_X, 205), 0, 1)
    assert for_mara == for_watcher
    assert_never_in_the_hedge_the_tree_or_the_old_gap(for_mara)
    assert for_mara[-1] == (GAP_MIDDLE_X, HEDGE["y"] - PLAYER_HALF_SIZE)


# Diagonal walks into the corner where tree 3 and the hedge meet


def test_up_and_left_from_below_right_ends_in_the_corner_under_tree_and_hedge(connect):
    for_mara, for_watcher = walk_from(connect, (600, 296), -1, -1)
    assert for_mara == for_watcher
    assert_never_in_the_hedge_the_tree_or_the_old_gap(for_mara)
    # Touching the bottom of the hedge and the right side of the tree.
    assert for_mara[-1] == (TREE["x"] + TREE["w"] + PLAYER_HALF_SIZE, HEDGE["y"] + HEDGE["h"] + PLAYER_HALF_SIZE)


def test_down_and_right_from_above_left_ends_in_the_corner_on_tree_and_hedge(connect):
    # A diagonal step moves x and y by the same amount, so from here she
    # reaches the top of the tree (y 233) at x 543, left of the hedge.
    for_mara, for_watcher = walk_from(connect, (516, 206), 1, 1)
    assert for_mara == for_watcher
    assert_never_in_the_hedge_the_tree_or_the_old_gap(for_mara)
    # Touching the top of the tree and the left side of the hedge.
    assert for_mara[-1] == (HEDGE["x"] - PLAYER_HALF_SIZE, TREE["y"] - PLAYER_HALF_SIZE)


def test_up_and_right_from_below_left_only_passes_on_the_far_side_of_the_hedge(connect):
    for_mara, for_watcher = walk_from(connect, (540, 296), 1, -1)
    assert for_mara == for_watcher
    assert_never_in_the_hedge_the_tree_or_the_old_gap(for_mara)
    # She slides along under tree and hedge and goes up only right of the
    # hedge, where the way past the red button is.
    hedge_right = HEDGE["x"] + HEDGE["w"]
    for x, y in for_mara:
        if y < HEDGE["y"] + HEDGE["h"] + PLAYER_HALF_SIZE:
            assert x >= hedge_right + PLAYER_HALF_SIZE, (x, y)
    assert min(y for _, y in for_mara) < HEDGE["y"] - PLAYER_HALF_SIZE


def test_down_and_left_from_above_right_only_passes_on_the_far_side_of_tree_3(connect):
    for_mara, for_watcher = walk_from(connect, (600, 205), -1, 1)
    assert for_mara == for_watcher
    assert_never_in_the_hedge_the_tree_or_the_old_gap(for_mara)
    # She slides along over hedge and tree and goes down only left of tree 3.
    for x, y in for_mara:
        if y > TREE["y"] - PLAYER_HALF_SIZE:
            assert x <= TREE["x"] - PLAYER_HALF_SIZE, (x, y)
    assert max(y for _, y in for_mara) > TREE["y"] + TREE["h"] + PLAYER_HALF_SIZE


# Trying to break it


def test_pushing_on_in_the_corner_and_switching_fast_never_gets_into_the_hedge(connect):
    mara, watcher = walker_and_watcher(connect)
    corner = (TREE["x"] + TREE["w"] + PLAYER_HALF_SIZE, HEDGE["y"] + HEDGE["h"] + PLAYER_HALF_SIZE)
    put("Mara", corner)
    # Every direction that points into the hedge or the tree, many times and
    # without any pause, then the same direction twice in a row.
    for _ in range(30):
        for dx, dy in ((0, -1), (-1, -1), (1, -1), (-1, 0), (0, -1), (0, -1)):
            move(mara, dx, dy)
    seen = read_until_quiet(watcher)
    move(mara, 0, 0)
    trail = [positions["Mara"] for positions in seen]
    for x, y in trail:
        assert is_free(x, y, SOLIDS, CAMPUS["width"], CAMPUS["height"]), (x, y)
        assert not overlaps(x, y, OLD_GAP), (x, y)
    # The last direction was straight up, into the hedge: she has not moved
    # past its bottom edge.
    assert all(y >= corner[1] for _, y in trail)


def test_a_move_that_names_a_position_inside_the_hedge_is_refused_and_nobody_moves(connect):
    mara, watcher = walker_and_watcher(connect)
    below = (GAP_MIDDLE_X, 280.0)
    put("Mara", below)
    # The browser only says which way to walk; a position is not a field of `move`.
    answer = ask(mara, {"type": "move", "dx": 0, "dy": -1, "x": GAP_MIDDLE_X, "y": 249})
    assert answer["type"] == "error"
    assert answer["message"] == "That message has a field the server does not expect."
    time.sleep(QUIET_SECONDS)
    assert waiting_messages(mara) == []
    assert waiting_messages(watcher) == []
    assert app.state.lobbies.lobby_of("Mara").walkers.position_of("Mara") == below
