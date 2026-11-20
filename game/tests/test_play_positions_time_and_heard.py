"""The server's time in `positions` and the numbered `move` it has heard, with the real tick (M2-1.16).

Real WebSocket connections against the real server, whose tick runs in the
background, as in test_play_walking.py. No test counts ticks: each one waits,
with a generous deadline, until the server has sent what it expects.

The plain rules and the message formats are tested in
test_positions_time_and_heard.py.
"""

import contextlib
import statistics
import time

import pytest
from fastapi.testclient import TestClient

from server import main
from server.main import app
from server.world.movement import PLAYER_HALF_SIZE

# Used by every test here without being asked for: the placeholder stands at
# all five stations, and a round has no Duel, so any station can be opened.
from task_helpers import placeholder_at_every_station  # noqa: F401
from task_helpers import round_without_duel  # noqa: F401

PASSWORD = "password123"
CAMPUS = app.state.campus
SPAWN = {"x": CAMPUS["spawn"]["x"], "y": CAMPUS["spawn"]["y"]}
STATION_1 = next(station for station in CAMPUS["stations"] if station["id"] == 1)
BAD_MOVE = {"type": "error", "code": "bad_move", "message": "That move could not be read."}

# Generous: a walk across the whole deck takes about two seconds.
DEADLINE_SECONDS = 15.0
# Long enough for several ticks. Used only to see that nothing more arrives.
QUIET_SECONDS = 0.4
TICK_MILLISECONDS = 1000 / main.TICKS_PER_SECOND


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


def positions_among(messages):
    return [message for message in messages if message["type"] == "positions"]


def wait_for(connection, wanted):
    """Read this player's messages until one fits `wanted`. Returns that message."""
    deadline = time.monotonic() + DEADLINE_SECONDS
    while True:
        for message in waiting_messages(connection):
            if wanted(message):
                return message
        assert time.monotonic() < deadline, "the expected message did not arrive in time"
        time.sleep(0.02)


def positions_until_quiet(connection):
    """Read this player's `positions` messages until none arrive any more. Returns all of them, in order."""
    deadline = time.monotonic() + DEADLINE_SECONDS
    everything = positions_among(waiting_messages(connection))
    while True:
        time.sleep(QUIET_SECONDS)
        arrived_meanwhile = positions_among(waiting_messages(connection))
        if not arrived_meanwhile:
            return everything
        everything.extend(arrived_meanwhile)
        assert time.monotonic() < deadline, "the positions did not stop arriving"


def place_of(name, message):
    for listed in message["players"]:
        if listed["name"] == name:
            return {"x": listed["x"], "y": listed["y"]}
    return None


def stands_at(name, place):
    return lambda message: message["type"] == "positions" and place_of(name, message) == place


def of_type(message_type):
    return lambda message: message["type"] == message_type


def guest(connect):
    """A new connection that entered as a guest. Returns (connection, name)."""
    connection = connect()
    connection.send_json({"type": "guest"})
    return connection, wait_for(connection, of_type("signed_in"))["name"]


def create(connection) -> str:
    connection.send_json({"type": "create_lobby"})
    return wait_for(connection, of_type("lobby_state"))["code"]


def join(connection, code):
    connection.send_json({"type": "join_lobby", "code": code})
    wait_for(connection, of_type("lobby_state"))


def move(connection, dx, dy, seq=None):
    message = {"type": "move", "dx": dx, "dy": dy}
    if seq is not None:
        message["seq"] = seq
    connection.send_json(message)


def lobby_with(connect, count):
    """`count` guests in one lobby, all placed on the spawn and with nothing left to read.

    Returns a list of (connection, name) pairs in joining order.
    """
    players = [guest(connect) for number in range(count)]
    code = create(players[0][0])
    for connection, name in players[1:]:
        join(connection, code)
    last_name = players[-1][1]
    for connection, name in players:
        wait_for(connection, stands_at(last_name, SPAWN))
    for connection, name in players:
        positions_until_quiet(connection)
    return players


def solid(solid_id):
    return next(listed for listed in CAMPUS["solids"] if listed["id"] == solid_id)


