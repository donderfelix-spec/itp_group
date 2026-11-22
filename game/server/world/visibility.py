"""Who is sent whose position: line of sight and hiding spots.

Plain functions: no network, no clock. The server leaves a player out of the
`positions` message when he is outside the viewer's sight (S-185) or hidden
from him (S-133), so a browser never learns where that player is.

Limited vision applies to living Classic players. The hiding-spot rules
additionally conceal a living Free Rider from distant High Performers.
"""

from math import hypot

# The phases of a Classic round in which the Free Rider can hide. A meeting
# does not reveal him: whoever hid when it started stays hidden (S-138).
HIDING_PHASES = ("round", "meeting")

# How close a viewer must be to see a hidden player, in map units, when the
# map does not say (`hide_reveal_range` in campus.json, which says 35, S-133).
DEFAULT_REVEAL_RANGE = 35
DEFAULT_VISION_RANGE = 120


def _wall_blocks(start, end, wall):
    """Intersect the open sight segment with the solid wall rectangle."""
    near, far = 0.0, 1.0
    for origin, target, edge, size in zip(
        start, end, (wall["x"], wall["y"]), (wall["w"], wall["h"])
    ):
        delta = target - origin
        if delta == 0:
            if not edge <= origin <= edge + size:
                return False
            continue
        first = (edge - origin) / delta
        last = (edge + size - origin) / delta
        near = max(near, min(first, last))
        far = min(far, max(first, last))
        if near > far:
            return False
    return near < 1 and far > 0


def positions_in_sight(positions, viewer, campus):
    """Keep the viewer and nearby players visible through clear space."""
    own = next((entry for entry in positions if entry[0] == viewer), None)
    if own is None:
        return []
    _, x, y = own
    origin = (x, y)
    vision_range = campus.get("classic_vision_range", DEFAULT_VISION_RANGE)
    walls = [solid for solid in campus["solids"] if solid["kind"] == "wall"]
    return [
        entry
        for entry in positions
        if entry[0] == viewer or (
            hypot(entry[1] - x, entry[2] - y) <= vision_range
            and not any(_wall_blocks(origin, entry[1:], wall) for wall in walls)
        )
    ]


def hiding_spot(campus, x, y):
    """Return the hiding circle containing the player centre, including its edge."""
    return next(
        (spot for spot in campus.get("hiding_spots", [])
         if hypot(x - spot["x"], y - spot["y"]) <= spot["r"]),
        None,
    )


def players_who_hide_from(viewer, roles, ghosts, phase) -> set:
    """The players who are hidden from `viewer` while they stand in a hiding spot.

    `roles` maps each player of the Classic round to "HP" or "FR", `ghosts`
    are the players who failed or were voted out, `phase` is the round's phase.
    Only living Free Riders hide. A ghost sees everybody (S-136), and a Free
    Rider sees the other Free Riders, because Free Riders know each other
    (S-137).
    """
    if phase not in HIDING_PHASES:
        return set()
    if viewer in ghosts or roles.get(viewer) == "FR":
        return set()
    return {
        name for name, role in roles.items()
        if role == "FR" and name not in ghosts and name != viewer
    }


def visible_positions(positions, viewer, campus, hiders):
    """The entries of `positions` that may be sent to `viewer`.

    `positions` are (name, x, y) triples. A player in `hiders` who stands in
    a hiding spot is left out, unless the viewer is within the map's reveal
    range of him (centre to centre, the range itself included). The viewer
    always gets its own position. The list given is not changed.
    """
    if not hiders:
        return list(positions)
    own = next((entry for entry in positions if entry[0] == viewer), None)
    reveal_range = campus.get("hide_reveal_range", DEFAULT_REVEAL_RANGE)
    return [
        entry for entry in positions
        if not _is_hidden(entry, own, campus, hiders, reveal_range)
    ]


def _is_hidden(entry, own, campus, hiders, reveal_range) -> bool:
    name, x, y = entry
    if name not in hiders or hiding_spot(campus, x, y) is None:
        return False
    if own is None:
        # A viewer without a position yet cannot be close to anybody.
        return True
    return hypot(x - own[1], y - own[2]) > reveal_range
