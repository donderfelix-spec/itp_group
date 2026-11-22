"""Only a player at the red button may call an emergency meeting (M3-3.19).

Three parts:
- the plain rule `emergency_button_in_reach` (rule 4: no network, no clock);
- the server's `emergency` handler, which asks the rule after the unlock
  check and before the ghost and once-only checks of the Classic round;
- the page: "E Emergency" shows only for a living player within the reach.
  It runs the page's JavaScript in Node with the harness of
  test_classic_round_end_cleanup.py (skipped without Node).
"""

import math

import pytest

from server import protocol
from server.classic.emergency_button import emergency_button_in_reach
from server.main import app
from task_helpers import clock, client, connect, placeholder_at_every_station, put  # noqa: F401
from test_classic_round_end_cleanup import (
    EMERGENCY_STATUS, OWN, PLAYERS, UNLOCK_WAIT, lobby_state, needs_node, run_page, signed_in_lobby,
)
from test_classic_server_features import classic_for, start_classic
from test_classic_triggers_area3 import failed_sheet

BUTTON = {"x": 365, "y": 375, "r": 11}
REACH = 25
OUT_OF_REACH = {
    "type": "error",
    "code": "emergency_out_of_reach",
    "message": "Walk to the red button to call a meeting.",
}
NAMES = ("Mara", "Tiago", "Ines", "Rui")


# The plain rule: accepted positions


def test_a_player_on_the_button_is_in_reach():
    assert emergency_button_in_reach((365, 375), BUTTON, REACH) is True


def test_a_player_closer_than_the_reach_is_in_reach():
    assert emergency_button_in_reach((365 + 10.5, 375 - 3), BUTTON, REACH) is True


def test_exactly_at_the_reach_still_counts():
    assert emergency_button_in_reach((365 - 25, 375), BUTTON, REACH) is True
    # 15 and 20 make a distance of exactly 25 on a diagonal too.
    assert emergency_button_in_reach((365 + 15, 375 + 20), BUTTON, REACH) is True


# The plain rule: rejected positions


def test_just_outside_the_reach_is_not_in_reach():
    assert emergency_button_in_reach((365 - 25.01, 375), BUTTON, REACH) is False


def test_the_spawn_is_far_out_of_reach():
    assert emergency_button_in_reach((365, 375 + 145), BUTTON, REACH) is False


# The plain rule: edge cases


def test_a_player_without_a_position_is_never_in_reach():
    assert emergency_button_in_reach(None, BUTTON, REACH) is False


@pytest.mark.parametrize("position", [
    (math.nan, 375),
    (365, math.nan),
    (math.nan, math.nan),
    (math.inf, 375),
    (-math.inf, 375),
])
def test_a_position_that_is_not_a_real_number_is_never_in_reach(position):
    assert emergency_button_in_reach(position, BUTTON, REACH) is False


@pytest.mark.parametrize("position", [("365", 375), (365, None), (True, True), ([365], 375)])
def test_a_position_that_is_not_a_number_at_all_is_never_in_reach(position):
    assert emergency_button_in_reach(position, BUTTON, REACH) is False


def test_the_distance_counts_from_the_centre_not_the_edge_of_the_button():
    # The button's radius of 11 does not add to the reach.
    assert emergency_button_in_reach((365 - 25 - 11, 375), BUTTON, REACH) is False


def test_a_reach_of_zero_only_allows_the_centre():
    assert emergency_button_in_reach((365, 375), BUTTON, 0) is True
    assert emergency_button_in_reach((365.01, 375), BUTTON, 0) is False


# The server


def test_the_numbers_of_these_tests_are_the_map_s_button_and_reach():
    # The page tests below read the real campus.json, so the two must agree.
    assert app.state.campus["button"] == BUTTON
    assert app.state.campus["use_range"] == REACH


def button_and_reach():
    campus = app.state.campus
    return campus["button"], campus["use_range"]


def test_the_new_rejection_has_its_own_text():
    assert protocol.rejection("emergency_out_of_reach") == OUT_OF_REACH


def test_a_call_out_of_reach_after_the_unlock_gets_its_own_rejection_and_changes_nothing(connect, clock):
    connections, _code, _public, _start = start_classic(connect, NAMES)
    caller = NAMES[0]
    round_state = classic_for(caller)
    button, reach = button_and_reach()
    put(caller, (button["x"], button["y"] + reach + 0.5))
    clock.wait(45.0)

    connections[caller].send_json({"type": "emergency"})
    assert connections[caller].receive_json() == OUT_OF_REACH
    assert round_state.meeting is None
    assert app.state.lobbies.lobby_of(caller).meeting is None
    assert caller not in round_state.emergency_used
    assert round_state.phase != "meeting"


