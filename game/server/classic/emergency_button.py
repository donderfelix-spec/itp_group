"""Whether a player stands close enough to the red emergency button, as a plain function.

No network, no database and no clock in here (rule 4). The button and the
reach come from the map file (`button` and `use_range` in `campus.json`) and
are passed in, so tests can control them.

The browser has the same rule in `client/js/world/world.js`, function
`isAtEmergencyButton`, to decide when "E Emergency" shows. Change both together.
"""


def emergency_button_in_reach(position, button, reach):
    """Return True if a player at `position` may press the emergency button.

    `position` is `(x, y)` or None (a player the tick has not placed yet).
    `button` is the map's button, a dict with the centre "x" and "y".
    The distance counts from the button's centre, as for a station, and a
    player exactly `reach` away still counts.
    """
    if position is None:
        return False
    x, y = position
    if not (_is_number(x) and _is_number(y)):
        return False
    dx = button["x"] - x
    dy = button["y"] - y
    # Squared distances, as in server/world/stations.py: no square root needed.
    # A position of NaN makes this comparison false, so it is never in reach.
    return dx * dx + dy * dy <= reach * reach


def _is_number(value):
    """A real int or float. True and False are ints in Python, but no coordinate."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)
