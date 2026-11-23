"""The Classic action buttons (M3-3.26, S-195).

- The Free Rider's main button is always "F Let fail" and never turns into
  anything else. Only F lets fail (Q no longer does).
  - While it charges (the 15 s cooldown): no seconds, switched off, and a
    darker grey fills it from left to right (`fail-charging`, `--fail-fill`).
  - Charged with nobody in range: all of it grey, switched off.
  - Charged with a victim in range: switched on, yellow like "E Use".
  A screen reader hears the state through the button's `aria-label`.
- The Free Rider's E actions have their own button, shown only while E would
  do one of them: "E Emergency" at the red button, "E Hide" at a hiding
  object, "E Leave hiding" while hidden.
- A High Performer keeps "E Use" / "E Emergency" and gets no second button.
- Report reads "R Report" for both roles.

The plain helpers of client/js/classic/fail-button.js run in Node on their
own; the page with world.js, round.js and main.js runs in
tests/classic_cleanup_in_node.js. Colours and places are checked in the
browser by tests/test_play_action_buttons.py.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

from test_classic_report_and_fail_ranges import free_rider_in_a_round
from test_classic_round_end_cleanup import NODE, SHEET, needs_node, run_page

FAIL_BUTTON = Path(__file__).resolve().parents[1] / "client" / "js" / "classic" / "fail-button.js"
CAMPUS = json.loads((Path(__file__).resolve().parents[1] / "client" / "js" / "world" / "campus.json").read_text())
HEDGE_SPOT = CAMPUS["hiding_spots"][0]
# The server's word during the cooldown: 10 of the 15 seconds still to go.
COOLDOWN = {"type": "classic_fail_status", "available": False, "in_range": True, "cooldown_until": 110, "server_time": 100}
CHARGED_NOBODY_NEAR = {"type": "classic_fail_status", "available": False, "in_range": False, "cooldown_until": None, "server_time": 100}


def helper(expression):
    script = f"""
      const ui = require({json.dumps(str(FAIL_BUTTON))});
      process.stdout.write(JSON.stringify({expression}));
    """
    return json.loads(subprocess.run([NODE, "-e", script], check=True, capture_output=True, text=True).stdout)


def fill(look):
    return float(look["useButtonFill"].rstrip("%"))


def stand(x, y):
    return [["receive", {"type": "positions", "players": [{"name": "Ana", "x": x, "y": y}]}], ["wait", 400]]


# The plain helpers


@needs_node
def test_the_button_text_has_the_key_first():
    assert helper("ui.TEXT") == "F Let fail"


@needs_node
@pytest.mark.parametrize("seconds,in_range,label", [
    (0, True, "Let fail"), (None, True, "Let fail"), (0, False, "Let fail, nobody in range"),
    (1, True, "Let fail, ready in 1 second"), (12, False, "Let fail, ready in 12 seconds"),
])
def test_a_screen_reader_hears_the_state(seconds, in_range, label):
    assert helper(f"ui.spokenLabel({json.dumps(seconds)}, {json.dumps(in_range)})") == label


# The three looks of "F Let fail"


@needs_node
def test_ready_with_a_victim_in_range_it_is_on():
    look = run_page(free_rider_in_a_round() + [["look"]])["looks"][0]
    assert look["useButtonText"] == "F Let fail"
    assert look["useButtonDisabled"] is False
    assert look["useButtonCharging"] is False
    assert look["useButtonLabel"] == "Let fail"
    assert fill(look) == 100


@needs_node
def test_charged_with_nobody_in_range_it_is_all_grey_and_off():
    look = run_page(free_rider_in_a_round(CHARGED_NOBODY_NEAR) + [["look"]])["looks"][0]
    assert look["useButtonText"] == "F Let fail"
    assert look["useButtonDisabled"] is True
    assert look["useButtonCharging"] is False
    assert look["useButtonLabel"] == "Let fail, nobody in range"
    assert fill(look) == 100


@needs_node
def test_in_the_cooldown_the_text_has_no_digits_and_the_grey_fill_runs():
    steps = free_rider_in_a_round(COOLDOWN) + [["look"], ["wait", 5000], ["look"]]
    early, later = run_page(steps)["looks"]
    for look in (early, later):
        assert look["useButtonText"] == "F Let fail"
        assert not re.search(r"\d", look["useButtonText"])
        assert look["useButtonDisabled"] is True
        assert look["useButtonCharging"] is True
    # About 10 s and 5 s left: a third and two thirds of the charge.
    assert 30 <= fill(early) < fill(later) <= 70
    assert early["useButtonLabel"] == "Let fail, ready in 10 seconds"
    assert later["useButtonLabel"] == "Let fail, ready in 5 seconds"


@needs_node
def test_at_the_end_of_the_cooldown_it_is_charged_and_on_again():
    steps = free_rider_in_a_round(COOLDOWN) + [["wait", 10500], ["look"]]
    look = run_page(steps)["looks"][0]
    assert look["useButtonText"] == "F Let fail"
    assert look["useButtonCharging"] is False
    assert look["useButtonDisabled"] is False
    assert look["useButtonLabel"] == "Let fail"
    assert fill(look) == 100


# The Free Rider's own E button


@needs_node
def test_away_from_everything_the_free_rider_has_no_e_button():
    look = run_page(free_rider_in_a_round() + [["look"]])["looks"][0]
    assert look["freeRiderEButtonText"] is None


@needs_node
def test_at_a_hiding_object_e_hide_appears_and_goes_again():
    steps = free_rider_in_a_round() + stand(HEDGE_SPOT["x"], HEDGE_SPOT["y"] + 20) + [["look"]] + stand(120, 120) + [["look"]]
    near, away = run_page(steps)["looks"]
    assert near["freeRiderEButtonText"] == "E Hide"
    assert near["freeRiderEButtonDisabled"] is False
    assert near["useButtonText"] == "F Let fail"  # the main button stays
    assert away["freeRiderEButtonText"] is None


@needs_node
def test_hidden_the_e_button_reads_e_leave_hiding_and_its_click_sends_it():
    steps = free_rider_in_a_round() + stand(HEDGE_SPOT["x"], HEDGE_SPOT["y"]) + [
        ["receive", {"type": "classic_hiding", "hidden": True}], ["wait", 50], ["look"], ["clickFreeRiderEButton"],
    ]
    result = run_page(steps)
    assert result["looks"][0]["freeRiderEButtonText"] == "E Leave hiding"
    assert [m for m in result["sent"] if m["type"] in ("hide", "leave_hiding")] == [{"type": "leave_hiding"}]


@needs_node
def test_a_click_on_e_hide_sends_hide_and_the_main_button_does_not():
    steps = free_rider_in_a_round() + stand(HEDGE_SPOT["x"], HEDGE_SPOT["y"] + 20) + [
        ["clickFreeRiderEButton"], ["clickUseButton"],
    ]
    sent = run_page(steps)["sent"]
    assert [m for m in sent if m["type"] == "hide"] == [{"type": "hide"}]
    # The main button only lets fail (nobody is in range here, so nothing).
    assert [m for m in sent if m["type"] in ("emergency", "leave_hiding")] == []


@needs_node
def test_a_high_performer_has_no_second_button_and_no_fail_label():
    steps = free_rider_in_a_round(role="HP") + stand(HEDGE_SPOT["x"], HEDGE_SPOT["y"] + 20) + [["look"]]
    look = run_page(steps)["looks"][0]
    assert look["useButtonText"] == "E Use"
    assert look["useButtonLabel"] is None
    assert look["freeRiderEButtonText"] is None


# Report


@needs_node
@pytest.mark.parametrize("role", ["FR", "HP"])
def test_report_reads_r_report_for_both_roles(role):
    steps = free_rider_in_a_round(role=role) + [["receive", SHEET]] + stand(SHEET["position"]["x"], SHEET["position"]["y"]) + [["look"]]
    look = run_page(steps)["looks"][0]
    assert look["reportButtonShown"] is True
    assert look["reportButtonText"] == "R Report"
