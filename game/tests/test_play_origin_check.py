"""M3-2.5 (S-207): the Origin check with the real server, in Chromium and with raw handshakes.

In Chromium (skipped when Node, Playwright or Chromium is missing): the game
page plays on http://localhost and http://127.0.0.1 without any setting; a
page of another site (another port) that opens `ws://.../ws` is refused; the
game page plays behind a proxy that keeps Host (as Render's does) and behind
one that rewrites Host but names the public host in X-Forwarded-Host.

Without a browser: handshakes sent by hand with the headers Render's proxy
sends (Host the public host, Origin https, the app spoken to in http), and
servers started with ORIGIN_CHECK=off and ALLOWED_ORIGINS.
"""

import contextlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

from test_play_campus_detail import NODE, node_environment, playwright_works

GAME = Path(__file__).resolve().parents[1]
BROWSER_SCRIPT = Path(__file__).with_name("play_origin_check_in_browser.js")
PUBLIC = "itp-group.onrender.com"

needs_chromium = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextlib.contextmanager
def game_server(**settings):
    """The real server on a free port, with these environment variables; yields (port, log file)."""
    port = free_port()
    env = {key: value for key, value in os.environ.items() if key not in ("ORIGIN_CHECK", "ALLOWED_ORIGINS", "DATABASE_URL")}
    env.update(settings)
    with tempfile.TemporaryFile(mode="w+") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server.main:app", "--port", str(port)],
            cwd=GAME, env=env, stdout=subprocess.DEVNULL, stderr=log,
        )
        try:
            for _ in range(200):
                with contextlib.suppress(OSError):
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
                    break
                time.sleep(0.1)
            else:
                pytest.fail("The server did not start within 20 seconds")
            yield port, log
        finally:
            server.terminate()
            server.wait(timeout=10)


def handshake(port: int, headers: dict) -> int:
    """Send a WebSocket handshake with exactly these headers; return the HTTP status (101 = accepted)."""
    lines = ["GET /ws HTTP/1.1"]
    lines += [f"{name}: {value}" for name, value in headers.items()]
    lines += ["Upgrade: websocket", "Connection: Upgrade", "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==", "Sec-WebSocket-Version: 13"]
    with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
        connection.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("ascii"))
        status_line = connection.recv(4096).split(b"\r\n", 1)[0].decode("ascii")
    return int(status_line.split()[1])


def render_headers(origin=f"https://{PUBLIC}", host=PUBLIC, **more):
    """What Render's edge sends on to the app: TLS ended, plain http, the public Host."""
    headers = {"Host": host, "Origin": origin, "X-Forwarded-Proto": "https", "X-Forwarded-For": "203.0.113.7"}
    headers.update(more)
    return headers


def log_text(log) -> str:
    log.flush()
    log.seek(0)
    return log.read()


@pytest.fixture(scope="module")
def default_server():
    with game_server() as running:
        yield running


# ---- Raw handshakes ----


def test_the_deployed_page_behind_renders_proxy_is_accepted(default_server):
    port, _ = default_server
    assert handshake(port, render_headers()) == 101
    assert handshake(port, render_headers(host=f"{PUBLIC}:443")) == 101


def test_the_deployed_page_is_accepted_even_if_the_proxy_rewrote_host(default_server):
    port, _ = default_server
    assert handshake(port, render_headers(host="10.0.0.5:10000")) == 101
    assert handshake(port, render_headers(origin="https://game.example.org", host="10.0.0.5:10000", **{"X-Forwarded-Host": "game.example.org"})) == 101


def test_a_foreign_page_is_refused_with_403_and_logged_by_host_only(default_server):
    port, log = default_server
    assert handshake(port, render_headers(origin="https://evil.example")) == 403
    assert handshake(port, render_headers(origin="null")) == 403
    assert handshake(port, render_headers(origin=f"https://{PUBLIC}.evil.example")) == 403
    ours = [line for line in log_text(log).splitlines() if line.startswith("Refused")]
    # Only the host of the refused origin, nothing else of the request; the
    # next refusals within a minute are counted, not logged one by one.
    assert ours == ["Refused a WebSocket from evil.example"]


def test_a_program_without_origin_is_accepted(default_server):
    port, _ = default_server
    assert handshake(port, {"Host": f"127.0.0.1:{port}"}) == 101


def test_the_kill_switch_in_the_environment_lets_a_foreign_page_in():
    with game_server(ORIGIN_CHECK="off") as (port, _):
        assert handshake(port, render_headers(origin="https://evil.example")) == 101


def test_an_origin_listed_in_the_environment_is_accepted():
    with game_server(ALLOWED_ORIGINS="https://game.example.org, other.example") as (port, _):
        assert handshake(port, render_headers(origin="https://game.example.org", host="internal")) == 101
        assert handshake(port, render_headers(origin="http://other.example", host="internal")) == 101
        assert handshake(port, render_headers(origin="https://evil.example", host="internal")) == 403


# ---- In Chromium ----


@pytest.fixture(scope="module")
def played(default_server):
    port, _ = default_server
    finished = subprocess.run(
        [NODE, str(BROWSER_SCRIPT), str(port)],
        env=node_environment(), capture_output=True, text=True, timeout=180, check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


@needs_chromium
def test_the_game_plays_on_localhost_and_127_0_0_1_without_any_setting(played):
    assert played["direct"] == {"localhost": True, "ip": True}


@needs_chromium
def test_a_page_of_another_site_cannot_open_the_games_websocket(played):
    for attempt in played["foreign"].values():
        assert attempt["opened"] is False and attempt.get("timedOut") is not True, attempt
    # Chromium names the refusal at the handshake.
    assert any("403" in line for line in played["console"]["foreign"]), played["console"]["foreign"]


@needs_chromium
def test_the_game_plays_behind_a_proxy_that_keeps_host_or_forwards_it(played):
    assert played["proxied"]["keepHost"] is True
    assert played["proxied"]["forwardedHost"] is True


@needs_chromium
def test_a_proxy_that_hides_the_public_host_is_refused_until_allowed(played):
    # Then ALLOWED_ORIGINS or ORIGIN_CHECK=off is needed (README); the public
    # address of the deployed game is allowed in any case.
    assert played["proxied"]["rewrittenHostOnly"]["opened"] is False


@needs_chromium
def test_the_pages_that_play_log_nothing(played):
    for label in ("localhost", "ip", "keepHost", "forwardedHost"):
        assert played["console"][label] == [], (label, played["console"][label])
