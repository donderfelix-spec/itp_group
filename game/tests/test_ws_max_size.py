"""The documented start command limits a WebSocket frame to 4096 bytes (S-224, audit A8a).

Without `--ws-max-size` uvicorn reads frames of up to 16 MiB into memory
before `protocol.py` refuses anything above 2048 bytes. With
`--ws-max-size 4096` a larger frame closes only that connection (1009), a
frame between 2048 and 4096 bytes still gets the polite "too long" answer,
the largest message a browser sends (under 2048 bytes) is untouched, and the
server's own messages to the browser are not limited by it.
"""

import asyncio
import contextlib
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
import websockets

from server.protocol import MAX_MESSAGE_BYTES

GAME = Path(__file__).resolve().parents[1]
WS_MAX_SIZE = 4096  # the value of the start command in README.md and AGENTS.md


@pytest.fixture(scope="module")
def limited_server():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app", "--port", str(port), "--ws-max-size", str(WS_MAX_SIZE)],
        cwd=GAME, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            with contextlib.suppress(OSError):
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
                break
            time.sleep(0.1)
        yield f"ws://127.0.0.1:{port}/ws"
    finally:
        server.terminate()
        server.wait(timeout=10)


async def ask(socket_, message):
    await socket_.send(message if isinstance(message, str) else json.dumps(message))
    return json.loads(await socket_.recv())


def test_the_limit_is_above_every_message_a_browser_may_send():
    assert MAX_MESSAGE_BYTES < WS_MAX_SIZE


def test_a_normal_message_and_a_too_long_one_below_the_limit_get_their_answers(limited_server):
    async def play():
        async with websockets.connect(limited_server) as connection:
            assert (await ask(connection, {"type": "guest"}))["type"] == "signed_in"
            assert (await ask(connection, "x" * 3000))["code"] == "too_large"
            # The connection is still open and works.
            assert (await ask(connection, {"type": "create_lobby"}))["type"] == "lobby_state"
    asyncio.run(play())


def test_a_frame_above_the_limit_closes_only_its_own_connection(limited_server):
    async def play():
        async with websockets.connect(limited_server) as bystander:
            await ask(bystander, {"type": "guest"})
            async with websockets.connect(limited_server) as attacker:
                await attacker.send("x" * (5 * 1024))
                with pytest.raises(websockets.ConnectionClosed) as closed:
                    await attacker.recv()
                assert closed.value.rcvd.code == 1009  # message too big
            # The other player is still served, also with a long answer from the server.
            assert (await ask(bystander, {"type": "get_leaderboard"}))["type"] == "leaderboard"
    asyncio.run(play())
