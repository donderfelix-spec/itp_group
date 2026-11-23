"""S-218: the emergency button is locked again for 45 s after every meeting.

It unlocks 45 s after the later of the round's start and the end of the
last meeting, report or emergency (`emergency_unlocks_at` in
server/classic/round.py, times passed in). The end of a meeting is its
deadline, the moment its result is applied and the round goes on. A press
before then is refused with "The emergency button unlocks in N seconds.",
heard only by the one who pressed; after a meeting every page is sent the
new unlock time in `classic_progress`. One call per living player stays
(S-123). Replaces the "no cooldown" part of S-172.
"""

import random

import pytest

from server.classic.round import EMERGENCY_DELAY_SECONDS, ClassicRound, emergency_unlocks_at
from server import main
from server.main import app
from task_helpers import client, clock, connect, put  # noqa: F401
from test_classic_meeting_once import (
    FIVE,
    classic_round,
    everybody_skips,
    everybody_votes,
    everything_sent,
    read_until,
    start_emergency,
    ticks,
)

BUTTON = (app.state.campus["button"]["x"], app.state.campus["button"]["y"])


# ---- The plain rule ----------------------------------------------------------------


def test_before_any_meeting_the_button_unlocks_45_s_after_the_start():
    assert emergency_unlocks_at(100.0) == 145.0
    assert emergency_unlocks_at(100.0, None) == 145.0


def test_after_a_meeting_it_unlocks_45_s_after_the_meetings_end():
    assert emergency_unlocks_at(100.0, 300.0) == 345.0
    assert emergency_unlocks_at(100.0, 120.0) == 165.0  # a meeting in the first 45 s is impossible, still the later


def finished_meeting(game, ended_at):
    meeting = dict(game.meeting or {}, phase="result", deadline=ended_at, vote_result=None)
    return meeting


def a_round(started_at=0.0):
    return ClassicRound(list(FIVE), list(range(1, 12)), random.Random(7), started_at=started_at)


def test_the_round_counts_from_the_end_of_the_last_meeting_with_the_edge_at_exactly_45_s():
    game = a_round()
    assert game.emergency_seconds_left(44.0) == 1.0  # the start rule is unchanged
    game.apply_meeting_result(finished_meeting(game, 200.0))

    assert game.emergency_seconds_left(244.0) == 1.0
    assert game.emergency_seconds_left(200.0 + EMERGENCY_DELAY_SECONDS) == 0.0
    caller = next(name for name in FIVE if game.roles[name] == "HP")
    with pytest.raises(ValueError, match="not unlocked"):
        game.emergency(caller, 244.99)
    assert game.emergency(caller, 245.0)["reason"] == "emergency"


def test_two_meetings_in_a_row_count_from_the_second():
    game = a_round()
    game.apply_meeting_result(finished_meeting(game, 200.0))
    game.apply_meeting_result(finished_meeting(game, 260.0))
    assert game.emergency_seconds_left(250.0) == 55.0
    assert game.emergency_seconds_left(305.0) == 0.0


def test_a_meeting_without_a_readable_end_locks_nothing_new():
    game = a_round()
    game.apply_meeting_result({"phase": "result", "deadline": float("nan")})
    assert game.last_meeting_ended_at is None
    assert game.emergency_seconds_left(45.0) == 0.0


# ---- Over the WebSocket -------------------------------------------------------------


def press(connections, name):
    put(name, BUTTON)
    for connection in connections.values():
        everything_sent(connection)
    connections[name].send_json({"type": "emergency"})


def test_right_after_a_meeting_a_player_at_the_button_is_refused_and_only_he_hears_it(connect, clock):
    connections, lobby, _fr, [caller, other, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    everybody_skips(connections, lobby, clock)
    ticks(connections, count=1)

    press(connections, other)  # he stands at the button, his call is unused
    refused = read_until(connections[other], "error")[-1]
    assert refused["code"] == "emergency_rejected"
    assert refused["message"] == "The emergency button unlocks in 45 seconds."
    for name in FIVE:
        if name != other:
            assert [m for m in everything_sent(connections[name]) if m["type"] in ("error", "meeting_state")] == []
    assert lobby.meeting["applied"] is True and lobby.classic_round.phase == "round"


def test_44_s_after_the_meeting_still_refused_at_45_s_accepted(connect, clock):
    connections, lobby, _fr, [caller, other, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    everybody_skips(connections, lobby, clock)
    ticks(connections, count=1)

    clock.wait(44)
    press(connections, other)
    assert read_until(connections[other], "error")[-1]["message"] == "The emergency button unlocks in 1 second."

    clock.wait(1)
    press(connections, other)
    for connection in connections.values():
        state = read_until(connection, "meeting_state")[-1]
        assert state["reason"] == "emergency" and state["trigger_player_id"] == other


def test_after_a_meeting_every_page_is_sent_the_new_unlock_time(connect, clock):
    connections, lobby, _fr, [caller, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    told = everybody_skips(connections, lobby, clock)
    ticks(connections, count=1)
    ended_at = lobby.classic_round.last_meeting_ended_at
    assert ended_at == lobby.meeting["deadline"]
    assert lobby.classic_round.emergency_seconds_left(main.seconds_now()) == pytest.approx(45, abs=0.5)
    for name in FIVE:
        progress = [m for m in told[name] + everything_sent(connections[name]) if m["type"] == "classic_progress"]
        assert progress, name
        last = progress[-1]
        assert last["emergency_ready_at"] - last["server_time"] == pytest.approx(45, abs=0.5), name


def test_a_report_meeting_locks_the_button_too(connect, clock):
    connections, lobby, fr, [reporter, other, *_] = classic_round(connect)
    clock.wait(46)  # the start lock is over
    game = lobby.classic_round
    game.apply_meeting_result(finished_meeting(game, main.seconds_now()))  # as a report meeting's end
    press(connections, other)
    assert read_until(connections[other], "error")[-1]["message"] == "The emergency button unlocks in 45 seconds."


def test_a_meeting_that_ends_the_round_leaves_the_next_round_on_the_start_rule(connect, clock):
    connections, lobby, fr, [caller, other, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    everybody_votes(connections, lobby, clock, lambda voter: fr if voter != fr else caller, last="lobby_state")
    assert lobby.classic_round is None

    connections[FIVE[0]].send_json({"type": "start_game"})
    for connection in connections.values():
        read_until(connection, "lobby_state")
    game = lobby.classic_round
    assert game.last_meeting_ended_at is None
    assert game.emergency_seconds_left(main.seconds_now()) == pytest.approx(45, abs=0.5)
