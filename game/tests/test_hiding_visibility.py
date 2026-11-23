"""Hiding is enforced before positions leave the server (M3-1.4).

The plain rules of `server/world/visibility.py`, the checks of the map
(`walkable`, the retired `hide_reveal_range`, the hiding spots) and walking
into the walkable hedge on the real map. Only a living Free Rider hides, and
only in a Classic round (S-131, S-132). Since S-192 a hidden player is left
out for those he hides from at any distance (no reveal range of 35 any
more), and only himself, the Free Riders and the ghosts are told he hides
(`told_hidden`). The server tests are in test_server_hiding.py.
"""

import pytest

from server.world.campus import CampusError, check_campus, load_campus
from server.world.movement import is_free, overlaps, step
from server.world.visibility import hiding_spot, players_who_hide_from, told_hidden, visible_positions

# Two High Performers and a Free Rider, and the ghost of a High Performer.
ROLES = {"hp": "HP", "fr": "FR", "near": "HP", "ghost": "HP"}
GHOSTS = {"ghost"}


@pytest.fixture
def campus():
    return load_campus()


@pytest.fixture
def spot(campus):
    """The hiding spot in the hedge on the Main Deck (595, 249, r 9)."""
    return campus["hiding_spots"][0]


def names(positions):
    return [entry[0] for entry in positions]


# The map


def test_all_four_hiding_spots_are_reachable_positions(campus):
    assert len(campus["hiding_spots"]) == 4
    for spot in campus["hiding_spots"]:
        assert is_free(spot["x"], spot["y"], campus["solids"], campus["width"], campus["height"])


def test_the_map_has_no_reveal_range_any_more(campus):
    # S-192 retired the reveal range of 35 (S-133).
    assert "hide_reveal_range" not in campus


def test_only_the_hedge_is_walkable(campus):
    walkable = [solid["id"] for solid in campus["solids"] if solid.get("walkable") is True]
    assert walkable == ["deck-hedge"]


@pytest.mark.parametrize("value", [35, 0, -1, float("inf"), float("nan"), True, "35"])
def test_invalid_reveal_range_is_rejected(campus, value):
    # Since S-192 every reveal range is refused, also the old 35.
    campus["hide_reveal_range"] = value
    with pytest.raises(CampusError):
        check_campus(campus)


def test_a_map_without_a_reveal_range_is_accepted(campus):
    campus.pop("hide_reveal_range", None)
    assert check_campus(campus) is campus


@pytest.mark.parametrize("value", ["yes", 1, 0, None])
def test_walkable_that_is_no_boolean_is_rejected(campus, value):
    campus["solids"][0]["walkable"] = value
    with pytest.raises(CampusError, match="walkable"):
        check_campus(campus)


def test_walkable_false_is_accepted_and_the_solid_blocks_again(campus):
    hedge = next(solid for solid in campus["solids"] if solid["id"] == "deck-hedge")
    hedge["walkable"] = False
    # Without its hiding spot, which would then lie inside a solid, the map is accepted.
    del campus["hiding_spots"][0]
    assert check_campus(campus) is campus
    assert overlaps(595, 249, hedge)


def test_hiding_inside_a_solid_is_rejected(campus):
    # Inside tree 3, left of the hedge.
    campus["hiding_spots"][0].update(x=534, y=249)
    with pytest.raises(CampusError, match="walkable centre"):
        check_campus(campus)


def test_hiding_inside_the_hedge_is_rejected_when_the_hedge_is_solid(campus):
    next(solid for solid in campus["solids"] if solid["id"] == "deck-hedge")["walkable"] = False
    with pytest.raises(CampusError, match="walkable centre"):
        check_campus(campus)


@pytest.mark.parametrize("radius", [0, -1, float("nan"), True])
def test_invalid_hiding_radius_is_rejected(campus, radius):
    campus["hiding_spots"][0]["r"] = radius
    with pytest.raises(CampusError):
        check_campus(campus)


# Walking into the walkable hedge, on the real map


def test_walking_enters_and_exits_the_hedge(campus):
    x, y = 595, 280
    for _ in range(12):
        x, y = step(x, y, 0, -1, 0.1, campus["solids"], campus["width"], campus["height"])
    assert y < 236
    assert x == 595


