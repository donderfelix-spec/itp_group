"""M3-3.22: once the own emergency call is used, the red button offers nothing more (S-170), in Chromium.

Five guests play Classic in real Chromium pages against the real server, run
in this process, with the pages, the server and the helpers of
test_play_emergency_button_range.py (and through it test_play_hiding.py).
The server's clock is set forward instead of waiting 45 seconds for the
button, 45 seconds of discussion and 30 of vote.

Round 1 (roles: the Free Rider and four High Performers: victim, caller,
other, spare):

1. After 45 s the Free Rider fails the victim far from the button (this also
   tells every page that the button is unlocked).
2. The caller at the button sees "E Emergency" and calls; the meeting is
   played to its result (nobody votes). Back on the map at the button he sees
   "E Use" (switched off) and no "E Emergency", E sends no `emergency`, and a
   call past the page is refused with "You cannot call an emergency meeting
   right now.". At the same time the other High Performer and the Free
   Rider, who have not called, see "E Emergency" at the button: another
   player's call hides nothing.
3. The Free Rider calls at the button; after that meeting, at the button, he
   sees the fail look: "F Let fail" (switched off with nobody near), then
   "F Let fail" with the spare beside him (no tile count, S-181; key first, S-195). E sends nothing; a click
   on the use button sends `fail` (not `emergency`) and the spare is out.
4. The other High Performer reports the spare's sheet; after that report
   meeting he still sees "E Emergency" at the button. He calls, and the
   Free Rider is voted out: the end screen.

Round 2 (the host starts a new round from the end screen): before the
45 s unlock nobody sees "E Emergency"; after it, round 1's caller and round
1's Free Rider see "E Emergency" at the button again, and the caller's E
opens a meeting that names him.

Set EMERGENCY_CALL_USED_SCREENSHOTS to a folder to keep the screenshots (and
seen.json, everything the play recorded). Skipped when Node, Playwright or
Chromium is missing.
"""

import json
import os
import time
import urllib.request
from pathlib import Path

import pytest

from rules import FAIL_COOLDOWN_SECONDS
from server import protocol
from test_play_emergency_button_range import (
    CENTRE,
    PROBE,
    bypass,
    end_meeting,
    first_meeting_state_since,
    meeting_states,
    press_and_watch,
    sent_emergencies,
    stand,
    use_button,
)
from test_play_hiding import (  # noqa: F401 (quiet_tick and server are fixtures)
    LABELS,
    Browser,
    failed,
    free_place_at,
    lobby_of,
    playwright_works,
    press_fail,
    put,
    quiet_tick,
    server,
    standing_still,
    start_round,
    wait_for_meeting_phase,
    wait_until,
)

pytestmark = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")

SCREENSHOTS = os.environ.get("EMERGENCY_CALL_USED_SCREENSHOTS")
CALL_REFUSED = protocol.REJECTIONS["emergency_rejected"]
EMERGENCY_DELAY_SECONDS = 45
VOTE_SECONDS = 30

# Places within the 25 units of the button, all of them free (S-170).
CALLER_AT_BUTTON = (CENTRE[0], CENTRE[1] + 10)
OTHER_AT_BUTTON = (CENTRE[0] + 12, CENTRE[1] - 8)
FR_AT_BUTTON = (CENTRE[0] - 20, CENTRE[1] + 10)
SPARE_BESIDE_FR = (FR_AT_BUTTON[0] + 3, FR_AT_BUTTON[1])


def shot(browser, label, name):
    if SCREENSHOTS:
        Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
        browser.call("screenshot", label=label, path=str(Path(SCREENSHOTS) / f"{name}.png"))


def write_down(seen):
    if SCREENSHOTS:
        Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
        (Path(SCREENSHOTS) / "seen.json").write_text(json.dumps(seen, indent=1, default=str))


def sent_since(browser, label, count):
    return browser.js(label, f"window.__sent.slice({count}).map((r) => r.m)")


