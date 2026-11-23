"""S-212: an emergency meeting follows the flow of a report meeting, played in Chromium.

Five guests play Classic in real Chromium pages against the real server, run
in this process, with the pages, the server and the helpers of
test_play_hiding.py and test_play_emergency_button_range.py. The round's
first 45 seconds are waited for real, so that every page unlocks the red
button by its own clock; after that the server's clock is set forward.

Roles: the Free Rider and four High Performers (caller, second, voter, leaver).

1. The caller calls an emergency meeting at the button. In its discussion
   every page shows the vote buttons and the Skip row; at 1280 x 800,
   1024 x 700 and 320 x 640 the Skip row, every vote button, the message
   field, "Send" and the hint under it lie inside the window. The caller votes
   for the Free Rider, changes to the voter and takes the vote back, and
   every page shows each count. Three of five press Skip (not yet 75 %); the
   leaver leaves with the meeting's "Leave lobby", and 3 of 4 end the meeting
   at once in its discussion, without an ejection.
2. The second High Performer calls: the voter votes, three of four press
   Skip, and the meeting ends at once in its discussion, nobody ejected.
3. The Free Rider fails the voter; the second High Performer reports the
   sheet. The report meeting offers the same vote buttons and Skip row in
   its discussion and runs to its end.
4. Back at the button the caller sees no "E Emergency", and a call past the
   page is refused with "You cannot call an emergency meeting right now.".
   After every meeting the button is locked for 45 s (S-218): grey, no
   "E Emergency", E sends nothing; then it is offered again.
5. S-215: the Free Rider calls; once the three living players have voted,
   every page, the ghost's included, shows 10 seconds left, and 10 seconds
   later the meeting ends from its discussion: the Free Rider is voted out.

The compact meeting picture has one row for the "Living" names; it ends in
"+N more" instead of cutting names off after a comma.

Set EMERGENCY_FLOW_SCREENSHOTS to a folder to keep the screenshots (and
seen.json). Skipped when Node, Playwright or Chromium is missing.
"""

import json
import os
import time
import urllib.request
from pathlib import Path

import pytest

from rules import FAIL_COOLDOWN_SECONDS
from server import main, protocol
from test_play_emergency_button_range import CENTRE, PROBE, bypass, press_and_watch, stand, use_button
from test_play_hiding import (  # noqa: F401 (quiet_tick and server are fixtures)
    LABELS,
    Browser,
    failed,
    free_place_at,
    lobby_of,
    playwright_works,
    position,
    press_fail,
    put,
    quiet_tick,
    server,
    standing_still,
    start_round,
    wait_until,
)

pytestmark = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")

SCREENSHOTS = os.environ.get("EMERGENCY_FLOW_SCREENSHOTS")
CALL_REFUSED = protocol.REJECTIONS["emergency_rejected"]
UNLOCK_SECONDS = 45
DISCUSSION_SECONDS = 45
VOTE_SECONDS = 30
SIZES = [(1280, 800), (1024, 700), (320, 640)]
HAS_E_EMERGENCY = ("Array.from(document.querySelectorAll('.use-button, .free-rider-e-button'))"
                   ".some((b) => !b.hidden && b.textContent === 'E Emergency')")

