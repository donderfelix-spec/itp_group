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
import socket
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
# The statement_timeout above is kept by the database server. If the network
# path dies in the middle of a call, nothing on our side would notice for
# minutes, and the worker thread would wait all that time (S-211). These are
# libpq's own socket options: our computer then checks an idle connection
# after 2 seconds and gives up when the other side has not answered for 5
# seconds. They only change our end of the connection and are never sent to
# the server, so the pooler of Supabase cannot refuse them. Where the system
# does not know an option (tcp_user_timeout outside Linux), libpq skips it.
WANTED_SOCKET_OPTIONS = {
    "keepalives": 1,
    "keepalives_idle": 2,
    "keepalives_interval": 1,
    "keepalives_count": 3,
    "tcp_user_timeout": 5000,  # milliseconds
}
# The socket option each of them sets, by its name in Python's `socket`.
# `keepalives` is missing on purpose: libpq switches it on by default anyway.
SOCKET_OPTION_NAMES = {
    "keepalives_idle": "TCP_KEEPIDLE",
    "keepalives_interval": "TCP_KEEPINTVL",
    "keepalives_count": "TCP_KEEPCNT",
    "tcp_user_timeout": "TCP_USER_TIMEOUT",
}


def usable_socket_options(wanted: dict, make_socket=socket.socket) -> dict:
    """The options of `wanted` that this system accepts.

    If the system knows an option but refuses it, libpq does not skip it but
    fails the whole connection. So each one is tried once on a socket that
    connects nowhere, and one that is refused is left out: the connection then
    works as before S-211, only without that option. Never raises.
    """
    usable = dict(wanted)
    try:
        probe = make_socket(socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        return usable
    try:
        for option, name in SOCKET_OPTION_NAMES.items():
            constant = getattr(socket, name, None)
            if option not in usable or constant is None:
                continue  # not known to Python here: left to libpq, which skips what the system lacks
            try:
                probe.setsockopt(socket.IPPROTO_TCP, constant, usable[option])
            except OSError:
                logger.warning("The socket option %s is not available here and is left out", option)
                del usable[option]
    finally:
        probe.close()
    return usable


# Worked out once, when the server starts.
SOCKET_OPTIONS = usable_socket_options(WANTED_SOCKET_OPTIONS)
# The socket options do not help when the server is reachable but stuck: its
# computer still answers, only no reply comes. After this many seconds a call
# is cut off from outside (see `CallDeadline`). A healthy call takes well
# under a second; every statement in it is limited to 5 seconds anyway.
CALL_DEADLINE_SECONDS = 10

CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS accounts (
        name_key TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
"""
# On Supabase, tables in the `public` schema can be reached through the
# project's Data API with the public "anon" key. With row level security on
# and no policy, the roles of that API see no rows and can change none. Our
# server connects as the owner of the table, and the owner is not held back
# by row level security, so it still reads and writes. Safe to repeat.
ENABLE_ROW_LEVEL_SECURITY = "ALTER TABLE accounts ENABLE ROW LEVEL SECURITY"
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


class CallDeadline:
    """Cuts off one call to the database if it is not over after `seconds`.

    A timer thread shuts down the connection's socket. The worker thread that
    waits for the answer then sees the connection closed and gets a
    `psycopg.OperationalError`, which the stores turn into `StoreUnavailable`
    like any other database problem. So a stuck database holds a worker
    thread for at most these seconds, not for good.

    The timer works on its own duplicate of the socket, never on libpq's
    number for it: once libpq has closed its socket, that number may already
    belong to another connection. Shutting down the duplicate ends the one
    connection both refer to, and nothing else.

    Call `stop()` when the call is over, also when it failed. If the duplicate
    cannot be made, the call runs without a deadline, as before S-211.
    """

    def __init__(self, connection, seconds=None):
        self._lock = threading.Lock()
        self._socket = duplicate_socket(connection)
        # Read here, not when the class is defined, so the tests can shorten it.
        self._seconds = CALL_DEADLINE_SECONDS if seconds is None else seconds
        self._timer = threading.Timer(self._seconds, self._cut_off)
        # A waiting timer must never keep the server from stopping.
        self._timer.daemon = True
        if self._socket is not None:
            self._timer.start()

    def _cut_off(self):
        # The lock keeps `stop` from closing the duplicate in the middle of this.
        with self._lock:
            if self._socket is None:
                return  # the call was over just before
            logger.warning("A database call took longer than %s seconds and was cut off", self._seconds)
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # the connection had closed already

    def stop(self):
        """The call is over: the deadline will not cut anything off any more."""
        self._timer.cancel()
        with self._lock:
            if self._socket is not None:
                self._socket.close()
                self._socket = None


def duplicate_socket(connection):
    """A duplicate of the connection's socket, or None if it cannot be made.

    Never raises: a problem here must not stop a call that would have worked.
    """
    try:
        return socket.socket(fileno=socket.dup(connection.pgconn.socket))
    except Exception:
        return None


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
        # The store is called from several worker threads. The lock makes sure
        # only one of them creates the table.
        self._table_lock = threading.Lock()

    def add(self, name: str, password_hash: str) -> bool:
        connection, deadline = self._connect()
        try:
            with connection:
                connection.execute(SET_STATEMENT_TIMEOUT)
                cursor = connection.execute(INSERT_ACCOUNT, (name_key(name), name, password_hash))
                # No row was inserted when the name already existed.
                return cursor.rowcount == 1
        except psycopg.Error as problem:
            raise self._unavailable("query", problem) from None
        finally:
            deadline.stop()

    def find(self, name: str):
        connection, deadline = self._connect()
        try:
            with connection:
                connection.execute(SET_STATEMENT_TIMEOUT)
                row = connection.execute(SELECT_ACCOUNT, (name_key(name),)).fetchone()
        except psycopg.Error as problem:
            raise self._unavailable("query", problem) from None
        finally:
            deadline.stop()
        if row is None:
            return None
        return (row[0], row[1])

    def _connect(self):
        """Open a connection, with the table `accounts` in place.

        Returns `(connection, deadline)`. The connection is used as `with
        connection:`, which saves the changes and closes it at the end; the
        deadline (see `CallDeadline`) must be stopped after that. Raises
        `StoreUnavailable` when connecting or creating the table fails; the
        log then says which of the two it was.
        """
        try:
            connection = psycopg.connect(
                self._database_url,
                connect_timeout=CONNECT_TIMEOUT_SECONDS,
                # Supabase's connection pooler does not support prepared statements.
                prepare_threshold=None,
                **SOCKET_OPTIONS,
            )
        # UnicodeError is not a psycopg error: Python raises it itself when the
        # host in the URL cannot be a host name (for example "db..example.com",
        # or a part longer than 63 letters). Without catching it here, a typing
        # mistake in the URL would not become StoreUnavailable.
        except (psycopg.Error, UnicodeError) as problem:
            raise self._unavailable("connect", problem) from None
        # Started before the table is created: that can hang as well, and
        # meanwhile it holds the lock every other worker waits for.
        deadline = CallDeadline(connection)
        try:
            self._create_table_once(connection)
        except psycopg.Error as problem:
            connection.close()
            deadline.stop()
            raise self._unavailable("create table", problem) from None
        return connection, deadline

    def _create_table_once(self, connection):
        """Create and protect the table `accounts` if this store has not done so yet."""
        with self._table_lock:
            if self._table_exists:
                return
            connection.execute(SET_STATEMENT_TIMEOUT)
            connection.execute(CREATE_TABLE)
            connection.execute(ENABLE_ROW_LEVEL_SECURITY)
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
