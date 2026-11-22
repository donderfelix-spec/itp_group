"""Public votes that can change, voting during a report, and Skip at 75 % (Lennart's rules).

Felix, 2026-11-22: "Build Lennart's version" (branch Spielfluss-und-Bug-Fixing).
- Clicking the same player again takes the vote back; another player replaces it.
- Who voted for whom, and who pressed Skip, is in every meeting snapshot.
- After a report the players may vote during the discussion; after an
  emergency meeting only once the voting phase has started.
- Skip is its own message, `skip_discussion`. It toggles the own Skip and
  takes back the own vote. At 75 % of the living players the meeting ends at
  once with its result.
- The count: Skip with at least as many as the leading player ejects nobody,
  and the same number is a tie. A player who did not vote is not a Skip.

Replaces tests/test_classic_skip_vote.py, which checked the older rule
(S-151, S-152): Skip as a secret, final vote with an empty target, and the
vote ending once everybody had voted.
"""

import asyncio
import json

import pytest

from server import main, protocol
from server.classic.meeting import (
    EjectResult,
    advance_meeting,
    agree_to_skip_discussion,
    cast_vote,
    meeting_snapshot,
    start_discussion,
    tally_votes,
    voting_is_open,
)
from server.net.lobbies import Lobbies
from server.net.sessions import Sessions
from task_helpers import client, clock, connect  # noqa: F401
from test_classic_triggers_area3 import failed_sheet, receive_broadcast


FIVE = {"A": "HP", "B": "HP", "C": "HP", "D": "HP", "F": "FR"}


def meeting(roles, phase="voting", reason="report", votes=None, skips=None):
    """A meeting of these living players. Its deadline is 30.0 by the clock."""
    state = start_discussion(
        list(roles), [], 0.0,
        {
            "roles": roles,
            "tasks": {player_id: ["1", "2", "3", "4"] for player_id in roles},
            "completed_tasks": {},
            "eliminated": set(),
        },
    )
    state["phase"] = phase
    state["deadline"] = 30.0
    state["reason"] = reason
    state["votes"] = dict(votes or {})
    state["skip_votes"] = set(skips or ())
    return state


def living_players(count):
    """Roles for `count` living players: the last one is the Free Rider."""
    names = [f"P{index}" for index in range(1, count + 1)]
    return {name: ("FR" if name == names[-1] else "HP") for name in names}


def result_of(state):
    """The result once the time of the vote has run out."""
    return advance_meeting(state, 30.0)["vote_result"]


# ---- A vote can be changed and taken back ------------------------------------

def test_another_player_replaces_the_vote():
    state = cast_vote(meeting(FIVE), "A", "B")
    changed = cast_vote(state, "A", "F")
    assert changed["votes"] == {"A": "F"}
    assert state["votes"] == {"A": "B"}  # the input stays as it was


def test_the_same_player_again_takes_the_vote_back():
    state = cast_vote(meeting(FIVE), "A", "F")
    withdrawn = cast_vote(state, "A", "F")
    assert withdrawn["votes"] == {}
    assert cast_vote(withdrawn, "A", "F")["votes"] == {"A": "F"}  # and once more


def test_a_vote_takes_back_the_own_skip_only():
    state = meeting(FIVE, skips={"A", "B"})
    voted = cast_vote(state, "A", "F")
    assert voted["skip_votes"] == {"B"}
    assert voted["votes"] == {"A": "F"}


def test_a_vote_for_a_ghost_or_a_stranger_or_by_a_ghost_is_rejected():
    state = meeting(FIVE)
    state["living"] = ("A", "B", "C", "F")
    state["ghosts"] = ("D",)
    with pytest.raises(ValueError, match="living player"):
        cast_vote(state, "A", "D")
    with pytest.raises(ValueError, match="living player"):
        cast_vote(state, "A", "Nobody")
    with pytest.raises(ValueError, match="living players may vote"):
        cast_vote(state, "D", "A")


def test_the_empty_target_is_no_longer_a_vote():
    # Skip has its own message now (replaces S-151's empty target).
    with pytest.raises(ValueError):
        cast_vote(meeting(FIVE), "A", "")
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_client_message('{"type": "vote", "target_id": ""}')


# ---- Votes are public -------------------------------------------------------