# What the meeting window shows: the vote buttons with their counts, the Skip
# row, and whether each control lies inside the window.
WINDOW = """(() => {
  const inside = (el) => {
    if (!el || el.hidden || el.closest('[hidden]')) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.left >= -0.5 && r.top >= -0.5
      && r.right <= innerWidth + 0.5 && r.bottom <= innerHeight + 0.5;
  };
  const buttons = Array.from(document.querySelectorAll('#classic-vote-players .classic-vote-player'));
  const hint = document.getElementById('classic-chat-hint');
  return {
    open: !document.getElementById('classic-meeting').hidden,
    votes: buttons.map((b) => ({ target: b.dataset.targetId, count: b.children[2].textContent,
                                 label: b.getAttribute('aria-label'), pressed: b.getAttribute('aria-pressed') })),
    votesShown: !document.getElementById('classic-vote-options').hidden,
    skipShown: !document.getElementById('classic-skip-options').hidden,
    skipText: document.getElementById('classic-skip-status').textContent,
    skipButton: document.getElementById('classic-skip-discussion').textContent,
    hint: hint.textContent,
    hintFits: inside(hint) && hint.scrollWidth <= hint.clientWidth + 1,
    inside: {
      skip: inside(document.getElementById('classic-skip-discussion')),
      votes: buttons.length > 0 && buttons.every(inside),
      input: inside(document.getElementById('classic-chat-input')),
      send: inside(document.getElementById('classic-chat-send')),
    },
    widths: buttons.map((b) => Math.round(b.getBoundingClientRect().width)),
    noPageScroll: document.documentElement.scrollWidth <= innerWidth,
  };
})()"""


# Records what the meeting canvas draws, from its last clearRect on (as in
# meeting_chat_in_browser.js), so the "Living" line can be read.
RECORD_MEETING_CANVAS = """(() => {
  const proto = CanvasRenderingContext2D.prototype;
  const fillText = proto.fillText;
  const clearRect = proto.clearRect;
  const mine = (context) => context.canvas && context.canvas.id === 'classic-meeting-canvas';
  window.__meetingDraw = { texts: [] };
  proto.clearRect = function (...args) {
    if (mine(this)) window.__meetingDraw = { texts: [] };
    return clearRect.apply(this, args);
  };
  proto.fillText = function (text, x, y, ...rest) {
    if (mine(this)) window.__meetingDraw.texts.push({ text: String(text), x, y, width: this.measureText(text).width });
    return fillText.call(this, text, x, y, ...rest);
  };
  return true;
})()"""

# The texts of the "Living" row: drawn one row below the title, left of "Dead players".
LIVING_LINE = """(() => {
  const texts = window.__meetingDraw.texts;
  const title = texts.find((t) => t.text === 'Living');
  const dead = texts.find((t) => t.text === 'Dead players');
  return texts.filter((t) => t.y === title.y + 24 && t.x < dead.x)
    .map((t) => ({ text: t.text, right: t.x + t.width, limit: dead.x }));
})()"""


TIME_LEFT_TEXT = """(() => {
  const time = window.__meetingDraw.texts.find((t) => t.text.startsWith('Time left'));
  return time ? time.text : null;
})()"""


def shot(browser, label, name):
    if SCREENSHOTS:
        Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
        browser.call("screenshot", label=label, path=str(Path(SCREENSHOTS) / f"{name}.png"))


def window(browser, label):
    return browser.js(label, WINDOW)


def states_of(browser, label, phase=None):
    test = "" if phase is None else f" && r.m.phase === '{phase}'"
    return browser.js(label, f"window.__received.filter((r) => r.m.type === 'meeting_state'{test}).map((r) => r.m)")


def wait_for_phase(browser, labels, phase, count):
    for label in labels:
        browser.wait(label, f"window.__received.filter((r) => r.m.type === 'meeting_state' && r.m.phase === '{phase}').length >= {count}")


def ballots(lobby):
    meeting = lobby.meeting
    return dict(meeting["votes"]), sorted(meeting["skip_votes"]), meeting["phase"]


def act(browser, label, selector, labels, lobby):
    """Click in the meeting window; wait until the server took it and every page in `labels` shows it.

    The pages wait for the server's new votes and Skips in their newest
    snapshot, not for any next snapshot: the tick sends one every second.
    """
    before = ballots(lobby)
    browser.call("click", label=label, selector=selector)
    wait_until(lambda: ballots(lobby) != before, f"the server took the click of {label}")
    votes, skips, _phase = ballots(lobby)
    compact = {"separators": (",", ":")}
    for other in labels:
        browser.wait(other, f"""(() => {{
            const last = window.__received.filter((r) => r.m.type === 'meeting_state').pop().m;
            return JSON.stringify(last.vote_targets) === {json.dumps(json.dumps(votes, **compact))}
                && JSON.stringify(last.skip_voted) === {json.dumps(json.dumps(skips, **compact))};
        }})()""")
    time.sleep(0.1)


