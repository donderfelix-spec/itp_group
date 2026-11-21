"""Helpers for the tests of "bridge the gaps" (M2-1.16).

A test describes what the player does (keys) and how the connection behaves
(how late each `positions` message arrives). The helpers here play the part
of the server with the server's own rule (server/world/movement.py), deliver
its messages late, and run the page's own bridge.js, world.js and
diagnostic.js in Node (tests/world_bridge_in_node.js) with a frame every
1000/fps ms.

Times are in ms on the browser's clock. The numbers of the connection are
those measured on the deployed game on 2026-11-20: the server ticks every
68 ms and moves a walking player 6.1 map units per tick.
"""

import json
import math
import shutil
import subprocess
from pathlib import Path

from server.main import app
from server.protocol import CHARACTERS
from server.world import movement
from world_tracking import with_tracked_player

TESTS = Path(__file__).resolve().parent
WORLD_IN_NODE = TESTS / "world_bridge_in_node.js"
TRACES = TESTS / "network_trace"
NODE = shutil.which("node")

CAMPUS = app.state.campus
SOLIDS = CAMPUS["solids"]
WIDTH = CAMPUS["width"]
HEIGHT = CAMPUS["height"]
SPAWN = (CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"])

OWN = "Mara"
OTHER = "Tiago"
OWN_CHARACTER = CHARACTERS[0]
OTHER_CHARACTER = CHARACTERS[1]

SERVER_TICK = 68.0  # ms between two ticks of the deployed server
SERVER_STEP = 6.1  # map units the server moves a walking player per tick
WAY_UP = 20  # ms a key takes to the server
WAY_DOWN = 25  # ms a message takes to the browser when it is not held up
TICK = 1000 / 15  # the browser's tick: the length of a bridged step's glide, ms
# Ticks of a server that are not all equally long: the map units of each
# step, used in a loop. Their median is SERVER_STEP.
UNEVEN_STEPS = [6.1, 6.22, 6.02, 6.1, 6.18, 6.06, 6.1, 6.14, 6.0]

# The server's first tick; the following ones come every SERVER_TICK.
FIRST_TICK = 13.0
# In every scenario the player stands on the spawn and presses the first key now.
KEY_AT = 1000

FIRST_FRAME = 5.0

# Which way the walk keys go: (dx, dy).
KEY_DIRECTIONS = {"KeyD": (1, 0), "KeyA": (-1, 0), "KeyW": (0, -1), "KeyS": (0, 1)}

# Less than this, in map units, is the same place: far below one pixel.
EXACT = 1e-6
# A drawn character that moved less than this between two frames stood (as in diagnostic.js).
SAME_PLACE = 0.01


def trace(name):
    """The extra delay of each message in ms, from a file in tests/network_trace."""
    return json.loads((TRACES / name).read_text(encoding="utf-8"))


FELIX = trace("felix_2026-11-20.json")  # about every 410 ms one message 105 ms late
FELIX_DEBUG_RUN = trace("felix_debug_run_2026-11-20.json")  # one hold-up of 620 ms, four of 240 ms
FELIX_BAD_SECOND = trace("felix_2026-11-20_bad_second.json")  # gaps of 201 and 365 ms within one second


# ---- How late the messages arrive -------------------------------------------------


# Each of these returns a function (number, sent_at) -> extra delay in ms:
# `number` counts the messages the server sent after the placement, from 0,
# and `sent_at` is the time of the server's tick.


def on_time():
    return lambda number, sent_at: 0


def looped(delays, first=0):
    """Message `first` gets the first delay of the list; the list is used in a loop."""
    return lambda number, sent_at: delays[(number - first) % len(delays)] if number >= first else 0


def held(**hold_ups):
    """`held(m30=600)`: message 30 is held 600 ms; all others are on time."""
    by_number = {int(name[1:]): milliseconds for name, milliseconds in hold_ups.items()}
    return lambda number, sent_at: by_number.get(number, 0)


def held_from(time, milliseconds):
    """The message of the server's first tick at `time` or later is held; all others are on time."""
    return lambda number, sent_at: milliseconds if time <= sent_at < time + SERVER_TICK else 0


def later_from(time, milliseconds):
    """From `time` on every message takes `milliseconds` longer: the connection got slower for good."""
    return lambda number, sent_at: milliseconds if sent_at >= time else 0


# ---- The server ----------------------------------------------------------------------


def direction_at(keys, time):
    """The direction of the keys held at `time`. `keys` is [(time, "down" or "up", code)], in order."""
    pressed = set()
    for at, up_or_down, code in keys:
        if at > time:
            break
        if up_or_down == "down":
            pressed.add(code)
        else:
            pressed.discard(code)
    dx = sum(KEY_DIRECTIONS[code][0] for code in pressed)
    dy = sum(KEY_DIRECTIONS[code][1] for code in pressed)
    return (dx, dy)


def server_ticks(keys, until, start=SPAWN, stands_from=math.inf, step_lengths=(SERVER_STEP,)):
    """What the server computes: [(time, (x, y), moved)] for every tick up to `until`.

    A key reaches the server WAY_UP ms after it was pressed. From
    `stands_from` on the server keeps the player standing whatever the keys
    say (a task was opened). `step_lengths` are the map units a walking
    player covers in each tick, used in a loop: the server measures the
    time since its last tick, and not every tick is equally long.
    """
    place = start
    ticks = []
    time = FIRST_TICK
    while time <= until:
        dx, dy = (0, 0) if time >= stands_from else direction_at(keys, time - WAY_UP)
        seconds = step_lengths[len(ticks) % len(step_lengths)] / movement.PLAYER_SPEED
        after = movement.step(place[0], place[1], dx, dy, seconds, SOLIDS, WIDTH, HEIGHT)
        ticks.append((time, after, after != place))
        place = after
        time += SERVER_TICK
    return ticks


def circling(centre, radius=20, per_tick=0.3):
    """Another player who walks in a circle: a function from the tick number to (x, y)."""
    return lambda number: (centre[0] + radius * math.cos(per_tick * number), centre[1] + radius * math.sin(per_tick * number))


def standing(place):
    return lambda number: place


class Scenario:
    """A walk of the own player on a connection, ready to be played in the browser's code.

    keys          [(time, "down" or "up", code)]: what the player does
    delays        how late each message is: a function (number, sent_at) -> ms, see on_time()
    until         the scenario ends at this time
    start         where the own player stands at the beginning
    other         a function from the tick number to the place of a second player, or None
    stands_from   see server_ticks()
    step_lengths  see server_ticks()
    silent_from   the server sends nothing from this time on (it is the test's
                  way to say that the server never walked what the keys asked)
    skipped       times: the server's first tick at or after each sends no
                  message (this browser was still busy with the one before),
                  so the next message holds two steps
    steps         more steps for the harness, each [name, time, ...]
    """

    def __init__(self, keys, delays, until, start=SPAWN, other=None, stands_from=math.inf, silent_from=math.inf,
                 step_lengths=(SERVER_STEP,), skipped=(), steps=()):
        self.keys = sorted(keys)
        self.until = until
        self.start = start
        self.has_other = other is not None
        self.steps = list(steps)
        self.ticks = server_ticks(self.keys, until, start, stands_from, step_lengths)
        self.sent = self._messages(other, silent_from, skipped)
        self.messages = self._deliver(delays)

    def _messages(self, other, silent_from, skipped):
        """[(sent_at, players)]: one message per tick in which somebody moved."""
        first = [{"name": OWN, "x": self.start[0], "y": self.start[1]}]
        if other:
            first.append({"name": OTHER, "x": other(0)[0], "y": other(0)[1]})
        sent = [(-WAY_DOWN, first)]  # the placement: it arrives at time 0
        before = other(0) if other else None
        for number, (time, place, moved) in enumerate(self.ticks):
            players = [{"name": OWN, "x": place[0], "y": place[1]}]
            if other:
                now = other(number + 1)
                players.append({"name": OTHER, "x": now[0], "y": now[1]})
                moved = moved or now != before
                before = now
            is_skipped = any(at <= time < at + SERVER_TICK for at in skipped)
            if moved and time < silent_from and not is_skipped:
                sent.append((time, players))
        return sent

    def _deliver(self, delays):
        """[(arrives_at, players, sent_at)]. A held message never overtakes an earlier one (TCP keeps the order)."""
        messages = []
        last = -math.inf
        for number, (sent_at, players) in enumerate(self.sent[1:]):
            last = max(sent_at + WAY_DOWN + delays(number, sent_at), last)
            messages.append((last, players, sent_at))
        return [(0, self.sent[0][1], -WAY_DOWN)] + messages

    # -- What the server did --

    def server_place(self, time=math.inf):
        """Where the server has the own player at `time` (at the end, by default)."""
        place = self.start
        for at, after, _ in self.ticks:
            if at > time:
                break
            place = after
        return place

    def server_path(self):
        """Every place the server had the own player at, in order."""
        return [self.start] + [place for _, place, moved in self.ticks if moved]

    def known_place(self, time):
        """The newest own position that has arrived in the browser by `time`."""
        place = self.start
        for arrives_at, players, _ in self.messages:
            if arrives_at > time:
                break
            place = (players[0]["x"], players[0]["y"])
        return place

    def arrival(self, number):
        """When message `number` of the walk arrives (0 is the first after the placement)."""
        return self.messages[number + 1][0]

    def last_arrival(self):
        return self.messages[-1][0]

    # -- Playing it --

    def run(self, fps=60, search="", bridge=True, ask=None, usable=None):
        """Play the scenario in the page's code. Returns the harness's output (see the harness)."""
        events = [(time, 0, ["key", time, up_or_down, code]) for time, up_or_down, code in self.keys]
        events += [(arrives_at, 1, ["positions", arrives_at, players]) for arrives_at, players, _ in self.messages]
        events += [(step[1], 2, list(step)) for step in self.steps]
        # The frames start a little after the first message. Each time is
        # worked out on its own (not added up), so a frame that exists at
        # two frame rates has the same time at both.
        number = 0
        while FIRST_FRAME + number * 1000 / fps <= self.until:
            frame = FIRST_FRAME + number * 1000 / fps
            events.append((frame, 3, ["frame", frame]))
            number += 1
        # At the same moment: the key, then the message, then the frame.
        events.sort(key=lambda event: (event[0], event[1]))
        players = [{"name": OWN, "character": OWN_CHARACTER}]
        if self.has_other:
            players.append({"name": OTHER, "character": OTHER_CHARACTER})
        program = {
            "own": OWN,
            "players": players,
            "search": search,
            "bridge": bridge,
            "ask": ask,
            "usable": usable,
            "steps": [event[2] for event in events],
        }
        finished = subprocess.run(
            [NODE, str(WORLD_IN_NODE)], input=json.dumps(program), capture_output=True, text=True, timeout=120, check=False
        )
        assert finished.returncode == 0, finished.stderr
        result = json.loads(finished.stdout)
        result["frames"] = with_tracked_player(result["frames"], players, OWN)
        return result


def longest_open_run():
    """The start (x, y) and the length of the longest straight way to the right on the map.

    Found with the server's rule, so it stays right when the map changes.
    """
    best = (0, None)
    for y in range(movement.PLAYER_HALF_SIZE, HEIGHT - movement.PLAYER_HALF_SIZE + 1, 4):
        x = float(movement.PLAYER_HALF_SIZE)
        while x < WIDTH - movement.PLAYER_HALF_SIZE:
            if any(movement.overlaps(x, y, solid) for solid in SOLIDS):
                x += 1
                continue
            end = wall_ahead((x, y), 1, 0)[0]
            best = max(best, (end - x, (x, float(y))))
            x = end + 1
    return best[1], best[0]


def open_square(size):
    """The top left corner (x, y) of a square of the map without any solid, `size` units wide.

    A player can walk anywhere inside it, also right up to its edges.
    """
    half = movement.PLAYER_HALF_SIZE

    def is_clear(x, y):
        return not any(
            x + size + half > solid["x"] and x - half < solid["x"] + solid["w"]
            and y + size + half > solid["y"] and y - half < solid["y"] + solid["h"]
            for solid in SOLIDS
        )

    for y in range(half, HEIGHT - size - half + 1, 3):
        for x in range(half, WIDTH - size - half + 1, 3):
            if is_clear(x, y):
                return (float(x), float(y))
    raise AssertionError(f"the map has no open square of {size} units")


def distance_to_path(point, path):
    """How far `point` is from the line through the places of `path`, in map units."""
    best = math.inf
    for a, b in zip(path, path[1:]):
        length_squared = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
        share = 0.0
        if length_squared > 0:
            share = ((point[0] - a[0]) * (b[0] - a[0]) + (point[1] - a[1]) * (b[1] - a[1])) / length_squared
            share = max(0.0, min(1.0, share))
        nearest = (a[0] + (b[0] - a[0]) * share, a[1] + (b[1] - a[1]) * share)
        best = min(best, math.dist(point, nearest))
    return best


def walk_right(delays, until=7000, release_at=None, **more):
    """The player presses "right" at KEY_AT and holds it (or releases it at `release_at`).

    By default the walk starts at the left end of the longest open way of
    the map, so the player can walk for seconds without meeting a wall.
    """
    keys = [(KEY_AT, "down", "KeyD")]
    if release_at is not None:
        keys.append((release_at, "up", "KeyD"))
    more.setdefault("start", OPEN_START)
    return Scenario(keys, delays, until, **more)


# ---- Reading the frames ----------------------------------------------------------------


def place(frame):
    """The drawn player's ground position, independently of camera clamping."""
    return (frame["tracked"]["x"], frame["tracked"]["y"])


def drawn(frame, character):
    """A character as drawn in this frame, or None."""
    return next((c for c in frame["characters"] if c["character"] == character), None)


def between(frames, start, end=math.inf):
    return [frame for frame in frames if start <= frame["t"] <= end]


def pairs(frames, start, end=math.inf):
    """(the frame before, the frame) for every frame with start <= t <= end."""
    return [(before, frame) for before, frame in zip(frames, frames[1:]) if start <= frame["t"] <= end]


def speeds(frames, start, end=math.inf):
    """The speed of the own character in every frame with start <= t <= end, in map units per second."""
    return [math.dist(place(before), place(frame)) / ((frame["t"] - before["t"]) / 1000)
            for before, frame in pairs(frames, start, end)]


def frozen(frames, start, end=math.inf):
    """The times of the frames in which the own character did not move."""
    return [frame["t"] for before, frame in pairs(frames, start, end) if math.dist(place(before), place(frame)) < SAME_PLACE]


def way_back(frames, direction, start=0, end=math.inf):
    """How far the own character moved against `direction` (dx, dy) in total, in map units."""
    length = math.hypot(*direction)
    total = 0.0
    for before, frame in pairs(frames, start, end):
        a, b = place(before), place(frame)
        along = ((b[0] - a[0]) * direction[0] + (b[1] - a[1]) * direction[1]) / length
        total += max(0.0, -along)
    return total


def place_at(frames, time):
    """Where the own character is drawn at `time`: between the two frames around it, in a straight line."""
    for before, frame in zip(frames, frames[1:]):
        if before["t"] <= time <= frame["t"]:
            share = (time - before["t"]) / (frame["t"] - before["t"])
            a, b = place(before), place(frame)
            return (a[0] + (b[0] - a[0]) * share, a[1] + (b[1] - a[1]) * share)
    raise AssertionError(f"no frame around {time}")


def overlapping(frames):
    """The frames in which the own character's square overlaps a solid of the map.

    The place is rounded to a billionth of a unit: a character that touches
    a wall is drawn at the wall, give or take the last digit of a float.
    """
    found = []
    for frame in frames:
        x, y = (round(value, 9) for value in place(frame))
        if any(movement.overlaps(x, y, solid) for solid in SOLIDS):
            found.append(frame["t"])
    return found


def wall_ahead(start, dx, dy):
    """Where a player who walks from `start` in the direction (dx, dy) ends touching a solid."""
    x, y = start
    for _ in range(1000):
        after = movement.step(x, y, dx, dy, 1 / 15, SOLIDS, WIDTH, HEIGHT)
        if after == (x, y):
            return (x, y)
        x, y = after
    raise AssertionError("no solid in this direction")


# The left end of the longest open way to the right, and how long it is in
# map units. At 90 units per second the tests need about 7 seconds of it.
OPEN_START, OPEN_LENGTH = longest_open_run()