def sent_count(browser, label):
    return browser.js(label, "window.__sent.length")


def call_at_button(browser, label, place, number):
    """Stand at the button, see "E Emergency", press E; wait for meeting `number` on every page."""
    stand(browser, label, place)
    browser.wait(label, "Array.from(document.querySelectorAll('.use-button, .free-rider-e-button')).some((b) => !b.hidden && b.textContent === 'E Emergency')", timeout=5000)
    before = use_button(browser, label)
    states = {other: meeting_states(browser, other) for other in LABELS}
    browser.call("press", label=label, key="KeyE")
    wait_for_meeting_phase(browser, LABELS, "discussion", number)
    for other in LABELS:
        browser.wait(other, "!document.getElementById('classic-meeting').hidden")
    return {"before": before,
            "first_state": {other: first_meeting_state_since(browser, other, states[other])[0] for other in LABELS}}


def wait_for_unlock(browser, label):
    """After a meeting the button is locked for 45 s again (S-218); the pages
    count them by their own clock, so the play waits them out."""
    browser.wait(label, "window.__button.frame && window.__button.frame.visible === true", timeout=60000)


def fail_far_from_the_button(browser, fr, victim, clock):
    """The Free Rider fails `victim` 60 units above the button; the pages hear of the unlock."""
    names = browser.names
    clock.skip(EMERGENCY_DELAY_SECONDS + 1)
    fr_place = free_place_at(CENTRE, 60, near=(CENTRE[0], CENTRE[1] - 60))
    put(names[victim], (fr_place[0] + 3, fr_place[1]))
    put(names[fr], fr_place)
    standing_still(names[fr])
    press_fail(browser, fr)
    failed(browser, fr, names[victim])
    for label in LABELS:
        browser.wait(label, "window.__button.frame && window.__button.frame.visible")


def new_round_from_end_screen(browser, host, seen_rounds):
    browser.call("click", label=host, selector="#classic-new-round")
    for label in LABELS:
        browser.wait(label, f"window.__received.filter((r) => r.m.type === 'classic_role').length > {seen_rounds}")
        browser.wait(label, "!document.getElementById('classic-role-card').hidden")
    roles = {label: browser.js(label, "document.getElementById('classic-role-name').textContent") for label in LABELS}
    for label in LABELS:
        browser.wait(label, "document.getElementById('classic-role-card').hidden", timeout=15000)
        browser.js(label, "document.activeElement && document.activeElement.blur()")
    return roles


