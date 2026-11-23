"""The play test of the Classic package (M3-3.20, M3-3.9, M3-3.11, M3-3.8) in Chromium.

Five guests play Classic in real Chromium pages (Playwright, driven through
`play_classic_leaving_in_browser.js`) against the real server with its real
tick, run in this process so the test can put players where a walk would
take them and set the server's clock forward instead of waiting 45 seconds
for the emergency button, 75 for a meeting and 15 for the fail cooldown.
One lobby plays these rounds one after the other:

1. Five players. The Free Rider fails a High Performer; a meeting follows.
   During it no living page is sent the ghost, the ghost's page is sent
   everybody (M3-3.20). The meeting ends by its clock with nobody ejected.
   The Free Rider fails a second player after the meeting: that player
   stays a ghost on the server and on every page over many ticks and
   cannot chat or vote in a second meeting (M3-3.9), in which the Free
   Rider is voted out; each meeting's result reaches every page once.
2. Five players. A High Performer finishes a task, another one opens a task
   window and clicks "Leave lobby" twice quickly: the round goes on for the
   four others, the leaver is gone from their lists and their map, the bar
   goes from 1/16 to 1/12, and the leaver cannot join the running round
   (M3-3.11). Then two players leave at the same moment: the round stops.
3. Five players. The Free Rider leaves: the High Performers win at once,
   the end screen opens on the four other pages (M3-3.11).
3b. Five players. In the vote, a player who was voted for leaves: he and
   the vote for him are gone from every page, the vote ends by its clock
   with nobody ejected, the round goes on. The meeting window lies over
   "Leave lobby", so the button is clicked as the keyboard can (Tab, Enter);
   whether a mouse can reach it is only recorded.
4. Five players. In the discussion of a meeting a player closes the tab:
   the others' meeting window and lists lose him, the vote ends by its
   clock, the round goes on; a new guest cannot join. Then, while one
   player has a task open, another clicks "Leave": too few are left, the
   round stops, the open window closes (M3-3.8).
5. Four players. One leaves mid-round: "Too many players left. The round
   was stopped." on every page, back in the lobby, the Classic panel gone,
   no end screen (M3-3.8).
6. Four players. One leaves during the countdown: no round starts.
7. Four players. The round starts normally; the host leaves while the role
   card is shown: the round stops, the host changes.
8. The new host starts a Duel with the three left: it runs.

No page may log an error or a warning. Skipped when Node, Playwright or
Chromium is missing. Screenshots and a JSON of everything seen go to the
folder in CLASSIC_LEAVING_SCREENSHOTS, if that is set.
"""

import json
import os
import socket
import subprocess
import threading
import time
import traceback
from pathlib import Path

import pytest
import uvicorn

from server import main
from server.main import app
from server.modes import minigames
from server.modes.placeholder import placeholder
from test_play_hiding import (  # noqa: F401 (quiet_tick replaces the fixture of conftest.py)
    BUTTON,
    NODE,
    Clock,
    fresh_server_state,
    lobby_of,
    node_environment,
    playwright_works,
    press_at_button,
    press_fail,
    put,
    quiet_tick,
    standing_still,
    wait_until,
)

BROWSER_SCRIPT = Path(__file__).with_name("play_classic_leaving_in_browser.js")
SCREENSHOTS = os.environ.get("CLASSIC_LEAVING_SCREENSHOTS")
STATION = {station["id"]: station for station in app.state.campus["stations"]}
# Far apart from each other: nobody is in the Free Rider's range of 5 units.
FAR_PLACES = [(100.0, 330.0), (300.0, 330.0), (300.0, 400.0), (200.0, 300.0), (400.0, 300.0)]
FAIL_PLACE = (500.0, 450.0)
STOPPED = "Too many players left. The round was stopped."
ROUND_RUNNING = "This round has already started."
NOT_IN_LOBBY = "You are not in a lobby."
VOTE_REJECTED = "You cannot cast that vote right now."
CHAT_REJECTED = "You cannot send that chat message right now."
# A page stops drawing a player it was told is gone within this time.
DRAW_LAG_MS = 300

pytestmark = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


# ---- Chromium -----------------------------------------------------------


class Browser:
    """The Chromium pages of one play, driven through play_classic_leaving_in_browser.js."""

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

    def now(self, label):
        return self.js(label, "performance.now()")

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

    # What a page received, sent, showed and drew

    def messages(self, label, kind, since=0):
        return self.js(label, f"""window.__received
            .filter((r) => r.t >= {since} && r.m.type === '{kind}').map((r) => r.m)""")

    def count(self, label, kind):
        return self.js(label, f"window.__received.filter((r) => r.m.type === '{kind}').length")

    def last(self, label, kind):
        return self.js(label, f"""(() => {{
            const found = window.__received.filter((r) => r.m.type === '{kind}').pop();
            return found ? found.m : null; }})()""")

    def frames(self, label, since):
        """Who the `positions` messages since `since` (the page's clock) listed: [[names]]."""
        return self.js(label, f"""window.__received
            .filter((r) => r.t >= {since} && r.m.type === 'positions')
            .map((r) => r.m.players.map((p) => p.name))""")

    def shown(self, label, since):
        """The texts of the message line at the top since `since`: [[text, is_error]]."""
        return self.js(label, f"window.__shown.filter((s) => s.t >= {since}).map((s) => [s.text, s.error])")

    def errors(self, label, since):
        return [m["message"] for m in self.messages(label, "error", since)]

    def drawn(self, label, character, since):
        # The draws of a character as a figure on the map. The victim's
        # portrait on the F-sheet (S-163) is drawn at the sheet-local point
        # (0, 0.6), where no player can stand; it is left out, as in
        # tests/test_play_hiding.py.
        return self.js(label, f"""window.__drawn
            .filter((d) => d.t >= {since} && d.character === '{character}'
                && !(d.x === 0 && d.y === 0.6)).length""")

    def meeting_texts(self, label, since):
        return self.js(label, f"window.__meetingTexts.filter((d) => d.t >= {since}).map((d) => d.text)")

    def player_list(self, label):
        return self.js(label, "document.getElementById('lobby-players').innerText")

    def visible(self, label, element_id):
        return self.js(label, f"""(() => {{
            const element = document.getElementById('{element_id}');
            return Boolean(element) && !element.hidden && element.getBoundingClientRect().width > 0; }})()""")

    def text(self, label, element_id):
        return self.js(label, f"document.getElementById('{element_id}').textContent")


# ---- The server in this process -----------------------------------------


@pytest.fixture(scope="module")
def server():
    """The real server with its real tick, its clock in the test's hand, placeholder minigames."""
    fresh_server_state()
    clock = Clock()
    real_clock = main.seconds_now
    real_minigames = minigames.MINIGAMES
    main.seconds_now = clock
    # Every station gets the placeholder ("Finish task" after 1 second).
    minigames.MINIGAMES = {station: placeholder(game.title) for station, game in real_minigames.items()}
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    running = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=running.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not running.started:
        assert time.monotonic() < deadline, "the server did not start"
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}", clock
    finally:
        running.should_exit = True
        thread.join(timeout=10)
        main.seconds_now = real_clock
        minigames.MINIGAMES = real_minigames


