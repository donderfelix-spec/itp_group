"""S-215: once every living player has voted or chosen Skip, the meeting ends 10 seconds later.

The meeting's end becomes the earlier of its old end and now + 10 s, once
per meeting (`shorten_when_everybody_voted` in server/classic/meeting.py).
Taking a vote back or changing it afterwards neither gives the time back
nor starts it again; ghosts do not count; the 75 % Skip still ends the
meeting at once; a leave that leaves only voters shortens it too. Replaces
"the vote ends when its 30 seconds run out, also when everybody has voted"
of S-162 for the case where everybody has voted.
"""

import math

import pytest

from server import main
from server.classic import meeting as rules
from server.classic.meeting import DISCUSSION_SECONDS, VOTING_SECONDS
from task_helpers import client, clock, connect  # noqa: F401
from test_classic_leaving import classic_round, drain, leave, start_emergency, tick
from test_classic_refused_meeting_actions import (
    GHOST,
    LIVING,
    SKIP,
    codes,
    forget_what_was_sent,
    lobby_in_a_meeting,
    run_the_tick_sends,
    send,
    set_clock,
    vote,
)

FIVE = ["Ana", "Bo", "Cy", "Dan", "Eve"]


def a_meeting(phase="voting", deadline=175.0, reason="report", votes=None, skips=(), ghosts=("Gus",)):
    """Five living players and a ghost; the meeting began at 100.0."""
    meeting = rules.start_discussion(FIVE, list(ghosts), 100.0)
    meeting.update(phase=phase, deadline=deadline, reason=reason)
    meeting["votes"] = dict(votes or {})
    meeting["skip_votes"] = set(skips)
    return meeting


ALL_BUT_EVE = {"Ana": "Bo", "Bo": "Cy", "Cy": "Bo", "Dan": "Bo"}


# ---- The plain rule ----------------------------------------------------------------


def test_the_last_vote_in_the_voting_phase_leaves_ten_seconds():
    meeting = a_meeting(votes=ALL_BUT_EVE | {"Eve": "Bo"})
    updated = rules.shorten_when_everybody_voted(meeting, 150.0)
    assert updated["deadline"] == 160.0 and updated["ends_by"] == 160.0
    assert meeting["deadline"] == 175.0  # the input is not changed
    assert rules.meeting_snapshot(updated, 150.0)["seconds_left"] == 10


def test_skips_count_as_voted_and_ghosts_do_not_count():
    meeting = a_meeting(votes={"Ana": "Bo", "Bo": "Cy"}, skips={"Cy", "Dan"})
    assert rules.shorten_when_everybody_voted(meeting, 150.0) is meeting  # Eve has not decided
    meeting["skip_votes"].add("Eve")
    # Gus, the ghost, never votes; the living have all decided.
    assert rules.shorten_when_everybody_voted(meeting, 150.0)["deadline"] == 160.0


def test_one_living_player_without_a_vote_changes_nothing():
    meeting = a_meeting(votes=ALL_BUT_EVE)
    assert rules.shorten_when_everybody_voted(meeting, 150.0) is meeting


@pytest.mark.parametrize(("left", "expected"), [(10.0, 175.0), (9.0, 175.0), (10.5, 175.0 - 0.5)])
def test_the_end_is_the_earlier_of_the_old_end_and_ten_seconds_from_now(left, expected):
    # 10 s or less left: nothing changes; 10.5 s left: half a second less.
    meeting = a_meeting(votes=ALL_BUT_EVE | {"Eve": "Bo"})
    updated = rules.shorten_when_everybody_voted(meeting, 175.0 - left)
    assert updated["deadline"] == expected


def test_it_happens_once_taking_a_vote_back_or_voting_again_changes_nothing():
    shortened = rules.shorten_when_everybody_voted(a_meeting(votes=ALL_BUT_EVE | {"Eve": "Bo"}), 150.0)
    taken_back = rules.cast_vote(shortened, "Eve", "Bo")  # the same target again: taken back
    assert "Eve" not in taken_back["votes"]
    assert rules.shorten_when_everybody_voted(taken_back, 152.0)["deadline"] == 160.0  # not given back
    again = rules.cast_vote(taken_back, "Eve", "Ana")
    assert rules.shorten_when_everybody_voted(again, 155.0)["deadline"] == 160.0  # not started again
    changed = rules.cast_vote(again, "Ana", "Eve")  # votes can still change in the seconds left
    assert changed["votes"]["Ana"] == "Eve" and changed["deadline"] == 160.0


def test_in_the_discussion_the_meeting_ends_ten_seconds_later_without_a_vote_phase():
    meeting = a_meeting(phase="discussion", deadline=145.0, votes=ALL_BUT_EVE | {"Eve": "Bo"})
    updated = rules.shorten_when_everybody_voted(meeting, 110.0)
    assert updated["deadline"] == 120.0 and updated["phase"] == "discussion"
    assert rules.can_send_chat(updated, "Ana", "still talking", 119.0)  # the chat ends with the meeting

    assert rules.advance_meeting(updated, 119.9)["phase"] == "discussion"
    ended = rules.advance_meeting(updated, 120.0)
    assert ended["phase"] == "result" and ended["deadline"] == 120.0
    assert ended["vote_result"].ejected_id == "Bo"


