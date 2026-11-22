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
- the corridor's name "Academic Hall" stands in the game's ink on free
  corridor floor (Felix, 2026-11-22), readable on the terrazzo;
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
# Measured again for M3-1.1 (S-185): the map gained "classic_vision_range": 120.
# Without that key the digest is main's old one, 9b1d9509...e1735a105ab4.
MAIN_DIGEST = "0882e72aa95a0ca54bba4dee3285fbe75c6b2c96c6311a5d3f19f647e019483d"

# Hanna's floors (3622182): room id -> (floor colour, pattern).
HANNAS_FLOORS = {
    "lecture-hall": ("#E8BF88", "planks"),
    "mon-cafe": ("#DDAC99", "cafe-tiles"),
    "canteen": ("#BCE2DC", "mint-tiles"),
    "ctt": ("#CACDEC", "speckled"),
    "pingo-doce": ("#D8D0A1", "diamond-tiles"),
}


# Felix, 2026-11-22: "Academic Hall" is to stand "in schwarzer Schrift auf
# dem Flur" (in black letters on the corridor floor), no longer in white on
# the slat wall. This one decor entry differs from main; the digest is taken
# with main's entry put back.
ACADEMIC_HALL_ON_MAIN = {"kind": "lettering", "layer": "wall", "x": 412, "y": 173, "w": 88, "h": 8, "text": "ACADEMIC HALL"}
ACADEMIC_HALL = {"kind": "lettering", "layer": "floor", "x": 300, "y": 198, "w": 92, "h": 13, "text": "Academic Hall"}


def with_mains_academic_hall(campus):
    """A copy of the map with main's "ACADEMIC HALL" on the slat wall."""
    copy = json.loads(json.dumps(campus))
    copy["decor"] = [dict(ACADEMIC_HALL_ON_MAIN) if item == ACADEMIC_HALL else item for item in copy["decor"]]
    return copy


def test_the_map_has_mains_number_of_solids_decor_stations_spots_and_doors():
    assert counts(current_map()) == MAIN_COUNTS


def test_the_map_is_mains_apart_from_floor_colours_patterns_and_the_corridor_name():
    assert ACADEMIC_HALL in current_map()["decor"]
    assert digest(with_mains_academic_hall(current_map())) == MAIN_DIGEST


def test_any_other_change_to_the_corridor_name_changes_the_digest():
    changed = current_map()
    next(item for item in changed["decor"] if item == ACADEMIC_HALL)["y"] += 1
    assert digest(with_mains_academic_hall(changed)) != MAIN_DIGEST


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


@pytest.mark.parametrize("key, value", [("label", {"x": 1, "y": 1}), ("x", 0), ("name", "Café")])
def test_a_room_key_other_than_floor_and_pattern_changes_the_digest(key, value):
    changed = current_map()
    changed["rooms"][1][key] = value
    assert digest(changed) != digest(current_map())


def test_a_moved_button_changes_the_digest():
    # Edge case: things that are no solid are pinned too.
    changed = current_map()
    changed["button"]["x"] += 1
    assert digest(changed) != digest(current_map())


def test_the_colour_of_decor_that_is_not_on_the_floor_changes_the_digest():
    # Edge case: only floor decor may change its colour (a sign on a wall
    # may not).
    changed = current_map()
    sign = next(item for item in changed["decor"] if item["layer"] == "wall" and "colour" in item)
    sign["colour"] = "#000000"
    assert digest(changed) != digest(current_map())


def test_a_removed_or_added_solid_changes_the_counts():
    fewer = current_map()
    fewer["solids"].pop()
    more = current_map()
    more["solids"].append({"id": "extra", "kind": "tree", "x": 0, "y": 0, "w": 1, "h": 1})
    assert counts(fewer)["solids"] == MAIN_COUNTS["solids"] - 1
    assert counts(more)["solids"] == MAIN_COUNTS["solids"] + 1


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


# ---- The corridor's name on the floor -------------------------------------

# The corridor's floor: the terrazzo below the slat wall's face (the face of
# the wall at y 167-173 is 8 high) down to the corridor wall at y 227.
CORRIDOR_FLOOR = {"x": 23, "y": 181, "w": 634, "h": 46}
# A station's object and its outline are drawn within this many units of
# its centre (OBJECT_HALF_SIZE in draw.js).
STATION_REACH = 20


def overlaps(first, second):
    """True when two rectangles share more than an edge."""
    return (first["x"] < second["x"] + second["w"] and second["x"] < first["x"] + first["w"]
            and first["y"] < second["y"] + second["h"] and second["y"] < first["y"] + first["h"])


