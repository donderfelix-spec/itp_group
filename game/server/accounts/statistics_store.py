"""Where statistics are kept.

Both stores offer the same three methods, like the stores for accounts
(`store.py`), so the rest of the server does not care which one it talks to:

    record_round(mode, changes)  add the changes of one round (see statistics.py)
    records_of(name)             -> {mode: record} of one account, {} if it never played
    top(limit)                   -> the best `limit` accounts as leaderboard totals
                                    (see statistics.total_of)

Statistics are keyed like accounts: by `name_key`, so "Mara" and "mara" are
the same account. There is one row per account and mode, so recording a
further mode does not require a schema change.

All three methods may raise `StoreUnavailable` when the database cannot be reached.
"""

import logging
import threading

import psycopg

from server.accounts import statistics
from server.accounts.store import (
    CONNECT_TIMEOUT_SECONDS,
    SET_STATEMENT_TIMEOUT,
    SOCKET_OPTIONS,
    CallDeadline,
    StoreUnavailable,
    describe_problem,
    name_key,
)

logger = logging.getLogger(__name__)

CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS account_statistics (
        name_key TEXT NOT NULL,
        mode TEXT NOT NULL,
        name TEXT NOT NULL,
        rounds INTEGER NOT NULL DEFAULT 0,
        wins INTEGER NOT NULL DEFAULT 0,
        best_seconds DOUBLE PRECISION,
        PRIMARY KEY (name_key, mode)
    )
"""
# Like the table `accounts` (S-90): with row level security on and no policy,
# Supabase's public Data API sees no rows. Our server is the owner of the
# table and still reads and writes. Safe to repeat.
ENABLE_ROW_LEVEL_SECURITY = "ALTER TABLE account_statistics ENABLE ROW LEVEL SECURITY"
# The %s are filled in by the database driver, never by Python string formatting.
# One statement adds a round, whether the row exists or not, so two rounds
# that end at the same moment cannot lose each other's numbers. LEAST skips
# NULL in Postgres: a time always beats "no time yet".
ADD_ROUND = """
    INSERT INTO account_statistics (name_key, mode, name, rounds, wins, best_seconds)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (name_key, mode) DO UPDATE SET
        rounds = account_statistics.rounds + EXCLUDED.rounds,
        wins = account_statistics.wins + EXCLUDED.wins,
        best_seconds = LEAST(account_statistics.best_seconds, EXCLUDED.best_seconds)
"""
SELECT_RECORDS = "SELECT mode, rounds, wins, best_seconds FROM account_statistics WHERE name_key = %s"
# The same order as `statistics.best_first`. COLLATE "C" compares the keys
# letter by letter, as Python does.
SELECT_TOP = """
    SELECT MIN(name), SUM(wins) AS total_wins,
           MIN(best_seconds) FILTER (WHERE mode = %s) AS best_duel,
           COALESCE(SUM(wins) FILTER (WHERE mode = %s), 0) AS classic_wins,
           COALESCE(SUM(wins) FILTER (WHERE mode = %s), 0) AS duel_wins
    FROM account_statistics
    GROUP BY name_key
    ORDER BY total_wins DESC, best_duel ASC NULLS LAST, name_key COLLATE "C" ASC
    LIMIT %s