def counts(browser, labels, phase):
    return {label: len(states_of(browser, label, phase)) for label in labels}


def wait_for_more(browser, labels, phase, before):
    """Wait until every page got a snapshot of `phase` after the `before` counts."""
    for label in labels:
        browser.wait(label, f"window.__received.filter((r) => r.m.type === 'meeting_state' && r.m.phase === '{phase}').length > {before[label]}")


def vote_selector(name):
    return f'#classic-vote-players button[data-target-id="{name}"]'


def own_place_on_page(browser, label):
    """Where the page was last told its own player stands."""
    name = json.dumps(browser.names[label])
    return browser.js(label, f"""(() => {{
        const last = window.__received.filter((r) => r.m.type === 'positions'
            && r.m.players.some((p) => p.name === {name})).pop();
        const me = last.m.players.find((p) => p.name === {name});
        return [me.x, me.y];
    }})()""")


def call_at_button(browser, label, labels):
    stand(browser, label, (CENTRE[0], CENTRE[1] + 10))
    browser.wait(label, HAS_E_EMERGENCY, timeout=5000)
    before = counts(browser, labels, "discussion")
    browser.call("press", label=label, key="KeyE")
    wait_for_more(browser, labels, "discussion", before)
    for other in labels:
        browser.wait(other, "!document.getElementById('classic-meeting').hidden")
    time.sleep(0.3)


