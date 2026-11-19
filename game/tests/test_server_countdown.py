"""The countdown before a round over the WebSocket, with 2, 3 and 8 players (M2-2.5, S-102).

The tick loop is switched off here (see conftest.py) and the server's clock
is the one of task_helpers.py: a test lets five seconds pass with
`clock.wait(5)` and runs the real tick itself. Nothing waits for real time.

The rules alone are tested in test_countdown.py.
"""

import random
import time

import pytest

from server import main, protocol
from server.main import app
from server.modes import duel

# `clock`, `client` and `connect` are fixtures; the placeholder at every
# station gives every task a known content and a minimum time of 1 second.
from task_helpers import (  # noqa: F401
    NOT_IN_ROUND,
    PASSWORD,
    SPAWN,
    client,
    clock,
    close_station,
    connect,
    finish_station,
    lobby_named,
    open_station,
    placeholder_at_every_station,
    player,
    put,
    put_at_station,
)
from test_server_duel import fixed_routes  # noqa: F401
from test_server_duel import (
    EIGHT_NAMES,
    FIXED_ROUTES,
    REAL_TICK,
    lobby_of,
    news,
    play_route,
    progress,
    result,
    state,
    types_of,
    wait_for_news,
    wait_until,
)

NOT_HOST = protocol.rejection("not_host")
ROUND_RUNNING = {"type": "error", "code": "round_running", "message": "This round has already started."}
TOO_FEW_FOR_DUEL = {"type": "error", "code": "too_few_players", "message": "Duel needs at least 2 players."}
COUNTDOWN = {"type": "countdown", "seconds": 5}
START = {"type": "start_game"}
FIRST, SECOND, THIRD = protocol.CHARACTERS[:3]
# When the tests' clock starts (see `Clock` in task_helpers.py).
CLOCK_START = 1000.0


@pytest.fixture(autouse=True)
def no_countdown():
    """Here the real countdown runs.

    Replaces the fixture of the same name in countdown_helpers.py, should
    that one ever be switched on for all tests (like `quiet_tick`).
    """


# Helpers


def lobby_state(code, host, *players, phase):
    return protocol.lobby_state(code, host, players, "duel", phase)


def ask(connection, message):
    """Send one message and return the server's one answer.

    Unlike `ask` of task_helpers.py this leaves out the `positions` that the
    ticks of these tests send, and it fails if anything else was waiting.
    """
    connection.send_json(message)
    told = news(connection)
    assert len(told) == 1, told
    return told[0]


def start_countdown(players):
    """The first player presses "Start game". Returns what each player was told, as `{name: [messages]}`."""
    names = list(players)
    players[names[0]].send_json(START)
    return {name: news(players[name]) for name in names}


def counting_lobby(connect, names):
    """A lobby of these players whose countdown has just begun. Everybody has read everything."""
    players, code = lobby_of(connect, names)
    start_countdown(players)
    return players, code


def tick(connection, seconds=0.0):
    """Run the real tick once, inside the server, as its loop would."""
    connection.portal.call(REAL_TICK, seconds)


def tick_after(connection, clock, seconds):
    clock.wait(seconds)
    tick(connection)


def round_news(players):
    """What each player is told when the round starts: read until the Duel's progress has arrived."""
    return {name: wait_for_news(connection, "duel_progress") for name, connection in players.items()}


def nothing_new_for(players):
    """True if nobody was sent anything, also not a moment later (the tick sends in the background)."""
    time.sleep(0.1)
    return all(news(connection) == [] for connection in players.values())


def where(name):
    return lobby_named(name).walkers.position_of(name)


def is_open_lobby(messages):
    return bool(messages) and messages[-1]["type"] == "lobby_state" and messages[-1]["phase"] == "lobby"


# The start of the countdown


@pytest.mark.parametrize("player_count", [2, 3, 8])
def test_the_host_starts_and_everybody_is_told_the_countdown_of_five_seconds(connect, player_count):
    names = EIGHT_NAMES[:player_count]
    players, code = lobby_of(connect, names)
    told = start_countdown(players)
    listed = list(zip(names, protocol.CHARACTERS))
    for name in names:
        assert told[name] == [lobby_state(code, names[0], *listed, phase="countdown"), COUNTDOWN]


