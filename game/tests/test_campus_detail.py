"""The detail of the campus map (M2-1.4): floor patterns, wall faces, decor and
the new furniture of Pingo Doce.

Patterns, faces and decor are only drawn by the browser, but the server
checks them like the rest of the map file, so a broken entry is refused with
a clear message (accepted, rejected and edge cases below). The rules for
placing things are checked on the real map:

- decor on layer "on" lies inside a solid, decor on layer "wall" touches a wall;
- a new solid leaves no gap of 10 to 13 units to any other solid: a player is
  10 wide and would just fit in, drawn over both (S-111);
- the spawn still reaches every station, and the new solids change no
  walking distance of the Duel (S-94).

The drawing itself runs in Node (tests/draw_art_in_node.js) with the page's
own draw.js and art files. Without Node those tests are skipped; CI has Node.
"""

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from server.modes import minigames
from server.world import paths
from server.world.campus import CampusError, check_campus, load_campus
from server.world.paths import station_distances

CAMPUS = load_campus()
SOLIDS = CAMPUS["solids"]
TESTS = Path(__file__).resolve().parent
DRAW_ART_IN_NODE = TESTS / "draw_art_in_node.js"

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

# The kinds of solids the map had before M2-1.4. Their counts are pinned by
# test_campus.py; everything added since is of a new kind.
OLD_KINDS = {
    "wall", "glass", "pool", "tree", "hedge", "logo", "bench", "board", "counter", "machine",
    "column", "round-table", "table", "table-row", "bookshelf", "shelf", "checkout",
}
NEW_SOLIDS = [solid for solid in SOLIDS if solid["kind"] not in OLD_KINDS]

# A gap a player (10 units wide) could just squeeze into (S-111).
SQUEEZE_GAPS = range(10, 14)

# The keys M2-1.4 added to the map.
ROOM_STYLE_KEYS = ("pattern", "wall_face")
MAP_STYLE_KEYS = ("deck_pattern", "deck_wall_face", "wall_face_height", "decor", "art_note")


def broken(change):
    """A copy of the real map with one thing changed by `change(copy)`."""
    bad = copy.deepcopy(CAMPUS)
    change(bad)
    return bad


def a_decor_entry(**changes):
    """A change that replaces decor[0] with a good floor entry, changed by `changes`."""
    entry = {"kind": "mat", "layer": "floor", "x": 300, "y": 200, "w": 20, "h": 8}
    entry.update(changes)
    return lambda bad: bad["decor"].__setitem__(0, entry)


def without_new_things(campus):
    """The map as it was before M2-1.4: no new keys and none of the new solids."""
    old = copy.deepcopy(campus)
    for key in MAP_STYLE_KEYS:
        old.pop(key, None)
    for room in old["rooms"]:
        for key in ROOM_STYLE_KEYS:
            room.pop(key, None)
    old["solids"] = [solid for solid in old["solids"] if solid["kind"] in OLD_KINDS]
    return old


def lies_inside(inner, outer):
    """The rectangle `inner` lies wholly inside `outer`; the edges may meet."""
    return (outer["x"] <= inner["x"] and inner["x"] + inner["w"] <= outer["x"] + outer["w"]
            and outer["y"] <= inner["y"] and inner["y"] + inner["h"] <= outer["y"] + outer["h"])


def touches(first, second):
    """The two rectangles overlap or meet at an edge."""
    return (first["x"] <= second["x"] + second["w"] and second["x"] <= first["x"] + first["w"]
            and first["y"] <= second["y"] + second["h"] and second["y"] <= first["y"] + first["h"])


def gap_between(first, second, solids=()):
    """The free space between two solids that face each other, or None.

    Two solids face each other when they overlap along one axis (by more
    than a point): then the gap is the distance along the other axis, 0 when
    they touch. Solids that only lie diagonally to each other leave no lane
    a player could get stuck in, and neither does a gap that a third solid of
    `solids` fills completely.
    """
    left = max(first["x"], second["x"])
    right = min(first["x"] + first["w"], second["x"] + second["w"])
    top = max(first["y"], second["y"])
    bottom = min(first["y"] + first["h"], second["y"] + second["h"])
    if right > left and bottom > top:
        return 0  # they overlap
    if right > left:
        between = {"x": left, "y": bottom, "w": right - left, "h": top - bottom}
    elif bottom > top:
        between = {"x": right, "y": top, "w": left - right, "h": bottom - top}
    else:
        return None
    if any(lies_inside(between, third) for third in solids if third is not first and third is not second):
        return None
    return between["w"] if right <= left else between["h"]


