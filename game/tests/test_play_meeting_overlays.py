"""The campus overview and "Leave lobby" during a Classic meeting, in Chromium (final audit, 2026-11-23).

Five guests play Classic in real Chromium pages against the real server, run
in this process; the pages, `put` and the driver are those of
test_play_hiding.py. A High Performer calls an emergency meeting (the
server's clock is set forward instead of waiting 45 seconds, and a fail by
the Free Rider tells every page the new time). Then:

1. M and the button "Map · M" do not open the campus overview over the
   meeting, and an overview that was open closes when the meeting starts.
2. The meeting covers the panel with "Leave lobby", so the meeting window has
   a "Leave lobby" of its own (S-201): it can be clicked with the mouse on
   every page, and the click leaves the lobby (here by the failed player, a
   ghost).

Skipped when Node, Playwright or Chromium is missing.
"""

import urllib.request

import pytest

from test_play_hiding import (  # noqa: F401 (quiet_tick and server are fixtures)
    BUTTON,
    LABELS,
    Browser,
    failed,
    free_place_at,
    lobby_of,
    playwright_works,
    press_at_button,
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

OVERVIEW_OPEN = "document.getElementById('campus-overview').open"
# Whether a mouse click in the middle of the meeting's "Leave lobby" reaches the button itself.
LEAVE_REACHABLE = """(() => {
  const button = document.getElementById('classic-meeting-leave');
  const box = button.getBoundingClientRect();
  if (box.width === 0 || box.height === 0) return false;
  return document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2) === button;
})()"""


@pytest.fixture(scope="module")
def played(server):  # noqa: F811 (the imported fixture)
    base, clock = server
    seen = {}
    with urllib.request.urlopen(base + "/health", timeout=5) as answer:
        assert answer.status == 200
    browser = Browser(base)
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
        caller, watcher, map_reader, leaver = [label for label in LABELS if label != fr]

        # Before the meeting: M opens the overview (it works at all).
        browser.call("press", label=map_reader, key="KeyM")
        browser.wait(map_reader, OVERVIEW_OPEN)
        seen["open_before_meeting"] = browser.js(map_reader, OVERVIEW_OPEN)

        # The button unlocks after 45 seconds; a fail tells every page the time.
        clock.skip(46)
        fr_place = free_place_at((BUTTON["x"], BUTTON["y"]), 60, near=(BUTTON["x"], BUTTON["y"] - 60))
        put(names[leaver], (fr_place[0] + 3, fr_place[1]))
        put(names[fr], fr_place)
        standing_still(names[fr])
        press_fail(browser, fr)
        failed(browser, fr, names[leaver])
        press_at_button(browser, caller, names[caller])
        wait_for_meeting_phase(browser, LABELS, "discussion", 1)
        for label in LABELS:
            browser.wait(label, "!document.getElementById('classic-meeting').hidden")
        seen["closed_by_the_meeting"] = not browser.js(map_reader, OVERVIEW_OPEN)

        # During the meeting: neither M nor the button opens it.
        browser.js(watcher, "document.activeElement && document.activeElement.blur()")
        browser.call("press", label=watcher, key="KeyM")
        browser.js(watcher, "document.getElementById('overview-open').click()")
        seen["open_by_m_in_meeting"] = browser.js(watcher, OVERVIEW_OPEN)

        # "Leave lobby" is reachable with the mouse, and the click leaves.
        seen["leave_reachable"] = {label: browser.js(label, LEAVE_REACHABLE) for label in LABELS}
        browser.call("click", label=leaver, selector="#classic-meeting-leave")
        wait_until(lambda: lobby_of(names[leaver]) is None, "the leaver is out of the lobby")
        seen["left"] = lobby_of(names[leaver]) is None
        seen["console"] = browser.close()  # every console error or warning of the pages
    except BaseException:
        browser.close()
        raise
    yield seen


def test_m_opens_the_overview_outside_a_meeting(played):
    assert played["open_before_meeting"] is True


def test_an_open_overview_closes_when_a_meeting_starts(played):
    assert played["closed_by_the_meeting"] is True


def test_neither_m_nor_the_map_button_opens_the_overview_over_a_meeting(played):
    assert played["open_by_m_in_meeting"] is False


def test_leave_lobby_can_be_clicked_during_a_meeting(played):
    assert all(played["leave_reachable"].values()), played["leave_reachable"]
    assert played["left"] is True


def test_no_console_error_or_warning_on_any_page(played):
    assert played["console"] == []
