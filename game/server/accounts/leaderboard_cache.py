"""The last answer of the store for the leaderboard, kept for a few seconds.

Every look at the leaderboard would otherwise open a connection to the
database. With the cache, many players looking at once cost one question.

A plain class without a clock (rule 4): the time `now` is passed in, in
seconds, so tests can control it.
"""

# How long an answer is served before the store is asked again.
KEEP_SECONDS = 10


class LeaderboardCache:
    def __init__(self):
        self._answer = None
        self._source = None
        self._stored_at = None
        # Counts the drops. An answer that was asked for before a drop is
        # older than the result that caused the drop, so `put` refuses it.
        self._drops = 0

    def get(self, source, now: float):
        """The kept answer of this `source`, or None when there is none or it is too old.

        `source` is the store the answer came from. The server's store can
        be replaced (the tests do that), and an answer of another store
        must never be served.
        """
        if self._answer is None or self._source is not source:
            return None
        if now - self._stored_at >= KEEP_SECONDS:
            return None
        return self._answer

    def ticket(self) -> int:
        """Taken before the store is asked and handed to `put` with its answer."""
        return self._drops

    def put(self, source, answer, now: float, ticket: int) -> bool:
        """Keep the answer. Returns False, and keeps nothing, if the cache was dropped since `ticket`."""
        if ticket != self._drops:
            return False
        self._answer = answer
        self._source = source
        self._stored_at = now
        return True

    def drop(self):
        """Forget the answer: the numbers have changed."""
        self._answer = None
        self._source = None
        self._stored_at = None
        self._drops += 1