def test_the_snapshot_shows_who_voted_for_whom_and_who_skipped():
    state = meeting(FIVE, votes={"A": "F", "B": "F", "C": "A"}, skips={"D"})
    snapshot = meeting_snapshot(state, 10.0)
    assert snapshot["vote_targets"] == {"A": "F", "B": "F", "C": "A"}
    assert snapshot["skip_voted"] == ["D"]
    assert sorted(snapshot["voted"]) == ["A", "B", "C"]
    assert "votes" not in snapshot and "roles" not in snapshot


def test_the_snapshot_follows_a_changed_and_a_withdrawn_vote():
    state = cast_vote(meeting(FIVE), "A", "B")
    assert meeting_snapshot(state, 10.0)["vote_targets"] == {"A": "B"}
    state = cast_vote(state, "A", "C")
    assert meeting_snapshot(state, 10.0)["vote_targets"] == {"A": "C"}
    state = cast_vote(state, "A", "C")
    assert meeting_snapshot(state, 10.0)["vote_targets"] == {}


def test_a_new_meeting_has_no_votes_and_no_skips():
    snapshot = meeting_snapshot(start_discussion(["A", "B"], [], 0.0), 1.0)
    assert snapshot["vote_targets"] == {}
    assert snapshot["skip_voted"] == []


# ---- When voting is open -------------------------------------------------------

@pytest.mark.parametrize(
    ("phase", "reason", "is_open"),
    [
        ("discussion", "report", True),
        ("voting", "report", True),
        ("discussion", "emergency", False),
        ("voting", "emergency", True),
        ("discussion", None, False),
        ("result", "report", False),
        ("result", "emergency", False),
    ],
)
def test_voting_is_open_during_a_report_discussion_and_every_voting_phase(phase, reason, is_open):
    assert voting_is_open(meeting(FIVE, phase=phase, reason=reason)) is is_open


def test_a_vote_during_a_report_discussion_stays_into_the_voting_phase():
    state = cast_vote(meeting(FIVE, phase="discussion"), "A", "F")
    assert state["phase"] == "discussion"
    voting = advance_meeting(state, 30.0)
    assert voting["phase"] == "voting"
    assert voting["votes"] == {"A": "F"}


def test_no_vote_and_no_skip_during_an_emergency_discussion():
    state = meeting(FIVE, phase="discussion", reason="emergency")
    with pytest.raises(ValueError, match="not open"):
        cast_vote(state, "A", "F")
    with pytest.raises(ValueError, match="not open"):
        agree_to_skip_discussion(state, "A", 5.0)


def test_no_vote_after_the_result():
    state = advance_meeting(meeting(FIVE), 30.0)
    with pytest.raises(ValueError, match="not open"):
        cast_vote(state, "A", "F")


# ---- Skip ---------------------------------------------------------------------

def test_skip_toggles_the_own_skip():
    state = agree_to_skip_discussion(meeting(FIVE), "A", 5.0)
    assert state["skip_votes"] == {"A"}
    undone = agree_to_skip_discussion(state, "A", 6.0)
    assert undone["skip_votes"] == set()
    assert undone["phase"] == "voting"


def test_skip_takes_back_the_own_vote():
    state = meeting(FIVE, votes={"A": "F", "B": "F"})
    skipped = agree_to_skip_discussion(state, "A", 5.0)
    assert skipped["votes"] == {"B": "F"}
    assert skipped["skip_votes"] == {"A"}


def test_undoing_skip_does_not_bring_the_old_vote_back():
    state = agree_to_skip_discussion(meeting(FIVE, votes={"A": "F"}), "A", 5.0)
    assert agree_to_skip_discussion(state, "A", 6.0)["votes"] == {}


# 75 % of the living, rounded up: 4 -> 3, 5 -> 4 (3.75), 7 -> 6 (5.25).
@pytest.mark.parametrize(("living", "needed"), [(4, 3), (5, 4), (7, 6)])
def test_skip_by_75_percent_of_the_living_ends_the_meeting_at_once(living, needed):
    roles = living_players(living)
    names = list(roles)
    state = meeting(roles, phase="discussion")
    for name in names[:needed - 1]:
        state = agree_to_skip_discussion(state, name, 5.0)
        assert state["phase"] == "discussion"  # one short of the threshold
    state = agree_to_skip_discussion(state, names[needed - 1], 7.5)
    assert state["phase"] == "result"
    assert state["deadline"] == 7.5
    assert state["vote_result"] == EjectResult(None, False, None)
    assert state["winner"] is None


