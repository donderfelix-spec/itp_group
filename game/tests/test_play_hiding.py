"""The play test of to-do M3-1.4 "hiding", as repeatable tests in Chromium.

What the tester played with five browsers in Classic and two in Duel is
played here by real Chromium pages (Playwright, driven through
`play_hiding_in_browser.js`) against the real server with its real tick:

- Classic, five players, so one Free Rider (found from the role card of his
  page). He walks with real keys into each of the four hiding spots, the one
  in the hedge from the spawn, into the hedge and through it. For every spot
  one High Performer stands about 55 units away and must neither be sent nor
  draw the Free Rider; another walks past him with real keys, and is sent
  and draws him exactly while he is within 35 units; then he walks out of
  the spot and is drawn at his new place at once. Only the Free Rider's own
  page shows him half transparent and the word "Hidden".
- A High Performer in a hiding spot is sent to everybody and sees no "Hidden".
- A ghost sees the hidden Free Rider from far away; the living are not sent
  the ghost, during the round and during a meeting.
- A meeting (the emergency button) does not reveal the hidden Free Rider,
  and after it everything is as before.
- The end of a round, by a vote and by parity while the Free Rider hides,
  sends everybody everybody again without anybody moving.
- A Free Rider who leaves the lobby while he hides is gone for everybody, his
  "Hidden" is gone, and joining again is refused with the text of DESIGN.md,
  section 9.
- Duel: a player in a hiding spot is sent to the other from far away, and
  the Duel runs to its end.

Not everything is walked: going from one hiding spot to the next would take
long and land somewhere else every time, so a player is put where a walk
starts (as `task_helpers.put` does for the stations) and then walks with real
key presses. The server runs in this process (uvicorn in a thread), so the
test can put players and set the server's clock forward instead of waiting
45 seconds for the emergency button, 75 for a meeting and 15 per fail.

Skipped when Node, Playwright or Chromium is missing. Screenshots go to the
folder in HIDING_SCREENSHOTS, if that is set.
"""

import json
import math
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
from collections import deque
from pathlib import Path

import pytest
import uvicorn

from server import main
from server.accounts.leaderboard_cache import LeaderboardCache
from server.accounts.statistics_store import MemoryStatisticsStore
from server.accounts.store import MemoryAccountStore
from server.main import app
from server.net.attempts import AttemptLimits
from server.net.lobbies import Lobbies
from server.net.repeated_faults import RepeatedFaults
from server.net.sessions import Sessions
from server.world import paths
from server.world.movement import is_free