def test_a_player_at_the_spawn_cannot_call(connect, clock):
    connections, _code, _public, _start = start_classic(connect, NAMES)
    caller = NAMES[1]
    clock.wait(45.0)
    connections[caller].send_json({"type": "emergency"})
    assert connections[caller].receive_json() == OUT_OF_REACH
    assert caller not in classic_for(caller).emergency_used


def test_after_an_out_of_reach_call_the_same_player_can_still_call_at_the_button(connect, clock):
    connections, _code, _public, _start = start_classic(connect, NAMES)
    caller = NAMES[0]
    round_state = classic_for(caller)
    button, reach = button_and_reach()
    put(caller, (button["x"] + reach + 1, button["y"]))
    clock.wait(45.0)
    connections[caller].send_json({"type": "emergency"})
    assert connections[caller].receive_json()["code"] == "emergency_out_of_reach"

    put(caller, (button["x"] + reach, button["y"]))
    connections[caller].send_json({"type": "emergency"})
    for connection in connections.values():
        meeting = connection.receive_json()
        assert meeting["type"] == "meeting_state"
        assert meeting["reason"] == "emergency"
        assert meeting["phase"] == "discussion"
        assert meeting["seconds_left"] == 45
    assert caller in round_state.emergency_used


def test_still_locked_out_of_reach_gets_the_unlock_text_first(connect, clock):
    connections, _code, _public, _start = start_classic(connect, NAMES)
    caller = NAMES[0]
    button, reach = button_and_reach()
    put(caller, (button["x"] - reach - 50, button["y"]))
    clock.wait(40.0)

    connections[caller].send_json({"type": "emergency"})
    rejected = connections[caller].receive_json()
    assert rejected == {
        "type": "error",
        "code": "emergency_rejected",
        "message": "The emergency button unlocks in 5 seconds.",
    }
    assert classic_for(caller).meeting is None


def test_a_ghost_at_the_button_still_gets_emergency_rejected(connect, clock):
    connections, round_state, _lobby, _fr_id, ghost_id, _reporter_id, _position = failed_sheet(
        NAMES, connect, clock
    )
    button, _reach = button_and_reach()
    put(ghost_id, (button["x"], button["y"]))
    clock.wait(45.0)

    connections[ghost_id].send_json({"type": "emergency"})
    assert connections[ghost_id].receive_json() == protocol.rejection("emergency_rejected")
    assert round_state.meeting is None
    assert ghost_id not in round_state.emergency_used


def test_a_ghost_out_of_reach_is_told_to_walk_to_the_button(connect, clock):
    # The reach comes before the ghost check (order in the brief); a ghost
    # out of reach learns nothing new from this text.
    connections, round_state, _lobby, _fr_id, ghost_id, _reporter_id, _position = failed_sheet(
        NAMES, connect, clock
    )
    clock.wait(45.0)
    connections[ghost_id].send_json({"type": "emergency"})
    assert connections[ghost_id].receive_json() == OUT_OF_REACH
    assert round_state.meeting is None


# The page


def hp_round_with_own_player_at(place, ghost=False):
    """A Classic round in which the own player is a High Performer (a ghost
    if `ghost`), stands at `place` after the unlock and then presses E."""
    players = [dict(player, ghost=(player["name"] == OWN and ghost)) for player in PLAYERS]
    return signed_in_lobby() + [
        lobby_state("countdown"),
        lobby_state("round"),
        ["receive", {"type": "classic_role", "role": "HP", "other_free_riders": []}],
        ["receive", {"type": "classic_roster", "players": players}],
        ["receive", EMERGENCY_STATUS],
        ["receive", {"type": "positions", "players": [dict(name=OWN, **place)]}],
        ["wait", 500],
        ["wait", UNLOCK_WAIT],
        ["look"],
        ["key", "KeyE"],
    ]


def emergency_calls(result):
    return [message for message in result["sent"] if message["type"] == "emergency"]


@needs_node
def test_a_living_player_exactly_at_the_reach_sees_e_emergency_and_can_press_it():
    result = run_page(hp_round_with_own_player_at({"x": BUTTON["x"] - REACH, "y": BUTTON["y"]}))
    look = result["looks"][-1]
    assert look["useButtonText"] == "E Emergency"
    assert look["useButtonDisabled"] is False
    assert emergency_calls(result) == [{"type": "emergency"}]


@needs_node
def test_a_living_player_just_outside_the_reach_sees_no_emergency_hint():
    result = run_page(hp_round_with_own_player_at({"x": BUTTON["x"] - REACH - 1, "y": BUTTON["y"]}))
    look = result["looks"][-1]
    assert look["useButtonText"] == "E Use"
    assert emergency_calls(result) == []


@needs_node
def test_a_ghost_on_the_button_sees_no_emergency_hint():
    result = run_page(hp_round_with_own_player_at({"x": BUTTON["x"], "y": BUTTON["y"]}, ghost=True))
    look = result["looks"][-1]
    assert look["useButtonText"] == "E Use"
    assert look["useButtonDisabled"] is True
    assert emergency_calls(result) == []