def inside(inner, outer):
    return (outer["x"] <= inner["x"] and inner["x"] + inner["w"] <= outer["x"] + outer["w"]
            and outer["y"] <= inner["y"] and inner["y"] + inner["h"] <= outer["y"] + outer["h"])


def in_the_way(name, campus):
    """What a floor name's rectangle would lie on: solids, doors, station
    objects, hiding spots and every decor but the terrazzo it is written on
    (and but the corridor's name itself, which `name` may stand in for)."""
    found = [solid["id"] for solid in campus["solids"] if overlaps(name, solid)]
    found += [f"door of {door['room']}" for door in campus["doors"] if overlaps(name, door)]
    for station in campus["stations"]:
        reach = {"x": station["x"] - STATION_REACH, "y": station["y"] - STATION_REACH,
                 "w": 2 * STATION_REACH, "h": 2 * STATION_REACH}
        if overlaps(name, reach):
            found.append(f"station {station['id']}")
    for spot in campus["hiding_spots"]:
        circle = {"x": spot["x"] - spot["r"], "y": spot["y"] - spot["r"], "w": 2 * spot["r"], "h": 2 * spot["r"]}
        if overlaps(name, circle):
            found.append("hiding spot")
    found += [item["kind"] for item in campus["decor"]
              if item.get("text") != name.get("text") and item["kind"] != "terrazzo" and overlaps(name, item)]
    return found


def corridor_name():
    return next(item for item in current_map()["decor"] if item.get("text") == "Academic Hall")


def test_the_corridor_name_is_floor_decor_in_title_case():
    name = corridor_name()
    assert (name["kind"], name["layer"]) == ("lettering", "floor")
    assert not any(item.get("text") == "ACADEMIC HALL" for item in current_map()["decor"])


def test_the_corridor_name_lies_on_the_corridor_floor():
    assert inside(corridor_name(), CORRIDOR_FLOOR)


def test_the_corridor_name_lies_on_nothing():
    # Not on a solid, a door, a station, a hiding spot, a light pool or the
    # door leaves of the corridor wall.
    assert in_the_way(corridor_name(), current_map()) == []


def test_the_corridor_name_stands_between_two_light_pools_below_the_cafe_door():
    name = corridor_name()
    pools = sorted(item["x"] for item in current_map()["decor"]
                   if item["kind"] == "light-pool" and overlaps(item, CORRIDOR_FLOOR))
    assert pools[1] + 26 <= name["x"] and name["x"] + name["w"] <= pools[2]


def test_the_name_in_its_old_place_on_the_wall_is_not_on_the_floor():
    # Rejected: main's place on the slat wall's face.
    assert not inside(ACADEMIC_HALL_ON_MAIN, CORRIDOR_FLOOR)


def test_a_name_over_a_sofa_or_a_light_pool_is_found():
    # Rejected: in front of the sofas, and one unit further left, onto the
    # second light pool.
    campus = current_map()
    over_sofa = dict(ACADEMIC_HALL, x=180, y=178)
    onto_pool = dict(ACADEMIC_HALL, x=293)
    assert "corridor-sofa-1" in in_the_way(over_sofa, campus)
    assert in_the_way(onto_pool, campus) == ["light-pool"]


def test_a_name_that_only_touches_a_light_pool_is_free():
    # Edge case: touching an edge is not lying on it.
    assert in_the_way(dict(ACADEMIC_HALL, x=294), current_map()) == []


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
def test_the_corridor_name_is_drawn_inside_its_entry_and_on_the_corridor_floor(drawn):
    name = drawn["corridorName"]
    assert name["entry"] == ACADEMIC_HALL
    assert inside(name["box"], ACADEMIC_HALL)
    assert inside(name["box"], CORRIDOR_FLOOR)
    # About as large as the room names (13 units high letters, 90 wide).
    assert name["box"]["w"] >= 80 and name["box"]["h"] >= 9


@needs_chromium
def test_the_corridor_name_is_drawn_in_the_games_ink(drawn):
    assert contrast(drawn["corridorName"]["ink"], NAME_COLOUR) < 1.1


@needs_chromium
def test_the_corridor_name_is_readable_on_the_terrazzo(drawn):
    behind = drawn["corridorName"]["behind"]
    assert contrast(NAME_COLOUR, behind["darkest"]) >= LEAST_TEXT_CONTRAST
    assert contrast(NAME_COLOUR, behind["lightest"]) >= LEAST_TEXT_CONTRAST


@needs_chromium
def test_the_pages_art_draws_the_cafe_tiles_and_every_pattern_the_map_names(drawn):
    assert "cafe-tiles" in drawn["floorPatterns"]
    assert patterns_without_drawing(current_map(), set(drawn["floorPatterns"])) == []
