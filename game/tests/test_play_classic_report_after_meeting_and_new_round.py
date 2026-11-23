"""Play test in Chromium: the Report button after a meeting, and a new round after a vote.

Five guests play Classic in real Chromium pages (Playwright, driven through
`play_classic_report_after_meeting_and_new_round_in_browser.js`) against the
real server with its real tick, run in this process. Every player walks
with the walk keys only; nobody is put anywhere. To meet exactly, players
walk until a wall stops them: whoever holds the same keys from the same
place stops on the same point. The test sets the server's clock forward
instead of waiting 15 seconds for the fail cooldown and 75 for a meeting.

Round 1 (Laurin's Report-button test, tests/test_classic_report_button_area3.py,
played for real): the Free Rider fails one High Performer at place A and,
after the cooldown, a second one at place B. A living player reports sheet A;
the meeting ends with Skip. Afterwards both sheets are still drawn on every
page that was told them (S-150; since S-202 the Free Rider and the ghosts
get both, a living High Performer only those that came into his sight),
sheet A cannot be reported again, and the living player who
walks to sheet B gets the Report button and starts a second meeting. In it
the Free Rider is voted out: every page gets the result, then the end screen
(S-166).

Round 2 (Laurin's new-round test, tests/test_classic_new_round_area3.py,
played for real): the host starts a new Classic round from the end screen.
No page shows a meeting window, a vote list, a vote result or an F-sheet of
the old round; everybody walks; a report opens a fresh meeting window
without the old votes.

The rejected actions on the way show the texts of DESIGN.md, section 9 (and
protocol.REJECTIONS). No page may log an error or a warning. Skipped when
Node, Playwright or Chromium is missing. Screenshots go to the folder in
CLASSIC_REPORT_SCREENSHOTS, if that is set.
"""

import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

from server import protocol
from server.classic.sheets import sheet_order
from server.main import app
from test_play_hiding import (  # noqa: F401 (server is a fixture; quiet_tick replaces the one of conftest.py)
    NODE,
    hold,
    lobby_of,
    node_environment,
    playwright_works,
    press_fail,
    quiet_tick,
    server,
    standing_still,
    wait_until,
)

BROWSER_SCRIPT = Path(__file__).with_name("play_classic_report_after_meeting_and_new_round_in_browser.js")
SCREENSHOTS = os.environ.get("CLASSIC_REPORT_SCREENSHOTS")
LABELS = ["P0", "P1", "P2", "P3", "P4"]
# Far beyond any wall: "hold the key until a wall stops the player".
WALL = 10_000
UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)
REPORT_REJECTED = protocol.REJECTIONS["report_rejected"]
VOTE_REJECTED = protocol.REJECTIONS["vote_rejected"]
# Long enough for a page to draw a few frames after a message.
SETTLE = 0.3
COOLDOWN_TEXT = re.compile(r"You can fail again in \d+ seconds?\.")

pytestmark = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


# ---- Chromium -----------------------------------------------------------