def test_the_state_of_a_counting_lobby_carries_nothing_new(connect):
    players, code = lobby_of(connect, ["Mara", "Tiago"])
    told = start_countdown(players)
    assert set(told["Mara"][0]) == {"type", "code", "host", "players", "mode", "phase"}
    assert set(told["Mara"][1]) == {"type", "seconds"}


def test_during_the_countdown_nothing_of_the_round_exists(connect, clock):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    lobby = lobby_named("Mara")
    assert lobby.phase == "countdown" and lobby.round_starts_at == CLOCK_START + 5
    for seconds in (0, 2.5, 2.4):  # the ticks at 0, 2.5 and 4.9 seconds
        tick_after(players["Mara"], clock, seconds)
        assert lobby.phase == "countdown"
        assert lobby.duel is None and lobby.tasks is None
    assert nothing_new_for(players)


@pytest.mark.parametrize("player_count", [2, 3, 8])
def test_after_five_seconds_everybody_is_told_the_round_as_before(connect, clock, fixed_routes, player_count):
    names = EIGHT_NAMES[:player_count]
    players, code = counting_lobby(connect, names)
    tick_after(players[names[0]], clock, 5)
    told = round_news(players)
    listed = list(zip(names, protocol.CHARACTERS))
    everybody_at_zero = progress(180, *[(name, 0) for name in names])
    for place, name in enumerate(names):
        assert told[name] == [
            lobby_state(code, names[0], *listed, phase="round"),
            state(FIXED_ROUTES[place][0], 0),
            everybody_at_zero,
        ]
    lobby = lobby_named(names[0])
    assert lobby.phase == "round" and lobby.round_starts_at is None
    assert sorted(lobby.duel.names()) == sorted(names)


def test_the_round_starts_with_real_routes_drawn_at_the_end_of_the_countdown(connect, clock, monkeypatch):
    drawn_at = []
    real_draw = duel.draw_routes

    def draw(names, stations_in_use, distances, rng):
        drawn_at.append((main.seconds_now(), list(names)))
        return real_draw(names, stations_in_use, distances, rng)

    monkeypatch.setattr(duel, "draw_routes", draw)
    monkeypatch.setattr(main, "random", random.Random(3))
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    assert drawn_at == []
    tick_after(players["Mara"], clock, 5)
    assert drawn_at == [(CLOCK_START + 5, ["Mara", "Tiago"])]
    told = round_news(players)
    for name in ("Mara", "Tiago"):
        route = lobby_named("Mara").duel._players[name].route
        assert len(set(route)) == 3
        assert told[name][1] == state(route[0], 0)


def test_the_three_minutes_of_the_duel_begin_when_the_countdown_ends(connect, clock, fixed_routes):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    tick_after(players["Mara"], clock, 5)
    round_news(players)
    # 179 seconds after the start of the round, 184 after the host's click.
    tick_after(players["Mara"], clock, 179)
    assert lobby_named("Mara").phase == "round"
    tick_after(players["Mara"], clock, 1)
    told = wait_until(players["Mara"], is_open_lobby)
    assert told[0] == result(True, (1, "Mara", None, 0), (1, "Tiago", None, 0))


def test_the_start_of_the_round_puts_everybody_on_the_spawn_also_who_walked_during_the_countdown(
    connect, clock, fixed_routes
):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    put("Mara", SPAWN)
    put("Tiago", (SPAWN[0] + 200, SPAWN[1]))
    tick_after(players["Mara"], clock, 4)
    assert where("Tiago") == (SPAWN[0] + 200, SPAWN[1])  # not yet
    tick_after(players["Mara"], clock, 1)
    # The start takes everybody off the map; the next tick puts them on the spawn.
    tick(players["Mara"])
    assert where("Mara") == where("Tiago") == (float(SPAWN[0]), float(SPAWN[1]))


# Exactly once


