"""Hanna's shrubs and floors on the smoothed map (M2-1.21).

Hanna's drawings (her commits df02681 and 3622182) are taken onto the map
of S-141 and S-144 without changing what blocks:

- campus.json is the map of main (1632544) apart from the floor colours
  and patterns of the rooms and the colours of the floor decor: its counts
  and a digest of everything else are pinned here;
- the six deck bushes keep their square trim: at least 90 % of each 28 x 28
  solid is drawn, and nothing outside it; the hedge is drawn inside its
  solid and its hiding spot's dashed circle stays visible on it;
- every room name stays readable on the new floors (WCAG contrast of at
  least 4.5 : 1 against the floor colour, the darkest and lightest colour
  of its pattern and what lies behind the letters); the dark edge of a
  station's outline and of a hiding spot is drawn in the same colour as
  the names, so it keeps the same contrast;
- Mon Café's floor is the new `cafe-tiles` pattern;
- the study area (Hanna's commit a916099, the `pool` kind of deck-pool):
  her two tables with chairs stand on a terrace as large as the solid, at
  least 90 % of it drawn and nothing outside it;
- the page draws the map without a console error or warning.

The browser part is hanna_floors_and_shrubs_in_browser.js.
"""

import contextlib
import hashlib
import json
import socket
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from server.world.campus import load_campus
from test_play_campus_detail import NODE, node_environment, playwright_works

GAME = Path(__file__).resolve().parents[1]
CAMPUS_FILE = GAME / "client" / "js" / "world" / "campus.json"
BROWSER_SCRIPT = Path(__file__).with_name("hanna_floors_and_shrubs_in_browser.js")

# The colour of the room names (OUTLINE in draw.js). The dark edge of the
# station outlines and the dashed outline of the hiding spots are drawn in
# the same colour.
NAME_COLOUR = "#2E2A3B"

# WCAG: normal text needs 4.5 : 1, a graphic part (an outline) 3 : 1.
LEAST_TEXT_CONTRAST = 4.5
LEAST_GRAPHIC_CONTRAST = 3

# What is drawn is what blocks (S-144 (4)).
LEAST_DRAWN_SHARE = 0.9


# ---- The map is main's, apart from colours --------------------------------

# Room keys and floor decor keys that only change how the map looks.
ROOM_LOOKS = ("floor", "pattern")
FLOOR_DECOR_LOOKS = ("colour",)


def without_looks(campus):
    """A copy of the map without the keys Hanna's floors may change."""
    copy = json.loads(json.dumps(campus))
    for room in copy.get("rooms", []):
        for key in ROOM_LOOKS:
            room.pop(key, None)
    for item in copy.get("decor", []):
        if item.get("layer") == "floor":
            for key in FLOOR_DECOR_LOOKS:
                item.pop(key, None)
    return copy


def differences(before, after, path="map"):
    """The places (as paths) where two maps differ, apart from the looks."""
    return compare(without_looks(before), without_looks(after), path)


def compare(before, after, path):
    if isinstance(before, dict) and isinstance(after, dict):
        found = []
        for key in sorted(set(before) | set(after)):
            found += compare(before.get(key), after.get(key), f"{path}.{key}")
        return found
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            return [f"{path} has {len(after)} entries instead of {len(before)}"]
        found = []
        for index, (old, new) in enumerate(zip(before, after)):
            found += compare(old, new, f"{path}[{index}]")
        return found
    return [] if before == after else [path]


def current_map():
    return json.loads(CAMPUS_FILE.read_text(encoding="utf-8"))