def closed(browser, labels):
    for label in labels:
        browser.wait(label, "document.getElementById('classic-meeting').hidden", timeout=20000)
    time.sleep(0.5)


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
            browser.js(label, RECORD_MEETING_CANVAS)
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
        # The host stays (a leaving host would only add a host notice).
        caller, second, voter, leaver = sorted((label for label in LABELS if label != fr),
                                               key=lambda label: label != "P0")
        seen["labels"] = {"fr": fr, "caller": caller, "second": second, "voter": voter, "leaver": leaver}
        classic = lobby_of(names[fr]).classic_round
        lobby = lobby_of(names[fr])
        everybody = list(LABELS)
        for label, (dx, dy) in zip(LABELS, [(-60, 0), (60, 0), (0, -60), (40, 45), (-40, 45)]):
            put(names[label], free_place_at(CENTRE, 60, near=(CENTRE[0] + dx, CENTRE[1] + dy)))
        time.sleep(UNLOCK_SECONDS + 1.5)  # every page unlocks the button by its own clock
        browser.wait(caller, "window.__button.frame && window.__button.frame.visible", timeout=10000)

        # 1. Emergency meeting: votes in the discussion, a leave that brings Skip to 75 %.
        results_before = counts(browser, everybody, "result")
        call_at_button(browser, caller, everybody)
        seen["m1_first"] = states_of(browser, caller)[-1]
        seen["m1_window"] = {label: window(browser, label) for label in everybody}
        seen["m1_sizes"] = {}
        for width, height in SIZES:
            browser.call("viewport", label=caller, width=width, height=height)
            time.sleep(0.4)
            seen["m1_sizes"][f"{width}x{height}"] = window(browser, caller)
            seen["m1_sizes"][f"{width}x{height}"]["living_line"] = browser.js(caller, LIVING_LINE)
            shot(browser, caller, f"1a_emergency_discussion_{width}x{height}")
        browser.call("viewport", label=caller, width=1280, height=800)
        time.sleep(0.3)

        act(browser, caller, vote_selector(names[fr]), everybody, lobby)
        seen["m1_voted"] = {label: window(browser, label)["votes"] for label in everybody}
        act(browser, caller, vote_selector(names[voter]), everybody, lobby)
        seen["m1_changed"] = {label: window(browser, label)["votes"] for label in everybody}
        shot(browser, voter, "1b_vote_changed_seen_by_voter")
        act(browser, caller, vote_selector(names[voter]), everybody, lobby)
        seen["m1_withdrawn"] = {label: window(browser, label)["votes"] for label in everybody}
        seen["m1_server_votes"] = dict(lobby.meeting["votes"])

        for label in (fr, caller, voter):
            act(browser, label, "#classic-skip-discussion", everybody, lobby)
        seen["m1_three_skips"] = {"phase": lobby.meeting["phase"], "window": window(browser, second)}
        shot(browser, second, "1c_three_of_five_skip")
        stayers = [label for label in LABELS if label != leaver]
        browser.call("click", label=leaver, selector="#classic-meeting-leave")
        wait_for_more(browser, stayers, "result", results_before)
        seen["m1_result"] = {label: states_of(browser, label, "result")[-1] for label in stayers}
        seen["m1_server"] = {"applied": lobby.meeting is None or lobby.meeting.get("applied"),
                             "eliminated": sorted(classic.eliminated), "phase": classic.phase}
        shot(browser, second, "1d_result_after_the_leave")
        closed(browser, stayers)
        seen["m1_results_sent"] = {label: n - results_before[label]
                                   for label, n in counts(browser, stayers, "result").items()}

        # S-218: after the meeting the button is locked again for 45 s: grey, and E does nothing.
        ended = time.monotonic()
        stand(browser, second, (CENTRE[0], CENTRE[1] + 10))
        browser.wait(second, "window.__button.frame && window.__button.frame.visible === false", timeout=5000)
        seen["m1_locked"] = {"frame": browser.js(second, "window.__button.frame"),
                             "has_e": browser.js(second, HAS_E_EMERGENCY),
                             "press": press_and_watch(browser, second)}
        shot(browser, second, "1e_button_locked_after_the_meeting")
        browser.wait(second, HAS_E_EMERGENCY, timeout=60000)
        seen["m1_unlocked_after"] = time.monotonic() - ended
        seen["m1_unlocked_frame"] = browser.js(second, "window.__button.frame")
        shot(browser, second, "1f_button_unlocked_45_s_later")

        # 2. Second emergency meeting: Skip by 75 % in the discussion.
        results_before = counts(browser, stayers, "result")
        call_at_button(browser, second, stayers)
        kept_before = {label: position(names[label]) for label in stayers}
        act(browser, voter, vote_selector(names[fr]), stayers, lobby)
        seen["m2_voted"] = window(browser, fr)["votes"]
        for label in (fr, caller):
            act(browser, label, "#classic-skip-discussion", stayers, lobby)
        browser.call("click", label=voter, selector="#classic-skip-discussion")
        wait_for_more(browser, stayers, "result", results_before)
        seen["m2_result"] = states_of(browser, second, "result")[-1]
        seen["m2_phases"] = [state["phase"] for state in states_of(browser, second)][-6:]
        shot(browser, second, "2a_result_by_skip")
        closed(browser, stayers)
        seen["m2_results_sent"] = {label: n - results_before[label]
                                   for label, n in counts(browser, stayers, "result").items()}
        seen["m2_positions"] = {"before": kept_before, "after": {label: position(names[label]) for label in stayers},
                                "told": {label: own_place_on_page(browser, label) for label in stayers}}

        # 3. The Free Rider fails the voter; the second reports: a report meeting.
        clock.skip(FAIL_COOLDOWN_SECONDS + 1)  # the cooldown starts again after a meeting
        fr_place = free_place_at(CENTRE, 60, near=(CENTRE[0], CENTRE[1] - 60))
        put(names[voter], (fr_place[0] + 3, fr_place[1]))
        put(names[fr], fr_place)
        standing_still(names[fr])
        press_fail(browser, fr)
        failed(browser, fr, names[voter])
        sheet = browser.js(fr, f"""window.__received.filter((r) => r.m.type === 'classic_fail'
            && r.m.target_id === {json.dumps(names[voter])}).pop().m.position""")
        put(names[fr], free_place_at(CENTRE, 60, near=(CENTRE[0] + 60, CENTRE[1])))
        put(names[voter], free_place_at(CENTRE, 60, near=(CENTRE[0] - 40, CENTRE[1] + 45)))
        stand(browser, second, (sheet["x"], sheet["y"]))
        browser.wait(second, "!document.querySelector('.report-button').hidden", timeout=5000)
        discussions_before = counts(browser, stayers, "discussion")
        results_before = counts(browser, stayers, "result")
        browser.call("press", label=second, key="KeyR")
        wait_for_more(browser, stayers, "discussion", discussions_before)
        for label in stayers:
            browser.wait(label, "!document.getElementById('classic-meeting').hidden")
        time.sleep(0.3)
        kept_before = {label: position(names[label]) for label in stayers}
        seen["m3_first"] = states_of(browser, second)[-1]
        seen["m3_window"] = {label: window(browser, label) for label in stayers}
        shot(browser, second, "3a_report_discussion")
        clock.skip(DISCUSSION_SECONDS + 1)
        wait_for_phase(browser, stayers, "voting", 1)
        clock.skip(VOTE_SECONDS + 1)
        wait_for_more(browser, stayers, "result", results_before)
        seen["m3_result"] = states_of(browser, second, "result")[-1]
        closed(browser, stayers)
        seen["m3_positions"] = {"before": kept_before, "after": {label: position(names[label]) for label in stayers},
                                "told": {label: own_place_on_page(browser, label) for label in stayers}}

        # 4. The caller's call is used; the Free Rider, who has not called, sees "E Emergency"
        # once the 45 s after the report meeting are over (S-218).
        stand(browser, fr, (CENTRE[0] - 20, CENTRE[1] + 10))
        seen["m3_locked_has_e"] = browser.js(fr, HAS_E_EMERGENCY)
        browser.wait(fr, HAS_E_EMERGENCY, timeout=60000)
        seen["unused_has_e_emergency"] = browser.js(fr, HAS_E_EMERGENCY)
        put(names[fr], free_place_at(CENTRE, 60, near=(CENTRE[0] + 60, CENTRE[1])))
        stand(browser, caller, (CENTRE[0], CENTRE[1] + 10))
        time.sleep(0.3)
        seen["used_button"] = use_button(browser, caller)
        seen["used_has_e_emergency"] = browser.js(caller, HAS_E_EMERGENCY)
        seen["used_bypass"] = bypass(browser, caller)
        shot(browser, caller, "4a_used_call_refused")

        # 5. S-215: the Free Rider calls; once all three living have voted, 10 seconds are left.
        put(names[fr], (CENTRE[0] - 20, CENTRE[1] + 10))
        put(names[caller], free_place_at(CENTRE, 60, near=(CENTRE[0] - 60, CENTRE[1])))
        call_at_button(browser, fr, stayers)
        clock.skip(5)  # 40 s of discussion are left
        time.sleep(1.2)
        for last_voter, target in ((caller, fr), (second, fr), (fr, caller)):
            act(browser, last_voter, vote_selector(names[target]), stayers, lobby)
        seen["m5_server"] = {"deadline_left": lobby.meeting["deadline"] - main.seconds_now(),
                             "ends_by": lobby.meeting.get("ends_by")}
        seen["m5_shortened"] = {label: states_of(browser, label)[-1] for label in stayers}
        seen["m5_clock_text"] = {label: browser.js(label, TIME_LEFT_TEXT) for label in stayers}
        shot(browser, voter, "5a_ghost_sees_ten_seconds")
        before = counts(browser, stayers, "result")
        clock.skip(10)
        wait_for_more(browser, stayers, "result", before)
        seen["m5_result"] = states_of(browser, second, "result")[-1]
        seen["m5_phases"] = [state["phase"] for state in states_of(browser, second)][-4:]
        for label in stayers:
            browser.wait(label, "!document.getElementById('classic-end-screen').hidden", timeout=20000)
        seen["problems"] = browser.close()
        browser = None
    finally:
        if browser is not None:
            try:
                seen["problems"] = browser.close()
            except Exception:  # noqa: BLE001 (the play failed already)
                pass
        if SCREENSHOTS:
            Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
            (Path(SCREENSHOTS) / "seen.json").write_text(json.dumps(seen, indent=1, default=str))
    seen["names"] = names
    return seen


