"""A limit on guessing passwords and lobby codes (M1-2.6).

Each connection may fail only so often within a minute. After that, further
attempts of the same kind are refused until the oldest of those failures is
more than a minute old (a sliding window).

Two details matter:

- A refused attempt is not counted. Otherwise a script that keeps trying
  would lock its connection out for ever.
- A success does not clear the count. Otherwise one known account (or one
  known lobby) could be used to reset the limit while guessing others.

This is a plain class without any network and without a clock: the time is
passed in as `now`, in seconds. A "connection" can be any object that works
as a dict key: the server passes its WebSocket, tests pass strings.
"""

LOG_IN_FAILURES_ALLOWED = 5
LOG_IN_WINDOW_SECONDS = 60
JOIN_LOBBY_FAILURES_ALLOWED = 10
JOIN_LOBBY_WINDOW_SECONDS = 60

# kind -> (failures allowed, window in seconds)
LIMITS = {
    "log_in": (LOG_IN_FAILURES_ALLOWED, LOG_IN_WINDOW_SECONDS),
    "join_lobby": (JOIN_LOBBY_FAILURES_ALLOWED, JOIN_LOBBY_WINDOW_SECONDS),
}


class AttemptLimits:
    def __init__(self):
        self._failures = {}  # connection -> {kind: [times of the failures, oldest first]}

    def is_blocked(self, connection, kind: str, now: float) -> bool:
        """Whether a new attempt of this kind must be refused at the time `now`."""
        allowed, window = LIMITS[kind]
        return len(self._recent_failures(connection, kind, now)) >= allowed

    def failed(self, connection, kind: str, now: float):
        """Remember one failed attempt. Call it only for attempts that were not refused."""
        allowed, window = LIMITS[kind]
        recent = self._recent_failures(connection, kind, now)
        recent.append(now)
        # More than `allowed` times are never needed to decide, so the list
        # stays short whatever the caller does.
        self._failures.setdefault(connection, {})[kind] = recent[-allowed:]

    def forget(self, connection):
        """Drop everything about a connection. Called when it closes, so nothing grows for ever."""
        self._failures.pop(connection, None)

    def knows(self, connection) -> bool:
        """Whether anything is stored about this connection."""
        return connection in self._failures

    def count(self) -> int:
        """How many connections have something stored."""
        return len(self._failures)

    def _recent_failures(self, connection, kind: str, now: float) -> list:
        """The failures that still count: those at most one window old."""
        allowed, window = LIMITS[kind]
        times = self._failures.get(connection, {}).get(kind, [])
        return [time for time in times if now - time <= window]