def digest(campus):
    """A fingerprint of everything in the map apart from the looks: ids,
    places, sizes, labels, doors, stations, hiding spots, the button."""
    text = json.dumps(without_looks(campus), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def counts(campus):
    return {key: len(campus[key]) for key in ("rooms", "solids", "decor", "stations", "hiding_spots", "doors")}


# The map of main 1632544 (after PR 86 moved the emergency button), apart
# from the looks. Hanna's drawing must not change any of it. When the map is
# changed on purpose later (a moved solid, a new station, ...), measure these
# again with counts() and digest() and update them here, naming the change.
MAIN_COUNTS = {"rooms": 5, "solids": 107, "decor": 76, "stations": 12, "hiding_spots": 4, "doors": 5}
MAIN_DIGEST = "9b1d9509b47d2463624f22f5ee959a8564cb25e11cbf8b1f7312e1735a105ab4"

# Hanna's floors (3622182): room id -> (floor colour, pattern).
HANNAS_FLOORS = {
    "lecture-hall": ("#E8BF88", "planks"),
    "mon-cafe": ("#DDAC99", "cafe-tiles"),
    "canteen": ("#BCE2DC", "mint-tiles"),
    "ctt": ("#CACDEC", "speckled"),
    "pingo-doce": ("#D8D0A1", "diamond-tiles"),
}


def test_the_map_has_mains_number_of_solids_decor_stations_spots_and_doors():
    assert counts(current_map()) == MAIN_COUNTS


def test_the_map_is_mains_apart_from_floor_colours_and_patterns():
    assert digest(current_map()) == MAIN_DIGEST


def test_the_rooms_have_hannas_floors():
    floors = {room["id"]: (room["floor"], room["pattern"]) for room in current_map()["rooms"]}
    assert floors == HANNAS_FLOORS


def test_a_new_floor_colour_pattern_or_tier_colour_keeps_the_digest():
    changed = current_map()
    changed["rooms"][0]["floor"] = "#000000"
    changed["rooms"][1]["pattern"] = "planks"
    next(item for item in changed["decor"] if item["kind"] == "tier")["colour"] = "#123456"
    assert digest(changed) == digest(current_map())


def test_a_bush_moved_by_one_unit_changes_the_digest():
    changed = current_map()
    next(solid for solid in changed["solids"] if solid["id"] == "deck-tree-1")["x"] += 1
    assert digest(changed) != digest(current_map())


def test_a_moved_room_name_or_button_changes_the_digest():
    # Edge cases: things that are no solid are pinned too.
    name = current_map()
    name["rooms"][0]["label"]["y"] += 1
    button = current_map()
    button["button"]["x"] += 1
    assert digest(name) != digest(current_map())
    assert digest(button) != digest(current_map())


def test_a_removed_solid_changes_the_counts():
    changed = current_map()
    changed["solids"].pop()
    assert counts(changed)["solids"] == MAIN_COUNTS["solids"] - 1
def test_a_new_floor_colour_pattern_and_tier_colour_are_no_difference():
    before = current_map()
    after = json.loads(json.dumps(before))
    after["rooms"][0]["floor"] = "#000000"
    after["rooms"][1]["pattern"] = "planks"
    tier = next(item for item in after["decor"] if item["kind"] == "tier")
    tier["colour"] = "#123456"
    assert differences(before, after) == []


def test_a_moved_bush_is_found():
    before = current_map()
    after = json.loads(json.dumps(before))
    bush = next(solid for solid in after["solids"] if solid["id"] == "deck-tree-1")
    bush["x"] += 1
    index = after["solids"].index(bush)
    assert differences(before, after) == [f"map.solids[{index}].x"]


def test_a_removed_or_added_solid_is_found():
    before = current_map()
    fewer = json.loads(json.dumps(before))
    fewer["solids"].pop()
    more = json.loads(json.dumps(before))
    more["solids"].append({"id": "extra", "kind": "tree", "x": 0, "y": 0, "w": 1, "h": 1})
    assert differences(before, fewer) == [f"map.solids has {len(before['solids']) - 1} entries instead of {len(before['solids'])}"]
    assert differences(before, more) != []


@pytest.mark.parametrize("key, value", [("label", {"x": 1, "y": 1}), ("x", 0), ("name", "Café")])
def test_a_room_key_other_than_floor_and_pattern_is_found(key, value):
    before = current_map()
    after = json.loads(json.dumps(before))
    after["rooms"][1][key] = value
    found = differences(before, after)
    assert found and all(place.startswith(f"map.rooms[1].{key}") for place in found)


def test_the_colour_of_decor_that_is_not_on_the_floor_is_found():
    # Edge case: only floor decor may change its colour (a sign on a wall
    # may not).
    before = current_map()
    after = json.loads(json.dumps(before))
    sign = next(item for item in after["decor"] if item["layer"] == "wall" and "colour" in item)
    sign["colour"] = "#000000"
    assert len(differences(before, after)) == 1


def test_the_server_still_loads_the_map():
    campus = load_campus()
    assert [room["id"] for room in campus["rooms"]] == [room["id"] for room in current_map()["rooms"]]


# ---- Mon Café has the new cafe-tiles floor --------------------------------


def patterns_without_drawing(campus, drawn_patterns):
    """The rooms whose floor pattern no art file draws."""
    return [room["id"] for room in campus["rooms"] if room.get("pattern") not in drawn_patterns]


def test_mon_cafe_names_the_cafe_tiles():
    room = next(room for room in current_map()["rooms"] if room["id"] == "mon-cafe")
    assert room["pattern"] == "cafe-tiles"


def test_a_room_naming_a_pattern_nobody_draws_is_found():
    campus = current_map()
    assert patterns_without_drawing(campus, {"planks", "mint-tiles", "speckled", "diamond-tiles"}) == ["mon-cafe"]


# ---- Contrast (WCAG 2) ----------------------------------------------------


def rgb(colour):
    """[red, green, blue] from "#RRGGBB" or from a list of three numbers."""
    if isinstance(colour, str):
        return [int(colour[i:i + 2], 16) for i in (1, 3, 5)]
    return list(colour)


def luminance(colour):
    def linear(channel):
        channel /= 255
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in rgb(colour))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first, second):
    """The WCAG contrast ratio of two colours, from 1 (the same) to 21."""
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def backgrounds(room):
    """Every colour a room's name may stand on: the floor colour, the
    darkest and lightest colour of the pattern and behind the letters."""
    return {
        "floor": room["floor"],
        "pattern darkest": room["floorPattern"]["darkest"],
        "pattern lightest": room["floorPattern"]["lightest"],
        "behind name darkest": room["behindName"]["darkest"],
        "behind name lightest": room["behindName"]["lightest"],
    }


