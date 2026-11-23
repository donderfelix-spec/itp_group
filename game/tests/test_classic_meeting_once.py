"""A meeting's result is applied exactly once (M3-3.9).

The finished meeting stays in `lobby.meeting` until the next meeting
replaces it or the round ends. Before this fix every tick applied its
result again: it set the round's ghosts back to the list of the meeting,
and a player failed after the meeting came back to life. Now the meeting
is marked "applied" the first time, and later calls change nothing. Only
the player voted out is added to the ghosts. A chat or a vote after the
meeting is refused; a new meeting can start.
"""

import random
import time

from rules import FAIL_COOLDOWN_SECONDS
from server import main
from server.classic.meeting import DISCUSSION_SECONDS, VOTING_SECONDS
from server.classic.round import ClassicRound
from server.main import app
from task_helpers import client, clock, connect, placeholder_at_every_station, put  # noqa: F401
from test_classic_server_features import classic_for, start_classic
from test_server_duel import REAL_TICK

FIVE = ("Mara", "Tiago", "Ines", "Rui", "Luca")
# Far from every hiding spot and from each other.
FAR_PLACES = [(100.0, 330.0), (300.0, 330.0), (300.0, 400.0), (200.0, 300.0), (400.0, 300.0)]
FAIL_PLACE = (500.0, 450.0)


# Helpers


def classic_round(connect):
    """A Classic round of five, everybody far apart. Returns (connections, lobby, FR, HPs)."""
    connections, _code, _public, _start = start_classic(connect, FIVE)
    roles = classic_for(FIVE[0]).roles
    for name, place in zip(FIVE, FAR_PLACES):
        put(name, place)
    fr = next(name for name in FIVE if roles[name] == "FR")
    high_performers = [name for name in FIVE if roles[name] == "HP"]
    return connections, app.state.lobbies.lobby_of(fr), fr, high_performers


def everything_sent(connection):
    """Every message this connection got so far. Never waits forever.

    A hello is sent, and everything before its answer is collected.
    """
    connection.send_json({"type": "hello", "name": "Reader"})
    arrived = []
    while True:
        message = connection.receive_json()
        if message["type"] == "welcome":
            return arrived
        arrived.append(message)


def read_until(connection, wanted, at_most=100):
    """The messages of this connection up to and including the next one of type `wanted`.

    Fails clearly instead of reading on and on when `at_most` messages came
    and none of them was the one wanted.
    """
    received = []
    while not received or received[-1]["type"] != wanted:
        assert len(received) < at_most, f"no {wanted} among {at_most} messages: {[m['type'] for m in received]}"
        received.append(connection.receive_json())
    return received


def everybody_until(connections, wanted):
    """`read_until` for every member. Returns `{name: messages}`."""
    return {name: read_until(connection, wanted) for name, connection in connections.items()}


def wait_for_background_sends():
    """Wait until the sends the server started as tasks of their own are done (the tick, positions)."""
    deadline = time.monotonic() + 5
    while main.background_sends:
        assert time.monotonic() < deadline, "the server's background sends did not finish"
        time.sleep(0.01)


def results_in(messages):
    return [m for m in messages if m["type"] == "meeting_state" and m["phase"] == "result"]


def ticks(connections, count=3):
    """Run the server's real tick a few times, as the server does every 50 ms.

    The tick sends in the background; this waits until those sends are done.
    """
    first = next(iter(connections.values()))
    for _ in range(count):
        first.portal.call(REAL_TICK, 0.0)
    wait_for_background_sends()


def start_emergency(connections, caller, clock):
    """`caller` presses the emergency button (it unlocks 45 s after the start)."""
    clock.wait(46)
    put(caller, (app.state.campus["button"]["x"], app.state.campus["button"]["y"]))
    connections[caller].send_json({"type": "emergency"})
    for connection in connections.values():
        assert connection.receive_json()["type"] == "meeting_state"


