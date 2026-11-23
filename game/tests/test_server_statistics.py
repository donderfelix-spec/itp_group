"""Statistics over the WebSocket: written after Duel and Classic, read as profile and leaderboard.

The rounds are played like in test_server_duel.py, whose helpers are used
here: the tick is off, the server's clock is set by the test and every
station holds the placeholder. Every test gets a fresh store in memory.

A result is written in the background, after the players were told. So a
test that wants to read it waits for it first (`wait_for_rounds`).
"""

import asyncio
import logging
import threading
import time

import pytest

from server import main, protocol
from server.accounts.leaderboard_cache import LeaderboardCache
from server.accounts.statistics_store import MemoryStatisticsStore
from server.accounts.store import StoreUnavailable
from server.main import app

from task_helpers import (  # noqa: F401
    ask,
    client,
    clock,
    connect,
    lobby_named,
    placeholder_at_every_station,
    player,
)
from test_classic_server_features import start_classic
from test_server_duel import (  # noqa: F401
    call_tick,
    duel_of,
    fixed_routes,
    lobby_of,
    news,
    play,
    play_route,
    start,
    types_of,
    wait_for_the_open_lobby,
)

DEADLINE_SECONDS = 5
NOT_SIGNED_IN = protocol.rejection("not_signed_in")
GUEST_MESSAGE = {
    "type": "error",
    "code": "guest_no_statistics",
    "message": "Guests have no statistics. Sign up to keep yours.",
}
UNAVAILABLE = {
    "type": "error",
    "code": "statistics_unavailable",
    "message": "Statistics are unavailable right now.",
}


class CountingStore(MemoryStatisticsStore):
    """A store in memory that also writes down every round it was given."""

    def __init__(self):
        super().__init__()
        self.rounds = []  # (mode, changes), in the order written
        self.tops = 0  # how often the leaderboard was asked for

    def record_round(self, mode, changes):
        super().record_round(mode, changes)
        self.rounds.append((mode, changes))

    def top(self, limit):
        self.tops += 1
        return super().top(limit)


class BrokenStore:
    """A store whose database cannot be reached."""

    def record_round(self, mode, changes):
        raise StoreUnavailable("down")

    def records_of(self, name):
        raise StoreUnavailable("down")

    def top(self, limit):
        raise StoreUnavailable("down")


class CrashingStore:
    """A store with a bug: it raises something nobody expects, with a secret in its text."""

    def record_round(self, mode, changes):
        raise RuntimeError("postgresql://user:hunter2secret@db.example.invalid")

    def records_of(self, name):
        raise RuntimeError("postgresql://user:hunter2secret@db.example.invalid")

    def top(self, limit):
        raise RuntimeError("postgresql://user:hunter2secret@db.example.invalid")


class WaitingStore(CountingStore):
    """A store that is as slow as the test wants: writing waits until `go` is set."""

    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.go = threading.Event()

    def record_round(self, mode, changes):
        self.started.set()
        assert self.go.wait(DEADLINE_SECONDS), "the test never let the store go on"
        super().record_round(mode, changes)


@pytest.fixture(autouse=True)
def store():
    app.state.statistics_store = CountingStore()
    app.state.leaderboard_cache = LeaderboardCache()
    app.state.leaderboard_call = None
    return app.state.statistics_store


# Helpers


def wait_for_rounds(store, count):
    """Wait until the store has been given `count` rounds."""
    deadline = time.monotonic() + DEADLINE_SECONDS
    while len(store.rounds) < count:
        assert time.monotonic() < deadline, "the result was not written in time"
        time.sleep(0.01)


def guest(connect):
    """A new connection, signed in as a guest. Returns `(connection, name)`."""
    connection = connect()
    answer = ask(connection, {"type": "guest"})
    assert answer["guest"] is True
    return connection, answer["name"]


def profile_of(connection):
    news(connection)  # whatever was still waiting
    return ask(connection, {"type": "get_profile"})


def leaderboard_for(connection):
    news(connection)
    return ask(connection, {"type": "get_leaderboard"})


def profile(name, rounds, wins, best):
    # These tests play only Duels, so the Classic row stays 0/0 (Classic writes its own since S-198).
    return protocol.profile(name, [("duel", rounds, wins), ("classic", 0, 0)], best)