# ---- Steps of a player --------------------------------------------------


class Play:
    """One lobby and its pages; the steps every round needs."""

    def __init__(self, browser, clock):
        self.browser = browser
        self.clock = clock
        self.code = None
        self.host = None

    def name(self, label):
        return self.browser.names[label]

    def lobby(self):
        return lobby_of(self.name(self.host))

    def classic(self):
        return self.lobby().classic_round

    def join(self, label):
        b = self.browser
        b.call("fill", label=label, selector="#join-code", text=self.code)
        b.call("click", label=label, selector="#join-submit")
        b.wait(label, "!document.getElementById('screen-lobby').hidden")

    def try_join(self, label):
        """Join the lobby while that cannot work; returns the text at the code field."""
        b = self.browser
        b.js(label, "document.getElementById('join-code-error').textContent = ''")
        b.call("fill", label=label, selector="#join-code", text=self.code)
        b.call("click", label=label, selector="#join-submit")
        return b.wait(label, "document.getElementById('join-code-error').textContent")

    def start(self, labels):
        """The host starts the round; returns {label: role} from each page's `classic_role`."""
        b = self.browser
        before = {label: b.count(label, "classic_role") for label in labels}
        b.call("click", label=self.host, selector="#lobby-start")
        wait_until(lambda: self.lobby().phase == "countdown", "the countdown")
        self.clock.skip(5)  # the countdown of 5 seconds is over at once
        for label in labels:
            b.wait(label, f"window.__received.filter((r) => r.m.type === 'classic_role').length > {before[label]}")
        return {label: b.last(label, "classic_role")["role"] for label in labels}

    def role_cards_closed(self, labels):
        for label in labels:
            self.browser.wait(label, "document.getElementById('classic-role-card').hidden")
            self.browser.js(label, "document.activeElement && document.activeElement.blur()")

    def spread(self, labels):
        for label, place in zip(labels, FAR_PLACES):
            put(self.name(label), place)

    def leave(self, label, past_the_window=False):
        """Click "Leave lobby" and wait for the server's `left_lobby`.

        During a meeting its window lies over the button, so a mouse cannot
        reach it; `past_the_window` clicks the button itself, as the
        keyboard (Tab, Enter) can.
        """
        b = self.browser
        before = b.count(label, "left_lobby")
        if past_the_window:
            b.js(label, "document.getElementById('lobby-leave').click()")
        else:
            b.call("click", label=label, selector="#lobby-leave")
        b.wait(label, f"window.__received.filter((r) => r.m.type === 'left_lobby').length > {before}")

    def open_task(self, label):
        """Stand at the player's first open station and press E; returns the station."""
        b = self.browser
        # The own open stations: from this round's `classic_role` or a later `station_done`.
        station = b.js(label, """(() => {
            const start = window.__received.map((r) => r.m.type).lastIndexOf('classic_role');
            const news = window.__received.slice(start).filter((r) => ['classic_role', 'station_done'].includes(r.m.type));
            return news.pop().m.task_stations[0]; })()""")
        put(self.name(label), (STATION[station]["x"], STATION[station]["y"]))
        standing_still(self.name(label))
        before = b.count(label, "station_opened")
        for _ in range(20):
            b.call("press", label=label, key="KeyE")
            try:
                b.wait(label, f"window.__received.filter((r) => r.m.type === 'station_opened').length > {before}", 1000)
                return station
            except AssertionError:
                continue
        raise AssertionError(f"E did not open station {station} for {label}")

    def finish_task(self, label):
        b = self.browser
        station = self.open_task(label)
        before = b.count(label, "station_done")
        b.wait(label, "Array.from(document.querySelectorAll('button')).some((x) => x.textContent.includes('Finish task') && !x.disabled)")
        time.sleep(1.3)  # the placeholder counts after 1 second (server.modes.placeholder)
        b.call("click", label=label, selector='button:has-text("Finish task")')
        try:
            b.wait(label, f"window.__received.filter((r) => r.m.type === 'station_done').length > {before}")
        except AssertionError:
            raise AssertionError(f"no station_done for {label} at {station}: received "
                                 f"{b.js(label, 'window.__received.slice(-6).map((r) => r.m)')}, sent "
                                 f"{b.js(label, 'window.__sent.slice(-4).map((r) => r.m)')}")
        return station

    def back_from_end_screen(self, labels):
        for label in labels:
            if self.browser.visible(label, "classic-end-screen"):
                self.browser.call("click", label=label, selector="#classic-back-lobby")

    def wait_for_phase(self, labels, phase, since):
        for label in labels:
            self.browser.wait(label, f"""window.__received.some((r) => r.t >= {since[label]}
                && r.m.type === 'meeting_state' && r.m.phase === '{phase}')""")

    def marks(self, labels):
        return {label: self.browser.now(label) for label in labels}

    def stop_seen(self, labels, since):
        """What every page saw of a stopped round: the notice, the lobby, no Classic panel."""
        b = self.browser
        seen = {}
        for label in labels:
            b.wait(label, f"window.__shown.some((s) => s.t >= {since[label]} && s.text === {json.dumps(STOPPED)})")
            b.wait(label, "!document.getElementById('lobby-start') || document.getElementById('classic-progress').hidden")
            time.sleep(0.2)
            notices = [m["message"] for m in b.messages(label, "notice", since[label])]
            seen[label] = {
                "notices": notices,
                "shown": b.shown(label, since[label]),
                "last_phase": b.last(label, "lobby_state")["phase"],
                "classic_panel": b.visible(label, "classic-progress"),
                "task_card": b.visible(label, "classic-task"),
                "hidden_hint": b.visible(label, "classic-hidden-hint"),
                "end_screen": b.visible(label, "classic-end-screen"),
                "results": len(b.messages(label, "classic_result", since[label])),
                "round_text": b.visible(label, "lobby-round"),
                "lobby_screen": b.visible(label, "screen-lobby"),
                "minigame_open": b.js(label, "Game.minigames.isOpen()"),
                "errors": b.errors(label, since[label]),
            }
        return seen


def character_of(browser, label, name):
    state = browser.last(label, "lobby_state")
    return next(player["character"] for player in state["players"] if player["name"] == name)


# ---- The rounds -----------------------------------------------------------