def test_two_ticks_at_the_boundary_start_one_round(connect, clock, fixed_routes):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    clock.wait(5)
    tick(players["Mara"])
    first_duel = lobby_named("Mara").duel
    tick(players["Mara"])
    tick(players["Mara"])
    told = round_news(players)
    for name in players:
        assert types_of(told[name]) == ["lobby_state", "duel_state", "duel_progress"]
    assert lobby_named("Mara").duel is first_duel
    assert nothing_new_for(players)


def test_a_tick_that_comes_very_late_still_starts_the_round_once(connect, clock, fixed_routes):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    tick_after(players["Mara"], clock, 60)
    told = round_news(players)
    for name in players:
        assert types_of(told[name]) == ["lobby_state", "duel_state", "duel_progress"]
        # The Duel's time runs from the real start, not from when it was due.
        assert told[name][2] == progress(180, ("Mara", 0), ("Tiago", 0))
    tick(players["Mara"])
    assert nothing_new_for(players)


def test_a_tick_just_before_the_five_seconds_starts_nothing(connect, clock):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    tick_after(players["Mara"], clock, 4.999)
    assert lobby_named("Mara").phase == "countdown"
    assert nothing_new_for(players)


@pytest.mark.parametrize("seconds_later", [0, 2, 4.9])
def test_a_second_start_during_the_countdown_is_refused_and_does_not_restart_it(
    connect, clock, fixed_routes, seconds_later
):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    clock.wait(seconds_later)
    assert ask(players["Mara"], START) == ROUND_RUNNING
    assert lobby_named("Mara").round_starts_at == CLOCK_START + 5
    assert news(players["Tiago"]) == []  # no second countdown for anybody
    # The round starts five seconds after the first click, neither later nor earlier.
    clock.now = CLOCK_START + 4.95
    tick(players["Mara"])
    assert lobby_named("Mara").phase == "countdown"
    clock.now = CLOCK_START + 5
    tick(players["Mara"])
    assert lobby_named("Mara").phase == "round"
    assert types_of(round_news(players)["Mara"]) == ["lobby_state", "duel_state", "duel_progress"]


def test_five_starts_in_a_row_begin_one_countdown(connect, clock):
    players, code = lobby_of(connect, ["Mara", "Tiago"])
    for _ in range(5):
        players["Mara"].send_json(START)
    told = news(players["Mara"])
    assert types_of(told) == ["lobby_state", "countdown"] + ["error"] * 4
    assert told[2:] == [ROUND_RUNNING] * 4
    assert news(players["Tiago"]) == [told[0], COUNTDOWN]


def test_the_server_s_own_tick_loop_starts_the_round(connect, clock, fixed_routes, monkeypatch):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    monkeypatch.setattr(main, "tick", REAL_TICK)  # from here on the server's own loop ticks
    time.sleep(0.2)
    assert lobby_named("Mara").phase == "countdown"  # several ticks, but no time has passed
    clock.wait(5)
    told = round_news(players)
    for name in players:
        assert types_of(told[name]) == ["lobby_state", "duel_state", "duel_progress"]
    # The loop keeps ticking: nothing more comes.
    time.sleep(0.3)
    assert news(players["Mara"]) == []


def test_a_fault_while_one_round_is_set_up_does_not_keep_another_lobby_from_starting(
    connect, clock, monkeypatch
):
    codes = iter(["AAAA", "BBBB"])
    monkeypatch.setattr(main, "pick_lobby_code", lambda: next(codes))
    broken, code = counting_lobby(connect, ["Mara", "Tiago"])
    fine, other_code = counting_lobby(connect, ["Ines", "Rui"])
    real_set_up = main.ROUND_SETUPS["duel"]

    def set_up(lobby):
        if lobby.code == "AAAA":
            raise RuntimeError("no routes today")
        real_set_up(lobby)

    monkeypatch.setitem(main.ROUND_SETUPS, "duel", set_up)
    tick_after(fine["Ines"], clock, 5)
    told = round_news(fine)
    assert types_of(told["Rui"]) == ["lobby_state", "duel_state", "duel_progress"]
    # A round without its tasks could never end. So the broken lobby is open
    # again, its players are told, and the host can try once more.
    open_again = lobby_state("AAAA", "Mara", ("Mara", FIRST), ("Tiago", SECOND), phase="lobby")
    for name in broken:
        assert wait_for_news(broken[name]) == [open_again]
    lobby = lobby_named("Mara")
    assert lobby.phase == "lobby" and lobby.tasks is None and lobby.duel is None
    monkeypatch.setitem(main.ROUND_SETUPS, "duel", real_set_up)
    assert start_countdown(broken)["Tiago"][1] == COUNTDOWN


