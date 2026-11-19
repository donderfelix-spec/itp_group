"""Creating, joining and leaving lobbies over the WebSocket, with several players."""

import asyncio
import contextlib
import re
import time

import pytest
from fastapi.testclient import TestClient

from server import main, protocol
from server.main import app

PASSWORD = "password123"
FIRST, SECOND, THIRD = protocol.CHARACTERS[:3]


@pytest.fixture
def client():
    # Used as a context manager, the test client runs all its connections in
    # one event loop, like the real server does. Without it every connection
    # gets a loop of its own, and a message from one player's handler to
    # another player's connection can get lost on the way to the test.
    with TestClient(app) as shared_client:
        yield shared_client


@pytest.fixture
def connect(client):
    """A function that opens one more connection. All of them are closed after the test."""
    with contextlib.ExitStack() as open_connections:
        yield lambda: open_connections.enter_context(client.websocket_connect("/ws"))


def wait_until(condition, seconds=2.0):
    """Wait until the server has caught up. Fails if it takes too long."""
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "the server did not get there in time"
        time.sleep(0.01)


def ask(connection, message):
    """Send one message and return the next message the server sends."""
    connection.send_json(message)
    return connection.receive_json()


def player(connect, name):
    """A new connection, signed in with a new account of this name."""
    connection = connect()
    answer = ask(connection, {"type": "sign_up", "name": name, "password": PASSWORD})
    assert answer["type"] == "signed_in"
    return connection


def guest(connect):
    connection = connect()
    assert ask(connection, {"type": "guest"})["type"] == "signed_in"
    return connection


def create(connection):
    return ask(connection, {"type": "create_lobby"})


def join(connection, code):
    return ask(connection, {"type": "join_lobby", "code": code})


def leave(connection):
    return ask(connection, {"type": "leave_lobby"})


def choose(connection, character):
    return ask(connection, {"type": "choose_character", "character": character})


def still_works(connection):
    """True if the next message is the answer to a hello: nothing else was waiting."""
    return ask(connection, {"type": "hello", "name": "Mara"})["type"] == "welcome"


def mara_and_tiago_in_a_lobby(connect):
    """Mara creates a lobby, Tiago joins. Returns both connections and the code."""
    mara = player(connect, "Mara")
    tiago = player(connect, "Tiago")
    code = create(mara)["code"]
    join(tiago, code)
    mara.receive_json()  # Mara's copy of the state after Tiago joined.
    return mara, tiago, code


def state(code, host, *players):
    return protocol.lobby_state(code, host, players)


TIAGO_IS_HOST = {"type": "notice", "message": "The host left. Tiago is the new host."}


# Creating and joining


def test_create_lobby_answers_with_the_state(connect, monkeypatch):
    monkeypatch.setattr(main, "pick_lobby_code", lambda: "ABCD")
    mara = player(connect, "Mara")
    assert create(mara) == {
        "type": "lobby_state",
        "code": "ABCD",
        "host": "Mara",
        "players": [{"name": "Mara", "character": FIRST}],
        "mode": "duel",
        "phase": "lobby",
    }


def test_the_real_code_is_four_capital_letters(connect):
    mara = player(connect, "Mara")
    assert re.fullmatch(r"[A-Z]{4}", create(mara)["code"])
    assert re.fullmatch(r"[A-Z]{4}", main.pick_lobby_code())


def test_a_code_in_use_is_not_given_out_twice(connect, monkeypatch):
    picks = ["ABCD", "ABCD", "WXYZ"]
    monkeypatch.setattr(main, "pick_lobby_code", lambda: picks.pop(0))
    assert create(player(connect, "Mara"))["code"] == "ABCD"
    assert create(player(connect, "Tiago"))["code"] == "WXYZ"


def test_join_in_lower_case_and_both_get_the_same_state(connect):
    mara = player(connect, "Mara")
    tiago = player(connect, "Tiago")
    code = create(mara)["code"]
    expected = state(code, "Mara", ("Mara", FIRST), ("Tiago", SECOND))
    assert join(tiago, code.lower()) == expected
    assert mara.receive_json() == expected


def test_a_guest_can_create_and_an_account_can_join(connect):
    first = guest(connect)
    created = create(first)
    guest_name = created["host"]
    assert re.fullmatch(r"Guest\d{4}", guest_name)
    mara = player(connect, "Mara")
    expected = state(created["code"], guest_name, (guest_name, FIRST), ("Mara", SECOND))
    assert join(mara, created["code"]) == expected
    assert first.receive_json() == expected


