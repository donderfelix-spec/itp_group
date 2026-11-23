"""Choosing the mode and starting the round over the WebSocket, with several players (M2-2.1)."""

import contextlib

import pytest
from fastapi.testclient import TestClient

from server import protocol
from server.main import app

PASSWORD = "password123"
FIRST, SECOND, THIRD = protocol.CHARACTERS[:3]

NOT_HOST = {"type": "error", "code": "not_host", "message": "Only the host can do that."}
ROUND_RUNNING = {"type": "error", "code": "round_running", "message": "This round has already started."}
TOO_FEW_FOR_DUEL = {"type": "error", "code": "too_few_players", "message": "Duel needs at least 2 players."}
NOT_IN_LOBBY = {"type": "error", "code": "not_in_lobby", "message": "You are not in a lobby."}
NOT_SIGNED_IN = {"type": "error", "code": "not_signed_in", "message": "Log in or play as a guest first."}
BAD_MODE = {"type": "error", "code": "bad_mode", "message": "That mode does not exist."}


@pytest.fixture
def client():
    # One event loop for all connections, like the real server (see test_server_lobby.py).
    with TestClient(app) as shared_client:
        yield shared_client


@pytest.fixture
def connect(client):
    """A function that opens one more connection. All of them are closed after the test."""
    with contextlib.ExitStack() as open_connections:
        yield lambda: open_connections.enter_context(client.websocket_connect("/ws"))


def ask(connection, message):
    """Send one message and return the next message the server sends."""
    connection.send_json(message)
    return connection.receive_json()


def player(connect, name):
    """A new connection, signed in with a new account of this name."""
    connection = connect()
    assert ask(connection, {"type": "sign_up", "name": name, "password": PASSWORD})["type"] == "signed_in"
    return connection


def guest(connect):
    connection = connect()
    assert ask(connection, {"type": "guest"})["type"] == "signed_in"
    return connection


def choose_mode(connection, mode):
    return ask(connection, {"type": "choose_mode", "mode": mode})


def start(connection):
    return ask(connection, {"type": "start_game"})


def still_works(connection):
    """True if the next message is the answer to a hello: nothing else was waiting."""
    return ask(connection, {"type": "hello", "name": "Mara"})["type"] == "welcome"


def state(code, host, *players, phase="lobby"):
    return protocol.lobby_state(code, host, players, "duel", phase)


def lobby_of_three(connect):
    """Mara creates a lobby, Tiago and Ines join. All read every state so far."""
    mara = player(connect, "Mara")
    tiago = player(connect, "Tiago")
    ines = player(connect, "Ines")
    code = ask(mara, {"type": "create_lobby"})["code"]
    ask(tiago, {"type": "join_lobby", "code": code})
    mara.receive_json()
    ask(ines, {"type": "join_lobby", "code": code})
    mara.receive_json()
    tiago.receive_json()
    return mara, tiago, ines, code


def running_round_of_three(connect):
    """A round of Mara, Tiago and Ines. All read everything the start sends them."""
    mara, tiago, ines, code = lobby_of_three(connect)
    start(mara)
    tiago.receive_json()
    ines.receive_json()
    # After the lobby's state every player is told about the Duel (S-94):
    # their own first station, then everybody's progress.
    for connection in (mara, tiago, ines):
        assert connection.receive_json()["type"] == "duel_state"
        assert connection.receive_json()["type"] == "duel_progress"
    return mara, tiago, ines, code


def read_progress_without(connection, name):
    """Read the Duel's progress that follows when a player left: it no longer lists them."""
    progress = connection.receive_json()
    assert progress["type"] == "duel_progress"
    assert name not in [listed["name"] for listed in progress["players"]]


THREE_PLAYERS = (("Mara", FIRST), ("Tiago", SECOND), ("Ines", THIRD))


# A new lobby


def test_a_new_lobby_is_in_mode_solo_and_phase_lobby(connect):
    mara = player(connect, "Mara")
    answer = ask(mara, {"type": "create_lobby"})
    assert answer["mode"] == "solo"  # one player: Solo (S-203)
    assert answer["phase"] == "lobby"


# Choosing the mode


def test_the_host_chooses_the_mode_and_everybody_is_told(connect):
    mara, tiago, ines, code = lobby_of_three(connect)
    expected = state(code, "Mara", *THREE_PLAYERS)
    assert choose_mode(mara, "duel") == expected
    assert tiago.receive_json() == expected
    assert ines.receive_json() == expected


