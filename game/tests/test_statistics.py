"""The rules for statistics and the two stores, without a server (M2-2.4, S-40)."""

import logging

import psycopg
import pytest

from server.accounts import statistics
from server.accounts.statistics_store import (
    MemoryStatisticsStore,
    PostgresStatisticsStore,
    make_statistics_store,
)
from server.accounts.store import StoreUnavailable
from server.modes.duel import Duel

SECRET_URL = "postgresql://user:hunter2secret@db.example.invalid:6543/postgres"


def row(place, name, seconds, done):
    return {"place": place, "name": name, "seconds": seconds, "done": done}


def change(name, wins, best_seconds):
    return {"name": name, "rounds": 1, "wins": wins, "best_seconds": best_seconds}


def record(rounds, wins, best_seconds):
    return {"rounds": rounds, "wins": wins, "best_seconds": best_seconds}


# From a ranking to the changes


def test_the_winner_gets_a_win_and_everybody_a_round():
    ranking = [row(1, "Mara", 72.4, 3), row(2, "Tiago", 80.0, 3)]
    assert statistics.changes_from_duel(ranking, {"Mara", "Tiago"}) == [
        change("Mara", 1, 72.4),
        change("Tiago", 0, 80.0),
    ]


def test_a_player_who_did_not_finish_gets_a_round_but_no_time():
    ranking = [row(1, "Mara", 72.4, 3), row(2, "Tiago", None, 2)]
    assert statistics.changes_from_duel(ranking, {"Mara", "Tiago"})[1] == change("Tiago", 0, None)


def test_place_1_without_finishing_is_no_win():
    # The time ran out: Mara is on place 1 with the most stations, but nobody won.
    ranking = [row(1, "Mara", None, 2), row(2, "Tiago", None, 0)]
    assert statistics.changes_from_duel(ranking, {"Mara", "Tiago"}) == [
        change("Mara", 0, None),
        change("Tiago", 0, None),
    ]


def test_two_players_with_the_same_time_both_win():
    ranking = [row(1, "Mara", 72.4, 3), row(1, "Tiago", 72.4, 3), row(3, "Ines", 90.0, 3)]
    changes = statistics.changes_from_duel(ranking, {"Mara", "Tiago", "Ines"})
    assert [each["wins"] for each in changes] == [1, 1, 0]


def test_a_single_remaining_player_who_finishes_wins():
    assert statistics.changes_from_duel([row(1, "Mara", 61.0, 3)], {"Mara"}) == [change("Mara", 1, 61.0)]


def test_a_single_remaining_player_who_does_not_finish_gets_only_the_round():
    assert statistics.changes_from_duel([row(1, "Mara", None, 1)], {"Mara"}) == [change("Mara", 0, None)]


def test_a_guest_gets_no_change_even_as_the_winner():
    ranking = [row(1, "Guest0042", 50.0, 3), row(2, "Mara", 72.4, 3)]
    assert statistics.changes_from_duel(ranking, {"Mara"}) == [change("Mara", 0, 72.4)]


def test_a_player_who_left_and_is_not_in_the_ranking_gets_no_change():
    # Tiago has an account, but he left: the ranking does not list him.
    assert statistics.changes_from_duel([row(1, "Mara", 72.4, 3)], {"Mara", "Tiago"}) == [change("Mara", 1, 72.4)]


def test_an_empty_ranking_gives_no_changes():
    assert statistics.changes_from_duel([], {"Mara"}) == []


def test_a_round_of_guests_only_gives_no_changes():
    assert statistics.changes_from_duel([row(1, "Guest0001", 50.0, 3)], set()) == []


