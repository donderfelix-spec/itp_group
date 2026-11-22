"""Loads the campus map and checks that it makes sense.

The map exists once, as `client/js/world/campus.json` (S-79). The browser
draws from that file and the server reads the same file here, so the walls a
player sees and the walls the server enforces cannot drift apart.

A broken map file must never start a game, so `check_campus` raises a
`CampusError` that says exactly what is wrong.
"""

import json
import math
import re
from pathlib import Path

from server.world.movement import is_free

# game/server/world/campus.py -> game/client/js/world/campus.json
CAMPUS_FILE = Path(__file__).resolve().parents[2] / "client" / "js" / "world" / "campus.json"

ROOM_COUNT = 5
STATION_COUNT = 12

# The detail of the map (M2-1.4) is only drawn by the browser. The server
# still checks it, so a typo in the map file is found when the server starts.
# A wall's face may be at most this high: a player pressed against the wall
# stands with the feet about 10 units below it.
HIGHEST_WALL_FACE = 10
# The layers of decor: flat on the floor, on a wall, standing on a solid.
DECOR_LAYERS = ("floor", "wall", "on")
# The keys a decor entry may have; any other key is a typo.
DECOR_KEYS = {"kind", "layer", "x", "y", "w", "h", "text", "colour"}
LONGEST_DECOR_TEXT = 40
# Names of drawings (patterns, faces, kinds of decor): small letters, digits
# and hyphens, such as "wood-slats".
ART_NAME = re.compile(r"[a-z][a-z0-9-]{0,39}")
COLOUR = re.compile(r"#[0-9A-Fa-f]{6}")


class CampusError(ValueError):
    """The map file is missing something or contains a value that cannot be right."""


def load_campus(path=CAMPUS_FILE) -> dict:
    """Read the map file, check it and return it as a dict."""
    try:
        with open(path, encoding="utf-8") as file:
            campus = json.load(file)
    except OSError as problem:
        raise CampusError(f"The map file {path} cannot be read: {problem}") from problem
    except json.JSONDecodeError as problem:
        raise CampusError(f"The map file {path} is not valid JSON: {problem}") from problem
    return check_campus(campus)


