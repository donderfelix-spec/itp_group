"""Once the own emergency call is used, the red button offers nothing more (M3-3.22).

Each player may call one emergency meeting per round; the server refuses a
second one. The page learns that the own call was accepted from the
`meeting_state` of that meeting: its `reason` is "emergency" and its
`trigger_player_id` is the own name. From then on, for the rest of the round,
the page shows no "E Emergency" at the red button and E sends no
`emergency` there; a Free Rider sees the normal "F Let fail" button instead.
The next round gives the call back.

The page's own JavaScript runs in Node with the harness of
test_classic_round_end_cleanup.py (skipped without Node).
"""

import math

from test_classic_round_end_cleanup import (
    AT_THE_BUTTON, BUTTON, EMERGENCY_STATUS, FAIL_STATUS, OWN, PLAYERS, UNLOCK_WAIT,
    end_of_round, lobby_state, needs_node, run_page, signed_in_lobby,
)

# How long a meeting result without an ejection stays open (see
# test_a_meeting_without_an_ejection_closes_after_its_result), plus a little.
RESULT_STAYS_MS = 1800 + 50
# Within the 25 units of the button, but not on it (like the play test).
FREE_RIDER_NEAR = {"x": BUTTON["x"] - 20, "y": BUTTON["y"] + 10}


def meeting(phase, caller, reason="emergency"):
    """A `meeting_state` as the server sends it; the result ejects nobody."""
    return ["receive", {
        "type": "meeting_state", "phase": phase, "seconds_left": 30,
        "living": ["Ana", "Bo", "Cy", "Di"], "ghosts": [], "messages": [], "voted": [],
        "vote_targets": {}, "skip_voted": [],
        "characters": {"Ana": "consultant", "Bo": "finance_bro", "Cy": "surfer", "Di": "founder"},
        "reason": reason, "trigger_player_id": caller,
        "reported_sheet_id": "f-sheet-1" if reason == "report" else None,
        "ejected_id": None, "revealed_role": None, "tie": False, "winner": None,
    }]


def whole_meeting(caller, reason="emergency"):
    """A meeting from its start to its result, which then closes by itself."""
    return [
        meeting("discussion", caller, reason),
        meeting("voting", caller, reason),
        meeting("result", caller, reason),
        ["wait", RESULT_STAYS_MS],
    ]


def stand_at(place):
    return [
        ["receive", {"type": "positions", "players": [dict(name=OWN, **place)]}],
        ["wait", 500],
    ]


def round_at_the_button(role="HP", place=AT_THE_BUTTON):
    """A Classic round: the own player has `role` and stands at `place`
    after the red button unlocked."""
    steps = signed_in_lobby() + [lobby_state("countdown"), lobby_state("round")]
    if role == "FR":
        steps.append(["receive", {"type": "you_are_fr"}])
    steps += [
        ["receive", {"type": "classic_role", "role": role, "other_free_riders": []}],
        ["receive", {"type": "classic_roster", "players": PLAYERS}],
        ["receive", EMERGENCY_STATUS],
    ]
    if role == "FR":
        steps.append(["receive", FAIL_STATUS])
    return steps + stand_at(place) + [["wait", UNLOCK_WAIT]]


def emergency_calls(result):
    return [message for message in result["sent"] if message["type"] == "emergency"]


# Accepted: the own call was used


@needs_node
def test_after_the_own_call_a_living_player_sees_no_e_emergency_at_the_button():
    steps = round_at_the_button() + [["look"]] + whole_meeting(OWN) + [
        ["look"], ["key", "KeyE"], ["clickUseButton"],
    ]
    result = run_page(steps)
    before, after = result["looks"]
    assert before["useButtonText"] == "E Emergency"
    assert after["meetingHidden"] is True
    assert after["inputPaused"] is False
    assert after["useButtonText"] == "E Use"
    assert after["useButtonDisabled"] is True
    assert emergency_calls(result) == []


@needs_node
def test_the_hint_goes_away_as_soon_as_the_meeting_starts():
    steps = round_at_the_button() + [meeting("discussion", OWN), ["look"]]
    during = run_page(steps)["looks"][0]
    assert during["useButtonText"] == "E Use"


@needs_node
def test_the_hint_stays_away_for_the_rest_of_the_round():
    steps = round_at_the_button() + whole_meeting(OWN) + [
        ["receive", EMERGENCY_STATUS],  # the server's status after the meeting
        *stand_at({"x": BUTTON["x"], "y": BUTTON["y"]}),
        ["wait", UNLOCK_WAIT],
        ["look"],
        ["key", "KeyE"],
    ]
    result = run_page(steps)
    assert result["looks"][0]["useButtonText"] == "E Use"
    assert emergency_calls(result) == []