def test_a_fault_in_the_rules_own_start_opens_the_lobby_again_and_tells_the_players(connect, clock, monkeypatch):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    lobby = lobby_named("Mara")
    real_back_to_spawn = lobby.walkers.back_to_spawn

    def back_to_spawn():
        raise RuntimeError("the spawn is gone")

    monkeypatch.setattr(lobby.walkers, "back_to_spawn", back_to_spawn)
    tick_after(players["Mara"], clock, 5)
    open_again = lobby_state(code, "Mara", ("Mara", FIRST), ("Tiago", SECOND), phase="lobby")
    for name in players:
        assert wait_for_news(players[name]) == [open_again]
    assert lobby.phase == "lobby" and lobby.round_starts_at is None
    assert lobby.tasks is None and lobby.duel is None
    # Nothing is left that a later tick could start, and the host can try again.
    tick_after(players["Mara"], clock, 60)
    assert lobby.phase == "lobby" and nothing_new_for(players)
    monkeypatch.setattr(lobby.walkers, "back_to_spawn", real_back_to_spawn)
    assert start_countdown(players)["Tiago"][1] == COUNTDOWN


# During the countdown


def test_players_walk_during_the_countdown(connect, clock):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    put("Tiago", SPAWN)
    players["Tiago"].send_json({"type": "move", "dx": 1, "dy": 0})
    news(players["Tiago"])  # the move has arrived
    tick(players["Mara"], 0.5)
    x, y = where("Tiago")
    assert x > SPAWN[0] and y == SPAWN[1]
    assert lobby_named("Mara").phase == "countdown"


@pytest.mark.parametrize("name", ["Mara", "Tiago"])
def test_choosing_a_character_during_the_countdown_is_refused(connect, name):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    assert ask(players[name], {"type": "choose_character", "character": THIRD}) == ROUND_RUNNING
    assert lobby_named("Mara").players() == [("Mara", FIRST), ("Tiago", SECOND)]
    assert all(news(connection) == [] for connection in players.values())  # nobody else hears of it


def test_choosing_the_mode_during_the_countdown_is_refused(connect):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    assert ask(players["Mara"], {"type": "choose_mode", "mode": "duel"}) == ROUND_RUNNING
    assert ask(players["Tiago"], {"type": "choose_mode", "mode": "duel"}) == NOT_HOST
    assert news(players["Tiago"]) == []


def test_a_member_who_is_not_host_cannot_start_during_the_countdown_either(connect):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    assert ask(players["Tiago"], START) == NOT_HOST
    assert lobby_named("Mara").round_starts_at == CLOCK_START + 5


@pytest.mark.parametrize("typed", ["same", "lower"])
def test_joining_with_the_code_during_the_countdown_is_refused(connect, typed):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    ines = player(connect, "Ines")
    typed_code = code if typed == "same" else code.lower()
    assert ask(ines, {"type": "join_lobby", "code": typed_code}) == ROUND_RUNNING
    assert lobby_named("Ines") is None
    assert lobby_named("Mara").names() == ["Mara", "Tiago"]
    assert all(news(connection) == [] for connection in players.values())


def test_no_station_can_be_opened_closed_or_finished_during_the_countdown(connect, clock):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    mara = players["Mara"]
    for station in (1, 2, 3, 4, 5):
        put_at_station("Mara", station)
        assert open_station(mara, station) == NOT_IN_ROUND
    assert close_station(mara) == NOT_IN_ROUND
    assert finish_station(mara) == NOT_IN_ROUND
    assert lobby_named("Mara").phase == "countdown" and lobby_named("Mara").tasks is None


