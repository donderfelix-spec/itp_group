"""A Classic round stops when the players left no longer fit its Free Riders (M3-3.8).

After a player leaves a running Classic round, the players still in it are
counted (members of the lobby with a role, living or ghost), and so are the
Free Riders among them. The round is stopped when fewer than 4 are left, or
more Free Riders than S-48 allows for that many (1 with 4 or 5 players, 2
with 6 to 8). Too few Free Riders never stop it. The stop comes before the
win check: a stopped round has no winner and no end screen. Everybody gets
the notice "Too many players left. The round was stopped." and then the
lobby's state, phase "lobby".
"""

import pytest

from rules import FAIL_COOLDOWN_SECONDS, free_riders_for, round_still_fits
from server.main import app
from task_helpers import client, clock, connect, placeholder_at_every_station, put, put_at_station  # noqa: F401
from test_classic_server_features import classic_for, start_classic
from test_server_duel import duel_of, wait_for_news, wait_for_the_open_lobby, wait_until

FOUR = ("Mara", "Tiago", "Ines", "Rui")
FIVE = FOUR + ("Luca",)
SIX = FIVE + ("Sofia",)
# Far from every hiding spot and from each other.
FAR_PLACES = [(100.0, 330.0), (300.0, 330.0), (300.0, 400.0), (200.0, 300.0), (400.0, 300.0), (250.0, 450.0)]
FAIL_PLACE = (500.0, 450.0)
STOPPED = {"type": "notice", "message": "Too many players left. The round was stopped."}


# The rule on its own


def roles_of(count, free_riders):
    """Roles for `count` players named P0, P1, ...; the first `free_riders` are Free Riders."""
    return {f"P{index}": "FR" if index < free_riders else "HP" for index in range(count)}


@pytest.mark.parametrize("count,expected", [(4, 1), (5, 1), (6, 2), (7, 2), (8, 2)])
def test_free_riders_for_follows_s48(count, expected):
    assert free_riders_for(count) == expected


@pytest.mark.parametrize("present", [3, 4, 5, 6, 7, 8])
@pytest.mark.parametrize("free_riders", [0, 1, 2])
def test_round_still_fits_for_every_number_of_players_and_free_riders(present, free_riders):
    roles = roles_of(8, 2)
    # The first `free_riders` of the two Free Riders and enough High
    # Performers are still there.
    names = [f"P{index}" for index in range(free_riders)]
    names += [f"P{index}" for index in range(2, 2 + present - free_riders)]
    allowed = 1 if present <= 5 else 2
    expected = present >= 4 and free_riders <= allowed

    assert round_still_fits(roles, names) is expected


def test_ghosts_count_as_players_still_in_the_round():
    # A ghost is still in the round: four players, one of them failed.
    assert round_still_fits(roles_of(5, 1), ["P0", "P1", "P2", "P3"]) is True


def test_names_without_a_role_do_not_count():
    # Somebody without a role in this round (it cannot happen while a round
    # runs, but the rule does not count them).
    assert round_still_fits(roles_of(4, 1), ["P0", "P1", "P2", "Zoe"]) is False


def test_no_player_left_does_not_fit():
    assert round_still_fits(roles_of(4, 1), []) is False


# Helpers for the network


def classic_round(connect, names):
    """A running Classic round, everybody far apart. Returns (connections, lobby, FRs, HPs)."""
    connections, _code, _public, _start = start_classic(connect, names)
    roles = classic_for(names[0]).roles
    for name, place in zip(names, FAR_PLACES):
        put(name, place)
    free_riders = [name for name in names if roles[name] == "FR"]
    high_performers = [name for name in names if roles[name] == "HP"]
    return connections, app.state.lobbies.lobby_of(names[0]), free_riders, high_performers


def press_leave(connection):
    """Send "Leave" and read this connection up to its answer `left_lobby`.

    Anything still on its way to the leaver from before is skipped.
    """
    connection.send_json({"type": "leave_lobby"})
    for _ in range(50):
        if connection.receive_json()["type"] == "left_lobby":
            return
    raise AssertionError("no left_lobby among the next 50 messages")


