"""Nothing of a Classic round stays in the browser once the round is over (PR #72).

A play test found the meeting window, the end screen, the F-sheets, the red
button (and "E Emergency"), "Report", "Let fail" and the red own name still
on the page after a Classic round: in the lobby, in a new lobby, and over a
Duel started in the same lobby, which then could not be played.

What is checked here:
- after `lobby_state` goes from phase "round" to "lobby", nothing of
  Classic is shown, also when the red button had unlocked (45 seconds);
- the end screen stays after the round (S-101) and closes with the next
  countdown, the next round and when the world stops;
- after leaving the lobby nothing of Classic reaches the next lobby, and the
  world's own stop() forgets the red button's unlock time;
- a Duel after a Classic round shows no Classic element and sends nothing of Classic;
- "Back to the lobby" on the end screen only closes it: the player stays in
  the lobby (S-101, M3-3.14), like the Duel ranking's "Back to lobby";
- edge cases: a lobby without a Classic round before, two such messages in
  a row, a meeting still open at the end, a minigame still open.

The page's own world.js, lobby.js, meeting.js, round.js and main.js run in
Node (tests/classic_cleanup_in_node.js). Without Node these tests are
skipped; CI has Node.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

CLEANUP_IN_NODE = Path(__file__).resolve().parent / "classic_cleanup_in_node.js"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

OWN = "Ana"
PLAYERS = [
    {"name": "Ana", "character": "c1"},
    {"name": "Bo", "character": "c2"},
    {"name": "Cy", "character": "c3"},
    {"name": "Di", "character": "c4"},
]
# Next to the map's emergency button, with an F-sheet within report range.
CAMPUS_FILE = Path(__file__).resolve().parents[1] / "client/js/world/campus.json"
BUTTON = json.loads(CAMPUS_FILE.read_text(encoding="utf-8"))["button"]
USE_RANGE = json.loads(CAMPUS_FILE.read_text(encoding="utf-8"))["use_range"]
AT_THE_BUTTON = {"x": BUTTON["x"] - 2, "y": BUTTON["y"]}
SHEET = {
    "type": "classic_fail", "sheet_id": "f-sheet-1", "target_id": "Bo",
    "position": {"x": BUTTON["x"] - 1, "y": BUTTON["y"] + 1},
}
# Unlocks 45 seconds after the round started (DESIGN: emergency meeting).
EMERGENCY_STATUS = {"type": "classic_emergency_status", "emergency_ready_at": 145, "server_time": 100}
FAIL_STATUS = {"type": "classic_fail_status", "available": True, "in_range": True, "cooldown_until": None, "server_time": 100}
UNLOCK_WAIT = 46_000  # milliseconds: past the 45-second unlock
RESULT = {
    "type": "classic_result", "winner": "HP", "reason": "all_free_riders_eliminated",
    "roles": {"Ana": "FR", "Bo": "HP", "Cy": "HP", "Di": "HP"},
    "stats": {"failures": 1, "completed_tasks": 0, "meetings": 1},
}

# What a page shows when nothing of Classic is on it.
NOTHING_OF_CLASSIC = {
    "meetingHidden": True,
    "inputPaused": False,
    "sheetIds": [],
    "sheetsDrawn": 0,
    "emergencyButtonDrawn": False,
    "useButtonText": "E Use",
    "useButtonHasFailLook": False,
    "reportButtonShown": False,
    "freeRiderEButtonText": None,
    "ownNameRedOnMap": False,
    "ownNameRedInLobby": False,
    "ownNameRedInRound": False,
    "meetingKnowsFreeRider": False,
}


def run_page(steps):
    """Runs the page through `steps` and returns {looks, sent, errors}."""
    finished = subprocess.run(
        [NODE, str(CLEANUP_IN_NODE)],
        input=json.dumps(steps),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    result = json.loads(finished.stdout)
    assert result["errors"] == []
    return result


def lobby_state(phase, mode="classic", code="ABCD", players=PLAYERS):
    return ["receive", {
        "type": "lobby_state", "code": code, "host": OWN, "mode": mode,
        "phase": phase, "players": players,
    }]


def meeting_state(phase):
    return ["receive", {
        "type": "meeting_state", "phase": phase, "seconds_left": 30,
        "living": ["Ana", "Bo", "Cy"], "ghosts": ["Di"], "messages": [], "voted": [], "vote_targets": {}, "skip_voted": [],
        "characters": {"Ana": "consultant", "Bo": "finance_bro", "Cy": "surfer", "Di": "founder"},
        "reason": "emergency", "trigger_player_id": "Bo", "reported_sheet_id": None,
        "ejected_id": "Ana" if phase == "result" else None,
        "revealed_role": "FR" if phase == "result" else None,
        "tie": False, "winner": "HP" if phase == "result" else None,
    }]


def walk_to_the_button():
    """The server puts the own player at the red button; the queue plays it."""
    return [
        ["receive", {"type": "positions", "players": [dict(name=OWN, **AT_THE_BUTTON)]}],
        ["wait", 500],
    ]


def signed_in_lobby(mode="classic"):
    return [
        ["receive", {"type": "signed_in", "name": OWN, "guest": False}],
        lobby_state("lobby", mode),
    ]


def classic_round_as_free_rider():
    """A Classic round in which the own player is the Free Rider, stands at
    the red button after its unlock and next to an F-sheet: everything of
    Classic is on show."""
    return signed_in_lobby() + [
        lobby_state("countdown"),
        lobby_state("round"),
        ["receive", {"type": "you_are_fr"}],
        ["receive", {"type": "classic_role", "role": "FR", "other_free_riders": []}],
        ["receive", EMERGENCY_STATUS],
        ["receive", SHEET],
        ["receive", FAIL_STATUS],
        *walk_to_the_button(),
        ["wait", UNLOCK_WAIT],
        ["look"],
    ]


def end_of_round():
    """The server's news at the end of a Classic round, in its order."""
    return [["receive", RESULT], lobby_state("lobby"), ["wait", 50]]