def test_a_message_that_is_not_as_it_should_be_does_not_disturb_the_countdown(connect, clock, fixed_routes):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    assert ask(players["Mara"], {"type": "start_game", "seconds": 0})["code"] == "unknown_field"
    assert ask(players["Mara"], {"type": "countdown", "seconds": 0})["code"] == "unknown_type"
    assert lobby_named("Mara").round_starts_at == CLOCK_START + 5
    tick_after(players["Mara"], clock, 5)
    assert types_of(round_news(players)["Tiago"]) == ["lobby_state", "duel_state", "duel_progress"]


# Leaving during the countdown


def test_a_member_leaves_and_the_countdown_goes_on_for_the_others(connect, clock, fixed_routes):
    players, code = counting_lobby(connect, ["Mara", "Tiago", "Ines"])
    assert ask(players["Tiago"], {"type": "leave_lobby"}) == {"type": "left_lobby"}
    expected = lobby_state(code, "Mara", ("Mara", FIRST), ("Ines", THIRD), phase="countdown")
    for name in ("Mara", "Ines"):
        # The state only: the countdown is not announced a second time.
        assert wait_for_news(players[name]) == [expected]
    assert lobby_named("Mara").round_starts_at == CLOCK_START + 5

    tick_after(players["Mara"], clock, 5)
    stayed = {name: players[name] for name in ("Mara", "Ines")}
    told = round_news(stayed)
    for name in stayed:
        assert told[name][0] == lobby_state(code, "Mara", ("Mara", FIRST), ("Ines", THIRD), phase="round")
        assert told[name][2] == progress(180, ("Mara", 0), ("Ines", 0))
    assert sorted(lobby_named("Mara").duel.names()) == ["Ines", "Mara"]
    assert news(players["Tiago"]) == []  # who left hears nothing of the round


def test_the_host_leaves_the_host_changes_and_the_countdown_goes_on(connect, clock, fixed_routes):
    players, code = counting_lobby(connect, ["Mara", "Tiago", "Ines"])
    assert ask(players["Mara"], {"type": "leave_lobby"}) == {"type": "left_lobby"}
    expected = [
        protocol.notice("The host left. Tiago is the new host."),
        lobby_state(code, "Tiago", ("Tiago", SECOND), ("Ines", THIRD), phase="countdown"),
    ]
    for name in ("Tiago", "Ines"):
        assert wait_for_news(players[name]) == expected
    # The new host cannot shorten or restart the countdown.
    assert ask(players["Tiago"], START) == ROUND_RUNNING
    assert lobby_named("Tiago").round_starts_at == CLOCK_START + 5

    tick_after(players["Tiago"], clock, 5)
    stayed = {name: players[name] for name in ("Tiago", "Ines")}
    told = round_news(stayed)
    for name in stayed:
        assert told[name][0] == lobby_state(code, "Tiago", ("Tiago", SECOND), ("Ines", THIRD), phase="round")
    assert news(players["Mara"]) == []


def test_a_member_who_closes_the_connection_during_the_countdown_is_gone_like_one_who_left(
    connect, clock, fixed_routes
):
    players, code = counting_lobby(connect, ["Mara", "Tiago", "Ines"])
    players["Ines"].close()
    expected = lobby_state(code, "Mara", ("Mara", FIRST), ("Tiago", SECOND), phase="countdown")
    assert wait_for_news(players["Mara"]) == [expected]
    assert wait_for_news(players["Tiago"]) == [expected]
    tick_after(players["Mara"], clock, 5)
    told = round_news({name: players[name] for name in ("Mara", "Tiago")})
    assert told["Mara"][2] == progress(180, ("Mara", 0), ("Tiago", 0))


@pytest.mark.parametrize("how", ["leave_lobby", "log_out", "close"])
def test_too_few_players_left_cancel_the_countdown_and_the_lobby_is_open_again(connect, clock, how):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    if how == "close":
        players["Tiago"].close()
    else:
        players["Tiago"].send_json({"type": how})
    open_again = lobby_state(code, "Mara", ("Mara", FIRST), phase="lobby")
    assert wait_for_news(players["Mara"]) == [open_again]
    lobby = lobby_named("Mara")
    assert lobby.phase == "lobby" and lobby.round_starts_at is None

    # The five seconds pass: nobody is put into a round.
    tick_after(players["Mara"], clock, 5)
    tick_after(players["Mara"], clock, 60)
    assert lobby.phase == "lobby" and lobby.duel is None and lobby.tasks is None
    assert nothing_new_for({"Mara": players["Mara"]})