def everybody_votes(connections, lobby, clock, target_of, last="positions"):
    """After the discussion every living player votes `target_of(voter)`, then the vote's time runs out.

    Votes can change (S-160), so all votes cast do not end the vote; the
    tick ends it with its time. Returns what each member was sent, up to
    the message of type `last`: the positions that follow the result, or
    the lobby state when the result ends the round. The votes are cast one
    after the other, each once everybody has its snapshot, so no two vote
    handlers run at the same time.
    """
    clock.wait(DISCUSSION_SECONDS)
    living = [name for name in FIVE if name not in lobby.classic_round.eliminated]
    told = {name: [] for name in connections}
    for voter in living:
        connections[voter].send_json({"type": "vote", "target_id": target_of(voter)})
        for name, messages in everybody_until(connections, "meeting_state").items():
            told[name] += messages
    clock.wait(VOTING_SECONDS)
    ticks(connections, count=1)
    for name in connections:
        told[name] += read_until(connections[name], "classic_roster")  # the result, then the roster
        told[name] += read_until(connections[name], last)
    return told


def everybody_skips(connections, lobby, clock, last="positions"):
    """After the discussion the living press Skip until 75 % have (S-162): the meeting ends at once.

    With five living players the fourth Skip ends it. Returns what each
    member was sent, up to the message of type `last`, like `everybody_votes`.
    """
    clock.wait(DISCUSSION_SECONDS)
    living = [name for name in FIVE if name not in lobby.classic_round.eliminated]
    needed = -(-3 * len(living) // 4)  # 75 %, rounded up
    told = {name: [] for name in connections}
    for skipper in living[:needed - 1]:
        connections[skipper].send_json({"type": "skip_discussion"})
        for name, messages in everybody_until(connections, "meeting_state").items():
            told[name] += messages
    connections[living[needed - 1]].send_json({"type": "skip_discussion"})
    for name, messages in everybody_until(connections, last).items():
        told[name] += messages
    return told


def fail(connections, fr, victim):
    """`fr` fails `victim`, who stands beside him; everybody else is far away."""
    for name, place in zip(FIVE, FAR_PLACES):
        put(name, place)
    put(fr, FAIL_PLACE)
    put(victim, (FAIL_PLACE[0] + 1, FAIL_PLACE[1]))
    connections[fr].send_json({"type": "fail"})
    for connection in connections.values():
        while connection.receive_json()["type"] != "positions":
            pass


def count_applications(monkeypatch):
    """Count the calls of `ClassicRound.apply_meeting_result`. Returns the list of calls."""
    calls = []
    apply = ClassicRound.apply_meeting_result

    def counted(round_state, meeting):
        calls.append(meeting)
        apply(round_state, meeting)

    monkeypatch.setattr(ClassicRound, "apply_meeting_result", counted)
    return calls


# Accepted: the result is applied once and sent once; the finished meeting stays until the next one


def test_a_failure_after_a_meeting_stays_failed_across_ticks(connect, clock):
    connections, lobby, fr, [caller, victim, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    everybody_skips(connections, lobby, clock)
    assert lobby.meeting["applied"] is True

    clock.wait(FAIL_COOLDOWN_SECONDS)  # the cooldown starts again after a meeting (DESIGN.md 5.8)
    fail(connections, fr, victim)
    ticks(connections)

    assert victim in lobby.classic_round.eliminated
    assert lobby.classic_round.phase == "round"


def test_an_ejection_is_applied_once(connect, clock, monkeypatch):
    calls = count_applications(monkeypatch)
    connections, lobby, _fr, [caller, ejected, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)

    told = everybody_votes(connections, lobby, clock, lambda voter: ejected if voter != ejected else caller)
    ticks(connections)

    assert len(calls) == 1
    assert lobby.classic_round.eliminated == {ejected}
    assert lobby.classic_round.phase == "round"
    assert lobby.meeting["applied"] is True
    for messages in told.values():
        assert results_in(messages)[0]["ejected_id"] == ejected


def test_the_result_of_an_early_end_is_sent_once(connect, clock):
    connections, lobby, _fr, [caller, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)

    told = everybody_skips(connections, lobby, clock)
    ticks(connections)
    clock.wait(VOTING_SECONDS)
    ticks(connections)
    later = {name: everything_sent(connection) for name, connection in connections.items()}

    for name in FIVE:
        assert len(results_in(told[name])) == 1
        # The news of the result follows it, as before.
        types = [message["type"] for message in told[name]]
        assert types[-3:] == ["meeting_state", "classic_roster", "positions"]
        assert results_in(later[name]) == []


def test_a_meeting_ended_by_its_time_is_sent_once_by_the_tick(connect, clock, monkeypatch):
    calls = count_applications(monkeypatch)
    connections, lobby, _fr, [caller, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    clock.wait(DISCUSSION_SECONDS + VOTING_SECONDS)

    ticks(connections)
    # The tick sends the result, then the roster (the tick's own positions
    # may come in between, so the test waits for the roster).
    told = everybody_until(connections, "classic_roster")
    ticks(connections)
    later = {name: everything_sent(connection) for name, connection in connections.items()}

    assert len(calls) == 1
    assert lobby.meeting["applied"] is True
    assert lobby.classic_round.phase == "round"
    for name in FIVE:
        assert len(results_in(told[name])) == 1
        assert results_in(later[name]) == []


def test_a_vote_that_comes_after_the_time_ran_out_gets_the_result_sent_once(connect, clock):
    connections, lobby, _fr, [caller, voter, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    clock.wait(DISCUSSION_SECONDS + VOTING_SECONDS)  # no tick in between

    connections[voter].send_json({"type": "vote", "target_id": caller})
    assert connections[voter].receive_json()["code"] == "vote_rejected"
    told = everybody_until(connections, "classic_roster")  # the result, then the roster
    ticks(connections)
    later = {name: everything_sent(connection) for name, connection in connections.items()}

    assert lobby.meeting["applied"] is True
    for name in FIVE:
        assert len(results_in(told[name] + later[name])) == 1


def test_a_second_meeting_can_start_after_the_first(connect, clock):
    connections, lobby, _fr, [first_caller, second_caller, *_] = classic_round(connect)
    start_emergency(connections, first_caller, clock)
    everybody_skips(connections, lobby, clock)
    ticks(connections)

    put(second_caller, (app.state.campus["button"]["x"], app.state.campus["button"]["y"]))
    connections[second_caller].send_json({"type": "emergency"})
    snapshots = [read_until(connection, "meeting_state")[-1] for connection in connections.values()]

    assert all(snapshot["type"] == "meeting_state" for snapshot in snapshots)
    assert all(snapshot["phase"] == "discussion" for snapshot in snapshots)
    # The new meeting replaced the finished one.
    assert lobby.meeting["phase"] == "discussion" and not lobby.meeting.get("applied")
    assert lobby.classic_round.meeting_count == 2


def test_a_vote_that_ejects_the_free_rider_still_ends_the_round(connect, clock):
    connections, lobby, fr, [caller, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)

    told = everybody_votes(connections, lobby, clock, lambda voter: fr if voter != fr else caller, last="lobby_state")

    assert lobby.classic_round is None and lobby.meeting is None  # the round ended
    for messages in told.values():
        result = next(message for message in messages if message["type"] == "classic_result")
        assert result["winner"] == "HP"
        assert len(results_in(messages)) == 1
        # S-166: the vote's result is sent before the end of the round.
        assert messages.index(results_in(messages)[0]) < messages.index(result)


# Rejected: chat and votes once the meeting is over


def test_chat_and_vote_after_the_meeting_are_refused_and_apply_nothing_again(connect, clock, monkeypatch):
    calls = count_applications(monkeypatch)
    connections, lobby, fr, [caller, other, victim, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    everybody_skips(connections, lobby, clock)
    clock.wait(FAIL_COOLDOWN_SECONDS)  # the cooldown starts again after a meeting (DESIGN.md 5.8)
    fail(connections, fr, victim)

    connections[other].send_json({"type": "chat", "text": "Too late?"})
    assert connections[other].receive_json()["code"] == "chat_rejected"
    connections[other].send_json({"type": "vote", "target_id": caller})
    assert connections[other].receive_json()["code"] == "vote_rejected"
    ticks(connections)

    assert len(calls) == 1
    assert lobby.classic_round.eliminated == {victim}


def test_a_chat_after_the_time_ran_out_is_refused_and_the_result_applied_once(connect, clock, monkeypatch):
    calls = count_applications(monkeypatch)
    connections, lobby, _fr, [caller, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    clock.wait(DISCUSSION_SECONDS + VOTING_SECONDS)

    connections[caller].send_json({"type": "chat", "text": "Hello?"})
    assert connections[caller].receive_json()["code"] == "chat_rejected"
    ticks(connections)
    # The tick sends the result again, then the roster.
    told = everybody_until(connections, "classic_roster")

    assert len(calls) == 1
    assert lobby.meeting["applied"] is True
    for name in FIVE:
        assert results_in(told[name])  # everybody got the result


# The rule itself, without a network


def a_round_in_a_meeting():
    """A ClassicRound of five with a running emergency meeting. Returns (game, FR, HPs)."""
    game = ClassicRound(list(FIVE), list(range(1, 12)), random.Random(7))
    fr = next(name for name, role in game.roles.items() if role == "FR")
    high_performers = [name for name, role in game.roles.items() if role == "HP"]
    game.emergency(high_performers[0], 100.0)
    return game, fr, high_performers


def finished(game, votes):
    """The game's meeting, voted to its result with these votes."""
    from server.classic.meeting import advance_meeting

    meeting = dict(game.meeting, phase="voting", votes=dict(votes))
    return advance_meeting(meeting, meeting["deadline"] + DISCUSSION_SECONDS + VOTING_SECONDS)


def test_apply_meeting_result_adds_only_the_player_voted_out():
    game, _fr, [first, second, *_] = a_round_in_a_meeting()
    meeting = finished(game, {name: second for name in FIVE})

    game.apply_meeting_result(meeting)

    assert game.eliminated == {second}
    assert game.phase == "round"
    assert game.timers_paused is False
    assert game.meeting is meeting


def test_apply_meeting_result_adds_nobody_when_nobody_is_voted_out():
    game, _fr, _hps = a_round_in_a_meeting()
    meeting = finished(game, {})

    game.apply_meeting_result(meeting)

    assert game.eliminated == set()
    assert game.phase == "round"


def test_apply_meeting_result_keeps_a_ghost_the_meeting_did_not_know():
    # The heart of the old defect: the meeting's own list of ghosts is older
    # than the round. A ghost the round has now must stay a ghost.
    game, _fr, [_first, second, later_ghost, *_] = a_round_in_a_meeting()
    meeting = finished(game, {name: second for name in FIVE})
    game.eliminated.add(later_ghost)

    game.apply_meeting_result(meeting)

    assert game.eliminated == {second, later_ghost}


class LobbyInAMeeting:
    """Just the parts of a lobby that `settle_meeting` reads."""

    def __init__(self, game, meeting):
        self.classic_round = game
        self.meeting = meeting


def test_sync_applies_a_finished_meeting_once_and_marks_it():
    game, _fr, [_first, second, later_ghost, *_] = a_round_in_a_meeting()
    lobby = LobbyInAMeeting(game, finished(game, {name: second for name in FIVE}))

    main.settle_meeting(lobby)
    game.eliminated.add(later_ghost)  # a failure after the meeting
    main.settle_meeting(lobby)  # the next tick
    main.settle_meeting(lobby)

    assert lobby.meeting["applied"] is True
    assert game.eliminated == {second, later_ghost}


def test_sync_leaves_a_running_meeting_alone():
    game, _fr, _hps = a_round_in_a_meeting()
    lobby = LobbyInAMeeting(game, game.meeting)

    main.settle_meeting(lobby)

    assert "applied" not in lobby.meeting
    assert game.phase == "meeting"


def test_sync_without_a_meeting_or_a_round_does_nothing():
    game, _fr, _hps = a_round_in_a_meeting()
    main.settle_meeting(LobbyInAMeeting(game, None))
    assert game.phase == "meeting"

    meeting = finished(game, {})
    main.settle_meeting(LobbyInAMeeting(None, meeting))
    assert "applied" not in meeting