def round_1_ghosts_and_meetings(play, labels, seen):
    """M3-3.20 and M3-3.9: a ghost during a meeting, a fail after a meeting, a second meeting."""
    b, clock = play.browser, play.clock
    names = b.names
    roles = play.start(labels)
    play.role_cards_closed(labels)
    fr = next(label for label in labels if roles[label] == "FR")
    first, second, caller, voter = [label for label in labels if label != fr]
    play.spread(labels)

    # The emergency button can be pressed 45 seconds after the start. The
    # pages learn it from the `classic_progress` that follows the fail.
    clock.skip(50)
    # The Free Rider fails `first` before any meeting: a ghost.
    put(names[fr], FAIL_PLACE)
    put(names[first], (FAIL_PLACE[0] + 3, FAIL_PLACE[1]))
    standing_still(names[fr])
    press_fail(b, fr)
    wait_until(lambda: names[first] in play.classic().eliminated, "the first fail")
    put(names[first], FAR_PLACES[0])
    put(names[fr], FAR_PLACES[1])
    time.sleep(0.4)

    # Meeting 1, called by `caller` with the emergency button.
    mark = play.marks(labels)
    press_at_button(b, caller, names[caller])
    play.wait_for_phase(labels, "discussion", mark)
    b.shot(caller, "r1_meeting1_caller")
    in_meeting = play.marks(labels)
    # The server still sends positions when somebody's place changes in a
    # meeting: the caller and the ghost are put a little further.
    for step in range(3):
        put(names[caller], (BUTTON["x"] + 8, BUTTON["y"] + 2 * step))
        put(names[first], (FAR_PLACES[0][0] + 10 * step, FAR_PLACES[0][1]))
        time.sleep(0.25)
    time.sleep(0.3)
    frames = {label: b.frames(label, in_meeting[label]) for label in labels}
    states = {label: b.messages(label, "lobby_state", in_meeting[label]) for label in labels}
    living = [label for label in labels if label != first]
    seen["meeting_ghost"] = {
        "phase": play.classic().phase,
        "living_frames": {label: len(frames[label]) for label in living},
        "living_frames_with_ghost": {label: sum(names[first] in f for f in frames[label]) for label in living},
        "living_states_with_ghost": {
            label: sum(any(p["name"] == names[first] for p in s["players"]) for s in states[label]) for label in living
        },
        "living_draws_of_ghost": {
            label: b.drawn(label, character_of(b, first, names[first]), in_meeting[label] + DRAW_LAG_MS)
            for label in living
        },
        "ghost_frames": len(frames[first]),
        "ghost_frames_with_everybody": sum(sorted(f) == sorted(names[label] for label in labels) for f in frames[first]),
    }
    clock.skip(46)
    play.wait_for_phase(labels, "voting", mark)
    clock.skip(31)
    play.wait_for_phase(labels, "result", mark)
    for label in labels:
        b.wait(label, "document.getElementById('classic-meeting').hidden", timeout=6000)
    seen["meeting1_result"] = {
        "results_per_page": {
            label: len([m for m in b.messages(label, "meeting_state", mark[label]) if m["phase"] == "result"])
            for label in labels
        },
        "ejected": [m["ejected_id"] for m in b.messages(labels[0], "meeting_state", mark[labels[0]]) if m["phase"] == "result"],
        "phase_after": play.classic().phase,
        "eliminated_after": sorted(play.classic().eliminated),
    }

    # After meeting 1 the Free Rider fails `second` (the cooldown starts again after a meeting).
    clock.skip(16)
    put(names[fr], FAIL_PLACE)
    put(names[second], (FAIL_PLACE[0] + 3, FAIL_PLACE[1]))
    standing_still(names[fr])
    press_fail(b, fr)
    wait_until(lambda: names[second] in play.classic().eliminated, "the fail after the meeting")
    put(names[second], FAR_PLACES[2])
    put(names[fr], FAR_PLACES[1])
    time.sleep(0.4)
    after_fail = play.marks(labels)
    # Many ticks, also with the server's clock moved on: the finished
    # meeting is still in the lobby and the tick looks at it every time.
    alive_checks = []
    for step in range(8):
        put(names[second], (FAR_PLACES[2][0] + 5 * step, FAR_PLACES[2][1]))
        clock.skip(1)
        time.sleep(0.2)
        alive_checks.append(names[second] in play.classic().eliminated)
    frames = {label: b.frames(label, after_fail[label]) for label in labels}
    rosters = {label: b.last(label, "classic_roster")["players"] for label in labels}
    ghosts = (first, second)
    seen["ghost_after_meeting"] = {
        "stays_ghost_on_server": alive_checks,
        "eliminated": sorted(play.classic().eliminated),
        "expected": sorted([names[first], names[second]]),
        "living_frames": {label: len(frames[label]) for label in labels if label not in ghosts},
        "living_frames_with_second": {
            label: sum(names[second] in f for f in frames[label]) for label in labels if label not in ghosts
        },
        "living_rosters_with_second": {
            label: [p["name"] for p in rosters[label]].count(names[second]) for label in labels if label not in ghosts
        },
        "ghost_rosters": {
            label: sorted((p["name"], p["ghost"]) for p in rosters[label]) for label in ghosts
        },
        "expected_ghost_roster": sorted((names[label], label in ghosts) for label in labels),
        "second_page_ghost_frames_with_everybody": sum(
            sorted(f) == sorted(names[label] for label in labels) for f in frames[second]
        ),
    }
    b.shot(second, "r1_ghost_after_meeting1")

    # Meeting 2, called by `caller2` = `voter` (each living player has one).
    mark2 = play.marks(labels)
    press_at_button(b, voter, names[voter])
    play.wait_for_phase(labels, "discussion", mark2)
    time.sleep(0.3)
    discussion = b.last(second, "meeting_state")
    ghost_chat_input = b.js(second, "document.getElementById('classic-chat-input').disabled")
    since = b.now(second)
    b.js(second, "window.__socket.send(JSON.stringify({type: 'chat', text: 'I am a ghost'}))")
    b.wait(second, f"window.__received.some((r) => r.t >= {since} && r.m.type === 'error')")
    ghost_chat_errors = b.errors(second, since)
    clock.skip(46)
    play.wait_for_phase(labels, "voting", mark2)
    b.wait(second, "document.querySelectorAll('.classic-vote-player').length > 0")
    ghost_buttons = b.js(second, "Array.from(document.querySelectorAll('.classic-vote-player')).map((x) => [x.dataset.targetId, x.disabled])")
    b.shot(second, "r1_meeting2_ghost_cannot_vote")
    since = b.now(second)
    b.js(second, f"window.__socket.send(JSON.stringify({{type: 'vote', target_id: {json.dumps(names[fr])}}}))")
    b.wait(second, f"window.__received.some((r) => r.t >= {since} && r.m.type === 'error')")
    ghost_vote_errors = b.errors(second, since)
    votes_after_ghost = dict(play.lobby().meeting["votes"])
    # The living vote the Free Rider out; he presses Skip.
    for label in (caller, voter):
        selector = f'.classic-vote-player[data-target-id="{names[fr]}"]'
        b.wait(label, f"document.querySelector('{selector}') !== null && !document.querySelector('{selector}').disabled")
        b.call("click", label=label, selector=selector)
    b.call("click", label=fr, selector="#classic-skip-discussion")
    # Lennart's rules (S-162): everybody having voted does not end the vote;
    # its clock does. The Skip must arrive before the clock jumps.
    wait_until(lambda: names[fr] in play.lobby().meeting.get("skip_votes", ()), "the Free Rider's Skip")
    clock.skip(31)
    for label in labels:
        b.wait(label, "!document.getElementById('classic-end-screen').hidden")
    time.sleep(0.5)
    b.shot(caller, "r1_end_screen_after_vote")
    seen["meeting2"] = {
        "living": discussion["living"],
        "ghosts": discussion["ghosts"],
        "expected_living": sorted(names[label] for label in (fr, caller, voter)),
        "expected_ghosts": sorted(names[label] for label in ghosts),
        "ghost_chat_input_disabled": ghost_chat_input,
        "ghost_chat_errors": ghost_chat_errors,
        "ghost_vote_buttons": ghost_buttons,
        "ghost_vote_errors": ghost_vote_errors,
        "ghost_in_votes": names[second] in votes_after_ghost,
        "results_per_page": {
            label: len([m for m in b.messages(label, "meeting_state", mark2[label]) if m["phase"] == "result"])
            for label in labels
        },
        "ejected": [m["ejected_id"] for m in b.messages(caller, "meeting_state", mark2[caller]) if m["phase"] == "result"],
        "fr": names[fr],
        "winners": {label: b.text(label, "classic-winner") for label in labels},
        "classic_results": {label: len(b.messages(label, "classic_result", mark2[label])) for label in labels},
        "lobby_phase": play.lobby().phase,
    }
    play.back_from_end_screen(labels)


