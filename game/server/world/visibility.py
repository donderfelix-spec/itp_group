"""Who is sent whose position: line of sight and hiding spots.

Plain functions: no network, no clock. The server leaves a player out of the
`positions` message when he is outside the viewer's sight (S-185) or hidden
from him, so a browser never learns where that player is. A living High
Performer is never sent a hidden player, however near (S-192; the reveal
range of 35 is gone). Those who may still see him (himself, the other Free
Riders within their sight, ghosts) are told that he hides (`told_hidden`),
so their pages draw him as hidden.

Limited vision applies to living Classic players. The hiding-spot rules
additionally conceal a hiding Free Rider from every living High Performer.
"""

from math import hypot

# The phases of a Classic round in which a Free Rider may be hidden from
# others. Since M3-1.6 (S-191) a meeting ends hiding, so in practice nobody
# is hidden in the phase "meeting"; who hides is `ClassicRound.hidden`.
HIDING_PHASES = ("round", "meeting")

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
    """The players who are hidden from `viewer` while they hide.

    Since M3-1.6 (S-191) the server passes on only those of them who pressed
    E at a hiding object (`ClassicRound.hidden`).

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

    `positions` are (name, x, y) triples. A player in `hiders` (who hides
    from this viewer, see `players_who_hide_from`) is left out at any
    distance (S-192). The viewer always gets its own position. The list
    given is not changed. `campus` is not needed any more and kept so the
    callers stay as they are.
    """
    return [entry for entry in positions if entry[0] == viewer or entry[0] not in hiders]


def told_hidden(viewer, roles, ghosts, hidden) -> set:
    """The hidden players `viewer` is told are hidden (S-192).

    `hidden` are the players in the hidden state. Only the Free Riders
    (himself and the others, also as ghosts) and the ghosts are told; a
    living High Performer never, so no message to him carries the flag.
    """
    if viewer in ghosts or roles.get(viewer) == "FR":
        return set(hidden)
    return set()
