"""The Classic action buttons in four Chromium pages (M3-3.26, S-195).

Four guests play Classic against the real server with its real tick (the
harness of test_play_hiding.py: the server runs in this process, so the test
can put players and set the server's clock forward). One Free Rider, three
High Performers. On the Free Rider's page:

1. Alone on the deck: "F Let fail", grey (all of it, charged) and off.
2. A High Performer 10 units away: "F Let fail", yellow and on, like "E Use".
3. At the red button with a High Performer beside him he presses F (Q does
   nothing): the High Performer fails, the button charges (grey, filling,
   no digits), the second button "E Emergency" and "R Report" appear above
   it. No two buttons and no button and the task card overlap, at
   1280 x 800, 1024 x 700 and 320 x 640, and "F Let fail" keeps its place.
4. Halfway through the cooldown, away from everything: the fill is about half.
5. Beside the hedge: the second button reads "E Hide"; after E, "E Leave hiding".
6. A High Performer at the F-sheet sees "R Report" and never a second button.
No page logs an error or a warning.

Skipped when Node, Playwright or Chromium is missing. Screenshots go to the
folder in ACTION_BUTTON_SCREENSHOTS, if that is set.
"""

import os
import re
import time
from pathlib import Path

import pytest

from server.main import app
from test_play_hiding import (  # noqa: F401  (fixtures)
    Browser,
    failed,
    lobby_of,
    playwright_works,
    position,
    press_hide,
    put,
    quiet_tick,
    server,
    standing_still,
    start_round,
    wait_until,
)

pytestmark = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")

CAMPUS = app.state.campus
BUTTON = CAMPUS["button"]
HEDGE_SPOT = CAMPUS["hiding_spots"][0]
LABELS = ["P0", "P1", "P2", "P3"]
SCREENSHOTS = os.environ.get("ACTION_BUTTON_SCREENSHOTS")
# Open deck, far from the red button, the stations and the hiding spots.
AWAY = (470.0, 330.0)
# Beside the red button (within 25 units) and, for the fail, a victim 6 units to the right.
AT_THE_BUTTON = (float(BUTTON["x"]) + 15.0, float(BUTTON["y"]) + 5.0)
FAR = [(120.0, 300.0), (130.0, 420.0), (300.0, 470.0)]

BUTTONS = """(() => {
  const box = (selector) => {
    const element = document.querySelector(selector);
    if (!element || element.hidden) return null;
    const r = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return { text: element.textContent, disabled: element.disabled === true,
             label: element.getAttribute('aria-label'),
             charging: element.classList.contains('fail-charging'),
             fill: element.style.getPropertyValue('--fail-fill'),
             colour: style.backgroundColor, image: style.backgroundImage,
             box: [r.left, r.top, r.width, r.height] };
  };
  return { main: box('.use-button'), e: box('.free-rider-e-button'), report: box('.report-button'),
           card: box('.task-card') };
})()"""


def buttons(browser, label):
    return browser.js(label, BUTTONS)


def overlap(a, b):
    """True when the two boxes [left, top, width, height] share any area."""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def shot(browser, label, name):
    if SCREENSHOTS:
        Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
        browser.call("screenshot", label=label, path=str(Path(SCREENSHOTS) / f"{name}.png"))


def until_buttons(browser, label, check, what, seconds=5):
    deadline = time.monotonic() + seconds
    while True:
        seen = buttons(browser, label)
        if check(seen):
            return seen
        assert time.monotonic() < deadline, f"{what}: {seen}"
        time.sleep(0.05)


