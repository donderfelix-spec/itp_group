"""The limit on failed log-ins and wrong lobby codes, over the WebSocket (M1-2.6).

The plain rule is tested in test_attempts.py. Here the server is asked: does
it refuse at the right moment, before it hashes a password or asks the
lobbies, and does everything else on the connection still work?
"""

import contextlib
import time

import pytest
from fastapi.testclient import TestClient

from server import main
from server.accounts.store import StoreUnavailable
from server.main import app
from server.net.attempts import (
    JOIN_LOBBY_FAILURES_ALLOWED,
    JOIN_LOBBY_WINDOW_SECONDS,
    LOG_IN_FAILURES_ALLOWED,
    LOG_IN_WINDOW_SECONDS,
)

PASSWORD = "password123"
WRONG_PASSWORD = "not-the-password"

WRONG_CREDENTIALS = {"type": "error", "code": "wrong_credentials", "message": "Wrong username or password."}
NO_LOBBY = {"type": "error", "code": "no_lobby", "message": "No lobby with that code."}
TOO_MANY = {
    "type": "error",
    "code": "too_many_attempts",
    "message": "Too many attempts. Try again in a minute.",
}


class Clock:
    """Stands in for `main.seconds_now`, so the test decides how late it is."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def wait(self, seconds):
        self.now += seconds


class CountingHasher:
    """The real hasher, but it counts how often a password was checked."""

    def __init__(self, hasher):
        self._hasher = hasher
        self.dummy_hash = hasher.dummy_hash
        self.checks = 0

    def hash(self, password):
        return self._hasher.hash(password)

    def matches(self, password_hash, password):
        self.checks += 1
        return self._hasher.matches(password_hash, password)


class BrokenStore:
    """A store whose database cannot be reached."""

    def add(self, name, password_hash):
        raise StoreUnavailable("down")

    def find(self, name):
        raise StoreUnavailable("down")


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    test_clock = Clock()
    monkeypatch.setattr(main, "seconds_now", test_clock)
    return test_clock


@pytest.fixture
def hasher():
    real_hasher = app.state.hasher
    counting = CountingHasher(real_hasher)
    app.state.hasher = counting
    yield counting
    # conftest.py does not renew the hasher, so it is put back here.
    app.state.hasher = real_hasher


@pytest.fixture
def client():
    # One event loop for all connections, like the real server.
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


def sign_up(connection, name="Mara", password=PASSWORD):
    return ask(connection, {"type": "sign_up", "name": name, "password": password})


def log_in(connection, name="Mara", password=PASSWORD):
    return ask(connection, {"type": "log_in", "name": name, "password": password})


def join(connection, code):
    return ask(connection, {"type": "join_lobby", "code": code})


def guest(connect):
    connection = connect()
    assert ask(connection, {"type": "guest"})["type"] == "signed_in"
    return connection


def account_of_mara(connect):
    """Mara signs up on a connection of her own and logs out again."""
    connection = connect()
    assert sign_up(connection)["type"] == "signed_in"
    assert ask(connection, {"type": "log_out"})["type"] == "signed_out"


def fail_log_ins(connection, how_many=LOG_IN_FAILURES_ALLOWED):
    for attempt in range(how_many):
        assert log_in(connection, password=WRONG_PASSWORD) == WRONG_CREDENTIALS


def fail_joins(connection, how_many=JOIN_LOBBY_FAILURES_ALLOWED):
    for attempt in range(how_many):
        assert join(connection, "ZZZZ") == NO_LOBBY


def lobby_of_a_guest(connect):
    """A guest creates a lobby. Returns the host's connection and the code."""
    host = guest(connect)
    return host, ask(host, {"type": "create_lobby"})["code"]


# Logging in


def test_under_the_limit_the_right_password_still_works(connect):
    account_of_mara(connect)
    mara = connect()
    fail_log_ins(mara, LOG_IN_FAILURES_ALLOWED - 1)
    assert log_in(mara) == {"type": "signed_in", "name": "Mara", "guest": False}