def round_2_high_performer_leaves(play, labels, seen):
    """M3-3.11: a High Performer with a task open leaves twice quickly; then two leave at once."""
    b = play.browser
    names = b.names
    roles = play.start(labels)
    play.role_cards_closed(labels)
    play.spread(labels)
    hps = [label for label in labels if roles[label] == "HP"]
    leaver = next(label for label in hps if label != play.host)
    worker = next(label for label in hps if label != leaver)
    others = [label for label in labels if label != leaver]
    progress_start = b.text(others[0], "classic-progress-label")
    play.finish_task(worker)
    for label in others:
        b.wait(label, f"document.getElementById('classic-progress-label').textContent !== {json.dumps(progress_start)}")
    progress_before = {label: b.text(label, "classic-progress-label") for label in others}
    server_before = play.classic().progress()
    play.open_task(leaver)
    window_open = b.js(leaver, "Game.minigames.isOpen()")
    leaver_character = character_of(b, others[0], names[leaver])
    mark = play.marks(labels)
    # Two clicks right after each other, as a quick double click does.
    b.js(leaver, "(() => { const button = document.getElementById('lobby-leave'); button.click(); button.click(); })()")
    b.wait(leaver, f"window.__received.some((r) => r.t >= {mark[leaver]} && r.m.type === 'left_lobby')")
    for label in others:
        b.wait(label, f"""(() => {{ const r = window.__received.filter((x) => x.t >= {mark[label]} && x.m.type === 'classic_roster').pop();
            return Boolean(r) && !r.m.players.some((p) => p.name === {json.dumps(names[leaver])}); }})()""")
        b.wait(label, f"!document.getElementById('lobby-players').innerText.includes({json.dumps(names[leaver])})")
    for label in others:
        b.wait(label, f"document.getElementById('classic-progress-label').textContent !== {json.dumps(progress_before[label])}")
    # Somebody walks: positions go out again.
    after = play.marks(others)
    for step in range(3):
        put(names[worker], (FAR_PLACES[3][0] + 5 * step, FAR_PLACES[3][1]))
        time.sleep(0.2)
    time.sleep(0.3)
    leaves_sent = b.js(leaver, f"window.__sent.filter((s) => s.t >= {mark[leaver]} && s.m.type === 'leave_lobby').length")
    # A second `leave_lobby` sent past the page (the page itself sends only one).
    b.js(leaver, "window.__socket.send(JSON.stringify({type: 'leave_lobby'}))")
    b.wait(leaver, f"window.__received.some((r) => r.t >= {mark[leaver]} && r.m.type === 'error')")
    b.shot(others[0], "r2_after_high_performer_left")
    seen["hp_leaves"] = {
        "leaver": names[leaver],
        "window_open_before": window_open,
        "leaves_sent_by_page": leaves_sent,
        "leaver_errors": b.errors(leaver, mark[leaver]),
        "leaver_window_open_after": b.js(leaver, "Game.minigames.isOpen()"),
        "leaver_home": b.visible(leaver, "screen-home"),
        "leaver_panel": b.visible(leaver, "classic-progress"),
        "phase": play.lobby().phase,
        "in_lobby": names[leaver] in play.lobby().names(),
        "eliminated": names[leaver] in play.classic().eliminated,
        "others_lists": {label: b.player_list(label) for label in others},
        "others_frames": {label: len(b.frames(label, after[label])) for label in others},
        "others_frames_with_leaver": {label: sum(names[leaver] in f for f in b.frames(label, after[label])) for label in others},
        "others_draws_of_leaver": {label: b.drawn(label, leaver_character, after[label] + DRAW_LAG_MS) for label in others},
        "progress_start": progress_start,
        "progress_before": progress_before,
        "progress_after": {label: b.text(label, "classic-progress-label") for label in others},
        "server_progress_before": server_before,
        "server_progress_after": play.classic().progress(),
        "others_errors": {label: b.errors(label, mark[label]) for label in others},
        "others_results": {label: len(b.messages(label, "classic_result", mark[label])) for label in others},
    }
    seen["hp_leaves"]["rejoin"] = play.try_join(leaver)
    seen["hp_leaves"]["rejoin_in_lobby"] = names[leaver] in play.lobby().names()
    b.shot(leaver, "r2_leaver_cannot_rejoin")

    # Two players leave at the same moment: from four, two.
    pair = [label for label in others if label != play.host][:2]
    stay = [label for label in others if label not in pair]
    mark = play.marks(labels)
    b.call("eval_together", labels=pair, js="document.getElementById('lobby-leave').click()")
    for label in pair:
        b.wait(label, f"window.__received.some((r) => r.t >= {mark[label]} && r.m.type === 'left_lobby')")
    stop = play.stop_seen(stay, mark)
    seen["two_leave"] = {
        "stay": stay,
        "seen": stop,
        "lobby_phase": play.lobby().phase,
        "pair_errors": {label: b.errors(label, mark[label]) for label in pair},
    }
    b.shot(stay[0], "r2_two_left_round_stopped")
    for label in [leaver] + pair:
        play.join(label)