def test_the_state_never_says_more_than_names_characters_code_and_host(connect):
    mara, tiago, code = mara_and_tiago_in_a_lobby(connect)
    answer = choose(tiago, "surfer")
    assert set(answer) == {"type", "code", "host", "players", "mode", "phase"}
    assert all(set(listed) == {"name", "character"} for listed in answer["players"])


# The ninth player and unknown codes


def test_a_ninth_player_gets_lobby_full(connect):
    host = guest(connect)
    code = create(host)["code"]
    members = [host]
    for number in range(7):
        joiner = guest(connect)
        assert join(joiner, code)["type"] == "lobby_state"
        for member in members:
            member.receive_json()
        members.append(joiner)

    ninth = guest(connect)
    assert join(ninth, code) == {"type": "error", "code": "lobby_full", "message": "This lobby is full."}
    # Nothing changed for the eight inside, and the ninth can go on.
    assert all(still_works(member) for member in members)
    assert create(ninth)["type"] == "lobby_state"


def test_an_unknown_code_gets_no_lobby(connect):
    mara = player(connect, "Mara")
    assert join(mara, "ABCD") == {"type": "error", "code": "no_lobby", "message": "No lobby with that code."}
    assert create(mara)["type"] == "lobby_state"


def test_a_code_that_is_not_four_letters_is_refused_by_the_message_check(connect):
    mara = player(connect, "Mara")
    assert join(mara, "ABC1") == {"type": "error", "code": "bad_code", "message": "Lobby codes are 4 letters."}
    assert still_works(mara)


# Permissions


@pytest.mark.parametrize(
    "message",
    [
        {"type": "create_lobby"},
        {"type": "join_lobby", "code": "ABCD"},
        {"type": "leave_lobby"},
        {"type": "choose_character", "character": "surfer"},
    ],
)
def test_lobby_messages_need_a_signed_in_player(connect, message):
    stranger = connect()
    assert ask(stranger, message) == {
        "type": "error",
        "code": "not_signed_in",
        "message": "Log in or play as a guest first.",
    }
    assert app.state.lobbies.count() == 0
    # The connection still works: the player can enter and create a lobby.
    assert ask(stranger, {"type": "guest"})["type"] == "signed_in"
    assert create(stranger)["type"] == "lobby_state"


def test_a_signed_out_player_cannot_join_an_existing_lobby(connect):
    mara = player(connect, "Mara")
    code = create(mara)["code"]
    stranger = connect()
    assert join(stranger, code) == protocol.rejection("not_signed_in")
    assert still_works(mara)  # Mara was not sent a new state.


def test_create_or_join_while_in_a_lobby_is_rejected(connect):
    mara = player(connect, "Mara")
    tiago = player(connect, "Tiago")
    code = create(mara)["code"]
    other_code = create(tiago)["code"]
    expected = {"type": "error", "code": "already_in_lobby", "message": "Leave your lobby first."}
    assert create(mara) == expected
    assert join(mara, other_code) == expected
    assert join(mara, code) == expected
    # Nothing changed and nobody else was told anything.
    assert still_works(tiago)
    assert choose(mara, "surfer") == state(code, "Mara", ("Mara", "surfer"))


def test_leave_or_choose_outside_a_lobby_is_rejected(connect):
    mara = player(connect, "Mara")
    expected = {"type": "error", "code": "not_in_lobby", "message": "You are not in a lobby."}
    assert leave(mara) == expected
    assert choose(mara, "surfer") == expected
    assert create(mara)["type"] == "lobby_state"


def test_move_is_not_answered_yet_even_in_a_lobby(connect):
    mara = player(connect, "Mara")
    create(mara)
    mara.send_json({"type": "move", "dx": 1, "dy": 0})
    assert still_works(mara)


# Characters


def test_choosing_a_taken_character_is_rejected(connect):
    mara, tiago, code = mara_and_tiago_in_a_lobby(connect)
    assert choose(tiago, FIRST) == {
        "type": "error",
        "code": "character_taken",
        "message": "That character is taken.",
    }
    assert still_works(mara)  # No new state for Mara: nothing changed.
    assert choose(tiago, SECOND) == state(code, "Mara", ("Mara", FIRST), ("Tiago", SECOND))


def test_choosing_a_free_character_tells_both(connect):
    mara, tiago, code = mara_and_tiago_in_a_lobby(connect)
    expected = state(code, "Mara", ("Mara", FIRST), ("Tiago", "surfer"))
    assert choose(tiago, "surfer") == expected
    assert mara.receive_json() == expected


