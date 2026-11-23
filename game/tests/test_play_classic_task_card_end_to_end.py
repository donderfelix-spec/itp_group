"""S-143 / S-154 / S-197: the Classic task card follows the real server, end to end.

The play test of the panel (test_play_duel_clock.py) hands the page made-up
`station_done` messages. This test lets the server send them: five guests
play Classic in Chromium against the real server, run in this process so the
test can put players where the tick would after a long walk (as
task_helpers.put does). Then

- every High Performer's card at the top left names its one active task and
  the side panel shows no task card (S-197); the Free Rider's names none
  and says "Fake tasks: stand at a station to look busy." instead;
- one High Performer stands at its active station, presses E, waits and
  clicks "Finish task" in the page; after the server's `station_done` the
  card names the next task, and the group bar moves;
- another High Performer stands next to the Free Rider, who presses F; the
  failed player (a ghost, DESIGN rule 9) still sees its active task.

The browser and this test talk through the browser script's stdin and stdout:
the script prints where players must stand, this test puts them there and
answers "ok". Skipped when Node, Playwright or Chromium is missing.
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

from server.main import app
from server.modes import minigames
from server.modes.placeholder import placeholder
from test_play_campus_detail import NODE, node_environment, playwright_works

BROWSER_SCRIPT = Path(__file__).with_name("play_classic_task_card_end_to_end_in_browser.js")
STATION = {station["id"]: station for station in app.state.campus["stations"]}

needs_chromium = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


@pytest.fixture(autouse=True)
def quiet_tick():
    """Replaces the fixture of the same name in conftest.py: the real tick sends the positions."""


@pytest.fixture(autouse=True)
def no_countdown():
    """Replaces the fixture of the same name in countdown_helpers.py: the real countdown runs."""


@pytest.fixture
def placeholder_at_every_station(monkeypatch):
    """Every station gets the placeholder ("Finish task" after 1 second), so the page can finish it."""
    table = {station: placeholder(game.title) for station, game in minigames.MINIGAMES.items()}
    monkeypatch.setattr(minigames, "MINIGAMES", table)


@pytest.fixture
def server_in_this_process(placeholder_at_every_station):
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


def put(name, where):
    """Place a player as the tick would after a walk: at a station id, "spawn", or [x, y]."""
    if where == "spawn":
        where = [app.state.campus["spawn"]["x"], app.state.campus["spawn"]["y"]]
    elif isinstance(where, int):
        where = [STATION[where]["x"], STATION[where]["y"]]
    walkers = app.state.lobbies.lobby_of(name).walkers
    walkers._walkers[name].position = (float(where[0]), float(where[1]))
    walkers._everybody_needs_news()  # so the tick sends the new position to every page


def play(base):
    """Run the browser script, placing players whenever it asks. Returns its last line."""
    browser = subprocess.Popen(
        [NODE, str(BROWSER_SCRIPT), base], env=node_environment(),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    timer = threading.Timer(180, browser.kill)
    timer.start()
    try:
        result = None
        for line in browser.stdout:
            message = json.loads(line)
            if "put" in message:
                for name, where in message["put"]:
                    put(name, where)
                browser.stdin.write("ok\n")
                browser.stdin.flush()
            else:
                result = message
        browser.wait()
        assert browser.returncode == 0, browser.stderr.read()
        return result
    finally:
        timer.cancel()


@pytest.fixture
def played(server_in_this_process):
    return play(server_in_this_process)


@needs_chromium
def test_classic_task_card_follows_the_real_server(played):
    pages = played["pages"]
    assert len(pages) == 5
    assert [page["role"] for page in pages].count("FR") == 1
    # S-197: the side panel shows no task card; the card at the top left of
    # the map names the own one active task, and nothing for the Free Rider.
    for page in pages:
        assert page["cardLines"] == [], page
        if page["role"] == "HP":
            assert len(page["tasks"]) == 1, page
            assert page["top"] == STATION[page["tasks"][0]]["name"] and page["note"] is None, page
        else:
            assert page["tasks"] == [] and page["top"] is None, page
            assert page["note"] == "Fake tasks: stand at a station to look busy.", page

    # A High Performer finished its active station through the page.
    done = played["done"]
    assert done["stationDone"]["station"] == done["station"] == done["tasksBefore"][0]
    following = done["stationDone"]["task_stations"]
    assert len(following) == 1 and following[0] != done["station"]
    # The card at the top left follows the next task; the panel stays empty.
    assert done["topBefore"] == STATION[done["station"]]["name"]
    assert done["topAfter"] == STATION[following[0]]["name"]
    assert done["cardAfter"] == [] and done["itemsAfter"] == []
    assert done["progressBefore"] == "0% complete"
    assert done["progressAfter"] != done["progressBefore"]
    assert done["fillAfter"] > done["fillBefore"]

    # A High Performer failed by the Free Rider keeps its active task (a ghost, rule 9).
    ghost = played["ghost"]
    assert ghost["failed"]
    assert ghost["topAfter"] == STATION[ghost["tasks"][0]]["name"]

    assert played["problems"] == []
