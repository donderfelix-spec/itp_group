"""Lennart's action ranges, the F key and the Free Rider's report (M3-4.25 to M3-4.28, S-180, S-181).

- Report range 8 map units, fail range 20 map units; the server (rules.py)
  and the browser (world.js) use the same numbers.
- A living Free Rider can report an F-sheet, also their own victim's
  (Lennart's test, kept unchanged from his commit).
- Key F lets fail like Q; the button says only "Let fail".

Edge cases decided here: a distance of exactly 8 (report) or 20 (fail)
counts as in range; 8.01 and 20.01 do not.
"""

import re
from pathlib import Path

import pytest

from rules import FAIL_RANGE_TILES, REPORT_RANGE, can_fail, can_report
from server.main import app
from task_helpers import clock, client, connect, placeholder_at_every_station  # noqa: F401
from test_classic_fail_hud_area3 import drain_fail, place_players
from test_classic_round_end_cleanup import (
    FAIL_STATUS, needs_node, run_page, signed_in_lobby, lobby_state,
)
from test_classic_server_features import classic_for, start_classic

WORLD_JS = (Path(__file__).resolve().parents[1] / "client/js/world/world.js").read_text(encoding="utf-8")


def browser_number(name):
    """The number a `var NAME = ...;` line of world.js holds."""
    match = re.search(r"var " + name + r" = (\d+(?:\.\d+)?);", WORLD_JS)
    assert match, name
    return float(match.group(1))


def report_state(roles=None, eliminated=None):
    return {
        "roles": roles or {"Free": "FR", "Victim": "HP", "Finder": "HP"},
        "eliminated": eliminated if eliminated is not None else {"Victim"},
        "phase": "round",
        "f_sheets": {"f-sheet-1": (0, 0)},
        "meeting_triggers": set(),
    }


def fail_state(target_position):
    return {
        "roles": {"Free": "FR", "Target": "HP"},
        "eliminated": set(),
        "phase": "round",
        "positions": {"Free": (0.0, 0.0), "Target": target_position},
        "last_fail_at": {},
    }


# Lennart's test from `Spielfluss-und-Bug-Fixing` (c506758), unchanged.
def test_free_rider_can_report_own_sheet_at_doubled_range():
    state = {
        "roles": {"Free": "FR", "Victim": "HP"},
        "eliminated": {"Victim"}, "phase": "round",
        "f_sheets": {"f-sheet-1": (0, 0)}, "meeting_triggers": set(),
    }
    assert REPORT_RANGE == 8
    assert FAIL_RANGE_TILES == 20
    assert can_report(state, "Free", "f-sheet-1", (8, 0))
    assert not can_report(state, "Free", "f-sheet-1", (8.01, 0))
    state["meeting_triggers"].add("report:f-sheet-1")
    assert not can_report(state, "Free", "f-sheet-1", (0, 0))


# Server and browser agree


def test_browser_and_server_use_the_same_ranges():
    assert browser_number("REPORT_RANGE") == REPORT_RANGE == 8
    assert browser_number("FAIL_RANGE_TILES") == FAIL_RANGE_TILES == 20


# Report range: accepted, rejected, edge


@pytest.mark.parametrize("position", [(8, 0), (0, -8), (4.8, 6.4), (7.99, 0)])
def test_a_high_performer_reports_up_to_eight_map_units_away(position):
    assert can_report(report_state(), "Finder", "f-sheet-1", position)


@pytest.mark.parametrize("position", [(8.01, 0), (0, 8.01), (6, 6), (20, 0)])
def test_a_report_just_beyond_eight_map_units_is_refused(position):
    assert not can_report(report_state(), "Finder", "f-sheet-1", position)
    assert not can_report(report_state(), "Free", "f-sheet-1", position)


def test_a_ghost_cannot_report_even_inside_the_range():
    state = report_state(eliminated={"Victim", "Finder"})
    assert not can_report(state, "Finder", "f-sheet-1", (1, 0))


# Fail range: accepted, rejected, edge


@pytest.mark.parametrize("position", [(20.0, 0.0), (0.0, 20.0), (12.0, 16.0), (19.99, 0.0)])
def test_the_free_rider_fails_up_to_twenty_map_units_away(position):
    assert can_fail(fail_state(position), "Free", "Target", now=100.0)


