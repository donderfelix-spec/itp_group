"""The deadline that cuts off a stuck database call from outside (S-211).

No real database: a pair of connected sockets stands in for the connection
to it, and for the stores a tiny local server answers psycopg's greeting and
then never answers a query, like a database that is alive but stuck.
"""

import socket
import struct
import threading
import time

import pytest

from server.accounts import store
from server.accounts.statistics_store import PostgresStatisticsStore
from server.accounts.store import CallDeadline, PostgresAccountStore, StoreUnavailable


class FakePgConn:
    def __init__(self, sock):
        self.socket = sock.fileno()


class FakeConnection:
    """Has what `CallDeadline` looks at: `connection.pgconn.socket`."""

    def __init__(self, sock):
        self.pgconn = FakePgConn(sock)


@pytest.fixture
def socket_pair():
    ours, theirs = socket.socketpair()
    yield ours, theirs
    ours.close()
    theirs.close()


def test_the_deadline_cuts_off_the_connection_after_its_seconds(socket_pair):
    ours, theirs = socket_pair
    started = time.monotonic()
    deadline = CallDeadline(FakeConnection(ours), seconds=0.2)
    ours.settimeout(5)
    # The waiting side sees the connection closed, as libpq does.
    assert ours.recv(10) == b""
    waited = time.monotonic() - started
    deadline.stop()
    assert 0.15 <= waited < 3


def test_the_other_end_sees_the_connection_closed_too(socket_pair):
    ours, theirs = socket_pair
    deadline = CallDeadline(FakeConnection(ours), seconds=0.1)
    theirs.settimeout(5)
    assert theirs.recv(10) == b""
    deadline.stop()


def test_a_call_that_is_over_in_time_is_never_cut_off(socket_pair):
    ours, theirs = socket_pair
    deadline = CallDeadline(FakeConnection(ours), seconds=0.2)
    deadline.stop()
    time.sleep(0.4)
    # Still open in both directions.
    ours.sendall(b"ping")
    theirs.settimeout(5)
    assert theirs.recv(10) == b"ping"
    theirs.sendall(b"pong")
    ours.settimeout(5)
    assert ours.recv(10) == b"pong"


def test_stopping_leaves_the_connections_own_socket_open(socket_pair):
    ours, theirs = socket_pair
    deadline = CallDeadline(FakeConnection(ours), seconds=5)
    deadline.stop()
    # Only the duplicate was closed: libpq's socket number still works.
    assert ours.fileno() != -1
    ours.sendall(b"x")
    theirs.settimeout(5)
    assert theirs.recv(1) == b"x"


def test_stopping_after_the_cut_and_stopping_twice_are_harmless(socket_pair):
    ours, theirs = socket_pair
    deadline = CallDeadline(FakeConnection(ours), seconds=0.05)
    ours.settimeout(5)
    assert ours.recv(10) == b""
    deadline.stop()
    deadline.stop()


def test_without_a_socket_the_call_runs_without_a_deadline():
    # Fail-safe: whatever stops the duplicate from being made must not stop the call.
    class NoSocket:
        @property
        def pgconn(self):
            raise OSError("no socket here")

    deadline = CallDeadline(NoSocket(), seconds=0.01)
    time.sleep(0.05)
    deadline.stop()


def test_the_deadline_is_ten_seconds_by_default(socket_pair):
    ours, theirs = socket_pair
    assert store.CALL_DEADLINE_SECONDS == 10
    deadline = CallDeadline(FakeConnection(ours))
    assert deadline._timer.interval == 10
    deadline.stop()


def test_the_log_line_of_a_cut_names_no_connection_details(socket_pair, caplog):
    ours, theirs = socket_pair
    deadline = CallDeadline(FakeConnection(ours), seconds=0.05)
    ours.settimeout(5)
    assert ours.recv(10) == b""
    deadline.stop()
    assert "A database call took longer than 0.05 seconds and was cut off" in caplog.text


# The stores against a server that is alive but stuck. It answers the start
# of the connection like Postgres (no password asked), then reads every
# query and never answers one.


def message(kind: bytes, body: bytes) -> bytes:
    return kind + struct.pack("!i", len(body) + 4) + body


def parameter(name: str, value: str) -> bytes:
    return message(b"S", name.encode() + b"\0" + value.encode() + b"\0")


GREETING = (
    message(b"R", struct.pack("!i", 0))  # no password needed
    + parameter("server_version", "16.0")
    + parameter("client_encoding", "UTF8")
    + parameter("standard_conforming_strings", "on")
    + message(b"K", struct.pack("!ii", 4242, 1234))
    + message(b"Z", b"I")  # ready for a query
)
SSL_REQUEST = struct.pack("!ii", 8, 80877103)


class StuckServer:
    def __init__(self):
        self._listener = socket.socket()
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(5)
        self.port = self._listener.getsockname()[1]
        self.connections = []
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                connection, _ = self._listener.accept()
            except OSError:
                return
            self.connections.append(connection)
            threading.Thread(target=self._greet_then_hang, args=(connection,), daemon=True).start()

    def _greet_then_hang(self, connection):
        try:
            first = connection.recv(8)
            if first == SSL_REQUEST:
                connection.sendall(b"N")  # no encryption: plain startup follows
                first = connection.recv(8)
            length = struct.unpack("!i", first[:4])[0]
            connection.recv(length - len(first))
            connection.sendall(GREETING)
            while connection.recv(4096):
                pass  # the query is read and never answered
        except OSError:
            pass

    def close(self):
        self._listener.close()
        for connection in self.connections:
            connection.close()


@pytest.fixture
def stuck_server(monkeypatch):
    monkeypatch.setattr(store, "CALL_DEADLINE_SECONDS", 0.5)
    server = StuckServer()
    yield f"postgresql://player:not-a-secret@127.0.0.1:{server.port}/game?sslmode=disable"
    server.close()


CUT_OFF = "A database call took longer than 0.5 seconds and was cut off"


def test_a_stuck_database_frees_the_account_worker_within_the_deadline(stuck_server, caplog):
    accounts = PostgresAccountStore(stuck_server)
    started = time.monotonic()
    with pytest.raises(StoreUnavailable):
        accounts.find("Mara")
    assert time.monotonic() - started < 3
    # It was the deadline, not some other failure of the fake server.
    assert CUT_OFF in caplog.text


def test_a_stuck_database_frees_the_statistics_worker_within_the_deadline(stuck_server, caplog):
    statistics = PostgresStatisticsStore(stuck_server)
    started = time.monotonic()
    with pytest.raises(StoreUnavailable):
        statistics.record_round("duel", [{"name": "Mara", "rounds": 1, "wins": 1, "best_seconds": 70.0}])
    assert time.monotonic() - started < 3
    assert CUT_OFF in caplog.text


def test_after_a_cut_off_the_next_call_tries_again(stuck_server, caplog):
    # The table was never created, so the next call must not take it for done.
    accounts = PostgresAccountStore(stuck_server)
    for _ in range(2):
        with pytest.raises(StoreUnavailable):
            accounts.add("Mara", "hash")
    assert accounts._table_exists is False
    assert caplog.text.count(CUT_OFF) == 2


def test_when_no_timer_thread_can_start_the_call_runs_without_a_deadline(socket_pair, monkeypatch):
    ours, theirs = socket_pair

    def no_thread(self):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(threading.Timer, "start", no_thread)
    deadline = CallDeadline(FakeConnection(ours), seconds=0.01)
    deadline.stop()
    # Nothing was cut off, and libpq's socket is still open.
    ours.sendall(b"x")
    theirs.settimeout(5)
    assert theirs.recv(1) == b"x"