def hard_to_read(rooms, least=LEAST_TEXT_CONTRAST):
    """(room, background, ratio) for every background a name is too faint on."""
    found = []
    for room in rooms:
        for name, colour in backgrounds(room).items():
            ratio = contrast(NAME_COLOUR, colour)
            if ratio < least:
                found.append((room["id"], name, round(ratio, 2)))
    return found


def test_black_on_white_is_21_and_a_colour_on_itself_is_1():
    assert contrast("#000000", "#FFFFFF") == pytest.approx(21)
    assert contrast("#DDAC99", "#DDAC99") == pytest.approx(1)
    assert contrast([0, 0, 0], "#FFFFFF") == contrast("#FFFFFF", "#000000")


def test_hannas_floor_colours_keep_the_names_readable():
    for room in current_map()["rooms"]:
        assert contrast(NAME_COLOUR, room["floor"]) >= LEAST_TEXT_CONTRAST, room["id"]


def a_room(floor, darkest=None):
    darkest = darkest or rgb(floor)
    return {
        "id": "room", "floor": floor,
        "floorPattern": {"darkest": darkest, "lightest": rgb(floor)},
        "behindName": {"darkest": darkest, "lightest": rgb(floor)},
    }


def test_a_dark_floor_is_found():
    # Rejected: a mid grey gives the names about 3 : 1.
    assert [found[1] for found in hard_to_read([a_room("#7A7A7A")])] == [
        "floor", "pattern darkest", "pattern lightest", "behind name darkest", "behind name lightest",
    ]


def test_a_light_floor_with_a_dark_tile_is_found():
    # Rejected: the floor is fine, one tile of the pattern is not.
    assert [found[1] for found in hard_to_read([a_room("#F3F0E9", [110, 110, 110])])] == [
        "pattern darkest", "behind name darkest",
    ]


def test_a_contrast_exactly_at_the_limit_is_readable():
    # Edge case: the limit itself is enough (here the ratio of white).
    assert hard_to_read([a_room("#FFFFFF")], least=contrast(NAME_COLOUR, "#FFFFFF")) == []


# ---- In Chromium ----------------------------------------------------------

needs_chromium = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


@pytest.fixture(scope="module")
def drawn():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app", "--port", str(port)],
        cwd=GAME, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            with contextlib.suppress(OSError):
                urllib.request.urlopen(base + "/health", timeout=1)
                break
            time.sleep(0.1)
        finished = subprocess.run(
            [NODE, str(BROWSER_SCRIPT), base],
            env=node_environment(), capture_output=True, text=True, timeout=240, check=False,
        )
        assert finished.returncode == 0, finished.stderr
        result = json.loads(finished.stdout)
        result["solids"] = {row["id"]: row for row in result["solids"]}
        return result
    finally:
        server.terminate()
        server.wait(timeout=10)