@pytest.fixture(scope="module")
def played(server):  # noqa: F811 (the imported fixture)
    base, clock = server
    seen = {}
    with urllib.request.urlopen(base + "/health", timeout=5) as answer:
        seen["health"] = answer.status
    browser = Browser(base)
    try:
        for label in LABELS:
            browser.open(label)
            browser.js(label, PROBE)
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

        # ---- Round 1 ----
        roles = start_round(browser, "P0", LABELS, 0)
        seen["roles"] = roles
        fr = next(label for label, role in roles.items() if role == "Free Rider")
        victim, caller, other, spare = [label for label in LABELS if label != fr]
        seen["labels"] = {"fr": fr, "victim": victim, "caller": caller, "other": other, "spare": spare}
        classic = lobby_of(names[fr]).classic_round
        around = {label: free_place_at(CENTRE, 60, near=(CENTRE[0] + dx, CENTRE[1] + dy))
                  for label, (dx, dy) in zip((caller, other, spare), [(-60, 0), (60, 0), (40, 45)])}
        for label, place in around.items():
            put(names[label], place)
        fail_far_from_the_button(browser, fr, victim, clock)
        put(names[victim], free_place_at(CENTRE, 60, near=(CENTRE[0] - 40, CENTRE[1] + 45)))

        # 2. The caller calls; the meeting runs to its result.
        seen["caller_call"] = call_at_button(browser, caller, CALLER_AT_BUTTON, 1)
        shot(browser, caller, "1a_caller_meeting_opened")
        end_meeting(browser, clock, 1)
        seen["after_meeting_1"] = {"phase": classic.phase, "eliminated": sorted(classic.eliminated)}
        wait_for_unlock(browser, caller)

        stand(browser, caller, CALLER_AT_BUTTON)
        seen["caller_after"] = use_button(browser, caller)
        seen["caller_frame_after"] = browser.js(caller, "window.__button.frame")
        shot(browser, caller, "1b_caller_back_at_button_E_Use")
        seen["caller_press_e"] = press_and_watch(browser, caller)
        seen["caller_bypass"] = bypass(browser, caller)
        shot(browser, caller, "1c_caller_second_call_past_page_refused")
        stand(browser, other, OTHER_AT_BUTTON)
        seen["other_after_callers_call"] = use_button(browser, other)
        shot(browser, other, "1d_other_hp_at_button_E_Emergency")
        stand(browser, fr, FR_AT_BUTTON)
        seen["fr_after_callers_call"] = use_button(browser, fr)
        put(names[other], around[other])
        put(names[caller], around[caller])

        # 3. The Free Rider calls; afterwards he has the fail button at the button.
        seen["fr_call"] = call_at_button(browser, fr, FR_AT_BUTTON, 2)
        end_meeting(browser, clock, 2)
        clock.skip(FAIL_COOLDOWN_SECONDS)  # the cooldown starts again after a meeting (DESIGN.md 5.8)
        stand(browser, fr, FR_AT_BUTTON)
        browser.wait(fr, "document.querySelector('.use-button').classList.contains('fail-button')", timeout=5000)
        seen["fr_after_alone"] = use_button(browser, fr)
        shot(browser, fr, "2a_free_rider_after_own_call_at_button_alone")
        seen["fr_press_e_alone"] = press_and_watch(browser, fr)
        stand(browser, spare, SPARE_BESIDE_FR)
        standing_still(names[fr])
        browser.wait(fr, """(() => {
            const status = window.__received.filter((r) => r.m.type === 'classic_fail_status').pop();
            const b = document.querySelector('.use-button');
            return Boolean(status) && status.m.available === true && status.m.in_range === true && !b.disabled;
        })()""", timeout=10000)
        time.sleep(0.3)
        seen["fr_after_with_target"] = use_button(browser, fr)
        shot(browser, fr, "2b_free_rider_after_own_call_let_fail_at_button")
        seen["fr_press_e_with_target"] = press_and_watch(browser, fr)
        count = sent_count(browser, fr)
        states = {label: meeting_states(browser, label) for label in LABELS}
        browser.call("click", label=fr, selector=".use-button")
        failed(browser, fr, names[spare])
        browser.js(fr, "document.activeElement && document.activeElement.blur()")
        seen["fr_click"] = {
            "sent": sent_since(browser, fr, count),
            "meetings": {label: meeting_states(browser, label) - states[label] for label in LABELS},
            "eliminated": sorted(classic.eliminated),
        }
        shot(browser, fr, "2c_free_rider_click_let_fail_done")

        # 4. A report meeting hides nothing; then the other High Performer calls and the Free Rider goes.
        # Since S-202 only the Free Rider (and who sees the place) is told where
        # the sheet lies; the page of `other` gets it once he stands there.
        sheet = browser.js(fr, f"""window.__received.filter((r) => r.m.type === 'classic_fail'
            && r.m.target_id === {json.dumps(names[spare])}).pop().m.position""")
        seen["sheet"] = sheet
        put(names[spare], around[spare])
        stand(browser, other, (sheet["x"], sheet["y"]))
        browser.wait(other, "!document.querySelector('.report-button').hidden", timeout=5000)
        states = {label: meeting_states(browser, label) for label in LABELS}
        browser.call("press", label=other, key="KeyR")
        wait_for_meeting_phase(browser, LABELS, "discussion", 3)
        seen["report_state"] = first_meeting_state_since(browser, other, states[other])[0]
        end_meeting(browser, clock, 3)
        wait_for_unlock(browser, other)
        stand(browser, other, OTHER_AT_BUTTON)
        browser.wait(other, "Array.from(document.querySelectorAll('.use-button, .free-rider-e-button')).some((b) => !b.hidden && b.textContent === 'E Emergency')", timeout=5000)
        seen["other_after_report"] = use_button(browser, other)
        shot(browser, other, "3a_other_after_report_meeting_E_Emergency")
        seen["other_call"] = call_at_button(browser, other, OTHER_AT_BUTTON, 4)
        clock.skip(EMERGENCY_DELAY_SECONDS + 1)
        wait_for_meeting_phase(browser, LABELS, "voting", 4)
        for label in (caller, other):
            before = meeting_states(browser, label)
            browser.call("click", label=label, selector=f'#classic-vote-players button[data-target-id="{names[fr]}"]')
            browser.wait(label, f"window.__received.filter((r) => r.m.type === 'meeting_state').length > {before}")
        clock.skip(VOTE_SECONDS + 1)
        for label in LABELS:
            browser.wait(label, "!document.getElementById('classic-end-screen').hidden", timeout=20000)
        seen["round_1_winner"] = browser.js(caller, "window.__received.filter((r) => r.m.type === 'classic_result').pop().m.winner")
        shot(browser, "P0", "3b_end_screen_round_1")

        # ---- Round 2 ----
        roles2 = new_round_from_end_screen(browser, "P0", 1)
        seen["roles2"] = roles2
        fr2 = next(label for label, role in roles2.items() if role == "Free Rider")
        victim2 = next(label for label in LABELS if label not in (fr2, caller, fr))
        seen["labels2"] = {"fr": fr2, "victim": victim2}
        stand(browser, caller, CALLER_AT_BUTTON)
        seen["r2_caller_locked"] = use_button(browser, caller)
        seen["r2_caller_frame_locked"] = browser.js(caller, "window.__button.frame")
        for label in LABELS:
            if label not in (fr2, victim2, caller):
                put(names[label], free_place_at(CENTRE, 60, near=(CENTRE[0] + 60, CENTRE[1])))
        put(names[caller], free_place_at(CENTRE, 60, near=(CENTRE[0] - 60, CENTRE[1])))
        fail_far_from_the_button(browser, fr2, victim2, clock)
        stand(browser, fr, FR_AT_BUTTON)
        browser.wait(fr, "Array.from(document.querySelectorAll('.use-button, .free-rider-e-button')).some((b) => !b.hidden && b.textContent === 'E Emergency')", timeout=5000)
        seen["r2_old_fr"] = use_button(browser, fr)
        shot(browser, fr, "4a_round_2_round_1_free_rider_E_Emergency")
        put(names[fr], free_place_at(CENTRE, 60, near=(CENTRE[0] + 60, CENTRE[1])))
        seen["r2_caller_call"] = call_at_button(browser, caller, CALLER_AT_BUTTON, 5)
        shot(browser, caller, "4b_round_2_caller_called_again")
        seen["problems"] = browser.close()
    except BaseException:
        write_down(seen)
        try:
            browser.close()
        except Exception:
            pass
        raise
    seen["names"] = dict(browser.names)
    write_down(seen)
    return seen


