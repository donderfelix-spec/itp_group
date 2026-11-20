"""Decides which of many equal faults is worth a line in the log.

The tick runs many times per second. A lobby that fails on every tick would
write a log line every time and flood the log. So the same fault is logged at
once the first time, and after that at most once per QUIET_SECONDS, together
with the number of times it happened in between.

No logging, no clock and no network in here: the caller passes the time in and
writes the log line itself, so tests can control everything.
"""

# The same fault is logged at most once in this many seconds.
QUIET_SECONDS = 60


class RepeatedFaults:
    """Remembers, per fault, when it was last logged and how often it came back since."""

    def __init__(self):
        self._entries = {}  # key -> {"logged": seconds, "seen": seconds, "swallowed": count}

    def happened(self, key, now: float):
        """Note that the fault `key` happened at `now` (in seconds).

        Returns `(log_it, swallowed)`. `log_it` says whether the caller should
        write a log line. `swallowed` is the number of times this fault
        happened without a line since the last line (0 for a first line).
        `key` says which fault it is, for example `(place, lobby code)`.
        """
        self._forget_quiet_faults(now)
        entry = self._entries.get(key)
        if entry is None:
            self._entries[key] = {"logged": now, "seen": now, "swallowed": 0}
            return True, 0
        entry["seen"] = now
        if now - entry["logged"] < QUIET_SECONDS:
            entry["swallowed"] += 1
            return False, 0
        swallowed = entry["swallowed"]
        entry["logged"] = now
        entry["swallowed"] = 0
        return True, swallowed

    def remembered(self) -> int:
        """How many faults are remembered right now."""
        return len(self._entries)

    def _forget_quiet_faults(self, now: float):
        """Drop every fault that has not happened for longer than QUIET_SECONDS.

        Without this the entries of closed lobbies would pile up for ever. A
        forgotten fault that comes back is logged at once, like a new one.
        """
        quiet = [key for key, entry in self._entries.items() if now - entry["seen"] > QUIET_SECONDS]
        for key in quiet:
            del self._entries[key]