def test_a_character_that_does_not_exist_is_refused_by_the_message_check(connect):
    mara, tiago, code = mara_and_tiago_in_a_lobby(connect)
    assert choose(tiago, "dragon")["code"] == "bad_character"
    assert still_works(mara)


def test_choosing_the_character_you_have_answers_only_you(connect):
    mara, tiago, code = mara_and_tiago_in_a_lobby(connect)
    assert choose(tiago, SECOND) == state(code, "Mara", ("Mara", FIRST), ("Tiago", SECOND))
    assert still_works(mara)  # Nothing changed, so Mara was not told anything.
    assert still_works(tiago)  # And Tiago got exactly one answer.


# Leaving


def test_a_member_leaves_and_the_host_gets_the_new_state(connect):
    mara, tiago, code = mara_and_tiago_in_a_lobby(connect)
    assert leave(tiago) == {"type": "left_lobby"}
    assert mara.receive_json() == state(code, "Mara", ("Mara", FIRST))
    # No notice: the host did not change. Tiago can come back.
    assert still_works(mara)
    assert join(tiago, code)["type"] == "lobby_state"


def test_the_host_leaves_and_the_next_player_becomes_host(connect):
    mara, tiago, code = mara_and_tiago_in_a_lobby(connect)
    assert leave(mara) == {"type": "left_lobby"}
    assert tiago.receive_json() == TIAGO_IS_HOST
    assert tiago.receive_json() == state(code, "Tiago", ("Tiago", SECOND))
    # Mara is outside now: she gets nothing more and may not act in the lobby.
    assert leave(mara) == protocol.rejection("not_in_lobby")


def test_the_host_goes_to_the_player_who_is_in_the_lobby_longest(connect):
    mara, tiago, code = mara_and_tiago_in_a_lobby(connect)
    ines = player(connect, "Ines")
    join(ines, code)
    mara.receive_json()
    tiago.receive_json()

    leave(mara)
    expected = state(code, "Tiago", ("Tiago", SECOND), ("Ines", THIRD))
    for connection in (tiago, ines):
        assert connection.receive_json() == TIAGO_IS_HOST
        assert connection.receive_json() == expected


def test_the_host_closes_the_connection(connect):
    mara, tiago, code = mara_and_tiago_in_a_lobby(connect)
    mara.close()
    assert tiago.receive_json() == TIAGO_IS_HOST
    assert tiago.receive_json() == state(code, "Tiago", ("Tiago", SECOND))


def test_the_host_logs_out(connect):
    mara, tiago, code = mara_and_tiago_in_a_lobby(connect)
    assert ask(mara, {"type": "log_out"}) == {"type": "signed_out"}
    assert tiago.receive_json() == TIAGO_IS_HOST
    assert tiago.receive_json() == state(code, "Tiago", ("Tiago", SECOND))
    # Mara can log in again and is in no lobby.
    assert ask(mara, {"type": "log_in", "name": "Mara", "password": PASSWORD})["type"] == "signed_in"
    assert leave(mara) == protocol.rejection("not_in_lobby")


def test_the_host_logs_in_on_another_connection(connect):
    mara, tiago, code = mara_and_tiago_in_a_lobby(connect)
    new_mara = connect()
    answer = ask(new_mara, {"type": "log_in", "name": "Mara", "password": PASSWORD})
    assert answer == {"type": "signed_in", "name": "Mara", "guest": False}
    assert mara.receive_json() == {"type": "signed_out"}
    assert tiago.receive_json() == TIAGO_IS_HOST
    assert tiago.receive_json() == state(code, "Tiago", ("Tiago", SECOND))

    # The new connection is in no lobby and received nothing of the lobby.
    assert leave(new_mara) == protocol.rejection("not_in_lobby")
    # It can join like anybody else, now at the end of the line.
    expected = state(code, "Tiago", ("Tiago", SECOND), ("Mara", FIRST))
    assert join(new_mara, code) == expected
    assert tiago.receive_json() == expected
    # The old connection is outside and gets nothing of this.
    assert still_works(mara)


class ClosedWebSocket:
    """Stands in for a WebSocket whose player has just closed the page."""

    async def accept(self):
        pass

    async def receive(self):
        return {"type": "websocket.disconnect"}