def round_3_free_rider_leaves(play, labels, seen):
    """M3-3.11: the Free Rider of five leaves: the High Performers win at once."""
    b = play.browser
    roles = play.start(labels)
    play.role_cards_closed(labels)
    play.spread(labels)
    fr = next(label for label in labels if roles[label] == "FR")
    others = [label for label in labels if label != fr]
    mark = play.marks(labels)
    play.leave(fr)
    if fr == play.host:
        # The roles are random: when the host is the Free Rider who leaves,
        # the lobby has a new host, and the later rounds are started by him
        # (M3-3.24; as in round 7).
        new_host_name = lobby_of(b.names[others[0]]).host
        play.host = next(label for label in others if b.names[label] == new_host_name)
    for label in others:
        b.wait(label, "!document.getElementById('classic-end-screen').hidden")
    time.sleep(0.3)
    b.shot(others[0], "r3_free_rider_left_end_screen")
    seen["fr_leaves"] = {
        "fr": b.names[fr],
        "winners": {label: b.text(label, "classic-winner") for label in others},
        "reasons": {label: b.text(label, "classic-end-reason") for label in others},
        "results": {label: b.messages(label, "classic_result", mark[label]) for label in others},
        "stop_notices": {label: [s for s in b.shown(label, mark[label]) if s[0] == STOPPED] for label in others},
        "fr_end_screen": b.visible(fr, "classic-end-screen"),
        "fr_home": b.visible(fr, "screen-home"),
        "lobby_phase": play.lobby().phase,
        "errors": {label: b.errors(label, mark[label]) for label in labels},
    }
    play.back_from_end_screen(others)
    play.join(fr)


def round_3b_leave_in_the_vote(play, labels, seen):
    """M3-3.11 in the vote: a player voted for leaves; the vote ends by its clock."""
    b, clock = play.browser, play.clock
    names = b.names
    roles = play.start(labels)
    play.role_cards_closed(labels)
    play.spread(labels)
    hps = [label for label in labels if roles[label] == "HP"]
    caller = hps[0]
    leaver = next(label for label in hps if label not in (caller, play.host))
    voter = next(label for label in labels if label not in (caller, leaver))
    others = [label for label in labels if label != leaver]
    clock.skip(50)
    play.finish_task(next(label for label in hps if label not in (caller, leaver)))
    play.spread(labels)
    mark = play.marks(labels)
    press_at_button(b, caller, names[caller])
    play.wait_for_phase(labels, "discussion", mark)
    clock.skip(46)
    play.wait_for_phase(labels, "voting", mark)
    selector = f'.classic-vote-player[data-target-id="{names[leaver]}"]'
    b.wait(voter, f"document.querySelector('{selector}') !== null && !document.querySelector('{selector}').disabled")
    b.call("click", label=voter, selector=selector)
    wait_until(lambda: names[voter] in play.lobby().meeting["votes"], "the vote for the leaver")
    # Can a mouse reach "Leave lobby" while the meeting window is open?
    reachable = b.js(leaver, """(() => {
        const button = document.getElementById('lobby-leave');
        const box = button.getBoundingClientRect();
        return document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2) === button; })()""")
    left = play.marks(others)
    play.leave(leaver, past_the_window=True)
    gone = json.dumps(names[leaver])
    for label in others:
        b.wait(label, f"""window.__received.some((r) => r.t >= {left[label]} && r.m.type === 'meeting_state'
            && !r.m.living.includes({gone}))""")
        b.wait(label, f"!document.querySelector('{selector}')")
    time.sleep(0.3)
    b.shot(voter, "r3b_vote_after_the_voted_player_left")
    votes_after = dict(play.lobby().meeting["votes"])
    buttons = {
        label: b.js(label, "Array.from(document.querySelectorAll('.classic-vote-player')).map((x) => [x.dataset.targetId, x.disabled])")
        for label in others
    }
    last_states = {label: b.last(label, "meeting_state") for label in others}
    clock.skip(31)
    play.wait_for_phase(others, "result", mark)
    result_texts = {label: b.wait(label, "document.getElementById('classic-vote-result').textContent") for label in others}
    for label in others:
        b.wait(label, "document.getElementById('classic-meeting').hidden", timeout=6000)
    seen["leave_in_vote"] = {
        "leaver": names[leaver],
        "leave_button_reachable_by_mouse": reachable,
        "voter": names[voter],
        "votes_after": votes_after,
        "voted_after": {label: state["voted"] for label, state in last_states.items()},
        "living_after": {label: state["living"] for label, state in last_states.items()},
        "buttons": buttons,
        "result_texts": result_texts,
        "phase_after": play.classic().phase if play.classic() else None,
        "lobby_phase": play.lobby().phase,
        "errors": {label: b.errors(label, mark[label]) for label in others},
    }
    # The round goes on with four; one more leave stops it.
    last = next(label for label in others if label != play.host)
    stay = [label for label in others if label != last]
    mark = play.marks(stay)
    play.leave(last)
    play.stop_seen(stay, mark)
    for label in (leaver, last):
        play.join(label)


