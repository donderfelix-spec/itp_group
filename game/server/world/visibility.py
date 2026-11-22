"""Who is sent whose position: the hiding spots (S-62, M3-1.4).

Plain functions: no network, no clock. The server leaves a hidden player out
of the `positions` message, so a living High Performer never learns where
that player is, however near (S-192; the reveal range of 35 is gone).
Those who may still see him (himself, the other Free Riders, ghosts) are
told that he hides (`told_hidden`), so their pages draw him as hidden.

Only a living Free Rider hides (S-132), and only during a Classic round
(S-131). Everybody else is sent as anywhere on the map.
"""

from math import hypot

# The phases of a Classic round in which a Free Rider may be hidden from
# others. Since M3-1.6 (S-191) a meeting ends hiding, so in practice nobody
# is hidden in the phase "meeting"; who hides is `ClassicRound.hidden`.
HIDING_PHASES = ("round", "meeting")


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