def leave(connections, name, last="classic_progress"):
    """`name` presses "Leave" and the round goes on. Returns `{other: messages}`.

    The others are read up to the last message a continuing leave brings:
    the progress, after the lobby state and the roster. In an open lobby
    the lobby state is the last one (`last="lobby_state"`).
    """
    press_leave(connections.pop(name))
    return {other: wait_for_news(conn, last) for other, conn in connections.items()}


def leave_and_stop(connections, name):
    """`name` leaves and the round stops. Returns `{other: messages}` up to the open lobby."""
    press_leave(connections.pop(name))
    return {other: wait_for_the_open_lobby(conn) for other, conn in connections.items()}


def drain(connections):
    for connection in connections.values():
        wait_until(connection, lambda messages: True)


def types_of(messages):
    return [message["type"] for message in messages]


def assert_stopped(told, lobby):
    """Every member was told the stop, then the open lobby, and nobody got a result."""
    assert lobby.classic_round is None and lobby.meeting is None
    assert not lobby.round_is_running()
    for messages in told.values():
        assert STOPPED in messages
        assert messages[-1]["type"] == "lobby_state" and messages[-1]["phase"] == "lobby"
        assert messages.index(STOPPED) < len(messages) - 1
        assert "classic_result" not in types_of(messages)


# Accepted: the round is stopped


def test_with_four_a_high_performer_leaves_and_the_round_is_stopped(connect):
    connections, lobby, _frs, [leaver, *_] = classic_round(connect, FOUR)
    drain(connections)

    told = leave_and_stop(connections, leaver)

    assert_stopped(told, lobby)


def test_with_six_a_high_performer_leaves_and_two_free_riders_are_too_many_for_five(connect):
    connections, lobby, [_first, _second], [leaver, *_] = classic_round(connect, SIX)
    drain(connections)

    told = leave_and_stop(connections, leaver)

    assert_stopped(told, lobby)


def test_with_five_two_high_performers_leave_one_after_the_other(connect):
    connections, lobby, _frs, [first, second, *_] = classic_round(connect, FIVE)
    drain(connections)

    told = leave(connections, first)
    assert lobby.round_is_running()
    assert all(STOPPED not in messages for messages in told.values())

    told = leave_and_stop(connections, second)

    assert_stopped(told, lobby)


def test_the_stop_comes_before_the_win_check(connect, clock):
    # 4 players: the Free Rider fails one High Performer (1 against 2), then
    # a living one leaves. 1 against 1 would be parity, but only 3 players
    # are left: the round is stopped and nobody wins.
    connections, lobby, [fr], [victim, leaver, _] = classic_round(connect, FOUR)
    put(fr, FAIL_PLACE)
    put(victim, (FAIL_PLACE[0] + 1, FAIL_PLACE[1]))
    connections[fr].send_json({"type": "fail"})
    for connection in connections.values():
        wait_for_news(connection, "classic_roster")
    assert lobby.classic_round is not None

    told = leave_and_stop(connections, leaver)

    assert_stopped(told, lobby)


def test_a_stop_during_a_meeting_ends_the_meeting_with_the_round(connect, clock):
    connections, lobby, _frs, [caller, leaver, _] = classic_round(connect, FOUR)
    clock.wait(46)  # the emergency button unlocks 45 seconds after the start
    connections[caller].send_json({"type": "emergency"})
    for connection in connections.values():
        wait_for_news(connection, "meeting_state")
    assert lobby.meeting is not None

    told = leave_and_stop(connections, leaver)

    assert_stopped(told, lobby)


def test_an_open_station_is_closed_before_the_notice(connect, clock):
    connections, lobby, _frs, [worker, leaver, _] = classic_round(connect, FOUR)
    station = int(lobby.classic_round.tasks[worker][0])
    put_at_station(worker, station)
    connections[worker].send_json({"type": "open_station", "station": station})
    wait_for_news(connections[worker], "station_opened")
    drain(connections)

    told = leave_and_stop(connections, leaver)

    assert_stopped(told, lobby)
    messages = told[worker]
    assert messages.index({"type": "station_closed", "station": station}) < messages.index(STOPPED)


def test_a_lost_connection_stops_the_round_too(connect):
    connections, lobby, _frs, [leaver, *_] = classic_round(connect, FOUR)
    drain(connections)

    connections.pop(leaver).close()
    told = {name: wait_for_the_open_lobby(conn) for name, conn in connections.items()}

    assert_stopped(told, lobby)


