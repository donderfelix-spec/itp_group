"""Who is sent whose position: the hiding spots (S-62, M3-1.4).

Plain functions: no network, no clock. The server leaves a hidden player out
of the `positions` message, so a browser far away never learns where that
player is. Positions outside the reveal range are never transmitted.

Only a living Free Rider hides (S-132), and only during a Classic round
(S-131). Everybody else is sent as anywhere on the map.
"""

from math import hypot

# The phases of a Classic round in which a Free Rider may be hidden from
# others. Since M3-1.6 (S-191) a meeting ends hiding, so in practice nobody
# is hidden in the phase "meeting"; who hides is `ClassicRound.hidden`.
HIDING_PHASES = ("round", "meeting")

# How close a viewer must be to see a hidden player, in map units, when the
# map does not say (`hide_reveal_range` in campus.json, which says 35, S-133).
DEFAULT_REVEAL_RANGE = 35


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
