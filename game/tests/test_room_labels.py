"""Where the names of the rooms and of the deck are drawn (M1-1.6).

Each room has a `label` in the map file and the deck has a `deck_label`.
They are only drawn, but the server checks them like the rest of the map,
so a broken map file is refused with a clear message.
"""

import copy
import math

import pytest

from server.world.campus import CampusError, check_campus, load_campus

CAMPUS = load_campus()
ROOMS = {room["id"]: room for room in CAMPUS["rooms"]}
HUGE = 10 ** 400  # does not fit into a float


def broken(change):
    """A copy of the real map with one thing changed by `change(copy)`."""
    bad = copy.deepcopy(CAMPUS)
    change(bad)
    return bad


def label_at(room_index, x, y):
    """A change that moves the label of one room."""
    return lambda bad: bad["rooms"][room_index].update(label={"x": x, "y": y})


def old_label_place(room):
    """Where the name was drawn before M1-1.6: the middle of the room's width,
    18 units inside the wall with the door (the old rule in draw.js)."""
    door = next(door for door in CAMPUS["doors"] if door["room"] == room["id"])
    door_is_at_the_top = door["y"] + door["h"] / 2 < room["y"] + room["h"] / 2
    if door_is_at_the_top:
        y = room["y"] + 18
    else:
        y = room["y"] + room["h"] - 18
    return {"x": room["x"] + room["w"] / 2, "y": y}


# Accepted: the real map

def test_every_room_has_a_label_inside_it():
    for room in CAMPUS["rooms"]:
        label = room["label"]
        assert room["x"] <= label["x"] <= room["x"] + room["w"], room["id"]
        assert room["y"] <= label["y"] <= room["y"] + room["h"], room["id"]


@pytest.mark.parametrize("room_id, x, y", [
    ("mon-cafe", 350, 152),
    ("canteen", 565, 152),
    ("ctt", 90, 248),
])
def test_other_room_names_keep_their_place(room_id, x, y):
    room = ROOMS[room_id]
    assert room["label"] == {"x": x, "y": y}
    assert room["label"] == old_label_place(room)


def test_pingo_doce_name_moves_left_but_stays_right_of_the_exit():
    # Hanna requested a small leftward adjustment from the original x614.
    # Keep the exact placement and the right-hand room position checked.
    assert ROOMS["pingo-doce"]["label"] == {"x": 608, "y": 421}
    room = ROOMS["pingo-doce"]
    assert ROOMS["pingo-doce"]["label"]["x"] > room["x"] + room["w"] / 2


def test_the_deck_is_called_main_deck_and_its_name_is_not_on_the_spawn_point():
    label = CAMPUS["deck_label"]
    spawn = CAMPUS["spawn"]
    assert label["name"] == "Main Deck"
    assert math.dist((label["x"], label["y"]), (spawn["x"], spawn["y"])) >= 40


def test_main_deck_is_in_no_room():
    label = CAMPUS["deck_label"]
    for room in CAMPUS["rooms"]:
        inside = (room["x"] <= label["x"] <= room["x"] + room["w"]
                  and room["y"] <= label["y"] <= room["y"] + room["h"])
        assert not inside, room["id"]


def test_main_deck_has_room_for_its_letters():
    # "Main Deck" in bold 13 px is about 70 units wide and 13 high. A box a
    # little larger than that around the label touches nothing that is drawn.
    label = CAMPUS["deck_label"]
    left, right = label["x"] - 42, label["x"] + 42
    top, bottom = label["y"] - 9, label["y"] + 9
    for solid in CAMPUS["solids"]:
        apart = (solid["x"] + solid["w"] < left or solid["x"] > right
                 or solid["y"] + solid["h"] < top or solid["y"] > bottom)
        assert apart, solid["id"]
    circles = CAMPUS["stations"] + CAMPUS["hiding_spots"] + [CAMPUS["button"]]
    for thing in circles:
        apart = (thing["x"] + thing["r"] < left or thing["x"] - thing["r"] > right
                 or thing["y"] + thing["r"] < top or thing["y"] - thing["r"] > bottom)
        assert apart, thing


@pytest.mark.parametrize("corner", ["top left", "bottom right"])
def test_a_label_exactly_on_the_edge_of_its_room_is_accepted(corner):
    # Decision for this to-do: the edge belongs to the room, as in roomAt() of draw.js.
    room = CAMPUS["rooms"][0]
    if corner == "top left":
        x, y = room["x"], room["y"]
    else:
        x, y = room["x"] + room["w"], room["y"] + room["h"]
    assert check_campus(broken(label_at(0, x, y)))


def test_a_label_with_a_fraction_is_accepted():
    # Labels are only drawn, so unlike solids they need not sit on whole units.
    assert check_campus(broken(label_at(0, 125.5, 151.25)))


