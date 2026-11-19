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
    assert kinds == ["SET", "CREATE", "commit", "SET", "SELECT", "commit", "close"]
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
    assert kinds == ["SET", "CREATE", "commit", "SET", "INSERT", "commit", "close", "SET", "SELECT", "commit", "close"]
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