def shows_nothing_of_classic(look):
    return {key: look[key] for key in NOTHING_OF_CLASSIC} == NOTHING_OF_CLASSIC


@needs_node
def test_a_fallen_character_stays_at_the_sheet_until_reported():
    sheet = dict(SHEET, character="finance_bro")
    report = dict(
        meeting_state("discussion")[1],
        reason="report",
        reported_sheet_id=sheet["sheet_id"],
    )
    page = run_page(signed_in_lobby() + [
        lobby_state("round"),
        ["receive", sheet],
        *walk_to_the_button(),
        ["lookAtDrawing"],
        ["look"],
        ["receive", report],
        ["wait", 50],
        ["lookAtDrawing"],
        ["look"],
    ])
    before, after = page["drawings"]
    assert before["fallenCharactersDrawn"] == [{
        "character": sheet["character"], "x": sheet["position"]["x"], "y": sheet["position"]["y"] - 5,
    }]
    assert after["fallenCharactersDrawn"] == []
    assert [look["sheetsDrawn"] for look in page["looks"]] == [1, 1]


@needs_node
def test_walking_ghosts_are_half_transparent_on_a_ghosts_page_only():
    positions = [
        dict(name=OWN, **AT_THE_BUTTON),
        dict(name="Bo", x=AT_THE_BUTTON["x"] + 14, y=AT_THE_BUTTON["y"]),
        dict(name="Cy", x=AT_THE_BUTTON["x"] - 14, y=AT_THE_BUTTON["y"]),
    ]
    steps = signed_in_lobby() + [lobby_state("round")]
    for ghost_names in ({"Bo"}, {OWN, "Bo"}):
        steps += [
            ["receive", {"type": "classic_roster", "players": [
                dict(player, ghost=player["name"] in ghost_names) for player in PLAYERS
            ]}],
            ["receive", {"type": "positions", "players": positions}],
            ["wait", 500],
            ["lookAtDrawing"],
        ]
    living_page, ghost_page = run_page(steps)["drawings"]
    assert {row["character"]: row["alpha"] for row in living_page["charactersDrawn"]} == {"c1": 1, "c3": 1}
    assert {row["character"]: row["alpha"] for row in ghost_page["charactersDrawn"]} == {"c1": 0.5, "c2": 0.5, "c3": 1}


# Accepted: the round shows everything, its end takes all of it away