@pytest.fixture(scope="module")
def played(server):
    base, clock = server
    browser = Browser(base)
    seen = {}
    try:
        for label in LABELS:
            browser.open(label)
        names = browser.names
        browser.call("click", label="P0", selector="#home-create")
        browser.wait("P0", "/[A-Z0-9]{4}/.test(document.getElementById('lobby-code').textContent)")
        code = browser.js("P0", "document.getElementById('lobby-code').textContent.match(/[A-Z0-9]{4}/)[0]")
        for label in LABELS[1:]:
            browser.call("fill", label=label, selector="#join-code", text=code)
            browser.call("click", label=label, selector="#join-submit")
            browser.wait(label, "!document.getElementById('screen-lobby').hidden")
        browser.call("click", label="P0", selector='#lobby-modes button:has-text("Classic")')
        wait_until(lambda: lobby_of(names["P0"]).mode == "classic", "Classic chosen")
        roles = start_round(browser, "P0", LABELS, 0)
        fr = next(label for label, role in roles.items() if role == "Free Rider")
        victim, reporter, other = [label for label in LABELS if label != fr]
        seen["roles"] = roles
        # The red button unlocks 45 s after the start; the fail's progress
        # message tells the pages, so the clock is set forward first.
        clock.skip(50)

        # 1. Alone on the deck: charged, nobody in range.
        for label, place in zip((victim, reporter, other), FAR):
            put(names[label], place)
        put(names[fr], AWAY)
        standing_still(names[fr])
        seen["alone"] = until_buttons(browser, fr, lambda b: b["main"] and b["main"]["disabled"], "charged and off")
        shot(browser, fr, "fr_1_charged_nobody_in_range")

        # 2. A High Performer 10 units away: yellow and on.
        put(names[victim], (AWAY[0] + 10, AWAY[1]))
        seen["ready"] = until_buttons(browser, fr, lambda b: b["main"] and not b["main"]["disabled"], "ready")
        shot(browser, fr, "fr_2_ready_in_range")

        # 3. At the red button: Q does nothing, F fails; three buttons.
        put(names[fr], AT_THE_BUTTON)
        put(names[victim], (AT_THE_BUTTON[0] + 6, AT_THE_BUTTON[1]))
        standing_still(names[fr])
        until_buttons(browser, fr, lambda b: b["main"] and not b["main"]["disabled"], "ready at the button")
        browser.call("press", label=fr, key="KeyQ")
        time.sleep(0.6)
        seen["failed_after_q"] = sorted(lobby_of(names[fr]).classic_round.eliminated)
        browser.call("press", label=fr, key="KeyF")
        failed(browser, fr, names[victim])
        put(names[victim], FAR[0])
        fail_time = time.monotonic()
        seen["at_button"] = until_buttons(
            browser, fr, lambda b: b["main"]["charging"] and b["e"] and b["report"], "three buttons at the red button")
        shot(browser, fr, "fr_3_at_the_red_button_in_the_cooldown")
        seen["layouts"] = {}
        for width, height in ((1280, 800), (1024, 700), (320, 640)):
            browser.call("viewport", label=fr, width=width, height=height)
            time.sleep(0.4)
            seen["layouts"][f"{width}x{height}"] = buttons(browser, fr)
            if width == 320:
                shot(browser, fr, "fr_3b_three_buttons_320")
        browser.call("viewport", label=fr, width=1280, height=800)
        time.sleep(0.3)

        # 4. Halfway through the cooldown, alone on the deck.
        put(names[fr], AWAY)
        standing_still(names[fr])
        time.sleep(max(0.0, fail_time + 7.5 - time.monotonic()))
        seen["half"] = buttons(browser, fr)
        shot(browser, fr, "fr_4_cooldown_half_filled")

        # 5. Beside the hedge: "E Hide", then "E Leave hiding".
        put(names[fr], (HEDGE_SPOT["x"], HEDGE_SPOT["y"] + 20))
        standing_still(names[fr])
        seen["hide"] = until_buttons(browser, fr, lambda b: b["e"] and b["e"]["text"] == "E Hide", "E Hide")
        shot(browser, fr, "fr_5_at_a_hiding_object")
        press_hide(browser, fr, names[fr])
        seen["hidden"] = until_buttons(browser, fr, lambda b: b["e"] and b["e"]["text"] == "E Leave hiding", "E Leave hiding")
        shot(browser, fr, "fr_6_hidden")

        # 6. A High Performer at the F-sheet.
        sheet = browser.messages(reporter, "classic_fail")[-1]["position"]
        put(names[reporter], (sheet["x"], sheet["y"] + 3))
        standing_still(names[reporter])
        seen["hp_report"] = until_buttons(browser, reporter, lambda b: b["report"], "R Report for the High Performer")
        shot(browser, reporter, "hp_r_report")
        seen["any_q_text"] = {label: browser.js(label, "Array.from(document.querySelectorAll('.use-button, .free-rider-e-button, .report-button')).some((b) => /\\bQ\\b/.test(b.textContent))") for label in LABELS}
        seen["e_button_on_hp_pages"] = {label: buttons(browser, label)["e"] for label in LABELS if label != fr}
    finally:
        seen["console"] = browser.close()
    return seen


