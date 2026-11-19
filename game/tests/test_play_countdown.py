"""Play test of the countdown before a round (M2-2.5, S-102).

What the tester played in real browsers with three players (and once with
eight), and what test_countdown.py and test_server_countdown.py do not
already check, as far as the server takes part in it:

- an evening of three rounds in a row, every one begun with its own
  countdown of five seconds and played to the ranking: nothing of an
  earlier round is there while the next countdown runs, and the statistics
  of the accounts add up afterwards;
- the host leaves during the countdown: the two others play the round to
  its ranking, the new host starts the next round with a countdown of its
  own, and the player who left has no round in the statistics;
- a player whose connection drops during the countdown logs in again and
  types the code: refused during the countdown and during the round,
  accepted after the ranking, and then part of the next countdown;
- actions sent twice or in one go (leaving twice, starting and leaving at
  once, everything a page could send past its switched-off buttons) get
  the texts of DESIGN.md, section 9, and neither move nor end the countdown.

The rounds are played like in test_server_countdown.py: the server's clock
is set by the test, the real tick is run by the test, every station holds
the placeholder, and every test gets a fresh store in memory.
"""

import pytest

from server import protocol
from task_helpers import NOT_IN_ROUND, PASSWORD, client, clock, connect  # noqa: F401
from task_helpers import placeholder_at_every_station  # noqa: F401
from task_helpers import lobby_named, player
from test_server_countdown import (
    COUNTDOWN,
    FIRST,
    NOT_HOST,
    ROUND_RUNNING,
    SECOND,
    START,
    THIRD,
    ask,
    counting_lobby,
    lobby_state,
    nothing_new_for,
    round_news,
    start_countdown,
    tick_after,
)
from test_server_duel import fixed_routes  # noqa: F401
from test_server_duel import lobby_of, news, play_route, progress, types_of, wait_for_news
from test_server_statistics import store  # noqa: F401
from test_server_statistics import profile, profile_of, wait_for_rounds

NOT_IN_LOBBY = protocol.rejection("not_in_lobby")
LEAVE = {"type": "leave_lobby"}
LEFT = {"type": "left_lobby"}


@pytest.fixture(autouse=True)
def no_countdown():
    """Here the real countdown runs (see the fixture of the same name in countdown_helpers.py)."""


# Helpers


def count_down_to_the_round(players, clock):  # noqa: F811
    """The first player presses "Start game" and the five seconds pass. Everybody has read the start of the round.

    Checks on the way what every player saw in the browser: the countdown
    is announced once, nothing of a round is there while it runs, it does
    not end early, and the round begins for everybody with nothing done.
    """
    host = next(iter(players))
    for connection in players.values():
        news(connection)
    pressed_at = clock.now
    told = start_countdown(players)
    for name in players:
        assert types_of(told[name]) == ["lobby_state", "countdown"]
        assert told[name][0]["phase"] == "countdown" and told[name][1] == COUNTDOWN
    lobby = lobby_named(host)
    assert lobby.round_starts_at == pressed_at + 5
    assert lobby.duel is None and lobby.tasks is None  # nothing of an earlier round, nothing of the next yet

    tick_after(players[host], clock, 4.5)
    assert lobby.phase == "countdown" and lobby.duel is None
    assert nothing_new_for(players)
    tick_after(players[host], clock, 0.5)
    told = round_news(players)
    everybody_at_zero = progress(180, *((name, 0) for name in players))
    for name in players:
        assert types_of(told[name]) == ["lobby_state", "duel_state", "duel_progress"]
        assert told[name][0]["phase"] == "round"
        assert told[name][2] == everybody_at_zero


def play_to_the_ranking(players, clock, store, order):  # noqa: F811
    """Everybody plays their three stations, one second each, in this order. Returns the ranking that was sent."""
    written_before = len(store.rounds)
    told = []
    for name in order:
        told = play_route(players[name], name, clock)
    results = [message for message in told if message["type"] == "duel_result"]
    assert len(results) == 1 and results[0]["time_up"] is False
    wait_for_rounds(store, written_before + 1)
    for connection in players.values():
        news(connection)
    assert lobby_named(order[0]).phase == "lobby"
    return [(row["place"], row["name"], row["seconds"]) for row in results[0]["ranking"]]


def log_in_on_a_new_connection(connect, name):  # noqa: F811
    connection = connect()
    connection.send_json({"type": "log_in", "name": name, "password": PASSWORD})
    assert connection.receive_json() == {"type": "signed_in", "name": name, "guest": False}
    return connection


# Three rounds in a row