def test_the_host_leaves_a_countdown_of_two_and_the_other_player_has_an_open_lobby(connect, clock):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    assert ask(players["Mara"], {"type": "leave_lobby"}) == {"type": "left_lobby"}
    assert wait_for_news(players["Tiago"]) == [
        protocol.notice("The host left. Tiago is the new host."),
        lobby_state(code, "Tiago", ("Tiago", SECOND), phase="lobby"),
    ]
    tick_after(players["Tiago"], clock, 5)
    assert lobby_named("Tiago").phase == "lobby"
    assert ask(players["Tiago"], START) == TOO_FEW_FOR_DUEL


def test_after_a_cancelled_countdown_join_character_mode_and_start_work_again(connect, clock, fixed_routes):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    mara = players["Mara"]
    players["Tiago"].send_json({"type": "leave_lobby"})
    wait_for_news(mara)
    clock.wait(2)

    assert ask(mara, START) == TOO_FEW_FOR_DUEL
    assert ask(mara, {"type": "choose_character", "character": THIRD})["players"] == [
        {"name": "Mara", "character": THIRD}
    ]
    assert ask(mara, {"type": "choose_mode", "mode": "duel"})["phase"] == "lobby"
    ines = player(connect, "Ines")
    joined = ask(ines, {"type": "join_lobby", "code": code})
    assert joined == lobby_state(code, "Mara", ("Mara", THIRD), ("Ines", FIRST), phase="lobby")
    news(mara)

    # A new start counts the full five seconds again, from its own click.
    pair = {"Mara": mara, "Ines": ines}
    told = start_countdown(pair)
    assert told["Ines"] == [lobby_state(code, "Mara", ("Mara", THIRD), ("Ines", FIRST), phase="countdown"), COUNTDOWN]
    assert lobby_named("Mara").round_starts_at == CLOCK_START + 2 + 5
    tick_after(mara, clock, 4.9)
    assert lobby_named("Mara").phase == "countdown"
    tick_after(mara, clock, 0.1)
    assert types_of(round_news(pair)["Ines"]) == ["lobby_state", "duel_state", "duel_progress"]
    assert news(players["Tiago"]) == [{"type": "left_lobby"}]  # nothing else ever reached Tiago


def test_a_lobby_that_empties_during_the_countdown_disappears_and_nothing_ticks_on(connect, clock, monkeypatch):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    lobby = lobby_named("Mara")
    assert ask(players["Tiago"], {"type": "leave_lobby"}) == {"type": "left_lobby"}
    wait_for_news(players["Mara"])
    assert ask(players["Mara"], {"type": "leave_lobby"}) == {"type": "left_lobby"}
    assert app.state.lobbies.count() == 0 and app.state.lobbies.find(code) is None

    set_up = []
    monkeypatch.setitem(main.ROUND_SETUPS, "duel", set_up.append)
    tick_after(players["Mara"], clock, 5)
    tick_after(players["Mara"], clock, 60)
    assert set_up == []  # no round was started for anybody
    assert lobby.phase == "lobby" and lobby.duel is None
    assert nothing_new_for(players)

    # The same four letters give an ordinary new lobby.
    monkeypatch.setattr(main, "pick_lobby_code", lambda: code)
    assert ask(players["Tiago"], {"type": "create_lobby"}) == lobby_state(
        code, "Tiago", ("Tiago", FIRST), phase="lobby"
    )


def test_both_players_close_their_connections_during_the_countdown(connect, clock):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    players["Mara"].close()
    players["Tiago"].close()
    watcher = player(connect, "Ines")
    deadline = time.monotonic() + 5
    while app.state.lobbies.count() > 0:
        assert time.monotonic() < deadline, "the empty lobby was not deleted in time"
        time.sleep(0.02)
    tick_after(watcher, clock, 5)
    assert app.state.lobbies.count() == 0
    assert ask(watcher, {"type": "join_lobby", "code": code})["code"] == "no_lobby"


