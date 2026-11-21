"""The play test of to-do M2-1.15 "A walking diagnostic that only shows with ?debug", as repeatable tests.

The diagnostic (client/js/world/diagnostic.js) only reads in its own
browser. The one thing it sends is its probe: once a second a `hello` with
the name "debug0", "debug1", ..., which the server answers with `welcome`.
A tester played it in real browsers with two and with eight players: the
player with `?debug` walked, started a Duel, opened and closed a station and
finished the round, while the browsers of the others were watched for
anything they got because of the probe.

The panel itself needs a browser (S-72). What can be repeated without one
is played here by WebSocket connections against the real server with the
real tick: the probe is answered only to the player who sent it, in every
phase of a lobby, it changes nothing in the game, and a probe that is wrong
or comes at the wrong moment gets its message and breaks nothing.

How diagnostic.js itself counts is tested in test_walking_diagnostic.py and
test_walking_diagnostic_world.py.

No test counts ticks. Each one waits, with a generous deadline, until the
server has sent what it expects.
"""

import contextlib
import time

import pytest
from fastapi.testclient import TestClient

from server import protocol
from server.main import app

DEADLINE_SECONDS = 15.0
MOST_PLAYERS = 8
STATIONS = {station["id"]: station for station in app.state.campus["stations"]}

# What the server sends on its own to everybody in a round.
ROUND_TRAFFIC = ("positions", "duel_state", "duel_progress")

BAD_NAME = "Usernames are 3–16 letters or numbers."


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


def probe_message(number):
    """The probe as diagnostic.js sends it: every probe has its own name."""
    return {"type": "hello", "name": f"debug{number}"}


def answer_to_probe(number):
    return {"type": "welcome", "name": f"debug{number}", "protocol": protocol.PROTOCOL_VERSION}


def ask(connection, message):
    """Send one message and return the next message the server sends."""
    connection.send_json(message)
    return connection.receive_json()


def waiting_messages(connection):
    """Everything the server has sent this connection and the test has not read yet.

    A hello with the name "Reader" is sent and everything up to ITS answer
    is collected. A `welcome` with another name is not the end: it is kept,
    so a test sees an answer to somebody's probe that went astray.
    """
    connection.send_json({"type": "hello", "name": "Reader"})
    messages = []
    while True:
        message = connection.receive_json()
        if message["type"] == "welcome" and message["name"] == "Reader":
            return messages
        messages.append(message)


def probe(connection, number):
    """Send one probe. Returns (its answer, what the server sent this player before the answer)."""
    connection.send_json(probe_message(number))
    before = []
    while True:
        message = connection.receive_json()
        if message["type"] == "welcome":
            return message, before
        before.append(message)


def types_of(messages):
    return [message["type"] for message in messages]


def guest(connect):
    """A new connection that entered as a guest. Returns (connection, name)."""
    connection = connect()
    answer = ask(connection, {"type": "guest"})
    assert answer["type"] == "signed_in" and answer["guest"] is True
    return connection, answer["name"]


def lobby_of(connect, count):
    """`count` guests in one lobby; the first is the host. Everybody has read everything so far.

    Returns (connections, names, code), the host first.
    """
    players = [guest(connect) for _ in range(count)]
    connections = [connection for connection, _ in players]
    names = [name for _, name in players]
    code = ask(connections[0], {"type": "create_lobby"})["code"]
    for connection in connections[1:]:
        connection.send_json({"type": "join_lobby", "code": code})
    wait_until_everybody_knows(connections, lambda state: len(state["players"]) == count)
    return connections, names, code


def wait_until_everybody_knows(connections, is_reached):
    """Read every player's messages until each has got a `lobby_state` that fits. Returns the messages per player."""
    deadline = time.monotonic() + DEADLINE_SECONDS
    seen = [[] for _ in connections]
    while True:
        for index, connection in enumerate(connections):
            seen[index] += waiting_messages(connection)
        if all(any(m["type"] == "lobby_state" and is_reached(m) for m in messages) for messages in seen):
            return seen
        assert time.monotonic() < deadline, "the lobby's state did not arrive in time"
        time.sleep(0.02)


def start_duel(connections):
    """The host starts the Duel. Returns each player's next station, in the order of `connections`."""
    connections[0].send_json({"type": "start_game"})
    seen = wait_until_everybody_knows(connections, lambda state: state["phase"] == "round")
    next_stations = []
    for index, connection in enumerate(connections):
        deadline = time.monotonic() + DEADLINE_SECONDS
        while "duel_state" not in types_of(seen[index]):
            assert time.monotonic() < deadline, "the Duel did not tell the next station in time"
            time.sleep(0.02)
            seen[index] += waiting_messages(connection)
        next_stations.append(next(m["next_station"] for m in seen[index] if m["type"] == "duel_state"))
    return next_stations