def test_when_the_host_leaves_everybody_hears_the_stop_and_the_new_host(connect):
    connections, lobby, _frs, _hps = classic_round(connect, FOUR)
    host = FOUR[0]
    drain(connections)

    told = leave_and_stop(connections, host)

    assert_stopped(told, lobby)
    new_host = {"type": "notice", "message": f"The host left. {lobby.host} is the new host."}
    for messages in told.values():
        assert new_host in messages


def test_the_next_round_in_the_same_lobby_starts_normally_after_a_stop(connect):
    connections, lobby, _frs, [leaver, *_] = classic_round(connect, FOUR)
    drain(connections)
    leave_and_stop(connections, leaver)

    from test_classic_server_features import player
    newcomer = player(connect, "Sofia")
    newcomer.send_json({"type": "join_lobby", "code": lobby.code})
    assert newcomer.receive_json()["type"] == "lobby_state"
    connections["Sofia"] = newcomer
    drain(connections)
    host = lobby.host
    connections[host].send_json({"type": "start_game"})
    for connection in connections.values():
        wait_for_news(connection, "classic_progress")

    assert lobby.round_is_running()
    assert sorted(lobby.classic_round.roles) == sorted(connections)
    assert lobby.classic_round.eliminated == set()


# Accepted: the round goes on


def test_with_six_a_free_rider_leaves_and_the_round_goes_on(connect):
    connections, lobby, [leaver, _other], _hps = classic_round(connect, SIX)
    drain(connections)

    told = leave(connections, leaver)

    assert lobby.round_is_running() and lobby.classic_round is not None
    assert all(STOPPED not in messages for messages in told.values())


def test_with_five_the_free_rider_leaves_and_the_high_performers_win_without_a_stop(connect):
    # 4 left, no Free Rider: too few Free Riders never stop the round.
    connections, lobby, [fr], _hps = classic_round(connect, FIVE)
    drain(connections)

    connection = connections.pop(fr)
    press_leave(connection)
    told = {name: wait_for_the_open_lobby(conn) for name, conn in connections.items()}

    for messages in told.values():
        assert STOPPED not in messages
        result = next(message for message in messages if message["type"] == "classic_result")
        assert result["winner"] == "HP"
        assert result["reason"] == "all_free_riders_eliminated"


def test_with_five_parity_after_a_leave_is_a_win_not_a_stop(connect, clock):
    connections, lobby, [fr], [first, second, leaver, _] = classic_round(connect, FIVE)
    for victim in (first, second):
        for name, place in zip(FIVE, FAR_PLACES):
            put(name, place)
        put(fr, FAIL_PLACE)
        put(victim, (FAIL_PLACE[0] + 1, FAIL_PLACE[1]))
        connections[fr].send_json({"type": "fail"})
        for connection in connections.values():
            wait_for_news(connection, "classic_roster")
        clock.wait(FAIL_COOLDOWN_SECONDS)

    connection = connections.pop(leaver)
    press_leave(connection)
    told = {name: wait_for_the_open_lobby(conn) for name, conn in connections.items()}

    for messages in told.values():
        assert STOPPED not in messages
        result = next(message for message in messages if message["type"] == "classic_result")
        assert result["winner"] == "FR"


# Unchanged: Duel, and a lobby without a round


def test_a_duel_goes_on_when_a_player_leaves(connect):
    players, _code = duel_of(connect, ("Mara", "Tiago", "Ines"))
    lobby = app.state.lobbies.lobby_of("Mara")

    leaver = players.pop("Ines")
    press_leave(leaver)
    told = {name: wait_for_news(conn) for name, conn in players.items()}

    assert lobby.round_is_running() and lobby.duel is not None
    assert all(STOPPED not in messages for messages in told.values())


def test_leaving_an_open_lobby_sends_no_stop(connect):
    connections, lobby, _frs, _hps = classic_round(connect, FOUR)
    lobby.end_round()
    drain(connections)

    told = leave(connections, FOUR[1], last="lobby_state")

    assert all(STOPPED not in messages for messages in told.values())