"""


class MemoryStatisticsStore:
    """Statistics in a dict. Used by the tests and when no database is configured.

    Everything is lost when the server stops.
    """

    def __init__(self):
        self._names = {}  # name key -> name as it is shown
        self._records = {}  # name key -> {mode: record}
        # The server calls the store from worker threads. The lock keeps two
        # rounds that end at the same moment from losing each other's numbers.
        self._lock = threading.Lock()

    def record_round(self, mode: str, changes):
        with self._lock:
            for change in changes:
                key = name_key(change["name"])
                self._names.setdefault(key, change["name"])
                records = self._records.setdefault(key, {})
                records[mode] = statistics.add_change(records.get(mode), change)

    def records_of(self, name: str) -> dict:
        with self._lock:
            # A copy: the caller must not be able to change what is stored.
            return {mode: dict(record) for mode, record in self._records.get(name_key(name), {}).items()}

    def top(self, limit: int) -> list:
        with self._lock:
            totals = [statistics.total_of(self._names[key], records) for key, records in self._records.items()]
        return statistics.best_first(totals)[:limit]


class PostgresStatisticsStore:
    """Statistics in the table `account_statistics` of a Postgres database (Supabase).

    Built like `PostgresAccountStore`: nothing connects until the first call,
    and each call opens its own short connection.
    """

    def __init__(self, database_url: str):
        # The URL contains the database password: never log or print it.
        self._database_url = database_url
        self._table_exists = False
        # The store is called from several worker threads. The lock makes sure
        # only one of them creates the table.
        self._table_lock = threading.Lock()

    def record_round(self, mode: str, changes):
        connection, deadline = self._connect()
        try:
            # All changes of a round are saved together or not at all.
            with connection:
                connection.execute(SET_STATEMENT_TIMEOUT)
                # Each row stays locked until the round is saved. Two rounds
                # written at the same moment with the same two accounts in
                # opposite order would wait for each other, and Postgres
                # would throw one of them away (a deadlock). In the order of
                # the keys, the second one simply waits for the first (S-211).
                for change in sorted(changes, key=lambda change: name_key(change["name"])):
                    connection.execute(ADD_ROUND, _values_of(mode, change))
        except psycopg.Error as problem:
            raise self._unavailable("query", problem) from None
        finally:
            deadline.stop()

    def records_of(self, name: str) -> dict:
        rows = self._select(SELECT_RECORDS, (name_key(name),))
        return {
            mode: {"rounds": rounds, "wins": wins, "best_seconds": best_seconds}
            for mode, rounds, wins, best_seconds in rows
        }

    def top(self, limit: int) -> list:
        rows = self._select(SELECT_TOP, (statistics.DUEL, statistics.CLASSIC, statistics.DUEL, limit))
        # SUM gives a whole number of its own kind; `int` makes it a plain one.
        return [
            (name, int(wins), best_seconds, int(classic_wins), int(duel_wins))
            for name, wins, best_seconds, classic_wins, duel_wins in rows
        ]

    def _select(self, query: str, values: tuple) -> list:
        connection, deadline = self._connect()
        try:
            with connection:
                connection.execute(SET_STATEMENT_TIMEOUT)
                return connection.execute(query, values).fetchall()
        except psycopg.Error as problem:
            raise self._unavailable("query", problem) from None
        finally:
            deadline.stop()

    def _connect(self):
        """Open a connection, with the table `account_statistics` in place.

        Returns `(connection, deadline)`, like `PostgresAccountStore._connect`.
        Raises `StoreUnavailable` when connecting or creating the table fails;
        the log then says which of the two it was.
        """
        try:
            connection = psycopg.connect(
                self._database_url,
                connect_timeout=CONNECT_TIMEOUT_SECONDS,
                # Supabase's connection pooler does not support prepared statements.
                prepare_threshold=None,
                # See `SOCKET_OPTIONS` in store.py (S-211).
                **SOCKET_OPTIONS,
            )
        # UnicodeError: see `PostgresAccountStore._connect`.
        except (psycopg.Error, UnicodeError) as problem:
            raise self._unavailable("connect", problem) from None
        # Started before the table is created, see `PostgresAccountStore._connect`.
        deadline = CallDeadline(connection)
        try:
            self._create_table_once(connection)
        except psycopg.Error as problem:
            connection.close()
            deadline.stop()
            raise self._unavailable("create table", problem) from None
        return connection, deadline

    def _create_table_once(self, connection):
        """Create and protect the table if this store has not done so yet."""
        with self._table_lock:
            if self._table_exists:
                return
            connection.execute(SET_STATEMENT_TIMEOUT)
            connection.execute(CREATE_TABLE)
            connection.execute(ENABLE_ROW_LEVEL_SECURITY)
            # Saved on its own, before anything else happens on the connection.
            # If this fails, the next call tries again.
            connection.commit()
            self._table_exists = True

    def _unavailable(self, step: str, problem: Exception) -> StoreUnavailable:
        # The log gets a fixed reason, never the text of the error: that text
        # can contain the host, the port and the user name of the database.
        logger.warning(problem_log_line(problem, step))
        return StoreUnavailable("The statistics database could not be used.")


def _values_of(mode: str, change) -> tuple:
    name = change["name"]
    return (name_key(name), mode, name, change["rounds"], change["wins"], change["best_seconds"])


def problem_log_line(problem: Exception, step: str) -> str:
    """The one line written to the log for a database error. No secrets in it."""
    reason = describe_problem(problem, step)
    kind = type(problem).__name__
    sqlstate = getattr(problem, "sqlstate", None) or "none"
    return f"Statistics database problem during {step}: {reason} ({kind}, SQLSTATE {sqlstate})"


def make_statistics_store(database_url):
    """Postgres when a database URL is configured, otherwise memory."""
    if database_url:
        return PostgresStatisticsStore(database_url)
    return MemoryStatisticsStore()