class Browser:
    """The five Chromium pages, driven through the browser script."""

    def __init__(self, base):
        self._node = subprocess.Popen(
            [NODE, str(BROWSER_SCRIPT), base], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, env=node_environment(),
        )
        self.names = {}  # label -> the guest name the server gave

    def call(self, cmd, **arguments):
        self._node.stdin.write(json.dumps({"cmd": cmd, **arguments}) + "\n")
        self._node.stdin.flush()
        line = self._node.stdout.readline()
        assert line, "the browser driver stopped"
        answer = json.loads(line)
        if "error" in answer:
            raise AssertionError(f"{cmd} failed in the browser: {answer['error']}")
        return answer["ok"]

    def open(self, label):
        self.names[label] = self.call("open", label=label)
        return self.names[label]

    def js(self, label, expression):
        return self.call("eval", label=label, js=expression)

    def wait(self, label, expression, timeout=15000):
        return self.call("wait", label=label, js=expression, timeout=timeout)

    def shot(self, label, name):
        if SCREENSHOTS:
            Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
            self.call("screenshot", label=label, path=str(Path(SCREENSHOTS) / f"{name}.png"))

    def close(self):
        problems = self.call("problems")
        self.call("quit")
        self._node.stdin.close()
        self._node.wait(timeout=30)
        return problems

    # What a page shows, received and sent

    def screen(self, label):
        """What the player sees of the meeting, the end screen, the sheets and the buttons."""
        return self.js(label, """(() => {
            const shown = (id) => {
                const element = document.getElementById(id);
                return Boolean(element) && !element.hidden && element.getClientRects().length > 0;
            };
            const report = document.querySelector('.report-button');
            return {
                meeting: shown('classic-meeting'),
                voteList: shown('classic-vote-options'),
                voteButtons: Array.from(document.querySelectorAll('#classic-vote-players button'))
                    .filter((button) => button.getClientRects().length > 0)
                    .map((button) => ({ target: button.dataset.targetId, voters: Number(button.querySelector('.classic-vote-count').textContent),
                                          selected: button.classList.contains('classic-vote-player-selected') })),
                voteResult: shown('classic-vote-result') ? document.getElementById('classic-vote-result').textContent : null,
                skipStatus: shown('classic-skip-options') ? document.getElementById('classic-skip-status').textContent : null,
                endScreen: shown('classic-end-screen'),
                roleCard: shown('classic-role-card'),
                report: Boolean(report) && !report.hidden && report.getClientRects().length > 0,
                sheets: Game.world.bloodSheetIds(),
                sheetsDrawn: window.__sheetsDrawn.slice(-5),
            };
        })()""")

    def last(self, label, kind):
        return self.js(label, f"(window.__received.filter((r) => r.m.type === '{kind}').pop() || {{}}).m || null")

    def count(self, label, kind):
        return self.js(label, f"window.__received.filter((r) => r.m.type === '{kind}').length")

    def sent(self, label, kind):
        return self.js(label, f"window.__sent.filter((s) => s.m.type === '{kind}').length")

    def bypass(self, label, message):
        """Send a message as a changed page would, and return the answer and the text shown."""
        errors_before = self.count(label, "error")
        meetings_before = self.count(label, "meeting_state")
        shown_before = self.js(label, "window.__shown.length")
        self.js(label, f"window.__socket.send(JSON.stringify({json.dumps(message)}))")
        # The answer is an error, or (for an action the server accepts) a meeting.
        self.wait(label, f"window.__received.filter((r) => r.m.type === 'error').length > {errors_before} "
                         f"|| window.__received.filter((r) => r.m.type === 'meeting_state').length > {meetings_before}")
        time.sleep(0.2)  # the message line shows the text
        answer = self.js(label, f"window.__received.filter((r) => r.m.type === 'error').slice({errors_before}).map((r) => r.m)")
        shown = self.js(label, f"window.__shown.slice({shown_before}).map((s) => s.text)")
        return {"errors": answer, "shown": shown}


# ---- Playing ------------------------------------------------------------


def position(name):
    return lobby_of(name).walkers.position_of(name)


def walk(browser, label, name, *steps):
    """Walk with the walk keys: each step is a direction and how far on its axis (WALL: until stopped)."""
    for direction, target in steps:
        if target == WALL:
            target = WALL * sum(direction)  # far beyond the map on the side the key walks to
        hold(browser, label, name, direction, target)
    return standing_still(name)


def wait_for_meeting(browser, phase, count):
    for label in LABELS:
        browser.wait(label, f"window.__received.filter((r) => r.m.type === 'meeting_state' && r.m.phase === '{phase}').length >= {count}")


def wait_meeting_closed(browser):
    for label in LABELS:
        browser.wait(label, "document.getElementById('classic-meeting').hidden", timeout=5000)


