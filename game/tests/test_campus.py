"""The map file: it loads, its numbers make sense, and a broken file is refused clearly."""

import copy
import json

import pytest

from server.world.campus import CAMPUS_FILE, CampusError, check_campus, load_campus
from server.world.movement import is_free


@pytest.fixture(scope="module")
def campus():
    return load_campus()


def broken(campus, change):
    """A copy of the real map with one thing changed by `change(copy)`."""
    bad = copy.deepcopy(campus)
    change(bad)
    return bad


# Accepted: the real file

def test_the_map_file_loads_with_the_size_of_the_sketch(campus):
    assert (campus["width"], campus["height"]) == (680, 668)


def test_the_five_rooms_are_there(campus):
    names = [room["name"] for room in campus["rooms"]]
    assert names == ["Lecture Hall", "Mon Café", "Canteen", "CTT Student Hall", "Pingo Doce"]


def test_the_deck_outline_has_the_eight_corners_of_the_sketch(campus):
    corners = [(point["x"], point["y"]) for point in campus["deck"]]
    assert corners == [(20, 170), (660, 170), (660, 400), (440, 400),
                       (440, 566), (160, 566), (160, 230), (20, 230)]


def test_there_are_five_doors_and_each_is_40_wide(campus):
    assert len(campus["doors"]) == 5
    assert all(door["w"] == 40 for door in campus["doors"])


def test_every_solid_and_door_has_a_size_and_lies_inside_the_map(campus):
    for rectangle in campus["solids"] + campus["doors"]:
        assert rectangle["w"] > 0 and rectangle["h"] > 0, rectangle
        assert rectangle["x"] >= 0 and rectangle["y"] >= 0, rectangle
        assert rectangle["x"] + rectangle["w"] <= campus["width"], rectangle
        assert rectangle["y"] + rectangle["h"] <= campus["height"], rectangle


def test_every_solid_has_a_kind_and_its_own_id(campus):
    ids = [solid["id"] for solid in campus["solids"]]
    assert len(ids) == len(set(ids))
    assert all(solid["kind"] for solid in campus["solids"])


@pytest.mark.parametrize("kind, count", [
    ("glass", 1), ("pool", 1), ("tree", 6), ("hedge", 1), ("logo", 1),
    # M2-1.19 (S-125): three lecture rows, Mon Café without the table in
    # front of its door and the column under station 2, the canteen without
    # its top middle and bottom right tables.
    ("bench", 3), ("board", 1), ("counter", 2), ("machine", 1), ("column", 3),
    ("round-table", 2), ("table", 3), ("table-row", 8), ("bookshelf", 1),
    ("shelf", 4), ("checkout", 1),
])
def test_the_furniture_of_the_sketch_is_all_there(campus, kind, count):
    assert sum(1 for solid in campus["solids"] if solid["kind"] == kind) == count


def test_every_wall_is_6_units_thick(campus):
    for solid in campus["solids"]:
        if solid["kind"] == "wall":
            assert min(solid["w"], solid["h"]) == 6, solid


def test_every_tree_bed_is_28_by_28(campus):
    trees = [solid for solid in campus["solids"] if solid["kind"] == "tree"]
    assert all((tree["w"], tree["h"]) == (28, 28) for tree in trees)


def test_no_wall_blocks_a_door(campus):
    for door in campus["doors"]:
        for solid in campus["solids"]:
            apart = (
                solid["x"] >= door["x"] + door["w"] or solid["x"] + solid["w"] <= door["x"]
                or solid["y"] >= door["y"] + door["h"] or solid["y"] + solid["h"] <= door["y"]
            )
            assert apart, (door, solid)


def test_the_spawn_point_is_free(campus):
    spawn = campus["spawn"]
    assert is_free(spawn["x"], spawn["y"], campus["solids"], campus["width"], campus["height"])


def test_stations_and_the_button_are_not_solid(campus):
    # A player must be able to stand on them, so their centres are free.
    points = campus["stations"] + [campus["button"]]
    assert len(campus["stations"]) == 6
    for point in points:
        assert is_free(point["x"], point["y"], campus["solids"], campus["width"], campus["height"]), point


def test_the_things_that_are_only_drawn_are_there(campus):
    assert len(campus["hiding_spots"]) == 4
    assert [band["id"] for band in campus["bands"]] == ["sand", "sea"]


def test_check_campus_returns_a_good_map_unchanged(campus):
    assert check_campus(copy.deepcopy(campus)) == campus


# Rejected: broken files

@pytest.mark.parametrize("not_a_map", [None, [], "campus", 5])
def test_something_that_is_not_an_object_is_refused(not_a_map):
    with pytest.raises(CampusError):
        check_campus(not_a_map)


def test_an_empty_map_is_refused_with_the_missing_key_in_the_message():
    with pytest.raises(CampusError, match="width"):
        check_campus({})