def test_the_sixth_log_in_is_refused_even_with_the_right_password(connect, hasher):
    account_of_mara(connect)
    mara = connect()
    fail_log_ins(mara)
    checks_before = hasher.checks
    assert checks_before == LOG_IN_FAILURES_ALLOWED

    assert log_in(mara) == TOO_MANY
    assert log_in(mara, password=WRONG_PASSWORD) == TOO_MANY
    assert log_in(mara, name="Nobody") == TOO_MANY
    # The point of the limit: no password was hashed for the refused attempts.
    assert hasher.checks == checks_before
    assert app.state.sessions.connection_of("Mara") is None


def test_a_refused_log_in_does_not_ask_the_store(connect, monkeypatch):
    account_of_mara(connect)
    mara = connect()
    fail_log_ins(mara)
    asked = []
    real_find = app.state.account_store.find
    monkeypatch.setattr(app.state.account_store, "find", lambda name: asked.append(name) or real_find(name))
    assert log_in(mara) == TOO_MANY
    assert asked == []


def test_wrong_names_count_like_wrong_passwords(connect):
    mara = connect()
    for attempt in range(LOG_IN_FAILURES_ALLOWED):
        assert log_in(mara, name=f"Nobody{attempt}") == WRONG_CREDENTIALS
    assert log_in(mara, name="Nobody9") == TOO_MANY


def test_after_the_window_the_right_password_works_again(connect, clock):
    account_of_mara(connect)
    mara = connect()
    fail_log_ins(mara)
    clock.wait(LOG_IN_WINDOW_SECONDS)
    assert log_in(mara) == TOO_MANY  # exactly one window later: still refused
    clock.wait(0.001)
    assert log_in(mara) == {"type": "signed_in", "name": "Mara", "guest": False}


def test_trying_while_refused_does_not_make_the_wait_longer(connect, clock):
    account_of_mara(connect)
    mara = connect()
    fail_log_ins(mara)
    for second in range(LOG_IN_WINDOW_SECONDS):
        clock.wait(1)
        assert log_in(mara, password=WRONG_PASSWORD) == TOO_MANY
    clock.wait(0.001)
    assert log_in(mara) == {"type": "signed_in", "name": "Mara", "guest": False}


def test_the_window_slides_over_the_log_ins(connect, clock):
    account_of_mara(connect)
    mara = connect()
    for attempt in range(LOG_IN_FAILURES_ALLOWED):
        assert log_in(mara, password=WRONG_PASSWORD) == WRONG_CREDENTIALS
        clock.wait(10)  # failures at 0, 10, 20, 30, 40 seconds; now it is second 50
    assert log_in(mara) == TOO_MANY
    clock.wait(10.5)  # second 60.5: the first failure is too old, the others are not
    assert log_in(mara, password=WRONG_PASSWORD) == WRONG_CREDENTIALS
    assert log_in(mara) == TOO_MANY  # and that new failure filled the window again


def test_a_successful_log_in_does_not_clear_the_count(connect):
    account_of_mara(connect)
    mara = connect()
    fail_log_ins(mara, LOG_IN_FAILURES_ALLOWED - 1)
    assert log_in(mara)["type"] == "signed_in"
    assert ask(mara, {"type": "log_out"})["type"] == "signed_out"
    fail_log_ins(mara, 1)
    assert log_in(mara) == TOO_MANY


def test_a_second_connection_is_not_affected(connect):
    account_of_mara(connect)
    blocked = connect()
    fail_log_ins(blocked)
    assert log_in(blocked) == TOO_MANY
    other = connect()
    assert log_in(other) == {"type": "signed_in", "name": "Mara", "guest": False}


def test_sign_up_still_works_while_log_in_is_refused(connect):
    mara = connect()
    for attempt in range(LOG_IN_FAILURES_ALLOWED):
        assert log_in(mara, password=WRONG_PASSWORD) == WRONG_CREDENTIALS
    assert log_in(mara) == TOO_MANY
    assert sign_up(mara) == {"type": "signed_in", "name": "Mara", "guest": False}