@needs_node
def test_the_harness_sees_every_classic_element_during_the_round():
    outside_range = {**AT_THE_BUTTON, "x": BUTTON["x"] - USE_RANGE - 1}
    during, outside = run_page(classic_round_as_free_rider() + [
        ["receive", {"type": "positions", "players": [dict(name=OWN, **outside_range)]}],
        ["wait", 500],
        ["look"],
    ])["looks"]
    assert during["sheetIds"] == ["f-sheet-1"]
    assert during["sheetsDrawn"] == 1
    assert during["emergencyButtonDrawn"] is True
    # S-195: the Free Rider's main button stays "F Let fail"; "E Emergency"
    # is his own second button, only at the red button.
    assert during["useButtonText"] == "F Let fail"
    assert during["useButtonHasFailLook"] is True
    assert during["freeRiderEButtonText"] == "E Emergency"
    assert during["freeRiderEButtonDisabled"] is False
    assert outside["useButtonHasFailLook"] is True
    assert outside["useButtonText"] == "F Let fail"
    assert outside["freeRiderEButtonText"] is None
    assert during["reportButtonShown"] is True
    assert during["ownNameDrawn"] is True
    assert during["ownNameRedOnMap"] is True
    assert during["ownNameRedInLobby"] is True
    assert during["ownNameRedInRound"] is True
    assert during["meetingKnowsFreeRider"] is True


@needs_node
def test_the_emergency_button_stays_available_to_the_free_rider_during_fail_cooldown():
    steps = classic_round_as_free_rider() + [
        ["receive", {**FAIL_STATUS, "available": False, "server_time": 146, "cooldown_until": 161}],
        ["wait", 50],
        ["look"],
        ["key", "KeyE"],
    ]
    result = run_page(steps)
    during = result["looks"][-1]
    # S-195: "F Let fail" stays (grey, charging); "E Emergency" is the second button.
    assert during["useButtonText"] == "F Let fail"
    assert during["useButtonDisabled"] is True
    assert during["freeRiderEButtonText"] == "E Emergency"
    assert during["freeRiderEButtonDisabled"] is False
    assert [message for message in result["sent"] if message["type"] == "emergency"] == [
        {"type": "emergency"},
    ]


@needs_node
def test_after_the_round_the_lobby_shows_nothing_of_classic():
    after = run_page(classic_round_as_free_rider() + end_of_round() + [["look"]])["looks"][1]
    assert shows_nothing_of_classic(after), after
    assert after["ownNameDrawn"] is True  # the name is still drawn, only not red


@needs_node
def test_after_the_round_the_red_button_stays_locked_while_time_goes_on():
    steps = classic_round_as_free_rider() + end_of_round() + [["wait", UNLOCK_WAIT], ["look"]]
    after = run_page(steps)["looks"][1]
    assert shows_nothing_of_classic(after), after


@needs_node
def test_after_the_round_e_r_and_q_at_the_red_button_send_nothing_of_classic():
    steps = classic_round_as_free_rider() + end_of_round() + [
        ["key", "KeyE"], ["key", "KeyR"], ["key", "KeyF"],
    ]
    sent_types = [message["type"] for message in run_page(steps)["sent"]]
    assert not {"emergency", "report", "fail"} & set(sent_types)


@needs_node
def test_the_end_screen_stays_after_the_round():
    after = run_page(classic_round_as_free_rider() + end_of_round() + [["look"]])["looks"][1]
    assert after["endScreenHidden"] is False


@needs_node
def test_a_meeting_still_open_at_the_end_is_closed_and_walking_is_free_again():
    # The Free Rider left during the discussion: the round ends with the meeting open.
    steps = classic_round_as_free_rider() + [meeting_state("discussion"), ["look"]] + end_of_round() + [["look"]]
    during, after = run_page(steps)["looks"][1:]
    assert during["meetingHidden"] is False
    assert during["inputPaused"] is True
    assert shows_nothing_of_classic(after), after


@needs_node
def test_a_round_ended_by_the_vote_closes_the_meeting_result():
    steps = classic_round_as_free_rider() + [
        meeting_state("discussion"), meeting_state("voting"), meeting_state("result"), ["look"],
    ] + end_of_round() + [["look"]]
    at_result, after = run_page(steps)["looks"][1:]
    assert at_result["meetingHidden"] is False
    assert shows_nothing_of_classic(after), after
    assert after["endScreenHidden"] is False


@needs_node
def test_a_meeting_without_an_ejection_closes_after_its_result():
    result = meeting_state("result")
    result[1]["ejected_id"] = None
    result[1]["revealed_role"] = None
    result[1]["winner"] = None
    steps = classic_round_as_free_rider() + [
        result, ["look"], ["wait", 1799], ["look"], ["wait", 1], ["look"],
    ]
    shown, still_shown, closed = run_page(steps)["looks"][1:]
    assert shown["meetingHidden"] is False
    assert still_shown["meetingHidden"] is False
    assert closed["meetingHidden"] is True
    assert closed["inputPaused"] is False