def test_a_deck_label_on_the_edge_of_the_map_is_accepted():
    # The corner (0, 0) lies on the map and in no room.
    assert check_campus(broken(lambda bad: bad["deck_label"].update(x=0, y=0)))


# Rejected: room labels

def test_a_room_without_label_is_refused_and_named():
    with pytest.raises(CampusError, match=r"rooms\[3\] has no \"label\""):
        check_campus(broken(lambda bad: bad["rooms"][3].pop("label")))


@pytest.mark.parametrize("label", [None, [125, 152]])
def test_a_label_that_is_not_an_object_is_refused(label):
    with pytest.raises(CampusError, match=r"the label of rooms\[0\] must be an object"):
        check_campus(broken(lambda bad: bad["rooms"][0].update(label=label)))


@pytest.mark.parametrize("key", ["x", "y"])
def test_a_label_without_x_or_y_is_refused(key):
    with pytest.raises(CampusError, match=rf"the label of rooms\[1\] has no \"{key}\""):
        check_campus(broken(lambda bad: bad["rooms"][1]["label"].pop(key)))


@pytest.mark.parametrize("key, value", [("x", "125"), ("y", float("nan")), ("x", HUGE)])
def test_a_label_that_is_not_an_ordinary_number_is_refused(key, value):
    with pytest.raises(CampusError, match=rf"\"{key}\" of the label of rooms\[2\]"):
        check_campus(broken(lambda bad: bad["rooms"][2]["label"].update({key: value})))


@pytest.mark.parametrize("x, y", [
    (19, 100),    # just left of the lecture hall
    (231, 100),   # just right of it
    (125, 19),    # just above it
    (125, 171),   # just below it, on the deck
])
def test_a_label_outside_its_room_is_refused(x, y):
    with pytest.raises(CampusError, match=r"the label of rooms\[0\] lies outside its room"):
        check_campus(broken(label_at(0, x, y)))


# Rejected: the deck label

def test_a_map_without_deck_label_is_refused_and_names_it():
    with pytest.raises(CampusError, match="deck_label"):
        check_campus(broken(lambda bad: bad.pop("deck_label")))


@pytest.mark.parametrize("label", ["Main Deck", [365, 350]])
def test_a_deck_label_that_is_not_an_object_is_refused(label):
    with pytest.raises(CampusError, match="deck_label must be an object"):
        check_campus(broken(lambda bad: bad.update(deck_label=label)))


def test_a_deck_label_without_name_is_refused():
    with pytest.raises(CampusError, match=r"deck_label has no \"name\""):
        check_campus(broken(lambda bad: bad["deck_label"].pop("name")))


@pytest.mark.parametrize("name", ["", 5])
def test_a_deck_label_whose_name_is_not_a_text_is_refused(name):
    with pytest.raises(CampusError, match=r"\"name\" of deck_label must be a text"):
        check_campus(broken(lambda bad: bad["deck_label"].update(name=name)))


@pytest.mark.parametrize("key", ["x", "y"])
def test_a_deck_label_without_x_or_y_is_refused(key):
    with pytest.raises(CampusError, match=rf"deck_label has no \"{key}\""):
        check_campus(broken(lambda bad: bad["deck_label"].pop(key)))


@pytest.mark.parametrize("key, value", [("x", "365"), ("y", float("nan")), ("x", HUGE)])
def test_a_deck_label_that_is_not_an_ordinary_number_is_refused(key, value):
    with pytest.raises(CampusError, match=rf"\"{key}\" of deck_label"):
        check_campus(broken(lambda bad: bad["deck_label"].update({key: value})))


@pytest.mark.parametrize("x, y", [(-1, 350), (681, 350), (365, -1), (365, 669)])
def test_a_deck_label_outside_the_map_is_refused(x, y):
    with pytest.raises(CampusError, match="deck_label lies outside the map"):
        check_campus(broken(lambda bad: bad["deck_label"].update(x=x, y=y)))


@pytest.mark.parametrize("x, y, room_id", [
    (125, 100, "lecture-hall"),
    (550, 480, "pingo-doce"),
    (440, 400, "pingo-doce"),  # exactly on the corner of the room: the edge belongs to the room
])
def test_a_deck_label_inside_a_room_is_refused_and_names_the_room(x, y, room_id):
    with pytest.raises(CampusError, match=f"deck_label lies inside the room \"{room_id}\""):
        check_campus(broken(lambda bad: bad["deck_label"].update(x=x, y=y)))


def test_lecture_name_is_in_the_new_clear_row_gap():
    room = ROOMS["lecture-hall"]
    assert room["label"] == {"x": 125, "y": 133}
    rows = sorted((s for s in CAMPUS["solids"] if s["kind"] == "bench"), key=lambda s: s["y"])
    assert rows[2]["y"] + rows[2]["h"] + 6 <= room["label"]["y"] <= rows[3]["y"] - 6