def read_role_cards(browser, round_number):
    for label in LABELS:
        browser.wait(label, f"window.__received.filter((r) => r.m.type === 'classic_role').length >= {round_number}")
    roles = {}
    for label in LABELS:
        browser.wait(label, "!document.getElementById('classic-role-card').hidden")
        roles[label] = browser.js(label, "document.getElementById('classic-role-name').textContent")
    return roles


def wait_role_cards_closed(browser):
    for label in LABELS:
        browser.wait(label, "document.getElementById('classic-role-card').hidden", timeout=15000)
        browser.js(label, "document.activeElement && document.activeElement.blur()")


def skip_by(browser, labels):
    for label in labels:
        before = browser.count(label, "meeting_state")
        browser.call("click", label=label, selector="#classic-skip-discussion")
        browser.wait(label, f"window.__received.filter((r) => r.m.type === 'meeting_state').length > {before}")


def vote(browser, label, target_name):
    before = browser.count(label, "meeting_state")
    browser.call("click", label=label, selector=f'#classic-vote-players button[data-target-id="{target_name}"]')
    browser.wait(label, f"window.__received.filter((r) => r.m.type === 'meeting_state').length > {before}")


def messages_of_round(browser, label, round_number):
    """Everything the page received from the start of the round (its classic_role) to its end."""
    return browser.js(label, f"""(() => {{
        const all = window.__received.map((r) => r.m);
        const starts = all.map((m, i) => m.type === 'classic_role' ? i : -1).filter((i) => i >= 0);
        const from = starts[{round_number - 1}];
        const next = starts[{round_number}];
        return all.slice(from, next === undefined ? all.length : next);
    }})()""")


