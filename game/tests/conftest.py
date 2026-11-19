"""Shared set-up for all tests.

Tests never touch a real database. Even if a developer has DATABASE_URL set in
the shell, every test gets a fresh store in memory, nobody signed in and no lobbies.
"""

import os

import pytest

# Removed before `server.main` is imported, so the server does not even build
# a Postgres store while the tests run.
os.environ.pop("DATABASE_URL", None)

from server.accounts.store import MemoryAccountStore  # noqa: E402
from server.main import app  # noqa: E402
from server.net.lobbies import Lobbies  # noqa: E402
from server.net.sessions import Sessions  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_accounts_and_sessions():
    app.state.account_store = MemoryAccountStore()
    app.state.sessions = Sessions()
    app.state.lobbies = Lobbies()
