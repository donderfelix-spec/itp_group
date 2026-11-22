"""A player who leaves a running Classic round counts as out (M3-3.11).

DESIGN.md, section 5: "If someone leaves the round, that player counts as
failed, and their open tasks disappear from the progress bar." The tasks
they finished keep counting. A leaver is also taken out of a running
meeting: out of the living, their vote and the votes for them are gone.
Every way of leaving does the same: "Leave", logging out, a lost connection.
"""

import random
import time

import pytest

from rules import FAIL_COOLDOWN_SECONDS, progress, tasks_after_leaving
from server.classic import meeting as meeting_rules
from server.classic.meeting import DISCUSSION_SECONDS, SKIP, VOTING_SECONDS
from server import main
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


def classic_round(connect, names=FIVE):
    """A running Classic round, everybody far apart. Returns (connections, lobby, FRs, HPs)."""
    connections, _code, _public, _start = start_classic(connect, names)
    roles = classic_for(names[0]).roles
    for name, place in zip(names, FAR_PLACES):
        put(name, place)
    free_riders = [name for name in names if roles[name] == "FR"]
    high_performers = [name for name in names if roles[name] == "HP"]
    return connections, app.state.lobbies.lobby_of(names[0]), free_riders, high_performers


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


def of_type(messages, wanted):
    return [message for message in messages if message["type"] == wanted]


def names_in(message):
    return {entry["name"] for entry in message["players"]}


def leave(connections, name):
    """`name` presses "Leave". Returns what everybody else was sent then."""
    connection = connections.pop(name)
    connection.send_json({"type": "leave_lobby"})
    assert connection.receive_json()["type"] == "left_lobby"
    # The server answers the leaver's next message only once it has told
    # everybody else about the leave, so after this all news is on its way.
    assert everything_sent(connection) == []
    wait_for_background_sends()
    return {other: everything_sent(conn) for other, conn in connections.items()}


def wait_for_background_sends():
    """Wait until the sends the server started as tasks of their own are done (positions, the tick)."""
    deadline = time.monotonic() + 5
    while main.background_sends:
        assert time.monotonic() < deadline, "the server's background sends did not finish"
        time.sleep(0.01)


def everything_now(connections):
    """Every message each member got so far, once the server has sent all it had to.

    The server answers a player's hello only after it has handled that
    player's earlier messages. So once everybody's first hello is answered,
    every handler is done; once the background sends are done too, a second
    hello collects everything they sent.
    """
    first = {name: everything_sent(connection) for name, connection in connections.items()}
    wait_for_background_sends()
    return {name: first[name] + everything_sent(connections[name]) for name in first}


def drain(connections):
    """Throw away everything sent so far (see `everything_now`)."""
    everything_now(connections)


def fail(connections, fr, victim):
    """`fr` fails `victim`, who stands beside him; everybody else stands far away."""
    for name, place in zip(connections, FAR_PLACES):
        put(name, place)
    put(fr, FAIL_PLACE)
    put(victim, (FAIL_PLACE[0] + 1, FAIL_PLACE[1]))
    connections[fr].send_json({"type": "fail"})
    drain(connections)


def start_emergency(connections, caller, clock):
    clock.wait(46)  # the button unlocks 45 seconds after the start
    connections[caller].send_json({"type": "emergency"})
    drain(connections)


def tick(connections):
    """Run the server's real tick once, as the server does every 50 ms.

    The tick sends in the background; this waits until those sends are done.
    """
    next(iter(connections.values())).portal.call(REAL_TICK, 0.0)
    wait_for_background_sends()


def finish_two_tasks(round_state, player):
    for station in round_state.tasks[player][:2]:
        round_state.station_done(player, int(station))


# The progress rule on its own


def test_tasks_after_leaving_keep_only_the_finished_ones():
    tasks = {"Ana": ["1", "2", "3", "4"], "Bo": ["5", "7", "8", "9"]}
    completed = {"Ana": {"2", "4"}, "Bo": {"5"}}

    updated = tasks_after_leaving(tasks, completed, "Ana")

    assert updated == {"Ana": ["2", "4"], "Bo": ["5", "7", "8", "9"]}
    # The lists given are not changed.
    assert tasks == {"Ana": ["1", "2", "3", "4"], "Bo": ["5", "7", "8", "9"]}


