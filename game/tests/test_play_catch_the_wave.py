"""Station 6, "Catch the wave", played end to end in Chromium (M4-4.0, S-221).

The real server runs in this process with the real minigame at station 6;
only the drawing of routes and task lists is fixed so that station 6 comes
first for everybody, and the red button is unlocked from the start. The browser script plays:

- a Duel of two guests (1280x800 and 1024x600): the card names "Catch the
  wave", E opens its window inside the viewport with the button focused, a
  click too early only says so, three catches with Space finish it, "Done"
  shows, the next station follows and the other guest sees 1/3;
- a Classic round of four guests: a High Performer catches three waves with
  the mouse and the group bar grows; E of the Free Rider standing at station
  6 opens nothing (S-154); a second High Performer's open window closes when a third
  player calls an emergency meeting (S-199).

No page logs a console error or warning. Skipped when Node, Playwright or
Chromium is missing.
"""

import contextlib
import json
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn

from server.classic import round as classic_round
from server.main import app
from server.modes import duel as duel_rules
from test_play_campus_detail import NODE, node_environment
from test_play_classic_task_card_end_to_end import (  # noqa: F401 (fixtures)
    needs_chromium,
    no_countdown,
    put,
    quiet_tick,
)

BROWSER_SCRIPT = Path(__file__).with_name("play_catch_the_wave_in_browser.js")
BUTTON = app.state.campus["button"]


@pytest.fixture(scope="module")
def station_6_first():
    """Every route and every task list starts at station 6, the rest as drawn."""
    def routes(names, stations, distances, rng):
        given = [(6, 1, 5), (5, 6, 1), (1, 5, 6)]
        return {name: given[index % len(given)] for index, name in enumerate(names)}

    real_assign = classic_round.assign_tasks

    def tasks(roles, stations, rng):
        drawn = real_assign(roles, stations, rng)
        return {name: ["6"] + [station for station in own if station != "6"][:3] for name, own in drawn.items()}

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(duel_rules, "draw_routes", routes)
        patch.setattr(classic_round, "assign_tasks", tasks)
        # The red button unlocks at once, so a meeting can start while a
        # wave window is open (normally after 45 s).
        patch.setattr(classic_round, "EMERGENCY_DELAY_SECONDS", 0.0)
        yield


@pytest.fixture(scope="module")
def real_server(station_6_first):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        with contextlib.suppress(OSError):
            urllib.request.urlopen(base + "/health", timeout=1)
            break
        time.sleep(0.1)
    yield base
    server.should_exit = True
    thread.join(timeout=10)


def place(name, where):
    if where == "button":
        where = [BUTTON["x"], BUTTON["y"]]
    put(name, where)


@pytest.fixture(scope="module")
def played(real_server):
    browser = subprocess.Popen(
        [NODE, str(BROWSER_SCRIPT), real_server], env=node_environment(),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    timer = threading.Timer(240, browser.kill)
    timer.start()
    try:
        result = None
        for line in browser.stdout:
            message = json.loads(line)
            if "put" in message:
                for name, where in message["put"]:
                    place(name, where)
                browser.stdin.write("ok\n")
                browser.stdin.flush()
            else:
                result = message
        browser.wait()
        assert browser.returncode == 0, browser.stderr.read()
        return result
    finally:
        timer.cancel()


def lies_inside(box, viewport):
    return box["x"] >= 0 and box["y"] >= 0 and box["x"] + box["w"] <= viewport["w"] and box["y"] + box["h"] <= viewport["h"]


def assert_the_window_is_station_6(window):
    assert window["title"] == "Catch the wave"
    assert window["instructions"].startswith("Tap the water or press Catch wave")
    assert lies_inside(window["window"], window["viewport"])
    assert lies_inside(window["button"], window["viewport"])
    assert window["focused"], "the Catch wave button takes the keys"
    assert window["score"] == "0 / 3 waves caught"


def assert_three_catches_after_an_early_click(played_wave):
    assert played_wave["early"] == "Too early. Try the next wave."
    assert played_wave["scores"][:2] == ["1 / 3 waves caught", "2 / 3 waves caught"]


@needs_chromium
def test_no_page_logs_a_console_error_or_warning(played):
    assert played["problems"] == []


@needs_chromium
def test_in_a_duel_station_6_is_opened_played_with_the_keys_and_counted(played):
    seen = played["duel"]
    assert seen["first"]["next_station"] == 6
    assert seen["cardTitle"] == "Catch the wave"
    assert seen["opened"]["type"] == "station_opened"
    assert seen["opened"]["content"]["kind"] == "catch_the_wave"
    assert_the_window_is_station_6(seen["window"])
    assert_three_catches_after_an_early_click(seen["played"])
    assert seen["done"] == {"type": "station_done", "station": 6}
    assert seen["doneText"] == "Done"
    assert seen["next"]["next_station"] == 1
    assert seen["nextCard"] != "Catch the wave"
    assert "1/3" in seen["otherRows"]


@needs_chromium
def test_in_classic_a_high_performer_finishes_station_6_with_the_mouse(played):
    seen = played["classic"]
    assert seen["workerTasks"] == [6]  # S-197: only the active task
    assert seen["cardTitle"] == "Catch the wave"
    assert_the_window_is_station_6(seen["window"])
    assert_three_catches_after_an_early_click(seen["played"])
    assert (seen["done"]["type"], seen["done"]["station"]) == ("station_done", 6)
    assert 6 not in seen["done"]["task_stations"]
    assert seen["progressAfter"] != seen["progressBefore"]
    assert seen["nextTitle"] != "Catch the wave"


@needs_chromium
def test_in_classic_the_free_rider_cannot_open_station_6(played):
    seen = played["classic"]
    assert seen["freeRiderOpened"] is False
    assert seen["freeRiderWindow"] is False


@needs_chromium
def test_an_open_wave_window_closes_when_a_meeting_starts(played):
    seen = played["classic"]
    assert seen["secondOpened"]["type"] == "station_opened"
    assert seen["meeting"], seen["afterTypes"]
    assert seen["closed"] == {"type": "station_closed", "station": 6}
    assert seen["windowAfterMeeting"] is False
