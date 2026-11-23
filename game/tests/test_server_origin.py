"""The Origin check at the WebSocket handshake of the real `/ws` (M3-2.6, S-207).

The test client sends Host "testserver" and no Origin unless a test adds one.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.main import app
from server.net.repeated_faults import RepeatedFaults

GAME_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def client():
    with TestClient(app) as shared_client:
        yield shared_client


def plays(client, headers=None):
    """Connect with these headers, play as a guest and open a lobby; True if all of it worked."""
    with client.websocket_connect("/ws", headers=headers or {}) as connection:
        connection.send_json({"type": "guest"})
        if connection.receive_json()["type"] != "signed_in":
            return False
        connection.send_json({"type": "create_lobby"})
        return connection.receive_json()["type"] == "lobby_state"


def refused(client, headers):
    """True if the handshake is refused with close code 1008 before any message."""
    with pytest.raises(WebSocketDisconnect) as closing:
        with client.websocket_connect("/ws", headers=headers):
            pass
    return closing.value.code == 1008


def test_a_page_of_the_same_host_plays(client):
    assert plays(client, {"origin": "http://testserver"})


def test_a_connection_without_origin_plays(client):
    assert plays(client)


def test_the_deployed_site_behind_renders_proxy_plays(client):
    # As Render forwards it: TLS ended at the edge, plain http to the app,
    # the Host header the public host, the page's Origin https.
    headers = {
        "host": "itp-group.onrender.com",
        "origin": "https://itp-group.onrender.com",
        "x-forwarded-proto": "https",
        "x-forwarded-for": "203.0.113.7",
    }
    assert plays(client, headers)


def test_a_forwarded_host_plays_when_the_proxy_rewrote_host(client):
    headers = {"host": "10.0.0.5:10000", "origin": "https://game.example.org", "x-forwarded-host": "game.example.org"}
    assert plays(client, headers)


def test_the_public_address_plays_even_with_an_unexpected_host(client):
    assert plays(client, {"host": "10.0.0.5:10000", "origin": "https://itp-group.onrender.com"})


def test_a_foreign_page_is_refused_and_the_next_good_one_plays(client):
    assert refused(client, {"origin": "https://evil.example"})
    assert plays(client, {"origin": "http://testserver"})


@pytest.mark.parametrize(
    "origin",
    ["null", "https://itp-group.onrender.com.evil.example", "https://evil-itp-group.onrender.com", "http://testserver:3000", "not an origin"],
)
def test_other_origins_are_refused(client, origin):
    assert refused(client, {"origin": origin})


def test_a_refusal_logs_only_the_host(client, caplog, settings):
    settings.refused_origins = RepeatedFaults()
    with caplog.at_level(logging.WARNING, logger="server.main"):
        assert refused(client, {"origin": "https://evil.example:8443", "cookie": "secret-value"})
    lines = [record.getMessage() for record in caplog.records if record.name == "server.main"]
    assert lines == ["Refused a WebSocket from evil.example"]


def test_many_refusals_within_a_minute_write_one_line(client, caplog, settings):
    settings.refused_origins = RepeatedFaults()
    with caplog.at_level(logging.WARNING, logger="server.main"):
        for number in range(5):
            assert refused(client, {"origin": f"https://evil{number}.example"})
    lines = [record.getMessage() for record in caplog.records if record.name == "server.main"]
    assert lines == ["Refused a WebSocket from evil0.example"]


@pytest.fixture
def settings():
    """Lets a test change the origin settings and the log limit; they are put back afterwards.

    (pytest's monkeypatch cannot be used: it deletes the setting from
    `app.state` on undo instead of restoring it.)
    """
    saved = (app.state.origin_check, app.state.allowed_origins, app.state.refused_origins)
    yield app.state
    app.state.origin_check, app.state.allowed_origins, app.state.refused_origins = saved


def test_the_kill_switch_lets_every_origin_in(client, settings):
    settings.origin_check = False
    assert plays(client, {"origin": "https://evil.example"})
    assert plays(client, {"origin": "null"})


def test_a_listed_origin_plays(client, settings):
    settings.allowed_origins += ("https://game.example.org",)
    assert plays(client, {"origin": "https://game.example.org"})
    assert refused(client, {"origin": "https://other.example.org"})


def settings_at_start(environment: dict) -> dict:
    """The origin settings of a freshly started server with these environment variables."""
    env = {key: value for key, value in os.environ.items() if key not in ("ORIGIN_CHECK", "ALLOWED_ORIGINS")}
    env.update(environment)
    env.pop("DATABASE_URL", None)
    script = (
        "import json; from server.main import app; "
        "print(json.dumps([app.state.origin_check, list(app.state.allowed_origins)]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=GAME_DIR, env=env, capture_output=True, text=True, timeout=120, check=True
    )
    check, listed = json.loads(result.stdout.strip().splitlines()[-1])
    return {"check": check, "listed": listed}


def test_the_server_reads_both_settings_from_the_environment():
    assert settings_at_start({}) == {"check": True, "listed": ["https://itp-group.onrender.com"]}
    assert settings_at_start({"ORIGIN_CHECK": "off", "ALLOWED_ORIGINS": "https://a.example, b.example"}) == {
        "check": False,
        "listed": ["https://itp-group.onrender.com", "https://a.example", "b.example"],
    }