@pytest.mark.parametrize("key", [
    "width", "height", "spawn", "rooms", "deck", "doors", "solids",
    "stations", "button", "hiding_spots", "bands",
])
def test_a_missing_part_is_refused_and_named(campus, key):
    with pytest.raises(CampusError, match=key):
        check_campus(broken(campus, lambda bad: bad.pop(key)))


@pytest.mark.parametrize("width", [0, -680, "680", None, True, float("nan"), float("inf")])
def test_a_width_that_is_not_a_positive_number_is_refused(campus, width):
    with pytest.raises(CampusError):
        check_campus(broken(campus, lambda bad: bad.update(width=width)))


@pytest.mark.parametrize("change", [
    lambda solid: solid.update(w=0),
    lambda solid: solid.update(h=-6),
    lambda solid: solid.update(x=-1),
    lambda solid: solid.update(x=679),         # sticks out on the right
    lambda solid: solid.update(y=667),         # sticks out at the bottom
    lambda solid: solid.update(x="17"),
    lambda solid: solid.pop("h"),
    lambda solid: solid.pop("kind"),
    lambda solid: solid.update(kind=""),
])
def test_a_broken_solid_is_refused_and_named(campus, change):
    with pytest.raises(CampusError, match=r"solids\[0\]"):
        check_campus(broken(campus, lambda bad: change(bad["solids"][0])))


def test_a_solid_that_is_not_an_object_is_refused(campus):
    with pytest.raises(CampusError, match=r"solids\[1\]"):
        check_campus(broken(campus, lambda bad: bad["solids"].__setitem__(1, [17, 17, 6, 6])))


def test_a_door_without_width_is_refused(campus):
    with pytest.raises(CampusError, match=r"doors\[2\]"):
        check_campus(broken(campus, lambda bad: bad["doors"][2].update(w=0)))


def test_a_spawn_outside_the_map_is_refused(campus):
    with pytest.raises(CampusError, match="spawn"):
        check_campus(broken(campus, lambda bad: bad.update(spawn={"x": 700, "y": 296})))


def test_a_missing_room_is_refused(campus):
    with pytest.raises(CampusError, match="5 rooms"):
        check_campus(broken(campus, lambda bad: bad["rooms"].pop()))


def test_a_missing_station_is_refused(campus):
    with pytest.raises(CampusError, match="6 stations"):
        check_campus(broken(campus, lambda bad: bad["stations"].pop()))


def test_solids_that_are_not_a_list_are_refused(campus):
    with pytest.raises(CampusError, match="solids"):
        check_campus(broken(campus, lambda bad: bad.update(solids={})))


# Edge cases

def test_a_map_without_any_solid_is_still_a_map(campus):
    empty = broken(campus, lambda bad: bad.update(solids=[]))
    assert check_campus(empty)["solids"] == []


def test_a_solid_may_reach_exactly_to_the_edge_of_the_map(campus):
    edge = {"id": "edge", "kind": "wall", "x": 674, "y": 0, "w": 6, "h": 668}
    assert check_campus(broken(campus, lambda bad: bad["solids"].append(edge)))


def test_a_file_that_does_not_exist_is_refused(tmp_path):
    with pytest.raises(CampusError, match="cannot be read"):
        load_campus(tmp_path / "nothing.json")


def test_a_file_that_is_not_json_is_refused(tmp_path):
    path = tmp_path / "campus.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(CampusError, match="not valid JSON"):
        load_campus(path)


def test_a_file_with_a_broken_map_is_refused(tmp_path):
    path = tmp_path / "campus.json"
    path.write_text(json.dumps({"width": 680, "height": 668}), encoding="utf-8")
    with pytest.raises(CampusError, match="spawn"):
        load_campus(path)


def test_the_map_file_sits_in_the_client_folder():
    assert CAMPUS_FILE.parts[-4:] == ("client", "js", "world", "campus.json")


# Rejected: found in the review of M1-1.3

HUGE = 10 ** 400        # a whole number too large for a float


def test_a_spawn_inside_a_solid_is_refused(campus):
    in_the_pool = {"x": 365, "y": 290}
    with pytest.raises(CampusError, match="spawn point is not free"):
        check_campus(broken(campus, lambda bad: bad.update(spawn=in_the_pool)))


def test_a_spawn_that_only_clips_a_solid_is_refused(campus):
    # The pool starts at x = 300. A player at x = 296 reaches to x = 301.
    with pytest.raises(CampusError, match="spawn point is not free"):
        check_campus(broken(campus, lambda bad: bad.update(spawn={"x": 296, "y": 290})))


def test_a_spawn_touching_a_solid_is_accepted(campus):
    # At x = 295 the player reaches exactly to the pool's edge at x = 300.
    assert check_campus(broken(campus, lambda bad: bad.update(spawn={"x": 295, "y": 290})))


def test_a_spawn_on_the_edge_of_the_map_is_refused(campus):
    # The point is inside the map, but half of the player would stick out.
    with pytest.raises(CampusError, match="spawn point is not free"):
        check_campus(broken(campus, lambda bad: bad.update(spawn={"x": 2, "y": 300})))


