"""A leaver's Skip, and Skip reaching 75 % because somebody left (M3-3.11 with S-162).

A player who leaves a meeting is out of the living, and their vote, their
Skip and the votes for them are gone. With one living player fewer, the
Skips that are left can now be 75 % of the living: then the meeting ends at
once, as after the Skip that reaches 75 %, and its result is applied once
(S-156) and sent once. This is checked in the leave path of server/main.py
(`end_if_enough_skips`, which knows the time). Since S-212 this holds in
the discussion of an emergency meeting too, as after a report. If the leave
stops the round (S-157), there is no meeting result at all.
"""

import pytest

from server import main
from server.classic import meeting as meeting_rules
from server.classic.meeting import DISCUSSION_SECONDS, EjectResult
from task_helpers import client, clock, connect  # noqa: F401
from test_classic_leaving import classic_round, drain, everything_now, leave, of_type, start_emergency


def a_meeting(phase="voting", reason="report", skips=(), votes=None):
    """Five living players; the vote ends at 175.0."""
    meeting = meeting_rules.start_discussion(["Ana", "Bo", "Cy", "Dan", "Eve"], [], 100.0)
    meeting["phase"] = phase
    meeting["deadline"] = 175.0
    meeting["reason"] = reason
    meeting["skip_votes"] = set(skips)
    meeting["votes"] = dict(votes or {})
    return meeting


# ---- The rules on their own ------------------------------------------------------

def test_a_leavers_skip_is_gone():
    updated = meeting_rules.remove_player(a_meeting(skips={"Ana", "Bo"}), "Bo")
    assert updated["skip_votes"] == {"Ana"}
    snapshot = meeting_rules.meeting_snapshot(updated, 120.0)
    assert snapshot["skip_voted"] == ["Ana"]


def test_a_leaver_is_in_no_vote_target_of_the_snapshot():
    meeting = a_meeting(votes={"Ana": "Bo", "Bo": "Cy", "Cy": "Ana"})
    snapshot = meeting_rules.meeting_snapshot(meeting_rules.remove_player(meeting, "Bo"), 120.0)
    assert snapshot["vote_targets"] == {"Cy": "Ana"}
    assert "Bo" not in snapshot["voted"] and "Bo" not in snapshot["living"]


@pytest.mark.parametrize("phase", ["discussion", "voting"])
@pytest.mark.parametrize("reason", ["report", "emergency"])
def test_three_skips_end_the_meeting_once_a_fourth_living_player_left(phase, reason):
    # Five living: 3 Skips are 60 %. Dan leaves: 3 of 4 are 75 %.
    meeting = a_meeting(phase=phase, reason=reason, skips={"Ana", "Bo", "Cy"}, votes={"Eve": "Ana"})
    assert meeting_rules.end_if_enough_skips(meeting, 120.0) is meeting  # not yet

    updated = meeting_rules.end_if_enough_skips(meeting_rules.remove_player(meeting, "Dan"), 120.0)

    assert updated["phase"] == "result"
    assert updated["deadline"] == 120.0
    assert updated["vote_result"] == EjectResult(None, False, None)


def test_a_leave_during_an_emergency_discussion_below_the_skip_threshold_ends_nothing():
    # Two Skips out of four living players are still below 75 % after Dan leaves.
    meeting = a_meeting(phase="discussion", reason="emergency", skips={"Ana", "Bo"})
    updated = meeting_rules.remove_player(meeting, "Dan")
    assert meeting_rules.end_if_enough_skips(updated, 120.0) is updated


def test_a_finished_meeting_or_nobody_living_ends_nothing_again():
    finished = meeting_rules.advance_meeting(a_meeting(skips={"Ana", "Bo", "Cy", "Dan"}), 175.0)
    assert meeting_rules.end_if_enough_skips(finished, 176.0) is finished
    empty = a_meeting()
    empty["living"] = ()
    assert meeting_rules.end_if_enough_skips(empty, 120.0) is empty


def test_ending_by_skips_needs_a_real_time():
    with pytest.raises(ValueError, match="time"):
        meeting_rules.end_if_enough_skips(a_meeting(), float("nan"))


# ---- Over the network -----------------------------------------------------------

def results_in(messages):
    return [m for m in messages if m["type"] == "meeting_state" and m["phase"] == "result"]


def skip(connections, *names):
    for name in names:
        connections[name].send_json({"type": "skip_discussion"})
        drain(connections)