def finished_duel(connect, clock, names, store):
    """A Duel these accounts played to the end, in this order, 3 seconds each. The result is written.

    Returns `{name: connection}`; everybody has read everything.
    """
    written_before = len(store.rounds)
    players, code = duel_of(connect, names)
    for name in names:
        play_route(players[name], name, clock)
    wait_for_rounds(store, written_before + 1)
    for connection in players.values():
        news(connection)
    return players


# Writing the result


def test_a_finished_duel_is_written_for_every_account(connect, clock, fixed_routes, store):
    players = finished_duel(connect, clock, ["Mara", "Tiago"], store)
    assert profile_of(players["Mara"]) == profile("Mara", 1, 1, 3.0)
    assert profile_of(players["Tiago"]) == profile("Tiago", 1, 0, 6.0)


def test_the_result_is_written_with_the_ranking_of_the_server(connect, clock, fixed_routes, store):
    finished_duel(connect, clock, ["Mara", "Tiago"], store)
    assert store.rounds == [
        (
            "duel",
            [
                {"name": "Mara", "rounds": 1, "wins": 1, "best_seconds": 3.0},
                {"name": "Tiago", "rounds": 1, "wins": 0, "best_seconds": 6.0},
            ],
        )
    ]


def test_statistics_survive_the_end_of_the_lobby_and_a_second_round_adds_to_them(connect, clock, fixed_routes, store):
    players = finished_duel(connect, clock, ["Mara", "Tiago"], store)
    for connection in players.values():
        connection.send_json({"type": "leave_lobby"})
        news(connection)
    assert app.state.lobbies.all() == []

    # A new lobby, and this time Tiago is faster and Mara slower than before.
    code = ask(players["Tiago"], {"type": "create_lobby"})["code"]
    assert ask(players["Mara"], {"type": "join_lobby", "code": code})["type"] == "lobby_state"
    for connection in players.values():
        news(connection)
    start({"Tiago": players["Tiago"], "Mara": players["Mara"]})
    play_route(players["Tiago"], "Tiago", clock)
    clock.wait(10)
    play_route(players["Mara"], "Mara", clock)
    wait_for_rounds(store, 2)

    assert profile_of(players["Mara"]) == profile("Mara", 2, 1, 3.0)
    assert profile_of(players["Tiago"]) == profile("Tiago", 2, 1, 3.0)


def test_a_second_round_in_the_same_lobby_adds_too(connect, clock, fixed_routes, store):
    players = finished_duel(connect, clock, ["Mara", "Tiago"], store)
    start(players)
    for name in ("Mara", "Tiago"):
        play_route(players[name], name, clock)
    wait_for_rounds(store, 2)
    assert profile_of(players["Mara"]) == profile("Mara", 2, 2, 3.0)
    assert profile_of(players["Tiago"]) == profile("Tiago", 2, 0, 6.0)


def test_a_guest_is_skipped_also_when_the_guest_wins(connect, clock, fixed_routes, store):
    mara = player(connect, "Mara")
    visitor, guest_name = guest(connect)
    code = ask(mara, {"type": "create_lobby"})["code"]
    assert ask(visitor, {"type": "join_lobby", "code": code})["type"] == "lobby_state"
    players = {"Mara": mara, guest_name: visitor}
    for connection in players.values():
        news(connection)
    start(players)
    play_route(visitor, guest_name, clock)
    play_route(mara, "Mara", clock)
    wait_for_rounds(store, 1)

    # Mara was second: a round, her time, no win. Nothing is kept about the guest.
    assert store.rounds == [("duel", [{"name": "Mara", "rounds": 1, "wins": 0, "best_seconds": 6.0}])]
    assert store.records_of(guest_name) == {}
    assert [row["name"] for row in leaderboard_for(mara)["players"]] == ["Mara"]


