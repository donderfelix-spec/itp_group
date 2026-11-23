"""M3-3.25 (S-202): the place of an F-sheet in the real game, read from the raw WebSocket messages.

Five guests play Classic in Chromium against the real server, run in this
process (the fixtures and `put` of test_play_classic_task_card_end_to_end.py).
The Free Rider fails a High Performer on the Main Deck, just below the
lecture hall's wall. One High Performer stands near, one far away, one
behind the wall.

- Everybody is told at once who failed (S-159, S-163, S-164).
- The place goes only to the Free Rider, the victim (a ghost now) and the near one.
- The far one is sent the sheet (`classic_sheet`) when he walks into its
  sight, and at the sheet his page shows Report.
- Behind the wall nothing arrives and no Report is shown.

Set FAIL_PLACE_SCREENSHOTS to a folder to keep pictures of the pages.
Skipped when Node, Playwright or Chromium is missing.
"""

import os
from pathlib import Path

import pytest

import test_play_classic_ranges_and_f_key as ranges
from test_play_classic_task_card_end_to_end import (  # noqa: F401 (fixtures)
    needs_chromium,
    no_countdown,
    placeholder_at_every_station,
    quiet_tick,
    server_in_this_process,
)

SHEET_POSITION = {"x": 201.0, "y": 200.0}


@pytest.fixture
def played(server_in_this_process, monkeypatch):
    monkeypatch.setattr(ranges, "BROWSER_SCRIPT", Path(__file__).with_name("play_fail_place_in_sight_in_browser.js"))
    monkeypatch.setattr(ranges, "SCREENSHOTS", os.environ.get("FAIL_PLACE_SCREENSHOTS", ""))
    return ranges.play(server_in_this_process)


@needs_chromium
def test_the_place_of_a_fail_reaches_only_who_sees_it_in_the_real_game(played):
    by_part = {part: label for label, part in played["names"].items()}  # "victim" -> "guest2"
    victim_name = played["fail"][by_part["victim"]]["target_id"]

    for label, message in played["fail"].items():
        assert message["target_id"] == victim_name, label
    for name in ("freeRider", "victim", "near"):
        assert played["fail"][by_part[name]]["position"] == SHEET_POSITION, name
    for name in ("far", "wall"):
        assert "position" not in played["fail"][by_part[name]], name
        assert played["sheets1"][by_part[name]] == [], name

    sheets = played["farReport"]["sheets"]
    assert [(m["sheet_id"], m["position"], m["reported"]) for m in sheets] == [
        (played["fail"][by_part["victim"]]["sheet_id"], SHEET_POSITION, False)
    ]
    assert played["farReport"]["reportShown"] is True

    assert played["wall"]["sheets"] == []
    assert played["wall"]["reportShown"] is False
    assert played["problems"] == []