def play_round_one(browser, clock, seen):
    names = browser.names
    roles = read_role_cards(browser, 1)
    fr = next(label for label, role in roles.items() if role == "Free Rider")
    v1, v2, reporter, other = [label for label in LABELS if label != fr]
    seen["round1"] = {"fr": fr, "v1": v1, "v2": v2, "reporter": reporter, "other": other}
    classic = lobby_of(names[fr]).classic_round
    assert classic.roles[names[fr]] == "FR"
    wait_role_cards_closed(browser)

    # The High Performers spread out; the Free Rider and his first victim
    # walk down until the wall of Pingo Doce stops them: place A.
    walk(browser, other, names[other], (LEFT, WALL))
    walk(browser, reporter, names[reporter], (UP, WALL))
    walk(browser, v2, names[v2], (RIGHT, WALL), (UP, WALL))
    place_a = walk(browser, v1, names[v1], (DOWN, WALL))
    assert walk(browser, fr, names[fr], (DOWN, WALL)) == place_a
    press_fail(browser, fr)
    wait_until(lambda: names[v1] in classic.eliminated, "the first fail")
    sheet_a = next(sheet for sheet, place in classic.f_sheets.items() if tuple(place) == tuple(place_a))
    seen["cooldown_fail"] = browser.bypass(fr, {"type": "fail"})

    # After the cooldown, at place B (right, then up into the corner).
    clock.skip(15)
    place_b = position(names[v2])
    assert walk(browser, fr, names[fr], (UP, place_a[1] - 90), (RIGHT, WALL), (UP, WALL)) == place_b
    press_fail(browser, fr)
    wait_until(lambda: names[v2] in classic.eliminated, "the second fail")
    sheet_b = next(sheet for sheet in classic.f_sheets if sheet != sheet_a)
    seen["sheet_ids"] = [sheet_a, sheet_b]
    # S-202: the Free Rider and the ghosts are told both places; a living
    # High Performer only the sheets that came into his sight.
    seen["knows_both"] = [fr, v1, v2]
    # The new ghost is sent sheet A by the next tick.
    wait_until(lambda: len(classic.sheets_told.get(names[v2], ())) == 2, "sheet A for the new ghost")
    seen["told_before_report"] = sheets_told(browser, classic)
    for label in LABELS:
        browser.wait(label, f"Game.world.bloodSheetIds().length === {len(seen['told_before_report'][label])}")
    time.sleep(SETTLE)  # a few frames: the page draws the new sheet
    seen["before_report"] = {label: browser.screen(label) for label in LABELS}

    # The reporter walks down to sheet A and reports it.
    assert walk(browser, reporter, names[reporter], (DOWN, WALL)) == place_a
    browser.wait(reporter, "!document.querySelector('.report-button').hidden")
    seen["at_a"] = {"reporter": browser.screen(reporter), "ghost_v1": browser.screen(v1)}
    browser.shot(reporter, "01_reporter_at_sheet_a")
    browser.js(reporter, "document.querySelector('.report-button').click()")
    wait_for_meeting(browser, "discussion", 1)
    time.sleep(SETTLE)  # a few frames: the page draws and sets its buttons
    seen["meeting1"] = {label: browser.screen(label) for label in LABELS}
    seen["meeting1_state"] = browser.last(reporter, "meeting_state")
    browser.shot(other, "02_meeting_1")
    seen["ghost_vote"] = browser.bypass(v1, {"type": "vote", "target_id": names[fr]})

    # The living all choose Skip: the meeting ends at once, nobody goes.
    skip_by(browser, [fr, reporter, other])
    wait_for_meeting(browser, "result", 1)
    seen["meeting1_result"] = browser.last(other, "meeting_state")
    wait_meeting_closed(browser)
    time.sleep(SETTLE)  # a few frames: the page draws and sets its buttons
    seen["after_meeting1"] = {label: browser.screen(label) for label in LABELS}
    seen["told_after_meeting1"] = sheets_told(browser, classic)

    # Sheet A cannot be reported again: the reporter stands on it (walking
    # down to the wall again, wherever the meeting left him).
    assert walk(browser, reporter, names[reporter], (DOWN, WALL)) == place_a
    time.sleep(SETTLE)  # a few frames: the page draws and sets its buttons
    seen["again_at_a"] = browser.screen(reporter)
    reports_sent = browser.sent(reporter, "report")
    browser.call("press", label=reporter, key="KeyR")
    time.sleep(SETTLE)  # a few frames: the page draws and sets its buttons
    seen["again_at_a_key_sent"] = browser.sent(reporter, "report") - reports_sent
    here = position(names[reporter])
    seen["again_at_a_bypass"] = browser.bypass(
        reporter, {"type": "report", "sheet_id": sheet_a, "position": {"x": here[0], "y": here[1]}})
    seen["far_report_bypass"] = browser.bypass(
        reporter, {"type": "report", "sheet_id": sheet_b, "position": {"x": place_b[0], "y": place_b[1]}})

    # The reporter walks to sheet B: the button lights up, R starts meeting 2.
    assert walk(browser, reporter, names[reporter], (UP, place_a[1] - 90), (RIGHT, WALL), (UP, WALL)) == place_b
    browser.wait(reporter, "!document.querySelector('.report-button').hidden")
    seen["at_b"] = {"reporter": browser.screen(reporter), "ghost_v2": browser.screen(v2)}
    browser.shot(reporter, "04_reporter_at_sheet_b")
    browser.shot(other, "03_after_meeting_1_sheet_a_still_drawn")
    browser.call("press", label=reporter, key="KeyR")
    wait_for_meeting(browser, "discussion", 2)
    time.sleep(SETTLE)  # a few frames: the page draws and sets its buttons
    seen["meeting2"] = {label: browser.screen(label) for label in LABELS}
    seen["meeting2_state"] = browser.last(other, "meeting_state")

    # The Free Rider is voted out when the vote's time is over.
    vote(browser, reporter, names[fr])
    vote(browser, other, names[fr])
    vote(browser, fr, names[reporter])
    browser.shot(other, "05_meeting_2_votes")
    seen["end_marks"] = {label: browser.js(label, "performance.now()") for label in LABELS}
    clock.skip(75)
    for label in LABELS:
        browser.wait(label, "!document.getElementById('classic-end-screen').hidden")
    browser.shot(other, "06_end_screen")
    seen["end"] = {label: browser.screen(label) for label in LABELS}
    seen["end_changes"] = {
        label: browser.js(label, f"window.__changes.filter((c) => c.t >= {seen['end_marks'][label]})") for label in LABELS
    }
    seen["end_messages"] = {
        label: browser.js(label, f"""window.__received.filter((r) => r.t >= {seen['end_marks'][label]}
            && ['meeting_state', 'classic_result'].includes(r.m.type)).map((r) => [r.m.type, r.m.phase || null])""")
        for label in LABELS
    }
    # Whether "New Round" is hidden (not in the layout): only the host sees it.
    seen["new_round_button"] = {
        label: browser.js(label, "document.getElementById('classic-new-round').offsetParent === null") for label in LABELS
    }