@needs_node
def test_a_free_rider_who_called_sees_the_normal_fail_button_near_the_red_button():
    steps = round_at_the_button("FR", FREE_RIDER_NEAR) + [["look"]] + whole_meeting(OWN) + [
        ["receive", FAIL_STATUS],
        ["wait", 50],
        ["look"],
        ["key", "KeyE"],
        ["clickUseButton"],
    ]
    result = run_page(steps)
    before, after = result["looks"]
    assert math.dist((FREE_RIDER_NEAR["x"], FREE_RIDER_NEAR["y"]), (BUTTON["x"], BUTTON["y"])) <= 25
    # S-195: "F Let fail" is always the main button; "E Emergency" is the
    # Free Rider's second button and goes once his call is used.
    assert before["useButtonText"] == "F Let fail"
    assert before["freeRiderEButtonText"] == "E Emergency"
    assert after["useButtonHasFailLook"] is True
    assert after["useButtonText"] == "F Let fail"
    assert after["useButtonDisabled"] is False
    assert after["freeRiderEButtonText"] is None
    assert emergency_calls(result) == []
    assert [message for message in result["sent"] if message["type"] == "fail"] == [{"type": "fail"}]


# Rejected: meetings that do not use the own call


@needs_node
def test_a_meeting_called_by_another_player_keeps_the_own_hint():
    steps = round_at_the_button() + whole_meeting("Bo") + [["look"], ["key", "KeyE"]]
    result = run_page(steps)
    assert result["looks"][0]["useButtonText"] == "E Emergency"
    assert result["looks"][0]["useButtonDisabled"] is False
    assert emergency_calls(result) == [{"type": "emergency"}]


@needs_node
def test_a_report_meeting_started_by_the_own_player_keeps_the_hint():
    steps = round_at_the_button() + whole_meeting(OWN, reason="report") + [["look"], ["key", "KeyE"]]
    result = run_page(steps)
    assert result["looks"][0]["useButtonText"] == "E Emergency"
    assert emergency_calls(result) == [{"type": "emergency"}]


@needs_node
def test_the_free_rider_s_e_alone_sends_neither_emergency_nor_fail_after_the_call():
    # E is not the fail key: only the button and Q let a task fail.
    steps = round_at_the_button("FR", FREE_RIDER_NEAR) + whole_meeting(OWN) + [
        ["receive", FAIL_STATUS], ["wait", 50], ["key", "KeyE"],
    ]
    sent_types = [message["type"] for message in run_page(steps)["sent"]]
    assert "emergency" not in sent_types
    assert "fail" not in sent_types


@needs_node
def test_a_free_rider_keeps_e_emergency_after_another_players_meeting():
    steps = round_at_the_button("FR", FREE_RIDER_NEAR) + whole_meeting("Bo") + [["look"]]
    after = run_page(steps)["looks"][0]
    # S-195: his own E button, beside the unchanged "F Let fail".
    assert after["freeRiderEButtonText"] == "E Emergency"
    assert after["useButtonText"] == "F Let fail"
    assert after["useButtonHasFailLook"] is True


# Edge cases: the next round gives the call back


@needs_node
def test_after_the_round_and_in_the_next_round_the_hint_is_back():
    steps = round_at_the_button() + whole_meeting(OWN) + end_of_round() + [
        lobby_state("countdown"),
        lobby_state("round"),
        ["receive", {"type": "classic_role", "role": "HP", "other_free_riders": []}],
        ["receive", EMERGENCY_STATUS],
        *stand_at(AT_THE_BUTTON),
        ["wait", UNLOCK_WAIT],
        ["look"],
        ["key", "KeyE"],
    ]
    result = run_page(steps)
    assert result["looks"][0]["useButtonText"] == "E Emergency"
    assert emergency_calls(result) == [{"type": "emergency"}]


@needs_node
def test_a_new_classic_role_alone_gives_the_call_back():
    steps = round_at_the_button() + whole_meeting(OWN) + [
        ["receive", {"type": "classic_role", "role": "HP", "other_free_riders": []}],
        ["wait", 50],
        ["look"],
    ]
    assert run_page(steps)["looks"][0]["useButtonText"] == "E Emergency"


@needs_node
def test_leaving_and_joining_a_new_lobby_gives_the_call_back():
    steps = round_at_the_button() + whole_meeting(OWN) + [
        ["receive", {"type": "left_lobby"}],
        ["receive", {"type": "signed_in", "name": OWN, "guest": False}],
        lobby_state("lobby", code="EFGH"),
        lobby_state("countdown", code="EFGH"),
        lobby_state("round", code="EFGH"),
        ["receive", {"type": "classic_role", "role": "HP", "other_free_riders": []}],
        ["receive", EMERGENCY_STATUS],
        *stand_at(AT_THE_BUTTON),
        ["wait", UNLOCK_WAIT],
        ["look"],
    ]
    assert run_page(steps)["looks"][0]["useButtonText"] == "E Emergency"


@needs_node
def test_a_meeting_state_without_a_caller_changes_nothing():
    broken = meeting("discussion", OWN)
    del broken[1]["trigger_player_id"]
    steps = round_at_the_button() + [broken, meeting("result", "Bo"), ["wait", RESULT_STAYS_MS], ["look"]]
    assert run_page(steps)["looks"][0]["useButtonText"] == "E Emergency"