def check_campus(campus) -> dict:
    """Return the map unchanged if it is usable, otherwise raise `CampusError`."""
    if not isinstance(campus, dict):
        raise CampusError("The map must be an object with width, height, rooms, solids and so on.")

    width = _number(campus, "width", "the map")
    height = _number(campus, "height", "the map")
    if width <= 0 or height <= 0:
        raise CampusError("The map needs a width and a height above 0.")

    spawn = _entry(campus, "spawn", "the map")
    _check_point(spawn, "spawn", width, height)

    rooms = _list(campus, "rooms")
    if len(rooms) != ROOM_COUNT:
        raise CampusError(f"The map needs exactly {ROOM_COUNT} rooms, found {len(rooms)}.")
    for index, room in enumerate(rooms):
        _check_rectangle(room, f"rooms[{index}]", width, height)
        for key in ("id", "name", "floor"):
            _text(room, key, f"rooms[{index}]")
        _check_room_label(room, f"rooms[{index}]")
        for key in ("pattern", "wall_face"):
            _optional_art_name(room, key, f"rooms[{index}]")
    _check_deck_label(_entry(campus, "deck_label", "the map"), rooms, width, height)
    for key in ("deck_pattern", "deck_wall_face"):
        _optional_art_name(campus, key, "the map")
    _check_wall_face_height(campus)

    deck = _list(campus, "deck")
    if len(deck) < 3:
        raise CampusError("The deck outline needs at least 3 points.")
    for index, point in enumerate(deck):
        _check_point(point, f"deck[{index}]", width, height)

    room_ids = [room["id"] for room in rooms]
    for index, door in enumerate(_list(campus, "doors")):
        _check_rectangle(door, f"doors[{index}]", width, height)
        _check_whole_numbers(door, f"doors[{index}]")
        if _text(door, "room", f"doors[{index}]") not in room_ids:
            raise CampusError(f"\"room\" of doors[{index}] is not the id of a room.")

    solids = _list(campus, "solids")
    solid_ids = set()
    for index, solid in enumerate(solids):
        _check_rectangle(solid, f"solids[{index}]", width, height)
        _check_whole_numbers(solid, f"solids[{index}]")
        _text(solid, "kind", f"solids[{index}]")
        if "walkable" in solid and not isinstance(solid["walkable"], bool):
            raise CampusError(f"walkable of solids[{index}] must be a boolean.")
        # Which drawing a solid shows, for kinds that have several (a sign
        # totem with a basket or a cup): only drawn, optional.
        _optional_art_name(solid, "icon", f"solids[{index}]")
        solid_id = _text(solid, "id", f"solids[{index}]")
        if solid_id in solid_ids:
            raise CampusError(f"solids[{index}] has the id \"{solid_id}\" of another solid.")
        solid_ids.add(solid_id)

    # Checked after the solids, because it needs them.
    if not is_free(spawn["x"], spawn["y"], solids, width, height):
        raise CampusError("The spawn point is not free: a player there would overlap a solid or the edge of the map.")

    stations = _list(campus, "stations")
    if len(stations) != STATION_COUNT:
        raise CampusError(f"The map needs exactly {STATION_COUNT} stations, found {len(stations)}.")
    station_ids = set()
    for index, station in enumerate(stations):
        _check_point(station, f"stations[{index}]", width, height)
        station_id = _entry(station, "id", f"stations[{index}]")
        if isinstance(station_id, bool) or not isinstance(station_id, int):
            raise CampusError(f"\"id\" of stations[{index}] must be a whole number.")
        if station_id in station_ids:
            raise CampusError(f"stations[{index}] has the id {station_id} of another station.")
        station_ids.add(station_id)

    # How close the centre of a player must be to the centre of a station to
    # use it (server/world/stations.py).
    if _number(campus, "use_range", "the map") <= 0:
        raise CampusError("\"use_range\" of the map must be above 0.")

    _check_point(_entry(campus, "button", "the map"), "button", width, height)
    if "hide_reveal_range" in campus and _number(campus, "hide_reveal_range", "the map") <= 0:
        raise CampusError("hide_reveal_range must be above 0.")
    for index, spot in enumerate(_list(campus, "hiding_spots")):
        _check_point(spot, f"hiding_spots[{index}]", width, height)
        if _number(spot, "r", f"hiding_spots[{index}]") <= 0:
            raise CampusError("A hiding radius must be above 0.")
        if not is_free(spot["x"], spot["y"], solids, width, height):
            raise CampusError("A hiding spot must have a walkable centre.")
    for index, band in enumerate(_list(campus, "bands")):
        _check_rectangle(band, f"bands[{index}]", width, height)

    if "decor" in campus:
        for index, item in enumerate(_list(campus, "decor")):
            _check_decor(item, f"decor[{index}]", width, height)

    return campus


# ---- The detail that only the browser draws (M2-1.4) -----------------------

def _optional_art_name(container, key, where):
    """A key that names a drawing may be missing; if it is there, it must be a name."""
    if key in container:
        _art_name(container, key, where)


def _art_name(container, key, where):
    value = _entry(container, key, where)
    if not isinstance(value, str) or not ART_NAME.fullmatch(value):
        raise CampusError(f"\"{key}\" of {where} must be a name of small letters, digits and hyphens, such as \"wood-slats\".")
    return value


def _check_wall_face_height(campus):
    """How far below a wall its face is drawn: optional, above 0 and at most 10."""
    if "wall_face_height" not in campus:
        return
    face_height = _number(campus, "wall_face_height", "the map")
    if not 0 < face_height <= HIGHEST_WALL_FACE:
        raise CampusError(f"\"wall_face_height\" of the map must be above 0 and at most {HIGHEST_WALL_FACE}.")


def _check_decor(item, where, map_width, map_height):
    """One thing that is only drawn: a sign, a mat, a coffee machine on a counter.

    Its `layer` says where it is: "floor" (flat on the floor, players walk
    over it), "wall" (on a wall) or "on" (standing on a solid). Whether a
    "wall" entry really touches a wall and an "on" entry lies inside a solid
    is checked by tests/test_campus_detail.py on the real map, not here: a
    map without solids is still a map (tests/test_campus.py).
    """
    _check_rectangle(item, where, map_width, map_height)
    unknown = sorted(set(item) - DECOR_KEYS)
    if unknown:
        raise CampusError(f"{where} has the unknown key \"{unknown[0]}\".")
    _art_name(item, "kind", where)
    layer = _entry(item, "layer", where)
    if layer not in DECOR_LAYERS:
        raise CampusError(f"\"layer\" of {where} must be \"floor\", \"wall\" or \"on\".")
    if "text" in item:
        words = _text(item, "text", where)
        if len(words) > LONGEST_DECOR_TEXT:
            raise CampusError(f"\"text\" of {where} is longer than {LONGEST_DECOR_TEXT} characters.")
    if "colour" in item:
        colour = item["colour"]
        if not isinstance(colour, str) or not COLOUR.fullmatch(colour):
            raise CampusError(f"\"colour\" of {where} must be a colour like \"#3E9B4F\".")


