"""Where accounts are kept.

Both stores offer the same two methods, so the rest of the server does not
care which one it talks to:

    add(name, password_hash)  -> True, or False when the name already exists
    find(name)                -> (stored_name, password_hash), or None

Names are unique ignoring case: "Mara" and "mara" are the same account. The
spelling of the first sign-up is kept and shown.

Both methods may raise `StoreUnavailable` when the database cannot be reached.
A store only ever sees the hash of a password, never the password itself.
"""

import logging
import threading

import psycopg

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECONDS = 5
# After connecting, no statement may run longer than 5 seconds (5000 ms).
# SET LOCAL lasts until the end of the current transaction, so it is sent at
# the start of each one. Unlike a connection option, it works through
# Supabase's connection pooler whatever mode that runs in.
SET_STATEMENT_TIMEOUT = "SET LOCAL statement_timeout = 5000"

CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS accounts (
        name_key TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
"""
# The %s are filled in by the database driver, never by Python string
# formatting. That is what keeps a name like "x'; DROP TABLE" harmless.
INSERT_ACCOUNT = """
    INSERT INTO accounts (name_key, name, password_hash)
    VALUES (%s, %s, %s)
    ON CONFLICT (name_key) DO NOTHING
"""
SELECT_ACCOUNT = "SELECT name, password_hash FROM accounts WHERE name_key = %s"


class StoreUnavailable(Exception):
    """The accounts cannot be read or written right now."""


def name_key(name: str) -> str:
    """The form of a name used to compare: "Mara" and "mara" give the same key."""
    return name.lower()


class MemoryAccountStore:
    """Accounts in a dict. Used by the tests and when no database is configured.

    Everything is lost when the server stops.
    """

    def __init__(self):
        self._accounts = {}  # name key -> (stored name, password hash)
        # The server calls the store from worker threads. The lock makes sure
        # two sign-ups with the same name cannot both pass the "is it free?" check.
        self._lock = threading.Lock()

    def add(self, name: str, password_hash: str) -> bool:
        key = name_key(name)
        with self._lock:
            if key in self._accounts:
                return False
            self._accounts[key] = (name, password_hash)
            return True

    def find(self, name: str):
        return self._accounts.get(name_key(name))


class PostgresAccountStore:
    """Accounts in the table `accounts` of a Postgres database (Supabase).

    Nothing connects until the first `add` or `find`. Each call opens its own
    short connection: slower than keeping one open, but there is no shared
    connection that could break or be used by two threads at once.
    """

    def __init__(self, database_url: str):
        # The URL contains the database password: never log or print it.
        self._database_url = database_url
        self._table_exists = False
        # The store is called from two worker threads. The lock makes sure
        # only one of them creates the table.
        self._table_lock = threading.Lock()

    def add(self, name: str, password_hash: str) -> bool:
        try:
            with self._connect() as connection:
                cursor = connection.execute(INSERT_ACCOUNT, (name_key(name), name, password_hash))
                # No row was inserted when the name already existed.
                return cursor.rowcount == 1
        except psycopg.Error as problem:
            raise self._unavailable(problem) from None

    def find(self, name: str):
        try:
            with self._connect() as connection:
                row = connection.execute(SELECT_ACCOUNT, (name_key(name),)).fetchone()
        except psycopg.Error as problem:
            raise self._unavailable(problem) from None
        if row is None:
            return None
        return (row[0], row[1])

    def _connect(self):
        """Open a connection, ready for one `add` or `find`.

        Used as `with self._connect() as connection:`, which saves the changes
        and closes the connection at the end.
        """
        connection = psycopg.connect(
            self._database_url,
            connect_timeout=CONNECT_TIMEOUT_SECONDS,
            # Supabase's connection pooler does not support prepared statements.
            prepare_threshold=None,
        )
        try:
            self._create_table_once(connection)
            connection.execute(SET_STATEMENT_TIMEOUT)
        except psycopg.Error:
            connection.close()
            raise
        return connection

    def _create_table_once(self, connection):
        """Create the table `accounts` if this store has not done so yet."""
        with self._table_lock:
            if self._table_exists:
                return
            connection.execute(SET_STATEMENT_TIMEOUT)
            connection.execute(CREATE_TABLE)
            # Saved on its own, before anything else happens on the connection.
            # Only then is it certain that the table exists, whatever goes
            # wrong later. If this fails, the next call tries again.
            connection.commit()
            self._table_exists = True

    def _unavailable(self, problem: Exception) -> StoreUnavailable:
        # Only the kind of error is logged. The full text could contain details
        # of the connection, and those stay out of the logs.
        logger.warning("Accounts database problem: %s", type(problem).__name__)
        return StoreUnavailable("The accounts database could not be used.")


def make_account_store(database_url):
    """Postgres when a database URL is configured, otherwise memory."""
    if database_url:
        return PostgresAccountStore(database_url)
    return MemoryAccountStore()