def test_ghosts_do_not_count_for_the_75_percent():
    # Five players, one of them a ghost: 3 of the 4 living are enough.
    state = meeting(FIVE)
    state["living"] = ("A", "B", "C", "F")
    state["ghosts"] = ("D",)
    for name in ("A", "B"):
        state = agree_to_skip_discussion(state, name, 5.0)
    assert agree_to_skip_discussion(state, "C", 5.0)["phase"] == "result"


def test_skip_ends_with_the_result_even_when_votes_were_cast():
    # Four living: three Skip and one vote. Skip has more, so nobody goes.
    roles = living_players(4)
    state = meeting(roles, votes={"P4": "P1"}, skips={"P1", "P2"})
    finished = agree_to_skip_discussion(state, "P3", 5.0)
    assert finished["phase"] == "result"
    assert finished["vote_result"].ejected_id is None
    assert finished["living"] == ("P1", "P2", "P3", "P4")


def test_a_ghost_cannot_skip():
    state = meeting(FIVE)
    state["living"] = ("A", "B", "C", "F")
    state["ghosts"] = ("D",)
    with pytest.raises(ValueError, match="living"):
        agree_to_skip_discussion(state, "D", 5.0)


def test_skip_after_the_deadline_is_rejected():
    with pytest.raises(ValueError, match="already ended"):
        agree_to_skip_discussion(meeting(FIVE), "A", 30.0)


def test_skip_after_the_result_is_rejected():
    state = advance_meeting(meeting(FIVE), 30.0)
    with pytest.raises(ValueError, match="not open"):
        agree_to_skip_discussion(state, "A", 31.0)


@pytest.mark.parametrize("bad_time", [float("nan"), float("inf"), True, "5"])
def test_skip_needs_a_real_time(bad_time):
    with pytest.raises(ValueError, match="time"):
        agree_to_skip_discussion(meeting(FIVE), "A", bad_time)


# ---- The count when the time runs out --------------------------------------------

def test_the_majority_ejects_its_player():
    state = meeting(FIVE, votes={"A": "F", "B": "F", "C": "F"}, skips={"D"})
    assert result_of(state) == EjectResult("F", False, "FR")


def test_skip_with_more_votes_than_the_leader_ejects_nobody_without_a_tie():
    state = meeting(FIVE, votes={"D": "F"}, skips={"A", "B"})
    assert result_of(state) == EjectResult(None, False, None)


def test_skip_with_as_many_votes_as_the_leader_is_a_tie():
    state = meeting(FIVE, votes={"A": "F", "B": "F"}, skips={"C", "D"})
    assert result_of(state) == EjectResult(None, True, None)


def test_two_players_with_the_most_votes_tie():
    state = meeting(FIVE, votes={"A": "F", "B": "F", "C": "D", "D": "C", "F": "D"})
    assert result_of(state) == EjectResult(None, True, None)


def test_a_player_who_did_not_vote_is_not_a_skip():
    # One vote out of five living, nobody pressed Skip: that one vote ejects.
    # (Under S-151 the four others counted as Skip and nobody went.)
    assert result_of(meeting(FIVE, votes={"A": "F"})) == EjectResult("F", False, "FR")


def test_only_skips_and_no_vote_eject_nobody():
    state = meeting(FIVE, skips={"A"})
    assert result_of(state) == EjectResult(None, False, None)


def test_nobody_voting_at_all_ejects_nobody():
    assert result_of(meeting(FIVE)) == EjectResult(None, False, None)


def test_the_skip_of_a_player_who_is_no_longer_living_does_not_count():
    state = meeting(FIVE, votes={"A": "F"}, skips={"Gone"})
    state["phase"] = "result"
    assert tally_votes(state) == EjectResult("F", False, "FR")


def test_everybody_voting_does_not_end_the_vote_early():
    # Votes can change, so only Skip at 75 % or the time ends it (replaces S-152).
    votes = {"A": "F", "B": "F", "C": "F", "D": "F", "F": "A"}
    state = meeting(FIVE)
    for voter, target in votes.items():
        state = cast_vote(state, voter, target)
    assert state["phase"] == "voting"
    assert advance_meeting(state, 29.9)["phase"] == "voting"
    assert advance_meeting(state, 30.0)["phase"] == "result"