def _check_rectangle(rectangle, where, map_width, map_height):
    """A rectangle needs x, y, w, h, a size above 0, and must lie inside the map."""
    if not isinstance(rectangle, dict):
        raise CampusError(f"{where} must be an object with x, y, w and h.")
    x = _number(rectangle, "x", where)
    y = _number(rectangle, "y", where)
    w = _number(rectangle, "w", where)
    h = _number(rectangle, "h", where)
    if w <= 0 or h <= 0:
        raise CampusError(f"{where} needs a width and a height above 0.")
    if x < 0 or y < 0 or x + w > map_width or y + h > map_height:
        raise CampusError(f"{where} lies outside the map.")


def _check_whole_numbers(rectangle, where):
    """Solids and doors must sit on whole units.

    The movement rules compare "touching" exactly. With whole numbers that is
    always exact; with numbers like 0.1 the computer rounds, and a player could
    stick to a wall or slip into it by a hair.
    """
    for key in ("x", "y", "w", "h"):
        if not isinstance(rectangle[key], int):
            raise CampusError(f"\"{key}\" of {where} must be a whole number.")


def _check_point(point, where, map_width, map_height):
    """A point needs x and y inside the map."""
    if not isinstance(point, dict):
        raise CampusError(f"{where} must be an object with x and y.")
    x = _number(point, "x", where)
    y = _number(point, "y", where)
    if not (0 <= x <= map_width and 0 <= y <= map_height):
        raise CampusError(f"{where} lies outside the map.")


def _check_room_label(room, where):
    """A room's name is drawn at its `label`, a point inside the room.

    Labels are only drawn: nothing on the server walks or collides with them.
    A point exactly on the room's edge still counts as inside:
    `_is_in_room` counts the edge as inside, like `roomAt()` in draw.js.
    """
    label = _entry(room, "label", where)
    label_where = f"the label of {where}"
    if not isinstance(label, dict):
        raise CampusError(f"{label_where} must be an object with x and y.")
    x = _number(label, "x", label_where)
    y = _number(label, "y", label_where)
    if not _is_in_room(x, y, room):
        raise CampusError(f"{label_where} lies outside its room.")


def _check_deck_label(label, rooms, map_width, map_height):
    """The deck's name: a text, drawn at a point on the map but in no room."""
    if not isinstance(label, dict):
        raise CampusError("deck_label must be an object with name, x and y.")
    _text(label, "name", "deck_label")
    _check_point(label, "deck_label", map_width, map_height)
    for room in rooms:
        if _is_in_room(label["x"], label["y"], room):
            raise CampusError(f"deck_label lies inside the room \"{room['id']}\", not on the deck.")


def _is_in_room(x, y, room):
    """True if the point lies in the room's rectangle or on its edge."""
    return room["x"] <= x <= room["x"] + room["w"] and room["y"] <= y <= room["y"] + room["h"]


def _entry(container, key, where):
    if key not in container:
        raise CampusError(f"{where} has no \"{key}\".")
    return container[key]


def _number(container, key, where):
    value = _entry(container, key, where)
    # `True` counts as a number in Python, but it is never a sensible coordinate.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CampusError(f"\"{key}\" of {where} must be a number.")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        # A whole number with hundreds of digits does not fit into a float.
        finite = False
    if not finite:
        raise CampusError(f"\"{key}\" of {where} must be a number of ordinary size.")
    return value


def _text(container, key, where):
    value = _entry(container, key, where)
    if not isinstance(value, str) or value == "":
        raise CampusError(f"\"{key}\" of {where} must be a text.")
    return value


def _list(campus, key):
    value = _entry(campus, key, "the map")
    if not isinstance(value, list):
        raise CampusError(f"\"{key}\" of the map must be a list.")
    return value