def sheets_told(browser, classic):
    """label -> the ids of the sheets the server has told this page (S-202), in issue order."""
    return {
        label: sorted(classic.sheets_told.get(name, ()), key=sheet_order)
        for label, name in browser.names.items()
    }


def play_round_two(browser, clock, seen):
    names = browser.names
    browser.call("click", label="P0", selector="#classic-new-round")
    roles = read_role_cards(browser, 2)
    # Right after the countdown, while the role card is shown.
    seen["round2_start"] = {label: browser.screen(label) for label in LABELS}
    wait_role_cards_closed(browser)
    time.sleep(SETTLE)  # a few frames: the page draws and sets its buttons
    seen["round2_running"] = {label: browser.screen(label) for label in LABELS}
    browser.shot("P0", "07_round_2_started")
    fr = next(label for label, role in roles.items() if role == "Free Rider")
    victim, reporter, left, right = [label for label in LABELS if label != fr]
    seen["round2"] = {"fr": fr, "victim": victim, "reporter": reporter, "left": left}
    classic = lobby_of(names[fr]).classic_round
    spawn = {label: position(names[label]) for label in LABELS}

    # Everybody walks; the Free Rider fails his victim at place A again.
    walk(browser, reporter, names[reporter], (UP, WALL))
    walk(browser, left, names[left], (LEFT, WALL))
    walk(browser, right, names[right], (RIGHT, WALL))
    place_a = walk(browser, victim, names[victim], (DOWN, WALL))
    assert walk(browser, fr, names[fr], (DOWN, WALL)) == place_a
    seen["round2_walked"] = {label: position(names[label]) != spawn[label] for label in LABELS}
    press_fail(browser, fr)
    wait_until(lambda: names[victim] in classic.eliminated, "the fail of round 2")
    seen["round2_sheet"] = next(iter(classic.f_sheets))

    # A report opens a fresh meeting window on every page.
    assert walk(browser, reporter, names[reporter], (DOWN, WALL)) == place_a
    browser.wait(reporter, "!document.querySelector('.report-button').hidden")
    meetings_before = {label: browser.count(label, "meeting_state") for label in LABELS}
    browser.call("press", label=reporter, key="KeyR")
    for label in LABELS:
        browser.wait(label, f"window.__received.filter((r) => r.m.type === 'meeting_state').length > {meetings_before[label]}")
        browser.wait(label, "!document.getElementById('classic-meeting').hidden")
    time.sleep(SETTLE)  # a few frames: the page draws and sets its buttons
    seen["round2_meeting"] = {label: browser.screen(label) for label in LABELS}
    seen["round2_meeting_state"] = {label: browser.last(label, "meeting_state") for label in LABELS}
    browser.shot(left, "08_round_2_meeting")

    # It ends with Skip.
    living = [label for label in LABELS if label != victim]
    skip_by(browser, living[:3])
    wait_meeting_closed(browser)


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
        browser.call("click", label="P0", selector='#lobby-modes button[data-mode="classic"]')
        wait_until(lambda: lobby_of(names["P0"]).mode == "classic", "Classic chosen")
        browser.call("click", label="P0", selector="#lobby-start")
        play_round_one(browser, clock, seen)
        play_round_two(browser, clock, seen)
        seen["rounds"] = {label: [messages_of_round(browser, label, 1), messages_of_round(browser, label, 2)] for label in LABELS}
        seen["names"] = dict(names)
    finally:
        seen["problems"] = browser.close()
    return seen


