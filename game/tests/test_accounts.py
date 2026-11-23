"""The account rules and the stores, called directly without a network."""

import psycopg
import pytest

from server.accounts import service
from server.accounts.store import (
    MemoryAccountStore,
    PostgresAccountStore,
    StoreUnavailable,
    make_account_store,
)


class FakeHasher:
    """Fast stand-in for Argon2, so the rule tests do not spend time hashing."""

    dummy_hash = "fake:dummy"

    def __init__(self):
        self.checked_hashes = []

    def hash(self, password):
        return "fake:" + password

    def matches(self, password_hash, password):
        self.checked_hashes.append(password_hash)
        return password_hash == "fake:" + password


class BrokenStore:
    """A store whose database cannot be reached."""

    def add(self, name, password_hash):
        raise StoreUnavailable("down")

    def find(self, name):
        raise StoreUnavailable("down")


@pytest.fixture
def store():
    return MemoryAccountStore()


@pytest.fixture
def hasher():
    return FakeHasher()


# The store in memory


def test_an_added_account_can_be_found(store):
    assert store.add("Mara", "hash-1") is True
    assert store.find("Mara") == ("Mara", "hash-1")


def test_an_unknown_name_is_not_found(store):
    assert store.find("Mara") is None


def test_a_name_can_only_be_added_once(store):
    store.add("Mara", "hash-1")
    assert store.add("Mara", "hash-2") is False
    assert store.find("Mara") == ("Mara", "hash-1")


def test_names_are_the_same_account_in_any_case(store):
    store.add("Mara", "hash-1")
    assert store.add("mara", "hash-2") is False
    assert store.add("MARA", "hash-3") is False


def test_find_in_another_case_returns_the_first_spelling(store):
    store.add("Mara", "hash-1")
    assert store.find("mARA") == ("Mara", "hash-1")


# Choosing the store


def test_without_a_database_url_accounts_live_in_memory():
    assert isinstance(make_account_store(None), MemoryAccountStore)
    assert isinstance(make_account_store(""), MemoryAccountStore)


def test_with_a_database_url_accounts_live_in_postgres():
    assert isinstance(make_account_store("postgresql://example.invalid/db"), PostgresAccountStore)


# The Postgres store, without a database: `psycopg.connect` is replaced.


def refuse_to_connect(*args, **kwargs):
    raise psycopg.OperationalError("connection refused")


def test_creating_the_postgres_store_does_not_connect(monkeypatch):
    monkeypatch.setattr(psycopg, "connect", refuse_to_connect)
    PostgresAccountStore("postgresql://example.invalid/db")


def test_a_database_that_cannot_be_reached_is_store_unavailable(monkeypatch):
    monkeypatch.setattr(psycopg, "connect", refuse_to_connect)
    store = PostgresAccountStore("postgresql://example.invalid/db")
    with pytest.raises(StoreUnavailable):
        store.add("Mara", "hash-1")
    with pytest.raises(StoreUnavailable):
        store.find("Mara")


def test_store_unavailable_does_not_repeat_the_database_url(monkeypatch):
    monkeypatch.setattr(psycopg, "connect", refuse_to_connect)
    store = PostgresAccountStore("postgresql://user:topsecret@example.invalid/db")
    with pytest.raises(StoreUnavailable) as caught:
        store.find("Mara")
    assert "topsecret" not in str(caught.value)
    assert caught.value.__cause__ is None


# Signing up


def test_sign_up_succeeds_and_stores_the_hash(store, hasher):
    assert service.sign_up(store, hasher, "Mara", "password123") == ("Mara", None)
    assert store.find("Mara") == ("Mara", "fake:password123")


def test_sign_up_with_a_taken_name_is_rejected(store, hasher):
    service.sign_up(store, hasher, "Mara", "password123")
    assert service.sign_up(store, hasher, "Mara", "otherpassword") == (None, "name_taken")


def test_sign_up_with_a_taken_name_in_another_case_is_rejected(store, hasher):
    service.sign_up(store, hasher, "Mara", "password123")
    assert service.sign_up(store, hasher, "mARA", "otherpassword") == (None, "name_taken")


