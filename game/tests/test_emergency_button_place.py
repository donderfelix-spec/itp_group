"""The red emergency button stands on free paving in the centre of the Main Deck (M3-4.23, S-147).

The circle that counts is the button's radius plus the "E Emergency" range
(REPORT_RANGE, 2 map units, client/js/world/world.js `isAtEmergencyButton`):
everything a player standing at the button's edge could be confused with must
lie outside it. With the real map file, that circle

- lies inside the deck polygon (`deck` points);
- touches no solid, no decor item, no hiding spot, no station circle and no
  drawn station object, shadow or number tag (the boxes measured in
  test_map_polish.py);
- keeps clear of the drawn "Main Deck" name: 13 px text centred at
  `deck_label`, taken as a conservative box of +-40 x +-7 around that point;
- keeps clear of the spawn by more than its own radius, so the players who
  stand at the spawn after a meeting do not stand on the button.

The button stands centred under the "Main Deck" name (S-147); its old place
right of the hedge, (642, 249), was free paving too but not central, so the
centre check rejects it. A circle on the pool, on station 12 or on the name
is rejected by the clearance check.

Edge case, decided here: a circle that only touches the edge of a solid or
box (distance exactly equal to the radius) counts as touching, so it is
rejected. The circle must stay strictly clear. A circle exactly on the deck
polygon's edge counts as inside: the deck's edge is its walls' inner side and
the button may reach it.
"""

import math

import pytest

from server.world.campus import load_campus
from server.world.movement import is_free
from test_map_polish import SHADOW_BOXES, STATION_BOXES, TAG_BOXES

CAMPUS = load_campus()
BUTTON = CAMPUS["button"]
# The "E Emergency" range beyond the button's radius (world.js REPORT_RANGE).
HINT_RANGE = 2
HINT_RADIUS = BUTTON["r"] + HINT_RANGE
# A conservative box for "Main Deck" in 13 px text centred at deck_label.
LABEL_HALF_WIDTH = 40
LABEL_HALF_HEIGHT = 7


def label_box(label=CAMPUS["deck_label"]):
    return {
        "x": label["x"] - LABEL_HALF_WIDTH, "y": label["y"] - LABEL_HALF_HEIGHT,
        "w": 2 * LABEL_HALF_WIDTH, "h": 2 * LABEL_HALF_HEIGHT,
    }


def station_boxes():
    """Every drawn station object, its shadow and its number tag, as map rectangles."""
    boxes = []
    for station in CAMPUS["stations"]:
        for table in (STATION_BOXES, SHADOW_BOXES, TAG_BOXES):
            if station["id"] in table:
                left, top, right, bottom = table[station["id"]]
                boxes.append({
                    "id": f"station {station['id']}",
                    "x": station["x"] + left, "y": station["y"] + top, "w": right - left, "h": bottom - top,
                })
    return boxes


def distance_to_box(x, y, box):
    closest_x = min(max(x, box["x"]), box["x"] + box["w"])
    closest_y = min(max(y, box["y"]), box["y"] + box["h"])
    return math.dist((x, y), (closest_x, closest_y))


def distance_to_segment(point, start, end):
    (px, py), (ax, ay), (bx, by) = point, start, end
    length_squared = (bx - ax) ** 2 + (by - ay) ** 2
    t = 0.0 if length_squared == 0 else max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / length_squared))
    return math.dist(point, (ax + t * (bx - ax), ay + t * (by - ay)))


def point_in_polygon(x, y, points):
    """Ray casting; a point on the edge may come out either way, the edge distance decides then."""
    inside = False
    for first, second in zip(points, points[1:] + points[:1]):
        if (first["y"] > y) != (second["y"] > y):
            crossing_x = first["x"] + (y - first["y"]) * (second["x"] - first["x"]) / (second["y"] - first["y"])
            if x < crossing_x:
                inside = not inside
    return inside


def circle_inside_deck(x, y, radius, deck=CAMPUS["deck"]):
    edges = list(zip(deck, deck[1:] + deck[:1]))
    nearest_edge = min(distance_to_segment((x, y), (a["x"], a["y"]), (b["x"], b["y"])) for a, b in edges)
    return point_in_polygon(x, y, deck) and nearest_edge >= radius


