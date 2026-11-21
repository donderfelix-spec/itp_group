"""The room and deck names as the browser draws them (M1-1.6), checked by the tester.

test_room_labels.py checks the numbers in the map file. These tests check
what the page does with them and what the drawn text covers:

- The page's own draw.js runs in Node (tests/draw_in_node.js) with a canvas
  that writes down every text. So a test sees where each name is really
  drawn, and that the drawing follows the map file, not a rule of its own.
- The space a drawn name takes may touch no furniture, wall, door, station,
  hiding spot or the button, in every room, not only on the deck. And
  "Main Deck" may not lie under a character standing on the spawn point.

Without Node the tests that run draw.js are skipped; CI has Node.
"""

import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from server.world.campus import load_campus

CAMPUS = load_campus()
TESTS = Path(__file__).resolve().parent
DRAW_IN_NODE = TESTS / "draw_in_node.js"
WORLD_JS = TESTS.parent / "client" / "js" / "world" / "world.js"

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

# The widest letter of a name in bold 13 px, in map units. Measured in
# Chromium (system-ui): "Pingo Doce" is 72.1 units wide, 7.2 per letter, the
# widest of the six names. 7.5 leaves a little room for other fonts.
WIDTH_PER_LETTER_AT_13 = 7.5
# Half the height of a line of bold 13 px text: Chromium measures 11 units
# from the top of a capital to the bottom of the letters.
HALF_TEXT_HEIGHT = 7


def drawn_texts(campus):
    """Every text that draw.js draws for this map: a list of {text, x, y, font}."""
    finished = subprocess.run(
        [NODE, str(DRAW_IN_NODE)],
        input=json.dumps(campus),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def where_drawn(texts, words):
    """The places (x, y) where `words` is drawn."""
    return [(text["x"], text["y"]) for text in texts if text["text"] == words]


def font_size(texts, words):
    font = next(text["font"] for text in texts if text["text"] == words)
    return int(re.search(r"(\d+)px", font).group(1))


def text_box(words, x, y, size):
    """The rectangle a name drawn with its middle at (x, y) covers, about."""
    half_width = len(words) * WIDTH_PER_LETTER_AT_13 * size / 13 / 2
    return {"left": x - half_width, "right": x + half_width,
            "top": y - HALF_TEXT_HEIGHT, "bottom": y + HALF_TEXT_HEIGHT}


def apart(box, rectangle):
    return (rectangle["x"] + rectangle["w"] <= box["left"] or rectangle["x"] >= box["right"]
            or rectangle["y"] + rectangle["h"] <= box["top"] or rectangle["y"] >= box["bottom"])


def as_rectangle(circle):
    return {"x": circle["x"] - circle["r"], "y": circle["y"] - circle["r"],
            "w": 2 * circle["r"], "h": 2 * circle["r"]}


def everything_drawn_on_the_map(campus):
    """(what, rectangle) for every solid, door, station, hiding spot and the button."""
    things = [(solid["id"], solid) for solid in campus["solids"]]
    things += [(f"door of {door['room']}", door) for door in campus["doors"]]
    things += [(f"station {station['id']}", as_rectangle(station)) for station in campus["stations"]]
    things += [(f"hiding spot {index}", as_rectangle(spot)) for index, spot in enumerate(campus["hiding_spots"])]
    things.append(("button", as_rectangle(campus["button"])))
    return things


def world_js_number(name):
    """A number written as `var NAME = number;` in world.js."""
    match = re.search(rf"var {name} = ([\d.]+);", WORLD_JS.read_text(encoding="utf-8"))
    assert match, name
    return float(match.group(1))


# Accepted: the real map, as draw.js draws it

@needs_node
@pytest.mark.parametrize("room", CAMPUS["rooms"], ids=lambda room: room["id"])
def test_every_room_name_is_drawn_once_at_its_label(room):
    texts = drawn_texts(CAMPUS)
    assert where_drawn(texts, room["name"]) == [(room["label"]["x"], room["label"]["y"])]


@needs_node
def test_main_deck_is_drawn_once_at_deck_label_and_not_on_the_spawn():
    texts = drawn_texts(CAMPUS)
    label = CAMPUS["deck_label"]
    spawn = CAMPUS["spawn"]
    assert where_drawn(texts, "Main Deck") == [(label["x"], label["y"])]
    assert (spawn["x"], spawn["y"]) not in [(text["x"], text["y"]) for text in texts]


@needs_node
def test_the_drawing_follows_the_map_file_and_not_a_rule_of_its_own():
    moved = copy.deepcopy(CAMPUS)
    moved["rooms"][4]["label"] = {"x": 470, "y": 520}
    moved["deck_label"] = {"name": "Sun Deck", "x": 250, "y": 400}
    texts = drawn_texts(moved)
    assert where_drawn(texts, "Pingo Doce") == [(470, 520)]
    assert where_drawn(texts, "Sun Deck") == [(250, 400)]
    assert where_drawn(texts, "Main Deck") == []


# What the drawn names cover

@needs_node
@pytest.mark.parametrize("room", CAMPUS["rooms"], ids=lambda room: room["id"])
def test_a_room_name_touches_no_furniture_wall_door_or_station(room):
    texts = drawn_texts(CAMPUS)
    [(x, y)] = where_drawn(texts, room["name"])
    box = text_box(room["name"], x, y, font_size(texts, room["name"]))
    for what, rectangle in everything_drawn_on_the_map(CAMPUS):
        assert apart(box, rectangle), f"{room['name']} covers {what}"


def test_pingo_doce_stands_above_the_right_shelf():
    # The sketch: the name is at the right of the room, above the fourth shelf.
    label = CAMPUS["rooms"][4]["label"]
    box = text_box("Pingo Doce", label["x"], label["y"], 13)
    shelf = next(solid for solid in CAMPUS["solids"] if solid["id"] == "pingo-doce-shelf-4")
    assert box["left"] <= shelf["x"] and shelf["x"] + shelf["w"] <= box["right"]
    assert box["bottom"] < shelf["y"]


def test_main_deck_lies_under_no_character_standing_on_the_spawn():
    # world.js draws a character CHARACTER_HEIGHT tall with its feet
    # FEET_BELOW_POSITION below its position. Its width is about half its
    # height; 30 units is more than that. The name tags stack upwards from
    # the head, so nothing of a player reaches below the feet.
    height = world_js_number("CHARACTER_HEIGHT")
    feet_below = world_js_number("FEET_BELOW_POSITION")
    spawn = CAMPUS["spawn"]
    character = {"x": spawn["x"] - 15, "y": spawn["y"] + feet_below - height, "w": 30, "h": height}
    label = CAMPUS["deck_label"]
    assert apart(text_box(label["name"], label["x"], label["y"], 13), character)


# Edge cases: a map without labels does not break the drawing

@needs_node
def test_a_room_without_label_is_left_out_and_the_others_are_still_drawn():
    without = copy.deepcopy(CAMPUS)
    without["rooms"][0].pop("label")
    texts = drawn_texts(without)
    assert where_drawn(texts, "Lecture Hall") == []
    assert where_drawn(texts, "Pingo Doce") == [(614, 421)]
    assert where_drawn(texts, "Main Deck") == [(365, 350)]


@needs_node
def test_a_map_without_deck_label_draws_no_deck_name_and_still_the_rooms():
    without = copy.deepcopy(CAMPUS)
    without.pop("deck_label")
    texts = drawn_texts(without)
    assert where_drawn(texts, "Main Deck") == []
    assert len([text for text in texts if text["text"] in {room["name"] for room in CAMPUS["rooms"]}]) == 5
