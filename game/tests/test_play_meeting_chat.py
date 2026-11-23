"""How many chat messages the Classic meeting window shows (S-210), in Chromium.

Found on 2026-11-23: at 1280x800 the discussion chat of a report meeting
(five players, one dead) showed only the newest two messages. Every message
had a fixed slot of 38 px (room for two lines), and the chat always started
below three reserved rows of the player lists.

What is checked here, at 1280x800, 1024x700, 1366x768, 320x640 and 1280x560
(compact), in the discussion of a report meeting (4 living, 1 dead) and of an
emergency meeting (5 living), both with the vote buttons shown:
- with 8 short messages at 1280x800 at least five are drawn, the newest ones,
  in their order, the newest lowest;
- a one-line message takes one line, a mix of one- and two-line messages
  never overlaps and never leaves the canvas; no message has more than two
  lines, and a longer one ends in "…";
- with both player lists on one row the chat starts higher than with three
  rows; with three rows it starts where it always did; the lists never reach
  into the chat;
- the chat stays where it is when only the messages and the clock change;
- the compact layout (canvas under 340 px) keeps its positions;
- no size shows fewer messages than the old fixed slots did, and 1024x700
  and 1366x768 show more.

The page comes from the real server; its WebSocket is answered by the
browser script (tests/meeting_chat_in_browser.js), which records what the
meeting canvas draws. Skipped when Node, Playwright or Chromium is missing.
Screenshots go to the folder in MEETING_CHAT_SCREENSHOTS, if set.
"""

import json
import math
import os
import subprocess
from pathlib import Path

import pytest

from test_play_campus_detail import NODE, node_environment, playwright_works, running_server  # noqa: F401

BROWSER_SCRIPT = Path(__file__).with_name("meeting_chat_in_browser.js")
SCREENSHOTS = os.environ.get("MEETING_CHAT_SCREENSHOTS")
VIEWPORTS = ["1280x800", "1024x700", "1366x768", "320x640", "1280x560"]
REASONS = ["report", "emergency"]
MESSAGE_SETS = ["short8", "mixed8", "mixed9"]
# From client/js/classic/meeting.js.
COMPACT_BELOW = 340
COMPACT_DIVIDER = 134 - 12
COMPACT_FIRST_MESSAGE = 134 + 12
THREE_ROW_DIVIDER = 230 - 12
LINE = 18
# A line's text reaches this far above and below its baseline (14 px font).
ASCENT = 14
DESCENT = 5

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


def situations(played, sets=MESSAGE_SETS):
    for reason in REASONS:
        for messages in sets:
            for viewport in VIEWPORTS:
                key = f"{reason} {messages} {viewport}"
                yield key, played["seen"][key]


def old_slot_count(seen):
    """How many messages the old fixed 38 px slots showed on this canvas."""
    compact = seen["canvas"]["height"] < COMPACT_BELOW
    first = COMPACT_FIRST_MESSAGE if compact else THREE_ROW_DIVIDER + 12 + 40
    return min(len(seen["sent"]), max(1, math.floor((seen["canvas"]["height"] - first + 14) / 38)))


@needs_chromium
def test_no_page_logs_a_console_error_or_warning(played):
    assert played["console"] == []


@needs_chromium
def test_eight_short_messages_at_1280x800_show_at_least_five_newest_lowest(played):
    seen = played["seen"]["report short8 1280x800"]
    shown = seen["messages"]
    assert len(shown) >= 5, len(shown)
    assert [f"{m['name']}: {m['lines'][0]['text']}" for m in shown] == seen["sent"][-len(shown):]
    assert all(len(m["lines"]) == 1 for m in shown)
    assert [m["y"] for m in shown] == sorted(m["y"] for m in shown)
    assert shown[-1]["y"] == max(m["y"] for m in shown)


@needs_chromium
def test_the_newest_messages_are_shown_in_their_order(played):
    for key, seen in situations(played):
        shown = seen["messages"]
        assert shown, key
        newest = seen["sent"][-len(shown):]
        assert [m["name"] for m in shown] == [text.split(": ", 1)[0] for text in newest], key
        for message, sent in zip(shown, newest):
            first_line = message["lines"][0]["text"].removesuffix(" …")
            assert sent.split(": ", 1)[1].startswith(first_line), (key, sent)


