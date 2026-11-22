"""Skip is an ordinary secret vote, and the vote ends early once everybody voted (M3-3.12).

Felix, 2026-11-21: "Skip" is a value of `vote.target_id`; whoever has not
voted when the time runs out counts as Skip; a tie, or Skip with at least
as many votes as the leading player, ejects nobody; the meeting ends as
soon as all living players have voted. Votes stay secret and final.
"""

import pytest

from server import protocol
from server.classic.meeting import (
    SKIP,
    EjectResult,
    advance_meeting,
    cast_vote,
    end_voting_if_everyone_voted,
    everyone_has_voted,
    meeting_snapshot,
    start_discussion,
)
from server.main import app
from task_helpers import client, clock, connect  # noqa: F401
from test_classic_server_features import classic_for, start_classic


def voting(roles, votes=None):
    """A meeting in its voting phase that ends at 30.0 by the clock."""
    state = start_discussion(
        list(roles), [], 0.0,
        {
            "roles": roles,
            "tasks": {player_id: ["1", "2", "3", "4"] for player_id in roles},
            "completed_tasks": {},
            "eliminated": set(),
        },
    )
    state["phase"] = "voting"
    state["deadline"] = 30.0
    state["votes"] = dict(votes or {})
    return state


FIVE = {"A": "HP", "B": "HP", "C": "HP", "D": "HP", "F": "FR"}


# ---- The value of Skip -------------------------------------------------

def test_skip_is_the_same_value_in_the_rules_and_in_the_protocol():
    assert SKIP == protocol.SKIP_VOTE == ""


def test_skip_can_never_be_a_player_name():
    with pytest.raises(protocol.ProtocolError):
        protocol._check_name(SKIP)


# ---- Accepted ----------------------------------------------------------

def test_a_living_player_may_vote_skip():
    state = cast_vote(voting(FIVE), "A", SKIP)
    assert state["votes"] == {"A": SKIP}


def test_a_skip_vote_is_final_like_any_vote():
    state = cast_vote(voting(FIVE), "A", SKIP)
    with pytest.raises(ValueError, match="final"):
        cast_vote(state, "A", "F")
    with pytest.raises(ValueError, match="final"):
        cast_vote(cast_vote(voting(FIVE), "A", "F"), "A", SKIP)


def test_the_majority_still_ejects_its_player():
    state = voting(FIVE, {"A": "F", "B": "F", "C": "F", "D": SKIP})
    result = advance_meeting(state, 30.0)
    assert result["vote_result"] == EjectResult("F", False, "FR")


# ---- Nobody goes --------------------------------------------------------

def test_a_player_who_did_not_vote_counts_as_skip():
    # One vote out of five: four count as Skip, so nobody goes.
    result = advance_meeting(voting(FIVE, {"A": "F"}), 30.0)
    assert result["vote_result"] == EjectResult(None, False, None)
    assert result["ghosts"] == ()


def test_skip_with_the_most_votes_ejects_nobody():
    state = voting(FIVE, {"A": SKIP, "B": SKIP, "C": SKIP, "D": "F", "F": "D"})
    result = advance_meeting(state, 30.0)
    assert result["vote_result"].ejected_id is None
    assert result["living"] == ("A", "B", "C", "D", "F")


def test_skip_as_many_as_the_leading_player_is_a_tie():
    state = voting(FIVE, {"A": "F", "B": "F", "C": SKIP, "D": SKIP, "F": "A"})
    result = advance_meeting(state, 30.0)
    assert result["vote_result"] == EjectResult(None, True, None)


def test_two_players_with_the_most_votes_tie():
    state = voting(FIVE, {"A": "F", "B": "F", "C": "D", "D": "C", "F": "D"})
    result = advance_meeting(state, 30.0)
    assert result["vote_result"] == EjectResult(None, True, None)


def test_nobody_voting_at_all_ejects_nobody():
    result = advance_meeting(voting(FIVE), 30.0)
    assert result["vote_result"] == EjectResult(None, False, None)


# ---- Rejected -----------------------------------------------------------

def test_a_ghost_cannot_vote_skip():
    state = voting(FIVE)
    state["living"] = ("A", "B", "C", "F")
    state["ghosts"] = ("D",)
    with pytest.raises(ValueError, match="living"):
        cast_vote(state, "D", SKIP)


def test_skip_is_not_possible_during_the_discussion():
    state = start_discussion(["A", "B", "C"], [], 0.0)
    state["reason"] = "report"
    with pytest.raises(ValueError, match="not open"):
        cast_vote(state, "A", SKIP)


