"""Signing up, logging in, logging out and guests over the WebSocket."""

import re

import pytest
from fastapi.testclient import TestClient

from server import protocol
from server.accounts.store import StoreUnavailable
from server.main import app

PASSWORD = "password123"


class BrokenStore:
    """A store whose database cannot be reached."""

    def add(self, name, password_hash):
        raise StoreUnavailable("down")

    def find(self, name):
        raise StoreUnavailable("down")


class CrashingStore:
    """A store with a bug: it raises something nobody expects."""

    def add(self, name, password_hash):
        raise RuntimeError("bug")

    def find(self, name):
        raise RuntimeError("bug")


@pytest.fixture
def client():
    # Used as a context manager, the test client runs all its connections in
    # one event loop, like the real server does. Without it every connection
    # gets a loop of its own, and `signed_out` from the second connection's
    # handler could fail to wake the first one: the test then hung (M1-2.20).
    with TestClient(app) as shared_client:
        yield shared_client


@pytest.fixture
def socket(client):
    with client.websocket_connect("/ws") as connection:
        yield connection


def ask(connection, message):
    """Send one message and return the answer."""
    connection.send_json(message)
    return connection.receive_json()


def sign_up(connection, name="Mara", password=PASSWORD):
    return ask(connection, {"type": "sign_up", "name": name, "password": password})


def log_in(connection, name="Mara", password=PASSWORD):
    return ask(connection, {"type": "log_in", "name": name, "password": password})


def guest(connection):
    return ask(connection, {"type": "guest"})


def log_out(connection):
    return ask(connection, {"type": "log_out"})


def still_works(connection):
    return ask(connection, {"type": "hello", "name": "Mara"})["type"] == "welcome"


# Accepted


def test_sign_up_log_out_and_log_in_again(socket):
    assert sign_up(socket) == {"type": "signed_in", "name": "Mara", "guest": False}
    assert log_out(socket) == {"type": "signed_out"}
    assert log_in(socket) == {"type": "signed_in", "name": "Mara", "guest": False}


def test_log_in_in_another_case_returns_the_stored_spelling(socket):
    sign_up(socket, "Mara")
    log_out(socket)
    assert log_in(socket, "mARA") == {"type": "signed_in", "name": "Mara", "guest": False}


def test_guest_gets_guest_plus_four_digits(socket):
    answer = guest(socket)
    assert answer["type"] == "signed_in"
    assert answer["guest"] is True
    assert re.fullmatch(r"Guest[0-9]{4}", answer["name"])


def test_a_guest_can_log_out_and_come_back(socket):
    guest(socket)
    assert log_out(socket) == {"type": "signed_out"}
    assert guest(socket)["type"] == "signed_in"


def test_two_guests_at_once_get_different_names(client, monkeypatch):
    # Both draw the same number, so the server has to move the second one on.
    monkeypatch.setattr("server.main.pick_guest_number", lambda: 4321)
    with client.websocket_connect("/ws") as first, client.websocket_connect("/ws") as second:
        assert guest(first)["name"] == "Guest4321"
        assert guest(second)["name"] == "Guest4322"


def test_hello_is_still_answered_while_signed_in(socket):
    sign_up(socket)
    assert still_works(socket)


# Rejected. Each answer carries the exact text and the connection keeps working.


def test_sign_up_with_a_taken_name_is_rejected(socket):
    sign_up(socket)
    log_out(socket)
    assert sign_up(socket, "Mara", "otherpassword") == protocol.rejection("name_taken")
    assert sign_up(socket, "mARA", "otherpassword") == protocol.rejection("name_taken")
    assert still_works(socket)
    # The first password still belongs to the account.
    assert log_in(socket)["type"] == "signed_in"


@pytest.mark.parametrize("name", ["Guest1234", "guest7"])
def test_sign_up_with_a_guest_name_is_rejected(socket, name):
    answer = sign_up(socket, name)
    assert answer == {"type": "error", "code": "name_taken", "message": "That username is taken."}
    assert still_works(socket)