def test_tasks_after_leaving_with_nothing_finished_leaves_nothing():
    assert tasks_after_leaving({"Ana": ["1", "2"]}, {}, "Ana") == {"Ana": []}


def test_tasks_after_leaving_of_an_unknown_player_changes_nothing():
    tasks = {"Ana": ["1", "2"]}
    assert tasks_after_leaving(tasks, {"Ana": {"1"}}, "Zoe") == tasks


def test_progress_after_a_leave_counts_finished_tasks_and_drops_open_ones():
    state = {
        "roles": {"Ana": "HP", "Bo": "HP", "Cy": "FR"},
        "tasks": {"Ana": ["1", "2", "3", "4"], "Bo": ["5", "7", "8", "9"], "Cy": ["10", "11", "12", "1"]},
        "completed_tasks": {"Ana": {"1"}, "Bo": {"5", "7"}, "Cy": set()},
        "eliminated": set(),
    }
    assert progress(state) == 3 / 8

    state["tasks"] = tasks_after_leaving(state["tasks"], state["completed_tasks"], "Bo")

    # Bo's two finished tasks still count, his two open ones are gone.
    assert progress(state) == 3 / 6


# The round's own state


def a_round():
    game = ClassicRound(list(FIVE), list(range(1, 12)), random.Random(7))
    fr = next(name for name, role in game.roles.items() if role == "FR")
    high_performers = [name for name, role in game.roles.items() if role == "HP"]
    return game, fr, high_performers


def test_remove_player_counts_the_leaver_as_failed_and_recomputes_progress():
    game, _fr, [leaver, *_] = a_round()
    finish_two_tasks(game, leaver)
    game.take_news()

    game.remove_player(leaver)

    assert leaver in game.eliminated
    assert len(game.tasks[leaver]) == 2
    assert game.progress() == 2 / 14
    assert game.take_news() is True


def test_remove_player_of_a_ghost_changes_only_the_progress_total():
    game, _fr, [ghost, other, *_] = a_round()
    finish_two_tasks(game, other)
    game.eliminated.add(ghost)
    before = set(game.eliminated)

    game.remove_player(ghost)

    assert game.eliminated == before
    assert game.progress() == 2 / 12


def test_remove_player_who_has_no_role_changes_nothing():
    game, _fr, _hps = a_round()
    game.take_news()

    game.remove_player("Zoe")

    assert game.eliminated == set()
    assert game.take_news() is False


def test_the_last_free_rider_leaving_lets_the_high_performers_win():
    game, fr, _hps = a_round()
    game.remove_player(fr)
    assert game.winner() == "HP"
    assert game.result_reason() == "all_free_riders_eliminated"


# The meeting rule on its own


def a_meeting_in_the_vote():
    meeting = meeting_rules.start_discussion(["Ana", "Bo", "Cy", "Dan"], ["Eve"], 100.0)
    meeting["phase"] = "voting"
    # Depends on S-151/S-152 (Skip as vote "", early end): adapt to Lennart's vote rules.
    meeting["votes"] = {"Ana": "Bo", "Bo": "Dan", "Cy": SKIP, "Dan": "Bo"}
    return meeting


def test_meeting_remove_player_takes_the_leaver_and_the_votes_for_him_out():
    meeting = a_meeting_in_the_vote()

    updated = meeting_rules.remove_player(meeting, "Bo")

    assert updated["living"] == ("Ana", "Cy", "Dan")
    # Depends on S-151/S-152 (Skip as vote "", early end): adapt to Lennart's vote rules.
    assert updated["votes"] == {"Cy": SKIP}
    # The meeting given is not changed.
    assert meeting["living"] == ("Ana", "Bo", "Cy", "Dan")
    assert "Bo" in meeting["votes"]


def test_meeting_remove_player_takes_a_ghost_out_of_the_ghosts():
    updated = meeting_rules.remove_player(a_meeting_in_the_vote(), "Eve")
    assert updated["ghosts"] == ()
    assert updated["living"] == ("Ana", "Bo", "Cy", "Dan")


