"""The real "Hidden" of M3-1.4 (S-135) in the Classic panel of M2-2.11 (S-143).

Five guests play Classic in Chromium against the real server, run in this
process so the test can put the Free Rider in a hiding spot as the tick would
after a walk (as test_play_classic_task_card_end_to_end.py does). Then on the
Free Rider's own page:

- "Hidden" is inside the Classic panel, under the group progress bar and
  above the "Players" heading;
- at 1280 x 800 and 1024 x 700 it is on the screen without scrolling, and at
  320 x 640 it still comes before "Players";
- High Performers never see it, also when one stands in a hiding spot;
- it goes when the Free Rider steps out of the spot.

Skipped when Node, Playwright or Chromium is missing. A screenshot of the
Free Rider while hidden (1280 x 800) goes to CLASSIC_HIDDEN_SCREENSHOT, and
the measurements to CLASSIC_HIDDEN_RESULT, if set.
"""

import json
import os
from pathlib import Path

import pytest

from server.main import app
from test_play_campus_detail import playwright_works
from test_play_classic_task_card_end_to_end import (  # noqa: F401  (fixtures)
    no_countdown,
    placeholder_at_every_station,
    put,
    quiet_tick,
    server_in_this_process,
)
import test_play_classic_task_card_end_to_end as end_to_end

BROWSER_SCRIPT = Path(__file__).with_name("play_classic_hidden_in_panel_in_browser.js")
SPOTS = app.state.campus["hiding_spots"]
PLACES = {
    "spot": [SPOTS[0]["x"], SPOTS[0]["y"]],
    "spot2": [SPOTS[1]["x"], SPOTS[1]["y"]],
    # Just outside the first spot, to the right (as test_classic_hiding_hint.py does).
    "outside": [SPOTS[0]["x"] + SPOTS[0]["r"] + 1, SPOTS[0]["y"]],
}
SCREENSHOT = os.environ.get("CLASSIC_HIDDEN_SCREENSHOT", "")
RESULT = os.environ.get("CLASSIC_HIDDEN_RESULT", "")  # the measurements, as JSON, if set

needs_chromium = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


def put_named_place(name, where):
    put(name, PLACES[where])


@pytest.fixture
def played(server_in_this_process, monkeypatch):
    # The browser script names places ("spot", "outside"); the shared runner puts them.
    monkeypatch.setattr(end_to_end, "BROWSER_SCRIPT", BROWSER_SCRIPT)
    monkeypatch.setattr(end_to_end, "put", put_named_place)
    if SCREENSHOT:  # the browser script reads it from its environment
        Path(SCREENSHOT).parent.mkdir(parents=True, exist_ok=True)
    result = end_to_end.play(server_in_this_process)
    if RESULT:
        Path(RESULT).write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def in_panel_under_bar_before_players(measured):
    hint, bar, panel, players = measured["hint"], measured["bar"], measured["panel"], measured["players"]
    assert measured["text"] == "Hidden"
    assert measured["parentId"] == "classic-progress"
    assert hint["height"] > 0
    assert hint["top"] >= bar["bottom"], measured
    assert panel["top"] <= hint["top"] and hint["bottom"] <= panel["bottom"], measured
    assert players is not None and hint["bottom"] <= players["top"], measured


@needs_chromium
def test_hidden_sits_in_the_classic_panel_and_follows_the_spot(played):
    assert played["roles"].count("FR") == 1
    assert played["frShown"], "the hidden Free Rider never saw 'Hidden'"

    for size in ("1280x800", "1024x700", "320x640"):
        measured = played["hidden"][size]
        assert measured["shown"], (size, measured)
        in_panel_under_bar_before_players(measured)
    for size in ("1280x800", "1024x700"):
        measured = played["hidden"][size]
        assert measured["scrolled"] == [], (size, measured)
        assert 0 <= measured["hint"]["top"] and measured["hint"]["bottom"] <= measured["viewport"]["height"], (size, measured)
        assert measured["onTop"], (size, measured)

    assert played["hpPages"] == [False] * 4
    assert played["hpInSpot"] is False
    assert played["goneAfterLeaving"] and played["afterLeaving"] is False
    assert played["problems"] == []
