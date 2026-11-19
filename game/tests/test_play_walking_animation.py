"""The play test of the walking animation (to-do M2-1.6), the part the server can show.

The animation itself is drawn in the browser and was played there with two
and with eight players; drawing code has no pytest tests. But the browser
decides from the positions of the server alone whether a character takes a
step or was put somewhere else (`LONGEST_STEP` in client/js/world/world.js:
a change of more than 15 map units on an axis is not a step). These tests
play what that rule relies on, against the real server with the real tick:

- a walking player never moves more than 9 units on an axis from one
  `positions` message to the next, in any direction;
- the start of a round puts a player who is far away on the spawn in one
  single message, with nothing in between that would look like a step;
- a player who holds a key over the start is put back in one message too and
  walks on from the spawn in normal steps.

No test counts ticks. Each one waits, with a generous deadline, until the
server has sent what it expects.
"""

import contextlib
import time

import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.world.movement import MAX_STEP_SECONDS, PLAYER_SPEED

PASSWORD = "password123"
START = {"type": "start_game"}
SPAWN_X = app.state.campus["spawn"]["x"]
SPAWN_Y = app.state.campus["spawn"]["y"]
AT_THE_SPAWN = {"x": SPAWN_X, "y": SPAWN_Y}

# The longest way on one axis the server moves a player in one go.
LONGEST_REAL_STEP = PLAYER_SPEED * MAX_STEP_SECONDS
# From this change on an axis the browser no longer draws a step
# (LONGEST_STEP in client/js/world/world.js).
BROWSER_TAKES_IT_FOR_A_RESET = 15
# Positions are sent with one decimal place, so two of them can differ by
# this much more than the way that was walked.
ROUNDING = 0.11

DEADLINE_SECONDS = 15.0


@pytest.fixture(autouse=True)
def quiet_tick():
    """Replaces the fixture of the same name in conftest.py: here the real tick runs."""


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


def answer_to(connection, message):
    """Send one message and return the first message after it that is not `positions`."""
    connection.send_json(message)
    while True:
        answer = connection.receive_json()
        if answer["type"] != "positions":
            return answer


def places_of(messages, name):
    """Where `name` is in each `positions` message among these, in the order they were sent."""
    places = []
    for message in messages:
        if message["type"] != "positions":
            continue
        for listed in message["players"]:
            if listed["name"] == name:
                places.append({"x": listed["x"], "y": listed["y"]})
    return places


def watch(connection, name, enough, known=()):
    """Read this connection until `enough(places)` is true. Returns every place of `name` on the way.

    `known` are places that were read before; they come first in the result.
    """
    places = list(known)
    deadline = time.monotonic() + DEADLINE_SECONDS
    while True:
        places += places_of(waiting_messages(connection), name)
        if enough(places):
            return places
        assert time.monotonic() < deadline, "the expected positions did not arrive in time"
        time.sleep(0.02)


def account(connect, name):
    connection = connect()
    assert answer_to(connection, {"type": "sign_up", "name": name, "password": PASSWORD})["type"] == "signed_in"
    return connection


def move(connection, dx, dy):
    connection.send_json({"type": "move", "dx": dx, "dy": dy})


def lobby_of_mara_and_tiago(connect):
    """Mara creates a lobby, Tiago joins. Both have read every message so far."""
    mara, tiago = account(connect, "Mara"), account(connect, "Tiago")
    code = answer_to(mara, {"type": "create_lobby"})["code"]
    assert answer_to(tiago, {"type": "join_lobby", "code": code})["type"] == "lobby_state"
    watch(mara, "Tiago", lambda places: AT_THE_SPAWN in places)
    waiting_messages(tiago)
    return mara, tiago


def steps_between(places):
    """The change on each axis from every place to the next: [(dx, dy), ...]."""
    return [
        (round(after["x"] - before["x"], 1), round(after["y"] - before["y"], 1))
        for before, after in zip(places, places[1:])
    ]


def is_a_real_step(step):
    return abs(step[0]) <= LONGEST_REAL_STEP + ROUNDING and abs(step[1]) <= LONGEST_REAL_STEP + ROUNDING


def looks_like_a_reset_to_the_browser(step):
    return abs(step[0]) > BROWSER_TAKES_IT_FOR_A_RESET or abs(step[1]) > BROWSER_TAKES_IT_FOR_A_RESET


def stand_far_right_of_the_spawn(mara, tiago):
    """Tiago walks more than 60 units to the right and stops. Returns where he stands."""
    move(tiago, 1, 0)
    places = watch(mara, "Tiago", lambda seen: seen and seen[-1]["x"] > SPAWN_X + 60)
    move(tiago, 0, 0)
    # Long enough for several ticks: the steps that were still on their way
    # have arrived, and a standing player is not sent again.
    time.sleep(0.4)
    places += places_of(waiting_messages(mara), "Tiago")
    return places[-1]


