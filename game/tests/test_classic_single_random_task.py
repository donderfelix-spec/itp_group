"""One random Classic assignment is exposed and permitted at a time."""

import random

from server import protocol
from server.classic.round import ClassicRound
from server.main import classic_task_stations
from server.modes import minigames
from task_helpers import client, clock, connect  # noqa: F401
from test_classic_server_features import ask, classic_for, put_at_station, start_classic
from extra_task_helpers import news


def test_random_queue_is_stable_advances_and_cannot_skip_ahead():
    queues = set()
    for seed in range(20):
        game = ClassicRound(['Ana', 'Bo', 'Cy', 'Di'], list(range(1, 6)), random.Random(seed))
        name = next(name for name, role in game.roles.items() if role == 'HP')
        queue = tuple(map(int, game.tasks[name]))
        queues.add(queue)
        assert game.stations_needed(name, set(), []) == [queue[0]]
        assert classic_task_stations(game, name) == [queue[0]]
        game.station_done(name, queue[1])
        assert game.completed_tasks[name] == set()
        for index, station in enumerate(queue):
            assert classic_task_stations(game, name) == [station]
            assert classic_task_stations(game, name) == [station]
            game.station_done(name, station)
            assert classic_task_stations(game, name) == list(queue[index + 1:index + 2])
        game.completed_tasks[name].discard(str(queue[0]))
        assert classic_task_stations(game, name) == [queue[0]]
        fr = next(name for name, role in game.roles.items() if role == 'FR')
        assert classic_task_stations(game, fr) == []
    assert len(queues) > 1


def test_websocket_rejects_other_station_and_unlocks_only_next_task(connect, clock):
    players, _code, _public, _messages = start_classic(connect)
    game = classic_for('Mara')
    name = next(player for player, role in game.roles.items() if role == 'HP')
    first, second = map(int, game.tasks[name][:2])
    put_at_station(name, second)
    assert ask(players[name], {'type': 'open_station', 'station': second}) == protocol.rejection('station_not_needed')
    assert classic_task_stations(game, name) == [first]
    put_at_station(name, first)
    assert ask(players[name], {'type': 'open_station', 'station': first})['type'] == 'station_opened'
    clock.wait(minigames.MINIGAMES[first].min_seconds + 0.1)  # 3 s at station 6 (S-221)
    assert ask(players[name], {'type': 'finish_station'}) == {
        'type': 'station_done', 'station': first, 'task_stations': [second],
    }
    news(players[name])
    put_at_station(name, second)
    assert ask(players[name], {'type': 'open_station', 'station': second})['type'] == 'station_opened'
