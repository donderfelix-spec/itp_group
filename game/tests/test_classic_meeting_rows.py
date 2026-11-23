"""The names in the meeting picture's "Living" and "Dead players" rows (S-215).

`rowLabels` in client/js/classic/meeting.js lays a list of names out in its
rows. When not every name fits (the compact layout has one row), the list
ends in "+N more" instead of cutting names off after a comma, and nothing
reaches past the row's width: a single name left that is still too long
ends in "…". Run in Node with a text width of 7 px per character.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
MEETING_JS = Path(__file__).resolve().parents[1] / "client" / "js" / "classic" / "meeting.js"

pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

SCRIPT = """
const fs = require('fs');
const vm = require('vm');
globalThis.window = globalThis;
vm.runInThisContext(fs.readFileSync(process.argv[1], 'utf8'));
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const measure = (text) => String(text).length * 7;
process.stdout.write(JSON.stringify(cases.map(([players, x, width, rows]) =>
  Game.classicMeeting.rowLabels(players, x, width, rows, measure))));
"""


def lay_out(*cases):
    finished = subprocess.run(
        [NODE, "-e", SCRIPT, str(MEETING_JS)], input=json.dumps(cases),
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(finished.stdout)


def text_of(parts):
    return "".join(part["text"] for part in parts)


def right_end(parts):
    return max(part["x"] + 7 * len(part["text"]) for part in parts)


def test_names_that_fit_are_all_shown_without_a_trailing_comma():
    [parts] = lay_out([["Ana", "Bo", "Cy"], 24, 200, 1])
    assert text_of(parts) == "Ana, Bo, Cy"
    assert [part["playerId"] for part in parts if part["playerId"]] == ["Ana", "Bo", "Cy"]


def test_names_that_do_not_fit_end_in_how_many_more():
    # 126 px hold "Ana, Bo, Cy, " (91 px); "+2 more" needs the room of one name.
    [parts] = lay_out([["Ana", "Bo", "Cy", "Dan", "Eve"], 24, 126, 1])
    assert text_of(parts) == "Ana, Bo, +3 more"
    assert right_end(parts) <= 24 + 126
    assert parts[-1] == {"playerId": None, "text": "+3 more", "x": 24 + 7 * len("Ana, Bo, "), "row": 0}


def test_a_single_long_name_left_ends_in_an_ellipsis_and_stays_in_its_column():
    # The review's case: a 16-character name alone in a 126 px row, four more hidden.
    [parts] = lay_out([["Alexandra1234567", "Bo", "Cy", "Dan", "Eve"], 24, 126, 1])
    text = text_of(parts)
    assert text.endswith("…, +4 more") and text.startswith("Alex")
    assert right_end(parts) <= 24 + 126


def test_more_rows_hold_more_names_and_only_the_last_row_says_how_many_more():
    names = [f"Player{n}" for n in range(8)]  # "Player0, " is 63 px: two per 140 px row
    [parts] = lay_out([names, 0, 140, 3])
    rows = {part["row"] for part in parts}
    assert rows == {0, 1, 2}
    assert text_of(parts).endswith("+3 more")
    assert sum(1 for part in parts if part["playerId"]) + 3 == 8
    assert right_end(parts) <= 140


def test_the_comma_and_the_count_are_not_names():
    # Only name parts carry a playerId, so only they can take the Free Rider's red.
    [parts] = lay_out([["Ana", "Bo", "Cy", "Dan"], 0, 90, 1])
    assert [(part["text"], part["playerId"]) for part in parts] == [("Ana", "Ana"), (", ", None), ("+3 more", None)]
