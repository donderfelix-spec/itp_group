"""The Classic meeting window and the end screen in Chromium (Felix, 2026-11-22).

Felix saw two things on the live site:

1. The vote buttons jumped: each voter's character was put into the button
   of their target, so the buttons grew and the row wrapped anew whenever a
   vote came, changed or was taken back. At 1280x800 the window was cut off
   at the bottom ("Message" and "Send" stuck out).
2. A player who is not the host saw a grey "New Round" on the end screen.

What is checked here, at 1280x800, 1024x700 (device pixel ratio 2) and 320x640:
- the boxes of all vote buttons (and of the window, the message field and
  Send) are pixel-identical before and after votes arrive, change and are
  withdrawn, with 4 and with 8 living players, one with a 16-letter name;
- all vote buttons have the same size; a long name ends in "…" and the
  whole name is in the title; no voter characters are drawn in a button;
- the count field shows how many voted for that player, and the label and
  title who ("Bo — votes: Ana, Cy"), read from `vote_targets` as sent;
- the window, the message field, Send, the Skip row and every vote button
  lie inside the viewport with 8 living players, in a vote and in a report
  discussion (votes, Skip and chat at once), and neither the window nor the
  page has to scroll;
- the canvas is drawn with as many pixels as it has on screen (sharp);
- the host sees "New Round"; a non-host does not (not in the layout), and
  "Back to the lobby" then stands alone in the middle of its row; a host
  change while the end screen is open shows or hides it.

The page comes from the real server; its WebSocket is answered by the
browser script (tests/meeting_window_and_end_screen_in_browser.js) with
the messages a server would send. Skipped when Node, Playwright or Chromium
is missing. Screenshots go to the folder in MEETING_WINDOW_SCREENSHOTS, if set.
"""

import json
import math
import os
import subprocess
from pathlib import Path

import pytest

from test_play_campus_detail import NODE, node_environment, playwright_works, running_server  # noqa: F401

BROWSER_SCRIPT = Path(__file__).with_name("meeting_window_and_end_screen_in_browser.js")
SCREENSHOTS = os.environ.get("MEETING_WINDOW_SCREENSHOTS")
VIEWPORTS = ["1280x800", "1024x700", "320x640"]
LONG_NAME = "Maximilianaaaaaa"

needs_chromium = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