# ---- The message -------------------------------------------------------------

def test_the_protocol_accepts_skip_discussion_without_fields():
    assert protocol.parse_client_message('{"type": "skip_discussion"}') == {"type": "skip_discussion"}


@pytest.mark.parametrize("extra", [{"target_id": "Mara"}, {"skip": True}])
def test_the_protocol_rejects_skip_discussion_with_fields(extra):
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_client_message(json.dumps({"type": "skip_discussion", **extra}))


# Kept from tests/test_classic_skip_vote.py: they check the vote message, not S-151.
@pytest.mark.parametrize("target", [" ", None, 0, False, [], "  Mara"])
def test_the_protocol_rejects_other_empty_or_wrong_targets(target):
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_client_message(json.dumps({"type": "vote", "target_id": target}))


def test_the_protocol_still_needs_a_target():
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_client_message('{"type": "vote"}')


def test_skip_discussion_rejected_has_its_text_from_design():
    assert protocol.rejection("skip_discussion_rejected")["message"] == "You cannot skip this discussion right now."


# ---- The handler ---------------------------------------------------------------

class FakeSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


def lobby_with_a_report_meeting(monkeypatch, now=101.0, signed_in=True, with_meeting=True):
    """Mara and Tiago are alive, Ines is a ghost. The discussion ends at 145.0."""
    names = ["Mara", "Tiago", "Ines"]
    sockets = {name: FakeSocket() for name in names}
    sessions = Sessions()
    if signed_in:
        for name, socket in sockets.items():
            sessions.sign_in_account(socket, name)
    monkeypatch.setattr(main.app.state, "sessions", sessions)
    monkeypatch.setattr(main, "seconds_now", lambda: now)
    lobbies = Lobbies()
    lobby, _ = lobbies.create("Mara", lambda: "ABCD")
    for name in names[1:]:
        lobbies.join(name, "ABCD")
    if with_meeting:
        lobby.meeting = start_discussion(["Mara", "Tiago"], ["Ines"], 100.0)
        lobby.meeting["reason"] = "report"
    monkeypatch.setattr(main.app.state, "lobbies", lobbies)
    return lobby, sockets


def skip(socket):
    asyncio.run(main.answer_skip_discussion_message(socket))


def rejections(socket):
    return [message["code"] for message in socket.messages if message.get("type") == "error"]


def test_the_handler_rejects_a_player_who_is_not_signed_in(monkeypatch):
    lobby, sockets = lobby_with_a_report_meeting(monkeypatch, signed_in=False)
    skip(sockets["Mara"])
    assert rejections(sockets["Mara"]) == ["not_signed_in"]
    assert lobby.meeting["skip_votes"] == set()


def test_the_handler_rejects_a_player_outside_a_lobby(monkeypatch):
    lobby, sockets = lobby_with_a_report_meeting(monkeypatch)
    stranger = FakeSocket()
    main.app.state.sessions.sign_in_account(stranger, "Luca")
    skip(stranger)
    assert rejections(stranger) == ["not_in_lobby"]


def test_the_handler_rejects_skip_without_a_meeting(monkeypatch):
    lobby, sockets = lobby_with_a_report_meeting(monkeypatch, with_meeting=False)
    skip(sockets["Mara"])
    assert rejections(sockets["Mara"]) == ["skip_discussion_rejected"]
    assert lobby.meeting is None


def test_the_handler_rejects_a_ghost(monkeypatch):
    lobby, sockets = lobby_with_a_report_meeting(monkeypatch)
    skip(sockets["Ines"])
    assert rejections(sockets["Ines"]) == ["skip_discussion_rejected"]
    assert lobby.meeting["skip_votes"] == set()


def test_the_handler_rejects_skip_after_the_deadline(monkeypatch):
    # 45 s of discussion and 30 s of voting from 100.0: over at 175.0.
    lobby, sockets = lobby_with_a_report_meeting(monkeypatch, now=176.0)
    skip(sockets["Mara"])
    assert rejections(sockets["Mara"]) == ["skip_discussion_rejected"]
    assert lobby.meeting["phase"] == "result"
    assert lobby.meeting["skip_votes"] == set()


