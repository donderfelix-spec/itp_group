"""The play test of to-do M3-1.6 "hide with E", with four Chromium pages.

Four guests play Classic against the real server with its real tick (the
harness of test_play_hiding.py: the server runs in this process, so the
test can put players and set the server's clock forward). One Free Rider,
three High Performers:

1. Beside the hedge his button reads "E Hide"; standing there alone hides
   nothing. He presses E: the server puts him in the middle of the spot,
   only his page shows "Hidden" and his half transparent character, and
   his own positions flag him as hidden. Neither the High Performer 30
   units away nor the one 40 units away is sent him (S-192). No High
   Performer's page is ever told anything about hiding.
2. He presses F beside a High Performer: refused with "Leave your hiding
   spot first."; nobody failed, he still hides.
3. One step ends hiding: the one 40 units away gets him again.
4. He fails that High Performer (not hidden) and hides again: the new
   ghost gets him flagged as hidden, the living do not get him.
5. A High Performer calls a meeting at the red button: the meeting ends
   hiding and he is sent to everybody.
6. The High Performers vote him out; a new round starts and nobody hides.
No page logs an error or a warning (the refusal in 2 is a message, not a
console error).

Skipped when Node, Playwright or Chromium is missing.
"""

import json
import math
import time

import pytest

from server.main import app
from test_play_hiding import (  # noqa: F401  (fixtures)
    Browser,
    lobby_of,
    playwright_works,
    position,
    press_at_button,
    press_fail,
    failed,
    press_hide,
    put,
    quiet_tick,
    server,
    standing_still,
    start_round,
    wait_for_meeting_phase,
    wait_until,
)

pytestmark = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")

