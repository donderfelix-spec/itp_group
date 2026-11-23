"""M3-4.23: the red emergency button in the centre of the Main Deck, end to end.

Four guests play Classic in Chromium against the real server, run in this
process (the fixtures and `put` of test_play_classic_task_card_end_to_end.py),
with the real 45 seconds of the server's clock (no clock is replaced, so this
test takes about a minute).

- Before 45 s a High Performer standing on the button sees it drawn grey and
  locked (S-216, approved by Felix 2026-11-23; before: no button at all) and no
  "E Emergency"; E opens nothing, and the message sent past the page is
  refused with "The emergency button unlocks in N seconds.", shown at the top.
- After 45 s the button is drawn red and ready at campus.button, (365, 375), radius 11, on
  every page.
- Two units outside the range (use_range, 25) there is no hint and E opens nothing.
- At the edge of the range the button reads "E Emergency"; E (pressed twice
  quickly) opens one emergency meeting for all four players, called by that
  player, and the second press is refused.

Set EMERGENCY_BUTTON_SCREENSHOTS to a folder to keep branch-deck.png and
branch-hint.png (deviceScaleFactor 2). Skipped when Node, Playwright or
Chromium is missing.
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

BROWSER_SCRIPT = Path(__file__).with_name("play_emergency_button_centre_in_browser.js")
SCREENSHOTS = os.environ.get("EMERGENCY_BUTTON_SCREENSHOTS", "")
EMERGENCY_DELAY_SECONDS = 45


def play(base, place=put, screenshots=SCREENSHOTS, label="branch"):
    """Run the browser script, placing players whenever it asks. Returns its last line."""
    browser = subprocess.Popen(
        [NODE, str(BROWSER_SCRIPT), base, screenshots, label], env=node_environment(),
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


@pytest.fixture
def round_played(server_in_this_process):  # noqa: F811 (the imported fixture)
    return play(server_in_this_process)


@needs_chromium
def test_the_emergency_button_is_locked_until_45_s_at_the_deck_centre_and_then_opens_the_meeting(round_played):
    result = round_played
    assert result["button"] == {"x": 365, "y": 375, "r": 11}

    before = result["before"]
    assert before["secondsAfterChecks"] < EMERGENCY_DELAY_SECONDS, before
    assert before["frame"] == {"visible": False, "drawn": True}, before
    assert before["look"] == "locked", before
    assert before["useText"] != "E Emergency"
    assert before["meetings"] == [0, 0, 0, 0]
    assert before["rejection"]["code"] == "emergency_rejected"
    assert before["rejection"]["message"].startswith("The emergency button unlocks in ")
    assert before["shown"] == before["rejection"]["message"]

    unlock = result["unlock"]
    assert EMERGENCY_DELAY_SECONDS - 1 <= unlock["seconds"] <= EMERGENCY_DELAY_SECONDS + 5, unlock
    assert unlock["frame"] == {"visible": True, "drawn": True}
    assert unlock["look"] == "ready", unlock
    assert all(frame == {"visible": True, "drawn": True} for frame in unlock["others"]), unlock["others"]

    assert result["outOfRange"]["useText"] != "E Emergency"
    assert result["outOfRange"]["meetings"] == [0, 0, 0, 0]

    assert result["scene"]["frame"]["drawn"]
    assert result["hint"] == {"useText": "E Emergency", "disabled": False}

    meeting = result["meeting"]
    assert len(meeting) == 4
    for page in meeting:
        assert page["open"] and page["reason"] == "emergency" and page["phase"] == "discussion", page
        assert page["trigger"] == page["caller"]
        assert page["discussions"] >= 1
    assert result["twice"]["errors"] in ([], ["You cannot call an emergency meeting right now."])

    assert result["problems"] == []