def test_a_round_of_guests_only_writes_nothing(connect, clock, fixed_routes, store):
    first, first_name = guest(connect)
    second, second_name = guest(connect)
    code = ask(first, {"type": "create_lobby"})["code"]
    ask(second, {"type": "join_lobby", "code": code})
    players = {first_name: first, second_name: second}
    for connection in players.values():
        news(connection)
    start(players)
    play_route(first, first_name, clock)
    told = play_route(second, second_name, clock)
    assert types_of(told)[-2:] == ["duel_result", "lobby_state"]
    assert leaderboard_for(first) == protocol.leaderboard([])
    assert store.rounds == []


def test_when_the_time_runs_out_everybody_gets_a_round_and_nobody_a_win(connect, clock, fixed_routes, store):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    play(players["Mara"], "Mara", 3, clock)  # one station, so Mara is on place 1
    clock.wait(181)
    call_tick(players["Mara"])
    wait_for_the_open_lobby(players["Mara"])
    wait_for_rounds(store, 1)
    assert profile_of(players["Mara"]) == profile("Mara", 1, 0, None)
    assert profile_of(players["Tiago"]) == profile("Tiago", 1, 0, None)


def test_a_round_is_written_exactly_once_however_often_the_end_is_asked_for(connect, clock, fixed_routes, store):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    clock.wait(181)
    # The tick and a player's message both notice the end, and the tick again.
    call_tick(players["Mara"])
    players["Tiago"].send_json({"type": "close_station"})
    call_tick(players["Mara"])
    wait_for_the_open_lobby(players["Mara"])
    wait_for_rounds(store, 1)
    call_tick(players["Mara"])
    time.sleep(0.1)  # time for a second write, if there were one
    assert len(store.rounds) == 1
    assert profile_of(players["Mara"]) == profile("Mara", 1, 0, None)


def test_a_player_who_left_during_the_round_gets_nothing(connect, clock, fixed_routes, store):
    players, code = duel_of(connect, ["Mara", "Tiago", "Ines"])
    assert ask(players["Tiago"], {"type": "leave_lobby"}) == {"type": "left_lobby"}
    play_route(players["Mara"], "Mara", clock)
    play_route(players["Ines"], "Ines", clock)
    wait_for_rounds(store, 1)
    assert profile_of(players["Tiago"]) == profile("Tiago", 0, 0, None)
    assert profile_of(players["Mara"]) == profile("Mara", 1, 1, 3.0)
    assert profile_of(players["Ines"]) == profile("Ines", 1, 0, 6.0)


def test_a_single_remaining_player_who_finishes_gets_the_win(connect, clock, fixed_routes, store):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    assert ask(players["Tiago"], {"type": "leave_lobby"}) == {"type": "left_lobby"}
    play_route(players["Mara"], "Mara", clock)
    wait_for_rounds(store, 1)
    assert profile_of(players["Mara"]) == profile("Mara", 1, 1, 3.0)
    assert store.records_of("Tiago") == {}


def test_nothing_is_written_while_the_round_is_still_running(connect, clock, fixed_routes, store):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    play_route(players["Mara"], "Mara", clock)
    time.sleep(0.1)
    assert store.rounds == []
    assert profile_of(players["Mara"]) == profile("Mara", 0, 0, None)


