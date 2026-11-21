"""The rules of Duel (S-56, S-94): routes, progress, the end of the round and the ranking.

These are the rules only: no network, no clock and no randomness in here.
The server passes in the time `now` (in seconds) and a random generator,
tests pass their own.

Every player gets a route of three different stations and has to finish them
in that order. Whoever finishes first wins. The round is over when everybody
still in it has finished, or after ROUND_SECONDS.
"""

import itertools
import math
from collections import Counter

from server.world.paths import SPAWN

# How many stations a player has to finish.
STATIONS_PER_ROUTE = 3

# How long a round lasts at most (DESIGN.md, section 6).
ROUND_SECONDS = 180

# How much the walking distance of the other players' routes may differ from
# the first route that was drawn: 10 % (S-94).
LENGTH_TOLERANCE = 0.10


# Routes


def all_routes(stations_in_use) -> list:
    """Every way to visit three different stations in an order: 60 routes for five stations."""
    return list(itertools.permutations(stations_in_use, STATIONS_PER_ROUTE))


def route_length(route, distances) -> float:
    """The walking distance from the spawn over the stations of the route, in order.

    `distances` is the table of `paths.station_distances`.
    """
    length = distances[(SPAWN, route[0])]
    for station, next_station in zip(route, route[1:]):
        length += distances[(station, next_station)]
    return length


def draw_routes(names, stations_in_use, distances, rng) -> dict:
    """Draw a route for every player. Returns `{name: (first, second, third)}`.

    One route is drawn at random. Then the other routes are added one at a
    time, and each new route must follow these rules, in this order:

    1. No two players get the same route, as long as there are routes left.
    2. The first stations are all different as long as there are stations
       left; after that they are spread as evenly as possible.
    3. Its length is within 10 % of the first route where possible,
       otherwise the nearest in length (see `routes_about_as_long`).
       The first route is drawn so that this is possible wherever it can
       be (see `draw_first_route`).

    Which player gets which route is random as well. Never raises for any
    number of players, as long as there are at least three stations.
    """
    if len(names) == 0:
        return {}
    candidates = all_routes(stations_in_use)
    first = draw_first_route(candidates, distances, len(names), rng)
    routes = [first]
    while len(routes) < len(names):
        routes.append(next_route(first, routes, candidates, distances, rng))
    rng.shuffle(routes)
    return dict(zip(names, routes))


def draw_first_route(candidates, distances, player_count, rng):
    """The route the others are measured against, drawn at random.

    A route that has too few routes within 10 % starting at other stations
    is put aside and another one is drawn: with it, rule 2 of `draw_routes`
    would push some players onto much longer or shorter ways. If every
    route is like that, the first one drawn is kept.
    """
    station_count = len({route[0] for route in candidates})
    other_starts_needed = min(player_count, station_count) - 1
    first_drawn = rng.choice(candidates)
    left = list(candidates)
    first = first_drawn
    while not has_close_routes_from_other_starts(first, candidates, distances, other_starts_needed):
        left.remove(first)
        if not left:
            return first_drawn
        first = rng.choice(left)
    return first


def has_close_routes_from_other_starts(first, candidates, distances, count) -> bool:
    """Whether at least `count` other first stations have a route within 10 % of `first`."""
    wanted = route_length(first, distances)
    close_starts = {
        route[0]
        for route in candidates
        if route[0] != first[0] and abs(route_length(route, distances) - wanted) <= LENGTH_TOLERANCE * wanted
    }
    return len(close_starts) >= count


def next_route(first, routes, candidates, distances, rng):
    """One more route for `draw_routes`, chosen from the least used ones."""
    allowed = least_used(routes, candidates)
    about_as_long = routes_about_as_long(first, allowed, distances, 1, rng)
    # Empty only if `first` itself is the one route left to give again.
    return about_as_long[0] if about_as_long else allowed[0]


def least_used(routes, candidates) -> list:
    """The candidates that were given least often, and of those the ones whose first station was used least.

    A route is only given twice when every route was given once, and a
    first station only twice when every station was a first station once.
    The order of `candidates` is kept, so nothing here depends on chance.
    """
    route_uses = Counter(routes)
    start_uses = Counter(route[0] for route in routes)

    def uses(route):
        return (route_uses[route], start_uses[route[0]])

    fewest = min(uses(route) for route in candidates)
    return [route for route in candidates if uses(route) == fewest]


def routes_about_as_long(first, candidates, distances, count, rng) -> list:
    """`count` routes other than `first` whose length is close to the length of `first`.

    They are drawn at random from the routes within LENGTH_TOLERANCE. If
    there are fewer of those than needed, the nearest ones in length are
    taken instead, however far away they are.
    """
    wanted = route_length(first, distances)

    def difference(route):
        return abs(route_length(route, distances) - wanted)

    others = [route for route in candidates if route != first]
    close = [route for route in others if difference(route) <= LENGTH_TOLERANCE * wanted]
    if len(close) >= count:
        return rng.sample(close, count)
    # `sorted` keeps routes of the same difference in the order of
    # `candidates`, so this choice is never random.
    return sorted(others, key=difference)[:count]


