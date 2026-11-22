"""The page in Node: votes, the Skip button and the own Classic task list (M3-3.12, M3-3.17).

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

def meeting_with(phase, **changes):
    """A meeting_state step of the own player Ana, with some fields changed."""
    step = meeting_state(phase)
    step[1].update(changes)
    return step


@needs_node
def test_the_skip_button_sends_skip_discussion_and_shows_the_count():
    steps = classic_round_as_free_rider() + [
        meeting_state("voting"), ["look"], ["click", "classic-skip-discussion"],
        meeting_with("voting", skip_voted=["Ana"]), ["look"],
    ]
    result = run_page(steps)
    before, after = result["looks"][-2:]
    # Three living players: 75 % is 2.25, so 3 are needed.
    assert before["skip"] == {"hidden": False, "status": "0 / 3 Skip votes to end voting early.", "text": "Skip", "disabled": False}
    assert result["sent"][-1] == {"type": "skip_discussion"}
    assert after["skip"]["text"] == "Undo Skip"
    assert after["skip"]["status"] == "1 / 3 Skip votes to end voting early."
    # Skip is no longer a vote button, and the vote buttons stay usable.
    assert [button["target"] for button in after["voteButtons"]] == ["Ana", "Bo", "Cy"]
    assert not any(button["disabled"] for button in after["voteButtons"])


@needs_node
def test_votes_can_change_and_be_withdrawn_and_show_every_voters_icon():
    steps = classic_round_as_free_rider() + [
        meeting_state("voting"),
        ["clickVote", "Bo"], meeting_with("voting", voted=["Ana", "Cy"], vote_targets={"Ana": "Bo", "Cy": "Bo"}), ["look"],
        ["clickVote", "Cy"], meeting_with("voting", voted=["Ana", "Cy"], vote_targets={"Ana": "Cy", "Cy": "Bo"}), ["look"],
        ["clickVote", "Cy"], meeting_with("voting", voted=["Cy"], vote_targets={"Cy": "Bo"}), ["look"],
    ]
    result = run_page(steps)
    first, changed, withdrawn = result["looks"][-3:]
    votes = [message for message in result["sent"] if message["type"] == "vote"]
    assert votes == [
        {"type": "vote", "target_id": "Bo"},
        {"type": "vote", "target_id": "Cy"},
        {"type": "vote", "target_id": "Cy"},
    ]
    assert first["selectedVoteTarget"] == "Bo"
    assert first["voteIconLabels"] == ["Ana voted for Bo", "Cy voted for Bo"]
    assert changed["selectedVoteTarget"] == "Cy"
    assert sorted(changed["voteIconLabels"]) == ["Ana voted for Cy", "Cy voted for Bo"]
    assert withdrawn["selectedVoteTarget"] is None
    assert withdrawn["voteIconLabels"] == ["Cy voted for Bo"]


@needs_node
def test_a_report_discussion_offers_voting_and_skip_but_an_emergency_one_does_not():
    steps = classic_round_as_free_rider() + [
        meeting_with("discussion", reason="report"), ["look"],
        ["click", "classic-skip-discussion"],
    ]
    result = run_page(steps)
    report = result["looks"][-1]
    assert report["skip"]["hidden"] is False
    assert [button["target"] for button in report["voteButtons"]] == ["Ana", "Bo", "Cy"]
    assert result["sent"][-1] == {"type": "skip_discussion"}

    steps = classic_round_as_free_rider() + [
        meeting_state("discussion"), ["look"], ["click", "classic-skip-discussion"],
    ]
    result = run_page(steps)
    assert result["looks"][-1]["skip"]["hidden"] is True
    assert not any(message["type"] == "skip_discussion" for message in result["sent"])


@needs_node
def test_a_ghost_sees_the_votes_but_cannot_vote_or_skip():
    steps = classic_round_as_free_rider() + [
        meeting_with("voting", living=["Bo", "Cy", "Di"], ghosts=["Ana"], vote_targets={"Bo": "Cy"}),
        ["look"], ["clickVote", "Cy"], ["click", "classic-skip-discussion"],
    ]
    result = run_page(steps)
    seen = result["looks"][-1]
    assert seen["skip"]["disabled"] is True
    assert all(button["disabled"] for button in seen["voteButtons"])
    assert seen["voteIconLabels"] == ["Bo voted for Cy"]
    assert not any(message["type"] in ("vote", "skip_discussion") for message in result["sent"])


@needs_node
def test_skip_needs_four_of_five_and_six_of_seven():
    five = ["Ana", "Bo", "Cy", "Di", "Ed"]
    seven = five + ["Flo", "Gus"]
    steps = classic_round_as_free_rider() + [
        meeting_with("voting", living=five, ghosts=[]), ["look"],
        meeting_with("voting", living=seven, ghosts=[]), ["look"],
    ]
    with_five, with_seven = run_page(steps)["looks"][-2:]
    assert with_five["skip"]["status"] == "0 / 4 Skip votes to end voting early."
    assert with_seven["skip"]["status"] == "0 / 6 Skip votes to end voting early."


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