def test_a_rejected_sign_up_does_not_change_the_account(store, hasher):
    service.sign_up(store, hasher, "Mara", "password123")
    service.sign_up(store, hasher, "mara", "otherpassword")
    assert store.find("Mara") == ("Mara", "fake:password123")


@pytest.mark.parametrize("name", ["Guest1234", "guest7", "GUEST0000", "Guest123456789"])
def test_guest_names_cannot_be_signed_up(store, hasher, name):
    assert service.sign_up(store, hasher, name, "password123") == (None, "name_taken")
    assert store.find(name) is None


@pytest.mark.parametrize("name", ["Guest", "Guesty", "Guest12a", "MyGuest12", "Guests1"])
def test_names_that_only_look_a_bit_like_guests_can_be_signed_up(store, hasher, name):
    assert service.sign_up(store, hasher, name, "password123") == (name, None)


def test_sign_up_without_the_database_is_accounts_unavailable(hasher):
    assert service.sign_up(BrokenStore(), hasher, "Mara", "password123") == (None, "accounts_unavailable")


# Logging in


def test_log_in_with_the_right_password_succeeds(store, hasher):
    service.sign_up(store, hasher, "Mara", "password123")
    assert service.log_in(store, hasher, "Mara", "password123") == ("Mara", None)


def test_log_in_in_another_case_returns_the_stored_spelling(store, hasher):
    service.sign_up(store, hasher, "Mara", "password123")
    assert service.log_in(store, hasher, "mara", "password123") == ("Mara", None)


def test_log_in_with_a_wrong_password_is_rejected(store, hasher):
    service.sign_up(store, hasher, "Mara", "password123")
    assert service.log_in(store, hasher, "Mara", "password124") == (None, "wrong_credentials")


def test_the_password_is_checked_exactly(store, hasher):
    service.sign_up(store, hasher, "Mara", "password123")
    assert service.log_in(store, hasher, "Mara", "Password123") == (None, "wrong_credentials")
    assert service.log_in(store, hasher, "Mara", "password123 ") == (None, "wrong_credentials")


def test_log_in_with_an_unknown_name_is_rejected_like_a_wrong_password(store, hasher):
    assert service.log_in(store, hasher, "Nobody", "password123") == (None, "wrong_credentials")


def test_an_unknown_name_is_still_checked_against_the_dummy_hash(store, hasher):
    service.log_in(store, hasher, "Nobody", "password123")
    assert hasher.checked_hashes == ["fake:dummy"]


def test_nobody_can_log_in_with_the_password_of_the_dummy_hash(store, hasher):
    # "dummy" is the password that matches FakeHasher.dummy_hash.
    assert service.log_in(store, hasher, "Nobody", "dummy") == (None, "wrong_credentials")


def test_log_in_without_the_database_is_accounts_unavailable(hasher):
    assert service.log_in(BrokenStore(), hasher, "Mara", "password123") == (None, "accounts_unavailable")


# The real Argon2 hasher


def test_argon2_hashes_and_verifies():
    real = service.Argon2Hasher()
    password_hash = real.hash("password123")
    assert password_hash.startswith("$argon2")
    assert "password123" not in password_hash
    assert real.matches(password_hash, "password123") is True
    assert real.matches(password_hash, "password124") is False


def test_argon2_gives_the_same_password_a_different_hash_each_time():
    real = service.Argon2Hasher()
    assert real.hash("password123") != real.hash("password123")


def test_a_stored_hash_that_cannot_be_read_never_matches():
    assert service.Argon2Hasher().matches("not a hash", "password123") is False


def test_sign_up_and_log_in_with_real_argon2(store):
    real = service.Argon2Hasher()
    assert service.sign_up(store, real, "Mara", "password123") == ("Mara", None)
    stored_name, password_hash = store.find("Mara")
    assert password_hash.startswith("$argon2")
    assert "password123" not in password_hash
    assert service.log_in(store, real, "mara", "password123") == ("Mara", None)
    assert service.log_in(store, real, "Mara", "wrong-password") == (None, "wrong_credentials")
    assert service.log_in(store, real, "Nobody", "password123") == (None, "wrong_credentials")


# The Postgres store with a fake connection (review findings on M1-2.0).
# `psycopg.connect` is replaced, so the SQL is recorded instead of run.


