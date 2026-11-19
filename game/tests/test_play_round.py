"""The play test of to-do M2-2.1 "The host chooses the mode and starts the round", as repeatable tests.

What a tester played in several browsers and tried to break is played here by
several WebSocket connections against the real server with the real tick.
The plain cases (who may choose and start, the texts of the rejections) are
in test_server_round.py; this file holds what the play test added: things
done twice quickly, at the wrong moment or by the wrong player, players who
leave in every way during a round, a lobby that is full, and where everybody
stands on the map after the start.

No test counts ticks. Each one waits, with a generous deadline, until the
server has sent what it expects.
"""

import contextlib
import time

import pytest
from fastapi.testclient import TestClient

from server import main, protocol
from server.main import app

PASSWORD = "password123"
SPAWN_X = app.state.campus["spawn"]["x"]
SPAWN_Y = app.state.campus["spawn"]["y"]
AT_THE_SPAWN = {"x": SPAWN_X, "y": SPAWN_Y}

DEADLINE_SECONDS = 15.0

NOT_HOST = {"type": "error", "code": "not_host", "message": "Only the host can do that."}
ROUND_RUNNING = {"type": "error", "code": "round_running", "message": "This round has already started."}
TOO_FEW_FOR_DUEL = {"type": "error", "code": "too_few_players", "message": "Duel needs at least 2 players."}
LOBBY_FULL = {"type": "error", "code": "lobby_full", "message": "This lobby is full."}
NO_LOBBY = {"type": "error", "code": "no_lobby", "message": "No lobby with that code."}
NOT_IN_LOBBY = {"type": "error", "code": "not_in_lobby", "message": "You are not in a lobby."}
NOT_SIGNED_IN = {"type": "error", "code": "not_signed_in", "message": "Log in or play as a guest first."}
BAD_MODE = {"type": "error", "code": "bad_mode", "message": "That mode does not exist."}

START = {"type": "start_game"}
CHOOSE_DUEL = {"type": "choose_mode", "mode": "duel"}


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


# What the server sends on its own while a round runs: the positions of the
# tick, and since S-94 the Duel's messages after the start and after a player
# left. The tests here are about the lobby and the start of a round; the
# Duel's messages are tested in test_server_duel.py.
ROUND_TRAFFIC = ("positions", "duel_state", "duel_progress")


def without_round_traffic(messages):
    return [message for message in messages if message["type"] not in ROUND_TRAFFIC]


def news(connection):
    """What is waiting for this player, without the messages in ROUND_TRAFFIC."""
    return without_round_traffic(waiting_messages(connection))


def answer_to(connection, message):
    """Send one message and return the first message after it that is not `positions`."""
    connection.send_json(message)
    while True:
        answer = connection.receive_json()
        if answer["type"] != "positions":
            return answer


def as_positions(message):
    return {listed["name"]: {"x": listed["x"], "y": listed["y"]} for listed in message["players"]}


def wait_for_positions(connection, wanted):
    """Read this player's messages until a `positions` message fits. Returns it as {name: {"x", "y"}}."""
    deadline = time.monotonic() + DEADLINE_SECONDS
    while True:
        for message in waiting_messages(connection):
            if message["type"] == "positions" and wanted(as_positions(message)):
                return as_positions(message)
        assert time.monotonic() < deadline, "the expected positions did not arrive in time"
        time.sleep(0.02)


def account(connect, name):
    connection = connect()
    assert answer_to(connection, {"type": "sign_up", "name": name, "password": PASSWORD})["type"] == "signed_in"
    return connection


def guest(connect):
    """A new connection that entered as a guest. Returns (connection, name)."""
    connection = connect()
    answer = answer_to(connection, {"type": "guest"})
    assert answer["type"] == "signed_in"
    return connection, answer["name"]


def move(connection, dx, dy):
    connection.send_json({"type": "move", "dx": dx, "dy": dy})


def lobby_of(connect, *names):
    """The first name creates a lobby, the others join in this order. Returns (connections, code).

    Everybody has read every lobby message so far.
    """
    connections = [account(connect, name) for name in names]
    code = answer_to(connections[0], {"type": "create_lobby"})["code"]
    for joiner in connections[1:]:
        assert answer_to(joiner, {"type": "join_lobby", "code": code})["type"] == "lobby_state"
    for connection in connections:
        news(connection)
    return connections, code


