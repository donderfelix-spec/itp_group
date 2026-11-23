"""The play test of S-125 to S-130 (Solo, stations as objects, the task card, one player list), as repeatable tests.

A tester played a Duel with two guests (1280x800 and 320x640) to the
ranking, a Duel with eight guests, Solo rounds until all eleven minigames
were solved, and a Classic round with five guests. What can be checked
without walking is repeated here in Chromium (skipped when Node,
Playwright or Chromium is missing), with the real server:

- in the lobby the card shows only the room, all eleven station objects are
  drawn and none pulses; Duel and Solo stand side by side, Classic below
  over the whole width;
- at the start of a Duel the two guests start at different stations, only
  the own next station pulses, the card says "NEXT TASK" with the title,
  the player list shows "0/3" with an empty bar, the old list under "Duel"
  is gone, and at 320 px the card covers neither the own character nor
  the walking hint;
- one guest alone starts Solo, and the panel says "Solo";
- in Classic only the own active task pulses and the card names it (S-197);
- no page logs a console error or warning.
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
BROWSER_SCRIPT = Path(__file__).with_name("play_task_card_in_browser.js")
STATIONS_IN_USE = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12]
# Every station's object is drawn; station 6 too since M3-1.7 (S-196), though
# it is not in use yet. Until then the drawn ones were STATIONS_IN_USE.
STATIONS_DRAWN = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

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


def overlaps(a, b):
    return a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]


@needs_chromium
def test_no_page_logs_a_console_error_or_warning(played):
    assert played["console"] == []


@needs_chromium
@pytest.mark.parametrize("who", ["wide", "narrow"])
def test_in_the_lobby_the_card_shows_only_the_room_and_no_station_pulses(played, who):
    seen = played["lobby"][who]
    assert seen["card"] and seen["here"] == "Main Deck"
    assert not seen["taskPart"]
    assert seen["pulse"] == []
    assert seen["drawn"] == STATIONS_DRAWN


@needs_chromium
def test_duel_and_solo_stand_side_by_side_and_classic_below_over_the_whole_width(played):
    duel, solo, classic = played["lobby"]["modes"]
    assert [duel["name"], solo["name"], classic["name"]] == ["Duel", "Solo", "Classic"]
    assert duel["y"] == solo["y"] and solo["x"] > duel["x"]
    assert classic["y"] > duel["y"]
    assert classic["x"] == duel["x"] and classic["w"] == pytest.approx(solo["x"] + solo["w"] - duel["x"], abs=1)


@needs_chromium
def test_two_duel_players_start_at_different_stations(played):
    firsts = [played["duel"][who]["firstStation"] for who in ("wide", "narrow")]
    assert all(station in STATIONS_IN_USE for station in firsts)
    assert firsts[0] != firsts[1]


@needs_chromium
@pytest.mark.parametrize("who", ["wide", "narrow"])
def test_in_a_duel_only_the_next_station_pulses_and_the_card_names_it(played, who):
    seen = played["duel"][who]
    assert seen["pulse"] == [seen["firstStation"]]
    assert seen["taskPart"] and seen["kicker"] == "NEXT TASK" and seen["title"]
    assert seen["duelHeading"] == "Duel"


@needs_chromium
@pytest.mark.parametrize("who", ["wide", "narrow"])
def test_in_a_duel_the_player_list_shows_the_progress_and_the_old_list_is_gone(played, who):
    seen = played["duel"][who]
    assert seen["rows"] == [{"done": "0/3", "bar": "0%"}] * 2
    assert not seen["oldDuelList"]


@needs_chromium
def test_at_320_pixels_the_card_covers_neither_the_own_character_nor_the_hint(played):
    seen = played["duel"]["narrow"]
    assert not overlaps(seen["cardRect"], seen["ownRect"])
    assert not overlaps(seen["cardRect"], seen["hintRect"])


@needs_chromium
def test_one_guest_alone_starts_solo_and_the_panel_says_solo(played):
    seen = played["solo"]
    assert seen["firstStation"] in STATIONS_IN_USE
    assert seen["duelHeading"] == "Solo"
    assert seen["pulse"] == [seen["firstStation"]]
    assert seen["rows"] == [{"done": "0/3", "bar": "0%"}]


@needs_chromium
def test_in_classic_only_the_active_task_pulses_and_the_card_names_it(played):
    """S-197: a High Performer has one active task, a Free Rider none."""
    for seen in played["classic"]:
        assert seen["pulse"] == sorted(seen["ownList"])
        assert len(seen["ownList"]) in (0, 1)
        assert seen["card"]
        if seen["ownList"]:
            assert seen["taskPart"] and seen["kicker"] in ("NEXT TASK", "E USE · YOUR TASK") and seen["title"]
        else:
            assert not seen["taskPart"]
        assert seen["drawn"] == STATIONS_DRAWN
    assert sum(1 for seen in played["classic"] if seen["ownList"]) == 3