class FakeCursor:
    def __init__(self, rowcount=0, row=None):
        self.rowcount = rowcount
        self._row = row

    def fetchone(self):
        return self._row


class FakeDatabase:
    """Hands out fake connections and writes down everything that happens.

    `events` holds, in order: ("execute", query, params), ("commit",), ("close",).
    """

    def __init__(self):
        self.events = []
        self.connections_opened = 0
        self.connect_arguments = None
        self.rowcount = 1  # answer to INSERT
        self.row = None  # answer to SELECT
        self.fail_on = None  # "create" or "commit": that step raises psycopg.Error
        self.before_commit = lambda: None

    def connect(self, *args, **kwargs):
        self.connections_opened += 1
        self.connect_arguments = (args, kwargs)
        return FakeConnection(self)

    def queries(self, start):
        """The executed queries that begin with `start`, as (query, params) pairs."""
        executed = [event[1:] for event in self.events if event[0] == "execute"]
        return [(query, params) for query, params in executed if query.strip().startswith(start)]


class FakeConnection:
    def __init__(self, database):
        self._database = database

    def execute(self, query, params=None):
        self._database.events.append(("execute", query, params))
        if query.strip().startswith("CREATE") and self._database.fail_on == "create":
            raise psycopg.OperationalError("create failed")
        return FakeCursor(self._database.rowcount, self._database.row)

    def commit(self):
        self._database.before_commit()
        if self._database.fail_on == "commit":
            raise psycopg.OperationalError("commit failed")
        self._database.events.append(("commit",))

    def close(self):
        self._database.events.append(("close",))

    def __enter__(self):
        return self

    def __exit__(self, error_type, error, traceback):
        # Like psycopg: save the changes if all went well, then close.
        if error_type is None:
            self.commit()
        self.close()
        return False


@pytest.fixture
def database(monkeypatch):
    fake = FakeDatabase()
    monkeypatch.setattr(psycopg, "connect", fake.connect)
    return fake


@pytest.fixture
def postgres(database):
    return PostgresAccountStore("postgresql://example.invalid/db")


def test_postgres_connects_with_a_short_timeout(database, postgres):
    postgres.find("Mara")
    args, kwargs = database.connect_arguments
    assert args == ("postgresql://example.invalid/db",)
    assert kwargs["connect_timeout"] == 5


def test_postgres_creates_the_table_on_the_first_call_only(database, postgres):
    postgres.find("Mara")
    postgres.add("Mara", "hash-1")
    postgres.find("Mara")
    assert len(database.queries("CREATE TABLE IF NOT EXISTS accounts")) == 1
    assert database.connections_opened == 3


def test_postgres_commits_the_table_before_anything_else_and_before_remembering_it(database, postgres):
    flag_at_commit = []
    database.before_commit = lambda: flag_at_commit.append(postgres._table_exists)
    postgres.find("Mara")
    kinds = [event[1].split()[0] if event[0] == "execute" else event[0] for event in database.events]
    assert kinds == ["SET", "CREATE", "ALTER", "commit", "SET", "SELECT", "commit", "close"]
    # At the first commit (the table) the store did not yet believe the table exists.
    assert flag_at_commit[0] is False
    assert postgres._table_exists is True


@pytest.mark.parametrize("failing_step", ["create", "commit"])
def test_postgres_tries_to_create_the_table_again_after_a_failure(database, postgres, failing_step):
    database.fail_on = failing_step
    with pytest.raises(StoreUnavailable):
        postgres.find("Mara")
    assert postgres._table_exists is False
    assert database.events[-1] == ("close",)

    database.fail_on = None
    assert postgres.find("Mara") is None
    assert postgres._table_exists is True
    assert len(database.queries("CREATE TABLE")) == 2


def test_postgres_limits_the_time_of_every_statement(database, postgres):
    postgres.add("Mara", "hash-1")
    postgres.find("Mara")
    kinds = [event[1].split()[0] if event[0] == "execute" else event[0] for event in database.events]
    # Each transaction starts with the time limit.
    assert kinds == ["SET", "CREATE", "ALTER", "commit", "SET", "INSERT", "commit", "close", "SET", "SELECT", "commit", "close"]
    for query, params in database.queries("SET"):
        assert query == "SET LOCAL statement_timeout = 5000"


