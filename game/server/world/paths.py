"""How far a player has to walk between two places on the campus, as plain functions.

No network, no clock and no randomness in here. Duel needs these distances to
give every player a route of about the same length (S-94): the straight line
between two stations says little, because walls and doors lie in between.

How it is measured: a grid of points is laid over the map, GRID_STEP units
apart. A grid point is free if a player may stand on it, asked with the real
collision rule (`movement.is_free`, which knows the player's size). From a
free point a player can step to the eight points around it. The walking
distance is the shortest chain of such steps (Dijkstra's algorithm).

A path on a grid is a little longer than the real one, because it only knows
eight directions (at most 8 % longer). That is the same for every route, so
the routes can still be compared fairly.
"""

import heapq
import math

from server.world.movement import PLAYER_HALF_SIZE, is_free

# The distance between two grid points. A way is never missed as long as it
# leaves a player at least 4 units of room to the sides, because then a grid
# line runs through it. Every door and every aisle that leads somewhere on the
# map does (the narrowest, beside the benches of the Lecture Hall, leaves 7).
# With 2 units the distances differ by less than 3 %, but measuring takes four
# times as long (about 1.5 seconds instead of 0.3 when the server starts).
GRID_STEP = 4

# The name of the spawn point in the table of `station_distances`.
SPAWN = "spawn"

STRAIGHT_STEPS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
DIAGONAL_STEPS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]


class PathError(ValueError):
    """A place on the map cannot be stood on or cannot be walked to."""


class Grid:
    """The grid over one map. Remembers which points are free, so each is asked only once."""

    def __init__(self, solids, width, height):
        self._solids = solids
        self._width = width
        self._height = height
        self._free = {}  # (column, row) -> whether a player may stand there
        self._neighbours = {}  # (column, row) -> the answer of `neighbours`
        self._solids_of_row = {}  # row -> the solids a player in that row could touch

    def is_free(self, point) -> bool:
        if point not in self._free:
            x, y = point[0] * GRID_STEP, point[1] * GRID_STEP
            self._free[point] = is_free(x, y, self._solids_near_row(point[1]), self._width, self._height)
        return self._free[point]

    def _solids_near_row(self, row) -> list:
        """The solids a player standing anywhere in this row of the grid could overlap.

        Asking `is_free` about these few gives the same answer as asking it
        about all solids, and is several times faster: most solids lie far
        above or below the row.
        """
        if row not in self._solids_of_row:
            y = row * GRID_STEP
            self._solids_of_row[row] = [
                solid for solid in self._solids
                if solid["y"] < y + PLAYER_HALF_SIZE and solid["y"] + solid["h"] > y - PLAYER_HALF_SIZE
            ]
        return self._solids_of_row[row]

    def neighbours(self, point) -> list:
        """The free points one step away, each with the length of that step."""
        if point not in self._neighbours:
            self._neighbours[point] = self._find_neighbours(point)
        return self._neighbours[point]

    def _find_neighbours(self, point) -> list:
        column, row = point
        found = []
        for dx, dy in STRAIGHT_STEPS:
            if self.is_free((column + dx, row + dy)):
                found.append(((column + dx, row + dy), GRID_STEP))
        for dx, dy in DIAGONAL_STEPS:
            # No cutting through a corner: a diagonal step counts only if the
            # player could also walk it as two straight steps, either way round.
            way_is_clear = self.is_free((column + dx, row)) and self.is_free((column, row + dy))
            if way_is_clear and self.is_free((column + dx, row + dy)):
                found.append(((column + dx, row + dy), GRID_STEP * math.sqrt(2)))
        return found

    def nearest_free_point(self, x, y, within):
        """The free grid point closest to `(x, y)` and at most `within` units away, or None.

        If two are equally close, the one further up and then further left is
        taken, so the answer is never random.
        """
        reach = math.ceil(within / GRID_STEP) + 1
        middle = (round(x / GRID_STEP), round(y / GRID_STEP))
        best = None
        for column in range(middle[0] - reach, middle[0] + reach + 1):
            for row in range(middle[1] - reach, middle[1] + reach + 1):
                distance = math.hypot(column * GRID_STEP - x, row * GRID_STEP - y)
                if distance > within or not self.is_free((column, row)):
                    continue
                candidate = (distance, row, column)
                if best is None or candidate < best:
                    best = candidate
        return None if best is None else (best[2], best[1])

    def distances_from(self, start) -> dict:
        """The walking distance from `start` to every grid point that can be reached."""
        distance_to = {start: 0.0}
        waiting = [(0.0, start)]  # a heap: the closest point comes out first
        while waiting:
            distance, point = heapq.heappop(waiting)
            if distance > distance_to[point]:
                continue  # an old entry: a shorter way to this point was found later
            for neighbour, step_length in self.neighbours(point):
                new_distance = distance + step_length
                if new_distance < distance_to.get(neighbour, math.inf):
                    distance_to[neighbour] = new_distance
                    heapq.heappush(waiting, (new_distance, neighbour))
        return distance_to


def walking_distances(places, solids, width, height) -> dict:
    """The walking distance between every two of `places`.

    `places` is a dict name -> `(x, y, within)`: the place counts as reached
    at the free grid point closest to `(x, y)` that is at most `within` units
    away. For a station `within` is its use range: that point is where a
    player can open it from.

    Returns a dict `(name, other_name) -> distance` with both orders of every
    pair. The distance is None if there is no way between the two, or if one
    of them has no free point at all.
    """
    grid = Grid(solids, width, height)
    points = {name: grid.nearest_free_point(x, y, within) for name, (x, y, within) in places.items()}
    distances = {}
    for name, start in points.items():
        reached = {} if start is None else grid.distances_from(start)
        for other_name, goal in points.items():
            if other_name != name:
                distances[(name, other_name)] = reached.get(goal)
    return distances


def station_distances(campus, station_ids) -> dict:
    """The walking distances Duel needs: between the spawn and these stations and between the stations.

    `campus` is the checked map from `load_campus`. The keys are pairs like
    `(SPAWN, 3)` and `(3, 5)`. Raises `PathError` if a station cannot be
    walked to: a Duel with such a station could never be finished.
    """
    stations = {station["id"]: station for station in campus["stations"]}
    # The spawn is a point, not a circle like a station's range. One grid
    # step around it is allowed, for a spawn that lies between grid points.
    places = {SPAWN: (campus["spawn"]["x"], campus["spawn"]["y"], GRID_STEP)}
    for station_id in station_ids:
        if station_id not in stations:
            raise PathError(f"Station {station_id} is not on the map.")
        station = stations[station_id]
        places[station_id] = (station["x"], station["y"], campus["use_range"])
    distances = walking_distances(places, campus["solids"], campus["width"], campus["height"])
    for (start, goal), distance in distances.items():
        if distance is None:
            raise PathError(f"There is no way from {start} to {goal} on the map.")
    return distances