def test_late_in_the_discussion_the_discussion_lasts_until_the_ten_seconds():
    # 5 s of discussion are left: the discussion runs on to the meeting's end,
    # with no short vote phase whose clock would jump up again (S-225).
    meeting = a_meeting(phase="discussion", deadline=145.0, votes=ALL_BUT_EVE | {"Eve": "Bo"})
    updated = rules.shorten_when_everybody_voted(meeting, 140.0)
    assert updated["deadline"] == 150.0 and updated["ends_by"] == 150.0
    assert rules.advance_meeting(updated, 146.0)["phase"] == "discussion"
    assert rules.can_send_chat(updated, "Ana", "still talking", 149.0)
    ended = rules.advance_meeting(updated, 150.0)
    assert ended["phase"] == "result" and ended["deadline"] == 150.0


@pytest.mark.parametrize(("phase", "deadline", "voted_at"), [
    ("discussion", 145.0, 110.0),  # plenty of discussion left
    ("discussion", 145.0, 140.0),  # 5 s of discussion left
    ("discussion", 145.0, 136.0),  # 9 s of discussion left
    ("voting", 175.0, 150.0),  # in the vote phase
    ("voting", 175.0, 168.0),  # 7 s left: nothing changes
])
def test_after_everybody_voted_the_clock_only_counts_down_and_the_result_comes_at_zero(phase, deadline, voted_at):
    meeting = a_meeting(phase=phase, deadline=deadline, votes=ALL_BUT_EVE | {"Eve": "Bo"})
    shortened = rules.shorten_when_everybody_voted(meeting, voted_at)
    seen = []
    now = voted_at
    while True:
        snapshot = rules.meeting_snapshot(shortened, now)
        seen.append((now, snapshot["phase"], snapshot["seconds_left"]))
        if snapshot["phase"] == "result":
            break
        now += 0.5
    clock = [left for _, _, left in seen]
    assert clock == sorted(clock, reverse=True), seen  # never up again
    assert clock[0] <= 10 and clock[-1] == 0
    assert seen[-1][0] <= voted_at + 10  # the result comes at the end, not later
    assert seen[-2][2] <= 1  # the last clock before the result shows 1 or 0


def test_an_emergency_discussion_is_shortened_too():
    meeting = a_meeting(phase="discussion", deadline=145.0, reason="emergency", votes=ALL_BUT_EVE | {"Eve": "Bo"})
    assert rules.shorten_when_everybody_voted(meeting, 110.0)["deadline"] == 120.0


@pytest.mark.parametrize("state", [
    {"phase": "discussion", "reason": None},  # voting not open
    {"phase": "result"},
    {"deadline": 150.0},  # the time already ran out
])
def test_nothing_changes_where_voting_is_not_open(state):
    meeting = a_meeting(votes=ALL_BUT_EVE | {"Eve": "Bo"})
    meeting.update(state)
    assert rules.shorten_when_everybody_voted(meeting, 150.0) is meeting


def test_a_leave_that_leaves_only_voters_shortens_the_meeting():
    meeting = rules.remove_player(a_meeting(votes=ALL_BUT_EVE), "Eve")
    assert rules.shorten_when_everybody_voted(meeting, 150.0)["deadline"] == 160.0


def test_skip_at_75_percent_still_ends_the_meeting_at_once():
    meeting = a_meeting(votes={"Ana": "Bo"}, skips={"Bo", "Cy"})
    shortened = rules.shorten_when_everybody_voted(rules.cast_vote(meeting, "Dan", "Bo"), 150.0)
    assert "ends_by" not in shortened  # Eve has not decided
    ended = rules.agree_to_skip_discussion(meeting, "Dan", 150.0)
    ended = rules.agree_to_skip_discussion(ended, "Eve", 151.0)
    assert ended["phase"] == "result" and ended["deadline"] == 151.0
    assert rules.shorten_when_everybody_voted(ended, 151.0) is ended


@pytest.mark.parametrize("now", [float("nan"), math.inf, True, "150"])
def test_the_rule_needs_a_real_time(now):
    with pytest.raises(ValueError, match="time"):
        rules.shorten_when_everybody_voted(a_meeting(), now)


# ---- The handlers (stand-in connections: Mara, Tiago, Rui living, Ines a ghost) -----


