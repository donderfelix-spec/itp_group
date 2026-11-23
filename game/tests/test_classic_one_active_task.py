"""One active Classic task at a time (M3-4.29, S-197), the cases around it.

Lennart's tests in test_classic_single_random_task.py pin the random order,
the stable read and the refusal of the own second task. These add: a
station of somebody else, the real roll-back of a count that could not be
told, the last of the four, a ghost, the Free Rider, a meeting while the
task window is open, a player who leaves, and the group progress, which
still counts four tasks per High Performer.
"""

import random

import pytest

from server import main, protocol
from server.classic.round import ClassicRound, active_task
from server.main import app, classic_task_stations
from task_helpers import TASK_FAILED, client, clock, connect, placeholder_at_every_station  # noqa: F401
from test_classic_server_features import ask, classic_for, put_at_station, start_classic
from extra_task_helpers import news

NOT_NEEDED = {"type": "error", "code": "station_not_needed", "message": "You do not need that station."}


def high_performers(game):
    return [name for name, role in game.roles.items() if role == "HP"]


def free_rider(game):
    return next(name for name, role in game.roles.items() if role == "FR")


def finish(players, name, station, clock):
    """Open and finish `station` through the server. Returns the `station_done`."""
    put_at_station(name, station)
    assert ask(players[name], {"type": "open_station", "station": station})["type"] == "station_opened"
    clock.wait(1.1)
    done = ask(players[name], {"type": "finish_station"})
    news(players[name])
    return done


# The plain rule


def test_the_active_task_is_the_first_unfinished_one_of_the_list():
    roles = {"Ana": "HP", "Bo": "FR"}
    tasks = {"Ana": ["3", "8", "1", "12"], "Bo": ["2", "4", "5", "7"]}
    assert active_task(roles, tasks, {"Ana": set()}, "Ana") == [3]
    assert active_task(roles, tasks, {"Ana": {"3"}}, "Ana") == [8]
    assert active_task(roles, tasks, {"Ana": {"3", "1"}}, "Ana") == [8]  # a gap does not skip
    assert active_task(roles, tasks, {"Ana": {"3", "8", "1", "12"}}, "Ana") == []


def test_the_free_rider_and_a_stranger_have_no_active_task():
    roles = {"Ana": "HP", "Bo": "FR"}
    tasks = {"Ana": ["3"], "Bo": ["2", "4"]}
    assert active_task(roles, tasks, {}, "Bo") == []
    assert active_task(roles, tasks, {}, "Nobody") == []
    assert active_task(roles, {}, {}, "Ana") == []  # no list at all


def test_station_done_counts_only_the_active_task():
    game = ClassicRound(["Ana", "Bo", "Cy", "Di"], [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12], random.Random(4))
    name = high_performers(game)[0]
    first, second = (int(station) for station in game.tasks[name][:2])
    game.station_done(name, second)  # not active yet
    game.station_done(name, 6)  # not even on the list
    assert game.completed_tasks[name] == set()
    game.station_done(name, first)
    game.station_done(name, first)  # twice counts once
    assert game.completed_tasks[name] == {str(first)}
    assert game.stations_needed(name, set(), ()) == [second]
    game.station_done(name, str(second))  # the id as text counts as well
    assert game.completed_tasks[name] == {str(first), str(second)}


def test_the_group_progress_still_counts_four_tasks_per_high_performer():
    game = ClassicRound(["Ana", "Bo", "Cy", "Di"], [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12], random.Random(9))
    name = high_performers(game)[0]
    game.station_done(name, int(game.tasks[name][0]))
    assert game.progress() == pytest.approx(1 / 12)
    for station in game.tasks[name][1:]:
        game.station_done(name, int(station))
    assert game.progress() == pytest.approx(4 / 12)
    assert game.stations_needed(name, set(), ()) == []


def test_a_player_who_leaves_has_no_active_task_and_the_others_keep_theirs():
    game = ClassicRound(["Ana", "Bo", "Cy", "Di"], [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12], random.Random(2))
    leaver, other, *_ = high_performers(game)
    game.station_done(leaver, int(game.tasks[leaver][0]))
    before = classic_task_stations(game, other)
    game.remove_player(leaver)
    assert classic_task_stations(game, leaver) == []
    assert classic_task_stations(game, other) == before
    assert game.progress() == pytest.approx(1 / 9)  # his finished one counts, his open three are gone


def test_a_ghost_keeps_its_active_task():
    game = ClassicRound(["Ana", "Bo", "Cy", "Di"], [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12], random.Random(5))
    ghost = high_performers(game)[0]
    game.eliminated.add(ghost)
    first = int(game.tasks[ghost][0])
    assert classic_task_stations(game, ghost) == [first]
    game.station_done(ghost, first)
    assert classic_task_stations(game, ghost) == [int(game.tasks[ghost][1])]