def test_meeting_remove_player_of_somebody_else_changes_no_list():
    meeting = a_meeting_in_the_vote()
    updated = meeting_rules.remove_player(meeting, "Zoe")
    assert updated["living"] == meeting["living"] and updated["votes"] == meeting["votes"]


def test_a_vote_for_the_leaver_ejects_nobody():
    meeting = a_meeting_in_the_vote()
    # Depends on S-151/S-152 (Skip as vote "", early end): adapt to Lennart's vote rules.
    meeting["votes"] = {"Ana": "Bo", "Cy": "Bo", "Dan": "Bo"}
    updated = meeting_rules.remove_player(meeting, "Bo")

    result = meeting_rules.advance_meeting(updated, updated["deadline"])

    assert result["phase"] == "result"
    assert result["vote_result"].ejected_id is None


def test_meeting_remove_player_counts_the_leaver_in_the_meetings_copy_of_the_round():
    game, _fr, [caller, leaver, *_] = a_round()
    finish_two_tasks(game, leaver)
    meeting = game.emergency(caller, 100.0)

    updated = meeting_rules.remove_player(meeting, leaver)

    assert leaver in updated["eliminated"]
    assert len(updated["tasks"][leaver]) == 2


# Accepted: over the network


def test_with_five_a_high_performer_leaves_and_the_round_goes_on(connect):
    connections, lobby, [fr], [leaver, *others] = classic_round(connect)
    round_state = lobby.classic_round
    finish_two_tasks(round_state, leaver)
    drain(connections)

    told = leave(connections, leaver)

    assert lobby.classic_round is round_state and lobby.round_is_running()
    assert leaver in round_state.eliminated
    for name, messages in told.items():
        assert leaver not in names_in(of_type(messages, "lobby_state")[-1])
        assert names_in(of_type(messages, "classic_roster")[-1]) == set(FIVE) - {leaver}
        # 16 tasks of four High Performers: the leaver's 2 open ones are gone, his 2 finished count.
        assert of_type(messages, "classic_progress")[-1]["progress"] == pytest.approx(2 / 14)
        assert of_type(messages, "classic_result") == []
    assert fr in told and len(others) == 3


def test_with_five_the_free_rider_leaves_and_the_high_performers_win(connect):
    connections, lobby, [fr], _hps = classic_round(connect)
    drain(connections)

    told = leave(connections, fr)

    assert lobby.classic_round is None
    for messages in told.values():
        result = of_type(messages, "classic_result")[-1]
        assert result["winner"] == "HP"
        assert result["reason"] == "all_free_riders_eliminated"
        assert of_type(messages, "lobby_state")[-1]["phase"] == "lobby"


def test_parity_after_two_fails_and_a_leave_lets_the_free_rider_win(connect, clock):
    connections, lobby, [fr], [first, second, leaver, _] = classic_round(connect)
    fail(connections, fr, first)
    clock.wait(FAIL_COOLDOWN_SECONDS)
    fail(connections, fr, second)
    assert lobby.classic_round is not None  # 1 Free Rider, 2 living: no parity yet

    told = leave(connections, leaver)

    for messages in told.values():
        result = of_type(messages, "classic_result")[-1]
        assert result["winner"] == "FR"
        assert result["reason"] == "free_riders_reached_parity"


def test_a_ghost_who_leaves_changes_only_the_lists_and_the_progress_total(connect):
    connections, lobby, [fr], [ghost, worker, *_] = classic_round(connect)
    fail(connections, fr, ghost)
    finish_two_tasks(lobby.classic_round, worker)
    eliminated_before = set(lobby.classic_round.eliminated)

    told = leave(connections, ghost)

    assert lobby.classic_round.eliminated == eliminated_before
    assert lobby.round_is_running()
    for messages in told.values():
        # The ghost had finished nothing: the total is 12 now.
        assert of_type(messages, "classic_progress")[-1]["progress"] == pytest.approx(2 / 12)
        assert ghost not in names_in(of_type(messages, "classic_roster")[-1])


