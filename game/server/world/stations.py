"""Which task station a player can use from where they stand, as a plain function.

No network and no clock in here. The stations and the range come from the map
file (`use_range` in `campus.json`, S-79) and are passed in, so tests can
control them.

The browser has the very same rule in `client/js/world/world.js`, function
`nearestStationInRange`, to decide which station glows. Change both together.
"""


def station_in_range(x, y, stations, use_range, usable_ids=None):
    """Return the id of the station the player at `(x, y)` can use, or None.

    A station counts when its centre is at most `use_range` away from the
    player's centre; exactly at the range still counts. With several stations
    in range the closest one wins, and an exact tie goes to the smaller id, so
    the answer is never random.

    `usable_ids` limits which stations count at all (None means all of them).
    """
    best_id = None
    best_distance = None
    for station in stations:
        if usable_ids is not None and station["id"] not in usable_ids:
            continue
        distance = _squared_distance(x, y, station)
        # Written as "not at most" so that a broken position (not a number)
        # is in range of nothing: every comparison with it is false.
        if not distance <= use_range * use_range:
            continue
        if _is_better(distance, station["id"], best_distance, best_id):
            best_id = station["id"]
            best_distance = distance
    return best_id


def _squared_distance(x, y, station):
    """The distance to the station's centre, squared.

    Squared distances are compared instead of real ones: no square root is
    needed, and Python and JavaScript then calculate exactly the same numbers.
    """
    dx = station["x"] - x
    dy = station["y"] - y
    return dx * dx + dy * dy


def _is_better(distance, station_id, best_distance, best_id):
    """Is this station closer than the best one so far, or as close with a smaller id?"""
    if best_id is None:
        return True
    if distance != best_distance:
        return distance < best_distance
    return station_id < best_id