def test_the_changes_of_a_real_duel_ranking():
    """With the ranking the Duel itself builds, so the two files agree on its shape."""
    the_duel = Duel({"Mara": (1, 2, 3), "Tiago": (2, 3, 4), "Ines": (3, 4, 5)}, 100.0)
    for station, now in ((1, 110.0), (2, 120.0), (3, 130.04)):
        the_duel.station_done("Mara", station, now)
    for station, now in ((2, 110.0), (3, 120.0), (4, 130.0)):
        the_duel.station_done("Tiago", station, now)
    the_duel.station_done("Ines", 3, 150.0)
    # Mara and Tiago are both shown with 30.0 and share place 1 (S-97).
    assert statistics.changes_from_duel(the_duel.ranking(), {"Mara", "Tiago", "Ines"}) == [
        change("Mara", 1, 30.0),
        change("Tiago", 1, 30.0),
        change("Ines", 0, None),
    ]


# Adding a change to a record


def test_the_first_round_starts_from_nothing():
    assert statistics.add_change(None, change("Mara", 1, 72.4)) == record(1, 1, 72.4)


def test_a_further_round_adds_rounds_and_wins():
    assert statistics.add_change(record(3, 1, 72.4), change("Mara", 1, 80.0)) == record(4, 2, 72.4)


def test_adding_a_change_leaves_the_old_record_as_it_was():
    old = record(3, 1, 72.4)
    statistics.add_change(old, change("Mara", 1, 60.0))
    assert old == record(3, 1, 72.4)


@pytest.mark.parametrize(
    "old, new, best",
    [
        (None, None, None),
        (None, 72.4, 72.4),
        (72.4, None, 72.4),
        (72.4, 80.0, 72.4),
        (72.4, 60.1, 60.1),
        (72.4, 72.4, 72.4),
    ],
)
def test_the_best_time_is_the_smaller_one_and_no_time_never_wins(old, new, best):
    assert statistics.smaller_time(old, new) == best
    assert statistics.add_change(record(1, 0, old), change("Mara", 0, new))["best_seconds"] == best


# The profile


def test_the_profile_lists_every_mode_also_one_never_played():
    records = {"duel": record(3, 1, 72.4)}
    assert statistics.profile_rows(records, ("duel", "classic")) == [("duel", 3, 1), ("classic", 0, 0)]


def test_the_profile_of_an_account_that_never_played_is_all_zeros():
    assert statistics.profile_rows({}, ("duel",)) == [("duel", 0, 0)]
    assert statistics.best_duel_seconds({}) is None


def test_the_best_duel_time_comes_from_the_duel_only():
    records = {"duel": record(3, 1, 72.4), "classic": record(2, 2, None)}
    assert statistics.best_duel_seconds(records) == 72.4


# The leaderboard


def test_the_total_adds_the_wins_of_all_modes():
    records = {"duel": record(3, 1, 72.4), "classic": record(2, 2, None)}
    assert statistics.total_of("Mara", records) == ("Mara", 3, 72.4)


def test_the_leaderboard_is_ordered_by_wins_then_time_then_name():
    totals = [
        ("Zoe", 1, None),
        ("Rui", 1, 80.0),
        ("Mara", 3, 90.0),
        ("ines", 1, 70.0),
        ("Tiago", 1, 70.0),
        ("Ana", 1, None),
        ("Bea", 0, 40.0),
    ]
    assert [name for name, wins, best in statistics.best_first(totals)] == [
        "Mara", "ines", "Tiago", "Rui", "Ana", "Zoe", "Bea",
    ]


def test_names_are_ordered_ignoring_case():
    totals = [("bea", 1, 70.0), ("Ana", 1, 70.0), ("Cid", 1, 70.0)]
    assert [name for name, wins, best in statistics.best_first(totals)] == ["Ana", "bea", "Cid"]


def test_the_rows_of_the_leaderboard_are_numbered_from_1():
    assert statistics.leaderboard_rows([("Mara", 3, 72.4), ("Tiago", 1, None)]) == [
        {"place": 1, "name": "Mara", "wins": 3, "best_seconds": 72.4},
        {"place": 2, "name": "Tiago", "wins": 1, "best_seconds": None},
    ]


def test_an_empty_leaderboard_has_no_rows():
    assert statistics.best_first([]) == []
    assert statistics.leaderboard_rows([]) == []