def running_round_of(connect, *names):
    connections, code = lobby_of(connect, *names)
    assert answer_to(connections[0], START)["phase"] == "round"
    for connection in connections:
        news(connection)
    return connections, code


def lobby_states(messages):
    return [message for message in messages if message["type"] == "lobby_state"]


def names_in(lobby_state):
    return [player["name"] for player in lobby_state["players"]]


# Starting twice quickly


def test_five_starts_in_a_row_start_one_round_and_reject_the_other_four(connect):
    (mara, tiago), code = lobby_of(connect, "Mara", "Tiago")
    for attempt in range(5):
        mara.send_json(START)
    answers = news(mara)
    assert [answer["type"] for answer in answers] == ["lobby_state"] + ["error"] * 4
    assert answers[0]["phase"] == "round"
    assert answers[1:] == [ROUND_RUNNING] * 4
    # The other player hears of the start exactly once and of no rejection.
    told = news(tiago)
    assert len(told) == 1 and told[0]["phase"] == "round"


def test_a_start_and_a_mode_choice_sent_together_start_the_round_and_refuse_the_choice(connect):
    (mara, tiago), code = lobby_of(connect, "Mara", "Tiago")
    mara.send_json(START)
    mara.send_json(CHOOSE_DUEL)
    answers = news(mara)
    assert answers[0]["phase"] == "round"
    assert answers[1] == ROUND_RUNNING
    assert len(news(tiago)) == 1


# The number of players changes around the start