@pytest.fixture(scope="module")
def played(running_server):  # noqa: F811 (the fixture imported above)
    command = [NODE, str(BROWSER_SCRIPT), running_server]
    if SCREENSHOTS:
        Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
        command.append(SCREENSHOTS)
    finished = subprocess.run(
        command, env=node_environment(), capture_output=True, text=True, timeout=300, check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def vote_steps(played):
    """(viewport, "votes4" or "votes8", the steps) for every vote sequence played."""
    for viewport in VIEWPORTS:
        for players in ("votes4", "votes8"):
            yield viewport, players, played["viewports"][viewport][players]


def expected_label(target, targets):
    voters = sorted(voter for voter, chosen in targets.items() if chosen == target)
    return (str(len(voters)), f"{target} — votes: {', '.join(voters)}" if voters else f"{target} — no votes")


def inside(box, outer):
    return (box["left"] >= outer["left"] - 0.5 and box["top"] >= outer["top"] - 0.5
            and box["right"] <= outer["right"] + 0.5 and box["bottom"] <= outer["bottom"] + 0.5)


@needs_chromium
def test_no_page_logs_a_console_error_or_warning(played):
    assert played["console"] == []


@needs_chromium
def test_every_viewport_was_looked_at(played):
    assert sorted(played["viewports"]) == sorted(VIEWPORTS)
    for _, players, steps in vote_steps(played):
        assert len(steps) == 7, players
        assert len(steps[0]["buttons"]) == (4 if players == "votes4" else 8)


# ---- (a) Nothing moves when votes come, change or go ------------------------------


@needs_chromium
def test_the_vote_buttons_never_move_or_change_size_when_votes_change(played):
    for viewport, players, steps in vote_steps(played):
        first = steps[0]["boxes"]
        for step in steps[1:]:
            assert step["boxes"] == first, (viewport, players, step["targets"])


@needs_chromium
def test_every_vote_button_has_the_same_size(played):
    for viewport, players, steps in vote_steps(played):
        sizes = {(box[2], box[3]) for box in steps[0]["boxes"]["buttons"]}
        assert len(sizes) == 1, (viewport, players, sizes)
        width, height = sizes.pop()
        assert width >= 120 and height >= 40, (viewport, width, height)


@needs_chromium
def test_the_grid_has_four_columns_wide_and_two_narrow(played):
    for viewport, columns in (("1280x800", 4), ("1024x700", 4), ("320x640", 2)):
        boxes = played["viewports"][viewport]["votes8"][0]["boxes"]["buttons"]
        assert len({box[0] for box in boxes}) == columns, viewport


@needs_chromium
def test_no_voter_character_is_drawn_in_a_vote_button(played):
    for viewport, players, steps in vote_steps(played):
        for step in steps:
            assert all(button["voterIcons"] == 0 for button in step["buttons"]), (viewport, players)


@needs_chromium
def test_the_count_and_label_show_who_voted_for_whom(played):
    for viewport, players, steps in vote_steps(played):
        for step in steps:
            for button in step["buttons"]:
                count, label = expected_label(button["target"], step["targets"])
                assert (button["count"], button["label"], button["title"]) == (count, label, label), (
                    viewport, players, step["targets"])


@needs_chromium
def test_the_own_target_stays_highlighted(played):
    for viewport, players, steps in vote_steps(played):
        for step in steps:
            selected = [button["target"] for button in step["buttons"] if button["selected"]]
            own = step["targets"].get("Ana")
            assert selected == ([own] if own else []), (viewport, players, step["targets"])


@needs_chromium
def test_a_long_name_is_cut_with_an_ellipsis_and_whole_in_the_title(played):
    for viewport in VIEWPORTS:
        buttons = played["viewports"][viewport]["votes8"][0]["buttons"]
        long_one = next(button for button in buttons if button["target"] == LONG_NAME)
        assert long_one["nameCut"] is True, viewport
        assert long_one["nameEllipsis"] == "ellipsis"
        assert long_one["title"].startswith(LONG_NAME + " — ")
        assert all(button["nameCut"] is False for button in buttons if button["target"] != LONG_NAME), viewport


# ---- (b) The window fits the viewport --------------------------------------------


@needs_chromium
@pytest.mark.parametrize("viewport", VIEWPORTS)
@pytest.mark.parametrize("situation", ["voting8", "report8"])
def test_the_whole_meeting_window_fits_the_viewport(played, viewport, situation):
    fit = played["viewports"][viewport]["fit"][situation]
    screen = {"left": 0, "top": 0, "right": fit["viewport"]["width"], "bottom": fit["viewport"]["height"]}
    assert inside(fit["window"], screen), fit["window"]
    assert fit["skip"] is not None
    for part in [fit["input"], fit["send"], fit["skip"], *fit["buttons"]]:
        assert inside(part, fit["window"]), part
        assert inside(part, screen), part
    assert len(fit["buttons"]) == 8
    assert fit["windowScrolls"] is False
    assert fit["pageScrollY"] == 0


@needs_chromium
@pytest.mark.parametrize("viewport", VIEWPORTS)
def test_the_canvas_is_drawn_sharp_at_its_size_on_screen(played, viewport):
    for key in ("canvas", "canvasReport"):
        canvas = played["viewports"][viewport][key]
        assert canvas["width"] == math.floor(canvas["clientWidth"] * canvas["ratio"]), canvas
        assert canvas["height"] == math.floor(canvas["clientHeight"] * canvas["ratio"]), canvas
        # The smallest size the window gives it (style.css: 150 px with its border).
        assert canvas["clientHeight"] >= 140, canvas


# ---- (c) "New Round" only for the host -------------------------------------------


@needs_chromium
@pytest.mark.parametrize("viewport", VIEWPORTS)
def test_only_the_host_sees_new_round(played, viewport):
    end = played["viewports"][viewport]["end"]
    host_sees = {"endScreen": True, "newRoundHidden": False, "newRoundInLayout": True,
                 "hint": "Start another round with the same lobby."}
    nobody_else = {"endScreen": True, "newRoundHidden": True, "newRoundInLayout": False, "newRoundWidth": 0,
                   "hint": "The host can start the next round.", "backCentreOffset": 0}
    assert {key: end["host"][key] for key in host_sees} == host_sees
    assert end["host"]["newRoundWidth"] > 0
    assert {key: end["guest"][key] for key in nobody_else} == nobody_else


@needs_chromium
@pytest.mark.parametrize("viewport", VIEWPORTS)
def test_new_round_follows_a_host_change_while_the_end_screen_is_open(played, viewport):
    end = played["viewports"][viewport]["end"]
    assert end["lostHost"]["newRoundInLayout"] is False
    assert end["lostHost"]["hint"] == "The host can start the next round."
    assert end["becameHostAgain"]["newRoundInLayout"] is True
    assert end["becameHostAgain"]["hint"] == "Start another round with the same lobby."