def run_node(mode, data):
    finished = subprocess.run(
        [NODE, str(DRAW_ART_IN_NODE), mode],
        input=json.dumps(data),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


# Accepted: the real map

def test_every_room_names_a_floor_pattern_and_a_wall_face():
    for room in CAMPUS["rooms"]:
        assert room["pattern"] and room["wall_face"], room["id"]


def test_the_deck_has_a_pattern_a_wall_face_and_faces_are_at_most_10_high():
    assert CAMPUS["deck_pattern"] == "paving"
    assert CAMPUS["deck_wall_face"] == "facade"
    assert 0 < CAMPUS["wall_face_height"] <= 10


def test_pingo_doce_has_its_new_furniture():
    kinds = sorted(solid["kind"] for solid in NEW_SOLIDS)
    assert kinds == ["fridge", "fridge", "fruit-stand", "hot-counter",
                     "turnstile", "turnstile", "turnstile", "turnstile"]
    pingo = next(room for room in CAMPUS["rooms"] if room["id"] == "pingo-doce")
    for solid in NEW_SOLIDS:
        assert lies_inside(solid, pingo), solid["id"]


def test_every_decor_on_a_solid_lies_inside_a_solid():
    on_solids = [item for item in CAMPUS["decor"] if item["layer"] == "on"]
    assert on_solids
    for item in on_solids:
        assert any(lies_inside(item, solid) for solid in SOLIDS), item


def test_every_decor_on_a_wall_touches_a_wall():
    on_walls = [item for item in CAMPUS["decor"] if item["layer"] == "wall"]
    assert on_walls
    walls = [solid for solid in SOLIDS if solid["kind"] == "wall"]
    for item in on_walls:
        assert any(touches(item, wall) for wall in walls), item


@pytest.mark.parametrize("solid", NEW_SOLIDS, ids=lambda solid: solid["id"])
def test_a_new_solid_leaves_no_gap_a_player_could_just_squeeze_into(solid):
    for other in SOLIDS:
        if other is not solid:
            assert gap_between(solid, other, SOLIDS) not in SQUEEZE_GAPS, (solid["id"], other["id"])


def test_the_spawn_reaches_every_station():
    grid = paths.Grid(SOLIDS, CAMPUS["width"], CAMPUS["height"])
    spawn = grid.nearest_free_point(CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"], paths.GRID_STEP)
    reached = grid.distances_from(spawn)
    for station in CAMPUS["stations"]:
        point = grid.nearest_free_point(station["x"], station["y"], CAMPUS["use_range"])
        assert point in reached, station["id"]


def test_the_new_solids_change_no_walking_distance_of_the_duel():
    # Measured for this to-do: spawn to station 5 stays 262.5, 4 to 5 stays 1031.5.
    stations = sorted(minigames.MINIGAMES)
    before = station_distances(without_new_things(CAMPUS), stations)
    after = station_distances(CAMPUS, stations)
    assert after.keys() == before.keys()
    for pair, distance in before.items():
        # Only the order of adding up the steps may differ.
        assert after[pair] == pytest.approx(distance, abs=0.001), pair


# Accepted: edge cases

def test_an_old_map_without_any_of_the_new_keys_still_loads():
    old = without_new_things(CAMPUS)
    assert check_campus(old) == old


def test_an_empty_list_of_decor_is_accepted():
    assert check_campus(broken(lambda bad: bad.update(decor=[])))["decor"] == []


@pytest.mark.parametrize("face_height", [10, 0.5, 8])
def test_a_wall_face_up_to_10_high_is_accepted(face_height):
    assert check_campus(broken(lambda bad: bad.update(wall_face_height=face_height)))


def test_decor_may_sit_on_fractions_of_a_unit_and_at_the_edge_of_the_map():
    # Unlike solids, decor is never walked against, so it need not sit on whole units.
    assert check_campus(broken(a_decor_entry(x=0, y=0.5, w=12.25, h=3)))
    assert check_campus(broken(a_decor_entry(x=660, y=648, w=20, h=20)))


def test_a_text_of_exactly_40_characters_is_accepted():
    assert check_campus(broken(a_decor_entry(kind="sign", text="X" * 40)))


@pytest.mark.parametrize("layer", ["floor", "wall", "on"])
def test_every_layer_is_accepted_by_the_server(layer):
    # Where a "wall" or "on" entry lies is a rule tested on the real map above.
    assert check_campus(broken(a_decor_entry(layer=layer)))


# Rejected: names of drawings

@pytest.mark.parametrize("key", ROOM_STYLE_KEYS)
@pytest.mark.parametrize("name", ["", "Wood Slats", "wood_slats", "-slats", 5, None, ["planks"], "a" * 41])
def test_a_room_style_that_is_not_a_name_is_refused_and_named(key, name):
    with pytest.raises(CampusError, match=rf"\"{key}\" of rooms\[2\] must be a name"):
        check_campus(broken(lambda bad: bad["rooms"][2].update({key: name})))


@pytest.mark.parametrize("key", ["deck_pattern", "deck_wall_face"])
@pytest.mark.parametrize("name", ["", "Paving", 0, True])
def test_a_deck_style_that_is_not_a_name_is_refused_and_named(key, name):
    with pytest.raises(CampusError, match=rf"\"{key}\" of the map must be a name"):
        check_campus(broken(lambda bad: bad.update({key: name})))


@pytest.mark.parametrize("face_height", [0, -8, 10.5, 11, 100])
def test_a_wall_face_height_outside_0_to_10_is_refused(face_height):
    with pytest.raises(CampusError, match="wall_face_height"):
        check_campus(broken(lambda bad: bad.update(wall_face_height=face_height)))


@pytest.mark.parametrize("face_height", ["8", None, True, float("nan"), float("inf"), 10 ** 400])
def test_a_wall_face_height_that_is_not_an_ordinary_number_is_refused(face_height):
    with pytest.raises(CampusError, match="wall_face_height"):
        check_campus(broken(lambda bad: bad.update(wall_face_height=face_height)))


# Rejected: decor

@pytest.mark.parametrize("decor", [{}, "mat", 5, None])
def test_decor_that_is_not_a_list_is_refused(decor):
    with pytest.raises(CampusError, match="\"decor\" of the map must be a list"):
        check_campus(broken(lambda bad: bad.update(decor=decor)))


@pytest.mark.parametrize("entry", [None, "mat", [300, 200, 20, 8]])
def test_a_decor_entry_that_is_not_an_object_is_refused_and_named(entry):
    with pytest.raises(CampusError, match=r"decor\[3\] must be an object"):
        check_campus(broken(lambda bad: bad["decor"].__setitem__(3, entry)))


@pytest.mark.parametrize("key", ["kind", "layer", "x", "y", "w", "h"])
def test_a_decor_entry_without_a_required_key_is_refused_and_named(key):
    with pytest.raises(CampusError, match=rf"decor\[1\] has no \"{key}\""):
        check_campus(broken(lambda bad: bad["decor"][1].pop(key)))


@pytest.mark.parametrize("change", [
    {"w": 0}, {"h": -3}, {"x": -1}, {"y": 665}, {"x": 670}, {"x": "300"}, {"w": float("nan")}, {"y": 10 ** 400},
])
def test_a_decor_entry_with_a_broken_rectangle_is_refused_and_named(change):
    with pytest.raises(CampusError, match=r"decor\[0\]"):
        check_campus(broken(a_decor_entry(**change)))


@pytest.mark.parametrize("layer", ["ceiling", "", "Floor", None, 1])
def test_a_decor_entry_on_an_unknown_layer_is_refused(layer):
    with pytest.raises(CampusError, match=r"\"layer\" of decor\[0\] must be \"floor\", \"wall\" or \"on\""):
        check_campus(broken(a_decor_entry(layer=layer)))


@pytest.mark.parametrize("kind", ["", "Coffee Machine", 7, None])
def test_a_decor_entry_whose_kind_is_not_a_name_is_refused(kind):
    with pytest.raises(CampusError, match=r"\"kind\" of decor\[0\] must be a name"):
        check_campus(broken(a_decor_entry(kind=kind)))


@pytest.mark.parametrize("key", ["colour_", "solid", "id", "color"])
def test_a_decor_entry_with_an_unknown_key_is_refused_and_names_the_key(key):
    with pytest.raises(CampusError, match=rf"decor\[0\] has the unknown key \"{key}\""):
        check_campus(broken(a_decor_entry(**{key: "x"})))


@pytest.mark.parametrize("words", ["", 5, None, ["SIGN"]])
def test_a_decor_text_that_is_not_a_text_is_refused(words):
    with pytest.raises(CampusError, match=r"\"text\" of decor\[0\] must be a text"):
        check_campus(broken(a_decor_entry(text=words)))


def test_a_decor_text_longer_than_40_characters_is_refused():
    with pytest.raises(CampusError, match=r"\"text\" of decor\[0\] is longer than 40"):
        check_campus(broken(a_decor_entry(text="X" * 41)))


@pytest.mark.parametrize("colour", ["green", "#3E9B4", "#3E9B4FF", "3E9B4F", "#GG9B4F", 0x3E9B4F, None])
def test_a_decor_colour_that_is_not_a_colour_is_refused(colour):
    with pytest.raises(CampusError, match=r"\"colour\" of decor\[0\] must be a colour"):
        check_campus(broken(a_decor_entry(colour=colour)))


# Rejected: the placing rules catch what they are meant to catch

def test_the_squeeze_rule_finds_the_old_gap_between_tree_3_and_the_hedge():
    tree = next(solid for solid in SOLIDS if solid["id"] == "deck-tree-3")
    old_hedge = {"x": 566, "y": 236, "w": 58, "h": 26}  # before S-111
    assert gap_between(tree, old_hedge) == 10


def test_solids_that_only_lie_diagonally_have_no_gap():
    assert gap_between({"x": 0, "y": 0, "w": 10, "h": 10}, {"x": 21, "y": 22, "w": 5, "h": 5}) is None


def test_a_gap_filled_by_a_third_solid_is_no_gap():
    above = {"x": 0, "y": 0, "w": 10, "h": 10}
    below = {"x": 0, "y": 22, "w": 10, "h": 10}
    filler = {"x": -5, "y": 10, "w": 30, "h": 12}
    assert gap_between(above, below) == 12
    assert gap_between(above, below, [above, below, filler]) is None


def test_a_sign_in_the_middle_of_a_room_touches_no_wall():
    sign = {"x": 540, "y": 470, "w": 10, "h": 5}
    walls = [solid for solid in SOLIDS if solid["kind"] == "wall"]
    assert not any(touches(sign, wall) for wall in walls)


def test_a_cup_beside_a_counter_lies_inside_no_solid():
    cup = {"x": 600, "y": 540, "w": 4, "h": 4}  # half on the hot counter (y 545), half on the floor
    assert not any(lies_inside(cup, solid) for solid in SOLIDS)


# The drawing, with the page's own draw.js and art files

@needs_node
def test_every_drawing_the_map_names_is_there():
    art = run_node("direct", {"campus": CAMPUS})["art"]
    for room in CAMPUS["rooms"]:
        assert room["pattern"] in art["floors"], room["id"]
        assert room["wall_face"] in art["faces"], room["id"]
    assert CAMPUS["deck_pattern"] in art["floors"]
    assert CAMPUS["deck_wall_face"] in art["faces"]
    for item in CAMPUS["decor"]:
        assert item["kind"] in art["decor"], item
    for kind in {solid["kind"] for solid in NEW_SOLIDS}:
        assert kind in art["kinds"], kind


@needs_node
def test_the_whole_map_draws_without_a_warning():
    assert run_node("direct", {"campus": CAMPUS})["warnings"] == []


@needs_node
def test_room_names_are_still_the_only_texts_equal_to_a_room_name():
    texts = [text["text"] for text in run_node("direct", {"campus": CAMPUS})["texts"]]
    for room in CAMPUS["rooms"]:
        assert texts.count(room["name"]) == 1, room["name"]
    signs = [item["text"] for item in CAMPUS["decor"] if "text" in item]
    assert "PINGO DOCE & GO" in texts
    assert set(signs) <= set(texts)


@needs_node
def test_a_drawing_that_fails_falls_back_to_the_plain_one_with_one_warning():
    # The art of the shelves throws: the four shelves are still drawn, in the
    # plain green of draw.js, the rest of the map goes on, and there is one
    # warning, not one per shelf.
    plain = run_node("direct", {"campus": CAMPUS})
    assert "#7DB55A" not in plain["fills"]
    failing = run_node("direct", {"campus": CAMPUS, "failingKind": "shelf"})
    assert "#7DB55A" in failing["fills"]
    assert len(failing["warnings"]) == 1
    assert [text["text"] for text in failing["texts"]].count("Main Deck") == 1
    assert "PANTRY" in [text["text"] for text in failing["texts"]]


def tiles_frames(frames):
    return run_node("tiles", {"campus": CAMPUS, "frames": frames})["frames"]


@needs_node
def test_tiles_cover_the_canvas_and_sit_on_whole_pixels():
    camera = {"scale": 9.846, "e": -3456.37, "f": -2211.81, "width": 2560, "height": 1600}
    [frame] = tiles_frames([camera])
    xs = sorted({copy_["x"] for copy_ in frame["copies"]})
    ys = sorted({copy_["y"] for copy_ in frame["copies"]})
    assert all(float(value).is_integer() for value in xs + ys)
    assert xs[0] <= 0 and xs[-1] + 512 >= camera["width"]
    assert ys[0] <= 0 and ys[-1] + 512 >= camera["height"]
    # Neighbouring tiles meet exactly: no seam, no overlap.
    assert all(right - left == 512 for left, right in zip(xs, xs[1:]))
    assert all(lower - upper == 512 for upper, lower in zip(ys, ys[1:]))
    assert len(frame["copies"]) == len(xs) * len(ys)


@needs_node
def test_tiles_are_drawn_once_and_again_only_for_a_new_zoom():
    camera = {"scale": 9.846, "e": -3456.37, "f": -2211.81, "width": 2560, "height": 1600}
    moved = dict(camera, e=camera["e"] - 3.4)  # the camera moved a little
    zoomed = dict(camera, scale=7.5)  # the window was resized
    first, again, after_moving, after_zooming = tiles_frames([camera, camera, moved, zoomed])
    assert first["newTiles"] == len(first["copies"])
    assert again["newTiles"] == 1  # nothing new is seen: one tile is drawn ahead
    assert after_moving["newTiles"] <= 4  # at most one new column of tiles
    assert after_zooming["newTiles"] == len(after_zooming["copies"])


@needs_node
def test_standing_still_draws_the_ring_around_the_picture_one_tile_per_frame_and_then_nothing():
    camera = {"scale": 9.846, "e": -3456.37, "f": -2211.81, "width": 2560, "height": 1600}
    frames = tiles_frames([camera] * 60)
    columns = len({copy_["x"] for copy_ in frames[0]["copies"]})
    rows = len({copy_["y"] for copy_ in frames[0]["copies"]})
    ring = (columns + 2) * (rows + 2) - columns * rows
    later = [frame["newTiles"] for frame in frames[1:]]
    assert max(later) == 1
    assert sum(later) == ring
    assert later[-5:] == [0, 0, 0, 0, 0]


@needs_node
def test_walking_across_the_whole_map_keeps_a_bounded_number_of_tiles():
    # Every tile made is kept or forgotten; walking far must not make the
    # stand-in page create a tile for every frame again and again.
    frames = [{"scale": 9.846, "e": 1280 - x * 9.846, "f": 800 - 300 * 9.846, "width": 2560, "height": 1600}
              for x in range(0, 680, 20)]
    result = tiles_frames(frames + list(reversed(frames)))
    made_on_the_way_back = sum(frame["newTiles"] for frame in result[len(frames):])
    made_on_the_way_out = sum(frame["newTiles"] for frame in result[:len(frames)])
    assert made_on_the_way_back < made_on_the_way_out