# Through the server


def test_a_station_of_somebody_else_is_refused_with_the_text_of_the_design(connect):
    players, _code, _public, _messages = start_classic(connect)
    game = classic_for("Mara")
    name, *others = high_performers(game)
    theirs = [station for other in others for station in game.tasks[other]]
    # A station on another High Performer's list; any other station if their lists equal his.
    foreign = next(int(station) for station in theirs + [str(id_) for id_ in range(1, 13)]
                   if station not in game.tasks[name] and station != "6")
    put_at_station(name, foreign)
    assert ask(players[name], {"type": "open_station", "station": foreign}) == NOT_NEEDED
    assert protocol.rejection("station_not_needed") == NOT_NEEDED
    assert game.completed_tasks[name] == set()


def test_a_later_own_station_is_refused_and_finish_without_an_open_task_is_refused(connect):
    players, _code, _public, _messages = start_classic(connect)
    game = classic_for("Mara")
    name = high_performers(game)[0]
    for station in game.tasks[name][1:]:
        put_at_station(name, int(station))
        assert ask(players[name], {"type": "open_station", "station": int(station)}) == NOT_NEEDED
    assert ask(players[name], {"type": "finish_station"})["code"] == "no_task_open"
    assert game.completed_tasks[name] == set()


def test_all_four_in_order_the_last_one_leaves_an_empty_list(connect, clock):
    players, _code, _public, _messages = start_classic(connect)
    game = classic_for("Mara")
    name = high_performers(game)[0]
    order = [int(station) for station in game.tasks[name]]
    for index, station in enumerate(order):
        assert finish(players, name, station, clock) == {
            "type": "station_done", "station": station, "task_stations": order[index + 1:index + 2],
        }
    assert classic_task_stations(game, name) == []
    put_at_station(name, order[0])
    assert ask(players[name], {"type": "open_station", "station": order[0]}) == NOT_NEEDED
    assert game.progress() == pytest.approx(4 / 12)


def test_a_count_that_could_not_be_told_is_taken_back_and_the_same_task_stays_active(connect, clock, monkeypatch):
    players, _code, _public, _messages = start_classic(connect)
    game = classic_for("Mara")
    name = high_performers(game)[0]
    first, second = (int(station) for station in game.tasks[name][:2])
    real = main.classic_task_stations
    broken = {"once": True}

    def fails_once(classic, who):
        if broken.pop("once", False):
            raise RuntimeError("the answer could not be built")
        return real(classic, who)

    monkeypatch.setattr(main, "classic_task_stations", fails_once)
    put_at_station(name, first)
    assert ask(players[name], {"type": "open_station", "station": first})["type"] == "station_opened"
    clock.wait(1.1)
    assert ask(players[name], {"type": "finish_station"}) == TASK_FAILED
    assert game.completed_tasks[name] == set()
    assert real(game, name) == [first]  # rolled back: the same task, not the next one
    news(players[name])  # an unchanged classic_progress may follow
    # The player can play it again, and then the next one comes.
    assert finish(players, name, first, clock) == {"type": "station_done", "station": first, "task_stations": [second]}


def test_the_free_rider_is_refused_at_every_station_and_has_no_active_task(connect):
    players, _code, _public, _messages = start_classic(connect)
    game = classic_for("Mara")
    fr = free_rider(game)
    assert classic_task_stations(game, fr) == []
    for station in game.tasks[fr]:
        put_at_station(fr, int(station))
        assert ask(players[fr], {"type": "open_station", "station": int(station)}) == protocol.rejection("fr_cannot_task")


def test_a_task_open_when_a_meeting_starts_stays_the_active_one(connect, clock):
    """As on main, the window may stay open in a meeting; S-197 changes nothing about that.

    The active task does not move on by itself, and finishing it reveals the next.
    """
    players, _code, _public, _messages = start_classic(connect)
    game = classic_for("Mara")
    worker, caller, *_ = high_performers(game)
    first, second = (int(station) for station in game.tasks[worker][:2])
    put_at_station(worker, first)
    assert ask(players[worker], {"type": "open_station", "station": first})["type"] == "station_opened"
    button = app.state.campus["button"]
    app.state.lobbies.lobby_of(caller).walkers._walkers[caller].position = (float(button["x"]), float(button["y"]))
    clock.wait(46)
    players[caller].send_json({"type": "emergency"})
    assert players[caller].receive_json()["type"] == "meeting_state"
    assert any(message["type"] == "meeting_state" for message in news(players[worker]))
    assert classic_task_stations(game, worker) == [first]
    assert ask(players[worker], {"type": "finish_station"})["type"] == "classic_progress"
    told = news(players[worker])
    assert {"type": "station_done", "station": first, "task_stations": [second]} in told