def put_at_station(name, station):
    """Place a player on a station, as the tick would after a long walk (as in task_helpers.py)."""
    position = (float(STATIONS[station]["x"]), float(STATIONS[station]["y"]))
    app.state.lobbies.lobby_of(name).walkers._walkers[name].position = position


def position_of(name):
    return app.state.lobbies.lobby_of(name).walkers._walkers[name].position


def wait_for_own_x(connection, name, is_reached):
    """Read this player's messages until a `positions` message has the own x that fits. Returns that x."""
    deadline = time.monotonic() + DEADLINE_SECONDS
    while True:
        for message in waiting_messages(connection):
            if message["type"] != "positions":
                continue
            own = next(listed for listed in message["players"] if listed["name"] == name)
            if is_reached(own["x"]):
                return own["x"]
        assert time.monotonic() < deadline, "the expected position did not arrive in time"
        time.sleep(0.02)


# ---- The answer goes to the prober and to nobody else -----------------------------------------


def test_in_a_full_lobby_the_seven_others_get_nothing_because_of_the_probe(connect):
    connections, _, _ = lobby_of(connect, MOST_PLAYERS)
    prober, others = connections[0], connections[1:]

    for number in range(5):
        answer, before = probe(prober, number)
        assert answer == answer_to_probe(number)
        assert before == []  # nobody walks: the probe alone makes the server send nothing else

    for other in others:
        assert waiting_messages(other) == []


def test_while_everybody_walks_the_others_get_positions_and_never_a_welcome(connect):
    connections, names, _ = lobby_of(connect, MOST_PLAYERS)
    prober, others = connections[0], connections[1:]
    for index, connection in enumerate(connections):
        connection.send_json({"type": "move", "dx": 1 if index % 2 else -1, "dy": 0})
    wait_for_own_x(prober, names[0], lambda x: x < app.state.campus["spawn"]["x"] - 5)

    for number in range(10):
        answer, before = probe(prober, number)
        assert answer == answer_to_probe(number)
        assert set(types_of(before)) <= {"positions"}
        time.sleep(0.03)

    for other in others:
        got = waiting_messages(other)
        assert "positions" in types_of(got)
        assert set(types_of(got)) == {"positions"}


def test_during_a_duel_the_others_get_nothing_because_of_the_probe(connect):
    connections, _, _ = lobby_of(connect, 3)
    prober, others = connections[0], connections[1:]
    start_duel(connections)

    for number in range(5):
        answer, before = probe(prober, number)
        assert answer == answer_to_probe(number)
        assert set(types_of(before)) <= set(ROUND_TRAFFIC)

    for other in others:
        got = waiting_messages(other)
        assert "welcome" not in types_of(got)
        assert set(types_of(got)) <= set(ROUND_TRAFFIC)


def test_the_probe_of_a_player_who_is_not_the_host_is_answered_the_same_way(connect):
    connections, _, _ = lobby_of(connect, 2)
    host, prober = connections

    assert probe(prober, 0) == (answer_to_probe(0), [])

    assert waiting_messages(host) == []


def test_the_answer_tells_nothing_but_the_name_of_the_probe(connect):
    connections, names, code = lobby_of(connect, 2)

    answer, _ = probe(connections[0], 7)

    assert answer == {"type": "welcome", "name": "debug7", "protocol": protocol.PROTOCOL_VERSION}
    assert names[0] not in str(answer) and names[1] not in str(answer) and code not in str(answer)


# ---- The probe changes nothing in the game ----------------------------------------------------------


def test_probing_does_not_move_the_player_or_stop_a_walk(connect):
    connections, names, _ = lobby_of(connect, 2)
    prober, name = connections[0], names[0]
    spawn_x = app.state.campus["spawn"]["x"]
    # A few steps to the right and a stop, so the player stands at a known place.
    prober.send_json({"type": "move", "dx": 1, "dy": 0})
    wait_for_own_x(prober, name, lambda x: x > spawn_x + 5)
    prober.send_json({"type": "move", "dx": 0, "dy": 0})
    waiting_messages(prober)  # the stop has arrived at the server
    standing = position_of(name)

    for number in range(5):
        probe(prober, number)
    assert position_of(name) == standing

    prober.send_json({"type": "move", "dx": 1, "dy": 0})
    first = wait_for_own_x(prober, name, lambda x: x > standing[0] + 5)
    for number in range(5, 10):
        probe(prober, number)
    # Still walking right: the probes did not reset the direction.
    assert wait_for_own_x(prober, name, lambda x: x > first + 5) > first