def test_the_emergency_discussion_offers_voting_and_skip_on_every_page(played):
    assert played["m1_first"]["reason"] == "emergency" and played["m1_first"]["phase"] == "discussion"
    for label, shown in played["m1_window"].items():
        assert shown["open"] and shown["votesShown"] and shown["skipShown"], label
        assert len(shown["votes"]) == 5
        assert shown["skipText"] == "0 / 4 Skip votes to end voting early."
        assert shown["hint"] == "Living players can chat during the discussion."


@pytest.mark.parametrize("size", [f"{w}x{h}" for w, h in SIZES])
def test_the_emergency_discussion_fits_the_window(played, size):
    shown = played["m1_sizes"][size]
    assert shown["inside"] == {"skip": True, "votes": True, "input": True, "send": True}, shown
    assert shown["hintFits"], shown
    assert len(set(shown["widths"])) == 1, shown["widths"]
    assert shown["noPageScroll"]


@pytest.mark.parametrize("size", [f"{w}x{h}" for w, h in SIZES])
def test_the_living_line_names_everybody_or_says_how_many_more(played, size):
    # The compact meeting picture has one row for the names: instead of
    # cutting names off after a comma, the row ends in "+N more".
    line = played["m1_sizes"][size]["living_line"]
    text = "".join(part["text"] for part in line)
    assert not text.rstrip().endswith(","), text
    names = [name for name in text.split(", ") if name and not name.startswith("+")]
    more = text.rsplit("+", 1)[1] if "+" in text else None
    hidden = int(more.split(" ")[0]) if more else 0
    assert more is None or more.endswith(" more"), text
    assert len(names) + hidden == 5 and names, text
    assert all(part["right"] <= part["limit"] for part in line), line