CAMPUS = app.state.campus
SOLIDS, WIDTH, HEIGHT = CAMPUS["solids"], CAMPUS["width"], CAMPUS["height"]
SPAWN = (CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"])
REVEAL_RANGE = CAMPUS["hide_reveal_range"]
SPOTS = {name: spot for name, spot in zip(("hedge", "pingo-doce", "ctt", "canteen"), CAMPUS["hiding_spots"])}
HEDGE = next(solid for solid in SOLIDS if solid["id"] == "deck-hedge")
BUTTON = CAMPUS["button"]

BROWSER_SCRIPT = Path(__file__).with_name("play_hiding_in_browser.js")
NODE = shutil.which("node")
NPM = shutil.which("npm")
SCREENSHOTS = os.environ.get("HIDING_SCREENSHOTS")

KEYS = {(1, 0): "KeyD", (-1, 0): "KeyA", (0, 1): "KeyS", (0, -1): "KeyW"}
# Positions carry one decimal: a distance this close to 35 may go either way.
ROUNDING = 0.2
# A page draws a player it was told about within this time, and stops
# drawing one it was told is gone within this time (a few frames).
DRAW_LAG_MS = 120


# ---- Chromium ------------------------------------------------------------


def node_environment():
    environment = dict(os.environ)
    if NPM:
        root = subprocess.run([NPM, "root", "-g"], capture_output=True, text=True, check=False).stdout.strip()
        environment["NODE_PATH"] = os.pathsep.join(filter(None, [environment.get("NODE_PATH"), root]))
    return environment


def playwright_works():
    if NODE is None:
        return False
    probe = "require('playwright').chromium.launch().then(b => b.close())"
    finished = subprocess.run([NODE, "-e", probe], env=node_environment(), capture_output=True, timeout=60, check=False)
    return finished.returncode == 0


pytestmark = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


class Browser:
    """The Chromium pages of one play, driven through play_hiding_in_browser.js."""

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

    # What a page received and drew

    def frames(self, label, since):
        """The `positions` messages the page got since `since` (its own clock): [(t, {name: (x, y)})]."""
        found = self.js(label, f"""window.__received
            .filter((r) => r.t >= {since} && r.m.type === 'positions')
            .map((r) => [r.t, r.m.players.map((p) => [p.name, p.x, p.y])])""")
        return [(t, {name: (x, y) for name, x, y in players}) for t, players in found]

    def messages(self, label, kind, since=0):
        return self.js(label, f"""window.__received
            .filter((r) => r.t >= {since} && r.m.type === '{kind}').map((r) => r.m)""")

    def drawn(self, label, character, since):
        """When and where the page drew this character on the map since `since`: [(t, x, y, alpha)]."""
        return [tuple(row) for row in self.js(label, f"""window.__drawn
            .filter((d) => d.t >= {since} && d.character === '{character}')
            .map((d) => [d.t, d.x, d.y, d.alpha])""")]

    def hidden_hint(self, label):
        """Whether the page shows "Hidden", and where (in CSS pixels of the 1280 x 800 window)."""
        return self.js(label, """(() => {
            const hint = document.getElementById('classic-hidden-hint');
            if (!hint) return { exists: false, shown: false };
            const box = hint.getBoundingClientRect();
            const panel = document.getElementById('classic-progress').getBoundingClientRect();
            const bar = document.querySelector('#classic-progress [role="progressbar"]').getBoundingClientRect();
            const shown = !hint.hidden && box.width > 0 && !document.getElementById('classic-progress').hidden;
            return { exists: true, shown, text: hint.textContent,
                     box: [box.left, box.top, box.width, box.height],
                     panel: [panel.left, panel.top, panel.width, panel.height], bar_bottom: bar.bottom };
        })()""")


# ---- The server in this process -----------------------------------------


class Clock:
    """The server's clock (`main.seconds_now`): the real one, plus the seconds the test skipped."""

    def __init__(self):
        self.skipped = 0.0

    def __call__(self):
        return time.monotonic() + self.skipped

    def skip(self, seconds):
        self.skipped += seconds


def fresh_server_state():
    """What conftest.py's fresh_accounts_and_sessions sets, for the play of one fixture."""
    app.state.account_store = MemoryAccountStore()
    app.state.statistics_store = MemoryStatisticsStore()
    app.state.leaderboard_cache = LeaderboardCache()
    app.state.leaderboard_call = None
    app.state.sessions = Sessions()
    app.state.attempt_limits = AttemptLimits()
    app.state.lobbies = Lobbies()
    app.state.repeated_faults = RepeatedFaults()
    main.taking_positions.clear()


@pytest.fixture(autouse=True)
def quiet_tick():
    """Replaces the fixture of the same name in conftest.py: here the real tick runs."""


@pytest.fixture(scope="module")
def server():
    fresh_server_state()
    clock = Clock()
    real_clock = main.seconds_now
    main.seconds_now = clock
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


def lobby_of(name):
    return app.state.lobbies.lobby_of(name)


def position(name):
    return lobby_of(name).walkers.position_of(name)


def put(name, place):
    """Put a player where a walk starts, as `task_helpers.put` does, and tell everybody."""
    walkers = lobby_of(name).walkers
    walkers._walkers[name].position = (float(place[0]), float(place[1]))
    walkers._everybody_needs_news()


def wait_until(condition, what, seconds=15.0):
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, f"timed out: {what}"
        time.sleep(0.02)


def standing_still(name, seconds=0.25):
    """Wait until the player has not moved for `seconds` (a few ticks)."""
    last, since = position(name), time.monotonic()
    deadline = time.monotonic() + 10
    while time.monotonic() - since < seconds:
        assert time.monotonic() < deadline, f"{name} does not stand still"
        time.sleep(0.02)
        now = position(name)
        if now != last:
            last, since = now, time.monotonic()
    return last


# ---- Walking with real keys ----------------------------------------------

GRID = paths.Grid(SOLIDS, WIDTH, HEIGHT)
STEP = paths.GRID_STEP


def grid_route(start, goal):
    """The shortest way on the grid of paths.py with straight steps only, as points in map units."""
    first = GRID.nearest_free_point(*start, 3 * STEP)
    last = GRID.nearest_free_point(*goal, 3 * STEP)
    assert first is not None and last is not None, (start, goal)
    came_from = {first: None}
    waiting = deque([first])
    while waiting and last not in came_from:
        point = waiting.popleft()
        for dx, dy in paths.STRAIGHT_STEPS:
            neighbour = (point[0] + dx, point[1] + dy)
            if neighbour not in came_from and GRID.is_free(neighbour):
                came_from[neighbour] = point
                waiting.append(neighbour)
    assert last in came_from, f"no way from {start} to {goal}"
    route = [last]
    while came_from[route[-1]] is not None:
        route.append(came_from[route[-1]])
    return [(column * STEP, row * STEP) for column, row in reversed(route)]


def hold(browser, label, name, direction, target):
    """Hold the walk key of `direction` until the player is about at `target` on that axis."""
    axis = 0 if direction[0] else 1
    sign = direction[axis]
    browser.call("down", label=label, key=KEYS[direction])
    try:
        deadline = time.monotonic() + 10
        last, since = position(name)[axis], time.monotonic()
        while sign * (target - position(name)[axis]) > 3:
            assert time.monotonic() < deadline, f"{name} did not get to {target}"
            time.sleep(0.005)
            now = position(name)[axis]
            if now != last:
                last, since = now, time.monotonic()
            elif time.monotonic() - since > 0.4:
                break  # blocked: the caller looks for another way
    finally:
        browser.call("up", label=label, key=KEYS[direction])
    standing_still(name)


def walk_to(browser, label, name, goal, within=5):
    """Walk the player with key presses until his centre is `within` units of `goal`.

    Each time: the way on the grid from where he stands, the first point of
    it more than 3 units away, and one walk key held towards it (and on, as
    long as the way goes straight on).
    """
    for _ in range(60):
        here = position(name)
        if math.dist(here, goal) <= within:
            return here
        way = grid_route(here, goal)[1:] + [goal]
        index = next(i for i, point in enumerate(way) if max(abs(point[0] - here[0]), abs(point[1] - here[1])) > 3)
        point = way[index]
        axis = 0 if abs(point[0] - here[0]) >= abs(point[1] - here[1]) else 1
        sign = 1 if point[axis] > here[axis] else -1
        target = point[axis]
        while (index + 1 < len(way) and abs(way[index + 1][1 - axis] - point[1 - axis]) < 1
               and sign * (way[index + 1][axis] - way[index][axis]) > 0):
            index += 1
            target = way[index][axis]
        hold(browser, label, name, (sign, 0) if axis == 0 else (0, sign), target)
    raise AssertionError(f"{name} did not get to {goal}, stands at {position(name)}")


def free_place_at(centre, distance, near=None):
    """A free place `distance` units from `centre` (in a direction near `near`, if given)."""
    places = []
    for step_ in range(72):
        angle = step_ * math.pi / 36
        place = (round(centre[0] + distance * math.cos(angle)), round(centre[1] + distance * math.sin(angle)))
        if is_free(place[0], place[1], SOLIDS, WIDTH, HEIGHT) and GRID.nearest_free_point(*place, 2) is not None:
            places.append(place)
    assert places, f"no free place {distance} units from {centre}"
    if near is None:
        return places[0]
    return min(places, key=lambda place: math.dist(place, near))


def entry_for(spot):
    """A free place about 20 units from the spot, from where one walk key leads straight into it."""
    for distance in (20, 16, 24):
        for direction in KEYS:
            start = (spot["x"] - direction[0] * distance, spot["y"] - direction[1] * distance)
            line = [(spot["x"] - direction[0] * t, spot["y"] - direction[1] * t) for t in range(distance + 1)]
            if all(is_free(x, y, SOLIDS, WIDTH, HEIGHT) for x, y in line):
                return start, direction
    raise AssertionError(f"no straight way into {spot}")


def in_spot(place, spot):
    return math.dist(place, (spot["x"], spot["y"])) <= spot["r"]


def walk_into(browser, label, name, spot):
    """Walk in with one key from the entry place until the centre is well inside the spot."""
    start, direction = entry_for(spot)
    put(name, start)
    standing_still(name)
    axis = 0 if direction[0] else 1
    hold(browser, label, name, direction, (spot["x"], spot["y"])[axis])
    here = position(name)
    assert in_spot(here, spot), f"{name} stands at {here}, not in {spot}"
    return here, start


# ---- What a page was told and drew ---------------------------------------


def character_of(browser, label, name):
    states = browser.messages(label, "lobby_state")
    return next(player["character"] for player in states[-1]["players"] if player["name"] == name)


def visibility_mistakes(frames, own, hider, hider_at):
    """The frames in which `hider` was listed though farther than 35 units, or missing though within."""
    mistakes = []
    for t, listed in frames:
        if own not in listed:
            mistakes.append((t, "own position missing"))
            continue
        distance = math.dist(listed[own], hider_at)
        if abs(distance - REVEAL_RANGE) <= ROUNDING:
            continue
        if (hider in listed) != (distance <= REVEAL_RANGE):
            mistakes.append((t, round(distance, 1), hider in listed))
    return mistakes


def drawn_while_unlisted(frames, draws, hider):
    """Draws of the hider later than DRAW_LAG_MS after a frame that left him out, before he was listed again."""
    wrong = []
    for index, (t, listed) in enumerate(frames):
        if hider in listed:
            continue
        until = next((later for later, again in frames[index + 1:] if hider in again), math.inf)
        wrong += [draw for draw in draws if t + DRAW_LAG_MS < draw[0] < until]
    return sorted(set(wrong))


def write_down(name, seen):
    """Everything a play saw, as JSON next to the screenshots (for the report of a play test)."""
    if SCREENSHOTS:
        Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
        (Path(SCREENSHOTS) / f"{name}.json").write_text(json.dumps(seen, indent=1, default=str))


# ---- The Classic play ----------------------------------------------------

LABELS = ["P0", "P1", "P2", "P3", "P4"]


def start_round(browser, host, labels, seen_rounds):
    """The host starts Classic; returns {label: role} from the role cards after the countdown."""
    browser.call("click", label=host, selector="#lobby-start")
    for label in labels:
        browser.wait(label, f"""window.__received.filter((r) => r.m.type === 'classic_role').length > {seen_rounds}""")
        browser.wait(label, "!document.getElementById('classic-role-card').hidden")
    roles = {label: browser.js(label, "document.getElementById('classic-role-name').textContent") for label in labels}
    for label in labels:
        # The role card closes by itself; then the keys walk.
        browser.wait(label, "document.getElementById('classic-role-card').hidden", timeout=15000)
        browser.js(label, "document.activeElement && document.activeElement.blur()")
    return roles


def play_one_spot(browser, spot_name, fr, far, near, others):
    """The Free Rider hides in one spot; `far` stands 55 units away, `near` walks past him."""
    names = browser.names
    spot = SPOTS[spot_name]
    centre = (spot["x"], spot["y"])
    record = {"spot": spot_name}
    fr_character = character_of(browser, far, names[fr])

    # The far High Performer first, and the Free Rider at the entry: he is
    # seen there by the far one, which shows the far one would draw him.
    start, direction = entry_for(spot)
    far_place = free_place_at(centre, 55, near=start)
    put(names[far], far_place)
    put(names[fr], start)
    standing_still(names[fr])
    time.sleep(0.3)
    marks = {label: browser.now(label) for label in LABELS}
    before = browser.drawn(far, fr_character, marks[far] - 300)
    record["far_draws_fr_before"] = before != []
    # The figure is drawn a little above the player's place: measure by how much.
    record["drawn_offset"] = (before[-1][1] - start[0], before[-1][2] - start[1]) if before else None
    fr_at, _ = walk_into(browser, fr, names[fr], spot)
    record["fr_at"] = fr_at
    record["far_distance"] = math.dist(far_place, fr_at)
    time.sleep(0.4)
    settled = {label: browser.now(label) for label in LABELS}
    record["fr_hint"] = browser.hidden_hint(fr)
    record["fr_own_alpha"] = sorted({row[3] for row in browser.drawn(fr, fr_character, settled[fr] - 200)})
    browser.shot(fr, f"{spot_name}_1_free_rider_hidden")
    browser.shot(far, f"{spot_name}_2_far_high_performer")

    # The near High Performer walks from 55 units to within 35 and back out.
    near_from = free_place_at(centre, 55, near=far_place if spot_name != "hedge" else (595, 300))
    near_to = free_place_at(centre, 22, near=near_from)
    put(names[near], near_from)
    standing_still(names[near])
    walk_start = browser.now(near)
    walk_to(browser, near, names[near], near_to)
    record["near_closest"] = math.dist(position(names[near]), fr_at)
    time.sleep(0.3)
    record["near_draws_fr_when_close"] = browser.drawn(near, fr_character, browser.now(near) - 200) != []
    browser.shot(near, f"{spot_name}_3_near_high_performer_close")
    walk_to(browser, near, names[near], near_from)
    time.sleep(0.4)
    browser.shot(near, f"{spot_name}_4_near_high_performer_away_again")
    near_frames = browser.frames(near, walk_start)
    record["near_mistakes"] = visibility_mistakes(near_frames, names[near], names[fr], fr_at)
    record["near_listed_some"] = any(names[fr] in listed for _, listed in near_frames)
    record["near_last_listed"] = names[fr] in near_frames[-1][1] if near_frames else None
    record["near_frozen_draws"] = drawn_while_unlisted(near_frames, browser.drawn(near, fr_character, walk_start), names[fr])
    record["near_hint"] = browser.hidden_hint(near)

    # Nobody farther than 35 was sent or drew him: the far one and the others.
    record["far_frames"] = 0
    record["far_mistakes"] = {}
    for label in [far] + others:
        frames = browser.frames(label, settled[label])
        record["far_frames"] += len(frames)
        mistakes = visibility_mistakes(frames, names[label], names[fr], fr_at)
        late_draws = [row for row in browser.drawn(label, fr_character, settled[label] + DRAW_LAG_MS)]
        if mistakes or late_draws:
            record["far_mistakes"][label] = {"frames": mistakes[:5], "draws": late_draws[:5]}
        record.setdefault("hp_hints", {})[label] = browser.hidden_hint(label)["shown"]
        # The messages themselves: the format of `positions` and no trace of him.
        record.setdefault("traces", {})[label] = browser.js(label, f"""window.__received
            .filter((r) => r.t >= {settled[label]} && r.m.type === 'positions')
            .filter((r) => Object.keys(r.m).sort().join() !== 'players,type'
                || r.m.players.some((p) => Object.keys(p).sort().join() !== 'name,x,y')
                || JSON.stringify(r.m).includes({json.dumps(names[fr])}))
            .length""")

    # He walks out again: the far one gets him at once, drawn at the new place.
    out_mark = browser.now(far)
    back = (direction[0] * -1, direction[1] * -1)
    hold(browser, fr, names[fr], back, start[0 if back[0] else 1])
    record["fr_out_at"] = position(names[fr])
    time.sleep(0.4)
    far_frames = browser.frames(far, out_mark)
    record["far_sees_fr_after_leaving"] = bool(far_frames) and names[fr] in far_frames[-1][1]
    first_draws = browser.drawn(far, fr_character, out_mark)
    record["far_first_draw_after_leaving"] = (
        (first_draws[0][1] - record["drawn_offset"][0], first_draws[0][2] - record["drawn_offset"][1])
        if first_draws and record["drawn_offset"] else None
    )
    record["fr_hint_after_leaving"] = browser.hidden_hint(fr)["shown"]
    browser.shot(far, f"{spot_name}_5_far_high_performer_after_leaving")
    return record


def told_after(browser, label, kind):
    """The page's time at which it got its newest message of this kind."""
    return browser.js(label, f"window.__received.filter((r) => r.m.type === '{kind}').pop().t")


def lists_after_end(browser, labels):
    """For every page: who its newest `positions` message after its `classic_result` lists."""
    listed = {}
    for label in labels:
        frames = browser.frames(label, told_after(browser, label, "classic_result"))
        listed[label] = sorted(frames[-1][1]) if frames else []
    return listed


def everybody_where_they_are(names):
    return {name: position(name) for name in names}


def press_fail(browser, label):
    """Press Q as a player does: once the page shows that a fail is possible.

    The page sends `fail` only while its newest `classic_fail_status` says
    "available" and "in range" (the button "Let fail" lights up).
    """
    try:
        browser.wait(label, """(() => {
            const status = window.__received.filter((r) => r.m.type === 'classic_fail_status').pop();
            return Boolean(status) && status.m.available === true && status.m.in_range === true;
        })()""", timeout=5000)
    except AssertionError:
        name = browser.names[label]
        classic = lobby_of(name).classic_round
        raise AssertionError(
            f"no fail possible for {name}: last statuses "
            f"{browser.js(label, 'window.__received.filter((r) => r.m.type === `classic_fail_status`).slice(-3).map((r) => [r.t, r.m])')}, "
            f"now {browser.now(label)}, server: phase {classic.phase}, eliminated {classic.eliminated}, "
            f"last fail {classic.last_fail_at}, clock {main.seconds_now()}, "
            f"positions {[(n, lobby_of(name).walkers.position_of(n)) for n in classic.roles]}, "
            f"later messages {browser.js(label, 'window.__received.slice(-8).map((r) => [r.t, r.m.type])')}, "
            f"needs news {[w.needs_news for w in lobby_of(name).walkers._walkers.values()]}, "
            f"busy {len(main.taking_positions)}, background {len(main.background_sends)}"
        )
    browser.call("press", label=label, key="KeyQ")


def failed(browser, label, victim):
    """Wait until the server has answered the fail of `victim` completely.

    The server first takes the victim out and then tells everybody, the
    Free Rider's page last of all its positions. A player put somewhere in
    between would be told in those positions while the Free Rider's
    "Let fail" stays as it was (nobody moves afterwards), so the test waits.
    """
    browser.wait(label, f"""(() => {{
        const fail = window.__received.find((r) => r.m.type === 'classic_fail' && r.m.target_id === {json.dumps(victim)});
        return Boolean(fail) && window.__received.some((r) => r.t > fail.t && r.m.type === 'classic_roster');
    }})()""")
    time.sleep(0.2)


def press_at_button(browser, label, name):
    put(name, (BUTTON["x"] + 8, BUTTON["y"]))
    standing_still(name)
    browser.wait(label, "document.querySelector('.use-button') && document.querySelector('.use-button').textContent.includes('Emergency')")
    browser.call("press", label=label, key="KeyE")


def wait_for_meeting_phase(browser, labels, phase, count):
    for label in labels:
        browser.wait(label, f"""window.__received.filter((r) => r.m.type === 'meeting_state' && r.m.phase === '{phase}').length >= {count}""")


@pytest.fixture(scope="module")
def classic(server):
    base, clock = server
    browser = Browser(base)
    seen = {"spots": []}
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

        # Round 1
        roles = start_round(browser, "P0", LABELS, 0)
        seen["roles"] = roles
        fr = next(label for label, role in roles.items() if role == "Free Rider")
        hps = [label for label in LABELS if label != fr]
        assert app.state.lobbies.lobby_of(names[fr]).classic_round.roles[names[fr]] == "FR"
        browser.shot(fr, "0_round_started_free_rider")

        # The hedge: walked to from the spawn, into it and through it.
        put(names[fr], SPAWN)
        standing_still(names[fr])
        hedge = SPOTS["hedge"]
        walk_to(browser, fr, names[fr], (hedge["x"], HEDGE["y"] + HEDGE["h"] + 12))
        through_mark = time.monotonic()
        trail = []
        browser.call("down", label=fr, key="KeyW")
        while position(names[fr])[1] > HEDGE["y"] - 12 and time.monotonic() - through_mark < 5:
            trail.append(position(names[fr]))
            time.sleep(0.01)
        browser.call("up", label=fr, key="KeyW")
        standing_still(names[fr])
        seen["hedge_walk"] = {"trail_in_hedge": [p for p in trail if HEDGE["y"] <= p[1] <= HEDGE["y"] + HEDGE["h"]],
                              "end": position(names[fr]), "in_spot_on_the_way": any(in_spot(p, hedge) for p in trail)}

        # The four spots
        far, near, other1, other2 = hps
        for spot_name in SPOTS:
            put(names[other1], SPAWN)
            put(names[other2], (SPAWN[0] - 60, SPAWN[1]))
            seen["spots"].append(play_one_spot(browser, spot_name, fr, far, near, [other1, other2]))

        # A High Performer in a spot: everybody gets him, nobody sees "Hidden".
        spot = SPOTS["pingo-doce"]
        put(names[fr], free_place_at((spot["x"], spot["y"]), 55))
        put(names[far], SPAWN)
        mark = {label: browser.now(label) for label in LABELS}
        hp_at, _ = walk_into(browser, near, names[near], spot)
        time.sleep(0.5)
        hp_character = character_of(browser, near, names[near])
        seen["hp_in_spot"] = {
            "at": hp_at,
            "listed_by": {label: names[near] in browser.frames(label, mark[label])[-1][1] for label in LABELS if label != near},
            "distances": {label: round(math.dist(position(names[label]), hp_at), 1) for label in LABELS if label != near},
            "drawn_by_fr": browser.drawn(fr, hp_character, browser.now(fr) - 200) != [],
            "own_alpha": sorted({row[3] for row in browser.drawn(near, hp_character, browser.now(near) - 200)}),
            "hints": {label: browser.hidden_hint(label)["shown"] for label in LABELS},
        }
        browser.shot(near, "6_high_performer_in_spot_own_page")
        browser.shot(fr, "6_high_performer_in_spot_seen_by_free_rider")

        # A ghost: the Free Rider fails `other2` beside the hedge, then hides.
        victim = other2
        put(names[fr], (HEDGE["x"] + 20, HEDGE["y"] + HEDGE["h"] + 14))
        put(names[victim], (HEDGE["x"] + 23, HEDGE["y"] + HEDGE["h"] + 14))
        standing_still(names[fr])
        press_fail(browser, fr)
        failed(browser, fr, names[victim])
        put(names[victim], (SPAWN[0] - 40, SPAWN[1] + 20))
        put(names[other1], (BUTTON["x"] + 8, BUTTON["y"] + 30))
        fr_at, _ = walk_into(browser, fr, names[fr], SPOTS["hedge"])
        time.sleep(0.5)
        marks = {label: browser.now(label) for label in LABELS}
        # The ghost walks around (through walls) while the Free Rider hides.
        browser.call("down", label=victim, key="KeyD")
        time.sleep(0.6)
        browser.call("up", label=victim, key="KeyD")
        standing_still(names[victim])
        time.sleep(0.3)
        fr_character = character_of(browser, victim, names[fr])
        ghost_frames = browser.frames(victim, marks[victim])
        seen["ghost"] = {
            "distance": math.dist(position(names[victim]), fr_at),
            "frames": len(ghost_frames),
            "frames_without_fr": sum(names[fr] not in listed for _, listed in ghost_frames),
            "draws_fr": browser.drawn(victim, fr_character, marks[victim] + DRAW_LAG_MS) != [],
            "hint": browser.hidden_hint(victim)["shown"],
            "living_frames_with_ghost": {
                label: sum(names[victim] in listed for _, listed in browser.frames(label, marks[label]))
                for label in LABELS if label != victim
            },
            "living_frames": {label: len(browser.frames(label, marks[label])) for label in LABELS if label != victim},
            "living_frames_with_fr": {
                label: sum(names[fr] in listed for _, listed in browser.frames(label, marks[label]))
                for label in (far, near, other1)
            },
        }
        browser.shot(victim, "7_ghost_sees_hidden_free_rider")

        # A meeting while he hides: `other1` presses the emergency button.
        clock.skip(50)
        caller = other1
        press_at_button(browser, caller, names[caller])
        wait_for_meeting_phase(browser, LABELS, "discussion", 1)
        assert lobby_of(names[fr]).classic_round.phase == "meeting"
        browser.shot(caller, "8_meeting_seen_by_caller")
        browser.shot(fr, "8_meeting_seen_by_hidden_free_rider")
        # The pages hold every character during the meeting, but the server
        # still sends positions when somebody's place changes (it does not
        # stop walking yet, M3-3.13): a player is put a little further.
        discussion = {label: told_after(browser, label, "meeting_state") for label in LABELS}
        for step_ in range(3):
            put(names[caller], (BUTTON["x"] + 8, BUTTON["y"] + 2 * step_))
            put(names[victim], (SPAWN[0] - 30, SPAWN[1] + 10 * step_))
            time.sleep(0.2)
        time.sleep(0.3)
        in_meeting = {label: browser.frames(label, discussion[label]) for label in LABELS}
        clock.skip(46)
        wait_for_meeting_phase(browser, LABELS, "voting", 1)
        clock.skip(31)
        wait_for_meeting_phase(browser, LABELS, "result", 1)
        time.sleep(0.5)
        during = {}
        for label in (far, near, caller):
            frames = in_meeting[label]
            during[label] = {"frames": len(frames), "with_fr": sum(names[fr] in listed for _, listed in frames),
                             "distance": round(math.dist(position(names[label]), fr_at), 1)}
        seen["meeting"] = {
            "during": during,
            "fr_still_in_spot": in_spot(position(names[fr]), SPOTS["hedge"]),
            "phase_after": lobby_of(names[fr]).classic_round.phase,
            "eliminated_after": sorted(lobby_of(names[fr]).classic_round.eliminated),
            "victim": names[victim],
            "fr_hint_after": browser.hidden_hint(fr)["shown"],
            "hints": {label: browser.hidden_hint(label)["shown"] for label in hps},
            "ghost_frames_with_fr": sum(names[fr] in listed for _, listed in in_meeting[victim]),
            "ghost_frames": len(in_meeting[victim]),
            "living_frames_with_ghost_during_meeting": {
                label: sum(names[victim] in listed for _, listed in in_meeting[label])
                for label in (far, near, caller, fr)
            },
            "living_draws_ghost_during_meeting": {
                label: len(browser.drawn(label, character_of(browser, victim, names[victim]), discussion[label]))
                for label in (far, near, caller, fr)
            },
        }
        browser.shot(fr, "9_after_meeting_free_rider")

        # After the meeting: the far ones still do not get him; he walks out and in.
        after = {label: browser.now(label) for label in LABELS}
        browser.call("down", label=far, key="KeyD")
        time.sleep(0.3)
        browser.call("up", label=far, key="KeyD")
        standing_still(names[far])
        time.sleep(0.3)
        seen["after_meeting"] = {
            label: visibility_mistakes(browser.frames(label, after[label]), names[label], names[fr], position(names[fr]))
            for label in (far, near, caller)
        }
        seen["after_meeting_frames"] = {label: len(browser.frames(label, after[label])) for label in (far, near, caller)}

        # Round end by a vote: `near` calls the second meeting, all vote him out.
        clock.skip(5)
        press_at_button(browser, near, names[near])
        wait_for_meeting_phase(browser, LABELS, "discussion", 2)
        clock.skip(46)
        wait_for_meeting_phase(browser, LABELS, "voting", 2)
        for label in (far, near, caller):
            browser.wait(label, f"""document.querySelector('.classic-vote-player[data-target-id="{names[fr]}"]') !== null""")
            browser.call("click", label=label, selector=f'.classic-vote-player[data-target-id="{names[fr]}"]')
        wait_until(lambda: len(lobby_of(names[fr]).meeting["votes"]) == 3 if lobby_of(names[fr]).meeting else True, "the votes")
        put(names[far], free_place_at((SPOTS["hedge"]["x"], SPOTS["hedge"]["y"]), 55))
        standing_still(names[far])
        clock.skip(31)
        for label in LABELS:
            browser.wait(label, "window.__received.some((r) => r.m.type === 'classic_result')")
        wait_until(lambda: lobby_of(names[fr]).phase == "lobby", "the lobby after the vote")
        places_at_end = everybody_where_they_are(names.values())
        time.sleep(0.6)
        seen["end_by_vote"] = {
            "result": browser.messages("P0", "classic_result")[-1],
            "fr": names[fr],
            "after_end": lists_after_end(browser, LABELS),
            "nobody_moved": everybody_where_they_are(names.values()) == places_at_end,
            "hints": {label: browser.hidden_hint(label)["shown"] for label in LABELS},
        }
        browser.shot("P0", "10_lobby_after_vote")
        browser.shot(fr, "10_lobby_after_vote_free_rider")

        # Round 2: the Free Rider wins by parity while he hides.
        for label in LABELS:
            browser.js(label, "document.getElementById('classic-back-lobby') && !document.getElementById('classic-end-screen').hidden && document.getElementById('classic-back-lobby').click()")
        roles2 = start_round(browser, "P0", LABELS, 1)
        seen["roles2"] = roles2
        fr2 = next(label for label, role in roles2.items() if role == "Free Rider")
        hps2 = [label for label in LABELS if label != fr2]
        spot = SPOTS["pingo-doce"]
        fr2_at, _ = walk_into(browser, fr2, names[fr2], spot)
        watcher = hps2[0]
        put(names[watcher], free_place_at((spot["x"], spot["y"]), 55))
        standing_still(names[watcher])
        watch_mark = browser.now(watcher)
        for victim2 in hps2[1:]:
            put(names[victim2], (fr2_at[0], fr2_at[1] + 3))
            standing_still(names[victim2])
            press_fail(browser, fr2)
            failed(browser, fr2, names[victim2])
            if lobby_of(names[fr2]).classic_round is not None:
                put(names[victim2], (SPAWN[0], SPAWN[1] + 30))
            clock.skip(16)
        wait_until(lambda: lobby_of(names[fr2]).phase == "lobby", "the end of round 2")
        places_at_end = everybody_where_they_are(names.values())
        time.sleep(0.8)
        ended = {label: told_after(browser, label, "classic_result") for label in LABELS}
        watcher_before = [frame for frame in browser.frames(watcher, watch_mark) if frame[0] < ended[watcher]]
        fr2_character = character_of(browser, watcher, names[fr2])
        seen["end_by_parity"] = {
            "result": browser.messages(watcher, "classic_result")[-1],
            "fr": names[fr2],
            "fr_in_spot_at_end": in_spot(position(names[fr2]), spot),
            "watcher_distance": round(math.dist(position(names[watcher]), position(names[fr2])), 1),
            "watcher_frames_before_end": len(watcher_before),
            "watcher_listed_fr_before_end": any(names[fr2] in listed for _, listed in watcher_before),
            "after_end": lists_after_end(browser, LABELS),
            "nobody_moved": everybody_where_they_are(names.values()) == places_at_end,
            "watcher_draws_fr": browser.drawn(watcher, fr2_character, ended[watcher] + DRAW_LAG_MS) != [],
            "fr_hint": browser.hidden_hint(fr2)["shown"],
            "fr_alpha": sorted({row[3] for row in browser.drawn(fr2, character_of(browser, fr2, names[fr2]), ended[fr2] + 200)}),
        }
        browser.shot(watcher, "11_lobby_after_parity_watcher")
        browser.shot(fr2, "11_lobby_after_parity_free_rider")

        # Round 3: the Free Rider leaves the lobby while he hides.
        for label in LABELS:
            browser.js(label, "!document.getElementById('classic-end-screen').hidden && document.getElementById('classic-back-lobby').click()")
        roles3 = start_round(browser, "P0", LABELS, 2)
        fr3 = next(label for label, role in roles3.items() if role == "Free Rider")
        stay = [label for label in LABELS if label != fr3]
        fr3_at, _ = walk_into(browser, fr3, names[fr3], SPOTS["hedge"])
        put(names[stay[0]], free_place_at((SPOTS["hedge"]["x"], SPOTS["hedge"]["y"]), 55))
        standing_still(names[stay[0]])
        time.sleep(0.3)
        hint_before = browser.hidden_hint(fr3)["shown"]
        fr3_character = character_of(browser, stay[0], names[fr3])
        leave_mark = {label: browser.now(label) for label in stay}
        browser.call("click", label=fr3, selector="#lobby-leave")
        wait_until(lambda: lobby_of(names[fr3]) is None, "the Free Rider left")
        time.sleep(0.5)
        join_mark = browser.now(fr3)
        browser.call("fill", label=fr3, selector="#join-code", text=code)
        browser.call("click", label=fr3, selector="#join-submit")
        rejection = browser.wait(fr3, f"window.__received.filter((r) => r.t > {join_mark} && r.m.type === 'error').map((r) => r.m).pop() || null")
        time.sleep(0.3)
        seen["leave_while_hidden"] = {
            "hint_before": hint_before,
            "hint_after": browser.hidden_hint(fr3)["shown"],
            "rejection": rejection,
            "rejection_shown": browser.js(fr3, f"document.body.innerText.includes({json.dumps(rejection['message'])})"),
            "others_draw_him": {label: len(browser.drawn(label, fr3_character, leave_mark[label] + 300)) for label in stay},
            "others_lists": {label: sorted(browser.frames(label, leave_mark[label])[-1][1]) if browser.frames(label, leave_mark[label]) else None for label in stay},
            "health": json.loads(urllib.request.urlopen(base + "/health", timeout=5).read()),
            "left": names[fr3],
        }
        browser.shot(fr3, "14_free_rider_left_while_hidden_and_tried_to_join")
        seen["names"] = dict(names)
        seen["fr"], seen["fr2"] = fr, fr2
        # Who ever saw "Hidden", in which round (round 2 starts with the second role card).
        seen["hint_shown"] = {}
        for label in LABELS:
            second, third = browser.js(label, "window.__received.filter((r) => r.m.type === 'classic_role').slice(1, 3).map((r) => r.t)")
            samples = browser.js(label, "window.__hintShown")
            seen["hint_shown"][label] = {"round 1": sum(t < second for t in samples),
                                         "round 2": sum(second <= t < third for t in samples)}
    finally:
        seen["console"] = browser.close()
        write_down("classic", seen)
    return seen


# ---- The tests: Classic ---------------------------------------------------


def test_the_four_spots_are_the_ones_of_the_map():
    assert {name: (spot["x"], spot["y"]) for name, spot in SPOTS.items()} == {
        "hedge": (595, 249), "pingo-doce": (549, 468), "ctt": (136, 524), "canteen": (636, 128),
    }
    assert REVEAL_RANGE == 35


def test_five_players_have_exactly_one_free_rider_on_the_role_cards(classic):
    assert sorted(classic["roles"].values()) == ["Free Rider"] + ["High Performer"] * 4


def test_the_free_rider_walks_from_the_spawn_into_the_hedge_and_through_it(classic):
    walk = classic["hedge_walk"]
    assert walk["trail_in_hedge"] != []
    assert walk["in_spot_on_the_way"]
    assert walk["end"][1] < HEDGE["y"]  # out at the other side


@pytest.mark.parametrize("spot_index", range(4), ids=list(SPOTS))
def test_the_free_rider_walks_into_the_spot_and_is_hidden_from_far_high_performers(classic, spot_index):
    record = classic["spots"][spot_index]
    assert in_spot(record["fr_at"], SPOTS[record["spot"]])
    assert record["far_draws_fr_before"], "the far one did not even draw him outside the spot"
    assert record["far_distance"] > REVEAL_RANGE
    assert record["far_frames"] > 0
    assert record["far_mistakes"] == {}
    assert record["traces"] == {label: 0 for label in record["traces"]}


@pytest.mark.parametrize("spot_index", range(4), ids=list(SPOTS))
def test_a_high_performer_walking_past_gets_the_free_rider_exactly_within_35_units(classic, spot_index):
    record = classic["spots"][spot_index]
    assert record["near_closest"] <= REVEAL_RANGE
    assert record["near_mistakes"] == []
    assert record["near_listed_some"]
    assert record["near_draws_fr_when_close"]
    assert record["near_last_listed"] is False


@pytest.mark.parametrize("spot_index", range(4), ids=list(SPOTS))
def test_no_frozen_free_rider_is_left_drawn_when_he_disappears(classic, spot_index):
    assert classic["spots"][spot_index]["near_frozen_draws"] == []


@pytest.mark.parametrize("spot_index", range(4), ids=list(SPOTS))
def test_only_the_hidden_free_rider_sees_himself_half_transparent_and_hidden(classic, spot_index):
    record = classic["spots"][spot_index]
    hint = record["fr_hint"]
    assert hint["shown"] and hint["text"] == "Hidden"
    # In the Classic panel on the right, below the progress bar.
    assert hint["box"][1] >= hint["bar_bottom"]
    assert hint["panel"][0] <= hint["box"][0] <= hint["panel"][0] + hint["panel"][2]
    assert record["fr_own_alpha"] == [0.5]
    assert not record["near_hint"]["shown"]
    assert not any(record["hp_hints"].values())


@pytest.mark.parametrize("spot_index", range(4), ids=list(SPOTS))
def test_walking_out_of_the_spot_shows_him_at_once_at_his_new_place(classic, spot_index):
    record = classic["spots"][spot_index]
    spot = SPOTS[record["spot"]]
    assert not in_spot(record["fr_out_at"], spot)
    assert record["far_sees_fr_after_leaving"]
    first = record["far_first_draw_after_leaving"]
    assert first is not None
    assert not in_spot(first, spot), "drawn first where he hid, not where he is"
    assert record["fr_hint_after_leaving"] is False


def test_a_high_performer_in_a_spot_is_sent_to_everybody_and_sees_no_hidden(classic):
    record = classic["hp_in_spot"]
    assert all(record["listed_by"].values()), record
    assert max(record["distances"].values()) > REVEAL_RANGE
    assert record["drawn_by_fr"]
    assert record["own_alpha"] == [1]
    assert not any(record["hints"].values())


def test_a_ghost_sees_the_hidden_free_rider_from_far_and_the_living_do_not_get_the_ghost(classic):
    ghost = classic["ghost"]
    assert ghost["distance"] > REVEAL_RANGE
    assert ghost["frames"] > 0 and ghost["frames_without_fr"] == 0
    assert ghost["draws_fr"]
    assert not ghost["hint"]
    assert all(ghost["living_frames"].values())
    assert ghost["living_frames_with_ghost"] == {label: 0 for label in ghost["living_frames_with_ghost"]}
    assert ghost["living_frames_with_fr"] == {label: 0 for label in ghost["living_frames_with_fr"]}


def test_a_meeting_does_not_reveal_the_hidden_free_rider(classic):
    meeting = classic["meeting"]
    assert meeting["fr_still_in_spot"]
    for label, told in meeting["during"].items():
        assert told["distance"] > REVEAL_RANGE
        assert told["frames"] > 0
        assert told["with_fr"] == 0, label
    # The ghost still sees him during the meeting.
    assert meeting["ghost_frames"] > 0 and meeting["ghost_frames_with_fr"] == meeting["ghost_frames"]


def test_living_pages_do_not_draw_the_ghost_during_a_meeting(classic):
    # The server does send the ghost's position to the living during a
    # meeting (`living_frames_with_ghost_during_meeting` is recorded above):
    # Classic's own filter in `tell_positions` only works in the phase
    # "round". That defect was on main before hiding and is M3-3.20 in
    # TODO.md (Laurin). Here only what the pages draw is checked.
    meeting = classic["meeting"]
    assert meeting["living_draws_ghost_during_meeting"] == {
        label: 0 for label in meeting["living_draws_ghost_during_meeting"]
    }


def test_after_the_meeting_the_round_goes_on_and_he_is_still_hidden(classic):
    meeting = classic["meeting"]
    assert meeting["phase_after"] == "round"
    assert meeting["eliminated_after"] == [meeting["victim"]]
    assert meeting["fr_hint_after"]
    assert not any(meeting["hints"].values())
    assert all(classic["after_meeting_frames"].values())
    assert classic["after_meeting"] == {label: [] for label in classic["after_meeting"]}


def test_after_the_round_ends_by_a_vote_everybody_sees_everybody(classic):
    end = classic["end_by_vote"]
    assert end["result"]["winner"] == "HP"
    everybody = sorted(classic["names"].values())
    assert end["after_end"] == {label: everybody for label in LABELS}
    assert end["nobody_moved"]
    assert not any(end["hints"].values())


def test_after_the_free_rider_wins_by_parity_while_hidden_everybody_sees_him_without_moving(classic):
    end = classic["end_by_parity"]
    assert end["result"]["winner"] == "FR"
    assert end["fr_in_spot_at_end"]
    assert end["watcher_distance"] > REVEAL_RANGE
    assert end["watcher_frames_before_end"] > 0 and not end["watcher_listed_fr_before_end"]
    everybody = sorted(classic["names"].values())
    assert end["after_end"] == {label: everybody for label in LABELS}
    assert end["nobody_moved"]
    assert end["watcher_draws_fr"]
    assert not end["fr_hint"]
    assert end["fr_alpha"] == [1]


def test_only_the_free_rider_of_the_round_ever_saw_hidden(classic):
    shown = classic["hint_shown"]
    for label in LABELS:
        if label != classic["fr"]:
            assert shown[label]["round 1"] == 0, label
        if label != classic["fr2"]:
            assert shown[label]["round 2"] == 0, label
    assert shown[classic["fr"]]["round 1"] > 0
    assert shown[classic["fr2"]]["round 2"] > 0


def test_a_free_rider_who_leaves_while_hidden_is_gone_for_all_and_cannot_come_back_in(classic):
    left = classic["leave_while_hidden"]
    assert left["hint_before"] and not left["hint_after"]
    assert left["rejection"] == {"type": "error", "code": "round_running", "message": "This round has already started."}
    assert left["rejection_shown"]
    assert left["others_draw_him"] == {label: 0 for label in left["others_draw_him"]}
    assert all(lists is None or left["left"] not in lists for lists in left["others_lists"].values())
    assert left["health"]["status"] == "ok"


def test_no_console_error_or_warning_in_any_of_the_five_pages(classic):
    assert classic["console"] == []


# ---- Duel ------------------------------------------------------------------


@pytest.fixture(scope="module")
def duel(server):
    base, clock = server
    fresh_server_state()
    browser = Browser(base)
    seen = {}
    try:
        for label in ("D0", "D1"):
            browser.open(label)
        names = browser.names
        browser.call("click", label="D0", selector="#home-create")
        browser.wait("D0", "/[A-Z0-9]{4}/.test(document.getElementById('lobby-code').textContent)")
        code = browser.js("D0", "document.getElementById('lobby-code').textContent.match(/[A-Z0-9]{4}/)[0]")
        browser.call("fill", label="D1", selector="#join-code", text=code)
        browser.call("click", label="D1", selector="#join-submit")
        browser.wait("D1", "!document.getElementById('screen-lobby').hidden")
        browser.call("click", label="D0", selector='#lobby-modes button:has-text("Duel")')
        time.sleep(0.3)
        browser.call("click", label="D0", selector="#lobby-start")
        for label in ("D0", "D1"):
            browser.wait(label, "window.__received.some((r) => r.m.type === 'duel_state')")
            browser.js(label, "document.activeElement && document.activeElement.blur()")
        wait_until(lambda: lobby_of(names["D0"]).duel is not None, "the Duel")
        hider = "D0"
        hider_character = character_of(browser, "D1", names[hider])
        results = {}
        for spot_name, spot in SPOTS.items():
            put(names["D1"], free_place_at((spot["x"], spot["y"]), 55))
            mark = browser.now("D1")
            at, _ = walk_into(browser, hider, names[hider], spot)
            time.sleep(0.4)
            frames = browser.frames("D1", mark)
            results[spot_name] = {
                "at": at,
                "distance": round(math.dist(position(names["D1"]), at), 1),
                "frames": len(frames),
                "frames_without_hider": sum(names[hider] not in listed for _, listed in frames),
                "drawn": browser.drawn("D1", hider_character, browser.now("D1") - 200) != [],
                "own_alpha": sorted({row[3] for row in browser.drawn(hider, character_of(browser, hider, names[hider]), browser.now(hider) - 200)}),
                "hint": browser.hidden_hint(hider)["shown"],
            }
            browser.shot("D1", f"12_duel_{spot_name}_other_player")
            browser.shot(hider, f"12_duel_{spot_name}_player_in_spot")
        seen["spots"] = results
        # The Duel runs to its end (its clock, set forward) and back to the lobby.
        the_duel = lobby_of(names["D0"]).duel
        clock.skip(the_duel.seconds_left(main.seconds_now()) + 1)
        for label in ("D0", "D1"):
            browser.wait(label, "window.__received.some((r) => r.m.type === 'duel_result')")
        wait_until(lambda: lobby_of(names["D0"]).phase == "lobby", "the lobby after the Duel")
        seen["result"] = browser.messages("D0", "duel_result")[-1]
        seen["phase"] = lobby_of(names["D0"]).phase
        browser.shot("D0", "13_duel_ranking")
    finally:
        seen["console"] = browser.close()
        write_down("duel", seen)
    return seen


@pytest.mark.parametrize("spot_name", list(SPOTS))
def test_in_duel_a_player_in_a_hiding_spot_is_sent_and_drawn_far_away_without_hidden(duel, spot_name):
    record = duel["spots"][spot_name]
    assert in_spot(record["at"], SPOTS[spot_name])
    assert record["distance"] > REVEAL_RANGE
    assert record["frames"] > 0 and record["frames_without_hider"] == 0
    assert record["drawn"]
    assert record["own_alpha"] == [1]
    assert not record["hint"]


def test_the_duel_still_runs_to_its_end(duel):
    assert duel["result"]["type"] == "duel_result"
    assert duel["phase"] == "lobby"


def test_no_console_error_or_warning_in_the_two_duel_pages(duel):
    assert duel["console"] == []
