"""Hiding with the key E (M3-1.6, S-191).

Plain functions: no network, no clock. A living Free Rider in a Classic
round who stands near a hiding object presses E to hide. The server keeps
who is hidden (`ClassicRound.hidden`); `server/world/visibility.py` then
leaves him out of the positions sent to distant High Performers.

Every rule Felix may still change has its own constant or function here:
- who may hide: `hide_refusal` (only a living Free Rider, only while the
  round is played, not in a meeting);
- how near the object he must stand: `HIDE_REACH_KEY` (the map's
  `use_range`, the reach of the stations and of the red button);
- what he may not do while hidden: `ACTIONS_BLOCKED_WHILE_HIDDEN`.
What ends hiding (moving, E again, a meeting, leaving) is done by the
server where those things happen; see `server/main.py`.
"""

from math import hypot

# He must stand at most this far (centre to centre) from a hiding spot's
# centre: the reach of E everywhere else on the map (`use_range`, 25).
HIDE_REACH_KEY = "use_range"

# The actions a hidden Free Rider must step out for first. Stepping out is
# instant (E again, or one step).
ACTIONS_BLOCKED_WHILE_HIDDEN = ("fail", "report", "emergency")


def spot_in_reach(campus, position):
    """The hiding spot nearest to `position` within reach, or None.

    The reach itself counts as within. On a tie the spot listed first in the
    map wins. `position` is `(x, y)` or None (not placed yet).
    """
    if position is None:
        return None
    reach = campus[HIDE_REACH_KEY]
    nearest = None
    nearest_distance = None
    for spot in campus.get("hiding_spots", []):
        distance = hypot(position[0] - spot["x"], position[1] - spot["y"])
        if distance <= reach and (nearest is None or distance < nearest_distance):
            nearest, nearest_distance = spot, distance
    return nearest


def hide_refusal(roles, ghosts, phase, player, position, campus):
    """Why `player` may not hide now, as a rejection code, or None if he may.

    `roles` maps the round's players to "HP" or "FR", `ghosts` are the failed
    and voted-out players, `phase` is the round's phase ("round", "meeting",
    "result"). Only a living Free Rider hides, only in the phase "round".
    """
    if roles.get(player) != "FR" or player in ghosts or phase != "round":
        return "hide_rejected"
    if spot_in_reach(campus, position) is None:
        return "hide_out_of_reach"
    return None


def blocked_while_hidden(action, player, hidden):
    """True when `player` is hidden and `action` needs him to step out first."""
    return player in hidden and action in ACTIONS_BLOCKED_WHILE_HIDDEN