@needs_chromium
def test_a_one_line_message_takes_one_line(played):
    for key, seen in situations(played):
        for above, below in zip(seen["messages"], seen["messages"][1:]):
            assert below["y"] - above["y"] == len(above["lines"]) * LINE + 2, key


@needs_chromium
def test_messages_never_overlap_and_never_leave_the_chat(played):
    for key, seen in situations(played):
        shown = seen["messages"]
        top = seen["heading"]["y"] + DESCENT if seen["heading"] else seen["divider"]
        for message in shown:
            assert 1 <= len(message["lines"]) <= 2, key
            for index, line in enumerate(message["lines"]):
                assert line["y"] == message["y"] + index * LINE, key
                # A line is never wider than the chat, unless it is one word.
                if " " in line["text"].removesuffix(" …"):
                    assert seen["textX"] + line["width"] <= seen["canvas"]["width"] - 24 + 0.5, (key, line)
        assert shown[0]["y"] - ASCENT >= top, key
        for above, below in zip(shown, shown[1:]):
            assert above["lines"][-1]["y"] + DESCENT <= below["y"] - ASCENT, key
        # The newest message is drawn whole (a canvas of 146 px has room for one only).
        assert shown[-1]["lines"][-1]["y"] + DESCENT <= seen["canvas"]["height"] or len(shown) == 1, key


@needs_chromium
def test_a_message_longer_than_two_lines_ends_in_an_ellipsis(played):
    cut = 0
    for key, seen in situations(played, ["mixed8"]):
        for message, sent in zip(seen["messages"], seen["sent"][-len(seen["messages"]):]):
            whole = " ".join(line["text"] for line in message["lines"])
            if whole.endswith(" …"):
                cut += 1
                assert len(message["lines"]) == 2, key
                assert sent.split(": ", 1)[1].startswith(whole.removesuffix(" …")), key
            else:
                assert whole == sent.split(": ", 1)[1], key
    assert cut > 0  # the 200-character message is in the mix


@needs_chromium
def test_the_chat_starts_higher_when_the_lists_need_one_row(played):
    roomy = 0
    for viewport in VIEWPORTS:
        one = played["seen"][f"rows1 {viewport}"]
        three = played["seen"][f"rows3 {viewport}"]
        assert one["canvas"] == three["canvas"], viewport
        if three["canvas"]["height"] < COMPACT_BELOW:
            continue
        roomy += 1
        assert three["divider"] == THREE_ROW_DIVIDER, viewport
        assert one["divider"] == THREE_ROW_DIVIDER - 2 * LINE, viewport
        assert len(one["messages"]) > len(three["messages"]), viewport
    assert roomy > 0


@needs_chromium
def test_the_player_lists_never_reach_into_the_chat(played):
    for key, seen in played["seen"].items():
        assert all(text["y"] + DESCENT <= seen["divider"] for text in seen["listTexts"]), key


@needs_chromium
def test_the_chat_stays_put_when_only_messages_and_clock_change(played):
    for reason in REASONS:
        for viewport in VIEWPORTS:
            before = played["seen"][f"{reason} mixed8 {viewport}"]
            after = played["seen"][f"{reason} mixed9 {viewport}"]
            assert before["canvas"] == after["canvas"]
            assert before["divider"] == after["divider"], (reason, viewport)
            assert before["messages"][0]["y"] == after["messages"][0]["y"], (reason, viewport)


@needs_chromium
def test_the_compact_layout_keeps_its_positions(played):
    compact = [(key, seen) for key, seen in played["seen"].items() if seen["canvas"]["height"] < COMPACT_BELOW]
    assert any(key.endswith("1280x560") for key, _ in compact)
    for key, seen in compact:
        assert seen["divider"] == COMPACT_DIVIDER, key
        assert seen["heading"] is None, key
        assert seen["messages"][0]["y"] == COMPACT_FIRST_MESSAGE, key


@needs_chromium
def test_no_size_shows_fewer_messages_than_the_old_slots(played):
    for key, seen in played["seen"].items():
        assert len(seen["messages"]) >= old_slot_count(seen), key


@needs_chromium
@pytest.mark.parametrize("viewport", ["1280x800", "1024x700", "1366x768"])
def test_the_usual_windows_show_more_messages_than_before(played, viewport):
    for reason in REASONS:
        seen = played["seen"][f"{reason} short8 {viewport}"]
        assert len(seen["messages"]) > old_slot_count(seen), (reason, viewport)