def test_log_in_with_a_wrong_password_is_rejected(socket):
    sign_up(socket)
    log_out(socket)
    answer = log_in(socket, "Mara", "wrongpassword")
    assert answer == {"type": "error", "code": "wrong_credentials", "message": "Wrong username or password."}
    assert still_works(socket)
    assert log_in(socket)["type"] == "signed_in"


def test_log_in_with_an_unknown_name_is_rejected_the_same_way(socket):
    assert log_in(socket, "Nobody") == protocol.rejection("wrong_credentials")
    assert still_works(socket)


def test_a_rejected_log_in_does_not_sign_in(socket):
    log_in(socket, "Nobody")
    assert log_out(socket) == protocol.rejection("not_signed_in")


def test_sign_up_with_a_too_short_password_is_rejected(socket):
    answer = sign_up(socket, "Mara", "short")
    assert answer["type"] == "error"
    assert answer["code"] == "bad_password"
    assert still_works(socket)
    # No account was created.
    assert log_in(socket, "Mara", "short") == protocol.rejection("wrong_credentials")


@pytest.mark.parametrize(
    "second",
    [
        {"type": "sign_up", "name": "Tiago", "password": PASSWORD},
        {"type": "log_in", "name": "Mara", "password": PASSWORD},
        {"type": "guest"},
    ],
)
def test_signing_in_twice_on_one_connection_is_rejected(socket, second):
    sign_up(socket)
    answer = ask(socket, second)
    assert answer == {"type": "error", "code": "already_signed_in", "message": "Log out first."}
    assert still_works(socket)
    # Still signed in as before: logging out works exactly once.
    assert log_out(socket) == {"type": "signed_out"}


def test_a_guest_cannot_sign_in_again_without_logging_out(socket):
    guest(socket)
    assert guest(socket) == protocol.rejection("already_signed_in")
    assert sign_up(socket) == protocol.rejection("already_signed_in")


def test_a_refused_second_sign_up_creates_no_account(socket):
    sign_up(socket)
    sign_up(socket, "Tiago")
    log_out(socket)
    assert log_in(socket, "Tiago") == protocol.rejection("wrong_credentials")


def test_log_out_when_signed_out_is_rejected(socket):
    answer = log_out(socket)
    assert answer == {"type": "error", "code": "not_signed_in", "message": "Log in or play as a guest first."}
    assert still_works(socket)


def test_log_out_twice_is_rejected_the_second_time(socket):
    guest(socket)
    log_out(socket)
    assert log_out(socket) == protocol.rejection("not_signed_in")


# Two connections


def test_a_second_log_in_signs_the_first_connection_out(client):
    with client.websocket_connect("/ws") as first, client.websocket_connect("/ws") as second:
        sign_up(first, "Mara")
        assert log_in(second, "mara") == {"type": "signed_in", "name": "Mara", "guest": False}
        assert first.receive_json() == {"type": "signed_out"}
        # The first connection is signed out for real and can go on as a guest.
        assert guest(first)["guest"] is True
        # The second one is still Mara.
        assert log_out(second) == {"type": "signed_out"}


def test_two_different_accounts_do_not_disturb_each_other(client):
    with client.websocket_connect("/ws") as first, client.websocket_connect("/ws") as second:
        sign_up(first, "Mara")
        sign_up(second, "Tiago")
        assert log_out(first) == {"type": "signed_out"}
        assert log_out(second) == {"type": "signed_out"}


def test_a_closed_connection_is_forgotten(client):
    with client.websocket_connect("/ws") as first:
        sign_up(first, "Mara")
    with client.websocket_connect("/ws") as second:
        assert log_in(second, "Mara")["type"] == "signed_in"
    assert app.state.sessions._signed_in == {}


def test_the_guest_name_of_a_closed_connection_is_free_again(client, monkeypatch):
    monkeypatch.setattr("server.main.pick_guest_number", lambda: 4321)
    with client.websocket_connect("/ws") as first:
        assert guest(first)["name"] == "Guest4321"
    with client.websocket_connect("/ws") as second:
        assert guest(second)["name"] == "Guest4321"


