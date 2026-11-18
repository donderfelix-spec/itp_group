"""The rules for walking on the campus, as plain functions.

No network and no clock in here: the time since the last step and the list of
solids are passed in, so tests can control them.

A player is a small square. A solid is a rectangle `{"x", "y", "w", "h"}`
from the map file (walls, furniture, the pool, ...). A player may touch a
solid but never overlap it.
"""

import math

# The player is a square of 10 x 10 units around its position.
PLAYER_HALF_SIZE = 5

# Units of the map per second, the same in every direction.
PLAYER_SPEED = 90

# The longest time one step may cover. Without it, a player whose connection
# paused for a few seconds would jump a long way in a single step.
MAX_STEP_SECONDS = 0.1


def step(x, y, dx, dy, seconds, solids, map_width, map_height):
    """Move a player for `seconds` and return the new position `(x, y)`.

    `dx` and `dy` say where the player wants to go: -1, 0 or 1 on each axis.
    The player stops at solids and at the edge of the map.
    """
    if not (_is_finite_number(x) and _is_finite_number(y)):
        raise ValueError("A player's position must be two finite numbers.")

    # A player should never be inside a solid. If it happens anyway (a wrong
    # spawn point, a teleport), that solid does not block this step, so the
    # player can walk out instead of being stuck forever.
    solids = [solid for solid in solids if not overlaps(x, y, solid)]

    dx = _direction(dx)
    dy = _direction(dy)
    distance = PLAYER_SPEED * _capped(seconds)
    if dx != 0 and dy != 0:
        # A diagonal step is split over both axes so that it is not faster
        # than a straight one (Pythagoras: side = diagonal / sqrt(2)).
        distance = distance / math.sqrt(2)

    # One axis after the other: when a wall blocks one axis, the other axis
    # still moves, so the player slides along the wall instead of sticking.
    x = _move_on_axis("x", x, y, dx, distance, solids, map_width)
    y = _move_on_axis("y", y, x, dy, distance, solids, map_height)
    return x, y


def overlaps(x, y, solid) -> bool:
    """Does the player square at `(x, y)` overlap this solid? Touching is not overlapping."""
    return (
        x + PLAYER_HALF_SIZE > solid["x"]
        and x - PLAYER_HALF_SIZE < solid["x"] + solid["w"]
        and y + PLAYER_HALF_SIZE > solid["y"]
        and y - PLAYER_HALF_SIZE < solid["y"] + solid["h"]
    )


def is_free(x, y, solids, map_width, map_height) -> bool:
    """Is the player square at `(x, y)` inside the map and clear of every solid?"""
    inside_map = (
        PLAYER_HALF_SIZE <= x <= map_width - PLAYER_HALF_SIZE
        and PLAYER_HALF_SIZE <= y <= map_height - PLAYER_HALF_SIZE
    )
    return inside_map and not any(overlaps(x, y, solid) for solid in solids)


def _is_finite_number(value) -> bool:
    """Is this an ordinary number: no text, no NaN, not infinite, not too large for a float?"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        # A whole number with hundreds of digits does not fit into a float.
        return False


def _direction(value):
    """Turn what the player wants into exactly -1, 0 or 1."""
    if not isinstance(value, (int, float)):
        return 0
    # Only comparisons here: they work for numbers of any size, and every
    # comparison with NaN is false, so NaN ends as 0.
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _capped(seconds):
    """The time this step may cover: never negative, never more than the cap."""
    if not isinstance(seconds, (int, float)):
        return 0
    # Written as "not above 0" so that NaN, which is not above anything, counts as no time.
    if not seconds > 0:
        return 0
    if seconds > MAX_STEP_SECONDS:
        return MAX_STEP_SECONDS
    return seconds


def _move_on_axis(axis, position, other_position, direction, distance, solids, map_size):
    """Move along one axis and stop at the first solid or at the edge of the map.

    `position` is the player's coordinate on the axis that moves,
    `other_position` the coordinate on the axis that stays.
    The step is shortened so that the player ends exactly touching the solid.
    """
    if direction == 0 or distance == 0:
        return position

    if axis == "x":
        along, length, across, breadth = "x", "w", "y", "h"
    else:
        along, length, across, breadth = "y", "h", "x", "w"

    # The lowest and highest coordinate the player's centre may have.
    lowest = PLAYER_HALF_SIZE
    highest = map_size - PLAYER_HALF_SIZE

    for solid in solids:
        # A solid that lies beside the player's lane cannot stop this move.
        beside = (
            solid[across] >= other_position + PLAYER_HALF_SIZE
            or solid[across] + solid[breadth] <= other_position - PLAYER_HALF_SIZE
        )
        if beside:
            continue
        near_side = solid[along]
        far_side = solid[along] + solid[length]
        # Only solids ahead of the player count, not those already behind.
        # (Solids the player overlapped at the start were removed in `step`.)
        if direction > 0 and far_side > position - PLAYER_HALF_SIZE:
            highest = min(highest, near_side - PLAYER_HALF_SIZE)
        if direction < 0 and near_side < position + PLAYER_HALF_SIZE:
            lowest = max(lowest, far_side + PLAYER_HALF_SIZE)

    # `max(position, ...)` and `min(position, ...)`: a blocked player stays
    # where they are and is never pushed backwards.
    if direction > 0:
        return max(position, min(position + distance, highest))
    return min(position, max(position - distance, lowest))