@pytest.mark.parametrize("part", ["solids", "doors"])
@pytest.mark.parametrize("key, value", [("x", 17.5), ("y", 17.25), ("w", 6.1), ("h", 6.5), ("x", 17.0)])
def test_solids_and_doors_must_sit_on_whole_units(campus, part, key, value):
    with pytest.raises(CampusError, match="whole number"):
        check_campus(broken(campus, lambda bad: bad[part][0].update({key: value})))


def test_a_door_without_a_room_is_refused(campus):
    with pytest.raises(CampusError, match="room"):
        check_campus(broken(campus, lambda bad: bad["doors"][0].pop("room")))


@pytest.mark.parametrize("room", ["", "library", 3, None])
def test_a_door_to_a_room_that_does_not_exist_is_refused(campus, room):
    with pytest.raises(CampusError, match=r"doors\[0\]"):
        check_campus(broken(campus, lambda bad: bad["doors"][0].update(room=room)))


@pytest.mark.parametrize("key", ["id", "kind"])
def test_a_solid_without_id_or_kind_is_refused(campus, key):
    with pytest.raises(CampusError, match=key):
        check_campus(broken(campus, lambda bad: bad["solids"][3].pop(key)))


@pytest.mark.parametrize("solid_id", ["", 7, None])
def test_a_solid_whose_id_is_not_a_text_is_refused(campus, solid_id):
    with pytest.raises(CampusError, match=r"solids\[3\]"):
        check_campus(broken(campus, lambda bad: bad["solids"][3].update(id=solid_id)))


def test_two_solids_with_the_same_id_are_refused(campus):
    with pytest.raises(CampusError, match="another solid"):
        check_campus(broken(campus, lambda bad: bad["solids"][1].update(id=bad["solids"][0]["id"])))


def test_a_station_without_id_is_refused(campus):
    with pytest.raises(CampusError, match=r"stations\[0\]"):
        check_campus(broken(campus, lambda bad: bad["stations"][0].pop("id")))


@pytest.mark.parametrize("station_id", ["1", 1.5, None, True])
def test_a_station_whose_id_is_not_a_whole_number_is_refused(campus, station_id):
    with pytest.raises(CampusError, match=r"stations\[0\]"):
        check_campus(broken(campus, lambda bad: bad["stations"][0].update(id=station_id)))


@pytest.mark.parametrize("change", [
    lambda bad: bad.update(width=HUGE),
    lambda bad: bad.update(height=-HUGE),
    lambda bad: bad["spawn"].update(x=HUGE),
    lambda bad: bad["solids"][0].update(x=HUGE),
    lambda bad: bad["solids"][0].update(w=HUGE),
    lambda bad: bad["doors"][0].update(y=-HUGE),
    lambda bad: bad["rooms"][0].update(h=HUGE),
    lambda bad: bad["deck"][0].update(x=HUGE),
    lambda bad: bad["stations"][0].update(y=HUGE),
    lambda bad: bad["button"].update(x=HUGE),
    lambda bad: bad["hiding_spots"][0].update(x=HUGE),
    lambda bad: bad["bands"][0].update(w=HUGE),
])
def test_a_huge_number_is_refused_as_a_broken_map_and_not_as_a_crash(campus, change):
    with pytest.raises(CampusError):
        check_campus(broken(campus, change))


def test_a_giant_map_that_still_fits_into_a_float_does_not_crash(campus):
    # 10 ** 300 still fits into a float. Everything else then lies inside this giant map.
    assert check_campus(broken(campus, lambda bad: bad.update(width=10 ** 300, height=10 ** 300)))


# The range for using a station and the ids of the stations (M2-1.1)

def test_the_map_says_how_close_a_station_must_be(campus):
    assert campus["use_range"] == 25


def test_every_station_has_its_own_id(campus):
    assert sorted(station["id"] for station in campus["stations"]) == [1, 2, 3, 4, 5, 6]


def test_a_map_without_use_range_is_refused_and_names_it(campus):
    with pytest.raises(CampusError, match="use_range"):
        check_campus(broken(campus, lambda bad: bad.pop("use_range")))


@pytest.mark.parametrize("use_range", [0, -25, "25", None, True, [25], float("nan"), float("inf"), HUGE])
def test_a_use_range_that_is_not_a_positive_number_is_refused(campus, use_range):
    with pytest.raises(CampusError, match="use_range"):
        check_campus(broken(campus, lambda bad: bad.update(use_range=use_range)))


@pytest.mark.parametrize("use_range", [1, 0.5, 25.5, 100])
def test_any_use_range_above_0_is_accepted(campus, use_range):
    assert check_campus(broken(campus, lambda bad: bad.update(use_range=use_range)))


def test_two_stations_with_the_same_id_are_refused(campus):
    with pytest.raises(CampusError, match=r"stations\[1\] has the id 1 of another station"):
        check_campus(broken(campus, lambda bad: bad["stations"][1].update(id=1)))