def test_a_station_stays_open_while_the_player_probes_and_can_be_closed_after(connect):
    connections, names, _ = lobby_of(connect, 2)
    prober, other = connections
    station = start_duel(connections)[0]
    put_at_station(names[0], station)
    prober.send_json({"type": "open_station", "station": station})
    deadline = time.monotonic() + DEADLINE_SECONDS
    opened = []
    while "station_opened" not in types_of(opened):
        assert time.monotonic() < deadline, "the station did not open in time"
        opened += waiting_messages(prober)
    waiting_messages(other)

    for number in range(5):
        answer, before = probe(prober, number)
        assert answer == answer_to_probe(number)
        assert "station_closed" not in types_of(before)

    # The task is still open: a second opening is refused, closing works.
    prober.send_json({"type": "open_station", "station": station})
    prober.send_json({"type": "close_station"})
    after = [m for m in waiting_messages(prober) if m["type"] not in ROUND_TRAFFIC]
    assert after == [
        {"type": "error", "code": "task_open", "message": "Close your current task first."},
        {"type": "station_closed", "station": station},
    ]
    assert set(types_of(waiting_messages(other))) <= set(ROUND_TRAFFIC)


def test_probing_does_not_count_as_playing_a_round(connect):
    """A probe is no action of the game: without a round it is still answered, not refused."""
    connections, _, _ = lobby_of(connect, 2)
    prober = connections[0]

    assert ask(prober, {"type": "close_station"}) == {
        "type": "error", "code": "not_in_round", "message": "No round is running.",
    }
    assert probe(prober, 0) == (answer_to_probe(0), [])


# ---- Trying to break it: many at once, the wrong moment, wrong names -----------------------------------


def test_forty_probes_sent_at_once_between_moves_are_all_answered_in_order(connect):
    connections, names, _ = lobby_of(connect, 2)
    prober, other = connections
    for number in range(40):
        prober.send_json({"type": "move", "dx": 1 if number % 2 == 0 else 0, "dy": 0})
        prober.send_json(probe_message(number))
    prober.send_json({"type": "move", "dx": 0, "dy": 0})

    answers = [m for m in waiting_messages(prober) if m["type"] == "welcome"]

    assert answers == [answer_to_probe(number) for number in range(40)]
    assert "welcome" not in types_of(waiting_messages(other))


def test_the_same_probe_twice_is_answered_twice(connect):
    """diagnostic.js never sends a name twice in a row, but nothing breaks if a browser does."""
    connections, _, _ = lobby_of(connect, 2)
    prober = connections[0]
    prober.send_json(probe_message(3))
    prober.send_json(probe_message(3))

    assert waiting_messages(prober) == [answer_to_probe(3), answer_to_probe(3)]


def test_the_probe_is_answered_before_signing_in_and_after_leaving_and_logging_out(connect):
    """The panel is there on the Start screen too, so the probe runs on every screen."""
    connection = connect()
    assert probe(connection, 0) == (answer_to_probe(0), [])

    assert ask(connection, {"type": "guest"})["type"] == "signed_in"
    assert ask(connection, {"type": "create_lobby"})["type"] == "lobby_state"
    assert probe(connection, 1) == (answer_to_probe(1), [])

    assert ask(connection, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    assert probe(connection, 2) == (answer_to_probe(2), [])

    assert ask(connection, {"type": "log_out"}) == {"type": "signed_out"}
    assert probe(connection, 3) == (answer_to_probe(3), [])


@pytest.mark.parametrize("name", ["debug" + "9" * 12, "debug 1", "de", ""])
def test_a_probe_with_a_name_that_is_no_name_gets_the_message_and_the_next_one_is_answered(connect, name):
    connections, _, _ = lobby_of(connect, 2)
    prober, other = connections

    assert ask(prober, {"type": "hello", "name": name}) == {"type": "error", "code": "bad_name", "message": BAD_NAME}
    assert probe(prober, 0) == (answer_to_probe(0), [])
    assert waiting_messages(other) == []


def test_a_probe_with_something_added_is_refused_and_the_lobby_goes_on(connect):
    connections, names, _ = lobby_of(connect, 2)
    prober, other = connections

    refused = ask(prober, {"type": "hello", "name": "debug0", "to": names[1]})

    assert refused["type"] == "error"
    assert refused["message"] == "That message has a field the server does not expect."
    assert probe(prober, 1) == (answer_to_probe(1), [])
    assert waiting_messages(other) == []


def test_the_prober_leaves_in_the_middle_and_the_other_only_hears_of_the_leaving(connect):
    connections, names, _ = lobby_of(connect, 2)
    prober, other = connections
    for number in range(3):
        prober.send_json(probe_message(number))
    prober.close()

    deadline = time.monotonic() + DEADLINE_SECONDS
    heard = []
    while "lobby_state" not in types_of(heard):
        assert time.monotonic() < deadline, "the other player was not told in time"
        time.sleep(0.02)
        heard += waiting_messages(other)

    assert "welcome" not in types_of(heard)
    assert heard[-1]["type"] == "lobby_state"
    assert [player["name"] for player in heard[-1]["players"]] == [names[1]]
