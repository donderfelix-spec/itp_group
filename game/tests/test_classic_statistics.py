"""Statistics of a Classic round (S-198): one round per account at the end, a win for the winning side.

The rule is the plain function `statistics.changes_from_classic`; the server
test ends a real Classic round through the real tick and reads the profile.
"""

import time

import pytest

from server import main, protocol
from server.accounts import statistics
from server.accounts.leaderboard_cache import LeaderboardCache
from server.main import app

from task_helpers import client, clock, connect, placeholder_at_every_station  # noqa: F401
from test_classic_server_features import start_classic
from test_server_duel import call_tick, news, wait_for_news, wait_for_the_open_lobby
from test_server_statistics import CountingStore, wait_for_rounds

ROLES = {"Mara": "FR", "Tiago": "HP", "Ines": "HP", "Rui": "HP"}
EVERYBODY = ["Mara", "Tiago", "Ines", "Rui"]


def change(name, wins):
    return {"name": name, "rounds": 1, "wins": wins, "best_seconds": None}


# Accepted: the plain rule

def test_when_the_high_performers_win_each_of_them_gets_a_win_and_the_free_rider_only_a_round():
    changes = statistics.changes_from_classic(ROLES, "HP", EVERYBODY, set(EVERYBODY))
    assert changes == [change("Mara", 0), change("Tiago", 1), change("Ines", 1), change("Rui", 1)]


def test_when_the_free_riders_win_only_they_get_a_win():
    roles = dict(ROLES, Tiago="FR")
    changes = statistics.changes_from_classic(roles, "FR", EVERYBODY, set(EVERYBODY))
    assert [c["wins"] for c in changes] == [1, 1, 0, 0]


def test_a_ghost_still_in_the_lobby_plays_the_round_and_shares_the_win():
    # Being failed does not take a player out of `names_at_the_end`.
    changes = statistics.changes_from_classic(ROLES, "HP", EVERYBODY, {"Tiago"})
    assert changes == [change("Tiago", 1)]


# Rejected: who gets nothing

def test_guests_get_no_change():
    assert statistics.changes_from_classic(ROLES, "HP", EVERYBODY, set()) == []


def test_a_player_who_left_during_the_round_gets_no_change():
    still_there = ["Mara", "Ines", "Rui"]
    changes = statistics.changes_from_classic(ROLES, "HP", still_there, set(EVERYBODY))
    assert "Tiago" not in [c["name"] for c in changes]


# Edge cases

def test_a_name_without_a_role_is_left_out():
    # Somebody in the lobby who was not in the round (cannot happen today: a
    # running round cannot be joined) never gets a Classic round.
    changes = statistics.changes_from_classic(ROLES, "HP", EVERYBODY + ["Zoe"], set(EVERYBODY) | {"Zoe"})
    assert "Zoe" not in [c["name"] for c in changes]


def test_the_change_fits_the_store_and_adds_up_over_rounds():
    record = None
    for winner in ("HP", "FR", "HP"):
        (tiago,) = statistics.changes_from_classic(ROLES, winner, ["Tiago"], {"Tiago"})
        record = statistics.add_change(record, tiago)
    assert record == {"rounds": 3, "wins": 2, "best_seconds": None}


# The server

@pytest.fixture
def store():
    app.state.statistics_store = CountingStore()
    app.state.leaderboard_cache = LeaderboardCache()
    app.state.leaderboard_call = None
    return app.state.statistics_store


def test_a_classic_round_won_by_voting_out_the_free_rider_reaches_every_profile(connect, store):
    connections, _code, _public, _start = start_classic(connect)
    lobby = app.state.lobbies.lobby_of("Mara")
    roles = dict(lobby.classic_round.roles)
    # All Free Riders out: the next tick ends the round for the High Performers.
    lobby.classic_round.eliminated.update(name for name, role in roles.items() if role == "FR")
    call_tick(connections["Mara"])
    wait_for_rounds(store, 1)

    mode, changes = store.rounds[0]
    assert mode == "classic"
    assert {c["name"]: c["wins"] for c in changes} == {
        name: 1 if role == "HP" else 0 for name, role in roles.items()
    }
    for name, connection in connections.items():
        news(connection)
        wins = 1 if roles[name] == "HP" else 0
        assert ask_profile(connection) == protocol.profile(name, [("duel", 0, 0), ("classic", 1, wins)], None)