CAMPUS = app.state.campus
HEDGE_SPOT = CAMPUS["hiding_spots"][0]
CENTRE = (float(HEDGE_SPOT["x"]), float(HEDGE_SPOT["y"]))
LABELS = ["P0", "P1", "P2", "P3"]
# Where the Free Rider stands when he presses E: in the hedge, 18 units
# right of the spot's centre (within the reach of 25).
BESIDE = (CENTRE[0] + 18, CENTRE[1])
# On the open deck straight below the spot, 30 and 40 units from its centre.
AT_30 = (CENTRE[0], CENTRE[1] + 30)
AT_40 = (CENTRE[0], CENTRE[1] + 40)
SPAWN = (CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"])


def button_text(browser, label):
    # The Free Rider's own E button (S-195) while shown, else the main button.
    return browser.js(label, "(() => { const e = document.querySelector('.free-rider-e-button'); const b = e && !e.hidden ? e : document.querySelector('.use-button'); return b ? b.textContent : null; })()")


def listed_since(browser, label, name, since):
    """For each `positions` message since `since`: whether `name` was in it."""
    return [name in listed for _, listed in browser.frames(label, since)]


def flagged_since(browser, label, since):
    """The names flagged as hidden in the `positions` messages since `since`."""
    return sorted(set(browser.js(label, f"""window.__received
        .filter((r) => r.t >= {since} && r.m.type === 'positions')
        .flatMap((r) => r.m.players.filter((p) => p.hidden === true).map((p) => p.name))""")))


def fresh_frames(browser, mover):
    """Put `mover` a little aside and back, so that everybody is sent positions now."""
    here = position(mover)
    put(mover, (here[0] + 1, here[1]))
    time.sleep(0.25)
    put(mover, here)
    time.sleep(0.25)


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
        w30, w40, victim = [label for label in LABELS if label != fr]
        seen["roles"] = roles
        classic = lobby_of(names[fr]).classic_round

        # 1. Beside the hedge: "E Hide"; standing there hides nothing.
        put(names[w30], AT_30)
        put(names[w40], AT_40)
        put(names[victim], SPAWN)
        put(names[fr], BESIDE)
        standing_still(names[fr])
        browser.wait(fr, "(() => { const e = document.querySelector('.free-rider-e-button'); return Boolean(e) && !e.hidden && e.textContent === 'E Hide'; })()")
        seen["fr_button_beside"] = button_text(browser, fr)
        seen["hp_buttons_beside"] = {label: button_text(browser, label) for label in (w30, w40, victim)}
        before = browser.now(w40)
        fresh_frames(browser, names[w30])
        seen["w40_sees_before_hiding"] = listed_since(browser, w40, names[fr], before)

        press_hide(browser, fr, names[fr])
        time.sleep(0.4)
        seen["fr_at_after_hiding"] = position(names[fr])
        seen["fr_hint"] = browser.hidden_hint(fr)["shown"]
        seen["fr_button_hidden"] = button_text(browser, fr)
        marks = {label: browser.now(label) for label in LABELS}
        fresh_frames(browser, names[victim])
        seen["w30_distance"] = math.dist(position(names[w30]), position(names[fr]))
        seen["w40_distance"] = math.dist(position(names[w40]), position(names[fr]))
        seen["w30_sees_hidden"] = listed_since(browser, w30, names[fr], marks[w30])
        seen["w40_sees_hidden"] = listed_since(browser, w40, names[fr], marks[w40])
        seen["hp_hints"] = {label: browser.hidden_hint(label)["shown"] for label in (w30, w40, victim)}
        seen["fr_flagged"] = flagged_since(browser, fr, marks[fr])
        browser.shot(fr, "hide_1_free_rider_hidden")
        browser.shot(w40, "hide_1_watcher_at_40")
        browser.shot(w30, "hide_1_watcher_at_30")

        # 2. F while hidden, beside a High Performer: refused (Q did this before S-195).
        put(names[victim], (CENTRE[0] + 6, CENTRE[1] + 4))
        standing_still(names[victim])
        time.sleep(0.3)
        q_mark = browser.now(fr)
        browser.call("press", label=fr, key="KeyF")
        browser.wait(fr, f"window.__received.some((r) => r.t > {q_mark} && r.m.type === 'error')", timeout=5000)
        seen["q_answer"] = browser.messages(fr, "error", q_mark)[-1]
        seen["after_q"] = {"eliminated": sorted(classic.eliminated), "hidden": classic.is_hidden(names[fr])}
        put(names[victim], SPAWN)

        # 3. One step ends hiding.
        step_mark = browser.now(w40)
        browser.call("down", label=fr, key="KeyW")  # up, away from the one at 40
        time.sleep(0.15)
        browser.call("up", label=fr, key="KeyW")
        standing_still(names[fr])
        time.sleep(0.3)
        seen["after_step"] = {
            "hidden": classic.is_hidden(names[fr]),
            "fr_hint": browser.hidden_hint(fr)["shown"],
            "w40_sees": listed_since(browser, w40, names[fr], step_mark),
            "w40_distance": math.dist(position(names[w40]), position(names[fr])),
        }

        # 4. He fails the victim (not hidden), then hides again: the ghost sees him flagged.
        put(names[fr], BESIDE)
        put(names[victim], (BESIDE[0], BESIDE[1] + 6))
        standing_still(names[fr])
        # The red button unlocks 45 s after the start; the fail's progress
        # message tells the pages, so the clock is set forward first.
        clock.skip(50)
        press_fail(browser, fr)
        failed(browser, fr, names[victim])
        put(names[victim], (CENTRE[0] - 60, CENTRE[1] + 40))
        press_hide(browser, fr, names[fr])
        ghost_mark = {label: browser.now(label) for label in LABELS}
        fresh_frames(browser, names[w30])
        seen["ghost_view"] = {
            "ghost_sees": listed_since(browser, victim, names[fr], ghost_mark[victim]),
            "ghost_flagged": flagged_since(browser, victim, ghost_mark[victim]),
            "living_see": {label: listed_since(browser, label, names[fr], ghost_mark[label]) for label in (w30, w40)},
            "living_flagged": {label: flagged_since(browser, label, 0) for label in (w30, w40)},
        }
        browser.shot(victim, "hide_4_ghost_sees_hidden_free_rider")

        # 5. A meeting at the red button.
        meeting_mark = {label: browser.now(label) for label in LABELS}
        press_at_button(browser, w30, names[w30])
        wait_for_meeting_phase(browser, LABELS, "discussion", 1)
        browser.wait(fr, f"window.__received.some((r) => r.t > {meeting_mark[fr]} && r.m.type === 'classic_hiding' && r.m.hidden === false)")
        fresh_frames(browser, names[w30])
        seen["meeting"] = {
            "hidden": classic.is_hidden(names[fr]),
            "fr_hint": browser.hidden_hint(fr)["shown"],
            "w40_sees": listed_since(browser, w40, names[fr], meeting_mark[w40]),
        }

        # 6. They vote him out; a new round: nobody hides.
        clock.skip(46)
        wait_for_meeting_phase(browser, LABELS, "voting", 1)
        for label in (w30, w40):
            browser.wait(label, f"""document.querySelector('.classic-vote-player[data-target-id="{names[fr]}"]') !== null""")
            browser.call("click", label=label, selector=f'.classic-vote-player[data-target-id="{names[fr]}"]')
        clock.skip(31)
        wait_until(lambda: lobby_of(names[fr]).phase == "lobby", "the lobby after the vote")
        for label in LABELS:
            browser.wait(label, "window.__received.some((r) => r.m.type === 'classic_result')")
        seen["result"] = browser.messages("P0", "classic_result")[-1]
        for label in LABELS:
            browser.js(label, "!document.getElementById('classic-end-screen').hidden && document.getElementById('classic-back-lobby').click()")
        roles2 = start_round(browser, "P0", LABELS, 1)
        fr2 = next(label for label, role in roles2.items() if role == "Free Rider")
        watcher2 = next(label for label in LABELS if label != fr2)
        put(names[fr2], CENTRE)
        put(names[watcher2], AT_40)
        standing_still(names[fr2])
        new_mark = browser.now(watcher2)
        fresh_frames(browser, names[watcher2])
        seen["new_round"] = {
            "hidden": dict(lobby_of(names[fr2]).classic_round.hidden),
            "fr_hint": browser.hidden_hint(fr2)["shown"],
            "watcher_sees_fr_standing_in_spot": listed_since(browser, watcher2, names[fr2], new_mark),
            "fr_button": button_text(browser, fr2),
        }
        # Who was ever told about hiding.
        seen["told_hiding"] = {label: len(browser.messages(label, "classic_hiding")) for label in LABELS}
        seen["fr"], seen["fr2"] = fr, fr2
        seen["names"] = dict(names)
    finally:
        seen["console"] = browser.close()
    return seen


def test_beside_a_hiding_object_only_the_free_rider_gets_e_hide(played):
    assert played["fr_button_beside"] == "E Hide"
    assert "E Hide" not in played["hp_buttons_beside"].values()
    assert played["w40_sees_before_hiding"] and all(played["w40_sees_before_hiding"])


def test_e_puts_him_in_the_middle_and_only_his_page_shows_hidden(played):
    assert played["fr_at_after_hiding"] == pytest.approx(CENTRE)
    assert played["fr_hint"] is True
    assert played["fr_flagged"] == [played["names"][played["fr"]]]
    assert played["fr_button_hidden"] == "E Leave hiding"
    assert not any(played["hp_hints"].values())


def test_neither_the_watcher_at_30_nor_the_one_at_40_gets_him(played):
    # S-192: no reveal range any more.
    assert played["w30_distance"] == pytest.approx(30)
    assert played["w40_distance"] == pytest.approx(40)
    assert played["w30_sees_hidden"] and not any(played["w30_sees_hidden"])
    assert played["w40_sees_hidden"] and not any(played["w40_sees_hidden"])


def test_a_ghost_gets_him_flagged_and_the_living_never_see_a_flag(played):
    view = played["ghost_view"]
    fr_name = played["names"][played["fr"]]
    assert view["ghost_sees"] and all(view["ghost_sees"])
    assert view["ghost_flagged"] == [fr_name]
    assert all(seen and not any(seen) for seen in view["living_see"].values()), view["living_see"]
    assert view["living_flagged"] == {label: [] for label in view["living_flagged"]}


def test_q_while_hidden_is_refused_and_nobody_fails(played):
    assert played["q_answer"]["code"] == "leave_hiding_first"
    assert played["q_answer"]["message"] == "Leave your hiding spot first."
    assert played["after_q"] == {"eliminated": [], "hidden": True}


def test_one_step_ends_hiding(played):
    after = played["after_step"]
    assert after["hidden"] is False and after["fr_hint"] is False
    assert after["w40_distance"] > 35
    assert after["w40_sees"] and after["w40_sees"][-1] is True


def test_a_meeting_ends_hiding(played):
    meeting = played["meeting"]
    assert meeting["hidden"] is False and meeting["fr_hint"] is False
    assert meeting["w40_sees"] and meeting["w40_sees"][-1] is True


def test_a_new_round_starts_with_nobody_hidden(played):
    assert played["result"]["winner"] == "HP"
    new = played["new_round"]
    assert new["hidden"] == {}
    assert new["fr_hint"] is False
    assert new["watcher_sees_fr_standing_in_spot"] and all(new["watcher_sees_fr_standing_in_spot"])
    assert new["fr_button"] == "E Hide"


def test_only_the_free_rider_was_ever_told_about_hiding(played):
    told = played["told_hiding"]
    assert told[played["fr"]] >= 4  # hide, step, hide, meeting
    for label, count in told.items():
        if label != played["fr"]:
            assert count == 0, label


def test_no_console_error_or_warning_in_the_four_pages(played):
    assert played["console"] == []
