"""Private task destinations join Classic's existing packets, never its public progress."""
from server import main, protocol
from task_helpers import client, clock, connect  # noqa: F401
from test_classic_server_features import ask, classic_for, put_at_station, start_classic
from extra_task_helpers import news


def expected_tasks(classic, player):
    if classic.roles[player] != 'HP':
        return []
    return [int(station) for station in classic.tasks[player]
            if station not in classic.completed_tasks[player]]


def test_role_packet_contains_only_its_own_private_task_destinations(connect):
    players, _code, public, messages = start_classic(connect)
    classic = classic_for('Mara')
    for message in public:
        assert 'task_stations' not in message
    for name, received in messages.items():
        card = next(message for message in received if message['type'] == 'classic_role')
        assert card['task_stations'] == expected_tasks(classic, name)
        expected_fields = {'type', 'role', 'task_stations'}
        if classic.roles[name] == 'FR':
            expected_fields.add('other_free_riders')
            assert card['task_stations'] == []
        else:
            assert len(card['task_stations']) == 4
        assert set(card) == expected_fields
        for message in received:
            if message['type'] != 'classic_role':
                assert 'task_stations' not in message


def test_completion_reveals_own_remaining_tasks_and_never_broadcasts_them(connect, clock):
    players, _code, _public, _messages = start_classic(connect)
    classic = classic_for('Mara')
    name = next(player for player, role in classic.roles.items() if role == 'HP')
    original = list(expected_tasks(classic, name))
    for index, station in enumerate(original):
        put_at_station(name, station)
        assert ask(players[name], {'type': 'open_station', 'station': station})['type'] == 'station_opened'
        clock.wait(1.1)
        assert ask(players[name], {'type': 'finish_station'}) == {
            'type': 'station_done', 'station': station, 'task_stations': original[index + 1:],
        }
        own_updates = news(players[name])
        assert own_updates and all(message['type'] == 'classic_progress' for message in own_updates)
        for other, connection in players.items():
            if other == name:
                continue
            updates = news(connection)
            assert updates and all(message['type'] == 'classic_progress' for message in updates)
            assert all('task_stations' not in message for message in updates)
    assert main.classic_task_stations(classic, name) == []


def test_a_failed_private_update_rolls_back_classic_and_frame_progress(connect, clock, monkeypatch):
    players, _code, _public, _messages = start_classic(connect)
    classic = classic_for('Mara')
    name = next(player for player, role in classic.roles.items() if role == 'HP')
    original = expected_tasks(classic, name)
    station = original[0]
    put_at_station(name, station)
    assert ask(players[name], {'type': 'open_station', 'station': station})['type'] == 'station_opened'
    clock.wait(1.1)
    def broken(*args):
        raise RuntimeError('cannot build the private task reply')
    with monkeypatch.context() as changes:
        changes.setattr(main, 'classic_task_stations', broken)
        assert ask(players[name], {'type': 'finish_station'}) == protocol.rejection('task_failed')
        news(players[name])
    assert expected_tasks(classic, name) == original
    assert classic.completed_tasks[name] == set()
    lobby = main.app.state.lobbies.lobby_of(name)
    assert lobby.tasks.finished_by(name) == set()
    assert not lobby.tasks.has_open_task(name)