def test_closing_the_replaced_connection_does_not_take_the_new_one_out(connect):
    # Called directly with a stand-in, because a real test connection cannot
    # be closed at an exact moment. The old connection was signed in as Mara
    # and has already been replaced by the new one (S-76).
    old_mara = ClosedWebSocket()
    new_mara = player(connect, "Mara")
    code = create(new_mara)["code"]

    asyncio.run(main.game_socket(old_mara))

    # Mara's lobby is still there, with her in it.
    assert choose(new_mara, "surfer") == state(code, "Mara", ("Mara", "surfer"))


def test_a_member_who_disconnects_is_taken_out(connect):
    mara, tiago, code = mara_and_tiago_in_a_lobby(connect)
    tiago.close()
    assert mara.receive_json() == state(code, "Mara", ("Mara", FIRST))


def test_a_guest_who_leaves_frees_the_place_in_the_lobby(connect):
    mara = player(connect, "Mara")
    visitor = guest(connect)
    code = create(mara)["code"]
    join(visitor, code)
    mara.receive_json()
    assert ask(visitor, {"type": "log_out"}) == {"type": "signed_out"}
    assert mara.receive_json() == state(code, "Mara", ("Mara", FIRST))


# The last player leaves


def test_after_the_last_player_left_the_code_is_gone(connect):
    mara, tiago, code = mara_and_tiago_in_a_lobby(connect)
    leave(mara)
    tiago.receive_json()
    tiago.receive_json()
    assert leave(tiago) == {"type": "left_lobby"}
    assert join(mara, code) == protocol.rejection("no_lobby")
    assert app.state.lobbies.count() == 0


def test_a_lobby_whose_only_player_disconnects_is_deleted(connect):
    mara = player(connect, "Mara")
    tiago = player(connect, "Tiago")
    code = create(mara)["code"]
    mara.close()
    wait_until(lambda: app.state.lobbies.find(code) is None)
    assert join(tiago, code) == protocol.rejection("no_lobby")
    assert app.state.lobbies.count() == 0


# Two lobbies


def test_two_lobbies_do_not_see_each_other(connect):
    mara, tiago, code = mara_and_tiago_in_a_lobby(connect)
    ines = player(connect, "Ines")
    joao = player(connect, "Joao")
    other_code = create(ines)["code"]
    assert code != other_code
    join(joao, other_code)
    ines.receive_json()

    # A character change and a host change in the first lobby.
    choose(tiago, "surfer")
    mara.receive_json()
    leave(mara)
    tiago.receive_json()
    tiago.receive_json()

    # The second lobby received none of it and is unchanged.
    assert still_works(ines)
    assert still_works(joao)
    expected = state(other_code, "Ines", ("Ines", FIRST), ("Joao", "founder"))
    assert choose(joao, "founder") == expected
    assert ines.receive_json() == expected
    # And the first lobby saw nothing of that.
    assert still_works(tiago)


# A member whose connection is going away


@pytest.mark.parametrize("send_error", [RuntimeError("closed"), OSError("broken")])
def test_a_member_who_cannot_be_reached_does_not_stop_the_others(connect, monkeypatch, send_error):
    mara, tiago, code = mara_and_tiago_in_a_lobby(connect)
    ines = player(connect, "Ines")

    async def broken_send(message):
        raise send_error

    # Mara is first in the list, so her failing send comes before the others'.
    monkeypatch.setattr(app.state.sessions.connection_of("Mara"), "send_json", broken_send)

    expected = state(code, "Mara", ("Mara", FIRST), ("Tiago", SECOND), ("Ines", THIRD))
    assert join(ines, code) == expected
    assert tiago.receive_json() == expected
    # The handlers of the others are alive.
    assert choose(ines, "surfer")["type"] == "lobby_state"
    assert tiago.receive_json()["type"] == "lobby_state"
    assert leave(tiago) == {"type": "left_lobby"}


# Sending to the members of a lobby (review findings on M1-2.2).
# These call the server's functions directly with stand-ins for the
# WebSockets, because a real test connection cannot get stuck or act at an
# exact moment.


class FakeWebSocket:
    """Stands in for a WebSocket. `on_send` is called whenever the server sends to it."""

    def __init__(self, on_send=None):
        self.sent = []
        self.closed = False
        self._on_send = on_send

    async def accept(self):
        pass

    async def receive(self):
        return {"type": "websocket.disconnect"}  # The player closes the page at once.

    async def send_json(self, message):
        if self._on_send is not None:
            self._on_send()
        self.sent.append(message)

    async def close(self):
        self.closed = True