def problems_at(x, y, radius=HINT_RADIUS, campus=CAMPUS):
    """Everything a circle at (x, y) touches; empty when the place is free. Touching counts."""
    found = []
    if not circle_inside_deck(x, y, radius, campus["deck"]):
        found.append("outside the deck")
    for solid in campus["solids"]:
        if distance_to_box(x, y, solid) <= radius:
            found.append(f"solid {solid['id']}")
    for item in campus["decor"]:
        if distance_to_box(x, y, item) <= radius:
            found.append(f"decor {item['kind']}")
    for spot in campus["hiding_spots"]:
        if math.dist((x, y), (spot["x"], spot["y"])) <= radius + spot["r"]:
            found.append(f"hiding spot at {spot['x']}, {spot['y']}")
    for station in campus["stations"]:
        if math.dist((x, y), (station["x"], station["y"])) <= radius + station["r"]:
            found.append(f"station circle {station['id']}")
    for box in station_boxes():
        if distance_to_box(x, y, box) <= radius:
            found.append(f"{box['id']} drawing")
    if distance_to_box(x, y, label_box(campus["deck_label"])) <= radius:
        found.append("the Main Deck name")
    spawn = campus["spawn"]
    if math.dist((x, y), (spawn["x"], spawn["y"])) - radius <= radius:
        found.append("the spawn")
    return found


def is_centred_under_the_deck_name(x, y, label=CAMPUS["deck_label"]):
    return x == label["x"] and y > label["y"]


# Accepted: the real button


def test_the_button_is_at_the_centre_of_the_main_deck_with_radius_11():
    assert (BUTTON["x"], BUTTON["y"], BUTTON["r"]) == (365, 375, 11)


def test_the_button_with_its_hint_range_lies_on_free_paving_of_the_deck():
    assert problems_at(BUTTON["x"], BUTTON["y"]) == []


def test_the_button_stands_centred_under_the_main_deck_name():
    assert is_centred_under_the_deck_name(BUTTON["x"], BUTTON["y"])


def test_a_player_can_stand_on_the_button_so_the_hint_is_reachable():
    assert is_free(BUTTON["x"], BUTTON["y"], CAMPUS["solids"], CAMPUS["width"], CAMPUS["height"])


def test_every_station_with_a_drawn_object_is_checked():
    checked = {box["id"] for box in station_boxes()}
    assert checked == {f"station {station_id}" for station_id in STATION_BOXES}


# Rejected


def test_the_old_place_right_of_the_hedge_is_not_the_centre():
    assert not is_centred_under_the_deck_name(642, 249)


@pytest.mark.parametrize("place, what", [
    ((365, 290), "solid deck-pool"),
    ((600, 350), "station circle 12"),
    ((365, 352), "the Main Deck name"),
    ((486, 296), "the spawn"),
    ((30, 200), "outside the deck"),
    ((365, 411), "decor drain"),
])
def test_a_circle_on_something_is_rejected(place, what):
    assert what in problems_at(*place)


def test_a_circle_just_below_the_name_is_rejected_when_it_reaches_the_box():
    # The name's box ends at y 357; a circle of 13 at y 370 touches it (edge case below).
    assert "the Main Deck name" in problems_at(365, 357 + HINT_RADIUS)
    assert "the Main Deck name" not in problems_at(365, 357 + HINT_RADIUS + 1)


# Edge: touching a solid's edge counts as touching


def campus_with(solid):
    campus = dict(CAMPUS)
    campus["solids"] = CAMPUS["solids"] + [solid]
    return campus


def test_a_circle_that_only_touches_a_solid_edge_counts_as_touching():
    touching = {"id": "test-box", "kind": "bench", "x": BUTTON["x"] + HINT_RADIUS, "y": 370, "w": 10, "h": 10}
    assert "solid test-box" in problems_at(BUTTON["x"], BUTTON["y"], campus=campus_with(touching))


def test_a_circle_half_a_unit_clear_of_a_solid_does_not_touch_it():
    clear = {"id": "test-box", "kind": "bench", "x": BUTTON["x"] + HINT_RADIUS + 0.5, "y": 370, "w": 10, "h": 10}
    assert problems_at(BUTTON["x"], BUTTON["y"], campus=campus_with(clear)) == []


def test_a_circle_that_only_touches_the_deck_edge_counts_as_inside():
    # The deck's bottom edge at y 566 between x 160 and 440.
    assert circle_inside_deck(300, 566 - HINT_RADIUS, HINT_RADIUS)
    assert not circle_inside_deck(300, 566 - HINT_RADIUS + 0.5, HINT_RADIUS)