def test_a_leave_that_brings_the_skips_to_75_percent_ends_the_meeting_once(connect, clock):
    connections, lobby, [fr], [caller, first, leaver, last] = classic_round(connect)
    start_emergency(connections, caller, clock)
    clock.wait(DISCUSSION_SECONDS)  # the vote is open
    skip(connections, fr, caller, first)  # 3 of 5: not yet
    assert lobby.meeting["phase"] == "voting"

    told = leave(connections, leaver)
    later = everything_now(connections)  # the next tick has nothing more to send

    assert lobby.meeting["phase"] == "result" and lobby.meeting["applied"] is True
    assert lobby.classic_round.phase == "round"
    assert lobby.classic_round.eliminated == {leaver}
    for name in connections:
        results = results_in(told[name] + later[name])
        assert len(results) == 1
        assert results[0]["ejected_id"] is None
        assert leaver not in results[0]["living"] and leaver not in results[0]["skip_voted"]
    # The one who neither pressed Skip nor left is still living and saw the result once.
    assert last not in lobby.classic_round.eliminated
    assert len(results_in(told[last] + later[last])) == 1


def test_a_leave_in_the_discussion_of_an_emergency_ends_the_meeting_by_the_skips_too(connect, clock):
    # S-212: Skip is open at once after an emergency call, so a leave can
    # bring it to 75 % before the vote phase, exactly as after a report.
    connections, lobby, [fr], [caller, first, leaver, last] = classic_round(connect)
    start_emergency(connections, caller, clock)
    skip(connections, fr, caller, first)  # 3 of 5: not yet
    assert lobby.meeting["phase"] == "discussion"

    told = leave(connections, leaver)
    later = everything_now(connections)

    assert lobby.meeting["phase"] == "result" and lobby.meeting["applied"] is True
    assert lobby.classic_round.eliminated == {leaver}
    for name in connections:
        results = results_in(told[name] + later[name])
        assert len(results) == 1
        assert results[0]["ejected_id"] is None
    assert last not in lobby.classic_round.eliminated


def test_a_leave_ends_the_meeting_before_anything_is_sent(connect, clock, monkeypatch):
    # S-165: "at once". The leave's first sends wait; in that time another
    # handler can run. Here `first` takes back his Skip while the lobby's
    # state is being sent. The meeting must already be over by then.
    connections, lobby, [fr], [caller, first, leaver, _last] = classic_round(connect)
    start_emergency(connections, caller, clock)
    clock.wait(DISCUSSION_SECONDS)
    skip(connections, fr, caller, first)
    seen = {}
    send_the_lobby = main.tell_lobby

    async def lobby_while_a_skip_is_taken_back(the_lobby, new_host=None):
        if not seen:  # only the leave below; later leaves (closing the test) go on as usual
            seen["phase"] = the_lobby.meeting["phase"]
            try:
                # What the Skip handler would do in this window.
                the_lobby.meeting = meeting_rules.agree_to_skip_discussion(the_lobby.meeting, first, main.seconds_now())
                seen["taken_back"] = True
            except ValueError:
                seen["taken_back"] = False
        await send_the_lobby(the_lobby, new_host)

    monkeypatch.setattr(main, "tell_lobby", lobby_while_a_skip_is_taken_back)
    told = leave(connections, leaver)
    later = everything_now(connections)

    assert seen == {"phase": "result", "taken_back": False}
    assert lobby.meeting["phase"] == "result" and lobby.meeting["applied"] is True
    for name in connections:
        assert len(results_in(told[name] + later[name])) == 1


def test_a_leave_with_too_few_skips_leaves_the_vote_open(connect, clock):
    connections, lobby, [fr], [caller, leaver, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    clock.wait(DISCUSSION_SECONDS)
    skip(connections, fr, caller)  # 2 of 5, then 2 of 4: not 75 %

    told = leave(connections, leaver)

    assert lobby.meeting["phase"] == "voting"
    for messages in told.values():
        snapshot = of_type(messages, "meeting_state")[-1]
        assert snapshot["phase"] == "voting"
        assert sorted(snapshot["skip_voted"]) == sorted([fr, caller])


def test_a_leave_that_stops_the_round_sends_no_meeting_result(connect, clock):
    # Six players with two Free Riders. Four of six press Skip (67 %). A
    # High Performer leaves: 4 of the 5 left would be 80 %, but five players
    # allow only one living Free Rider (S-157), so the round is stopped
    # first and there is no meeting result at all.
    six = ("Mara", "Tiago", "Ines", "Rui", "Luca", "Nina")
    connections, lobby, frs, [caller, first, leaver, *_] = classic_round(connect, six)
    assert len(frs) == 2
    start_emergency(connections, caller, clock)
    clock.wait(DISCUSSION_SECONDS)
    skip(connections, *frs, caller, first)
    assert lobby.meeting["phase"] == "voting"

    told = leave(connections, leaver)

    assert lobby.classic_round is None and lobby.meeting is None
    for messages in told.values():
        assert results_in(messages) == []
        assert of_type(messages, "classic_result") == []
        assert any(m["type"] == "notice" and "stopped" in m["message"] for m in messages)
        assert of_type(messages, "lobby_state")[-1]["phase"] == "lobby"