class StuckWebSocket(FakeWebSocket):
    """A browser that has stopped reading: a send to it never returns."""

    def __init__(self, close_error=None):
        super().__init__()
        self._close_error = close_error

    async def send_json(self, message):
        await asyncio.Event().wait()  # Nobody ever sets this event.

    async def close(self):
        self.closed = True
        if self._close_error is not None:
            raise self._close_error


def fake_lobby(**websockets):
    """Sign the stand-ins in under their names and put them in one lobby, in order."""
    names = list(websockets)
    for name, websocket in websockets.items():
        app.state.sessions.sign_in_account(websocket, name)
    lobby, rejection_code = app.state.lobbies.create(names[0], lambda: "ABCD")
    for name in names[1:]:
        app.state.lobbies.join(name, "ABCD")
    return lobby


def run_and_time(coroutine):
    """Run the coroutine and return how many seconds it took."""
    started = time.monotonic()
    asyncio.run(coroutine)
    return time.monotonic() - started


@pytest.fixture
def short_timeout(monkeypatch):
    monkeypatch.setattr(main, "SEND_TIMEOUT_SECONDS", 0.05)


def test_sends_have_a_time_limit_of_two_seconds():
    assert main.SEND_TIMEOUT_SECONDS == 2


def test_a_member_who_stopped_reading_does_not_hold_up_a_join(short_timeout):
    mara, tiago, ines = StuckWebSocket(), FakeWebSocket(), FakeWebSocket()
    fake_lobby(Mara=mara, Tiago=tiago)
    app.state.sessions.sign_in_account(ines, "Ines")

    seconds = run_and_time(main.answer_lobby_message(ines, {"type": "join_lobby", "code": "ABCD"}))

    expected = state("ABCD", "Mara", ("Mara", FIRST), ("Tiago", SECOND), ("Ines", THIRD))
    assert tiago.sent == [expected]
    assert ines.sent == [expected]
    assert seconds < 1  # Without the limit this would never return.
    assert mara.closed  # So she cannot hold up the lobby a second time.


def test_a_member_who_stopped_reading_does_not_hold_up_a_leaving_host(short_timeout):
    mara, tiago, ines = FakeWebSocket(), StuckWebSocket(), FakeWebSocket()
    fake_lobby(Mara=mara, Tiago=tiago, Ines=ines)

    seconds = run_and_time(main.answer_lobby_message(mara, {"type": "leave_lobby"}))

    assert mara.sent == [{"type": "left_lobby"}]
    assert ines.sent == [TIAGO_IS_HOST, state("ABCD", "Tiago", ("Tiago", SECOND), ("Ines", THIRD))]
    assert seconds < 1
    # Tiago was closed after the notice timed out; the state was not tried as well.
    assert tiago.closed


def test_a_member_who_stopped_reading_does_not_hold_up_a_log_out(short_timeout):
    mara, tiago = FakeWebSocket(), StuckWebSocket()
    fake_lobby(Mara=mara, Tiago=tiago)
    seconds = run_and_time(main.answer_account_message(mara, {"type": "log_out"}))
    assert mara.sent == [{"type": "signed_out"}]
    assert seconds < 1


def test_a_member_who_stopped_reading_does_not_hold_up_the_cleanup_of_a_closed_connection(short_timeout):
    mara, tiago, ines = FakeWebSocket(), StuckWebSocket(), FakeWebSocket()
    lobby = fake_lobby(Mara=mara, Tiago=tiago, Ines=ines)
    seconds = run_and_time(main.game_socket(mara))  # Mara's connection closes.
    assert lobby.names() == ["Tiago", "Ines"]
    assert ines.sent == [TIAGO_IS_HOST, state("ABCD", "Tiago", ("Tiago", SECOND), ("Ines", THIRD))]
    assert seconds < 1


@pytest.mark.parametrize("close_error", [RuntimeError("already closed"), OSError("broken")])
def test_a_stuck_connection_that_cannot_be_closed_changes_nothing(short_timeout, close_error):
    mara, tiago, ines = StuckWebSocket(close_error), FakeWebSocket(), FakeWebSocket()
    fake_lobby(Mara=mara, Tiago=tiago)
    app.state.sessions.sign_in_account(ines, "Ines")
    asyncio.run(main.answer_lobby_message(ines, {"type": "join_lobby", "code": "ABCD"}))
    assert tiago.sent == ines.sent
    assert len(ines.sent) == 1


