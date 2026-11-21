"""Exercise the real countdown before playing the branch's added tasks.

The normal tick is quiet in WebSocket tests. Keep its original function
before the fixture replaces it, and drive it with the injected clock.
"""
import time

import pytest

from server import main, protocol
from server.net.lobbies import COUNTDOWN_SECONDS
from task_helpers import lobby_named

REAL_TICK = main.tick


@pytest.fixture(autouse=True)
def no_countdown():
    """Override the global skip fixture: these tests drive the real countdown."""


def news(connection):
    connection.send_json({'type': 'hello', 'name': 'Reader'})
    messages = []
    while True:
        message = connection.receive_json()
        if message['type'] == 'welcome':
            return messages
        if message['type'] != 'positions':
            messages.append(message)


def wait_for_round_messages(connection):
    deadline = time.monotonic() + 5
    messages = []
    while True:
        messages += news(connection)
        if any(message['type'] == 'duel_progress' for message in messages):
            return messages
        assert time.monotonic() < deadline, 'the round did not start after its countdown'
        time.sleep(0.01)


def start_after_countdown(players, clock):
    """Start, verify the real countdown, advance five seconds, then tick once."""
    names = list(players)
    host = players[names[0]]
    host.send_json({'type': 'start_game'})
    for name, connection in players.items():
        announced = news(connection)
        assert [message['type'] for message in announced] == ['lobby_state', 'countdown'], announced
        assert announced[0]['phase'] == protocol.PHASE_COUNTDOWN
        assert announced[1] == protocol.countdown(COUNTDOWN_SECONDS)
        lobby = lobby_named(name)
        assert lobby.tasks is None and lobby.duel is None
    clock.wait(COUNTDOWN_SECONDS)
    host.portal.call(REAL_TICK, 0.0)
    told = {name: wait_for_round_messages(connection) for name, connection in players.items()}
    for name in names:
        assert told[name][0]['type'] == 'lobby_state'
        assert told[name][0]['phase'] == protocol.PHASE_ROUND
    return told