# Criterion 1, over the wire: a bad "seq" is refused and the connection stays open


@pytest.mark.parametrize("raw_seq", ["true", "1.0", '"1"', "-1", "2000000001", "null"])
def test_a_bad_seq_is_refused_and_the_player_can_still_walk(connect, raw_seq):
    [(mara, mara_name)] = lobby_with(connect, 1)
    mara.send_text('{"type": "move", "dx": 1, "dy": 0, "seq": ' + raw_seq + "}")
    assert wait_for(mara, of_type("error")) == BAD_MOVE
    # The refused move did nothing: no walk, no answer in `positions`.
    time.sleep(QUIET_SECONDS)
    assert positions_among(waiting_messages(mara)) == []
    # The connection still works.
    move(mara, 1, 0, seq=1)
    wait_for(mara, lambda message: message["type"] == "positions" and message.get("you", {}).get("seq") == 1)


def test_a_numbered_move_from_outside_a_lobby_gets_the_usual_rejection(connect):
    stranger = connect()
    move(stranger, 1, 0, seq=1)
    assert stranger.receive_json()["code"] == "not_signed_in"
    someone, name = guest(connect)
    move(someone, 1, 0, seq=1)
    assert wait_for(someone, of_type("error"))["code"] == "not_in_lobby"


# Criterion 2: one player walks with a numbered move


def test_a_walk_with_seq_7_carries_the_time_and_what_was_heard(connect):
    [(mara, mara_name)] = lobby_with(connect, 1)
    move(mara, -1, 0, seq=7)  # Left, towards the pool, until the pool stops her.
    seen = positions_until_quiet(mara)
    assert len(seen) > 5, "a walk across the deck is told in many small steps"

    times = [message["t"] for message in seen]
    assert all(type(t) is int for t in times)
    assert times == sorted(times), "the time of the server never goes back"
    steps = [after - before for before, after in zip(times, times[1:])]
    # One message per tick at most, so two messages are at least about one
    # tick apart. A busy machine may skip ticks, so only the middle step is
    # held to "about one tick".
    assert min(steps) >= TICK_MILLISECONDS / 2
    assert statistics.median(steps) <= 4 * TICK_MILLISECONDS

    heard = seen[0]["you"]
    assert heard["seq"] == 7 and (heard["dx"], heard["dy"]) == (-1, 0)
    assert type(heard["t"]) is int and heard["t"] <= seen[0]["t"]
    # The same move was heard all along: "you" stays the same.
    assert all(message["you"] == heard for message in seen)
    # And she really walked left.
    xs = [place_of(mara_name, message)["x"] for message in seen]
    assert xs == sorted(xs, reverse=True) and xs[-1] < SPAWN["x"]


# Criterion 3: in a lobby, each player gets their own "you" and everybody the same time


def test_each_player_gets_only_their_own_you_and_the_same_time_and_players(connect):
    (mara, mara_name), (tiago, tiago_name), (ines, ines_name) = lobby_with(connect, 3)
    move(mara, 1, 0, seq=3)  # Right, towards the wall of the deck.
    move(tiago, 0, -1, seq=50)  # Up, towards the Canteen.
    move(ines, -1, 0)  # Left, but without a number: she gets no "you".

    seen = {name: positions_until_quiet(connection)
            for name, connection in [(mara_name, mara), (tiago_name, tiago), (ines_name, ines)]}

    for message in seen[mara_name]:
        assert message["you"]["seq"] == 3 and (message["you"]["dx"], message["you"]["dy"]) == (1, 0)
    for message in seen[tiago_name]:
        assert message["you"]["seq"] == 50 and (message["you"]["dx"], message["you"]["dy"]) == (0, -1)
    assert all("you" not in message for message in seen[ines_name])

    # A message of the same tick carries the same time and the same players for everybody.
    by_time = {name: {message["t"]: message["players"] for message in messages} for name, messages in seen.items()}
    common_times = set(by_time[mara_name]) & set(by_time[tiago_name]) & set(by_time[ines_name])
    assert len(common_times) >= 5
    for t in common_times:
        assert by_time[mara_name][t] == by_time[tiago_name][t] == by_time[ines_name][t]


