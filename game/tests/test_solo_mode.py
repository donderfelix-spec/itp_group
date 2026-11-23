"""The user-requested Solo mode reuses Duel's real task lifecycle."""
import json

import pytest

from server import main, protocol
from server.modes import duel
from extra_task_helpers import news, start_after_countdown, no_countdown  # noqa: F401
from task_helpers import (  # noqa: F401
    ask, client, clock, connect, lobby_named, player, put_at_station,
)


def solo_lobby(connect):
    connection = player(connect, 'Mara')
    assert ask(connection, {'type': 'create_lobby'})['mode'] == 'solo'  # one player: Solo (S-203)
    assert ask(connection, {'type': 'choose_mode', 'mode': 'solo'})['mode'] == 'solo'
    return connection


def start(connection, clock):
    return start_after_countdown({'Mara': connection}, clock)['Mara']


def play(connection, clock):
    lobby = lobby_named('Mara')
    station = lobby.duel.next_station('Mara')
    put_at_station('Mara', station)
    assert ask(connection, {'type': 'open_station', 'station': station})['type'] == 'station_opened'
    clock.wait(1)
    connection.send_json({'type': 'finish_station'})
    return station, news(connection)


def test_solo_mode_is_explicit_and_a_single_player_receives_their_current_task(connect, clock):
    assert protocol.parse_client_message(json.dumps({'type': 'choose_mode', 'mode': 'solo'})) == {
        'type': 'choose_mode', 'mode': 'solo',
    }
    assert protocol.DEFAULT_MODE == 'duel'
    assert protocol.MIN_PLAYERS['solo'] == 1
    assert main.ROUND_SETUPS['solo'] is main.ROUND_SETUPS['duel']
    assert duel.ROUND_SECONDS == 180
    connection = solo_lobby(connect)
    told = start(connection, clock)
    assert [message['type'] for message in told] == ['lobby_state', 'duel_state', 'duel_progress']
    state = told[1]
    assert set(state) == {'type', 'next_station', 'done', 'total'}
    assert state['total'] == 3 and state['done'] == 0
    assert state['next_station'] == lobby_named('Mara').duel.next_station('Mara')
    assert told[2] == protocol.duel_progress([('Mara', 0)], 3, 180)


def test_solo_mode_rejects_an_unassigned_station(connect, clock):
    connection = solo_lobby(connect)
    state = start(connection, clock)[1]
    wrong = next(station for station in (1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12)
                 if station != state['next_station'])
    put_at_station('Mara', wrong)
    assert ask(connection, {'type': 'open_station', 'station': wrong}) == protocol.rejection('station_not_needed')
    assert lobby_named('Mara').duel.state_of('Mara')[1] == 0


def test_solo_mode_finishes_three_real_tasks_then_can_restart(connect, clock, monkeypatch):
    monkeypatch.setattr(duel, 'draw_routes', lambda names, stations, distances, rng: {'Mara': (9, 1, 12)})
    connection = solo_lobby(connect)
    start(connection, clock)
    for index in range(3):
        station, received = play(connection, clock)
        assert received[0] == protocol.station_done(station)
        assert next(message for message in received if message['type'] == 'duel_state')['done'] == index + 1
    lobby = lobby_named('Mara')
    assert lobby.phase == 'lobby'
    assert lobby.tasks is None and lobby.duel is None
    result = next(message for message in received if message['type'] == 'duel_result')
    assert result == protocol.duel_result([{'place': 1, 'name': 'Mara', 'seconds': 3.0, 'done': 3}], False)
    assert received[-1]['type'] == 'lobby_state'
    assert received[-1]['mode'] == 'solo'
    restarted = start(connection, clock)
    assert restarted[1] == protocol.duel_state(9, 0, 3)
    assert lobby.tasks.finished_by('Mara') == set()


def test_regular_duel_still_refuses_a_single_player(connect):
    connection = player(connect, 'Mara')
    assert ask(connection, {'type': 'create_lobby'})['mode'] == 'solo'  # one player: Solo (S-203)
    assert ask(connection, {'type': 'choose_mode', 'mode': 'duel'})['mode'] == 'duel'
    assert ask(connection, {'type': 'start_game'}) == protocol.too_few_players('duel')
    assert protocol.MIN_PLAYERS['duel'] == 2
    assert lobby_named('Mara').phase == 'lobby'


def test_a_signed_in_solo_round_cannot_change_duel_statistics_or_the_leaderboard(connect, clock, monkeypatch):
    """Even a completed practice win leaves an account's real record untouched."""
    monkeypatch.setattr(duel, 'draw_routes', lambda names, stations, distances, rng: {'Mara': (9, 1, 12)})
    connection = solo_lobby(connect)
    store = main.app.state.statistics_store
    store.record_round('duel', [
        {'name': 'Mara', 'rounds': 2, 'wins': 1, 'best_seconds': 12.0},
    ])
    records_before = store.records_of('Mara')
    leaderboard_before = store.top(20)
    profile_before = ask(connection, {'type': 'get_profile'})
    # Classic is a built mode since the merge of main, so it has a row of its own.
    assert profile_before == protocol.profile('Mara', [('duel', 2, 1), ('classic', 0, 0)], 12.0)

    # Capture the boundary before background writes, so the regression
    # cannot pass merely because an incorrect write has not run yet.
    pending_results = []
    write_result_later = main.write_result_later
    def note_result(result):
        pending_results.append(result)
        write_result_later(result)
    monkeypatch.setattr(main, 'write_result_later', note_result)

    start(connection, clock)
    for _ in range(3):
        _, messages = play(connection, clock)
    assert any(message['type'] == 'duel_result' for message in messages)
    assert lobby_named('Mara').phase == 'lobby'
    assert pending_results == [None]
    assert store.records_of('Mara') == records_before
    assert store.top(20) == leaderboard_before
    assert ask(connection, {'type': 'get_profile'}) == profile_before


@pytest.mark.parametrize('mode', ['SOLO', 'Solo', 'solo ', 'test', 'Test mode', ['solo'], {'mode': 'solo'}])
def test_solo_mode_does_not_bypass_mode_message_validation(mode):
    with pytest.raises(protocol.ProtocolError) as caught:
        protocol.parse_client_message(json.dumps({'type': 'choose_mode', 'mode': mode}))
    assert caught.value.code == 'bad_mode'