def test_the_last_vote_sends_everybody_the_ten_seconds_and_the_tick_the_result_once(monkeypatch):
    lobby, sockets = lobby_in_a_meeting(monkeypatch)  # a report discussion until 145.0
    send(sockets, "Mara", vote("Tiago"))
    send(sockets, "Tiago", vote("Mara"))
    forget_what_was_sent(sockets)
    send(sockets, "Rui", SKIP)  # Rui decides last; 1 Skip of 3 is not 75 %

    for name, socket in sockets.items():  # the ghost too: everybody sees the same clock
        assert codes(socket) == ["meeting_state"], name
        assert socket.messages[0]["seconds_left"] == 10 and socket.messages[0]["phase"] == "discussion"
    assert lobby.meeting["deadline"] == 111.0

    forget_what_was_sent(sockets)
    set_clock(monkeypatch, 111.0)
    run_the_tick_sends(monkeypatch, lobby)
    run_the_tick_sends(monkeypatch, lobby)
    for socket in sockets.values():
        results = [m for m in socket.messages if m["type"] == "meeting_state" and m["phase"] == "result"]
        assert len(results) == 1
    # Nobody was voted out (a tie, Skip as strong); the Free Rider's cooldown starts at the real end.
    assert lobby.classic_round.last_fail_at["Mara"] == 111.0


def test_a_refused_vote_shortens_nothing_and_is_heard_only_by_the_sender(monkeypatch):
    lobby, sockets = lobby_in_a_meeting(monkeypatch)
    send(sockets, "Mara", vote("Tiago"))
    send(sockets, "Tiago", vote("Mara"))
    forget_what_was_sent(sockets)
    send(sockets, GHOST, vote("Rui"))  # a ghost's vote is refused and counts for nobody
    assert codes(sockets[GHOST]) == ["vote_rejected"]
    assert all(not socket.messages for name, socket in sockets.items() if name != GHOST)
    assert lobby.meeting["deadline"] == 145.0 and "ends_by" not in lobby.meeting


def test_taking_the_last_vote_back_does_not_give_the_time_back(monkeypatch):
    lobby, sockets = lobby_in_a_meeting(monkeypatch)
    for voter, target in zip(LIVING, ["Tiago", "Rui", "Mara"]):
        send(sockets, voter, vote(target))
    assert lobby.meeting["deadline"] == 111.0
    set_clock(monkeypatch, 105.0)
    forget_what_was_sent(sockets)
    send(sockets, "Rui", vote("Mara"))  # taken back
    send(sockets, "Rui", vote("Tiago"))  # and cast again
    assert lobby.meeting["deadline"] == 111.0
    assert [m["seconds_left"] for m in sockets["Ines"].messages] == [6, 6]


def test_a_leave_that_leaves_only_voters_shortens_the_meeting_over_the_websocket(connect, clock):
    connections, lobby, [fr], [caller, first, second, leaver] = classic_round(connect)
    start_emergency(connections, caller, clock)
    for voter in (fr, caller, first, second):
        connections[voter].send_json({"type": "vote", "target_id": leaver if voter != leaver else fr})
        drain(connections)
    assert "ends_by" not in lobby.meeting  # the leaver has not voted
    # Every vote was for the leaver; they would go with him. Vote again, so that `first` has the most.
    for voter, target in ((caller, first), (second, first), (first, fr), (fr, caller)):
        connections[voter].send_json({"type": "vote", "target_id": target})
        drain(connections)
    assert "ends_by" not in lobby.meeting

    now = main.seconds_now()
    told = leave(connections, leaver)

    assert lobby.meeting["ends_by"] == pytest.approx(now + 10, abs=0.5)
    for name, messages in told.items():
        states = [m for m in messages if m["type"] == "meeting_state"]
        assert states and states[-1]["seconds_left"] == 10, name
    clock.wait(10)
    tick(connections)
    assert lobby.meeting["phase"] == "result"
    assert lobby.meeting["vote_result"].ejected_id == first


def test_without_everybody_voted_the_meeting_keeps_its_full_time(connect, clock):
    connections, lobby, [fr], [caller, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    connections[caller].send_json({"type": "vote", "target_id": fr})
    drain(connections)
    assert lobby.meeting["deadline"] == pytest.approx(main.seconds_now() + DISCUSSION_SECONDS, abs=1)
    clock.wait(DISCUSSION_SECONDS)
    tick(connections)
    assert lobby.meeting["phase"] == "voting"
    assert lobby.meeting["deadline"] - main.seconds_now() == pytest.approx(VOTING_SECONDS, abs=1)


def test_the_ghost_and_the_living_get_the_same_shortened_snapshot(monkeypatch):
    # Rule 1: the shortened clock is public, like the votes; no new field is sent.
    lobby, sockets = lobby_in_a_meeting(monkeypatch)
    for voter, target in zip(LIVING, ["Tiago", "Rui", "Mara"]):
        send(sockets, voter, vote(target))
    last = {name: socket.messages[-1] for name, socket in sockets.items()}
    assert all(message == last[GHOST] for message in last.values())
    assert last[GHOST]["seconds_left"] == 10
    assert "ends_by" not in last[GHOST]