def test_a_connection_whose_send_fails_is_not_closed():
    def fail():
        raise RuntimeError("closed")

    mara, tiago = FakeWebSocket(on_send=fail), FakeWebSocket()
    lobby = fake_lobby(Mara=mara, Tiago=tiago)
    asyncio.run(main.tell_lobby(lobby))
    assert tiago.sent == [state("ABCD", "Mara", ("Mara", FIRST), ("Tiago", SECOND))]
    assert not mara.closed  # Its own handler deals with it.


def test_someone_who_left_during_a_broadcast_is_not_told():
    # While the server sends to Mara, Ines leaves. The server must notice
    # that before it sends to Ines, and Tiago must get the state without her.
    mara = FakeWebSocket(on_send=lambda: app.state.lobbies.leave("Ines"))
    tiago, ines = FakeWebSocket(), FakeWebSocket()
    lobby = fake_lobby(Mara=mara, Tiago=tiago, Ines=ines)

    asyncio.run(main.tell_lobby(lobby))

    assert ines.sent == []
    assert tiago.sent == [state("ABCD", "Mara", ("Mara", FIRST), ("Tiago", SECOND))]


def test_someone_who_left_between_the_notice_and_the_state_gets_no_state():
    tiago = FakeWebSocket()
    ines = FakeWebSocket(on_send=lambda: app.state.lobbies.leave("Ines"))  # Leaves on the notice.
    lobby = fake_lobby(Mara=FakeWebSocket(), Tiago=tiago, Ines=ines)
    lobby, new_host, rejection_code = app.state.lobbies.leave("Mara")

    asyncio.run(main.tell_lobby(lobby, new_host))

    assert ines.sent == [TIAGO_IS_HOST]


def test_a_notice_about_a_host_who_is_no_longer_host_is_skipped():
    tiago, ines = FakeWebSocket(), FakeWebSocket()
    lobby = fake_lobby(Mara=FakeWebSocket(), Tiago=tiago, Ines=ines)
    # Mara leaves, Tiago becomes host; before anyone is told, Tiago leaves too.
    lobby, first_new_host, rejection_code = app.state.lobbies.leave("Mara")
    lobby, second_new_host, rejection_code = app.state.lobbies.leave("Tiago")
    assert (first_new_host, second_new_host) == ("Tiago", "Ines")

    asyncio.run(main.tell_lobby(lobby, first_new_host))  # The late news of the first change.

    # No "Tiago is the new host": only the state as it is now.
    assert ines.sent == [state("ABCD", "Ines", ("Ines", THIRD))]
    assert tiago.sent == []


def test_a_notice_about_the_current_host_is_sent():
    tiago, ines = FakeWebSocket(), FakeWebSocket()
    lobby = fake_lobby(Mara=FakeWebSocket(), Tiago=tiago, Ines=ines)
    lobby, new_host, rejection_code = app.state.lobbies.leave("Mara")
    asyncio.run(main.tell_lobby(lobby, new_host))
    expected = [TIAGO_IS_HOST, state("ABCD", "Tiago", ("Tiago", SECOND), ("Ines", THIRD))]
    assert tiago.sent == expected
    assert ines.sent == expected


def test_a_really_replaced_connection_that_closes_later_leaves_the_new_one_in_its_lobby(connect):
    # The old connection is a stand-in so that it can close at an exact
    # moment. It is signed in as Mara for real and then replaced by a real
    # log-in on a new connection (S-76).
    mara = player(connect, "Mara")
    ask(mara, {"type": "log_out"})
    old_mara = FakeWebSocket()
    app.state.sessions.sign_in_account(old_mara, "Mara")
    tiago = player(connect, "Tiago")
    code = create(tiago)["code"]

    assert ask(mara, {"type": "log_in", "name": "Mara", "password": PASSWORD})["type"] == "signed_in"
    assert not app.state.sessions.is_signed_in(old_mara)
    expected = state(code, "Tiago", ("Tiago", FIRST), ("Mara", SECOND))
    assert join(mara, code) == expected
    assert tiago.receive_json() == expected

    asyncio.run(main.game_socket(old_mara))  # Only now the old connection closes.

    # Mara is still signed in and still in the lobby, and Tiago was told nothing.
    assert app.state.lobbies.find(code).names() == ["Tiago", "Mara"]
    assert still_works(tiago)
    assert choose(mara, "surfer") == state(code, "Tiago", ("Tiago", FIRST), ("Mara", "surfer"))