def test_the_start_is_refused_when_the_only_other_player_has_just_left(connect):
    (mara, tiago), code = lobby_of(connect, "Mara", "Tiago")
    assert answer_to(tiago, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    mara.send_json(START)
    answers = news(mara)
    assert TOO_FEW_FOR_DUEL in answers
    # Every state Mara was sent says the lobby is still waiting, with her alone in it.
    assert all(state["phase"] == "lobby" and names_in(state) == ["Mara"] for state in lobby_states(answers))
    assert app.state.lobbies.find(code).phase == "lobby"


def test_the_start_is_refused_when_the_only_other_player_has_just_closed_the_connection(connect):
    (mara, tiago), code = lobby_of(connect, "Mara", "Tiago")
    tiago.close()
    assert lobby_states([mara.receive_json()])[0]["phase"] == "lobby"
    assert answer_to(mara, START) == TOO_FEW_FOR_DUEL
    assert app.state.lobbies.find(code).phase == "lobby"


def test_a_host_who_was_alone_can_start_as_soon_as_somebody_joined(connect):
    mara = account(connect, "Mara")
    code = answer_to(mara, {"type": "create_lobby"})["code"]
    assert answer_to(mara, START) == TOO_FEW_FOR_DUEL
    tiago = account(connect, "Tiago")
    tiago.send_json({"type": "join_lobby", "code": code})
    mara.send_json(START)
    assert lobby_states(news(mara))[-1]["phase"] == "round"
    last_for_tiago = lobby_states(news(tiago))[-1]
    assert last_for_tiago["phase"] == "round"
    assert names_in(last_for_tiago) == ["Mara", "Tiago"]


def test_a_round_goes_on_when_it_drops_below_two_players(connect):
    (mara, tiago), code = running_round_of(connect, "Mara", "Tiago")
    assert answer_to(tiago, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    assert news(mara) == [protocol.lobby_state(code, "Mara", [("Mara", protocol.CHARACTERS[0])], "duel", "round")]
    # Alone in the round Mara still walks, and nobody can come in.
    move(mara, 1, 0)
    wait_for_positions(mara, lambda positions: positions["Mara"]["x"] > SPAWN_X)
    assert answer_to(tiago, {"type": "join_lobby", "code": code}) == ROUND_RUNNING


# A full lobby


def full_lobby(connect):
    """Eight guests in one lobby. Returns (connections, names, code); the first one is the host."""
    guests = [guest(connect) for number in range(8)]
    connections = [connection for connection, name in guests]
    names = [name for connection, name in guests]
    code = answer_to(connections[0], {"type": "create_lobby"})["code"]
    for joiner in connections[1:]:
        assert answer_to(joiner, {"type": "join_lobby", "code": code})["type"] == "lobby_state"
    for connection in connections:
        news(connection)
    return connections, names, code


def test_a_ninth_player_hears_full_before_the_start_and_round_running_after_it(connect):
    connections, names, code = full_lobby(connect)
    ninth, ninth_name = guest(connect)
    assert answer_to(ninth, {"type": "join_lobby", "code": code}) == LOBBY_FULL
    assert answer_to(connections[0], START)["phase"] == "round"
    assert answer_to(ninth, {"type": "join_lobby", "code": code}) == ROUND_RUNNING
    # A place that becomes free during the round stays closed.
    connections[5].close()
    wait_for_positions(connections[0], lambda positions: names[5] not in positions)
    assert answer_to(ninth, {"type": "join_lobby", "code": code}) == ROUND_RUNNING
    # The ninth player was never let in and can open a lobby of their own.
    assert answer_to(ninth, {"type": "create_lobby"})["phase"] == "lobby"


def test_after_the_start_all_eight_stand_on_the_spawn_also_those_who_walked_away(connect):
    connections, names, code = full_lobby(connect)
    move(connections[3], 1, 0)
    move(connections[6], 0, 1)
    wait_for_positions(
        connections[0],
        lambda positions: positions[names[3]]["x"] > SPAWN_X + 20 and positions[names[6]]["y"] > SPAWN_Y + 20,
    )
    move(connections[3], 0, 0)
    move(connections[6], 0, 0)
    assert answer_to(connections[0], START)["phase"] == "round"
    everybody_at_the_spawn = {name: AT_THE_SPAWN for name in names}
    for connection in connections:
        wait_for_positions(connection, lambda positions: positions == everybody_at_the_spawn)


# Where the players stand


def test_a_player_holding_a_key_at_the_start_walks_on_from_the_spawn(connect):
    # S-91: the direction is kept. Tiago is far to the right when the round
    # starts; afterwards he is seen close to the spawn, still walking right.
    (mara, tiago), code = lobby_of(connect, "Mara", "Tiago")
    move(tiago, 1, 0)
    far = wait_for_positions(mara, lambda positions: positions["Tiago"]["x"] > SPAWN_X + 60)["Tiago"]["x"]
    mara.send_json(START)
    back = wait_for_positions(mara, lambda positions: positions["Tiago"]["x"] < far - 30)
    assert back["Tiago"]["x"] >= SPAWN_X
    assert back["Tiago"]["y"] == SPAWN_Y
    assert back["Mara"] == AT_THE_SPAWN
    later = wait_for_positions(mara, lambda positions: positions["Tiago"]["x"] > back["Tiago"]["x"])
    assert later["Tiago"]["y"] == SPAWN_Y


def test_a_rejected_start_leaves_everybody_where_they_are(connect):
    (mara, tiago, ines), code = lobby_of(connect, "Mara", "Tiago", "Ines")
    move(ines, 0, 1)
    wait_for_positions(tiago, lambda positions: positions["Ines"]["y"] > SPAWN_Y + 20)
    move(ines, 0, 0)
    assert answer_to(tiago, START) == NOT_HOST
    # A step by Tiago makes the server send positions again: Ines is still down there.
    move(tiago, 1, 0)
    seen = wait_for_positions(mara, lambda positions: positions["Tiago"]["x"] > SPAWN_X)
    assert seen["Ines"]["y"] > SPAWN_Y + 20
    assert app.state.lobbies.find(code).phase == "lobby"


def test_after_a_player_left_the_round_the_others_still_see_each_other_walk(connect):
    (mara, tiago, ines), code = running_round_of(connect, "Mara", "Tiago", "Ines")
    assert answer_to(tiago, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    move(ines, -1, 0)
    seen = wait_for_positions(mara, lambda positions: "Tiago" not in positions and positions["Ines"]["x"] < SPAWN_X)
    assert set(seen) == {"Mara", "Ines"}
    # The one who left is told nothing about the round any more.
    move(mara, 0, 1)
    wait_for_positions(ines, lambda positions: positions["Mara"]["y"] > SPAWN_Y)
    assert waiting_messages(tiago) == []


# The host goes


def test_the_host_starts_and_leaves_at_once(connect):
    (mara, tiago, ines), code = lobby_of(connect, "Mara", "Tiago", "Ines")
    mara.send_json(START)
    mara.send_json({"type": "leave_lobby"})
    answers = news(mara)
    assert answers[0]["phase"] == "round"
    assert answers[-1] == {"type": "left_lobby"}
    for connection in (tiago, ines):
        told = news(connection)
        assert {"type": "notice", "message": "The host left. Tiago is the new host."} in told
        last = told[-1]
        assert (last["phase"], last["host"], names_in(last)) == ("round", "Tiago", ["Tiago", "Ines"])
    assert answer_to(tiago, START) == ROUND_RUNNING


def test_a_player_who_became_host_before_the_start_can_choose_the_mode_and_start(connect):
    (mara, tiago, ines), code = lobby_of(connect, "Mara", "Tiago", "Ines")
    assert answer_to(tiago, START) == NOT_HOST
    assert answer_to(mara, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    news(tiago)
    news(ines)
    assert answer_to(ines, START) == NOT_HOST
    assert answer_to(tiago, CHOOSE_DUEL)["host"] == "Tiago"
    started = answer_to(tiago, START)
    assert (started["phase"], started["host"]) == ("round", "Tiago")
    assert lobby_states(news(ines))[-1]["phase"] == "round"
    # The old host is outside and cannot come back into the running round.
    assert answer_to(mara, START) == NOT_IN_LOBBY
    assert answer_to(mara, {"type": "join_lobby", "code": code}) == ROUND_RUNNING


def test_a_player_who_became_host_during_the_round_can_neither_start_nor_choose(connect):
    (mara, tiago, ines), code = running_round_of(connect, "Mara", "Tiago", "Ines")
    mara.close()
    assert tiago.receive_json() == {"type": "notice", "message": "The host left. Tiago is the new host."}
    news(tiago)
    news(ines)  # Ines reads the same notice and the new state.
    assert answer_to(tiago, START) == ROUND_RUNNING
    assert answer_to(tiago, CHOOSE_DUEL) == ROUND_RUNNING
    assert answer_to(tiago, {"type": "choose_character", "character": "surfer"}) == ROUND_RUNNING
    assert answer_to(ines, START) == NOT_HOST


# Leaving in other ways


def test_a_player_who_logs_out_during_the_round_leaves_it_and_the_others_stay(connect):
    (mara, tiago, ines), code = running_round_of(connect, "Mara", "Tiago", "Ines")
    assert answer_to(tiago, {"type": "log_out"}) == {"type": "signed_out"}
    for connection in (mara, ines):
        told = news(connection)
        assert len(told) == 1
        assert (told[0]["phase"], names_in(told[0])) == ("round", ["Mara", "Ines"])
    assert answer_to(tiago, START) == NOT_SIGNED_IN


def test_an_account_that_logs_in_again_during_the_round_has_given_up_its_place(connect):
    (mara, tiago, ines), code = running_round_of(connect, "Mara", "Tiago", "Ines")
    second_tab = connect()
    answer = answer_to(second_tab, {"type": "log_in", "name": "Tiago", "password": PASSWORD})
    assert answer == {"type": "signed_in", "name": "Tiago", "guest": False}
    # The others stay in the round without Tiago.
    for connection in (mara, ines):
        last = lobby_states(news(connection))[-1]
        assert (last["phase"], names_in(last)) == ("round", ["Mara", "Ines"])
    # The old tab is signed out, the new one is in no lobby and cannot rejoin.
    assert news(tiago) == [{"type": "signed_out"}]
    assert answer_to(tiago, START) == NOT_SIGNED_IN
    assert answer_to(second_tab, START) == NOT_IN_LOBBY
    assert answer_to(second_tab, {"type": "join_lobby", "code": code}) == ROUND_RUNNING


def test_a_lobby_with_the_code_of_an_abandoned_round_starts_fresh(connect, monkeypatch):
    (mara, tiago), code = running_round_of(connect, "Mara", "Tiago")
    move(mara, 1, 0)
    wait_for_positions(tiago, lambda positions: positions["Mara"]["x"] > SPAWN_X + 20)
    mara.close()
    tiago.close()

    ines = account(connect, "Ines")
    assert answer_to(ines, {"type": "join_lobby", "code": code}) == NO_LOBBY
    # The server happens to pick the same four letters again.
    monkeypatch.setattr(main, "pick_lobby_code", lambda: code)
    created = answer_to(ines, {"type": "create_lobby"})
    assert created == protocol.lobby_state(code, "Ines", [("Ines", protocol.CHARACTERS[0])], "duel", "lobby")
    assert wait_for_positions(ines, lambda positions: True) == {"Ines": AT_THE_SPAWN}
    # It is an ordinary lobby: it can be joined and its characters can be chosen.
    rui = account(connect, "Rui")
    assert answer_to(rui, {"type": "join_lobby", "code": code})["phase"] == "lobby"
    assert answer_to(rui, {"type": "choose_character", "character": "surfer"})["phase"] == "lobby"


# Messages that are not as they should be


@pytest.mark.parametrize(
    "message, code",
    [
        ({"type": "start_game", "now": True}, "unknown_field"),
        ({"type": "start_game", "mode": None}, "unknown_field"),
        ({"type": "choose_mode"}, "missing_field"),
        ({"type": "choose_mode", "mode": "duel", "extra": 1}, "unknown_field"),
        ({"type": "choose_mode", "mode": "Duel"}, "bad_mode"),
        ({"type": "choose_mode", "mode": "xyz"}, "bad_mode"),
        ({"type": "choose_mode", "mode": {"mode": "duel"}}, "bad_mode"),
        ({"type": "choose_mode", "mode": 1.5}, "bad_mode"),
        ({"type": "choose_mode", "mode": "x" * 3000}, "too_large"),
        ({"type": "START_GAME"}, "unknown_type"),
    ],
)
def test_a_malformed_message_of_the_host_is_refused_and_changes_nothing(connect, message, code):
    (mara, tiago), lobby_code = lobby_of(connect, "Mara", "Tiago")
    answer = answer_to(mara, message)
    assert (answer["type"], answer["code"]) == ("error", code)
    assert isinstance(answer["message"], str) and answer["message"]
    assert news(tiago) == []  # Nobody else was told anything.
    lobby = app.state.lobbies.find(lobby_code)
    assert (lobby.mode, lobby.phase) == ("duel", "lobby")
    # The connection is still usable: the host starts the round with it.
    assert answer_to(mara, START)["phase"] == "round"


def test_a_malformed_message_during_the_round_does_not_disturb_it(connect):
    (mara, tiago), code = running_round_of(connect, "Mara", "Tiago")
    assert answer_to(tiago, {"type": "start_game", "again": 1})["code"] == "unknown_field"
    assert news(mara) == [] and news(tiago) == []
    move(tiago, 0, 1)
    wait_for_positions(mara, lambda positions: positions["Tiago"]["y"] > SPAWN_Y)
    assert app.state.lobbies.find(code).phase == "round"


def test_classic_mode_is_rejected_during_a_running_round(connect):
    (mara, tiago), code = running_round_of(connect, "Mara", "Tiago")
    assert answer_to(mara, {"type": "choose_mode", "mode": "classic"}) == ROUND_RUNNING
    assert app.state.lobbies.find(code).phase == "round"


def test_someone_who_is_not_signed_in_changes_nothing_in_a_lobby(connect):
    (mara, tiago), code = lobby_of(connect, "Mara", "Tiago")
    stranger = connect()
    assert answer_to(stranger, START) == NOT_SIGNED_IN
    assert answer_to(stranger, CHOOSE_DUEL) == NOT_SIGNED_IN
    assert news(mara) == [] and news(tiago) == []
    assert app.state.lobbies.find(code).phase == "lobby"