@needs_node
def test_a_cast_vote_keeps_the_selected_player_highlighted_until_the_result():
    voting = meeting_state("voting")
    confirmed = meeting_state("voting")
    confirmed[1]["voted"] = ["Ana"]
    confirmed[1]["vote_targets"] = {"Ana": "Bo"}
    steps = classic_round_as_free_rider() + [
        voting, ["clickVote", "Bo"], confirmed, ["look"],
    ]
    result = run_page(steps)
    assert result["sent"][-1] == {"type": "vote", "target_id": "Bo"}
    assert result["looks"][-1]["selectedVoteTarget"] == "Bo"
    assert result["looks"][-1]["votes"]["Bo"] == {
        "count": "1", "countIsZero": False, "label": "Bo — votes: Ana", "title": "Bo — votes: Ana",
    }


@needs_node
def test_a_report_allows_voting_before_the_discussion_timer_ends():
    report = meeting_state("discussion")
    report[1]["reason"] = "report"
    steps = classic_round_as_free_rider() + [report, ["clickVote", "Bo"]]
    assert run_page(steps)["sent"][-1] == {"type": "vote", "target_id": "Bo"}


# Accepted: the end screen closes with the next countdown, round or stop


@needs_node
@pytest.mark.parametrize("mode", ["classic", "duel"])
def test_the_end_screen_closes_when_the_next_countdown_starts(mode):
    steps = classic_round_as_free_rider() + end_of_round() + [lobby_state("countdown", mode), ["look"]]
    assert run_page(steps)["looks"][1]["endScreenHidden"] is True


@needs_node
@pytest.mark.parametrize("mode", ["classic", "duel"])
def test_the_end_screen_closes_when_a_round_starts_without_a_countdown_seen(mode):
    steps = classic_round_as_free_rider() + end_of_round() + [lobby_state("round", mode), ["look"]]
    assert run_page(steps)["looks"][1]["endScreenHidden"] is True


@needs_node
@pytest.mark.parametrize("way_out", [
    {"type": "left_lobby"},
    {"type": "signed_out"},
    {"type": "close"},  # the connection was lost
])
def test_the_end_screen_closes_when_the_world_stops(way_out):
    steps = classic_round_as_free_rider() + end_of_round() + [["receive", way_out], ["look"]]
    assert run_page(steps)["looks"][1]["endScreenHidden"] is True


@needs_node
def test_back_to_the_lobby_closes_the_end_screen_and_stays_in_the_lobby():
    steps = classic_round_as_free_rider() + end_of_round() + [
        ["look"], ["click", "classic-back-lobby"], ["look"],
    ]
    result = run_page(steps)
    before, after = result["looks"][1:]
    assert before["endScreenHidden"] is False
    assert after["endScreenHidden"] is True
    assert after["focusedId"] is None  # the walking keys work at once
    assert "leave_lobby" not in [message["type"] for message in result["sent"]]
    assert shows_nothing_of_classic(after), after


@needs_node
def test_back_to_the_lobby_twice_is_harmless():
    steps = classic_round_as_free_rider() + end_of_round() + [
        ["click", "classic-back-lobby"], ["click", "classic-back-lobby"], ["look"],
    ]
    result = run_page(steps)
    assert result["looks"][1]["endScreenHidden"] is True
    assert "leave_lobby" not in [message["type"] for message in result["sent"]]


# Accepted: leaving the lobby takes everything of Classic along


@needs_node
@pytest.mark.parametrize("way_out", [{"type": "left_lobby"}, {"type": "close"}])
def test_leaving_during_the_round_brings_nothing_of_classic_into_the_next_lobby(way_out):
    steps = classic_round_as_free_rider() + [
        ["receive", way_out],
        ["receive", {"type": "signed_in", "name": OWN, "guest": False}],
        lobby_state("lobby", "duel", code="EFGH"),
        *walk_to_the_button(),
        ["look"],
    ]
    after = run_page(steps)["looks"][1]
    assert shows_nothing_of_classic(after), after
    assert after["endScreenHidden"] is True