def test_walking_up_from_below_stops_in_the_hiding_spot_when_the_key_is_let_go(campus, spot):
    x, y = 595, 280
    # 3 steps of 9 units: from y 280 to y 253, inside the spot (249 +- 9).
    for _ in range(3):
        x, y = step(x, y, 0, -1, 0.1, campus["solids"], campus["width"], campus["height"])
    assert (x, y) == (595, 253)
    assert hiding_spot(campus, x, y) is spot


def test_walking_sideways_through_the_hedge_stops_only_at_tree_3(campus):
    # From the right of the hedge to the left: through the hedge, up to tree 3 (right edge 556).
    x, y = 640, 249
    for _ in range(20):
        x, y = step(x, y, -1, 0, 0.1, campus["solids"], campus["width"], campus["height"])
    assert (x, y) == (561, 249)


def test_the_hedge_still_has_its_place_and_size(campus):
    hedge = next(solid for solid in campus["solids"] if solid["id"] == "deck-hedge")
    assert (hedge["x"], hedge["y"], hedge["w"], hedge["h"], hedge["kind"]) == (556, 236, 68, 26, "hedge")


# Who hides from whom


def test_a_living_high_performer_does_not_see_a_hiding_free_rider():
    assert players_who_hide_from("hp", ROLES, GHOSTS, "round") == {"fr"}


def test_the_free_rider_hides_during_a_meeting_too():
    assert players_who_hide_from("hp", ROLES, GHOSTS, "meeting") == {"fr"}


@pytest.mark.parametrize("phase", ["result", "lobby", None, ""])
def test_nobody_hides_outside_the_round_and_the_meeting(phase):
    assert players_who_hide_from("hp", ROLES, GHOSTS, phase) == set()


def test_a_ghost_sees_everybody():
    assert players_who_hide_from("ghost", ROLES, GHOSTS, "round") == set()


def test_the_free_rider_hides_from_nobody_he_sees():
    assert players_who_hide_from("fr", ROLES, GHOSTS, "round") == set()


def test_free_riders_see_each_other_and_both_hide_from_high_performers():
    roles = {"a": "FR", "b": "FR", "c": "HP", "d": "HP", "e": "HP", "f": "HP"}
    assert players_who_hide_from("a", roles, set(), "round") == set()
    assert players_who_hide_from("b", roles, set(), "round") == set()
    assert players_who_hide_from("c", roles, set(), "round") == {"a", "b"}


def test_a_free_rider_who_was_voted_out_does_not_hide():
    roles = {"a": "FR", "b": "FR", "c": "HP", "d": "HP", "e": "HP", "f": "HP"}
    assert players_who_hide_from("c", roles, {"a"}, "round") == {"b"}


def test_a_player_who_is_not_in_the_round_counts_as_a_high_performer():
    assert players_who_hide_from("stranger", ROLES, GHOSTS, "round") == {"fr"}


def test_who_hides_does_not_change_its_arguments():
    roles, ghosts = dict(ROLES), set(GHOSTS)
    players_who_hide_from("hp", roles, ghosts, "round")
    assert (roles, ghosts) == (ROLES, GHOSTS)


# Which positions a viewer is sent


def test_hidden_player_does_not_reach_a_distant_viewer(campus, spot):
    positions = [("viewer", 300, 300), ("hidden", spot["x"], spot["y"])]
    assert visible_positions(positions, "viewer", campus, {"hidden"}) == positions[:1]


def test_hidden_player_always_sees_their_own_position(campus, spot):
    positions = [("hidden", spot["x"], spot["y"])]
    assert visible_positions(positions, "hidden", campus, {"hidden"}) == positions


@pytest.mark.parametrize("distance", [0, 1, 34, 35, 35.01, 36, 500])
def test_a_hidden_player_is_left_out_at_every_distance(campus, spot, distance):
    # Before S-192 he was sent within 35 units; now never.
    positions = [("viewer", spot["x"] + distance, spot["y"]), ("hidden", spot["x"], spot["y"])]
    assert names(visible_positions(positions, "viewer", campus, {"hidden"})) == ["viewer"]


def test_a_hidden_player_is_left_out_also_on_a_diagonal_at_35(campus, spot):
    # 21 and 28 make 35 (3-4-5 triangle): the old reveal range.
    positions = [("viewer", spot["x"] + 21, spot["y"] + 28), ("hidden", spot["x"], spot["y"])]
    assert names(visible_positions(positions, "viewer", campus, {"hidden"})) == ["viewer"]


