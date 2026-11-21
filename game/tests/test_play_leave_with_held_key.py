"""M2-2.12: "Leave lobby" with a walking key held shows no "You are not in a lobby.".

A walking key held while "Leave lobby" is clicked and released before the
answer `left_lobby` arrived sent `move (0, 0)` after `leave_lobby`. The
server had taken the player out already and refused it with the red message
"You are not in a lobby.". Now the page sends no `move` from the click on
"Leave lobby" until it is in a new lobby.

Checked in Chromium (skipped when Node, Playwright or Chromium is missing),
with the real server. The browser script routes the page's WebSocket,
writes down every message both ways and can hold the answer `left_lobby`
back, so that a key is released for sure before it arrives.
"""

import contextlib
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from test_play_campus_detail import NODE, node_environment, playwright_works

GAME = Path(__file__).resolve().parents[1]
BROWSER_SCRIPT = Path(__file__).with_name("play_leave_with_held_key_in_browser.js")
SCENARIOS = [
    "release_before_answer",
    "release_after_answer",
    "two_keys_before_answer",
    "two_keys_one_before_one_after",
    "no_key_held",
]
WITH_KEYS = [name for name in SCENARIOS if name != "no_key_held"]
RELEASED_BEFORE_THE_ANSWER = ["release_before_answer", "two_keys_before_answer", "two_keys_one_before_one_after"]

needs_chromium = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


@pytest.fixture(scope="module")
def running_server():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app", "--port", str(port)],
        cwd=GAME, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            with contextlib.suppress(OSError):
                urllib.request.urlopen(base + "/health", timeout=1)
                break
            time.sleep(0.1)
        yield base
    finally:
        server.terminate()
        server.wait(timeout=10)


@pytest.fixture(scope="module")
def played(running_server):
    finished = subprocess.run(
        [NODE, str(BROWSER_SCRIPT), running_server],
        env=node_environment(), capture_output=True, text=True, timeout=180, check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def sent(frames):
    return [frame["message"] for frame in frames if frame["way"] == "sent"]


def received(frames):
    return [frame["message"] for frame in frames if frame["way"] == "received"]


def moves_after_leaving(frames):
    """The `move` messages the page sent after its `leave_lobby`."""
    types = [message["type"] for message in sent(frames)]
    assert types.count("leave_lobby") == 1
    after = sent(frames)[types.index("leave_lobby") + 1:]
    return [message for message in after if message["type"] == "move"]


# ---- Accepted: walking before the click, leaving, walking in the next lobby ----


@needs_chromium
@pytest.mark.parametrize("name", WITH_KEYS)
def test_the_held_key_walked_before_the_click(played, name):
    frames = played["scenarios"][name]["frames"]
    types = [message["type"] for message in sent(frames)]
    walks = [message for message in sent(frames)[:types.index("leave_lobby")] if message["type"] == "move"]
    assert walks and (walks[-1]["dx"], walks[-1]["dy"]) != (0, 0)


@needs_chromium
@pytest.mark.parametrize("name", SCENARIOS)
def test_the_player_lands_on_home(played, name):
    seen = played["scenarios"][name]
    assert seen["home"] and not seen["lobby"]
    assert [message["type"] for message in received(seen["frames"])][-1] == "left_lobby"


@needs_chromium
def test_after_joining_a_new_lobby_walking_is_sent_again(played):
    seen = played["again"]
    moves = [(message["dx"], message["dy"]) for message in sent(seen["frames"]) if message["type"] == "move"]
    assert moves == [(1, 0), (0, 0)]
    assert [message for message in received(seen["frames"]) if message["type"] == "error"] == []
    assert seen["lobby"] and not seen["messageShown"]


# ---- Rejected: no move after leave_lobby, and so no refusal ----


@needs_chromium
@pytest.mark.parametrize("name", SCENARIOS)
def test_no_move_is_sent_after_leave_lobby(played, name):
    assert moves_after_leaving(played["scenarios"][name]["frames"]) == []


@needs_chromium
@pytest.mark.parametrize("name", SCENARIOS)
def test_no_refusal_comes_and_no_red_message_is_shown(played, name):
    seen = played["scenarios"][name]
    assert [message for message in received(seen["frames"]) if message["type"] == "error"] == []
    assert not seen["messageShown"]


@needs_chromium
def test_the_server_still_refuses_a_move_outside_a_lobby(played):
    seen = played["refused"]
    errors = [message for message in received(seen["frames"]) if message["type"] == "error"]
    assert errors == [{"type": "error", "code": "not_in_lobby", "message": "You are not in a lobby."}]
    assert seen["messageShown"] and seen["messageIsError"]
    assert seen["messageText"] == "You are not in a lobby."


# ---- Edge cases ----


@needs_chromium
@pytest.mark.parametrize("name", RELEASED_BEFORE_THE_ANSWER)
def test_the_keys_were_released_before_the_answer_arrived(played, name):
    # Proves that these scenarios test the race: the answer was held back,
    # so the Home screen was not shown yet when the key was let go.
    assert played["scenarios"][name]["homeAtRelease"] is False


@needs_chromium
def test_no_page_logs_a_console_error_or_warning(played):
    assert played["console"] == []