@needs_node
def test_the_worlds_own_stop_forgets_the_red_button_and_the_f_sheets():
    # Only Game.world.stop(): nothing else of the page is asked to reset.
    steps = classic_round_as_free_rider() + [
        ["call", "world", "stop"],
        ["call", "world", "start"],
        ["receive", {"type": "positions", "players": [dict(name=OWN, **AT_THE_BUTTON)]}],
        ["wait", 500],
        ["look"],
    ]
    after = run_page(steps)["looks"][1]
    assert after["emergencyButtonDrawn"] is False
    assert after["useButtonText"] == "E Use"
    assert after["useButtonHasFailLook"] is False
    assert after["sheetIds"] == []
    assert after["sheetsDrawn"] == 0
    assert after["reportButtonShown"] is False
    assert after["ownNameRedOnMap"] is False


# Accepted: a Duel after a Classic round


@needs_node
def test_a_duel_after_a_classic_round_shows_nothing_of_classic():
    steps = classic_round_as_free_rider() + end_of_round() + [
        ["receive", {"type": "lobby_state", "code": "ABCD", "host": OWN, "mode": "duel", "phase": "lobby", "players": PLAYERS}],
        lobby_state("countdown", "duel"),
        lobby_state("round", "duel"),
        *walk_to_the_button(),
        ["wait", UNLOCK_WAIT],
        ["look"],
        ["key", "KeyE"], ["key", "KeyR"], ["key", "KeyF"],
    ]
    result = run_page(steps)
    in_the_duel = result["looks"][1]
    assert shows_nothing_of_classic(in_the_duel), in_the_duel
    assert in_the_duel["endScreenHidden"] is True
    sent_types = [message["type"] for message in result["sent"]]
    assert not {"emergency", "report", "fail"} & set(sent_types)


@needs_node
def test_classic_news_arriving_late_in_a_duel_draws_nothing():
    steps = classic_round_as_free_rider() + end_of_round() + [
        lobby_state("countdown", "duel"),
        lobby_state("round", "duel"),
        *walk_to_the_button(),
        ["receive", SHEET],
        ["receive", EMERGENCY_STATUS],
        ["receive", FAIL_STATUS],
        ["wait", UNLOCK_WAIT],
        ["look"],
    ]
    in_the_duel = run_page(steps)["looks"][1]
    assert shows_nothing_of_classic(in_the_duel), in_the_duel


# Rejected: a lobby_state of the running round resets nothing


@needs_node
def test_a_lobby_state_during_the_round_keeps_the_classic_elements():
    # For example when a player leaves: the round goes on.
    steps = classic_round_as_free_rider() + [meeting_state("discussion"), lobby_state("round"), ["wait", 50], ["look"]]
    still = run_page(steps)["looks"][1]
    assert still["meetingHidden"] is False
    assert still["inputPaused"] is True
    assert still["sheetIds"] == ["f-sheet-1"]
    assert still["ownNameRedInLobby"] is True
    assert still["ownNameRedInRound"] is True
    assert still["meetingKnowsFreeRider"] is True


# Edge cases


@needs_node
def test_a_lobby_without_any_classic_round_before_changes_nothing():
    steps = [["receive", {"type": "signed_in", "name": OWN, "guest": False}], ["look"],
             lobby_state("lobby"), ["wait", 50], ["look"],
             lobby_state("lobby"), ["wait", 50], ["look"]]
    result = run_page(steps)
    _before, first, second = result["looks"]
    assert shows_nothing_of_classic(first), first
    assert first == second
    assert first["endScreenHidden"] is True
    assert result["sent"] == []


@needs_node
def test_two_lobby_states_in_a_row_after_the_round_are_harmless():
    steps = classic_round_as_free_rider() + end_of_round() + [["look"], lobby_state("lobby"), ["wait", 50], ["look"]]
    first, second = run_page(steps)["looks"][1:]
    assert shows_nothing_of_classic(second), second
    assert first == second
    assert second["endScreenHidden"] is False  # the result is still there to read


@needs_node
def test_a_minigame_open_at_the_end_is_closed_first_and_walking_is_free():
    steps = classic_round_as_free_rider() + [["openMinigame"], ["look"]] + end_of_round() + [["look"]]
    during, after = run_page(steps)["looks"][1:]
    assert during["inputPaused"] is True
    assert shows_nothing_of_classic(after), after


@needs_node
def test_closing_the_meeting_does_not_free_walking_while_a_minigame_is_open():
    steps = classic_round_as_free_rider() + [
        meeting_state("discussion"), ["openMinigame"],
        ["call", "classicMeeting", "hide"],
        ["look"],
    ]
    after = run_page(steps)["looks"][1]
    assert after["meetingHidden"] is True
    assert after["inputPaused"] is True