def test_three_rounds_in_a_row_each_begin_with_their_own_countdown_and_the_statistics_add_up(
    connect, clock, fixed_routes, store
):
    players, code = lobby_of(connect, ["Mara", "Tiago", "Ines"])

    count_down_to_the_round(players, clock)
    first = play_to_the_ranking(players, clock, store, ["Tiago", "Mara", "Ines"])
    assert first == [(1, "Tiago", 3.0), (2, "Mara", 6.0), (3, "Ines", 9.0)]

    count_down_to_the_round(players, clock)
    second = play_to_the_ranking(players, clock, store, ["Tiago", "Mara", "Ines"])
    assert second == first  # the clock of the second round began at the end of its own countdown

    count_down_to_the_round(players, clock)
    third = play_to_the_ranking(players, clock, store, ["Ines", "Mara", "Tiago"])
    assert third == [(1, "Ines", 3.0), (2, "Mara", 6.0), (3, "Tiago", 9.0)]

    assert len(store.rounds) == 3  # one result per round, none for a countdown
    assert profile_of(players["Mara"]) == profile("Mara", 3, 0, 6.0)
    assert profile_of(players["Tiago"]) == profile("Tiago", 3, 2, 3.0)
    assert profile_of(players["Ines"]) == profile("Ines", 3, 1, 3.0)
    # The lobby is the same one, open, with the same code.
    lobby = lobby_named("Mara")
    assert lobby.code == code and lobby.phase == "lobby" and lobby.round_starts_at is None


def test_the_five_seconds_of_the_countdown_are_not_part_of_the_time_in_the_ranking(
    connect, clock, fixed_routes, store
):
    players, _ = lobby_of(connect, ["Mara", "Tiago"])
    count_down_to_the_round(players, clock)
    assert play_to_the_ranking(players, clock, store, ["Mara", "Tiago"]) == [(1, "Mara", 3.0), (2, "Tiago", 6.0)]
    assert profile_of(players["Mara"]) == profile("Mara", 1, 1, 3.0)


# The host leaves during the countdown


def test_the_host_leaves_during_the_countdown_the_others_play_and_the_new_host_starts_the_next_round(
    connect, clock, fixed_routes, store
):
    players, code = counting_lobby(connect, ["Mara", "Tiago", "Ines"])
    clock.wait(1.5)
    assert ask(players["Mara"], LEAVE) == LEFT
    stayed = {name: players[name] for name in ("Tiago", "Ines")}
    for name in stayed:
        assert wait_for_news(players[name]) == [
            protocol.notice("The host left. Tiago is the new host."),
            lobby_state(code, "Tiago", ("Tiago", SECOND), ("Ines", THIRD), phase="countdown"),
        ]

    # The rest of the five seconds, counted from the old host's click.
    tick_after(players["Tiago"], clock, 3.0)
    assert lobby_named("Tiago").phase == "countdown"
    tick_after(players["Tiago"], clock, 0.5)
    told = round_news(stayed)
    for name in stayed:
        assert told[name][2] == progress(180, ("Tiago", 0), ("Ines", 0))
    assert play_to_the_ranking(stayed, clock, store, ["Ines", "Tiago"]) == [(1, "Ines", 3.0), (2, "Tiago", 6.0)]

    # The next round is the new host's to start; the other player still cannot.
    assert ask(players["Ines"], START) == NOT_HOST
    count_down_to_the_round(stayed, clock)
    play_to_the_ranking(stayed, clock, store, ["Tiago", "Ines"])

    assert profile_of(players["Tiago"]) == profile("Tiago", 2, 1, 3.0)
    assert profile_of(players["Ines"]) == profile("Ines", 2, 1, 3.0)
    # Who left during the countdown was in no round, and heard of none.
    assert profile_of(players["Mara"]) == profile("Mara", 0, 0, None)


# A connection that drops during the countdown


def test_a_player_who_dropped_during_the_countdown_gets_back_in_only_after_the_round(
    connect, clock, fixed_routes, store
):
    players, code = counting_lobby(connect, ["Mara", "Tiago", "Ines"])
    clock.wait(1.5)
    players["Ines"].close()
    stayed = {name: players[name] for name in ("Mara", "Tiago")}
    for name in stayed:
        assert wait_for_news(players[name]) == [
            lobby_state(code, "Mara", ("Mara", FIRST), ("Tiago", SECOND), phase="countdown")
        ]

    # Ines reloads, logs in again and types the code while the countdown still runs.
    ines = log_in_on_a_new_connection(connect, "Ines")
    assert ask(ines, {"type": "join_lobby", "code": code}) == ROUND_RUNNING
    assert nothing_new_for(stayed)  # the others are not disturbed
    assert lobby_named("Mara").round_starts_at == 1000.0 + 5

    tick_after(players["Mara"], clock, 3.5)
    told = round_news(stayed)
    for name in stayed:
        assert told[name][2] == progress(180, ("Mara", 0), ("Tiago", 0))
    assert ask(ines, {"type": "join_lobby", "code": code}) == ROUND_RUNNING  # and not during the round either
    play_to_the_ranking(stayed, clock, store, ["Mara", "Tiago"])
    assert profile_of(ines) == profile("Ines", 0, 0, None)

    # After the ranking the code works again, and the next countdown is hers too.
    joined = ask(ines, {"type": "join_lobby", "code": code})
    assert joined == lobby_state(code, "Mara", ("Mara", FIRST), ("Tiago", SECOND), ("Ines", THIRD), phase="lobby")
    three = {"Mara": players["Mara"], "Tiago": players["Tiago"], "Ines": ines}
    count_down_to_the_round(three, clock)
    assert sorted(lobby_named("Mara").duel.names()) == ["Ines", "Mara", "Tiago"]