def test_a_round_that_goes_on_has_no_result_to_write(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    assert main.end_round_if_over(lobby_named("Mara")) == ({}, None)


def test_two_ends_in_one_lobby_each_write_their_own_result_after_their_own_players_were_told(monkeypatch, store):
    """The second round of a lobby ends while the first is still being told.

    Each call of `tell_round_ended` carries its own result: the second one
    writes only its own, and the first is written only once its own
    players have been told, however long that takes.
    """
    first_result = ("duel", [{"name": "Mara", "rounds": 1, "wins": 1, "best_seconds": 30.0}])
    second_result = ("duel", [{"name": "Mara", "rounds": 1, "wins": 0, "best_seconds": 40.0}])
    lobby = object()
    told = []

    async def scenario():
        first_may_finish = asyncio.Event()

        async def slow_for_the_first(name, the_lobby, messages):
            if messages == ["first"]:
                await first_may_finish.wait()
            told.append(messages[0])

        async def no_lobby_state(the_lobby, new_host=None):
            pass

        monkeypatch.setattr(main, "tell_farewell", slow_for_the_first)
        monkeypatch.setattr(main, "tell_lobby", no_lobby_state)

        first = asyncio.create_task(main.tell_round_ended(lobby, {"Mara": ["first"]}, first_result))
        await asyncio.sleep(0)  # the first call is now waiting for its player
        await main.tell_round_ended(lobby, {"Mara": ["second"]}, second_result)
        await asyncio.gather(*main.background_sends)
        written_while_the_first_waits = list(store.rounds)

        first_may_finish.set()
        await first
        await asyncio.gather(*main.background_sends)
        return written_while_the_first_waits

    written_while_the_first_waits = asyncio.run(scenario())
    assert written_while_the_first_waits == [second_result]
    assert told == ["second", "first"]
    assert store.rounds == [second_result, first_result]


def test_a_round_without_a_result_writes_nothing(monkeypatch, store):
    async def scenario():
        async def told_at_once(*values):
            pass

        monkeypatch.setattr(main, "tell_farewell", told_at_once)
        monkeypatch.setattr(main, "tell_lobby", told_at_once)
        await main.tell_round_ended(object(), {"Guest0001": ["bye"]}, None)
        await asyncio.gather(*main.background_sends)

    asyncio.run(scenario())
    assert store.rounds == []


# Writing does not delay or break the end of the round


def test_the_players_have_the_result_before_the_store_has_written(connect, clock, fixed_routes):
    slow = WaitingStore()
    app.state.statistics_store = slow
    players, code = duel_of(connect, ["Mara", "Tiago"])
    play_route(players["Mara"], "Mara", clock)
    told = play_route(players["Tiago"], "Tiago", clock)
    try:
        # The store is still waiting, and both players already know how it ended.
        assert types_of(told)[-2:] == ["duel_result", "lobby_state"]
        assert types_of(wait_for_the_open_lobby(players["Mara"]))[-2:] == ["duel_result", "lobby_state"]
        assert slow.started.wait(DEADLINE_SECONDS)
        assert slow.rounds == []
        # The server goes on answering while the store is busy.
        assert ask(players["Mara"], {"type": "hello", "name": "Mara"})["type"] == "welcome"
    finally:
        slow.go.set()
    wait_for_rounds(slow, 1)


@pytest.mark.parametrize("broken_store", [BrokenStore, CrashingStore])
def test_a_store_that_fails_does_not_keep_the_round_from_ending(connect, clock, fixed_routes, caplog, broken_store):
    app.state.statistics_store = broken_store()
    players, code = duel_of(connect, ["Mara", "Tiago"])
    play_route(players["Mara"], "Mara", clock)
    with caplog.at_level(logging.DEBUG):
        told = play_route(players["Tiago"], "Tiago", clock)
        assert types_of(told)[-2:] == ["duel_result", "lobby_state"]
        assert told[-1]["phase"] == "lobby"
        assert types_of(wait_for_the_open_lobby(players["Mara"]))[-2:] == ["duel_result", "lobby_state"]
        # The next round starts as if nothing had happened.
        assert start(players)["Mara"][0]["phase"] == "round"
        assert profile_of(players["Mara"]) == UNAVAILABLE
    assert "hunter2secret" not in caplog.text and "example.invalid" not in caplog.text


def test_a_crashing_store_is_logged_by_the_kind_of_error_only(connect, clock, fixed_routes, caplog):
    app.state.statistics_store = CrashingStore()
    mara = player(connect, "Mara")
    with caplog.at_level(logging.DEBUG):
        assert ask(mara, {"type": "get_leaderboard"}) == UNAVAILABLE
    assert "The statistics store failed in top: RuntimeError" in caplog.messages
    assert "hunter2secret" not in caplog.text


def test_a_fault_while_noting_the_result_does_not_keep_the_round_from_ending(connect, clock, fixed_routes, monkeypatch, store):
    def broken(ranking, account_names):
        raise RuntimeError("bug")

    monkeypatch.setattr("server.main.statistics.changes_from_duel", broken)
    players, code = duel_of(connect, ["Mara", "Tiago"])
    play_route(players["Mara"], "Mara", clock)
    told = play_route(players["Tiago"], "Tiago", clock)
    assert types_of(told)[-2:] == ["duel_result", "lobby_state"]
    assert lobby_named("Mara").phase == "lobby"
    assert store.rounds == []


# The profile


def test_a_new_account_has_a_profile_of_zeros(connect):
    mara = player(connect, "Mara")
    assert ask(mara, {"type": "get_profile"}) == {
        "type": "profile",
        "name": "Mara",
        "modes": [
            {"mode": "duel", "title": "Duel", "rounds": 0, "wins": 0},
            {"mode": "classic", "title": "Classic", "rounds": 0, "wins": 0},
        ],
        "best_duel_seconds": None,
    }


def test_the_profile_is_the_one_of_the_own_account_only(connect, clock, fixed_routes, store):
    players = finished_duel(connect, clock, ["Mara", "Tiago"], store)
    # There is no way to name another account: a field is refused by the protocol.
    assert ask(players["Tiago"], {"type": "get_profile", "name": "Mara"})["code"] == "unknown_field"
    assert profile_of(players["Tiago"])["name"] == "Tiago"


def test_the_profile_belongs_to_the_account_in_any_spelling_of_the_log_in(connect, clock, fixed_routes, store):
    players = finished_duel(connect, clock, ["Mara", "Tiago"], store)
    assert ask(players["Mara"], {"type": "log_out"}) == {"type": "signed_out"}
    again = connect()
    assert ask(again, {"type": "log_in", "name": "mARA", "password": "password123"})["name"] == "Mara"
    assert profile_of(again) == profile("Mara", 1, 1, 3.0)


def test_a_guest_asking_for_a_profile_gets_the_guest_message(connect):
    visitor, guest_name = guest(connect)
    assert ask(visitor, {"type": "get_profile"}) == GUEST_MESSAGE
    # The guest can go on playing.
    assert ask(visitor, {"type": "create_lobby"})["type"] == "lobby_state"


def test_a_guest_is_told_so_even_when_the_store_is_down(connect):
    app.state.statistics_store = BrokenStore()
    visitor, guest_name = guest(connect)
    assert ask(visitor, {"type": "get_profile"}) == GUEST_MESSAGE


@pytest.mark.parametrize("message_type", ["get_profile", "get_leaderboard"])
def test_statistics_need_a_signed_in_player(connect, message_type):
    connection = connect()
    assert ask(connection, {"type": message_type}) == NOT_SIGNED_IN
    assert ask(connection, {"type": "hello", "name": "Mara"})["type"] == "welcome"


@pytest.mark.parametrize("message_type", ["get_profile", "get_leaderboard"])
def test_statistics_after_logging_out_need_a_new_log_in(connect, message_type):
    mara = player(connect, "Mara")
    assert ask(mara, {"type": "log_out"}) == {"type": "signed_out"}
    assert ask(mara, {"type": message_type}) == NOT_SIGNED_IN


@pytest.mark.parametrize("message_type", ["get_profile", "get_leaderboard"])
@pytest.mark.parametrize("broken_store", [BrokenStore, CrashingStore])
def test_a_store_that_fails_is_statistics_unavailable(connect, message_type, broken_store):
    app.state.statistics_store = broken_store()
    mara = player(connect, "Mara")
    assert ask(mara, {"type": message_type}) == UNAVAILABLE
    # The connection is still there and everything else works.
    assert ask(mara, {"type": "create_lobby"})["type"] == "lobby_state"


def test_the_profile_can_be_asked_for_inside_a_lobby_and_during_a_round(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    assert profile_of(players["Mara"]) == profile("Mara", 0, 0, None)
    assert lobby_named("Mara").phase == "round"


# The leaderboard


def test_the_leaderboard_is_empty_before_the_first_round(connect):
    mara = player(connect, "Mara")
    assert ask(mara, {"type": "get_leaderboard"}) == {"type": "leaderboard", "players": []}


def test_the_leaderboard_lists_the_accounts_of_a_round_best_first(connect, clock, fixed_routes, store):
    players = finished_duel(connect, clock, ["Mara", "Tiago"], store)
    assert leaderboard_for(players["Tiago"]) == {
        "type": "leaderboard",
        "players": [
            {"place": 1, "name": "Mara", "wins": 1, "classic_wins": 0, "duel_wins": 1, "best_duel_seconds": 3.0},
            {"place": 2, "name": "Tiago", "wins": 0, "classic_wins": 0, "duel_wins": 0, "best_duel_seconds": 6.0},
        ],
    }


def test_a_finished_classic_round_counts_once_and_preserves_duel_totals(connect, store):
    players, _, _, _ = start_classic(connect)
    lobby = lobby_named("Mara")
    classic = lobby.classic_round
    roles = classic.roles.copy()
    store.record_round("duel", [{"name": "Mara", "rounds": 1, "wins": 1, "best_seconds": 72.4}])
    classic.eliminated = {name for name, role in roles.items() if role == "FR"}
    for _ in range(2):
        players["Mara"].portal.call(main.tell_round_news, lobby)
    wait_for_rounds(store, 2)
    assert len(store.rounds) == 2
    assert store.rounds[-1][0] == "classic"
    rows = {row["name"]: row for row in leaderboard_for(player(connect, "Reader"))["players"]}
    assert set(rows) == set(roles)
    for name, role in roles.items():
        classic_wins = int(role == "HP")
        duel_wins = int(name == "Mara")
        assert rows[name]["classic_wins"] == classic_wins
        assert rows[name]["duel_wins"] == duel_wins
        assert rows[name]["wins"] == classic_wins + duel_wins
        assert rows[name]["best_duel_seconds"] == (72.4 if name == "Mara" else None)


def test_a_guest_sees_the_leaderboard_too(connect, clock, fixed_routes, store):
    finished_duel(connect, clock, ["Mara", "Tiago"], store)
    visitor, guest_name = guest(connect)
    assert [row["name"] for row in ask(visitor, {"type": "get_leaderboard"})["players"]] == ["Mara", "Tiago"]


def test_the_leaderboard_is_ordered_by_wins_then_time_then_name(connect, store):
    def change(name, wins, best):
        return {"name": name, "rounds": 1, "wins": wins, "best_seconds": best}

    store.record_round("duel", [change("Zoe", 1, None), change("Rui", 1, 80.0), change("Tiago", 1, 70.0)])
    store.record_round("duel", [change("ines", 1, 70.0), change("Ana", 1, None), change("Bea", 0, 40.0)])
    store.record_round("duel", [change("Mara", 1, 90.0)])
    store.record_round("duel", [change("Mara", 1, 95.0)])
    rows = ask(player(connect, "Reader"), {"type": "get_leaderboard"})["players"]
    assert [(row["place"], row["name"]) for row in rows] == [
        (1, "Mara"), (2, "ines"), (3, "Tiago"), (4, "Rui"), (5, "Ana"), (6, "Zoe"), (7, "Bea"),
    ]
    assert rows[0] == {
        "place": 1, "name": "Mara", "wins": 2, "classic_wins": 0, "duel_wins": 2, "best_duel_seconds": 90.0,
    }


def test_the_leaderboard_shows_at_most_20_accounts(connect, store):
    for number in range(25):
        change = {"name": f"Player{number:02d}", "rounds": 1, "wins": number, "best_seconds": None}
        store.record_round("duel", [change])
    rows = ask(player(connect, "Reader"), {"type": "get_leaderboard"})["players"]
    assert len(rows) == 20
    assert [row["place"] for row in rows] == list(range(1, 21))
    assert rows[0]["name"] == "Player24" and rows[-1]["name"] == "Player05"


def test_a_store_that_returns_too_many_rows_is_still_cut_at_20(connect):
    class GenerousStore(MemoryStatisticsStore):
        def top(self, limit):
            return [(f"Player{number:02d}", 0, None, 0, 0) for number in range(50)]

    app.state.statistics_store = GenerousStore()
    assert len(ask(player(connect, "Reader"), {"type": "get_leaderboard"})["players"]) == 20


def test_the_answers_carry_nothing_else_about_an_account(connect, clock, fixed_routes, store):
    players = finished_duel(connect, clock, ["Mara", "Tiago"], store)
    own = profile_of(players["Mara"])
    board = leaderboard_for(players["Mara"])
    assert set(own) == {"type", "name", "modes", "best_duel_seconds"}
    assert all(set(row) == {"mode", "title", "rounds", "wins"} for row in own["modes"])
    assert set(board) == {"type", "players"}
    assert all(
        set(row) == {"place", "name", "wins", "classic_wins", "duel_wins", "best_duel_seconds"}
        for row in board["players"]
    )
    for answer in (own, board):
        text = str(answer)
        assert "hash" not in text and "argon2" not in text and "name_key" not in text and "password" not in text


# The leaderboard's cache: the store is asked at most once in 10 seconds


def names_on(board):
    return [row["name"] for row in board["players"]]


def one_round(name, wins=1):
    return ("duel", [{"name": name, "rounds": 1, "wins": wins, "best_seconds": None}])


def test_within_10_seconds_the_leaderboard_comes_from_the_cache(connect, clock, store):
    store.record_round(*one_round("Mara"))
    mara, tiago = player(connect, "Mara"), player(connect, "Tiago")
    first = ask(mara, {"type": "get_leaderboard"})
    # Written past the server, so nothing drops the cache: the old answer stays.
    store.record_round(*one_round("Tiago", wins=5))
    clock.wait(9.9)
    assert ask(mara, {"type": "get_leaderboard"}) == first
    assert ask(tiago, {"type": "get_leaderboard"}) == first
    assert store.tops == 1


def test_after_10_seconds_the_store_is_asked_again(connect, clock, store):
    store.record_round(*one_round("Mara"))
    mara = player(connect, "Mara")
    ask(mara, {"type": "get_leaderboard"})
    store.record_round(*one_round("Tiago", wins=5))
    clock.wait(10)
    assert names_on(ask(mara, {"type": "get_leaderboard"})) == ["Tiago", "Mara"]
    assert store.tops == 2
    # The new answer is kept for its own 10 seconds.
    clock.wait(9.9)
    ask(mara, {"type": "get_leaderboard"})
    assert store.tops == 2


def test_a_written_result_drops_the_cache_so_the_new_numbers_show(connect, clock, fixed_routes, store):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    assert leaderboard_for(players["Mara"]) == protocol.leaderboard([])
    assert leaderboard_for(players["Tiago"]) == protocol.leaderboard([])
    assert store.tops == 1
    play_route(players["Mara"], "Mara", clock)
    play_route(players["Tiago"], "Tiago", clock)
    wait_for_rounds(store, 1)
    # The server's clock stands still here, so only the drop can bring new
    # numbers. It follows the write within a moment.
    deadline = time.monotonic() + DEADLINE_SECONDS
    while names_on(leaderboard_for(players["Mara"])) != ["Mara", "Tiago"]:
        assert time.monotonic() < deadline, "the cache was not dropped after the result was written"
        time.sleep(0.01)
    assert store.tops == 2


def test_a_failed_question_is_not_cached(connect, clock):
    class FailingOnce(CountingStore):
        def top(self, limit):
            self.tops += 1
            if self.tops == 1:
                raise StoreUnavailable("down")
            return MemoryStatisticsStore.top(self, limit)

    app.state.statistics_store = FailingOnce()
    app.state.statistics_store.record_round(*one_round("Mara"))
    mara = player(connect, "Mara")
    assert ask(mara, {"type": "get_leaderboard"}) == UNAVAILABLE
    # At once, without waiting 10 seconds: the store is asked again.
    assert names_on(ask(mara, {"type": "get_leaderboard"})) == ["Mara"]
    assert app.state.statistics_store.tops == 2


def test_players_who_ask_while_the_store_is_busy_wait_for_the_same_answer(connect, clock):
    class SlowTop(CountingStore):
        def __init__(self):
            super().__init__()
            self.started = threading.Event()
            self.go = threading.Event()

        def top(self, limit):
            self.started.set()
            assert self.go.wait(DEADLINE_SECONDS), "the test never let the store go on"
            return super().top(limit)

    slow = SlowTop()
    app.state.statistics_store = slow
    slow.record_round(*one_round("Mara"))
    mara, tiago, ines = player(connect, "Mara"), player(connect, "Tiago"), player(connect, "Ines")
    try:
        mara.send_json({"type": "get_leaderboard"})
        assert slow.started.wait(DEADLINE_SECONDS)
        tiago.send_json({"type": "get_leaderboard"})
        ines.send_json({"type": "get_leaderboard"})
        # Both have arrived at the server when their hello is answered... which
        # is only after the leaderboard, so a short wait has to do here.
        time.sleep(0.2)
    finally:
        slow.go.set()
    answers = [connection.receive_json() for connection in (mara, tiago, ines)]
    assert [names_on(answer) for answer in answers] == [["Mara"]] * 3
    assert slow.tops == 1


def test_three_calls_while_the_store_is_busy_share_one_question_and_one_answer():
    """The same rule as the test above, without the network and without waiting for a time.

    Three calls of `leaderboard_totals` run in one event loop against a
    store whose `top` blocks until the test lets it go on.
    """

    class BlockedTop(CountingStore):
        def __init__(self, loop, started):
            super().__init__()
            self.loop = loop
            self.started = started  # an asyncio.Event of the test's loop
            self.go = threading.Event()

        def top(self, limit):
            # `top` runs in a worker thread, so the event of the loop is
            # set through the loop.
            self.loop.call_soon_threadsafe(self.started.set)
            assert self.go.wait(DEADLINE_SECONDS), "the test never let the store go on"
            return super().top(limit)

    async def scenario():
        started = asyncio.Event()
        slow = BlockedTop(asyncio.get_running_loop(), started)
        app.state.statistics_store = slow
        slow.record_round(*one_round("Mara"))
        calls = [asyncio.create_task(main.leaderboard_totals()) for _ in range(3)]
        try:
            # Why all three are waiting once `started` is set, whatever the
            # speed of the machine: the event loop runs its tasks in the
            # order they were created. The three calls were created first,
            # and the question to the store is a task created by the first
            # of them, so it is behind all three in the line. Each call runs
            # without a pause until it waits for that question. So the
            # store's `top` cannot even begin before all three are waiting.
            await asyncio.wait_for(started.wait(), DEADLINE_SECONDS)
            assert not any(call.done() for call in calls)
        finally:
            slow.go.set()
        return slow, await asyncio.gather(*calls)

    slow, answers = asyncio.run(scenario())
    # What the store itself says, asked past the counter: one account, Mara.
    expected = MemoryStatisticsStore.top(slow, 20)
    assert len(expected) == 1
    assert answers == [expected] * 3
    assert slow.tops == 1


def test_the_end_of_a_round_cannot_be_told_without_a_result():
    async def scenario():
        await main.tell_round_ended(object(), {"Guest0001": ["bye"]})

    with pytest.raises(TypeError):
        asyncio.run(scenario())


def test_the_answer_of_another_store_is_never_served(connect, clock, store):
    store.record_round(*one_round("Mara"))
    mara = player(connect, "Mara")
    assert names_on(ask(mara, {"type": "get_leaderboard"})) == ["Mara"]
    app.state.statistics_store = CountingStore()
    assert ask(mara, {"type": "get_leaderboard"}) == protocol.leaderboard([])


# The page


def test_the_page_has_the_two_buttons_and_the_two_screens(client):
    page = client.get("/").text
    for element_id in ("home-profile", "home-leaderboard", "screen-profile", "screen-leaderboard"):
        assert f'id="{element_id}"' in page
    assert page.count(">Back</button>") == 4  # sign up, log in, profile, leaderboard


def test_the_statistics_script_is_served_and_loaded_between_the_duel_and_the_start(client):
    assert client.get("/js/lobby/statistics.js").status_code == 200
    page = client.get("/").text
    # It uses the Duel's way of writing a time, and main.js calls it.
    scripts = ["js/lobby/forms.js", "js/minigames/duel.js", "js/lobby/statistics.js", "js/main.js"]
    places = [page.index(f'<script src="{script}">') for script in scripts]
    assert places == sorted(places)


def test_the_statistics_script_never_writes_html(client):
    script = client.get("/js/lobby/statistics.js").text
    code = "\n".join(line for line in script.splitlines() if not line.strip().startswith("//"))
    assert "innerHTML" not in code and "insertAdjacentHTML" not in code