def test_a_member_who_is_not_host_cannot_choose_the_mode(connect):
    mara, tiago, ines, code = lobby_of_three(connect)
    assert choose_mode(tiago, "duel") == NOT_HOST
    assert still_works(mara)  # Nobody else was told anything.
    assert still_works(ines)


@pytest.mark.parametrize("mode", ["chess", "", None, 2, ["duel"]])
def test_an_unknown_or_malformed_mode_is_refused_and_connection_stays_usable(connect, mode):
    mara, tiago, ines, code = lobby_of_three(connect)
    assert choose_mode(mara, mode) == BAD_MODE
    assert still_works(tiago)
    assert choose_mode(mara, "duel")["mode"] == "duel"


def test_classic_can_be_chosen_and_needs_four_players(connect):
    mara, tiago, ines, code = lobby_of_three(connect)
    chosen = choose_mode(mara, "classic")
    assert chosen["mode"] == "classic"
    assert tiago.receive_json() == chosen
    assert ines.receive_json() == chosen
    assert start(mara) == {
        "type": "error", "code": "too_few_players",
        "message": "Classic needs at least 4 players.",
    }


def test_choose_mode_outside_a_lobby_is_rejected(connect):
    mara = player(connect, "Mara")
    assert choose_mode(mara, "duel") == NOT_IN_LOBBY


def test_choose_mode_when_signed_out_is_rejected(connect):
    stranger = connect()
    assert choose_mode(stranger, "duel") == NOT_SIGNED_IN
    assert start(stranger) == NOT_SIGNED_IN


# Starting


def test_the_host_starts_and_everybody_gets_phase_round(connect):
    mara, tiago, ines, code = lobby_of_three(connect)
    expected = state(code, "Mara", *THREE_PLAYERS, phase="round")
    assert start(mara) == expected
    assert tiago.receive_json() == expected
    assert ines.receive_json() == expected


def test_the_host_starts_with_eight_players(connect):
    members = [guest(connect) for number in range(8)]
    host = members[0]
    code = ask(host, {"type": "create_lobby"})["code"]
    for number, joiner in enumerate(members[1:], start=1):
        ask(joiner, {"type": "join_lobby", "code": code})
        for earlier in members[:number]:
            earlier.receive_json()
    assert start(host)["phase"] == "round"
    for member in members[1:]:
        answer = member.receive_json()
        assert answer["phase"] == "round"
        assert len(answer["players"]) == 8


def test_starting_alone_is_rejected(connect):
    mara = player(connect, "Mara")
    ask(mara, {"type": "create_lobby"})
    ask(mara, {"type": "choose_mode", "mode": "duel"})  # a new lobby is in Solo (S-203); Duel needs two
    assert start(mara) == TOO_FEW_FOR_DUEL
    assert ask(mara, {"type": "choose_character", "character": "surfer"})["phase"] == "lobby"


def test_a_member_who_is_not_host_cannot_start(connect):
    mara, tiago, ines, code = lobby_of_three(connect)
    assert start(tiago) == NOT_HOST
    assert still_works(mara)
    assert still_works(ines)
    assert start(mara)["phase"] == "round"


def test_a_second_start_is_rejected(connect):
    mara, tiago, ines, code = running_round_of_three(connect)
    assert start(mara) == ROUND_RUNNING
    assert still_works(tiago)
    assert still_works(ines)


def test_start_outside_a_lobby_is_rejected(connect):
    mara = player(connect, "Mara")
    assert start(mara) == NOT_IN_LOBBY


def test_start_game_with_a_field_is_refused_by_the_message_check(connect):
    mara, tiago, ines, code = lobby_of_three(connect)
    assert ask(mara, {"type": "start_game", "mode": "duel"})["code"] == "unknown_field"
    assert still_works(tiago)
    assert choose_mode(mara, "duel")["phase"] == "lobby"


# While the round runs


def test_joining_a_running_round_is_rejected(connect):
    mara, tiago, ines, code = running_round_of_three(connect)
    latecomer = player(connect, "Rui")
    assert ask(latecomer, {"type": "join_lobby", "code": code}) == ROUND_RUNNING
    assert still_works(mara)
    # Rui is in no lobby and can open one of his own.
    assert ask(latecomer, {"type": "create_lobby"})["phase"] == "lobby"


def test_choosing_a_character_during_the_round_is_rejected(connect):
    mara, tiago, ines, code = running_round_of_three(connect)
    assert ask(tiago, {"type": "choose_character", "character": "surfer"}) == ROUND_RUNNING
    assert still_works(mara)