# The store in memory


@pytest.fixture
def store():
    return MemoryStatisticsStore()


def test_an_account_that_never_played_has_no_records(store):
    assert store.records_of("Mara") == {}
    assert store.top(20) == []


def test_a_recorded_round_can_be_read(store):
    store.record_round("duel", [change("Mara", 1, 72.4), change("Tiago", 0, None)])
    assert store.records_of("Mara") == {"duel": record(1, 1, 72.4)}
    assert store.records_of("Tiago") == {"duel": record(1, 0, None)}


def test_a_second_round_adds_to_the_first(store):
    store.record_round("duel", [change("Mara", 1, 72.4)])
    store.record_round("duel", [change("Mara", 0, 65.0)])
    assert store.records_of("Mara") == {"duel": record(2, 1, 65.0)}


def test_statistics_are_the_same_account_in_any_case(store):
    store.record_round("duel", [change("Mara", 1, 72.4)])
    assert store.records_of("mARA") == {"duel": record(1, 1, 72.4)}


def test_a_second_mode_is_one_more_record(store):
    store.record_round("duel", [change("Mara", 1, 72.4)])
    store.record_round("classic", [change("Mara", 1, None)])
    assert store.records_of("Mara") == {"duel": record(1, 1, 72.4), "classic": record(1, 1, None)}
    assert store.top(20) == [("Mara", 2, 72.4)]


def test_what_the_store_returns_cannot_change_what_it_keeps(store):
    store.record_round("duel", [change("Mara", 1, 72.4)])
    store.records_of("Mara")["duel"]["wins"] = 99
    assert store.records_of("Mara") == {"duel": record(1, 1, 72.4)}


def test_recording_no_changes_changes_nothing(store):
    store.record_round("duel", [])
    assert store.top(20) == []


def test_top_is_ordered_and_cut_at_the_limit(store):
    store.record_round("duel", [change("Mara", 1, 72.4), change("Tiago", 0, 80.0), change("Ines", 0, None)])
    assert store.top(20) == [("Mara", 1, 72.4), ("Tiago", 0, 80.0), ("Ines", 0, None)]
    assert store.top(2) == [("Mara", 1, 72.4), ("Tiago", 0, 80.0)]


def test_without_a_database_url_statistics_live_in_memory():
    assert isinstance(make_statistics_store(None), MemoryStatisticsStore)
    assert isinstance(make_statistics_store(""), MemoryStatisticsStore)


def test_with_a_database_url_statistics_live_in_postgres():
    assert isinstance(make_statistics_store("postgresql://example.invalid/db"), PostgresStatisticsStore)


# The Postgres store with a fake connection: `psycopg.connect` is replaced,
# so the SQL is written down instead of run.


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeDatabase:
    """Hands out fake connections and writes down everything that happens.

    `events` holds, in order: ("execute", query, values), ("commit",), ("close",).
    """

    def __init__(self):
        self.events = []
        self.connections_opened = 0
        self.connect_arguments = None
        self.rows = []  # answer to SELECT
        self.fail_on = None  # the first word of the query that fails, or "commit"

    def connect(self, *args, **kwargs):
        self.connections_opened += 1
        self.connect_arguments = (args, kwargs)
        return FakeConnection(self)

    def queries(self, start=""):
        """The executed queries that begin with `start`, as (query, values) pairs."""
        executed = [event[1:] for event in self.events if event[0] == "execute"]
        return [(query, values) for query, values in executed if query.strip().startswith(start)]


class FakeConnection:
    def __init__(self, database):
        self._database = database

    def execute(self, query, values=None):
        self._database.events.append(("execute", query, values))
        fail_on = self._database.fail_on
        if fail_on is not None and query.strip().startswith(fail_on):
            raise psycopg.OperationalError("the query failed at host db.example.invalid for user hunter2secret")
        return FakeCursor(self._database.rows)

    def commit(self):
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
    return PostgresStatisticsStore("postgresql://example.invalid/db")


