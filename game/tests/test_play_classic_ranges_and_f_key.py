"""M3-4.25 to M3-4.28 (S-180, S-181): the new ranges and key F in the real game.

Four guests play Classic in Chromium against the real server, run in this
process (the fixtures and `put` of test_play_classic_task_card_end_to_end.py),
two pages at 1280 x 800 and two at 1024 x 700.

- The Free Rider 21 map units from a High Performer: the server says "not in
  range" and F fails nobody.
- At 20 map units: the button says only "Let fail" and F fails the victim.
- A High Performer 8.5 map units from the F-sheet sees no Report button.
- The Free Rider 8 map units from the sheet sees Report; R starts the meeting
  for everybody, as a report by the Free Rider.
- No page scrolls sideways or downwards with the larger sheet on the map.

Set CLASSIC_RANGES_SCREENSHOTS to a folder to keep pictures of every page.
Skipped when Node, Playwright or Chromium is missing.
"""

import json
import os
import subprocess
import threading
from pathlib import Path

import pytest

from test_play_campus_detail import NODE, node_environment
from test_play_classic_task_card_end_to_end import (  # noqa: F401 (fixtures)
    needs_chromium,
    no_countdown,
    placeholder_at_every_station,
    put,
    quiet_tick,
    server_in_this_process,
)

BROWSER_SCRIPT = Path(__file__).with_name("play_classic_ranges_and_f_key_in_browser.js")
SCREENSHOTS = os.environ.get("CLASSIC_RANGES_SCREENSHOTS", "")


def play(base):
    """Run the browser script, placing players whenever it asks. Returns its last line."""
    browser = subprocess.Popen(
        [NODE, str(BROWSER_SCRIPT), base, SCREENSHOTS], env=node_environment(),
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
def test_ranges_and_f_key_in_the_real_game(played):
    assert sorted(played["roles"].values()) == ["FR", "HP", "HP", "HP"]

    # Rejected just outside the fail range: nothing happens on F.
    assert played["fail21"]["status"]["in_range"] is False
    assert played["fail21"]["failed"] is False
    assert played["fail21"]["buttons"]["useDisabled"] is True

    # Accepted at exactly 20: "Let fail" without a tile count, F fails.
    assert played["fail20"]["buttonsBefore"]["useText"] == "Let fail"
    assert played["fail20"]["buttonsBefore"]["useDisabled"] is False
    assert played["fail20"]["failed"] is True

    # Report: hidden at 8.5, shown at 8, also for the Free Rider.
    assert played["report85"]["reportShown"] is False
    assert played["report8"]["buttonsBefore"]["reportShown"] is True
    assert played["report8"]["meetingReason"] == "report"
    assert played["report8"]["trigger"] is True

    for label, box in played["sheetBox"].items():
        assert box["scrollWidth"] <= box["viewport"]["w"], label
        assert box["scrollHeight"] <= box["viewport"]["h"], label
    assert played["problems"] == []
