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
from server.net.lobbies import Lobbies  # noqa: E402
from server.net.sessions import Sessions  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_accounts_and_sessions():
    app.state.account_store = MemoryAccountStore()
    app.state.statistics_store = MemoryStatisticsStore()
    app.state.leaderboard_cache = LeaderboardCache()
    app.state.leaderboard_call = None
    app.state.sessions = Sessions()
    app.state.lobbies = Lobbies()
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