def test_guest_and_everything_else_still_work_while_log_in_is_refused(connect):
    mara = connect()
    for attempt in range(LOG_IN_FAILURES_ALLOWED):
        assert log_in(mara, password=WRONG_PASSWORD) == WRONG_CREDENTIALS
    assert log_in(mara) == TOO_MANY
    assert ask(mara, {"type": "hello", "name": "Mara"})["type"] == "welcome"
    assert ask(mara, {"type": "guest"})["type"] == "signed_in"
    assert ask(mara, {"type": "create_lobby"})["type"] == "lobby_state"


def test_sign_up_is_not_limited(connect):
    account_of_mara(connect)
    tiago = connect()
    for attempt in range(LOG_IN_FAILURES_ALLOWED + 2):
        assert sign_up(tiago, name="Mara")["code"] == "name_taken"
    assert sign_up(tiago, name="Tiago")["type"] == "signed_in"


def test_a_database_that_is_down_does_not_count(connect):
    account_of_mara(connect)
    store = app.state.account_store
    mara = connect()
    app.state.account_store = BrokenStore()  # conftest.py puts a fresh store in for the next test
    for attempt in range(LOG_IN_FAILURES_ALLOWED + 2):
        assert log_in(mara)["code"] == "accounts_unavailable"
    app.state.account_store = store
    assert log_in(mara)["type"] == "signed_in"


def test_a_malformed_log_in_does_not_count(connect):
    account_of_mara(connect)
    mara = connect()
    for attempt in range(LOG_IN_FAILURES_ALLOWED + 2):
        # No name at all: refused by the protocol, nothing was guessed.
        assert log_in(mara, name="") == WRONG_CREDENTIALS
        assert ask(mara, {"type": "log_in"})["type"] == "error"
    assert log_in(mara)["type"] == "signed_in"


def test_logging_in_while_signed_in_says_log_out_first_and_does_not_count(connect):
    account_of_mara(connect)
    mara = connect()
    assert log_in(mara)["type"] == "signed_in"
    for attempt in range(LOG_IN_FAILURES_ALLOWED + 2):
        assert log_in(mara, password=WRONG_PASSWORD)["code"] == "already_signed_in"
    assert ask(mara, {"type": "log_out"})["type"] == "signed_out"
    assert log_in(mara)["type"] == "signed_in"


def test_wrong_log_ins_do_not_block_joining(connect):
    host, code = lobby_of_a_guest(connect)
    mara = connect()
    for attempt in range(LOG_IN_FAILURES_ALLOWED):
        assert log_in(mara, password=WRONG_PASSWORD) == WRONG_CREDENTIALS
    assert ask(mara, {"type": "guest"})["type"] == "signed_in"
    assert join(mara, code)["type"] == "lobby_state"


# Joining a lobby


def test_under_the_limit_the_right_code_still_works(connect):
    host, code = lobby_of_a_guest(connect)
    joiner = guest(connect)
    fail_joins(joiner, JOIN_LOBBY_FAILURES_ALLOWED - 1)
    assert join(joiner, code)["type"] == "lobby_state"


def test_the_eleventh_join_is_refused_even_with_an_existing_code(connect):
    host, code = lobby_of_a_guest(connect)
    joiner = guest(connect)
    fail_joins(joiner)
    assert join(joiner, code) == TOO_MANY
    assert join(joiner, "ZZZZ") == TOO_MANY
    # Nothing else happened: the joiner is in no lobby and the host heard nothing.
    assert len(app.state.lobbies.find(code).names()) == 1
    assert ask(host, {"type": "hello", "name": "Mara"})["type"] == "welcome"


def test_after_the_window_the_right_code_works_again(connect, clock):
    host, code = lobby_of_a_guest(connect)
    joiner = guest(connect)
    fail_joins(joiner)
    clock.wait(JOIN_LOBBY_WINDOW_SECONDS)
    assert join(joiner, code) == TOO_MANY  # exactly one window later: still refused
    clock.wait(0.001)
    assert join(joiner, code)["type"] == "lobby_state"


def test_a_successful_join_does_not_clear_the_count(connect):
    host, code = lobby_of_a_guest(connect)
    joiner = guest(connect)
    fail_joins(joiner, JOIN_LOBBY_FAILURES_ALLOWED - 1)
    assert join(joiner, code)["type"] == "lobby_state"
    assert ask(joiner, {"type": "leave_lobby"})["type"] == "left_lobby"
    fail_joins(joiner, 1)
    assert join(joiner, code) == TOO_MANY