def test_postgres_add_returns_true_when_a_row_was_inserted(database, postgres):
    database.rowcount = 1
    assert postgres.add("Mara", "hash-1") is True


def test_postgres_add_returns_false_when_the_name_existed(database, postgres):
    database.rowcount = 0
    assert postgres.add("Mara", "hash-1") is False


def test_postgres_add_passes_the_values_as_parameters_with_a_lower_case_key(database, postgres):
    postgres.add("MaRa", "hash-1")
    [(query, params)] = database.queries("INSERT")
    assert params == ("mara", "MaRa", "hash-1")
    # The values travel next to the query, never inside it.
    assert "MaRa" not in query and "mara" not in query and "hash-1" not in query
    assert query.count("%s") == 3
    assert "ON CONFLICT (name_key) DO NOTHING" in query


def test_postgres_add_saves_and_closes(database, postgres):
    postgres.add("Mara", "hash-1")
    assert database.events[-2:] == [("commit",), ("close",)]


def test_postgres_find_returns_the_stored_name_and_hash(database, postgres):
    database.row = ("Mara", "hash-1")
    assert postgres.find("mara") == ("Mara", "hash-1")


def test_postgres_find_returns_none_for_an_unknown_name(database, postgres):
    database.row = None
    assert postgres.find("Nobody") is None


def test_postgres_find_looks_up_the_lower_case_key_as_a_parameter(database, postgres):
    postgres.find("MaRa")
    [(query, params)] = database.queries("SELECT")
    assert params == ("mara",)
    assert "MaRa" not in query and "mara" not in query
    assert query.count("%s") == 1


def test_postgres_closes_the_connection_when_a_query_fails(database, postgres):
    postgres.find("Mara")  # creates the table

    def failing_execute(self, query, params=None):
        if query.startswith("SELECT"):
            raise psycopg.OperationalError("query failed")
        return FakeCursor()

    FakeConnection.execute, original = failing_execute, FakeConnection.execute
    try:
        with pytest.raises(StoreUnavailable):
            postgres.find("Mara")
    finally:
        FakeConnection.execute = original
    assert database.events[-1] == ("close",)


# A database that dies or hangs in the middle of a call (S-211).

EXPECTED_SOCKET_OPTIONS = {
    "keepalives": 1,
    "keepalives_idle": 2,
    "keepalives_interval": 1,
    "keepalives_count": 3,
    "tcp_user_timeout": 5000,
}


def test_postgres_connects_with_socket_options_that_notice_a_dead_network(database, postgres):
    postgres.find("Mara")
    args, kwargs = database.connect_arguments
    assert args == ("postgresql://example.invalid/db",)
    assert kwargs == {"connect_timeout": 5, "prepare_threshold": None, **EXPECTED_SOCKET_OPTIONS}


class ProbeSocket:
    """A socket that refuses the socket options named in `refused`."""

    def __init__(self, refused=()):
        self.refused = set(refused)
        self.tried = []
        self.closed = False

    def __call__(self, family, kind):
        return self

    def setsockopt(self, level, option, value):
        self.tried.append((option, value))
        if option in self.refused:
            raise OSError(92, "Protocol not available")

    def close(self):
        self.closed = True


def test_every_socket_option_this_system_accepts_is_used():
    from server.accounts.store import WANTED_SOCKET_OPTIONS, usable_socket_options

    probe = ProbeSocket()
    assert usable_socket_options(WANTED_SOCKET_OPTIONS, probe) == EXPECTED_SOCKET_OPTIONS
    assert probe.closed


def test_on_this_linux_server_all_socket_options_are_used():
    import sys

    from server.accounts.store import SOCKET_OPTIONS

    if not sys.platform.startswith("linux"):
        pytest.skip("Render runs Linux; elsewhere libpq skips what the system lacks")
    assert SOCKET_OPTIONS == EXPECTED_SOCKET_OPTIONS