def test_a_classic_round_won_by_the_free_riders_gives_them_the_win(connect, store):
    names = ("Mara", "Tiago", "Ines", "Rui")
    connections, _code, _public, _start = start_classic(connect, names)
    lobby = app.state.lobbies.lobby_of("Mara")
    roles = dict(lobby.classic_round.roles)
    high_performers = [name for name in names if roles[name] == "HP"]
    # Two of three High Performers failed: one Free Rider against one High Performer.
    lobby.classic_round.eliminated.update(high_performers[:2])
    call_tick(connections["Mara"])
    wait_for_rounds(store, 1)

    mode, changes = store.rounds[0]
    assert mode == "classic"
    # The two ghosts are still in the lobby: they play the round and lose it.
    assert {c["name"]: c["wins"] for c in changes} == {
        name: 1 if role == "FR" else 0 for name, role in roles.items()
    }


def test_a_player_who_left_before_the_end_gets_no_classic_round(connect, store):
    names = ("Mara", "Tiago", "Ines", "Rui", "Luca")
    connections, _code, _public, _start = start_classic(connect, names)
    lobby = app.state.lobbies.lobby_of("Mara")
    roles = dict(lobby.classic_round.roles)
    leaver = next(name for name in names if roles[name] == "HP")
    connections[leaver].send_json({"type": "leave_lobby"})
    wait_for_the_open_lobby_or_round(connections, leaver)
    stayer = next(name for name in names if name != leaver)
    lobby.classic_round.eliminated.update(name for name, role in roles.items() if role == "FR")
    call_tick(connections[stayer])
    wait_for_rounds(store, 1)

    _mode, changes = store.rounds[0]
    assert sorted(c["name"] for c in changes) == sorted(name for name in names if name != leaver)


def test_a_round_stopped_because_too_many_left_writes_nothing(connect, store):
    names = ("Mara", "Tiago", "Ines", "Rui")
    connections, _code, _public, _start = start_classic(connect, names)
    lobby = app.state.lobbies.lobby_of("Mara")
    leaver = next(name for name in names if lobby.classic_round.roles[name] == "HP")
    connections[leaver].send_json({"type": "leave_lobby"})
    stayer = next(name for name in names if name != leaver)
    wait_for_the_open_lobby(connections[stayer])
    wait_for_background_work()

    assert lobby.classic_round is None
    assert store.rounds == []


def test_a_classic_round_of_guests_has_nothing_to_write(connect, store):
    guests = {}
    for _ in range(4):
        connection = connect()
        guests[ask(connection, {"type": "guest"})["name"]] = connection
    names = list(guests)
    code = ask(guests[names[0]], {"type": "create_lobby"})["code"]
    for name in names[1:]:
        ask(guests[name], {"type": "join_lobby", "code": code})
    ask(guests[names[0]], {"type": "choose_mode", "mode": "classic"})
    ask(guests[names[0]], {"type": "start_game"})
    lobby = app.state.lobbies.lobby_of(names[0])
    roles = lobby.classic_round.roles

    # Asked directly, so no write still on its way can hide one.
    assert main.classic_result_to_write(lobby, roles, "HP") is None
    assert main.classic_result_to_write(lobby, roles, "FR") is None

    lobby.classic_round.eliminated.update(name for name, role in roles.items() if role == "FR")
    call_tick(guests[names[0]])
    wait_for_background_work()
    assert lobby.classic_round is None
    assert store.rounds == []


def wait_for_background_work():
    """Wait until the tasks the server started on its own (sends, writes) are done."""
    deadline = time.monotonic() + 5
    while main.background_sends:
        assert time.monotonic() < deadline, "the server's background work did not finish"
        time.sleep(0.01)


def wait_for_the_open_lobby_or_round(connections, leaver):
    """After `leaver` left, read every other member up to the news of the leave."""
    for name, connection in connections.items():
        if name != leaver:
            wait_for_news(connection, "classic_progress")


def ask(connection, message):
    connection.send_json(message)
    return connection.receive_json()


def ask_profile(connection):
    return ask(connection, {"type": "get_profile"})