def test_hiding_circle_includes_its_edge(campus, spot):
    assert hiding_spot(campus, spot["x"] + spot["r"], spot["y"]) is spot
    assert hiding_spot(campus, spot["x"] + spot["r"] + 0.01, spot["y"]) is None


@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_every_one_of_the_four_spots_hides(campus, index):
    spot = campus["hiding_spots"][index]
    positions = [("viewer", 20, 20), ("hidden", spot["x"], spot["y"] - spot["r"])]
    assert names(visible_positions(positions, "viewer", campus, {"hidden"})) == ["viewer"]


def test_a_player_in_a_spot_who_may_not_hide_is_seen_from_anywhere(campus, spot):
    positions = [("viewer", 20, 20), ("hp in the spot", spot["x"], spot["y"])]
    assert visible_positions(positions, "viewer", campus, {"somebody else"}) == positions


def test_leaving_hiding_reveals_player_to_distant_viewer(campus, spot):
    # He left the hidden state, so he is no longer among the hiders.
    positions = [("viewer", 300, 300), ("hidden", spot["x"] + spot["r"] + 1, spot["y"])]
    assert visible_positions(positions, "viewer", campus, set()) == positions


def test_the_hidden_state_counts_not_the_place(campus):
    # A hider is left out wherever he stands (S-191: the server keeps him
    # on the spot's centre, but the rule does not depend on it).
    positions = [("viewer", 300, 300), ("hidden", 20, 20)]
    assert names(visible_positions(positions, "viewer", campus, {"hidden"})) == ["viewer"]


def test_without_hiders_the_positions_are_sent_as_they_are(campus, spot):
    positions = [("viewer", 300, 300), ("in the spot", spot["x"], spot["y"])]
    sent = visible_positions(positions, "viewer", campus, set())
    assert sent == positions
    assert sent is not positions


def test_a_viewer_without_a_position_gets_everybody_but_the_hidden(campus, spot):
    positions = [("other", 300, 300), ("hidden", spot["x"], spot["y"])]
    assert visible_positions(positions, "missing", campus, {"hidden"}) == positions[:1]


def test_visibility_is_recipient_specific_and_does_not_mutate_positions(campus, spot):
    positions = [("far", 300, 300), ("near", spot["x"] + 20, spot["y"]), ("hidden", spot["x"], spot["y"])]
    before = list(positions)
    assert len(visible_positions(positions, "far", campus, {"hidden"})) == 2
    assert len(visible_positions(positions, "near", campus, {"hidden"})) == 2
    assert len(visible_positions(positions, "hidden", campus, {"hidden"})) == 3
    assert len(visible_positions(positions, "near", campus, set())) == 3
    assert positions == before


# Who is told that a player hides (S-192)


def test_the_hidden_free_rider_is_told_about_himself():
    assert told_hidden("fr", ROLES, GHOSTS, {"fr"}) == {"fr"}


def test_a_ghost_is_told():
    assert told_hidden("ghost", ROLES, GHOSTS, {"fr"}) == {"fr"}


def test_the_other_free_rider_is_told_also_as_a_ghost():
    roles = {"a": "FR", "b": "FR", "c": "HP", "d": "HP", "e": "HP", "f": "HP"}
    assert told_hidden("b", roles, set(), {"a"}) == {"a"}
    assert told_hidden("b", roles, {"b"}, {"a"}) == {"a"}


@pytest.mark.parametrize("viewer", ["hp", "near", "stranger"])
def test_a_living_high_performer_is_never_told(viewer):
    assert told_hidden(viewer, ROLES, GHOSTS, {"fr"}) == set()


def test_nobody_hidden_tells_nobody():
    assert told_hidden("fr", ROLES, GHOSTS, set()) == set()


def test_told_hidden_does_not_change_its_arguments():
    hidden = {"fr"}
    told = told_hidden("ghost", ROLES, GHOSTS, hidden)
    told.add("x")
    assert hidden == {"fr"}


def test_the_order_of_the_positions_stays_the_same(campus, spot):
    positions = [("a", 300, 300), ("hidden", spot["x"], spot["y"]), ("b", 20, 20)]
    assert names(visible_positions(positions, "a", campus, {"hidden"})) == ["a", "b"]