def test_a_vote_for_a_ghost_or_a_stranger_is_still_rejected():
    state = voting(FIVE)
    state["living"] = ("A", "B", "C", "F")
    with pytest.raises(ValueError, match="living player or Skip"):
        cast_vote(state, "A", "D")
    with pytest.raises(ValueError, match="living player or Skip"):
        cast_vote(state, "A", "Nobody")


# ---- The vote ends early once everybody voted ----------------------------

def test_the_vote_ends_as_soon_as_every_living_player_voted():
    state = voting(FIVE, {"A": "F", "B": "F", "C": "F", "D": SKIP})
    assert end_voting_if_everyone_voted(state, 12.0) is state  # F has not voted yet
    state = cast_vote(state, "F", "A")
    assert everyone_has_voted(state)
    finished = end_voting_if_everyone_voted(state, 12.0)
    assert finished["phase"] == "result"
    assert finished["deadline"] == 12.0
    assert finished["vote_result"] == EjectResult("F", False, "FR")
    assert finished["winner"] == "HP"


def test_skip_votes_count_for_ending_the_vote_early():
    state = voting(FIVE, {player: SKIP for player in FIVE})
    finished = end_voting_if_everyone_voted(state, 5.0)
    assert finished["phase"] == "result"
    assert finished["vote_result"] == EjectResult(None, False, None)


def test_ghosts_are_not_waited_for():
    state = voting(FIVE, {"A": SKIP, "B": SKIP, "C": SKIP, "F": SKIP})
    state["living"] = ("A", "B", "C", "F")
    state["ghosts"] = ("D",)
    assert end_voting_if_everyone_voted(state, 5.0)["phase"] == "result"


def test_the_discussion_never_ends_early():
    state = start_discussion(["A", "B"], [], 0.0)
    state["votes"] = {"A": "B", "B": "A"}  # cannot happen, but must not end it
    assert end_voting_if_everyone_voted(state, 1.0) is state


def test_ending_early_needs_a_real_time():
    state = voting(FIVE, {player: SKIP for player in FIVE})
    with pytest.raises(ValueError, match="time"):
        end_voting_if_everyone_voted(state, float("nan"))


def test_the_snapshot_tells_who_voted_but_never_for_whom_or_skip():
    state = voting(FIVE, {"A": SKIP, "B": "F"})
    snapshot = meeting_snapshot(state, 10.0)
    assert sorted(snapshot["voted"]) == ["A", "B"]
    assert "votes" not in snapshot
    assert "vote_targets" not in snapshot


# ---- The message ----------------------------------------------------------

def test_the_protocol_accepts_a_skip_vote():
    assert protocol.parse_client_message('{"type": "vote", "target_id": ""}') == {"type": "vote", "target_id": ""}


@pytest.mark.parametrize("target", [" ", None, 0, False, [], "  Mara"])
def test_the_protocol_rejects_other_empty_or_wrong_targets(target):
    import json
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_client_message(json.dumps({"type": "vote", "target_id": target}))


def test_the_protocol_still_needs_a_target():
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_client_message('{"type": "vote"}')


# ---- Over the WebSocket -------------------------------------------------------

def test_everybody_voting_ends_the_meeting_early_over_the_websocket(connect, clock):
    names = ("Mara", "Tiago", "Ines", "Rui")
    connections, _code, _public, _start = start_classic(connect, names)
    round_state = classic_for(names[0])
    lobby = app.state.lobbies.lobby_of(names[0])
    lobby.meeting = start_discussion(list(names), [], clock.now, round_state.state())
    clock.wait(45.0)

    for voter in names[:-1]:
        connections[voter].send_json({"type": "vote", "target_id": SKIP})
        snapshots = [connection.receive_json() for connection in connections.values()]
        assert all(snapshot == snapshots[0] for snapshot in snapshots)
        assert snapshots[0]["phase"] == "voting"
        assert "vote_targets" not in snapshots[0]

    connections[names[-1]].send_json({"type": "vote", "target_id": names[0]})
    snapshots = [connection.receive_json() for connection in connections.values()]
    assert all(snapshot == snapshots[0] for snapshot in snapshots)
    assert snapshots[0]["phase"] == "result"
    assert snapshots[0]["ejected_id"] is None  # three Skip against one vote
    assert lobby.round_is_running()

    # The vote is over: a further vote is refused.
    connections[names[0]].send_json({"type": "vote", "target_id": SKIP})
    answer = connections[names[0]].receive_json()
    while answer["type"] != "error":  # the news of the result comes first
        answer = connections[names[0]].receive_json()
    assert answer["code"] == "vote_rejected"