def test_the_handler_rejects_skip_in_an_emergency_discussion(monkeypatch):
    lobby, sockets = lobby_with_a_report_meeting(monkeypatch)
    lobby.meeting["reason"] = "emergency"
    skip(sockets["Mara"])
    assert rejections(sockets["Mara"]) == ["skip_discussion_rejected"]


def test_the_handler_sends_the_skips_to_everybody(monkeypatch):
    lobby, sockets = lobby_with_a_report_meeting(monkeypatch)
    skip(sockets["Mara"])
    assert lobby.meeting["phase"] == "discussion"
    for socket in sockets.values():
        assert socket.messages[-1]["type"] == "meeting_state"
        assert socket.messages[-1]["skip_voted"] == ["Mara"]
    skip(sockets["Mara"])  # and undone
    assert all(socket.messages[-1]["skip_voted"] == [] for socket in sockets.values())


# ---- Over the WebSocket ----------------------------------------------------------

def test_votes_during_a_report_discussion_reach_everybody_and_can_change(connect, clock):
    names = ("Mara", "Tiago", "Ines", "Rui", "Luca")
    connections, round_state, lobby, fr_id, ghost_id, reporter_id, position = failed_sheet(
        names, connect, clock
    )
    sheet_id = next(iter(round_state.f_sheets))
    connections[reporter_id].send_json({"type": "report", "sheet_id": sheet_id, "position": position})
    meeting_now = receive_broadcast(connections, "meeting_state")
    assert meeting_now["phase"] == "discussion"
    assert meeting_now["characters"] == dict(lobby.players())

    voter, target, other = [player for player in names if player != ghost_id][:3]
    connections[voter].send_json({"type": "vote", "target_id": target})
    assert receive_broadcast(connections, "meeting_state")["vote_targets"] == {voter: target}
    connections[voter].send_json({"type": "vote", "target_id": other})
    assert receive_broadcast(connections, "meeting_state")["vote_targets"] == {voter: other}
    connections[voter].send_json({"type": "vote", "target_id": other})
    snapshot = receive_broadcast(connections, "meeting_state")
    assert snapshot["vote_targets"] == {}
    assert snapshot["phase"] == "discussion"


def test_skip_by_three_of_four_living_ends_a_report_meeting(connect, clock):
    names = ("Mara", "Tiago", "Ines", "Rui", "Luca")
    connections, round_state, lobby, fr_id, ghost_id, reporter_id, position = failed_sheet(
        names, connect, clock
    )
    sheet_id = next(iter(round_state.f_sheets))
    connections[reporter_id].send_json({"type": "report", "sheet_id": sheet_id, "position": position})
    receive_broadcast(connections, "meeting_state")

    living = [player for player in names if player != ghost_id]
    assert len(living) == 4
    for player in living[:2]:
        connections[player].send_json({"type": "skip_discussion"})
        assert receive_broadcast(connections, "meeting_state")["phase"] == "discussion"
    connections[living[2]].send_json({"type": "skip_discussion"})
    result = receive_broadcast(connections, "meeting_state")
    assert result["phase"] == "result"
    assert result["ejected_id"] is None
    assert sorted(result["skip_voted"]) == sorted(living[:3])
    assert lobby.round_is_running()

    # The meeting is over: one more Skip is refused.
    connections[living[3]].send_json({"type": "skip_discussion"})
    answer = connections[living[3]].receive_json()
    while answer["type"] != "error":  # the news of the result comes first
        answer = connections[living[3]].receive_json()
    assert answer["code"] == "skip_discussion_rejected"


def test_an_emergency_discussion_rejects_votes_over_the_websocket(connect, clock):
    names = ("Mara", "Tiago", "Ines", "Rui")
    connections, round_state, lobby, fr_id, ghost_id, reporter_id, position = failed_sheet(
        names, connect, clock
    )
    clock.wait(45.0)  # the red button unlocks after 45 seconds
    caller = reporter_id
    connections[caller].send_json({"type": "emergency"})
    meeting_now = receive_broadcast(connections, "meeting_state")
    assert meeting_now["phase"] == "discussion"
    assert meeting_now["reason"] == "emergency"

    connections[caller].send_json({"type": "vote", "target_id": fr_id})
    answer = connections[caller].receive_json()
    assert answer["code"] == "vote_rejected"
    assert lobby.meeting["votes"] == {}