# The same action twice, and two actions at once


def test_leaving_twice_quickly_during_the_countdown_leaves_once(connect, clock, fixed_routes):
    players, code = counting_lobby(connect, ["Mara", "Tiago", "Ines"])
    players["Tiago"].send_json(LEAVE)
    players["Tiago"].send_json(LEAVE)
    assert news(players["Tiago"]) == [LEFT, NOT_IN_LOBBY]
    stayed = {name: players[name] for name in ("Mara", "Ines")}
    for name in stayed:
        # One state for the one leave, and the countdown is not announced again.
        assert wait_for_news(players[name]) == [
            lobby_state(code, "Mara", ("Mara", FIRST), ("Ines", THIRD), phase="countdown")
        ]
    assert nothing_new_for(stayed)
    tick_after(players["Mara"], clock, 5)
    assert types_of(round_news(stayed)["Ines"]) == ["lobby_state", "duel_state", "duel_progress"]


def test_a_host_who_starts_and_leaves_in_one_go_leaves_the_countdown_to_the_others(connect, clock, fixed_routes):
    players, code = lobby_of(connect, ["Mara", "Tiago", "Ines"])
    players["Mara"].send_json(START)
    players["Mara"].send_json(LEAVE)
    assert types_of(news(players["Mara"])) == ["lobby_state", "countdown", "left_lobby"]
    stayed = {name: players[name] for name in ("Tiago", "Ines")}
    for name in stayed:
        told = wait_for_news(players[name], "notice")
        told += [] if told[-1]["type"] == "lobby_state" else wait_for_news(players[name])
        assert told == [
            lobby_state(code, "Mara", ("Mara", FIRST), ("Tiago", SECOND), ("Ines", THIRD), phase="countdown"),
            COUNTDOWN,
            protocol.notice("The host left. Tiago is the new host."),
            lobby_state(code, "Tiago", ("Tiago", SECOND), ("Ines", THIRD), phase="countdown"),
        ]
    tick_after(players["Tiago"], clock, 5)
    told = round_news(stayed)
    for name in stayed:
        assert told[name][2] == progress(180, ("Tiago", 0), ("Ines", 0))


def test_everything_a_page_could_send_past_its_switched_off_buttons_leaves_the_countdown_as_it_was(
    connect, clock, fixed_routes
):
    players, code = counting_lobby(connect, ["Mara", "Tiago", "Ines"])
    noa = player(connect, "Noa")
    lobby = lobby_named("Mara")
    before = lobby_state(code, "Mara", ("Mara", FIRST), ("Tiago", SECOND), ("Ines", THIRD), phase="countdown")

    clock.wait(1)
    assert ask(players["Tiago"], {"type": "choose_character", "character": "surfer"}) == ROUND_RUNNING
    assert ask(players["Mara"], {"type": "choose_mode", "mode": "duel"}) == ROUND_RUNNING
    assert ask(players["Mara"], START) == ROUND_RUNNING
    clock.wait(1)
    assert ask(players["Tiago"], START) == NOT_HOST
    assert ask(players["Tiago"], {"type": "choose_mode", "mode": "duel"}) == NOT_HOST
    assert ask(players["Ines"], {"type": "open_station", "station": 1}) == NOT_IN_ROUND
    assert ask(noa, {"type": "join_lobby", "code": code}) == ROUND_RUNNING
    assert ask(noa, START) == NOT_IN_LOBBY

    # Nobody was told anything, and the lobby is as the host's click left it.
    assert nothing_new_for(players)
    assert protocol.lobby_state(lobby.code, lobby.host, lobby.players(), lobby.mode, lobby.phase) == before
    assert lobby.round_starts_at == 1000.0 + 5

    # The round starts five seconds after the first click, for the three and not for the fourth.
    tick_after(players["Mara"], clock, 2.5)
    assert lobby.phase == "countdown"
    tick_after(players["Mara"], clock, 0.5)
    told = round_news(players)
    for name in players:
        assert told[name][2] == progress(180, ("Mara", 0), ("Tiago", 0), ("Ines", 0))
    assert news(noa) == []