# A newer log-in replaces a player during the countdown (S-76)


def log_in_again(connect, name):
    """The account logs in on a new connection, which takes the old one's place. Returns the new connection."""
    newer = connect()
    newer.send_json({"type": "log_in", "name": name, "password": PASSWORD})
    assert newer.receive_json() == {"type": "signed_in", "name": name, "guest": False}
    return newer


def test_a_newer_log_in_of_one_of_two_players_cancels_the_countdown(connect, clock):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    newer = log_in_again(connect, "Tiago")
    open_again = lobby_state(code, "Mara", ("Mara", FIRST), phase="lobby")
    assert wait_for_news(players["Mara"]) == [open_again]
    assert wait_for_news(players["Tiago"], "signed_out") == [{"type": "signed_out"}]

    # The five seconds pass: no round for anybody.
    tick_after(players["Mara"], clock, 5)
    lobby = lobby_named("Mara")
    assert lobby.phase == "lobby" and lobby.duel is None and lobby.tasks is None
    assert nothing_new_for({"Mara": players["Mara"], "old Tiago": players["Tiago"], "new Tiago": newer})

    # The new connection starts outside of any lobby and can join the open one.
    assert ask(newer, {"type": "join_lobby", "code": code}) == lobby_state(
        code, "Mara", ("Mara", FIRST), ("Tiago", SECOND), phase="lobby"
    )


def test_a_newer_log_in_of_the_host_of_three_changes_the_host_and_the_countdown_goes_on(
    connect, clock, fixed_routes
):
    players, code = counting_lobby(connect, ["Mara", "Tiago", "Ines"])
    newer = log_in_again(connect, "Mara")
    expected = [
        protocol.notice("The host left. Tiago is the new host."),
        lobby_state(code, "Tiago", ("Tiago", SECOND), ("Ines", THIRD), phase="countdown"),
    ]
    stayed = {name: players[name] for name in ("Tiago", "Ines")}
    for name in stayed:
        assert wait_for_news(players[name]) == expected
    assert wait_for_news(players["Mara"], "signed_out") == [{"type": "signed_out"}]
    assert lobby_named("Tiago").round_starts_at == CLOCK_START + 5

    # The new connection is outside and stays outside: the lobby is closed.
    assert lobby_named("Mara") is None
    assert ask(newer, {"type": "join_lobby", "code": code}) == ROUND_RUNNING

    tick_after(players["Tiago"], clock, 5)
    told = round_news(stayed)
    for name in stayed:
        assert told[name][0] == lobby_state(code, "Tiago", ("Tiago", SECOND), ("Ines", THIRD), phase="round")
        assert told[name][2] == progress(180, ("Tiago", 0), ("Ines", 0))
    lobby = lobby_named("Tiago")
    assert sorted(lobby.duel.names()) == sorted(lobby.names()) == ["Ines", "Tiago"]
    # Neither connection of the replaced player hears anything of the round.
    assert nothing_new_for({"old Mara": players["Mara"], "new Mara": newer})


# The seconds in a `countdown` message that is sent late


@pytest.mark.parametrize("seconds_later, seconds_sent", [(0, 5), (0.5, 5), (2, 3), (2.5, 3), (4.9, 1)])
def test_a_countdown_message_sent_late_carries_the_whole_seconds_that_are_left(
    connect, clock, seconds_later, seconds_sent
):
    # A slow send of the lobby's state delays the `countdown` message after
    # it. Here the time passes between the two, and the message is sent as
    # the server sends it.
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    clock.wait(seconds_later)
    players["Mara"].portal.call(main.tell_countdown, lobby_named("Mara"))
    for connection in players.values():
        assert news(connection) == [{"type": "countdown", "seconds": seconds_sent}]


def test_no_countdown_message_is_sent_once_the_round_has_started(connect, clock, fixed_routes):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    tick_after(players["Mara"], clock, 5)
    round_news(players)
    players["Mara"].portal.call(main.tell_countdown, lobby_named("Mara"))
    assert nothing_new_for(players)


