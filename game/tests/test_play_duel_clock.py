"""M2-2.11: in a Duel or Solo round the clock is seen without scrolling, also with eight players.

The clock (`#duel-clock`) and the own next task (`#duel-next`) stood below
the player list in the scrolling middle of the side panel. With eight
players and their progress rows (S-130) they were only seen after
scrolling in a 1280x800 window. Now the Duel panel stands first in the
middle of the panel.

Checked in Chromium (skipped when Node, Playwright or Chromium is missing),
with the real server: eight guests in one lobby, the host starts a Duel;
the host and one other guest are measured at 1280x800, 1024x700 and
320x640. Then one guest plays Solo alone, and four guests play Classic.
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
BROWSER_SCRIPT = Path(__file__).with_name("play_duel_clock_in_browser.js")
WIDE_SIZES = ["1280x800", "1024x700"]
NARROW_SIZE = "320x640"
ALL_SIZES = WIDE_SIZES + [NARROW_SIZE]
WHO = ["host", "guest"]

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
        env=node_environment(), capture_output=True, text=True, timeout=240, check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def is_fully_seen(box, panel):
    """Whether `box` lies inside the visible part of the panel's middle and inside the window."""
    visible = panel["visible"]
    window = panel["window"]
    inside_panel = (
        box["top"] >= visible["top"] and box["bottom"] <= visible["bottom"]
        and box["left"] >= visible["left"] and box["right"] <= visible["right"]
    )
    inside_window = box["top"] >= 0 and box["bottom"] <= window["height"] and box["right"] <= window["width"]
    return inside_panel and inside_window


def assert_seen_without_scrolling(panel):
    assert panel["middleScrollTop"] == 0 and panel["pageScrollY"] == 0
    assert panel["clock"] is not None and panel["next"] is not None
    assert is_fully_seen(panel["clock"], panel), (panel["clock"], panel["visible"])
    assert is_fully_seen(panel["next"], panel), (panel["next"], panel["visible"])


# ---- Accepted: the clock and the next task are seen ----


@needs_chromium
@pytest.mark.parametrize("size", WIDE_SIZES)
@pytest.mark.parametrize("who", WHO)
def test_in_a_duel_with_eight_players_clock_and_next_task_are_seen_without_scrolling(played, size, who):
    panel = played["duel"][size][who]
    assert panel["playerRows"] == 8
    assert panel["clockText"] and panel["nextText"].startswith("Next:")
    assert_seen_without_scrolling(panel)


@needs_chromium
@pytest.mark.parametrize("size", ALL_SIZES)
@pytest.mark.parametrize("who", WHO)
def test_the_clock_stands_before_the_player_list(played, size, who):
    panel = played["duel"][size][who]
    assert panel["firstShownId"] == "duel-panel"
    assert panel["clock"]["bottom"] <= panel["players"]["top"]


@needs_chromium
@pytest.mark.parametrize("who", WHO)
def test_at_320_pixels_the_clock_is_not_pushed_below_the_eight_players(played, who):
    panel = played["duel"][NARROW_SIZE][who]
    assert panel["playerRows"] == 8
    assert panel["next"]["bottom"] <= panel["players"]["top"]
    assert not panel["pageScrollsSideways"]


@needs_chromium
@pytest.mark.parametrize("size", ALL_SIZES)
def test_solo_shows_the_same_layout_with_its_own_heading(played, size):
    panel = played["solo"][size]
    assert panel["heading"] == "Solo"
    assert panel["firstShownId"] == "duel-panel"
    assert panel["clock"]["bottom"] <= panel["players"]["top"]
    if size in WIDE_SIZES:
        assert_seen_without_scrolling(panel)


# ---- What must stay as it was (S-110, S-113, S-130, lobby, Classic) ----


@needs_chromium
@pytest.mark.parametrize("size", ALL_SIZES)
def test_the_duel_player_list_keeps_its_progress_and_the_old_list_stays_gone(played, size):
    for panel in played["duel"][size].values():
        assert panel["progressRows"] == ["0/3"] * 8
        assert panel["bars"] == 8
        assert not panel["oldDuelList"]


@needs_chromium
def test_in_the_lobby_the_panel_starts_with_the_players_as_before(played):
    panel = played["lobby"]
    assert panel["duelPanel"] is None
    assert panel["firstShownId"] == "Players"
    assert panel["playerRows"] == 8
    assert panel["progressRows"] == [] and panel["bars"] == 0
    # The order below the list is unchanged: modes, then the characters.
    assert panel["players"]["bottom"] <= panel["modes"]["top"] <= panel["characterArea"]["top"]


@needs_chromium
def test_in_the_lobby_all_character_buttons_are_equally_high(played):
    heights = played["lobby"]["characterHeights"]
    assert len(heights) == 8
    assert max(heights) - min(heights) < 0.5


@needs_chromium
def test_in_classic_the_group_progress_stands_below_the_players_as_before(played):
    panel = played["classic"]
    assert panel["duelPanel"] is None
    assert panel["firstShownId"] == "Players"
    assert panel["progressRows"] == [] and panel["bars"] == 0
    assert panel["classicProgress"] is not None
    assert panel["players"]["bottom"] <= panel["classicProgress"]["top"]


# ---- Edge: nothing is logged ----


@needs_chromium
def test_no_page_logs_a_console_error_or_warning(played):
    assert played["console"] == []