def test_a_socket_option_the_system_refuses_is_left_out(caplog):
    import socket

    from server.accounts.store import WANTED_SOCKET_OPTIONS, usable_socket_options

    if not hasattr(socket, "TCP_USER_TIMEOUT"):
        pytest.skip("this system has no TCP_USER_TIMEOUT")
    probe = ProbeSocket(refused={socket.TCP_USER_TIMEOUT})
    usable = usable_socket_options(WANTED_SOCKET_OPTIONS, probe)
    assert "tcp_user_timeout" not in usable
    assert usable["keepalives_idle"] == 2
    assert "The socket option tcp_user_timeout is not available here and is left out" in caplog.text
    assert probe.closed


def test_when_no_probe_socket_can_be_made_the_options_stay_to_libpq():
    from server.accounts.store import WANTED_SOCKET_OPTIONS, usable_socket_options

    def no_socket(family, kind):
        raise OSError("no sockets")

    assert usable_socket_options(WANTED_SOCKET_OPTIONS, no_socket) == WANTED_SOCKET_OPTIONS


def test_the_wanted_options_are_never_changed_by_the_probe():
    import socket

    from server.accounts.store import WANTED_SOCKET_OPTIONS, usable_socket_options

    before = dict(WANTED_SOCKET_OPTIONS)
    usable_socket_options(WANTED_SOCKET_OPTIONS, ProbeSocket(refused={getattr(socket, "TCP_KEEPCNT", -1)}))
    assert WANTED_SOCKET_OPTIONS == before


class RecordedDeadline:
    """Stands in for `CallDeadline` and writes down when it starts and stops."""

    events = []

    def __init__(self, connection, seconds=None):
        RecordedDeadline.events.append("start")

    def stop(self):
        RecordedDeadline.events.append("stop")


@pytest.fixture
def deadlines(monkeypatch):
    from server.accounts import store

    RecordedDeadline.events = []
    monkeypatch.setattr(store, "CallDeadline", RecordedDeadline)
    return RecordedDeadline.events


def test_postgres_stops_the_deadline_of_every_call(database, postgres, deadlines):
    postgres.find("Mara")
    postgres.add("Mara", "hash-1")
    assert deadlines == ["start", "stop", "start", "stop"]


def test_postgres_stops_the_deadline_after_the_connection_is_closed(database, postgres, monkeypatch):
    from server.accounts import store

    order = []

    class OrderedDeadline(RecordedDeadline):
        def stop(self):
            order.append("stop deadline")

    original_close = FakeConnection.close
    monkeypatch.setattr(store, "CallDeadline", OrderedDeadline)
    monkeypatch.setattr(FakeConnection, "close", lambda self: (order.append("close"), original_close(self)))
    postgres.add("Mara", "hash-1")
    assert order == ["close", "stop deadline"]


@pytest.mark.parametrize("failing_step", ["create", "commit"])
def test_postgres_stops_the_deadline_when_a_call_fails(database, postgres, deadlines, failing_step):
    database.fail_on = failing_step
    with pytest.raises(StoreUnavailable):
        postgres.add("Mara", "hash-1")
    assert deadlines == ["start", "stop"]


def test_no_deadline_is_started_when_connecting_fails(monkeypatch, deadlines):
    monkeypatch.setattr(psycopg, "connect", refuse_to_connect)
    with pytest.raises(StoreUnavailable):
        PostgresAccountStore("postgresql://example.invalid/db").find("Mara")
    assert deadlines == []