@pytest.mark.parametrize("position", [(20.01, 0.0), (15.0, 15.0), (0.0, 21.0)])
def test_a_fail_just_beyond_twenty_map_units_is_refused(position):
    assert not can_fail(fail_state(position), "Free", "Target", now=100.0)


# Report range over the WebSocket, with the server's own positions


def test_report_over_the_websocket_at_eight_accepted_and_just_beyond_refused(connect, clock):
    names = ("Mara", "Tiago", "Ines", "Rui")
    connections, _code, _public, _start = start_classic(connect, names)
    round_state = classic_for(names[0])
    fr_id = next(player for player, role in round_state.roles.items() if role == "FR")
    lobby = app.state.lobbies.lobby_of(fr_id)
    place_players(lobby, names, {player: (100.0, 100.0) for player in names})

    connections[fr_id].send_json({"type": "fail"})
    fail = connections[fr_id].receive_json()
    assert fail["type"] == "classic_fail"
    drain_fail(connections, round_state, fr_id, fail["target_id"])
    sheet = fail["position"]
    reporter = next(player for player in names if player not in (fr_id, fail["target_id"]))

    too_far = (sheet["x"] + 8.5, sheet["y"])
    lobby.walkers._walkers[reporter].position = too_far
    connections[reporter].send_json({
        "type": "report", "sheet_id": fail["sheet_id"], "position": {"x": too_far[0], "y": too_far[1]},
    })
    refused = connections[reporter].receive_json()
    assert refused["type"] == "error"
    assert refused["code"] == "report_rejected"
    assert lobby.meeting is None

    at_the_edge = (sheet["x"] + 8.0, sheet["y"])
    lobby.walkers._walkers[reporter].position = at_the_edge
    connections[reporter].send_json({
        "type": "report", "sheet_id": fail["sheet_id"], "position": {"x": at_the_edge[0], "y": at_the_edge[1]},
    })
    meeting = connections[reporter].receive_json()
    assert meeting["type"] == "meeting_state"
    assert meeting["reason"] == "report"
    assert meeting["trigger_player_id"] == reporter


# Key F in the page (world.js, main.js), run in Node


AWAY_FROM_THE_BUTTON = {"x": 120, "y": 120}


def free_rider_in_a_round(fail_status=FAIL_STATUS, role="FR"):
    """A Classic round in which the own player stands away from the red button."""
    return signed_in_lobby() + [
        lobby_state("countdown"),
        lobby_state("round"),
        *([["receive", {"type": "you_are_fr"}]] if role == "FR" else []),
        ["receive", {"type": "classic_role", "role": role, "other_free_riders": []}],
        ["receive", fail_status],
        ["receive", {"type": "positions", "players": [{"name": "Ana", **AWAY_FROM_THE_BUTTON}]}],
        ["wait", 500],
    ]


def sent_fails(steps):
    return [message for message in run_page(steps)["sent"] if message["type"] == "fail"]


@needs_node
@pytest.mark.parametrize("key", ["KeyF", "KeyQ"])
def test_f_and_q_both_let_fail(key):
    assert sent_fails(free_rider_in_a_round() + [["key", key]]) == [{"type": "fail"}]


@needs_node
def test_f_does_nothing_without_a_high_performer_in_range():
    out_of_range = dict(FAIL_STATUS, in_range=False)
    assert sent_fails(free_rider_in_a_round(out_of_range) + [["key", "KeyF"]]) == []


@needs_node
def test_f_does_nothing_for_a_high_performer():
    steps = free_rider_in_a_round(role="HP")
    steps = [step for step in steps if not (step[0] == "receive" and step[1]["type"] == "classic_fail_status")]
    assert sent_fails(steps + [["key", "KeyF"]]) == []


@needs_node
def test_f_does_nothing_while_a_minigame_is_open():
    assert sent_fails(free_rider_in_a_round() + [["openMinigame"], ["key", "KeyF"]]) == []


@needs_node
def test_the_fail_button_says_only_let_fail():
    look = run_page(free_rider_in_a_round() + [["look"]])["looks"][0]
    assert look["useButtonHasFailLook"] is True
    assert look["useButtonText"] == "Let fail"
    assert "tiles" not in WORLD_JS


def test_f_sheets_are_drawn_thirty_percent_larger():
    sheet_drawing = WORLD_JS[WORLD_JS.index("ctx.rotate(-0.12);"):]
    assert sheet_drawing.index("ctx.scale(1.3, 1.3);") < sheet_drawing.index('ctx.fillStyle = "#FFFDF5";')