def test_choosing_the_mode_during_the_round_is_rejected(connect):
    mara, tiago, ines, code = running_round_of_three(connect)
    assert choose_mode(mara, "duel") == ROUND_RUNNING
    assert still_works(tiago)


def test_not_host_comes_before_round_running(connect):
    mara, tiago, ines, code = running_round_of_three(connect)
    assert start(tiago) == NOT_HOST
    assert choose_mode(tiago, "duel") == NOT_HOST


def test_a_member_leaves_the_round_and_the_others_stay_in_it(connect):
    mara, tiago, ines, code = running_round_of_three(connect)
    assert ask(tiago, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    expected = state(code, "Mara", ("Mara", FIRST), ("Ines", THIRD), phase="round")
    assert mara.receive_json() == expected
    assert ines.receive_json() == expected
    read_progress_without(mara, "Tiago")
    read_progress_without(ines, "Tiago")


def test_a_member_disconnects_and_the_others_stay_in_the_round(connect):
    mara, tiago, ines, code = running_round_of_three(connect)
    ines.close()
    expected = state(code, "Mara", ("Mara", FIRST), ("Tiago", SECOND), phase="round")
    assert mara.receive_json() == expected
    assert tiago.receive_json() == expected
    read_progress_without(mara, "Ines")
    read_progress_without(tiago, "Ines")


def test_the_host_leaves_the_round_and_the_next_player_is_host(connect):
    mara, tiago, ines, code = running_round_of_three(connect)
    mara.close()
    expected = state(code, "Tiago", ("Tiago", SECOND), ("Ines", THIRD), phase="round")
    for connection in (tiago, ines):
        assert connection.receive_json() == {"type": "notice", "message": "The host left. Tiago is the new host."}
        assert connection.receive_json() == expected
        read_progress_without(connection, "Mara")
    # The new host cannot start the running round a second time.
    assert start(tiago) == ROUND_RUNNING


def test_a_round_that_everybody_left_is_gone(connect):
    mara = player(connect, "Mara")
    tiago = player(connect, "Tiago")
    code = ask(mara, {"type": "create_lobby"})["code"]
    ask(tiago, {"type": "join_lobby", "code": code})
    mara.receive_json()
    start(mara)
    tiago.receive_json()
    ask(mara, {"type": "leave_lobby"})
    ask(tiago, {"type": "leave_lobby"})
    assert app.state.lobbies.find(code) is None
    assert ask(player(connect, "Ines"), {"type": "join_lobby", "code": code})["code"] == "no_lobby"


def test_classic_round_sends_each_living_player_a_private_role_card(connect):
    mara, tiago, ines, code = lobby_of_three(connect)
    rui = player(connect, "Rui")
    assert ask(rui, {"type": "join_lobby", "code": code})["phase"] == "lobby"
    for connection in (mara, tiago, ines):
        connection.receive_json()

    chosen = choose_mode(mara, "classic")
    for connection in (tiago, ines, rui):
        connection.receive_json()
    assert chosen["mode"] == "classic"

    assert start(mara)["phase"] == "round"
    for connection in (tiago, ines, rui):
        connection.receive_json()

    cards = [connection.receive_json() for connection in (mara, tiago, ines, rui)]
    assert all(card["type"] == "classic_role" for card in cards)
    assert all(card["role"] in {"HP", "FR"} for card in cards)
    assert sum(card["role"] == "FR" for card in cards) == 1
    assert all("other_free_riders" not in card for card in cards if card["role"] == "HP")
    for connection, card in zip((mara, tiago, ines, rui), cards):
        if card["role"] == "FR":
            assert connection.receive_json() == {"type": "you_are_fr"}
            fail_status = connection.receive_json()
            assert fail_status["type"] == "classic_fail_status"
            assert fail_status["cooldown_until"] is None
    progress_messages = [connection.receive_json() for connection in (mara, tiago, ines, rui)]
    assert all(set(message) == {
        "type", "progress", "server_time", "emergency_ready_at"
    } for message in progress_messages)
    assert all(message["type"] == "classic_progress" and message["progress"] == 0.0 for message in progress_messages)
    assert all(isinstance(message["server_time"], (int, float)) for message in progress_messages)
    assert all(
        message["emergency_ready_at"] - message["server_time"] == pytest.approx(45.0, abs=0.01)
        for message in progress_messages
    )