# The database is down


def test_without_the_database_accounts_are_unavailable_but_guests_work(socket):
    app.state.account_store = BrokenStore()
    unavailable = {
        "type": "error",
        "code": "accounts_unavailable",
        "message": "Accounts are unavailable right now. You can still play as a guest.",
    }
    assert sign_up(socket) == unavailable
    assert log_in(socket) == unavailable
    assert still_works(socket)
    assert guest(socket)["guest"] is True


def test_an_unexpected_error_in_the_store_does_not_close_the_connection(socket):
    app.state.account_store = CrashingStore()
    assert sign_up(socket) == protocol.rejection("accounts_unavailable")
    assert log_in(socket) == protocol.rejection("accounts_unavailable")
    assert still_works(socket)
    assert guest(socket)["guest"] is True


# What is stored


def test_only_an_argon2_hash_is_stored(socket):
    sign_up(socket, "Mara", "a-very-secret-password")
    stored_name, password_hash = app.state.account_store.find("Mara")
    assert stored_name == "Mara"
    assert password_hash.startswith("$argon2")
    assert "a-very-secret-password" not in repr(app.state.account_store._accounts)


# Messages of later to-dos


def test_a_movement_message_needs_a_signed_in_player(socket):
    # Until walking was built (M1-2.3) this test checked that `move` got no
    # answer at all. Walking is tested in test_server_walking.py.
    assert ask(socket, {"type": "move", "dx": 1, "dy": 0}) == {
        "type": "error",
        "code": "not_signed_in",
        "message": "Log in or play as a guest first.",
    }
    assert ask(socket, {"type": "hello", "name": "Mara"})["type"] == "welcome"


# Players who vanish in the middle of something (review findings on M1-2.0).
# These call the server's functions directly with a fake WebSocket, because a
# real test connection cannot disappear at an exact moment.

import asyncio  # noqa: E402

from fastapi import WebSocketDisconnect  # noqa: E402
from starlette.websockets import WebSocketState  # noqa: E402

from server import main  # noqa: E402
from server.accounts import service  # noqa: E402


class FakeWebSocket:
    """Stands in for a WebSocket. `frames` are the messages the player sends."""

    def __init__(self, frames=(), connected=True, send_error=None):
        state = WebSocketState.CONNECTED if connected else WebSocketState.DISCONNECTED
        self.client_state = state
        self.application_state = WebSocketState.CONNECTED
        self.sent = []
        self._frames = list(frames)
        self._send_error = send_error

    async def accept(self):
        pass

    async def receive(self):
        if self._frames:
            return {"type": "websocket.receive", "text": self._frames.pop(0)}
        return {"type": "websocket.disconnect"}

    async def send_json(self, message):
        if self._send_error is not None:
            raise self._send_error
        self.sent.append(message)


MARA = {"type": "log_in", "name": "Mara", "password": PASSWORD}


def make_account_mara():
    name, rejection_code = service.sign_up(app.state.account_store, app.state.hasher, "Mara", PASSWORD)
    assert rejection_code is None


def test_a_log_in_on_a_fake_connection_works_like_a_real_one():
    make_account_mara()
    websocket = FakeWebSocket()
    asyncio.run(main.answer_account_message(websocket, MARA))
    assert websocket.sent == [{"type": "signed_in", "name": "Mara", "guest": False}]
    assert app.state.sessions.name_of(websocket) == "Mara"


def test_a_connection_that_closed_during_the_password_check_is_not_signed_in():
    make_account_mara()
    living = FakeWebSocket()
    app.state.sessions.sign_in_account(living, "Mara")
    gone = FakeWebSocket(connected=False)

    asyncio.run(main.answer_account_message(gone, MARA))

    assert gone.sent == []
    assert not app.state.sessions.is_signed_in(gone)
    # The living session of the same account was left alone.
    assert app.state.sessions.name_of(living) == "Mara"
    assert living.sent == []