# Criterion 4: a numbered move into a wall is answered to that player alone


def test_a_numbered_move_into_the_wall_is_answered_once_and_only_to_that_player(connect):
    (mara, mara_name), (tiago, tiago_name) = lobby_with(connect, 2)
    move(mara, 1, 0, seq=1)  # Right, until the wall of the deck stops her.
    at_the_wall = {"x": solid("deck-wall-right")["x"] - PLAYER_HALF_SIZE, "y": SPAWN["y"]}
    assert place_of(mara_name, positions_until_quiet(mara)[-1]) == at_the_wall
    positions_until_quiet(tiago)

    # She pushes against the wall again: nobody moves, but she learns the move was heard.
    move(mara, 1, 0, seq=2)
    answers = positions_until_quiet(mara)
    assert len(answers) == 1
    assert answers[0]["you"]["seq"] == 2 and (answers[0]["you"]["dx"], answers[0]["you"]["dy"]) == (1, 0)
    assert answers[0]["you"]["t"] <= answers[0]["t"]
    assert place_of(mara_name, answers[0]) == at_the_wall
    assert positions_until_quiet(tiago) == []

    # She lets go of the key: the same, with the direction 0, 0.
    move(mara, 0, 0, seq=3)
    answers = positions_until_quiet(mara)
    assert len(answers) == 1
    assert answers[0]["you"]["seq"] == 3 and (answers[0]["you"]["dx"], answers[0]["you"]["dy"]) == (0, 0)
    assert positions_until_quiet(tiago) == []


def test_a_move_without_seq_into_the_wall_still_brings_nothing(connect):
    (mara, mara_name), (tiago, tiago_name) = lobby_with(connect, 2)
    move(mara, 1, 0)
    positions_until_quiet(mara)
    positions_until_quiet(tiago)
    move(mara, 1, 0)
    time.sleep(QUIET_SECONDS)
    assert waiting_messages(mara) == []
    assert waiting_messages(tiago) == []


# Criterion 5: with a station open the move is heard but not walked


def test_with_a_station_open_a_numbered_move_is_heard_and_she_stands_still(connect, monkeypatch):
    (mara, mara_name), (tiago, tiago_name) = lobby_with(connect, 2)
    mara.send_json({"type": "start_game"})
    wait_for(mara, stands_at(mara_name, SPAWN))

    # The walk to a station takes many seconds, so she is put next to station 1,
    # where the tick keeps the position (as in test_server_tasks_walking.py).
    lobby = app.state.lobbies.lobby_of(mara_name)
    at_station = (float(STATION_1["x"]), float(STATION_1["y"]))
    lobby.walkers._walkers[mara_name].position = at_station
    mara.send_json({"type": "open_station", "station": 1})
    wait_for(mara, of_type("station_opened"))
    positions_until_quiet(mara)
    positions_until_quiet(tiago)

    move(mara, 1, 0, seq=11)
    answers = positions_until_quiet(mara)
    assert len(answers) == 1
    assert answers[0]["you"]["seq"] == 11
    assert (answers[0]["you"]["dx"], answers[0]["you"]["dy"]) == (0, 0)
    assert place_of(mara_name, answers[0]) == {"x": at_station[0], "y": at_station[1]}
    assert lobby.walkers.position_of(mara_name) == at_station
    assert positions_until_quiet(tiago) == []


# Leaving the lobby forgets what was heard


def test_after_leaving_and_joining_again_there_is_no_you(connect):
    (tiago, tiago_name), (mara, mara_name) = lobby_with(connect, 2)
    move(mara, 0, 0, seq=5)
    wait_for(mara, lambda message: message["type"] == "positions" and message.get("you", {}).get("seq") == 5)

    mara.send_json({"type": "leave_lobby"})
    wait_for(mara, of_type("left_lobby"))
    code = app.state.lobbies.lobby_of(tiago_name).code
    join(mara, code)
    back = wait_for(mara, stands_at(mara_name, SPAWN))
    assert "you" not in back
    assert all("you" not in message for message in positions_until_quiet(mara))
