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
# psycopg's own WARNING about a failed rollback can contain the host and the user.
logging.getLogger("psycopg").setLevel(logging.ERROR)

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

# Why the database could not be used, for the server log. The log only ever
# shows one of these fixed texts, never the text of the error itself: that
# text can contain the host, the port and the user name of the database.

# Postgres gives most errors a five-character code, the SQLSTATE.
REASON_BY_SQLSTATE = {
    "28P01": "password rejected",
    "28000": "user or project not found",
    "3D000": "database name not found",
    "53300": "too many connections",
    "57014": "statement timed out",
    "42501": "no permission",
    "42P01": "table missing",
}
# An error while connecting has no SQLSTATE, only a text. Each reason is
# listed with the words that give it away, in lower case. The order matters:
# the first match wins, and "ssl" comes last because it also appears in the
# text of other problems.
REASONS_BY_WORDS = [
    ("password rejected", ["password authentication failed"]),
    # "Tenant or user not found" is what Supabase's pooler answers when the
    # user name or the project in the URL is wrong.
    ("user or project not found", ["tenant or user not found"]),
    (
        "host name not found",
        [
            "could not translate host name",
            "name or service not known",
            "nodename nor servname",
            "failed to resolve host",  # psycopg's own wording, on every system
        ],
    ),
    ("network unreachable", ["network is unreachable", "no route to host"]),
    ("connection refused", ["connection refused"]),
    ("connection timed out", ["timeout expired", "timed out"]),
    ("too many connections", ["too many clients", "max client connections"]),
    ("encrypted connection failed", ["ssl"]),
]
URL_NOT_READABLE = "database URL could not be read"
OTHER_REASON = "other database error"


class StoreUnavailable(Exception):
    """The accounts cannot be read or written right now."""


def name_key(name: str) -> str:
    """The form of a name used to compare: "Mara" and "mara" give the same key."""
    return name.lower()


def describe_problem(problem: Exception, step: str = "query") -> str:
    """The reason for a database error, as one of the fixed texts above.

    `step` is what the store was doing: "connect", "create table" or "query".
    """
    sqlstate = getattr(problem, "sqlstate", None)
    if sqlstate in REASON_BY_SQLSTATE:
        return REASON_BY_SQLSTATE[sqlstate]
    text = str(problem).lower()
    # A wrong database name while connecting comes without its SQLSTATE.
    if 'database "' in text and "does not exist" in text:
        return REASON_BY_SQLSTATE["3D000"]
    for reason, words in REASONS_BY_WORDS:
        if any(word in text for word in words):
            return reason
    # psycopg could not even take the URL apart (ProgrammingError), or the
    # host name in it cannot be a host name at all (UnicodeError).
    if step == "connect" and isinstance(problem, (psycopg.ProgrammingError, UnicodeError)):
        return URL_NOT_READABLE
    return OTHER_REASON


def problem_log_line(problem: Exception, step: str) -> str:
    """The one line written to the log for a database error. No secrets in it."""
    reason = describe_problem(problem, step)
    kind = type(problem).__name__
    sqlstate = getattr(problem, "sqlstate", None) or "none"
    return f"Accounts database problem during {step}: {reason} ({kind}, SQLSTATE {sqlstate})"


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
        connection = self._connect()
        try:
            with connection:
                connection.execute(SET_STATEMENT_TIMEOUT)
                cursor = connection.execute(INSERT_ACCOUNT, (name_key(name), name, password_hash))
                # No row was inserted when the name already existed.
                return cursor.rowcount == 1
        except psycopg.Error as problem:
            raise self._unavailable("query", problem) from None

    def find(self, name: str):
        connection = self._connect()
        try:
            with connection:
                connection.execute(SET_STATEMENT_TIMEOUT)
                row = connection.execute(SELECT_ACCOUNT, (name_key(name),)).fetchone()
        except psycopg.Error as problem:
            raise self._unavailable("query", problem) from None
        if row is None:
            return None
        return (row[0], row[1])

    def _connect(self):
        """Open a connection, with the table `accounts` in place.

        Used as `with connection:`, which saves the changes and closes the
        connection at the end. Raises `StoreUnavailable` when connecting or
        creating the table fails; the log then says which of the two it was.
        """
        try:
            connection = psycopg.connect(
                self._database_url,
                connect_timeout=CONNECT_TIMEOUT_SECONDS,
                # Supabase's connection pooler does not support prepared statements.
                prepare_threshold=None,
            )
        # UnicodeError is not a psycopg error: Python raises it itself when the
        # host in the URL cannot be a host name (for example "db..example.com",
        # or a part longer than 63 letters). Without catching it here, a typing
        # mistake in the URL would not become StoreUnavailable.
        except (psycopg.Error, UnicodeError) as problem:
            raise self._unavailable("connect", problem) from None
        try:
            self._create_table_once(connection)
        except psycopg.Error as problem:
            connection.close()
            raise self._unavailable("create table", problem) from None
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

    def _unavailable(self, step: str, problem: Exception) -> StoreUnavailable:
        # The log gets a fixed reason, never the text of the error. That text
        # could contain details of the connection, and those stay out of the logs.
        logger.warning(problem_log_line(problem, step))
        return StoreUnavailable("The accounts database could not be used.")


def make_account_store(database_url):
    """Postgres when a database URL is configured, otherwise memory."""
    if database_url:
        return PostgresAccountStore(database_url)
    return MemoryAccountStore()