def test_at_most_two_passwords_are_hashed_at_the_same_moment():
    # One Argon2 hash needs 64 MiB; four workers must not hash four at once.
    import threading
    import time

    real = service.Argon2Hasher()
    running = []
    most = []
    lock = threading.Lock()

    class SlowHasher:
        def _work(self):
            with lock:
                running.append(1)
                most.append(len(running))
            time.sleep(0.1)
            with lock:
                running.pop()
            return "$argon2-fake"

        def hash(self, password):
            return self._work()

        def verify(self, password_hash, password):
            self._work()
            return True

    real._hasher = SlowHasher()
    threads = [threading.Thread(target=real.hash, args=("pw",)) for _ in range(3)]
    threads += [threading.Thread(target=real.matches, args=("h", "pw")) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert service.HASHES_AT_ONCE == 2
    assert max(most) == 2


# Diagnosing database problems from the log without leaking secrets (M1-2.5).
# The fake values below are easy to recognise, so a test can check that none
# of them reaches the log.

from server.accounts.store import describe_problem, problem_log_line  # noqa: E402

SECRET_URL = "postgresql://postgres.abcdefgh:hunter2secret@aws-0-eu-west-9.pooler.supabase.example:6543/gamedb"
SECRET_PARTS = [
    SECRET_URL,
    "postgres.abcdefgh",  # user name
    "abcdefgh",  # project
    "hunter2secret",  # password
    "pooler.supabase.example",  # host
    "203.0.113.5",  # IP address
    "6543",  # port
    "gamedb",  # database name
]
CONNECTION_FAILED = 'connection failed: connection to server at "203.0.113.5", port 6543 failed: '
PASSWORD_REJECTED = CONNECTION_FAILED + 'FATAL:  password authentication failed for user "postgres.abcdefgh"'


class StandInError(Exception):
    """An error with a SQLSTATE that psycopg has no class of its own for here."""

    def __init__(self, message, sqlstate=None):
        super().__init__(message)
        self.sqlstate = sqlstate


@pytest.mark.parametrize(
    "problem, reason",
    [
        (psycopg.OperationalError(PASSWORD_REJECTED), "password rejected"),
        (psycopg.errors.InvalidPassword("FATAL:  no access"), "password rejected"),
        (psycopg.OperationalError(CONNECTION_FAILED + "FATAL:  Tenant or user not found"), "user or project not found"),
        (psycopg.errors.InvalidAuthorizationSpecification("FATAL:  no such role"), "user or project not found"),
        (psycopg.errors.InvalidCatalogName("FATAL:  no such thing"), "database name not found"),
        (psycopg.OperationalError(CONNECTION_FAILED + 'FATAL:  database "gamedb" does not exist'), "database name not found"),
        (
            psycopg.OperationalError('could not translate host name "pooler.supabase.example" to address'),
            "host name not found",
        ),
        (
            psycopg.OperationalError("failed to resolve host 'pooler.supabase.example': [Errno -2] Name or service not known"),
            "host name not found",
        ),
        (
            psycopg.OperationalError("[Errno 8] nodename nor servname provided, or not known"),
            "host name not found",
        ),
        (psycopg.OperationalError(CONNECTION_FAILED + "Network is unreachable"), "network unreachable"),
        (psycopg.OperationalError(CONNECTION_FAILED + "No route to host"), "network unreachable"),
        (psycopg.OperationalError(CONNECTION_FAILED + "Connection refused"), "connection refused"),
        (psycopg.errors.ConnectionTimeout("connection timeout expired"), "connection timed out"),
        (psycopg.OperationalError(CONNECTION_FAILED + "Operation timed out"), "connection timed out"),
        (psycopg.errors.TooManyConnections("FATAL:  go away"), "too many connections"),
        (psycopg.OperationalError(CONNECTION_FAILED + "FATAL:  sorry, too many clients already"), "too many connections"),
        (psycopg.OperationalError(CONNECTION_FAILED + "FATAL:  Max client connections reached"), "too many connections"),
        (psycopg.OperationalError(CONNECTION_FAILED + "server does not support SSL, but SSL was required"), "encrypted connection failed"),
        (psycopg.errors.QueryCanceled("canceling statement due to statement timeout"), "statement timed out"),
        (psycopg.errors.InsufficientPrivilege("permission denied for schema public"), "no permission"),
        (psycopg.errors.UndefinedTable('relation "accounts" does not exist'), "table missing"),
        (StandInError("something unusual", sqlstate="57014"), "statement timed out"),
        (StandInError("something unusual", sqlstate="XX000"), "other database error"),
        (psycopg.OperationalError("something nobody has seen before"), "other database error"),
        (psycopg.OperationalError(""), "other database error"),
    ],
)
def test_describe_problem_names_the_reason(problem, reason):
    assert describe_problem(problem, "connect") == reason


def test_describe_problem_trusts_the_sqlstate_more_than_the_text():
    problem = StandInError("connection refused", sqlstate="42501")
    assert describe_problem(problem) == "no permission"


def test_describe_problem_takes_the_first_matching_reason():
    # The text of a rejected password may also mention SSL.
    problem = psycopg.OperationalError(PASSWORD_REJECTED + ", SSL off")
    assert describe_problem(problem, "connect") == "password rejected"


def test_a_url_that_cannot_be_read_is_named_only_while_connecting():
    problem = psycopg.ProgrammingError('missing "=" after "postgres" in connection info string')
    assert describe_problem(problem, "connect") == "database URL could not be read"
    assert describe_problem(problem, "query") == "other database error"
    assert describe_problem(problem) == "other database error"


def test_a_real_malformed_url_is_a_url_that_cannot_be_read(caplog):
    # Nothing is replaced here: psycopg itself refuses the text before any
    # network is used.
    store = PostgresAccountStore("postgres ql://user:hunter2secret@example.invalid/db")
    with caplog.at_level("WARNING"), pytest.raises(StoreUnavailable):
        store.find("Mara")
    assert caplog.messages == [
        "Accounts database problem during connect: database URL could not be read (ProgrammingError, SQLSTATE none)"
    ]


def test_a_host_that_cannot_be_a_host_name_is_store_unavailable(caplog):
    # Python raises UnicodeError for this host, not a psycopg error, and does
    # so before any network is used.
    store = PostgresAccountStore("postgresql://user:hunter2secret@db..example.invalid:6543/db")
    with caplog.at_level("WARNING"), pytest.raises(StoreUnavailable):
        store.add("Mara", "hash-1")
    assert caplog.messages == [
        "Accounts database problem during connect: database URL could not be read (UnicodeEncodeError, SQLSTATE none)"
    ]


def test_the_log_line_has_reason_step_class_and_sqlstate():
    line = problem_log_line(psycopg.errors.InsufficientPrivilege("permission denied"), "create table")
    assert line == "Accounts database problem during create table: no permission (InsufficientPrivilege, SQLSTATE 42501)"


@pytest.mark.parametrize(
    "message",
    [
        PASSWORD_REJECTED,
        f"invalid connection option in {SECRET_URL}",
        f'FATAL:  database "gamedb" does not exist on aws-0-eu-west-9.pooler.supabase.example ({SECRET_URL})',
    ],
)
def test_the_log_never_shows_the_connection_details(monkeypatch, caplog, message):
    def fail(*args, **kwargs):
        raise psycopg.OperationalError(message)

    monkeypatch.setattr(psycopg, "connect", fail)
    store = PostgresAccountStore(SECRET_URL)
    with caplog.at_level("DEBUG"), pytest.raises(StoreUnavailable) as caught:
        store.find("Mara")

    assert len(caplog.records) == 1
    logged = caplog.text
    assert "Accounts database problem during connect: " in logged
    assert "(OperationalError, SQLSTATE none)" in logged
    for secret in SECRET_PARTS:
        assert secret not in logged
        assert secret not in str(caught.value)
    # Nothing of the raw text beyond the fixed reason.
    for raw in ["FATAL", "connection to server", "authentication", "invalid connection option", "does not exist"]:
        assert raw not in logged


def test_the_whole_log_line_for_a_rejected_password(monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise psycopg.OperationalError(PASSWORD_REJECTED)

    monkeypatch.setattr(psycopg, "connect", fail)
    with caplog.at_level("WARNING"), pytest.raises(StoreUnavailable):
        PostgresAccountStore(SECRET_URL).add("Mara", "hash-1")
    assert caplog.messages == [
        "Accounts database problem during connect: password rejected (OperationalError, SQLSTATE none)"
    ]


def test_a_failure_in_create_table_logs_the_step_create_table(database, postgres, caplog):
    database.fail_on = "create"
    with caplog.at_level("WARNING"), pytest.raises(StoreUnavailable):
        postgres.find("Mara")
    assert caplog.messages == [
        "Accounts database problem during create table: other database error (OperationalError, SQLSTATE none)"
    ]


def test_a_failure_saving_the_table_logs_the_step_create_table(database, postgres, caplog):
    database.fail_on = "commit"
    with caplog.at_level("WARNING"), pytest.raises(StoreUnavailable):
        postgres.add("Mara", "hash-1")
    assert len(caplog.messages) == 1
    assert "during create table: " in caplog.messages[0]


@pytest.mark.parametrize("failing_query", ["SET", "INSERT", "SELECT"])
def test_a_failure_in_the_query_logs_the_step_query(database, postgres, caplog, monkeypatch, failing_query):
    postgres.find("Mara")  # creates the table

    def failing_execute(self, query, params=None):
        if query.strip().startswith(failing_query):
            raise psycopg.errors.QueryCanceled("canceling statement due to statement timeout")
        return FakeCursor()

    monkeypatch.setattr(FakeConnection, "execute", failing_execute)
    with caplog.at_level("WARNING"), pytest.raises(StoreUnavailable):
        postgres.add("Mara", "hash-1")
        postgres.find("Mara")
    assert caplog.messages == [
        "Accounts database problem during query: statement timed out (QueryCanceled, SQLSTATE 57014)"
    ]
    assert database.events[-1] == ("close",)


def test_a_failure_saving_the_query_logs_the_step_query(database, postgres, caplog):
    postgres.find("Mara")  # creates the table
    database.fail_on = "commit"
    with caplog.at_level("WARNING"), pytest.raises(StoreUnavailable):
        postgres.add("Mara", "hash-1")
    assert len(caplog.messages) == 1
    assert "during query: " in caplog.messages[0]


@pytest.mark.parametrize("rule", [service.sign_up, service.log_in])
def test_players_still_get_accounts_unavailable_for_every_step(monkeypatch, hasher, rule):
    def fail(*args, **kwargs):
        raise psycopg.OperationalError(PASSWORD_REJECTED)

    monkeypatch.setattr(psycopg, "connect", fail)
    store = PostgresAccountStore(SECRET_URL)
    assert rule(store, hasher, "Mara", "password123") == (None, "accounts_unavailable")


def test_postgres_turns_prepared_statements_off_for_the_pooler(database, postgres):
    postgres.find("Mara")
    args, kwargs = database.connect_arguments
    assert kwargs["prepare_threshold"] is None


def test_psycopg_itself_only_logs_errors():
    # Its WARNING about a failed rollback can contain the host and the user.
    import logging

    assert logging.getLogger("psycopg").level == logging.ERROR


# Row level security on the table `accounts` (M1-2.5): without it, Supabase's
# Data API would show the table to anyone with the project's public key.

ROW_LEVEL_SECURITY = "ALTER TABLE accounts ENABLE ROW LEVEL SECURITY"


def test_postgres_turns_row_level_security_on_between_create_and_commit(database, postgres):
    postgres.find("Mara")
    assert database.events[1][1].strip().startswith("CREATE TABLE IF NOT EXISTS accounts")
    assert database.events[2] == ("execute", ROW_LEVEL_SECURITY, None)
    assert database.events[3] == ("commit",)


def test_postgres_turns_row_level_security_on_once_only(database, postgres):
    postgres.find("Mara")
    postgres.add("Mara", "hash-1")
    postgres.find("Mara")
    assert database.queries("ALTER") == [(ROW_LEVEL_SECURITY, None)]


def test_a_failure_turning_row_level_security_on_is_a_failed_create_table(database, postgres, caplog, monkeypatch):
    working_execute = FakeConnection.execute

    def failing_execute(self, query, params=None):
        working_execute(self, query, params)  # writes the statement down
        if query.startswith("ALTER"):
            raise psycopg.errors.InsufficientPrivilege("must be owner of table accounts")
        return FakeCursor()

    monkeypatch.setattr(FakeConnection, "execute", failing_execute)
    with caplog.at_level("WARNING"), pytest.raises(StoreUnavailable):
        postgres.find("Mara")
    assert caplog.messages == [
        "Accounts database problem during create table: no permission (InsufficientPrivilege, SQLSTATE 42501)"
    ]
    assert postgres._table_exists is False
    # Nothing was saved and no query was tried on the unprotected table.
    assert ("commit",) not in database.events
    assert database.queries("SELECT") == []
    assert database.events[-1] == ("close",)

    # The next call tries the whole step again.
    monkeypatch.setattr(FakeConnection, "execute", working_execute)
    assert postgres.find("Mara") is None
    assert postgres._table_exists is True
    assert len(database.queries("CREATE TABLE")) == 2
    assert len(database.queries("ALTER")) == 2