# ---- Round 1: the Report button after a meeting --------------------------


def test_both_fails_leave_a_sheet_on_every_page_that_was_told_them(played):
    # S-202: the Free Rider and both ghosts know both places; each living
    # High Performer draws exactly the sheets the server told him.
    for label in played["knows_both"]:
        assert played["told_before_report"][label] == played["sheet_ids"], label
    for label, screen in played["before_report"].items():
        assert sorted(screen["sheets"], key=sheet_order) == played["told_before_report"][label], label
        assert screen["sheetsDrawn"][-1] == len(played["told_before_report"][label]), label


def test_the_living_reporter_next_to_sheet_a_sees_report_and_the_ghost_on_it_does_not(played):
    assert played["at_a"]["reporter"]["report"] is True
    assert played["at_a"]["ghost_v1"]["report"] is False


def test_reporting_sheet_a_opens_the_meeting_on_all_five_pages(played):
    state = played["meeting1_state"]
    assert (state["reason"], state["reported_sheet_id"]) == ("report", played["sheet_ids"][0])
    assert all(screen["meeting"] for screen in played["meeting1"].values())


def test_after_the_meeting_both_sheets_are_still_drawn_on_every_page_that_was_told_them(played):
    assert played["meeting1_result"]["ejected_id"] is None
    for label in played["knows_both"]:
        assert played["told_after_meeting1"][label] == played["sheet_ids"], label
    for label, screen in played["after_meeting1"].items():
        assert screen["meeting"] is False, label
        # S-202: a page keeps every sheet it was told (the reporter stood at sheet A).
        assert sorted(screen["sheets"], key=sheet_order) == played["told_after_meeting1"][label], label
        assert screen["sheetsDrawn"][-1] == len(played["told_after_meeting1"][label]), label
    assert played["sheet_ids"][0] in played["told_after_meeting1"][played["round1"]["reporter"]]


def test_sheet_a_cannot_be_reported_again(played):
    assert played["again_at_a"]["report"] is False
    assert played["again_at_a_key_sent"] == 0
    answer = played["again_at_a_bypass"]
    assert [error["code"] for error in answer["errors"]] == ["report_rejected"]
    assert REPORT_REJECTED in answer["shown"]


def test_a_report_of_a_far_sheet_with_a_made_up_position_is_rejected(played):
    answer = played["far_report_bypass"]
    assert [error["code"] for error in answer["errors"]] == ["report_rejected"]
    assert REPORT_REJECTED in answer["shown"]


def test_next_to_sheet_b_the_living_player_sees_report_and_starts_a_second_meeting(played):
    assert played["at_b"]["reporter"]["report"] is True
    assert played["at_b"]["ghost_v2"]["report"] is False
    state = played["meeting2_state"]
    assert (state["phase"], state["reason"], state["reported_sheet_id"]) == ("discussion", "report", played["sheet_ids"][1])
    assert (state["messages"], state["vote_targets"], state["skip_voted"]) == ([], {}, [])
    assert all(screen["meeting"] for screen in played["meeting2"].values())


def test_a_ghost_cannot_vote_and_reads_why(played):
    answer = played["ghost_vote"]
    assert [error["code"] for error in answer["errors"]] == ["vote_rejected"]
    assert VOTE_REJECTED in answer["shown"]