def test_no_countdown_message_is_sent_once_the_countdown_was_cancelled_or_to_who_left(connect, clock):
    players, code = counting_lobby(connect, ["Mara", "Tiago", "Ines"])
    lobby = lobby_named("Mara")
    assert ask(players["Ines"], {"type": "leave_lobby"}) == {"type": "left_lobby"}
    for name in ("Mara", "Tiago"):
        wait_for_news(players[name])
    clock.wait(1)
    players["Mara"].portal.call(main.tell_countdown, lobby)
    assert news(players["Mara"]) == [{"type": "countdown", "seconds": 4}]
    assert news(players["Tiago"]) == [{"type": "countdown", "seconds": 4}]
    assert news(players["Ines"]) == []  # who left is not told

    assert ask(players["Tiago"], {"type": "leave_lobby"}) == {"type": "left_lobby"}
    wait_for_news(players["Mara"])
    assert lobby.phase == "lobby"
    players["Mara"].portal.call(main.tell_countdown, lobby)
    assert nothing_new_for(players)


def test_a_countdown_message_after_the_time_is_up_but_before_the_tick_says_zero(connect, clock):
    # Cannot be shown wrongly: the page ignores a countdown that is not above zero.
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    clock.wait(7)
    players["Mara"].portal.call(main.tell_countdown, lobby_named("Mara"))
    assert news(players["Mara"]) == [{"type": "countdown", "seconds": 0}]


# After the countdown


def test_once_the_round_runs_the_countdown_is_over_for_good(connect, clock, fixed_routes):
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    tick_after(players["Mara"], clock, 5)
    round_news(players)
    assert ask(players["Mara"], START) == ROUND_RUNNING
    ines = player(connect, "Ines")
    assert ask(ines, {"type": "join_lobby", "code": code}) == ROUND_RUNNING
    # Leaving the round does not cancel it (S-94): it goes on for a single player.
    players["Tiago"].send_json({"type": "leave_lobby"})
    wait_for_news(players["Mara"])
    assert lobby_named("Mara").phase == "round"


def test_the_second_round_counts_down_again_and_starts_fresh(connect, clock, monkeypatch):
    monkeypatch.setattr(main, "random", random.Random(3))
    players, code = counting_lobby(connect, ["Mara", "Tiago"])
    tick_after(players["Mara"], clock, 5)
    round_news(players)
    first_duel = lobby_named("Mara").duel
    for name in players:
        put(name, SPAWN)
        play_route(players[name], name, clock)
    for connection in players.values():
        news(connection)  # the ranking and the open lobby
    assert lobby_named("Mara").phase == "lobby"

    started_at = clock.now
    told = start_countdown(players)
    for name in players:
        assert types_of(told[name]) == ["lobby_state", "countdown"]
        assert told[name][0]["phase"] == "countdown" and told[name][1] == COUNTDOWN
    assert lobby_named("Mara").round_starts_at == started_at + 5
    assert lobby_named("Mara").duel is None  # the old Duel is gone, the new one is not there yet

    tick_after(players["Mara"], clock, 5)
    told = round_news(players)
    second_duel = lobby_named("Mara").duel
    assert second_duel is not None and second_duel is not first_duel
    for name in players:
        assert types_of(told[name]) == ["lobby_state", "duel_state", "duel_progress"]
        assert told[name][1] == state(second_duel._players[name].route[0], 0)
        assert told[name][2] == progress(180, ("Mara", 0), ("Tiago", 0))


# The page


def test_the_countdown_script_is_served_and_loaded_after_the_lobby_and_before_main(client):
    assert client.get("/js/lobby/countdown.js").status_code == 200
    page = client.get("/").text
    scripts = ["js/lobby/lobby.js", "js/lobby/countdown.js", "js/main.js"]
    places = [page.index(f'<script src="{script}">') for script in scripts]
    assert places == sorted(places)


def test_the_page_has_the_text_of_the_countdown_and_leaves_the_number_to_the_server(client):
    page = client.get("/").text
    assert ">Round starts in<" in page
    # The number is empty in the page: it comes with the `countdown` message.
    assert '<p id="countdown-number" class="countdown-number"></p>' in page
    script = client.get("/js/lobby/countdown.js").text
    assert "message.seconds" in script