def refuse_to_connect(*args, **kwargs):
    raise psycopg.OperationalError(f"connection to {SECRET_URL} failed: password authentication failed")


def test_creating_the_postgres_store_does_not_connect(monkeypatch):
    monkeypatch.setattr(psycopg, "connect", refuse_to_connect)
    PostgresStatisticsStore("postgresql://example.invalid/db")


def test_postgres_connects_like_the_accounts_do(database, postgres):
    postgres.records_of("Mara")
    args, kwargs = database.connect_arguments
    assert args == ("postgresql://example.invalid/db",)
    assert kwargs == {"connect_timeout": 5, "prepare_threshold": None}


def test_postgres_creates_the_table_on_the_first_call_only(database, postgres):
    postgres.records_of("Mara")
    postgres.record_round("duel", [change("Mara", 1, 72.4)])
    postgres.top(20)
    assert len(database.queries("CREATE TABLE IF NOT EXISTS account_statistics")) == 1
    assert database.connections_opened == 3


def test_postgres_turns_row_level_security_on_before_saving_the_table(database, postgres):
    postgres.records_of("Mara")
    kinds = [event[1].strip().split()[0] if event[0] == "execute" else event[0] for event in database.events]
    assert kinds[:4] == ["SET", "CREATE", "ALTER", "commit"]
    assert database.queries("ALTER") == [("ALTER TABLE account_statistics ENABLE ROW LEVEL SECURITY", None)]


@pytest.mark.parametrize("failing_step", ["CREATE", "ALTER", "commit"])
def test_postgres_tries_to_create_the_table_again_after_a_failure(database, postgres, failing_step):
    database.fail_on = failing_step
    with pytest.raises(StoreUnavailable):
        postgres.records_of("Mara")
    database.fail_on = None
    postgres.records_of("Mara")
    assert len(database.queries("CREATE TABLE")) == 2


def test_postgres_limits_the_time_of_every_statement(database, postgres):
    postgres.records_of("Mara")
    postgres.top(20)
    # Once before creating the table, then once in each of the two calls.
    assert len(database.queries("SET LOCAL statement_timeout")) == 3


def test_postgres_records_a_round_with_one_parameterised_statement_per_account(database, postgres):
    postgres.record_round("duel", [change("Mara", 1, 72.4), change("Tiago", 0, None)])
    inserts = database.queries("INSERT INTO account_statistics")
    assert [values for query, values in inserts] == [
        ("mara", "duel", "Mara", 1, 1, 72.4),
        ("tiago", "duel", "Tiago", 1, 0, None),
    ]
    for query, values in inserts:
        assert query.count("%s") == 6
        assert "Mara" not in query and "duel" not in query


def test_postgres_adds_to_an_existing_row_and_keeps_the_smaller_time(database, postgres):
    postgres.record_round("duel", [change("Mara", 1, 72.4)])
    query = database.queries("INSERT")[0][0]
    assert "ON CONFLICT (name_key, mode) DO UPDATE" in query
    assert "rounds = account_statistics.rounds + EXCLUDED.rounds" in query
    assert "wins = account_statistics.wins + EXCLUDED.wins" in query
    assert "best_seconds = LEAST(account_statistics.best_seconds, EXCLUDED.best_seconds)" in query


def test_postgres_saves_a_round_once_and_closes(database, postgres):
    postgres.record_round("duel", [change("Mara", 1, 72.4), change("Tiago", 0, None)])
    # One commit for the table, one for both accounts of the round together.
    assert database.events.count(("commit",)) == 2
    assert database.events[-2:] == [("commit",), ("close",)]


def test_postgres_saves_nothing_of_a_round_when_one_statement_fails(database, postgres):
    postgres.records_of("Mara")  # the table is in place
    database.events.clear()
    database.fail_on = "INSERT"
    with pytest.raises(StoreUnavailable):
        postgres.record_round("duel", [change("Mara", 1, 72.4), change("Tiago", 0, None)])
    assert ("commit",) not in database.events
    assert database.events[-1] == ("close",)