def too_little_drawn(rows, least=LEAST_DRAWN_SHARE):
    return [row["id"] for row in rows if row["share"] < least]


def drawn_outside(rows):
    return [row["id"] for row in rows if row["outside"] > 0]


BUSHES = [f"deck-tree-{number}" for number in range(1, 7)]


def test_a_bush_drawn_to_80_percent_is_too_little():
    rows = [{"id": "a", "share": 0.8, "outside": 0}, {"id": "b", "share": 0.95, "outside": 0}]
    assert too_little_drawn(rows) == ["a"]


def test_a_bush_drawn_to_exactly_90_percent_is_enough():
    assert too_little_drawn([{"id": "a", "share": 0.9, "outside": 0}]) == []


def test_a_single_pixel_outside_the_solid_is_found():
    rows = [{"id": "a", "share": 1, "outside": 1}, {"id": "b", "share": 1, "outside": 0}]
    assert drawn_outside(rows) == ["a"]


@needs_chromium
def test_the_page_draws_the_map_without_a_console_error_or_warning(drawn):
    assert drawn["console"] == []


@needs_chromium
def test_every_deck_bush_is_drawn_to_at_least_90_percent_of_its_solid(drawn):
    assert too_little_drawn([drawn["solids"][bush] for bush in BUSHES]) == []


@needs_chromium
def test_no_deck_bush_and_not_the_hedge_is_drawn_outside_its_solid(drawn):
    assert drawn_outside([drawn["solids"][solid] for solid in BUSHES + ["deck-hedge"]]) == []


@needs_chromium
def test_the_study_area_is_drawn_to_at_least_90_percent_of_its_solid_and_not_outside(drawn):
    study = drawn["solids"]["deck-pool"]
    assert study["kind"] == "pool"
    assert too_little_drawn([study]) == []
    assert drawn_outside([study]) == []


# The drawing check counts a pixel as drawn when red + green + blue differ
# by more than 60 from the paving (play_map_polish_in_browser.js).
CLEAR = 60
DECK_ART = GAME / "client" / "js" / "world" / "art" / "deck.js"


def differs_clearly(first, second):
    return sum(abs(a - b) for a, b in zip(rgb(first), rgb(second))) > CLEAR


def table_top():
    source = DECK_ART.read_text(encoding="utf-8")
    return source.split('var TABLE_TOP = "', 1)[1][:7]


def test_a_pure_white_table_would_not_count_as_drawn_on_the_paving():
    # Rejected: white differs from the deck's paving by only 49.
    assert not differs_clearly("#FFFFFF", current_map()["colours"]["deck"])


def test_the_table_top_counts_as_drawn_on_the_paving():
    assert differs_clearly(table_top(), current_map()["colours"]["deck"])


@needs_chromium
def test_the_hedge_with_its_round_bushes_is_still_seen(drawn):
    # play_campus_detail_in_browser.js asks for at least a quarter of every
    # solid; the hedge's four round crowns leave room around them.
    assert drawn["solids"]["deck-hedge"]["share"] >= 0.25


def middle(colours):
    return [statistics.median(colour[channel] for colour in colours) for channel in range(3)]


@needs_chromium
def test_the_dashed_circle_of_the_hiding_spot_stands_out_on_the_hedge(drawn):
    spot = drawn["spot"]
    assert (spot["x"], spot["y"]) == (595, 249)
    dash = middle(spot["dashes"])
    assert contrast(dash, middle(spot["disc"])) >= LEAST_GRAPHIC_CONTRAST
    assert contrast(dash, middle(spot["around"])) >= LEAST_GRAPHIC_CONTRAST


@needs_chromium
def test_every_room_name_is_readable_on_its_new_floor_and_pattern(drawn):
    assert hard_to_read(drawn["rooms"]) == []


@needs_chromium
def test_the_pages_art_draws_the_cafe_tiles_and_every_pattern_the_map_names(drawn):
    assert "cafe-tiles" in drawn["floorPatterns"]
    assert patterns_without_drawing(current_map(), set(drawn["floorPatterns"])) == []