def round_4_tab_closed_in_meeting(play, labels, seen, newcomer):
    """M3-3.11 in a meeting: a tab is closed in the discussion; later a leave stops the round."""
    b, clock = play.browser, play.clock
    names = b.names
    roles = play.start(labels)
    play.role_cards_closed(labels)
    play.spread(labels)
    hps = [label for label in labels if roles[label] == "HP"]
    caller = hps[0]
    closer = next(label for label in hps if label not in (caller, play.host))
    others = [label for label in labels if label != closer]
    # The emergency button can be pressed 45 seconds after the start; the
    # pages learn it from the `classic_progress` after a finished task.
    clock.skip(50)
    play.finish_task(next(label for label in hps if label not in (caller, closer)))
    play.spread(labels)
    mark = play.marks(labels)
    press_at_button(b, caller, names[caller])
    play.wait_for_phase(labels, "discussion", mark)
    time.sleep(0.3)
    living_before = sorted(b.last(others[0], "meeting_state")["living"])
    closed = play.marks(others)
    b.call("close_page", label=closer)
    gone = json.dumps(names[closer])
    for label in others:
        b.wait(label, f"""window.__received.some((r) => r.t >= {closed[label]} && r.m.type === 'meeting_state'
            && !r.m.living.includes({gone}) && !r.m.ghosts.includes({gone}))""")
        b.wait(label, f"!document.getElementById('lobby-players').innerText.includes({gone})")
    time.sleep(0.4)
    b.shot(others[0], "r4_meeting_after_tab_closed")
    # The window is drawn anew with each `meeting_state`: what was drawn from
    # the first one without him on.
    without = {
        label: b.js(label, f"""window.__received.find((r) => r.t >= {closed[label]} && r.m.type === 'meeting_state'
            && !r.m.living.includes({gone})).t""")
        for label in others
    }
    texts = {label: b.meeting_texts(label, without[label]) for label in others}
    clock.skip(46)
    play.wait_for_phase(others, "voting", mark)
    for label in others:
        b.wait(label, "document.querySelectorAll('.classic-vote-player').length > 0")
    buttons = {
        label: b.js(label, "Array.from(document.querySelectorAll('.classic-vote-player')).map((x) => x.dataset.targetId)")
        for label in others
    }
    b.shot(others[0], "r4_vote_without_the_closed_tab")
    b.call("click", label=caller, selector="#classic-skip-discussion")
    # The Skip must arrive before the clock jumps past the end of the vote.
    wait_until(lambda: names[caller] in play.lobby().meeting.get("skip_votes", ()), "the Skip")
    clock.skip(31)
    play.wait_for_phase(others, "result", mark)
    result_texts = {label: b.wait(label, "document.getElementById('classic-vote-result').textContent") for label in others}
    for label in others:
        b.wait(label, "document.getElementById('classic-meeting').hidden", timeout=6000)
    seen["tab_closed_in_meeting"] = {
        "closer": names[closer],
        "living_before": living_before,
        "last_meeting_states": {label: b.last(label, "meeting_state") for label in others},
        "meeting_texts_with_closer": {label: sum(names[closer] in t for t in texts[label]) for label in others},
        "meeting_texts_drawn": {label: len(texts[label]) for label in others},
        "vote_buttons": buttons,
        "result_texts": result_texts,
        "results_per_page": {
            label: len([m for m in b.messages(label, "meeting_state", mark[label]) if m["phase"] == "result"])
            for label in others
        },
        "phase_after": play.classic().phase if play.classic() else None,
        "lobby_phase": play.lobby().phase,
        "eliminated": sorted(play.classic().eliminated) if play.classic() else None,
        "lists": {label: b.player_list(label) for label in others},
        "errors": {label: b.errors(label, mark[label]) for label in others},
    }
    seen["tab_closed_in_meeting"]["newcomer_join"] = play.try_join(newcomer)
    b.shot(newcomer, "r4_newcomer_cannot_join")

    # A leave with a task open elsewhere: four left, one leaves, the round stops.
    hps_left = [label for label in others if roles[label] == "HP"]
    leaver = next(label for label in hps_left if label != play.host)
    worker = next(label for label in hps_left if label != leaver)
    play.open_task(worker)
    stay = [label for label in others if label != leaver]
    mark = play.marks(stay)
    play.leave(leaver)
    seen["stop_with_open_task"] = {
        "worker": worker,
        "seen": play.stop_seen(stay, mark),
        "worker_station_closed": len(b.messages(worker, "station_closed", mark[worker])),
        "lobby_phase": play.lobby().phase,
    }
    b.shot(worker, "r4_stopped_task_window_closed")
    play.join(leaver)
    return others


def round_5_four_and_one_leaves(play, labels, seen):
    """M3-3.8: four players, one leaves mid-round: the round stops for the three."""
    b = play.browser
    roles = play.start(labels)
    play.role_cards_closed(labels)
    play.spread(labels)
    for label in labels:
        b.wait(label, "!document.getElementById('classic-progress').hidden")
    panel_during = {label: b.visible(label, "classic-progress") for label in labels}
    leaver = next(label for label in labels if roles[label] == "HP" and label != play.host)
    stay = [label for label in labels if label != leaver]
    mark = play.marks(stay)
    play.leave(leaver)
    seen["four_one_leaves"] = {
        "panel_during": panel_during,
        "seen": play.stop_seen(stay, mark),
        "lobby_phase": play.lobby().phase,
    }
    for label in stay:
        b.shot(label, f"r5_stopped_{label}")
    play.join(leaver)


def round_6_leave_in_countdown(play, labels, seen):
    """A player leaves during the countdown: too few for Classic, no round starts."""
    b = play.browser
    before = {label: b.count(label, "classic_role") for label in labels}
    leaver = next(label for label in labels if label != play.host)
    stay = [label for label in labels if label != leaver]
    mark = play.marks(labels)
    b.call("click", label=play.host, selector="#lobby-start")
    wait_until(lambda: play.lobby().phase == "countdown", "the countdown")
    for label in labels:
        b.wait(label, "!document.getElementById('countdown').hidden")
    play.leave(leaver)
    play.clock.skip(6)
    time.sleep(1.0)
    seen["countdown_leave"] = {
        "lobby_phase": play.lobby().phase,
        "roles_after": {label: b.count(label, "classic_role") - before[label] for label in stay},
        "countdown_shown": {label: b.visible(label, "countdown") for label in stay},
        "last_phase": {label: b.last(label, "lobby_state")["phase"] for label in stay},
        "errors": {label: b.errors(label, mark[label]) for label in labels},
        "shown": {label: b.shown(label, mark[label]) for label in stay},
    }
    b.shot(stay[0], "r6_countdown_cancelled")
    play.join(leaver)


def round_7_host_leaves_in_role_reveal(play, labels, seen):
    """The round runs normally; the host leaves while the role card is shown: stop and new host."""
    b = play.browser
    roles = play.start(labels)
    cards = {label: b.visible(label, "classic-role-card") for label in labels}
    old_host = play.host
    stay = [label for label in labels if label != old_host]
    mark = play.marks(stay)
    play.leave(old_host)
    new_host_name = lobby_of(b.names[stay[0]]).host
    play.host = next(label for label in stay if b.names[label] == new_host_name)
    stop = play.stop_seen(stay, mark)
    for label in stay:
        b.wait(label, "document.getElementById('classic-role-card').hidden")
    seen["host_leaves_in_reveal"] = {
        "roles": roles,
        "cards_shown": cards,
        "seen": stop,
        "new_host": new_host_name,
        "host_area_on_new_host": b.visible(play.host, "lobby-host-area"),
        "lobby_phase": play.lobby().phase,
        "message_line_now": {label: [b.text(label, "message"), b.visible(label, "message")] for label in stay},
    }
    b.shot(play.host, "r7_new_host_after_stop")
    return stay


def round_8_duel_runs(play, labels, seen):
    """After a stop the new host starts a Duel with the three left: it runs."""
    b = play.browser
    b.call("click", label=play.host, selector='#lobby-modes button:has-text("Duel")')
    wait_until(lambda: play.lobby().mode == "duel", "Duel chosen")
    mark = play.marks(labels)
    b.call("click", label=play.host, selector="#lobby-start")
    wait_until(lambda: play.lobby().phase == "countdown", "the countdown")
    play.clock.skip(5)
    for label in labels:
        b.wait(label, f"window.__received.some((r) => r.t >= {mark[label]} && r.m.type === 'duel_state')")
        b.wait(label, "!document.getElementById('duel-panel').hidden")
    time.sleep(0.5)
    b.shot(play.host, "r8_duel_runs")
    seen["duel_after_stop"] = {
        "lobby_phase": play.lobby().phase,
        "duel_panels": {label: b.visible(label, "duel-panel") for label in labels},
        "classic_panels": {label: b.visible(label, "classic-progress") for label in labels},
        "positions": {label: len(b.frames(label, mark[label])) for label in labels},
        "errors": {label: b.errors(label, mark[label]) for label in labels},
    }