def test_a_vote_in_the_emergency_discussion_is_changed_and_taken_back_on_every_page(played):
    names, labels = played["names"], played["labels"]
    caller, fr, voter = names[labels["caller"]], names[labels["fr"]], names[labels["voter"]]

    def counts(votes):
        return {vote["target"]: vote["count"] for vote in votes}

    for label in LABELS:
        voted, changed, withdrawn = (counts(played[key][label]) for key in ("m1_voted", "m1_changed", "m1_withdrawn"))
        assert voted[fr] == "1" and sum(map(int, voted.values())) == 1
        assert changed[fr] == "0" and changed[voter] == "1" and sum(map(int, changed.values())) == 1
        assert set(withdrawn.values()) == {"0"}
    assert {v["target"]: v["label"] for v in played["m1_changed"][labels["second"]]}[voter] == f"{voter} — votes: {caller}"
    assert played["m1_server_votes"] == {}


def test_a_leave_that_brings_skip_to_75_percent_ends_the_emergency_meeting_at_once(played):
    names, labels = played["names"], played["labels"]
    assert played["m1_three_skips"]["phase"] == "discussion"
    assert played["m1_three_skips"]["window"]["skipText"] == "3 / 4 Skip votes to end voting early."
    for label, result in played["m1_result"].items():
        assert result["ejected_id"] is None and result["tie"] is False, label
        assert names[labels["leaver"]] not in result["living"]
    assert played["m1_server"]["eliminated"] == [names[labels["leaver"]]]
    assert played["m1_server"]["phase"] == "round"
    assert set(played["m1_results_sent"].values()) == {1}  # the result reached every page once