def test_joining_a_full_lobby_does_not_count(connect):
    host, code = lobby_of_a_guest(connect)
    members = [host]
    for number in range(7):
        member = guest(connect)
        assert join(member, code)["type"] == "lobby_state"
        for earlier in members:
            earlier.receive_json()
        members.append(member)

    ninth = guest(connect)
    for attempt in range(JOIN_LOBBY_FAILURES_ALLOWED + 2):
        assert join(ninth, code)["code"] == "lobby_full"
    assert join(ninth, "ZZZZ") == NO_LOBBY  # still asked, not refused


def test_joining_a_running_round_does_not_count(connect):
    host, code = lobby_of_a_guest(connect)
    app.state.lobbies.find(code).start_round()
    joiner = guest(connect)
    for attempt in range(JOIN_LOBBY_FAILURES_ALLOWED + 2):
        assert join(joiner, code)["code"] == "round_running"
    assert join(joiner, "ZZZZ") == NO_LOBBY


def test_a_malformed_code_does_not_count(connect):
    host, code = lobby_of_a_guest(connect)
    joiner = guest(connect)
    for attempt in range(JOIN_LOBBY_FAILURES_ALLOWED + 2):
        assert join(joiner, "12")["type"] == "error"
    assert join(joiner, code)["type"] == "lobby_state"


def test_joining_while_signed_out_does_not_count(connect):
    host, code = lobby_of_a_guest(connect)
    joiner = connect()
    for attempt in range(JOIN_LOBBY_FAILURES_ALLOWED + 2):
        assert join(joiner, "ZZZZ")["code"] == "not_signed_in"
    assert ask(joiner, {"type": "guest"})["type"] == "signed_in"
    assert join(joiner, code)["type"] == "lobby_state"


def test_a_second_connection_can_still_join(connect):
    host, code = lobby_of_a_guest(connect)
    blocked = guest(connect)
    fail_joins(blocked)
    assert join(blocked, code) == TOO_MANY
    other = guest(connect)
    assert join(other, code)["type"] == "lobby_state"


def test_everything_else_still_works_while_joining_is_refused(connect):
    joiner = guest(connect)
    fail_joins(joiner)
    assert join(joiner, "ZZZZ") == TOO_MANY
    assert ask(joiner, {"type": "hello", "name": "Mara"})["type"] == "welcome"
    assert ask(joiner, {"type": "create_lobby"})["type"] == "lobby_state"
    assert ask(joiner, {"type": "leave_lobby"})["type"] == "left_lobby"
    assert ask(joiner, {"type": "log_out"})["type"] == "signed_out"


def test_wrong_codes_do_not_block_logging_in(connect):
    account_of_mara(connect)
    joiner = guest(connect)
    fail_joins(joiner)
    assert ask(joiner, {"type": "log_out"})["type"] == "signed_out"
    assert log_in(joiner)["type"] == "signed_in"
    # The count belongs to the connection, not to the name: still refused.
    assert join(joiner, "ZZZZ") == TOO_MANY


# Forgetting


def test_a_closed_connection_leaves_nothing_behind(client):
    limits = app.state.attempt_limits
    with client.websocket_connect("/ws") as connection:
        fail_log_ins(connection, 2)
        assert ask(connection, {"type": "guest"})["type"] == "signed_in"
        fail_joins(connection, 2)
        assert limits.count() == 1
    wait_until(lambda: limits.count() == 0)


def test_a_blocked_connection_that_closes_is_forgotten_too(client):
    limits = app.state.attempt_limits
    with client.websocket_connect("/ws") as connection:
        fail_log_ins(connection)
        assert log_in(connection) == TOO_MANY
        assert limits.count() == 1
    wait_until(lambda: limits.count() == 0)
    with client.websocket_connect("/ws") as connection:
        # A new connection starts from nothing.
        assert log_in(connection, password=WRONG_PASSWORD) == WRONG_CREDENTIALS