@pytest.fixture(scope="module")
def played(server):
    base, clock = server
    browser = Browser(base)
    seen = {"errors": {}}
    labels = ["P0", "P1", "P2", "P3", "P4"]
    play = Play(browser, clock)
    stage = "setup"
    try:
        for label in labels + ["N"]:
            browser.open(label)
        browser.call("click", label="P0", selector="#home-create")
        browser.wait("P0", "/[A-Z0-9]{4}/.test(document.getElementById('lobby-code').textContent)")
        play.code = browser.js("P0", "document.getElementById('lobby-code').textContent.match(/[A-Z0-9]{4}/)[0]")
        play.host = "P0"
        for label in labels[1:]:
            play.join(label)
        browser.call("click", label="P0", selector='#lobby-modes button:has-text("Classic")')
        wait_until(lambda: play.lobby().mode == "classic", "Classic chosen")

        stage = "round 1"
        round_1_ghosts_and_meetings(play, labels, seen)
        stage = "round 2"
        round_2_high_performer_leaves(play, labels, seen)
        stage = "round 3"
        round_3_free_rider_leaves(play, labels, seen)
        stage = "round 3b"
        round_3b_leave_in_the_vote(play, labels, seen)
        stage = "round 4"
        four = round_4_tab_closed_in_meeting(play, labels, seen, "N")
        stage = "round 5"
        round_5_four_and_one_leaves(play, four, seen)
        stage = "round 6"
        round_6_leave_in_countdown(play, four, seen)
        stage = "round 7"
        three = round_7_host_leaves_in_role_reveal(play, four, seen)
        stage = "round 8"
        round_8_duel_runs(play, three, seen)
        stage = "done"
    except Exception:
        seen["errors"][stage] = traceback.format_exc()
    finally:
        seen["stage"] = stage
        try:
            seen["problems"] = browser.close()
        except Exception:
            seen["problems"] = ["the browser driver could not be closed"]
        if SCREENSHOTS:
            Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
            (Path(SCREENSHOTS) / "classic_leaving_seen.json").write_text(json.dumps(seen, indent=1, default=str))
    return seen


def reached(played, key):
    """The part of the play under `key`; fails with the reason if the play stopped before it."""
    assert key in played, f"the play stopped in {played['stage']}: {played['errors']}"
    return played[key]


# ---- M3-3.20 --------------------------------------------------------------


def test_during_a_meeting_no_living_page_is_sent_the_ghost(played):
    seen = reached(played, "meeting_ghost")
    assert seen["phase"] == "meeting"
    assert all(count > 0 for count in seen["living_frames"].values()), seen
    assert seen["living_frames_with_ghost"] == {label: 0 for label in seen["living_frames"]}
    assert seen["living_states_with_ghost"] == {label: 0 for label in seen["living_frames"]}
    assert seen["living_draws_of_ghost"] == {label: 0 for label in seen["living_frames"]}


def test_during_a_meeting_the_ghost_page_is_sent_everybody(played):
    seen = reached(played, "meeting_ghost")
    assert seen["ghost_frames"] > 0
    assert seen["ghost_frames_with_everybody"] == seen["ghost_frames"]


# ---- M3-3.9 ---------------------------------------------------------------


def test_a_meeting_ended_by_its_clock_reaches_every_page_once_and_ejects_nobody(played):
    seen = reached(played, "meeting1_result")
    assert set(seen["results_per_page"].values()) == {1}, seen
    assert seen["ejected"] == [None]
    assert seen["phase_after"] == "round"


def test_a_player_failed_after_a_meeting_stays_a_ghost_across_ticks(played):
    seen = reached(played, "ghost_after_meeting")
    assert all(seen["stays_ghost_on_server"]), seen
    assert seen["eliminated"] == seen["expected"]
    assert all(count > 0 for count in seen["living_frames"].values()), seen
    assert seen["living_frames_with_second"] == {label: 0 for label in seen["living_frames"]}
    assert seen["living_rosters_with_second"] == {label: 0 for label in seen["living_frames"]}
    for roster in seen["ghost_rosters"].values():
        assert [list(entry) for entry in roster] == [list(entry) for entry in seen["expected_ghost_roster"]]


def test_a_ghost_cannot_chat_or_vote_in_the_second_meeting(played):
    seen = reached(played, "meeting2")
    assert sorted(seen["living"]) == seen["expected_living"]
    assert sorted(seen["ghosts"]) == seen["expected_ghosts"]
    assert seen["ghost_chat_input_disabled"] is True
    assert seen["ghost_chat_errors"] == [CHAT_REJECTED]
    assert seen["ghost_vote_buttons"] and all(disabled for _, disabled in seen["ghost_vote_buttons"])
    assert seen["ghost_vote_errors"] == [VOTE_REJECTED]
    assert seen["ghost_in_votes"] is False


def test_the_free_rider_voted_out_is_applied_once_and_ends_the_round(played):
    seen = reached(played, "meeting2")
    assert set(seen["results_per_page"].values()) == {1}, seen
    assert seen["ejected"] == [seen["fr"]]
    assert set(seen["classic_results"].values()) == {1}
    assert all("High Performers" in winner for winner in seen["winners"].values()), seen["winners"]
    assert seen["lobby_phase"] == "lobby"


# ---- M3-3.11 --------------------------------------------------------------


def test_a_high_performer_who_leaves_is_out_and_the_round_goes_on(played):
    seen = reached(played, "hp_leaves")
    assert seen["phase"] == "round"
    assert seen["in_lobby"] is False and seen["eliminated"] is True
    assert seen["others_results"] == {label: 0 for label in seen["others_results"]}
    for label, listed in seen["others_lists"].items():
        assert seen["leaver"] not in listed, (label, listed)
    assert all(count > 0 for count in seen["others_frames"].values()), seen["others_frames"]
    assert seen["others_frames_with_leaver"] == {label: 0 for label in seen["others_frames"]}
    assert seen["others_draws_of_leaver"] == {label: 0 for label in seen["others_frames"]}
    assert seen["others_errors"] == {label: [] for label in seen["others_errors"]}


def test_the_leavers_open_tasks_leave_the_progress_bar(played):
    seen = reached(played, "hp_leaves")
    # 4 High Performers with 4 tasks each; one task finished: 1/16, then 1/12.
    assert seen["progress_start"] == "0% complete"
    assert seen["server_progress_before"] == pytest.approx(1 / 16)
    assert seen["server_progress_after"] == pytest.approx(1 / 12)
    assert set(seen["progress_before"].values()) == {"6% complete"}, seen["progress_before"]
    assert set(seen["progress_after"].values()) == {"8% complete"}, seen["progress_after"]