def test_the_server_answers_health(played):
    assert played["health"] == 200


def test_the_callers_call_opens_an_emergency_meeting_that_names_him(played):
    call = played["caller_call"]
    caller_name = played["names"][played["labels"]["caller"]]
    assert call["before"] == {"text": "E Emergency", "disabled": False, "failLook": False}
    for label, state in call["first_state"].items():
        assert (state["reason"], state["trigger_player_id"]) == ("emergency", caller_name), label
    assert played["after_meeting_1"]["phase"] != "meeting"


def test_after_his_meeting_the_caller_at_the_button_sees_e_use_and_no_e_emergency(played):
    assert played["caller_after"] == {"text": "E Use", "disabled": True, "failLook": False}
    # The button itself is still drawn: only the offer is gone.
    assert played["caller_frame_after"]["visible"] and played["caller_frame_after"]["drawn"]


def test_after_his_meeting_e_of_the_caller_sends_no_emergency(played):
    assert played["caller_press_e"]["sent"] == 0
    assert set(played["caller_press_e"]["meetings"].values()) == {0}


def test_a_second_call_past_the_page_is_refused_with_the_message_of_section_9(played):
    answer = played["caller_bypass"]
    assert [(e["code"], e["message"]) for e in answer["errors"]] == [("emergency_rejected", CALL_REFUSED)]
    assert answer["shown"] == {"hidden": False, "text": CALL_REFUSED}
    assert set(answer["meetings"].values()) == {0}
    assert answer["server_meeting"] is False


