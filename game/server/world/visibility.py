"""Server-side hiding rules. Positions outside reveal range are never transmitted."""

from math import hypot


def hiding_spot(campus, x, y):
    """Return the hiding circle containing the player centre, including its edge."""
    return next(
        (spot for spot in campus.get("hiding_spots", [])
         if hypot(x - spot["x"], y - spot["y"]) <= spot["r"]),
        None,
    )


def visible_positions(positions, viewer, campus):
    """Keep the viewer and reveal hidden players only within the map's reveal range."""
    own = next((entry for entry in positions if entry[0] == viewer), None)
    if own is None:
        return []
    reveal_range = campus.get("hide_reveal_range", 35)
    return [
        entry for entry in positions
        if entry[0] == viewer
        or hiding_spot(campus, entry[1], entry[2]) is None
        or hypot(entry[1] - own[1], entry[2] - own[2]) <= reveal_range
    ]