@pytest.mark.parametrize("send_error", [WebSocketDisconnect(1006), RuntimeError("not connected")])
def test_a_log_in_whose_answer_cannot_be_sent_signs_nobody_out(send_error):
    make_account_mara()
    living = FakeWebSocket()
    app.state.sessions.sign_in_account(living, "Mara")
    gone = FakeWebSocket(send_error=send_error)

    with pytest.raises(type(send_error)):
        asyncio.run(main.answer_account_message(gone, MARA))

    assert not app.state.sessions.is_signed_in(gone)
    assert app.state.sessions.name_of(living) == "Mara"
    assert living.sent == []


@pytest.mark.parametrize("send_error", [WebSocketDisconnect(1006), RuntimeError("not connected")])
@pytest.mark.parametrize(
    "frame",
    [
        '{"type": "hello", "name": "Mara"}',
        "not json",
        '{"type": "guest"}',
        '{"type": "log_out"}',
        '{"type": "log_in", "name": "Mara", "password": "password123"}',
    ],
)
def test_a_send_to_a_player_who_is_gone_ends_the_handler_quietly(frame, send_error):
    make_account_mara()
    websocket = FakeWebSocket(frames=[frame], send_error=send_error)
    asyncio.run(main.game_socket(websocket))  # must not raise
    assert not app.state.sessions.is_signed_in(websocket)


def test_the_new_log_in_gets_its_answer_before_the_old_connection_is_told():
    make_account_mara()
    order = []
    old = FakeWebSocket()
    new = FakeWebSocket()
    old.send_json = lambda message: record(order, "old", message)
    new.send_json = lambda message: record(order, "new", message)
    app.state.sessions.sign_in_account(old, "Mara")

    async def log_in_and_let_the_background_send_finish():
        await main.answer_account_message(new, MARA)
        await asyncio.gather(*main.background_sends)

    asyncio.run(log_in_and_let_the_background_send_finish())
    assert order == [("new", "signed_in"), ("old", "signed_out")]
    assert app.state.sessions.name_of(new) == "Mara"
    assert not app.state.sessions.is_signed_in(old)


async def record(order, who, message):
    order.append((who, message["type"]))


def test_a_log_in_still_succeeds_when_the_replaced_connection_cannot_be_told(client, monkeypatch):
    with client.websocket_connect("/ws") as first, client.websocket_connect("/ws") as second:
        sign_up(first, "Mara")
        [old_websocket] = list(app.state.sessions._signed_in)

        async def broken_send(message):
            raise RuntimeError("the old connection is broken")

        monkeypatch.setattr(old_websocket, "send_json", broken_send)

        assert log_in(second, "Mara") == {"type": "signed_in", "name": "Mara", "guest": False}
        assert still_works(second)
        # The new connection really is Mara now, and the old one is signed out.
        assert app.state.sessions.name_of(old_websocket) is None
        assert log_out(second) == {"type": "signed_out"}


def test_a_slow_old_connection_does_not_delay_the_new_log_in():
    make_account_mara()
    old = FakeWebSocket()
    new = FakeWebSocket()
    app.state.sessions.sign_in_account(old, "Mara")

    async def scenario():
        never = asyncio.Event()

        async def stuck_send(message):
            await never.wait()

        old.send_json = stuck_send
        # Finishes although the send to the old connection never does.
        await asyncio.wait_for(main.answer_account_message(new, MARA), timeout=5)
        for task in list(main.background_sends):
            task.cancel()

    asyncio.run(scenario())
    assert new.sent == [{"type": "signed_in", "name": "Mara", "guest": False}]


def test_account_calls_run_on_four_workers():
    # S-211: four, so a slow database keeps fewer players waiting. The memory
    # of Argon2 is kept in bounds by the hasher itself: see
    # test_at_most_two_passwords_are_hashed_at_the_same_moment.
    assert main.account_workers._max_workers == 4