def test_another_players_call_hides_nothing(played):
    assert played["other_after_callers_call"] == {"text": "E Emergency", "disabled": False, "failLook": False}
    assert played["fr_after_callers_call"] == {"text": "E Emergency", "disabled": False, "failLook": False}


def test_the_free_riders_call_opens_a_meeting_that_names_him(played):
    call = played["fr_call"]
    fr_name = played["names"][played["labels"]["fr"]]
    assert call["before"] == {"text": "E Emergency", "disabled": False, "failLook": False}
    for label, state in call["first_state"].items():
        assert (state["reason"], state["trigger_player_id"]) == ("emergency", fr_name), label


def test_after_his_call_the_free_rider_at_the_button_sees_the_fail_look(played):
    assert played["fr_after_alone"] == {"text": "F Let fail", "disabled": True, "failLook": True}
    assert played["fr_after_with_target"] == {"text": "F Let fail", "disabled": False, "failLook": True}


def test_after_his_call_e_of_the_free_rider_at_the_button_sends_no_emergency(played):
    for press in ("fr_press_e_alone", "fr_press_e_with_target"):
        assert played[press]["sent"] == 0, press
        assert set(played[press]["meetings"].values()) == {0}, press


def test_a_click_on_the_free_riders_use_button_at_the_button_sends_fail_not_emergency(played):
    click = played["fr_click"]
    spare_name = played["names"][played["labels"]["spare"]]
    assert [m["type"] for m in click["sent"]] == ["fail"], click["sent"]
    assert click["sent"][0].get("target_id") in (None, spare_name)
    assert set(click["meetings"].values()) == {0}
    assert spare_name in click["eliminated"]


def test_a_report_meeting_hides_nothing(played):
    other_name = played["names"][played["labels"]["other"]]
    assert (played["report_state"]["reason"], played["report_state"]["trigger_player_id"]) == ("report", other_name)
    assert played["other_after_report"] == {"text": "E Emergency", "disabled": False, "failLook": False}
    for label, state in played["other_call"]["first_state"].items():
        assert (state["reason"], state["trigger_player_id"]) == ("emergency", other_name), label


def test_round_1_ends_with_the_free_rider_voted_out(played):
    assert played["round_1_winner"] == "HP"


def test_in_a_new_round_the_button_is_locked_at_first(played):
    assert played["r2_caller_locked"]["text"] != "E Emergency"
    assert not (played["r2_caller_frame_locked"] or {}).get("visible")


def test_in_a_new_round_the_earlier_callers_see_e_emergency_again(played):
    assert played["r2_old_fr"] == {"text": "E Emergency", "disabled": False, "failLook": False}
    call = played["r2_caller_call"]
    caller_name = played["names"][played["labels"]["caller"]]
    assert call["before"] == {"text": "E Emergency", "disabled": False, "failLook": False}
    for label, state in call["first_state"].items():
        assert (state["reason"], state["trigger_player_id"]) == ("emergency", caller_name), label


def test_no_console_error_or_warning_on_any_page(played):
    assert played["problems"] == []