def test_postgres_reads_the_records_of_the_lower_case_key(database, postgres):
    database.rows = [("duel", 3, 1, 72.4), ("classic", 2, 0, None)]
    assert postgres.records_of("Mara") == {"duel": record(3, 1, 72.4), "classic": record(2, 0, None)}
    query, values = database.queries("SELECT")[0]
    assert values == ("mara",)
    assert query.count("%s") == 1


def test_postgres_returns_no_records_for_an_account_that_never_played(database, postgres):
    assert postgres.records_of("Mara") == {}


def test_postgres_asks_for_the_top_with_the_limit_as_a_parameter(database, postgres):
    database.rows = [("Mara", 3, 72.4), ("Tiago", 1, None)]
    assert postgres.top(20) == [("Mara", 3, 72.4), ("Tiago", 1, None)]
    query, values = database.queries("SELECT")[0]
    assert values == ("duel", 20)
    assert "ORDER BY total_wins DESC, best_duel ASC NULLS LAST, name_key" in query
    assert "LIMIT %s" in query


def test_postgres_never_selects_the_key_or_anything_of_the_accounts(database, postgres):
    postgres.top(20)
    postgres.records_of("Mara")
    for query, values in database.queries("SELECT"):
        selected = query.split("FROM")[0]
        assert "name_key" not in selected
        assert "password" not in query
        assert "accounts" not in query.replace("account_statistics", "")


@pytest.mark.parametrize("call", ["record_round", "records_of", "top"])
def test_a_database_that_cannot_be_reached_is_store_unavailable(monkeypatch, caplog, call):
    monkeypatch.setattr(psycopg, "connect", refuse_to_connect)
    store = PostgresStatisticsStore(SECRET_URL)
    calls = {
        "record_round": lambda: store.record_round("duel", [change("Mara", 1, 72.4)]),
        "records_of": lambda: store.records_of("Mara"),
        "top": lambda: store.top(20),
    }
    with caplog.at_level(logging.DEBUG), pytest.raises(StoreUnavailable) as raised:
        calls[call]()
    assert caplog.messages == [
        "Statistics database problem during connect: password rejected (OperationalError, SQLSTATE none)"
    ]
    for secret in ("hunter2secret", "db.example.invalid", "6543", SECRET_URL):
        assert secret not in caplog.text
        assert secret not in str(raised.value)
    # Nothing of the first error travels along with the new one.
    assert raised.value.__cause__ is None and raised.value.__suppress_context__


@pytest.mark.parametrize(
    "failing_step, logged_step",
    [("CREATE", "create table"), ("ALTER", "create table"), ("INSERT", "query")],
)
def test_the_log_names_the_step_and_never_the_text_of_the_error(database, postgres, caplog, failing_step, logged_step):
    database.fail_on = failing_step
    with caplog.at_level(logging.DEBUG), pytest.raises(StoreUnavailable):
        postgres.record_round("duel", [change("Mara", 1, 72.4)])
    assert caplog.messages == [
        f"Statistics database problem during {logged_step}: other database error (OperationalError, SQLSTATE none)"
    ]
    assert "hunter2secret" not in caplog.text and "example.invalid" not in caplog.text


def test_a_failing_select_is_store_unavailable_and_logged_as_a_query(database, postgres, caplog):
    database.fail_on = "SELECT"
    with caplog.at_level(logging.DEBUG), pytest.raises(StoreUnavailable):
        postgres.top(20)
    assert caplog.messages == [
        "Statistics database problem during query: other database error (OperationalError, SQLSTATE none)"
    ]


def test_a_host_that_cannot_be_a_host_name_is_store_unavailable(caplog):
    store = PostgresStatisticsStore("postgresql://user:hunter2secret@db..example.invalid:6543/db")
    with caplog.at_level(logging.DEBUG), pytest.raises(StoreUnavailable):
        store.top(20)
    assert "hunter2secret" not in caplog.text