# A real step is far below what the browser takes for a reset


@pytest.mark.parametrize(
    "dx, dy",
    [(1, 0), (-1, 0), (0, -1), (0, 1), (1, 1), (-1, 1), (1, -1), (-1, -1)],
    ids=["right", "left", "up", "down", "down-right", "down-left", "up-right", "up-left"],
)
def test_a_walking_player_moves_at_most_nine_units_on_an_axis_per_message(connect, dx, dy):
    mara, tiago = lobby_of_mara_and_tiago(connect)
    move(tiago, dx, dy)
    # Six messages: to the left the pool stops him after 51 units.
    places = watch(mara, "Tiago", lambda seen: len(seen) >= 6)
    move(tiago, 0, 0)

    steps = steps_between([AT_THE_SPAWN] + places)
    assert all(is_a_real_step(step) for step in steps), steps
    assert not any(looks_like_a_reset_to_the_browser(step) for step in steps), steps
    # And he really walked the way he chose, on both screens the same way.
    assert all(step[0] * dx >= 0 and step[1] * dy >= 0 for step in steps), steps
    assert sum(abs(step[0]) + abs(step[1]) for step in steps) > 20


def test_both_players_are_sent_the_same_steps_of_a_walk(connect):
    # The view of a character is chosen from these steps in every browser, so
    # the walker and the watcher must be told the same ones.
    mara, tiago = lobby_of_mara_and_tiago(connect)
    move(tiago, -1, 0)
    seen_by_mara = watch(mara, "Tiago", lambda seen: len(seen) >= 8)
    move(tiago, 0, 0)
    time.sleep(0.4)
    seen_by_mara += places_of(waiting_messages(mara), "Tiago")
    seen_by_tiago = places_of(waiting_messages(tiago), "Tiago")

    assert seen_by_tiago == seen_by_mara


# The start of a round


def test_the_start_puts_a_player_who_stands_far_away_on_the_spawn_in_one_message(connect):
    mara, tiago = lobby_of_mara_and_tiago(connect)
    far = stand_far_right_of_the_spawn(mara, tiago)
    assert far["x"] > SPAWN_X + 60 and far["y"] == SPAWN_Y

    assert answer_to(mara, START)["phase"] == "round"
    places = watch(mara, "Tiago", lambda seen: AT_THE_SPAWN in seen)
    time.sleep(0.4)
    places += places_of(waiting_messages(mara), "Tiago")

    # He is either still where he stood or on the spawn, never in between
    # and never back: the browser has nothing it could draw as a step.
    assert all(place in (far, AT_THE_SPAWN) for place in places), places
    assert places.index(AT_THE_SPAWN) == places.count(far)
    assert looks_like_a_reset_to_the_browser((AT_THE_SPAWN["x"] - far["x"], AT_THE_SPAWN["y"] - far["y"]))


def test_the_walker_is_told_the_same_single_jump_to_the_spawn(connect):
    mara, tiago = lobby_of_mara_and_tiago(connect)
    far = stand_far_right_of_the_spawn(mara, tiago)
    waiting_messages(tiago)

    assert answer_to(mara, START)["phase"] == "round"
    places = watch(tiago, "Tiago", lambda seen: AT_THE_SPAWN in seen)

    assert all(place in (far, AT_THE_SPAWN) for place in places), places


def test_a_player_holding_a_key_over_the_start_is_put_back_once_and_then_takes_real_steps(connect):
    mara, tiago = lobby_of_mara_and_tiago(connect)
    move(tiago, 0, 1)
    before = watch(mara, "Tiago", lambda seen: seen and seen[-1]["y"] > SPAWN_Y + 40)

    assert answer_to(mara, START)["phase"] == "round"
    # Read on until he has walked down from the spawn again for a while.
    def is_back_and_walking(seen):
        back = [index for index, step in enumerate(steps_between(seen)) if step[1] < 0]
        return bool(back) and len(seen) - back[0] > 8

    places = watch(mara, "Tiago", is_back_and_walking, known=before[-1:])
    move(tiago, 0, 0)
    steps = steps_between(places)

    # Exactly one message takes him back up, by more than the browser takes
    # for a step. It puts him on the spawn or one step below it (S-91).
    resets = [step for step in steps if not is_a_real_step(step)]
    assert len(resets) == 1, steps
    assert looks_like_a_reset_to_the_browser(resets[0]), steps
    after_the_reset = places[steps.index(resets[0]) + 1]
    assert after_the_reset["x"] == SPAWN_X
    assert SPAWN_Y <= after_the_reset["y"] <= SPAWN_Y + LONGEST_REAL_STEP + ROUNDING
    # Everything else, before and after it, is a real step straight down.
    others = [step for step in steps if step is not resets[0]]
    assert all(step[0] == 0 and 0 <= step[1] <= LONGEST_REAL_STEP + ROUNDING for step in others), steps