# One round


class DuelPlayer:
    """One player in one Duel."""

    def __init__(self, route):
        self.route = route
        # How many stations of the route are finished: 0 to 3.
        self.done = 0
        # From the start of the round to the third station, or None.
        self.seconds = None


class Duel:
    def __init__(self, routes: dict, started: float):
        """`routes` comes from `draw_routes`, `started` is the time the round began."""
        # name -> DuelPlayer, in the order of `routes`: the joining order.
        self._players = {name: DuelPlayer(route) for name, route in routes.items()}
        self._started = started
        # Whether the progress changed since the server last told everybody.
        self._has_news = False

    def names(self) -> list:
        """The players still in the Duel, in joining order."""
        return list(self._players)

    def next_station(self, name: str):
        """The station the player has to go to now, or None after the last one."""
        player = self._players.get(name)
        if player is None or player.done >= len(player.route):
            return None
        return player.route[player.done]

    def stations_needed(self, name: str, finished=None, in_use=None) -> list:
        """For the frame of the minigames (`RoundTasks`): only the next station can be opened.

        `finished` and `in_use` are what the frame passes to every such
        function. Duel does not need them: it keeps its own count.
        """
        station = self.next_station(name)
        return [] if station is None else [station]

    def station_done(self, name: str, station: int, now: float) -> bool:
        """The player finished the task at `station`. Returns whether it counted.

        Only the next station of the player's route counts. With the third
        one the player's time is set, once and for good.
        """
        if station is None or station != self.next_station(name):
            return False
        player = self._players[name]
        player.done += 1
        if player.done == len(player.route):
            player.seconds = now - self._started
        self._has_news = True
        return True

    def take_back(self, name: str, station: int):
        """Undo `station_done` for the station that was counted last.

        The server calls this when something failed right after the count,
        before the player could be told: then the station does not count
        after all and the player can play it again.
        """
        player = self._players.get(name)
        if player is None or player.done == 0 or player.route[player.done - 1] != station:
            return
        player.done -= 1
        player.seconds = None
        self._has_news = True

    def remove(self, name: str):
        """A player who leaves is taken out: no progress, no place in the ranking."""
        if self._players.pop(name, None) is not None:
            self._has_news = True

    def state_of(self, name: str) -> tuple:
        """What one player may know about their own Duel: `(next_station, done, seconds)`."""
        player = self._players[name]
        return (self.next_station(name), player.done, _shown(player.seconds))

    def progress(self) -> list:
        """(name, done) pairs in joining order: what everybody may know about everybody."""
        return [(name, player.done) for name, player in self._players.items()]

    def take_news(self) -> bool:
        """Whether the progress changed since this was last asked. Asking clears it."""
        had_news = self._has_news
        self._has_news = False
        return had_news

    def time_is_up(self, now: float) -> bool:
        return now - self._started >= ROUND_SECONDS

    def everybody_finished(self) -> bool:
        """Whether every player still in the Duel has finished. True as well if nobody is left."""
        return all(player.seconds is not None for player in self._players.values())

    def is_over(self, now: float) -> bool:
        """Everybody still in the Duel has finished, or the time is up.

        A Duel that everybody has left is over as well.
        """
        return self.everybody_finished() or self.time_is_up(now)

    def seconds_left(self, now: float) -> int:
        """Whole seconds until the time is up, rounded up, never below 0."""
        return max(0, math.ceil(ROUND_SECONDS - (now - self._started)))

    def ranking(self) -> list:
        """The rows of the ranking, best first (S-94).

        Each row is a dict with "place", "name", "seconds" (None if the
        player did not finish) and "done". Players who finished come first,
        by time. Then the others, by stations done. Equal results share a
        place and the next place is skipped (1, 2, 2, 4); among them the
        joining order is kept.
        """
        rows = [
            {"name": name, "seconds": _shown(player.seconds), "done": player.done}
            for name, player in self._players.items()
        ]
        # `sorted` keeps rows with the same result in their order, which is the joining order.
        rows = sorted(rows, key=_result)
        for index, row in enumerate(rows):
            shares_place = index > 0 and _result(row) == _result(rows[index - 1])
            row["place"] = rows[index - 1]["place"] if shares_place else index + 1
        return rows


def _shown(seconds):
    """A time as it is shown and compared: one decimal. None stays None."""
    return None if seconds is None else round(seconds, 1)


def _result(row) -> tuple:
    """What the ranking sorts by: smaller is better."""
    if row["seconds"] is not None:
        return (0, row["seconds"])
    # Not finished: after everybody who did, and more stations done is better.
    return (1, -row["done"])
