"""Shared set-up for all tests.

Tests never touch a real database. Even if a developer has DATABASE_URL set in
the shell, every test gets a fresh store in memory, nobody signed in and no lobbies.
"""

import os

import pytest

# Removed before `server.main` is imported, so the server does not even build
# a Postgres store while the tests run.
os.environ.pop("DATABASE_URL", None)

from server.accounts.leaderboard_cache import LeaderboardCache  # noqa: E402
from server.accounts.statistics_store import MemoryStatisticsStore  # noqa: E402
from server.accounts.store import MemoryAccountStore  # noqa: E402
from server import main  # noqa: E402
from server.main import app  # noqa: E402
from server.net.attempts import AttemptLimits  # noqa: E402
from server.net.lobbies import Lobbies  # noqa: E402
from server.net.repeated_faults import RepeatedFaults  # noqa: E402
from server.net.sessions import Sessions  # noqa: E402

# `no_countdown` runs for every test: a stand-in answers `start_game` and
# starts the round at once (see countdown_helpers.py).
#
# That answer is NOT what the real server sends. The real server answers
# `start_game` with the lobby's state in phase "countdown" and a `countdown`
# message, and starts the round five seconds later from the tick (S-102).
# Existing tests that read phase "round" in the answer to `start_game`
# therefore describe the stand-in, not the server. The real contract is
# tested in tests/test_server_countdown.py, which replaces this fixture with
# one of the same name that does nothing.
from countdown_helpers import no_countdown  # noqa: E402, F401


@pytest.fixture(autouse=True)
def fresh_accounts_and_sessions():
    app.state.account_store = MemoryAccountStore()
    app.state.statistics_store = MemoryStatisticsStore()
    app.state.leaderboard_cache = LeaderboardCache()
    app.state.leaderboard_call = None
    app.state.sessions = Sessions()
    app.state.attempt_limits = AttemptLimits()
    app.state.lobbies = Lobbies()
    # Otherwise a fault logged in one test would be swallowed in the next (M1-2.15).
    app.state.repeated_faults = RepeatedFaults()
    main.taking_positions.clear()


@pytest.fixture(autouse=True)
def quiet_tick(monkeypatch):
    """Switch the tick off, so that no `positions` messages are sent.

    The tests of accounts and lobby count the messages a player gets, and a
    `positions` message in between would confuse them. The tests of walking
    (test_server_walking.py) want the real tick: they replace this fixture
    with one of the same name that does nothing.

    So the lobby and account tests run without any positions traffic. How
    lobby messages and positions mix is tested in test_server_walking.py.
    """
    monkeypatch.setattr(main, "tick", lambda seconds: None)