def test_skip_by_75_percent_ends_the_second_emergency_meeting_in_its_discussion(played):
    names, labels = played["names"], played["labels"]
    assert {v["target"]: v["count"] for v in played["m2_voted"]}[names[labels["fr"]]] == "1"
    result = played["m2_result"]
    assert result["reason"] == "emergency" and result["ejected_id"] is None
    assert result["trigger_player_id"] == names[labels["second"]]
    assert set(played["m2_results_sent"].values()) == {1}
    assert result["vote_targets"] == {}  # the voter's Skip took his vote back
    assert len(result["skip_voted"]) == 3
    assert "voting" not in played["m2_phases"]  # it never reached the vote phase


def test_the_report_meeting_offers_the_same_controls(played):
    names, labels = played["names"], played["labels"]
    assert played["m3_first"]["reason"] == "report" and played["m3_first"]["phase"] == "discussion"
    assert played["m3_first"]["trigger_player_id"] == names[labels["second"]]
    for label, shown in played["m3_window"].items():
        assert shown["votesShown"] and shown["skipShown"], label
        assert len(shown["votes"]) == 3
    assert played["m3_result"]["ejected_id"] is None


@pytest.mark.parametrize("meeting", ["m2_positions", "m3_positions"], ids=["emergency", "report"])
def test_everybody_goes_on_from_where_they_stood_and_the_page_shows_no_jump(played, meeting):
    # S-213: nobody is moved by the meeting, and each page was last told its own old place.
    kept = played[meeting]
    assert kept["after"] == kept["before"]
    for label, place in kept["before"].items():
        assert kept["told"][label] == pytest.approx(list(place)), label


def test_after_a_meeting_the_button_is_locked_for_45_s_then_offered_again(played):
    # S-218: grey (drawn, but not usable), no "E Emergency", E sends nothing.
    locked = played["m1_locked"]
    assert locked["frame"]["visible"] is False and locked["frame"]["drawn"] is True
    assert locked["has_e"] is False
    assert locked["press"]["sent"] == 0 and set(locked["press"]["meetings"].values()) == {0}
    assert 42 <= played["m1_unlocked_after"] <= 50
    assert played["m1_unlocked_frame"]["visible"] is True
    assert played["m3_locked_has_e"] is False  # after a report meeting too


def test_a_used_emergency_call_offers_nothing_and_is_refused(played):
    assert played["unused_has_e_emergency"] is True  # the button itself is still there for others
    assert played["used_has_e_emergency"] is False
    refused = played["used_bypass"]
    assert [error["message"] for error in refused["errors"]] == [CALL_REFUSED]
    assert refused["server_meeting"] is False
    assert set(refused["meetings"].values()) <= {0}


def test_once_everybody_voted_every_page_shows_ten_seconds_and_the_result_follows(played):
    names, labels = played["names"], played["labels"]
    assert played["m5_server"]["deadline_left"] == pytest.approx(10, abs=1.5)
    for label, state in played["m5_shortened"].items():
        assert state["phase"] == "discussion" and state["seconds_left"] in (9, 10), label
        assert len(state["vote_targets"]) == 3
    # The ghost (the failed voter) sees the same clock as the living.
    assert played["m5_shortened"][labels["voter"]]["seconds_left"] == played["m5_shortened"][labels["fr"]]["seconds_left"]
    assert all(text in ("Time left: 10 s", "Time left: 9 s") for text in played["m5_clock_text"].values()), played["m5_clock_text"]
    assert played["m5_result"]["ejected_id"] == names[labels["fr"]]
    assert "voting" not in played["m5_phases"]  # it ended from the discussion, without a vote phase


def test_no_console_error_or_warning_on_any_page(played):
    assert played["problems"] == []