def test_a_lost_connection_counts_like_leave(connect):
    connections, lobby, _frs, [leaver, *_] = classic_round(connect)
    drain(connections)

    connections.pop(leaver).close()
    # The server notices the closed connection in its own time.
    told = {name: [] for name in connections}
    for name, connection in connections.items():
        while not of_type(told[name], "classic_roster"):
            told[name].append(connection.receive_json())

    assert leaver in lobby.classic_round.eliminated
    for messages in told.values():
        assert leaver not in names_in(of_type(messages, "lobby_state")[-1])
        assert leaver not in names_in(of_type(messages, "classic_roster")[-1])


# A meeting


def test_a_leaver_in_the_discussion_is_gone_from_the_living_in_the_next_snapshot(connect, clock):
    connections, lobby, _frs, [caller, leaver, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)

    told = leave(connections, leaver)

    for messages in told.values():
        snapshot = of_type(messages, "meeting_state")[-1]
        assert snapshot["phase"] == "discussion"
        assert leaver not in snapshot["living"]
    assert leaver not in lobby.meeting["living"]


def test_a_leaver_in_the_vote_is_gone_from_the_voters_and_so_are_the_votes_for_him(connect, clock):
    connections, lobby, [fr], [caller, leaver, other, last] = classic_round(connect)
    start_emergency(connections, caller, clock)
    clock.wait(DISCUSSION_SECONDS)
    # Depends on S-151/S-152 (Skip as vote "", early end): adapt to Lennart's vote rules.
    connections[leaver].send_json({"type": "vote", "target_id": caller})
    connections[caller].send_json({"type": "vote", "target_id": leaver})
    connections[other].send_json({"type": "vote", "target_id": leaver})
    drain(connections)
    assert set(lobby.meeting["votes"]) == {leaver, caller, other}

    told = leave(connections, leaver)

    assert lobby.meeting["votes"] == {}
    for messages in told.values():
        snapshot = of_type(messages, "meeting_state")[-1]
        assert snapshot["phase"] == "voting"
        assert leaver not in snapshot["living"]
        # Depends on S-151/S-152 (Skip as vote "", early end): adapt to Lennart's vote rules.
        assert snapshot["voted"] == []

    # The vote ends by its time: a vote for the leaver ejects nobody.
    clock.wait(VOTING_SECONDS)
    tick(connections)
    results = {name: of_type(messages, "meeting_state")[-1] for name, messages in everything_now(connections).items()}
    for result in results.values():
        assert result["phase"] == "result"
        assert result["ejected_id"] is None
        assert leaver not in result["living"]
    assert lobby.classic_round.eliminated == {leaver}
    assert fr in connections and last in connections


def test_a_leave_that_ends_the_round_during_a_meeting_sends_the_result(connect, clock):
    connections, lobby, [fr], [caller, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)

    told = leave(connections, fr)

    assert lobby.classic_round is None and lobby.meeting is None
    for messages in told.values():
        result = of_type(messages, "classic_result")[-1]
        assert result["winner"] == "HP"


# Rejected and edge cases


def test_leaving_twice_is_refused_the_second_time(connect):
    connections, lobby, _frs, [leaver, *_] = classic_round(connect)
    drain(connections)
    connection = connections[leaver]
    leave(connections, leaver)

    connection.send_json({"type": "leave_lobby"})
    assert connection.receive_json()["code"] == "not_in_lobby"
    assert leaver in lobby.classic_round.eliminated


def test_a_leaver_gets_no_more_news_of_the_round(connect):
    connections, lobby, _frs, [leaver, *_] = classic_round(connect)
    drain(connections)
    connection = connections[leaver]
    leave(connections, leaver)

    assert everything_sent(connection) == []


def test_a_high_performer_who_left_a_round_that_goes_on_cannot_join_it_again(connect):
    connections, lobby, _frs, [leaver, *_] = classic_round(connect)
    drain(connections)
    connection = connections[leaver]
    leave(connections, leaver)
    assert lobby.round_is_running()

    connection.send_json({"type": "join_lobby", "code": lobby.code})

    assert connection.receive_json() == {
        "type": "error", "code": "round_running", "message": "This round has already started.",
    }
    assert leaver not in lobby.names()
