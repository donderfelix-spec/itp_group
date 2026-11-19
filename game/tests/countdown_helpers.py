"""Helpers for tests that need a round without waiting for its countdown (M2-2.5, S-102).

Since S-102 the host's `start_game` begins a countdown of 5 seconds, and the
tick starts the round after it. Tests that are about the round itself, not
about the countdown, can skip it:

    from countdown_helpers import no_countdown  # noqa: F401

`no_countdown` is used by every test of a file that imports it by name,
asked for or not (like `clock` of task_helpers.py). Tests of the plain rules
call `start_round_at_once` instead of `Lobbies.start`. The countdown itself
is tested in test_countdown.py and test_server_countdown.py.
"""

import pytest

from server import main
from server.main import app
from server.net.lobbies import COUNTDOWN_SECONDS


def start_round_at_once(lobbies, name: str):
    """For tests of the plain rules: the host starts, and the five seconds are over at once.

    Returns what `Lobbies.start` returns, `(lobby, rejection_code)`. After
    an accepted start the lobby's round is running.
    """
    lobby, rejection_code = lobbies.start(name, 0.0)
    if rejection_code is None:
        assert lobby.start_round_if_due(COUNTDOWN_SECONDS)
    return (lobby, rejection_code)


async def start_without_countdown(websocket, name: str, message: dict):
    """Stands in for `main.handle_start_game`: the countdown is over the moment it begins.

    The checks, the start of the round and its messages are the server's
    own. Only the five seconds, and the two messages that announce them, are
    left out, so the players are told about the round in the host's own
    handler: the lobby's state with phase "round", then what the mode tells.
    """
    now = main.seconds_now()
    lobby, rejection_code = app.state.lobbies.start(name, now)
    if rejection_code is None:
        lobby.round_starts_at = now
        assert main.start_round_if_due(lobby)
        await main.tell_round_begins(lobby)
    return rejection_code


@pytest.fixture(autouse=True)
def no_countdown(monkeypatch):
    """Rounds start at once while a test runs that imported this fixture."""
    monkeypatch.setitem(main.LOBBY_HANDLERS, "start_game", start_without_countdown)
