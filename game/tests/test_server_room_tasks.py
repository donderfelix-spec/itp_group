"""The existing two-player Duel mixes old tasks and new extra-room stations."""
import pytest

from server import main, protocol
from server.modes import duel, minigames, room_tasks
from extra_task_helpers import news, start_after_countdown, no_countdown  # noqa: F401
from task_helpers import (  # noqa: F401
    ask, client, clock, connect, lobby_named, player, put_at_station, put, SPAWN,
)


def running(connect, monkeypatch, routes, clock):
    monkeypatch.setattr(duel, 'draw_routes', lambda names, stations, distances, rng: dict(zip(names, routes)))
    players = {name: player(connect, name) for name in ('Mara', 'Tiago')}
    code = ask(players['Mara'], {'type': 'create_lobby'})['code']
    assert ask(players['Tiago'], {'type': 'join_lobby', 'code': code})['type'] == 'lobby_state'
    news(players['Mara'])
    return players, start_after_countdown(players, clock)


def target_of(name):
    return lobby_named(name).duel.next_station(name)


def play(connection, name, clock):
    news(connection)
    station = target_of(name)
    put_at_station(name, station)
    opened = ask(connection, {'type': 'open_station', 'station': station})
    assert opened['type'] == 'station_opened'
    assert opened['title'] == minigames.MINIGAMES[station].title
    if station in room_tasks.MINIGAMES:
        assert opened['content']['kind'] == 'campus_task'
    clock.wait(1)
    connection.send_json({'type': 'finish_station'})
    return station, news(connection)


@pytest.mark.parametrize('station', range(7, 13))
def test_each_extra_task_can_be_completed_and_then_an_original_task_follows(connect, clock, monkeypatch, station):
    players, told = running(connect, monkeypatch, [(station, 1, 5), (2, 4, 3)], clock)
    assert [message['next_station'] for message in told['Mara'] if message['type'] == 'duel_state'] == [station]
    assert [message['next_station'] for message in told['Tiago'] if message['type'] == 'duel_state'] == [2]
    played, received = play(players['Mara'], 'Mara', clock)
    assert played == station
    assert received[0] == protocol.station_done(station)
    state = next(message for message in received if message['type'] == 'duel_state')
    assert state == protocol.duel_state(1, 1, 3)
    assert not any(message['type'] == 'duel_state' for message in news(players['Tiago']))
    played, received = play(players['Mara'], 'Mara', clock)
    assert played == 1
    assert target_of('Mara') == 5


def test_all_six_new_games_work_in_the_existing_multiplayer_duel(connect, clock, monkeypatch):
    players, _ = running(connect, monkeypatch, [(7, 9, 12), (8, 10, 11)], clock)
    played = []
    for _ in range(3):
        for name, connection in players.items():
            station, messages = play(connection, name, clock)
            played.append(station)
    assert set(played) == set(range(7, 13))
    assert lobby_named('Mara').phase == 'lobby'
    assert lobby_named('Mara').duel is None
    assert any(message['type'] == 'duel_result' for message in messages)


def test_extra_target_enforces_range_order_close_minimum_time_and_no_duplicate(connect, clock, monkeypatch):
    players, _ = running(connect, monkeypatch, [(9, 7, 11), (8, 10, 12)], clock)
    connection = players['Mara']
    put_at_station('Mara', 7)
    assert ask(connection, {'type': 'open_station', 'station': 7}) == protocol.rejection('station_not_needed')
    put('Mara', SPAWN)
    assert ask(connection, {'type': 'open_station', 'station': 9}) == protocol.rejection('too_far')
    put_at_station('Mara', 9)
    assert ask(connection, {'type': 'open_station', 'station': 9})['type'] == 'station_opened'
    assert ask(connection, {'type': 'close_station'}) == protocol.station_closed(9)
    assert target_of('Mara') == 9
    assert ask(connection, {'type': 'open_station', 'station': 9})['type'] == 'station_opened'
    connection.send_json({'type': 'finish_station'})
    assert news(connection) == [protocol.rejection('too_fast'), protocol.station_closed(9)]
    assert target_of('Mara') == 9
    play(connection, 'Mara', clock)
    assert ask(connection, {'type': 'finish_station'}) == protocol.rejection('no_task_open')
    assert target_of('Mara') == 7


def test_duel_still_requires_two_players_and_the_discarded_campus_mode_is_absent(connect):
    assert protocol.MODES == ('duel', 'classic', 'solo')
    assert protocol.MIN_PLAYERS['duel'] == 2
    connection = player(connect, 'Mara')
    assert ask(connection, {'type': 'create_lobby'})['mode'] == 'duel'
    assert ask(connection, {'type': 'start_game'}) == protocol.too_few_players('duel')
    assert ask(connection, {'type': 'choose_mode', 'mode': 'campus_tasks'})['code'] == 'bad_mode'