def test_failing_during_the_cooldown_tells_the_seconds_left(played):
    answer = played["cooldown_fail"]
    assert [error["code"] for error in answer["errors"]] == ["fail_rejected"]
    assert any(COOLDOWN_TEXT.fullmatch(text) for text in answer["shown"]), answer


# ---- Round 1 ends by a vote ------------------------------------------------


def test_every_page_gets_the_vote_result_before_the_end_screen(played):
    fr_name = played["names"][played["round1"]["fr"]]
    for label in LABELS:
        kinds = played["end_messages"][label]
        assert kinds.index(["meeting_state", "result"]) < kinds.index(["classic_result", None]), label
        changes = played["end_changes"][label]
        result_at = next(c["t"] for c in changes if c["id"] == "classic-vote-result" and c["shown"]
                         and c["text"].startswith(f"{fr_name} was a Free Rider."))
        end_at = next(c["t"] for c in changes if c["id"] == "classic-end-screen" and c["shown"])
        assert result_at <= end_at, label
        assert played["end"][label]["endScreen"] is True, label


def test_only_the_host_may_start_the_next_round_from_the_end_screen(played):
    assert played["new_round_button"] == {label: label != "P0" for label in LABELS}


# ---- Round 2: nothing of the old round is left ------------------------------


@pytest.mark.parametrize("moment", ["round2_start", "round2_running"])
def test_the_new_round_shows_no_meeting_vote_or_sheet_of_the_old_round(played, moment):
    for label, screen in played[moment].items():
        assert screen["meeting"] is False, label
        assert screen["voteList"] is False and screen["voteButtons"] == [], label
        assert screen["voteResult"] is None, label
        assert screen["endScreen"] is False, label
        assert screen["sheets"] == [], label
        assert screen["sheetsDrawn"][-1] == 0, label
        assert screen["report"] is False, label


def test_everybody_walks_in_the_new_round(played):
    assert played["round2_walked"] == {label: True for label in LABELS}


def test_a_report_in_the_new_round_opens_a_fresh_meeting_window(played):
    victim = played["names"][played["round2"]["victim"]]
    living = [played["names"][label] for label in LABELS if label != played["round2"]["victim"]]
    for label in LABELS:
        state = played["round2_meeting_state"][label]
        assert (state["phase"], state["reason"], state["reported_sheet_id"]) == ("discussion", "report", played["round2_sheet"])
        assert (state["living"], state["ghosts"]) == (living, [victim])
        assert (state["messages"], state["vote_targets"], state["skip_voted"]) == ([], {}, [])
        assert state["ejected_id"] is None and state["winner"] is None
        screen = played["round2_meeting"][label]
        assert screen["meeting"] is True, label
        assert screen["voteResult"] is None, label
        assert screen["voteButtons"] == [{"target": name, "voters": 0, "selected": False} for name in living], label
        assert screen["skipStatus"] == "0 / 3 Skip votes to end voting early.", label


# ---- Throughout --------------------------------------------------------------


@pytest.mark.parametrize("round_number", [1, 2])
def test_no_high_performer_page_is_told_who_the_free_rider_is(played, round_number):
    key = "round1" if round_number == 1 else "round2"
    fr = played[key]["fr"]
    fr_name = played["names"][fr]
    for label in LABELS:
        if label == fr:
            continue
        for message in played["rounds"][label][round_number - 1]:
            if message["type"] == "classic_result":
                break  # the end screen names every role
            assert message["type"] not in ("you_are_fr", "classic_fail_status"), (label, message)
            if message["type"] == "classic_role":
                assert message["role"] == "HP" and not message.get("other_free_riders"), (label, message)
            if message["type"] == "meeting_state" and message.get("revealed_role") is not None:
                assert message["phase"] == "result" and message["ejected_id"] == fr_name, (label, message)
            assert "roles" not in message, (label, message)


def test_no_console_error_or_warning_in_any_of_the_five_pages(played):
    assert played["problems"] == []
