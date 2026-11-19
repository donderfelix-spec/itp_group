"""Who has which task open and who has finished which station, for one round.

These are the rules only (S-93): no network, no clock and no randomness in
here. The server passes in the time `now` (in seconds) and a random generator,
tests pass their own.

A lobby gets one `RoundTasks` object when its round starts. Before that it
has none (`None`), which is why the three functions at the bottom exist: the
server calls them with whatever the lobby holds, and they answer
"not_in_round" when there is no round.

Every action returns the rejection code as its last value: None when the
action was accepted, otherwise a key of `protocol.REJECTIONS`. A rejected
action changes nothing, with one exception that S-93 asks for: a task that is
reported as done too soon is closed.
"""

from server.modes import minigames as registry
from server.world.stations import station_in_range


class PlayerTasks:
    """The tasks of one player in one round."""

    def __init__(self):
        # The station whose minigame is open, or None. Never more than one.
        self.open_station = None
        # When it was opened, in the seconds of the server's clock.
        self.opened_at = None
        # The stations this player has finished in this round.
        self.finished = set()


def every_station_in_use(name: str, finished: set, in_use: list) -> list:
    """The default for `needed_stations`: a player needs every station in use."""
    return in_use


class RoundTasks:
    def __init__(self, stations, use_range, minigames=None, needed_stations=every_station_in_use):
        """`stations` and `use_range` come from the map (`load_campus`).

        `minigames` is the table station id -> `Minigame`; without it the
        real one from `minigames.py` is used.

        `needed_stations(name, finished, in_use)` returns the ids of the
        stations this player may open: a mode can restrict a player with it
        (Duel will allow only the next station of its order). `finished` is
        the set of stations the player has finished, `in_use` the ids of all
        stations in use. A finished station can never be opened again,
        whatever this function returns.
        """
        self._stations = stations
        self._use_range = use_range
        self._minigames = registry.MINIGAMES if minigames is None else minigames
        self._needed_stations = needed_stations
        self._players = {}  # name -> PlayerTasks

    def open(self, name: str, station: int, position, now: float, rng):
        """Open the minigame of a station. Returns `(opened, rejection_code)`.

        `position` is where the server has the player, as `(x, y)`, or None
        if the player has not been placed yet. `opened` is a dict with
        "station", "title" and the "content" drawn for this opening.
        """
        player = self._player(name)
        rejection_code = self._why_not_open(name, player, station, position)
        if rejection_code is not None:
            return (None, rejection_code)
        minigame = self._minigames[station]
        # Drawn before the task is remembered: if a minigame's function
        # fails, the player is not left with a task that never opened.
        content = minigame.make_content(rng)
        player.open_station = station
        player.opened_at = now
        return ({"station": station, "title": minigame.title, "content": content}, None)

    def close(self, name: str):
        """Close the open task without counting it. Returns `(station, rejection_code)`."""
        player = self._player(name)
        if player.open_station is None:
            return (None, "no_task_open")
        return (self._forget_open_task(player), None)

    def finish(self, name: str, now: float):
        """Report the open task as done. Returns `(station, rejection_code)`.

        After "too_fast" the station is returned too: the task is closed
        then, and the server tells the browser which window to close.
        """
        player = self._player(name)
        if player.open_station is None:
            return (None, "no_task_open")
        seconds_open = now - player.opened_at
        station = self._forget_open_task(player)
        # Exactly the minimum time is long enough.
        if seconds_open < self._minigames[station].min_seconds:
            return (station, "too_fast")
        player.finished.add(station)
        return (station, None)

    def has_open_task(self, name: str) -> bool:
        """While this is true, the player stands still (S-93)."""
        return self.open_station_of(name) is not None

    def open_station_of(self, name: str):
        """The station whose minigame the player has open, or None."""
        player = self._players.get(name)
        return None if player is None else player.open_station

    def finished_by(self, name: str) -> set:
        """The stations the player has finished in this round."""
        player = self._players.get(name)
        return set() if player is None else set(player.finished)

    def remove(self, name: str):
        """A player who leaves loses the open task and everything finished."""
        self._players.pop(name, None)

    def _why_not_open(self, name: str, player: PlayerTasks, station: int, position):
        """The rejection code for opening this station, or None. The order of the checks is fixed."""
        if station not in self._minigames:
            return "no_station"
        if not self._is_needed(name, player, station):
            return "station_not_needed"
        if player.open_station is not None:
            return "task_open"
        if not self._is_in_range(station, position):
            return "too_far"
        return None

    def _is_needed(self, name: str, player: PlayerTasks, station: int) -> bool:
        if station in player.finished:
            return False
        in_use = sorted(self._minigames)
        return station in self._needed_stations(name, set(player.finished), in_use)

    def _is_in_range(self, station: int, position) -> bool:
        if position is None:
            return False  # Not placed on the map yet: too far from everything.
        # Only this station is asked about. So a player who stands in range
        # of two stations may open either, not just the closer one.
        in_range = station_in_range(position[0], position[1], self._stations, self._use_range, [station])
        return in_range == station

    def _forget_open_task(self, player: PlayerTasks) -> int:
        station = player.open_station
        player.open_station = None
        player.opened_at = None
        return station

    def _player(self, name: str) -> PlayerTasks:
        # Made at the player's first action, so no list of names has to be
        # kept in step with the lobby.
        if name not in self._players:
            self._players[name] = PlayerTasks()
        return self._players[name]


# What the server calls. `tasks` is what the lobby holds: the `RoundTasks` of
# its running round, or None while no round is running.


def open_station(tasks, name: str, station: int, position, now: float, rng):
    """Like `RoundTasks.open`. Returns `(opened, rejection_code)`."""
    if tasks is None:
        return (None, "not_in_round")
    return tasks.open(name, station, position, now, rng)


def close_station(tasks, name: str):
    """Like `RoundTasks.close`. Returns `(station, rejection_code)`."""
    if tasks is None:
        return (None, "not_in_round")
    return tasks.close(name)


def finish_station(tasks, name: str, now: float):
    """Like `RoundTasks.finish`. Returns `(station, rejection_code)`."""
    if tasks is None:
        return (None, "not_in_round")
    return tasks.finish(name, now)


def stands_still(tasks, name: str) -> bool:
    """Whether the player may not walk right now, because a task is open."""
    return tasks is not None and tasks.has_open_task(name)
