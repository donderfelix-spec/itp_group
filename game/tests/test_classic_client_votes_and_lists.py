"""The page in Node: the Skip vote button and the own Classic task list (M3-3.12, M3-3.17).

Runs the page's own JavaScript through tests/classic_cleanup_in_node.js.
"""

from test_classic_round_end_cleanup import (
    OWN,
    classic_round_as_free_rider,
    lobby_state,
    meeting_state,
    needs_node,
    run_page,
    signed_in_lobby,
)

# Station 3 of campus.json stands at x 640, y 48; its use range is 25.
AT_STATION_3 = {"x": 640, "y": 60}


def stand_at_station_3():
    return [
        ["receive", {"type": "positions", "players": [dict(name=OWN, **AT_STATION_3)]}],
        ["wait", 500],
    ]


def classic_round_as_high_performer(task_stations):
    return signed_in_lobby() + [
        lobby_state("countdown"),
        lobby_state("round"),
        ["receive", {"type": "classic_role", "role": "HP", "task_stations": task_stations}],
        ["wait", 100],
    ]


# ---- Skip ------------------------------------------------------------------

@needs_node
def test_the_skip_button_sends_an_empty_target_and_then_every_button_is_off():
    steps = classic_round_as_free_rider() + [
        meeting_state("voting"), ["look"], ["clickVote", ""], ["look"],
    ]
    result = run_page(steps)
    before, after = result["looks"][-2:]
    skip = [button for button in before["voteButtons"] if button["target"] == ""]
    assert skip == [{"target": "", "text": "Skip", "disabled": False}]
    assert result["sent"][-1] == {"type": "vote", "target_id": ""}
    assert all(button["disabled"] for button in after["voteButtons"])


@needs_node
def test_skip_is_a_final_vote_like_the_others():
    steps = classic_round_as_free_rider() + [
        meeting_state("voting"), ["clickVote", ""], ["clickVote", "Bo"],
    ]
    votes = [message for message in run_page(steps)["sent"] if message["type"] == "vote"]
    assert votes == [{"type": "vote", "target_id": ""}]


@needs_node
def test_skip_is_offered_only_while_voting():
    steps = classic_round_as_free_rider() + [meeting_state("discussion"), ["look"]]
    result = run_page(steps)
    # In the discussion there are no vote buttons yet, so no Skip either.
    assert result["looks"][-1]["voteButtons"] == []
    assert not any(message["type"] == "vote" for message in result["sent"])


# ---- The own list -------------------------------------------------------------

@needs_node
def test_a_high_performers_whole_list_pulses_and_e_use_works_at_its_station():
    steps = classic_round_as_high_performer([3, 8]) + stand_at_station_3() + [
        ["look"], ["key", "KeyE"],
    ]
    result = run_page(steps)
    seen = result["looks"][-1]
    assert sorted(seen["pulsing"]) == [3, 8]
    assert seen["useButtonText"] == "E Use"
    assert seen["useButtonDisabled"] is False
    assert {"type": "open_station", "station": 3} in result["sent"]


@needs_node
def test_the_free_riders_empty_list_gives_no_pulse_and_no_e_use():
    steps = classic_round_as_free_rider() + [
        ["receive", {"type": "classic_role", "role": "FR", "other_free_riders": [], "task_stations": []}],
    ] + stand_at_station_3() + [["look"], ["key", "KeyE"]]
    result = run_page(steps)
    seen = result["looks"][-1]
    assert seen["pulsing"] == []
    assert seen["useButtonText"] != "E Use"
    assert not any(message["type"] == "open_station" for message in result["sent"])


@needs_node
def test_a_malformed_list_is_ignored_and_a_finished_station_never_pulses_again():
    steps = classic_round_as_high_performer([3, 8, 1]) + [
        ["receive", {"type": "station_done", "station": 3, "task_stations": "8,1"}],
        ["wait", 100], ["look"],
        ["receive", {"type": "station_done", "station": 8, "task_stations": [1, 1]}],
        ["wait", 100], ["look"],
        ["receive", {"type": "station_done", "station": 1, "task_stations": [99]}],
        ["wait", 100], ["look"],
    ]
    after_text, after_twice, after_unknown = run_page(steps)["looks"][-3:]
    assert sorted(after_text["pulsing"]) == [1, 8]
    assert after_twice["pulsing"] == [1]
    assert after_unknown["pulsing"] == []


@needs_node
def test_a_malformed_role_list_gives_no_usable_station():
    for bad in (None, "3", [3.5], [0], [3, 3], list(range(1, 14))):
        steps = classic_round_as_high_performer(bad) + [["look"]]
        assert run_page(steps)["looks"][-1]["pulsing"] == []