def test_leaving_twice_quickly_with_a_task_open(played):
    seen = reached(played, "hp_leaves")
    assert seen["window_open_before"] is True
    assert seen["leaves_sent_by_page"] == 1
    # The second `leave_lobby` was sent past the page.
    assert seen["leaver_errors"] == [NOT_IN_LOBBY]
    assert seen["leaver_window_open_after"] is False
    assert seen["leaver_home"] is True and seen["leaver_panel"] is False


def test_the_leaver_cannot_join_the_running_round(played):
    seen = reached(played, "hp_leaves")
    assert seen["rejoin"] == ROUND_RUNNING
    assert seen["rejoin_in_lobby"] is False


def test_two_players_leaving_at_once_stop_the_round_once(played):
    seen = reached(played, "two_leave")
    assert seen["lobby_phase"] == "lobby"
    for label, page in seen["seen"].items():
        assert page["notices"].count(STOPPED) == 1, (label, page)
        assert page["last_phase"] == "lobby" and page["results"] == 0 and not page["end_screen"], (label, page)
    assert seen["pair_errors"] == {label: [] for label in seen["pair_errors"]}


def test_the_free_rider_who_leaves_lets_the_high_performers_win(played):
    seen = reached(played, "fr_leaves")
    assert seen["lobby_phase"] == "lobby"
    for label, results in seen["results"].items():
        assert len(results) == 1 and results[0]["winner"] == "HP", (label, results)
    assert all("High Performers" in winner for winner in seen["winners"].values()), seen["winners"]
    assert seen["stop_notices"] == {label: [] for label in seen["stop_notices"]}
    assert seen["fr_end_screen"] is False and seen["fr_home"] is True
    assert seen["errors"] == {label: [] for label in seen["errors"]}


def test_a_player_voted_for_who_leaves_in_the_vote_takes_the_vote_with_him(played):
    seen = reached(played, "leave_in_vote")
    assert seen["voter"] not in seen["votes_after"]
    for label, living in seen["living_after"].items():
        assert seen["leaver"] not in living, (label, living)
    for label, buttons in seen["buttons"].items():
        assert seen["leaver"] not in [target for target, _ in buttons] and len(buttons) == 4, (label, buttons)  # Skip is its own button (S-162)
    assert set(seen["result_texts"].values()) == {"No one was ejected."}
    assert seen["phase_after"] == "round" and seen["lobby_phase"] == "round"
    assert seen["errors"] == {label: [] for label in seen["errors"]}


def test_a_tab_closed_in_the_discussion_leaves_the_meeting_and_it_ends_by_its_clock(played):
    seen = reached(played, "tab_closed_in_meeting")
    closer = seen["closer"]
    assert closer in seen["living_before"]
    for label, state in seen["last_meeting_states"].items():
        assert closer not in state["living"] and closer not in state["ghosts"], (label, state)
    assert all(count > 0 for count in seen["meeting_texts_drawn"].values())
    assert seen["meeting_texts_with_closer"] == {label: 0 for label in seen["meeting_texts_drawn"]}
    for label, buttons in seen["vote_buttons"].items():
        assert closer not in buttons and len(buttons) == 4, (label, buttons)  # four players; Skip is its own button (S-162)
    assert set(seen["result_texts"].values()) == {"No one was ejected."}
    assert set(seen["results_per_page"].values()) == {1}
    assert seen["phase_after"] == "round" and seen["lobby_phase"] == "round"
    assert closer in seen["eliminated"]
    for label, listed in seen["lists"].items():
        assert closer not in listed, (label, listed)
    assert seen["errors"] == {label: [] for label in seen["errors"]}


def test_nobody_new_can_join_after_a_tab_was_closed(played):
    seen = reached(played, "tab_closed_in_meeting")
    assert seen["newcomer_join"] == ROUND_RUNNING


# ---- M3-3.8 ---------------------------------------------------------------


def stopped_cleanly(page):
    return {
        "notice": page["notices"].count(STOPPED),
        "shown": [text for text, _ in page["shown"]].count(STOPPED),
        "phase": page["last_phase"],
        "panel": page["classic_panel"],
        "task_card": page["task_card"],
        "hidden": page["hidden_hint"],
        "end_screen": page["end_screen"],
        "results": page["results"],
        "round_text": page["round_text"],
        "lobby_screen": page["lobby_screen"],
        "minigame": page["minigame_open"],
        "errors": page["errors"],
    }


CLEAN_STOP = {
    "notice": 1, "shown": 1, "phase": "lobby", "panel": False, "task_card": False, "hidden": False,
    "end_screen": False, "results": 0, "round_text": False, "lobby_screen": True, "minigame": False, "errors": [],
}


def test_with_four_one_leaves_and_the_round_stops_for_everybody(played):
    seen = reached(played, "four_one_leaves")
    assert all(seen["panel_during"].values())
    assert seen["lobby_phase"] == "lobby"
    for label, page in seen["seen"].items():
        assert stopped_cleanly(page) == CLEAN_STOP, label


def test_a_stop_closes_an_open_task_window(played):
    seen = reached(played, "stop_with_open_task")
    assert seen["worker_station_closed"] == 1
    assert seen["lobby_phase"] == "lobby"
    for label, page in seen["seen"].items():
        assert stopped_cleanly(page) == CLEAN_STOP, label


def test_a_leave_in_the_countdown_starts_no_round(played):
    seen = reached(played, "countdown_leave")
    assert seen["lobby_phase"] == "lobby"
    assert seen["roles_after"] == {label: 0 for label in seen["roles_after"]}
    assert seen["countdown_shown"] == {label: False for label in seen["countdown_shown"]}
    assert set(seen["last_phase"].values()) == {"lobby"}
    assert seen["errors"] == {label: [] for label in seen["errors"]}


def test_the_host_leaving_in_the_role_reveal_stops_the_round_and_hands_over(played):
    seen = reached(played, "host_leaves_in_reveal")
    assert all(seen["cards_shown"].values())
    assert seen["lobby_phase"] == "lobby"
    assert seen["host_area_on_new_host"] is True
    for label, page in seen["seen"].items():
        assert page["notices"].count(STOPPED) == 1, (label, page)
        assert f"The host left. {seen['new_host']} is the new host." in page["notices"], (label, page)
        assert page["last_phase"] == "lobby" and not page["classic_panel"] and not page["end_screen"], (label, page)


def test_after_a_stop_the_new_host_starts_a_duel_that_runs(played):
    seen = reached(played, "duel_after_stop")
    assert seen["lobby_phase"] == "round"
    assert all(seen["duel_panels"].values())
    assert not any(seen["classic_panels"].values())
    assert all(count > 0 for count in seen["positions"].values())
    assert seen["errors"] == {label: [] for label in seen["errors"]}


# ---- Everything -----------------------------------------------------------


def test_the_whole_play_ran_without_console_errors(played):
    assert played["stage"] == "done", played["errors"]
    assert played["problems"] == []