def grey_fill(button):
    return "linear-gradient" in button["image"] and button["disabled"]


def test_charged_with_nobody_in_range_it_is_all_grey_and_off(played):
    main = played["alone"]["main"]
    assert main["text"] == "F Let fail"
    assert grey_fill(main) and main["charging"] is False
    assert main["fill"] == "100%"
    assert main["label"] == "Let fail, nobody in range"
    assert played["alone"]["e"] is None


def test_ready_in_range_it_is_yellow_like_e_use(played):
    main = played["ready"]["main"]
    assert main["text"] == "F Let fail"
    assert main["disabled"] is False
    assert main["image"] == "none"
    assert main["colour"] == "rgb(255, 210, 63)"  # var(--sun), the yellow of an active "E Use"


def test_q_no_longer_lets_fail_and_f_does(played):
    assert played["failed_after_q"] == []
    assert played["at_button"]["main"]["charging"] is True


def test_at_the_red_button_in_the_cooldown_there_are_three_separate_buttons(played):
    at = played["at_button"]
    assert at["main"]["text"] == "F Let fail" and grey_fill(at["main"])
    assert not re.search(r"\d", at["main"]["text"])
    assert at["e"]["text"] == "E Emergency" and at["e"]["disabled"] is False
    assert at["report"]["text"] == "R Report"


@pytest.mark.parametrize("size", ["1280x800", "1024x700", "320x640"])
def test_no_button_overlaps_another_or_the_task_card(played, size):
    layout = played["layouts"][size]
    boxes = [layout[key]["box"] for key in ("main", "e", "report") if layout[key]]
    assert len(boxes) == 3, layout
    if layout["card"]:
        boxes.append(layout["card"]["box"])
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert not overlap(a, b), (size, a, b)


def test_f_let_fail_keeps_its_place_when_the_others_appear(played):
    alone, at = played["alone"]["main"]["box"], played["at_button"]["main"]["box"]
    assert alone == at


def test_halfway_through_the_cooldown_the_grey_fill_is_about_half(played):
    main = played["half"]["main"]
    assert main["text"] == "F Let fail" and grey_fill(main) and main["charging"] is True
    assert 35 <= float(main["fill"].rstrip("%")) <= 65
    assert re.fullmatch(r"Let fail, ready in \d+ seconds?", main["label"])


def test_at_a_hiding_object_e_hide_then_e_leave_hiding(played):
    assert played["hide"]["e"]["text"] == "E Hide"
    assert played["hidden"]["e"]["text"] == "E Leave hiding"
    assert played["hidden"]["main"]["text"] == "F Let fail"


def test_a_high_performer_sees_r_report_and_never_a_second_button(played):
    assert played["hp_report"]["report"]["text"] == "R Report"
    assert played["hp_report"]["main"]["text"] in ("E Use", "E Emergency")
    assert played["e_button_on_hp_pages"] == {label: None for label in played["e_button_on_hp_pages"]}


def test_no_button_mentions_q(played):
    assert not any(played["any_q_text"].values())


def test_no_console_error_or_warning_in_the_four_pages(played):
    assert played["console"] == []
