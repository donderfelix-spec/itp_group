"""To-do M2-1.14 "Walking stalls regularly on the deployed site", as repeatable tests.

On a real connection the `positions` messages arrive bunched: about every
410 ms one message is held back about 105 ms and arrives together with the
next one. With a glide of 110 ms from each arrival, the character and the
camera stood still about twice a second. client/js/world/world.js now puts
every position into a short queue per player and plays the queue back at the
server's pace, one tick per position, a little later: about one largest gap
behind the arrivals.

Like test_play_walking_glide.py, these tests run the page's own world.js in
Node (tests/world_playback_in_node.js): a test decides exactly when a message
arrives and when a frame is drawn, and reads where the camera looks and where
every character is drawn. Without Node the tests are skipped; CI has Node.
"""

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from server.main import TICKS_PER_SECOND, app
from server.protocol import CHARACTERS

TESTS = Path(__file__).resolve().parent
WORLD_IN_NODE = TESTS / "world_playback_in_node.js"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

CAMPUS = app.state.campus
SPAWN = (CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"])
USE_RANGE = CAMPUS["use_range"]

TICK = 1000 / TICKS_PER_SECOND  # ms between two positions messages of the server
FRAME = 1000 / 60  # ms between two frames of a 60 Hz screen
FRAME_OFFSET = 5  # the frames start a little after the first message

# Measured by the lead on Felix's connection to the deployed site: the server
# sent a message every 68.2 ms, 6.1 map units apart, and each one arrived this
# many ms later than the one before it would have on time (in a loop).
FELIX_TICK = 68.2
FELIX_STEP = 6.1
FELIX_DELAYS = [8.9, 1.7, 6.5, 3.3, 37.1, 2.0, 2.8, 0.6, 2.4, 37.2, 0.0, 105.8,
                37.6, 2.4, 1.2, 2.0, 2.9, 103.7, 37.5, 14.3, 2.1, 1.9, 1.7, 103.5]

# The playback delay is at most this long, so a position is drawn at the latest
# this long plus one tick after it arrived (see schedulePosition in world.js).
LONGEST_DELAY = 250
STRIDE_FADES = 150  # STRIDE_FADES_MILLISECONDS in world.js

# Less than this, in map units, is the same position: far below one pixel.
EXACT = 1e-6

# The i-th player of a lobby gets the i-th character: Mara the first, Tiago the second.
MARA = CHARACTERS[0]
TIAGO = CHARACTERS[1]


# ---- Helpers ---------------------------------------------------------------


def lobby(players):
    """The lobby list for setPlayers: the i-th name gets the i-th character."""
    return [{"name": name, "character": CHARACTERS[i]} for i, name in enumerate(players)]


def run_world(messages, until, players, own, start_of_round=None, usable=None, paused=None, steps=()):
    """Play `messages` [(t, [{name, x, y}, ...])] into world.js and draw frames until `until` ms.

    `players` are the names in the lobby; each gets its own character.
    `paused` (from, to): no frames in between, as in a hidden tab.
    `steps`: more steps of the lobby page, each a list [name, t, ...] (see the harness).
    Returns one dict per frame: {t, camera, glow, useButtonOn, characters}.
    """
    events = [(t, 0, ["positions", t, places]) for t, places in messages]
    if start_of_round is not None:
        events.append((start_of_round, 0, ["start_of_round", start_of_round]))
    events += [(step[1], 0, list(step)) for step in steps]
    t = FRAME_OFFSET
    while t <= until:
        if paused is None or not paused[0] <= t < paused[1]:
            events.append((t, 1, ["frames", t, t]))
        t += FRAME
    # A message that arrives at the same moment as a frame comes first.
    events.sort(key=lambda event: (event[0], event[1]))
    program = {"own": own, "players": lobby(players), "usable": usable, "steps": [event[2] for event in events]}
    finished = subprocess.run(
        [NODE, str(WORLD_IN_NODE)],
        input=json.dumps(program),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def delivered(places_per_message, tick, extra_delay):
    """Messages produced every `tick` ms; message k arrives `extra_delay(k)` ms later.

    A held-back message never overtakes an earlier one (TCP keeps the order).
    """
    messages = []
    last = -math.inf
    for k, places in enumerate(places_per_message):
        arrives = max(k * tick + extra_delay(k), last)
        messages.append((arrives, places))
        last = arrives
    return messages


def felix(places_per_message):
    """The messages as they arrived on Felix's connection."""
    return delivered(places_per_message, FELIX_TICK, lambda k: FELIX_DELAYS[k % len(FELIX_DELAYS)])


def on_time(places_per_message):
    return delivered(places_per_message, TICK, lambda k: 0)


def walk(name, messages, start, direction, step):
    """Positions of `name` walking from `start` in `direction` (dx, dy), one step per message."""
    return [{"name": name, "x": start[0] + direction[0] * step * k, "y": start[1] + direction[1] * step * k}
            for k in range(messages)]


def camera(frame):
    return (frame["camera"]["x"], frame["camera"]["y"])


def drawn(frame, character):
    """The character as drawn in this frame, or None."""
    return next((c for c in frame["characters"] if c["character"] == character), None)


def drawn_place(frame, character):
    c = drawn(frame, character)
    return (c["x"], c["middleY"])


def moves_per_frame(frames, position_of, start, end=math.inf):
    """How far `position_of(frame)` moved from the frame before, for frames with start <= t <= end."""
    return [math.dist(position_of(before), position_of(frame))
            for before, frame in zip(frames, frames[1:]) if start <= frame["t"] <= end]


def frames_between(frames, start, end=math.inf):
    return [frame for frame in frames if start <= frame["t"] <= end]


# ---- The bunched messages of the deployed site -----------------------------


@needs_node
def test_with_felix_bunched_messages_the_camera_never_stalls_after_the_first_three_seconds():
    count = 160  # 160 x 68.2 ms: almost 11 s of walking
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), FELIX_STEP)]
    messages = felix(places)
    frames = run_world(messages, until=messages[-1][0], players=["Mara"], own="Mara")

    normal = FELIX_STEP / FELIX_TICK * FRAME  # about 1.5 units per frame
    moves = moves_per_frame(frames, camera, 3000)
    assert len(moves) > 400
    # Never standing still, never slower than half the normal speed.
    assert min(moves) >= normal / 2, min(moves)
    # And never a jump: at most the fastest playback (1.25 x) plus a little.
    assert max(moves) < 1.5 * normal, max(moves)


@needs_node
def test_with_felix_bunched_messages_the_camera_never_moves_backwards():
    count = 100
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), FELIX_STEP)]
    messages = felix(places)
    frames = run_world(messages, until=messages[-1][0] + 500, players=["Mara"], own="Mara")

    xs = [frame["camera"]["x"] for frame in frames]
    assert all(a <= b + EXACT for a, b in zip(xs, xs[1:]))
    # The drawn character is where the camera looks, from the first position on.
    shown = frames_between(frames, messages[0][0])
    assert all(abs(drawn(frame, MARA)["x"] - frame["camera"]["x"]) < EXACT for frame in shown)


@needs_node
def test_eight_players_walking_with_bunched_messages_all_move_in_every_frame():
    names = ["Mara", "Tiago", "Ines", "Rui", "Ana", "Joao", "Rita", "Luis"]
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)]
    count = 100  # almost 7 s
    walks = [walk(name, count, (300 + 40 * i, 300 + 30 * i), direction, FELIX_STEP / math.hypot(*direction))
             for i, (name, direction) in enumerate(zip(names, directions))]
    messages = felix([list(places) for places in zip(*walks)])
    frames = run_world(messages, until=messages[-1][0], players=names, own="Mara")

    normal = FELIX_STEP / FELIX_TICK * FRAME
    for character in CHARACTERS[:len(names)]:
        moves = moves_per_frame(frames, lambda frame: drawn_place(frame, character), 3000)
        assert len(moves) > 200
        assert min(moves) >= normal / 2, (character, min(moves))


# ---- Messages on time ------------------------------------------------------


@needs_node
def test_with_messages_on_time_the_camera_moves_the_same_distance_in_every_frame():
    count = 60
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), 6)]
    messages = on_time(places)
    frames = run_world(messages, until=messages[-1][0], players=["Mara"], own="Mara")

    # After the start: the first step is drawn over one whole delay (110 ms).
    moves = moves_per_frame(frames, camera, messages[1][0] + 110 + FRAME)
    normal = 6 / TICK * FRAME
    assert all(abs(move - normal) <= 0.1 * normal for move in moves), (min(moves), max(moves))


# ---- Start, stop and standing ----------------------------------------------


@needs_node
def test_a_walk_starts_in_the_first_frame_after_the_first_step_and_never_goes_backwards():
    # Placed on the spawn, standing for a second (the server sends nothing),
    # then walking right.
    count = 30
    steps = walk("Mara", count, SPAWN, (1, 0), 6)
    first_step_at = 1000
    messages = [(0, [steps[0]])] + [(first_step_at + k * TICK, [place]) for k, place in enumerate(steps[1:])]
    frames = run_world(messages, until=messages[-1][0] + 500, players=["Mara"], own="Mara")

    before = frames_between(frames, 0, first_step_at - EXACT)
    assert all(math.dist(camera(frame), SPAWN) < EXACT for frame in before)
    first_after = frames_between(frames, first_step_at)[0]
    assert first_after["t"] - first_step_at < FRAME
    # No added wait: the camera has already left the spawn in this frame.
    assert first_after["camera"]["x"] > SPAWN[0] + 0.01
    xs = [frame["camera"]["x"] for frame in frames]
    assert all(a <= b + EXACT for a, b in zip(xs, xs[1:]))


@needs_node
def test_a_stop_reaches_the_last_server_position_exactly_in_time_without_overshooting():
    count = 80
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), FELIX_STEP)]
    messages = felix(places)
    last_at = messages[-1][0]
    last = (places[-1][0]["x"], places[-1][0]["y"])
    frames = run_world(messages, until=last_at + 1500, players=["Mara"], own="Mara")

    # Never past the last server position.
    assert all(frame["camera"]["x"] <= last[0] + EXACT for frame in frames)
    # There at the latest the longest delay plus one tick after the last message.
    reached = [frame for frame in frames if math.dist(camera(frame), last) < EXACT]
    assert reached and reached[0]["t"] <= last_at + LONGEST_DELAY + TICK
    # And from then on it stays there.
    assert all(math.dist(camera(frame), last) < EXACT for frame in frames_between(frames, reached[0]["t"]))
    # The feet stop once the steps have faded.
    still = [drawn(frame, MARA) for frame in frames_between(frames, reached[0]["t"] + STRIDE_FADES + FRAME)]
    assert still and all(c["stride"] == 0 and c["walkPhase"] is None for c in still)
    # While the character still moved, its feet did too.
    moving = [drawn(frame, MARA) for frame in frames_between(frames, 3000, reached[0]["t"] - FRAME)]
    assert moving and all(c["stride"] > 0 for c in moving)


@needs_node
def test_without_messages_for_two_seconds_nothing_moves():
    # Mara and Tiago are placed; then the server sends nothing for 2 s.
    placed = [(0, [{"name": "Mara", "x": SPAWN[0], "y": SPAWN[1]}, {"name": "Tiago", "x": 400, "y": 500}])]
    frames = run_world(placed, until=2000, players=["Mara", "Tiago"], own="Mara")

    for frame in frames:
        assert math.dist(camera(frame), SPAWN) < EXACT
        assert drawn(frame, TIAGO)["x"] == 400
        assert all(c["stride"] == 0 and c["walkPhase"] is None for c in frame["characters"])


@needs_node
def test_after_a_walk_and_two_seconds_without_messages_nothing_moves():
    count = 30
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), FELIX_STEP)]
    messages = felix(places)
    last_at = messages[-1][0]
    frames = run_world(messages, until=last_at + 2000, players=["Mara"], own="Mara")

    settled = frames_between(frames, last_at + LONGEST_DELAY + TICK + STRIDE_FADES)
    assert len(settled) > 90
    assert all(camera(frame) == camera(settled[0]) for frame in settled)
    assert all(drawn(frame, MARA)["stride"] == 0 for frame in settled)


# ---- Stations -----------------------------------------------------------------


@needs_node
def test_the_station_glow_follows_the_newest_server_position_while_the_drawing_is_behind():
    station = next(s for s in CAMPUS["stations"] if s["id"] == 2)
    # Mara walks left along the row of the station, past it, with the
    # bunched messages.
    start = (station["x"] + 80, station["y"])
    places = [[place] for place in walk("Mara", 30, start, (-1, 0), FELIX_STEP)]
    messages = felix(places)
    frames = run_world(messages, until=messages[-1][0] + 500, players=["Mara"], own="Mara",
                       usable=[station["id"]])

    def newest_server_place(frame):
        arrived = [places for t, places in messages if t <= frame["t"]]
        return (arrived[-1][0]["x"], arrived[-1][0]["y"]) if arrived else None

    def in_range(place):
        if place is None:
            return False  # no position yet: nothing glows
        return (place[0] - station["x"]) ** 2 + (place[1] - station["y"]) ** 2 <= USE_RANGE ** 2

    glowing_while_drawn_outside = 0
    for frame in frames:
        server_says = in_range(newest_server_place(frame))
        assert (frame["glow"] == station["id"]) == server_says, frame["t"]
        assert frame["useButtonOn"] == server_says, frame["t"]
        if server_says and not in_range(camera(frame)):
            glowing_while_drawn_outside += 1
    # The drawing is behind, and the glow did not wait for it.
    assert glowing_while_drawn_outside > 0


# ---- Jumps and the start of a round -----------------------------------------


@needs_node
def test_a_respawn_far_away_is_drawn_in_the_next_frame_without_waiting_for_the_queue():
    count = 40
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), FELIX_STEP)]
    messages = felix(places)
    respawn = (SPAWN[0] - 200, SPAWN[1] + 100)
    respawn_at = messages[-1][0] + 1  # positions of the walk are still queued
    messages.append((respawn_at, [{"name": "Mara", "x": respawn[0], "y": respawn[1]}]))
    frames = run_world(messages, until=respawn_at + 500, players=["Mara"], own="Mara")

    before = frames_between(frames, 0, respawn_at - EXACT)
    assert math.dist(camera(before[-1]), (places[-1][0]["x"], places[-1][0]["y"])) > 1  # still behind
    after = frames_between(frames, respawn_at)
    assert after[0]["t"] - respawn_at < FRAME
    for frame in after:
        assert math.dist(camera(frame), respawn) < EXACT
        mara = drawn(frame, MARA)
        assert mara["stride"] == 0 and mara["walkPhase"] is None and mara["mirrored"] is False


@needs_node
def test_the_start_of_a_round_puts_a_nearby_character_on_the_spawn_in_one_frame():
    # Tiago walks left towards the spawn and ends 18 units right of it, closer
    # than a jump. Mara walks with him. The round starts while positions are
    # still queued, and the next tick puts both on the spawn.
    count = 30
    tiago_start = (SPAWN[0] + 18 + FELIX_STEP * (count - 1), SPAWN[1])
    tiago = walk("Tiago", count, tiago_start, (-1, 0), FELIX_STEP)
    mara = walk("Mara", count, (SPAWN[0] - 40, SPAWN[1] + 30), (0, 1), FELIX_STEP)
    messages = felix([[m, t] for m, t in zip(mara, tiago)])
    round_at = messages[-1][0] + 1
    back = round_at + TICK
    messages.append((back, [{"name": "Mara", "x": SPAWN[0], "y": SPAWN[1]},
                            {"name": "Tiago", "x": SPAWN[0], "y": SPAWN[1]}]))
    frames = run_world(messages, until=back + 500, players=["Mara", "Tiago"], own="Mara",
                       start_of_round=round_at)

    before = frames_between(frames, 0, round_at - EXACT)
    assert drawn(before[-1], TIAGO)["mirrored"] is True  # Tiago faced left
    after = frames_between(frames, back)
    assert after[0]["t"] - back < FRAME
    for frame in after:
        for character in (MARA, TIAGO):
            c = drawn(frame, character)
            assert math.dist((c["x"], c["middleY"]), drawn_place(after[0], character)) < EXACT
            assert abs(c["x"] - SPAWN[0]) < EXACT
            assert c["mirrored"] is False
            assert c["stride"] == 0 and c["walkPhase"] is None
    assert math.dist(camera(after[0]), SPAWN) < EXACT


# ---- Bursts and hold-ups -------------------------------------------------------


def assert_stops_on_time(frames, messages, last):
    """The camera never goes past `last` nor backwards, and is on `last` at most
    the longest delay plus one tick after the last message, and stays there."""
    last_at = messages[-1][0]
    xs = [frame["camera"]["x"] for frame in frames_between(frames, messages[0][0])]
    assert all(a <= b + EXACT for a, b in zip(xs, xs[1:]))
    assert all(x <= last[0] + EXACT for x in xs)
    on_time_frames = frames_between(frames, last_at + LONGEST_DELAY + TICK)
    assert on_time_frames and all(math.dist(camera(frame), last) < EXACT for frame in on_time_frames)


# After a gap the queue catches up at most this many times faster than the
# server's pace (FASTEST_PACE in world.js), and a queue reaching further than
# the delay plus LONGEST_CATCH_UP after an arrival snaps to the newest position.
FASTEST_PACE = 1.5
LONGEST_CATCH_UP = 600


def too_fast_frames(frames, step, start=0):
    """The frames (from `start` on) in which the camera moved faster than
    FASTEST_PACE times one `step` per server tick."""
    fastest = FASTEST_PACE * step / TICK * FRAME * (1 + 1e-9)
    return [frame for before, frame in zip(frames, frames[1:])
            if frame["t"] >= start and math.dist(camera(before), camera(frame)) > fastest]


def assert_ends_on(frames, messages, last, within):
    """The camera never goes backwards nor past `last`, and is on `last` at
    most `within` ms after the last message, and stays there."""
    xs = [frame["camera"]["x"] for frame in frames_between(frames, messages[0][0])]
    assert all(a <= b + EXACT for a, b in zip(xs, xs[1:]))
    assert all(x <= last[0] + EXACT for x in xs)
    ended = frames_between(frames, messages[-1][0] + within)
    assert ended and all(math.dist(camera(frame), last) < EXACT for frame in ended)


@needs_node
@pytest.mark.parametrize("bursts", [[35], [15, 35]], ids=["at the end", "in the middle and at the end"])
def test_five_messages_at_once_catch_up_at_most_one_and_a_half_times_as_fast(bursts):
    count = 40
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), 6)]
    # From each message in `bursts` on, four are held back and arrive together
    # with the fifth: the queue runs dry, then five positions come at once.
    held = {first + k: first + 4 for first in bursts for k in range(4)}
    messages = delivered(places, TICK, lambda k: (held[k] - k) * TICK if k in held else 0)
    assert abs(messages[35][0] - messages[39][0]) < EXACT
    frames = run_world(messages, until=messages[-1][0] + 1200, players=["Mara"], own="Mara")

    # No jump and no rush: five steps after a hold are no reason to snap.
    assert too_fast_frames(frames, 6, start=messages[1][0]) == []
    assert_ends_on(frames, messages, (places[-1][0]["x"], places[-1][0]["y"]),
                   within=LONGEST_DELAY + LONGEST_CATCH_UP)


@needs_node
def test_a_hold_up_of_two_seconds_and_thirty_messages_at_once_snap_at_once():
    count = 50
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), 6)]
    # From message 20 on nothing arrives for 2 s; then all 30 at once.
    burst_at = 20 * TICK + 2000
    messages = delivered(places, TICK, lambda k: burst_at - k * TICK if k >= 20 else 0)
    assert all(abs(t - burst_at) < EXACT for t, _ in messages[20:])
    frames = run_world(messages, until=burst_at + 1200, players=["Mara"], own="Mara")

    # Catching up 30 steps at 1.5 times the pace would take far too long: one
    # snap, in the first frame after the burst, and otherwise never too fast.
    first_after = frames_between(frames, burst_at)[0]
    assert too_fast_frames(frames, 6, start=messages[1][0]) == [first_after]
    assert_ends_on(frames, messages, (places[-1][0]["x"], places[-1][0]["y"]),
                   within=LONGEST_DELAY + LONGEST_CATCH_UP)


def playback_delay(arrivals, now):
    """The playback delay world.js uses at `now` (playbackDelay()): the largest
    gap of at most 400 ms between the arrivals of the last 3 s, plus 15 ms,
    between 110 and 250 ms."""
    recent = [t for t in arrivals if now - 3000 <= t <= now]
    gaps = [b - a for a, b in zip(recent, recent[1:]) if b - a <= 400]
    return min(LONGEST_DELAY, max(110, max(gaps, default=0) + 15))


@needs_node
def test_with_felix_messages_and_a_long_gap_every_three_seconds_the_drawing_stops_briefly_and_catches_up_smoothly():
    # Felix's bunched messages, and every 44th message (about every 3 s) is held
    # back 400 ms more: longer than the largest delay, so the queue runs dry.
    count = 200  # 200 x 68.2 ms: more than 13 s of walking
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), FELIX_STEP)]
    extra = lambda k: FELIX_DELAYS[k % len(FELIX_DELAYS)] + (400 if k % 44 == 43 else 0)
    messages = delivered(places, FELIX_TICK, extra)
    arrivals = [t for t, _ in messages]
    frames = run_world(messages, until=arrivals[-1] + 1200, players=["Mara"], own="Mara")

    # Never faster than 1.5 times the server's pace (one step per tick), never backwards.
    assert too_fast_frames(frames, FELIX_STEP, start=arrivals[1]) == []
    assert_ends_on(frames, messages, (places[-1][0]["x"], places[-1][0]["y"]),
                   within=LONGEST_DELAY + LONGEST_CATCH_UP)

    long_gaps = [(a, b) for a, b in zip(arrivals, arrivals[1:]) if b - a > 300]
    assert len(long_gaps) == 4
    for gap_start, gap_end in long_gaps:
        delay = playback_delay(arrivals, gap_start)
        # The stop: at most the part of the gap the delay could not cover, plus one frame.
        around = frames_between(frames, gap_start, gap_end + FRAME)
        still = sum(1 for before, frame in zip(around, around[1:])
                    if math.dist(camera(before), camera(frame)) < EXACT)
        assert still * FRAME <= gap_end - gap_start - delay + FRAME, (gap_start, still)
        # Then it goes on at once at least at half the normal speed: no slow
        # first step over the whole delay. (The frame in which it starts again
        # moves only part of a frame.)
        normal = FELIX_STEP / FELIX_TICK * FRAME
        after = frames_between(frames, gap_end, min(gap_end + 1000, arrivals[-1]))
        moves = [math.dist(camera(before), camera(frame)) for before, frame in zip(after, after[1:])]
        started = next(i for i, move in enumerate(moves) if move > EXACT)
        assert all(move >= normal / 2 for move in moves[started + 1:]), (gap_end, min(moves[started + 1:]))
        # 1 s after the gap the drawing is back to at most one delay plus one
        # tick behind the newest position. (Right after that, a bunched message
        # can still put it a few ms further behind once while the last of the
        # catch-up runs out.) From 1.5 s on it stays within that, until the next gap.
        def behind(frame):
            newest = [p for t, p in messages if t <= frame["t"]][-1][0]
            return newest["x"] - frame["camera"]["x"]

        allowed = FELIX_STEP * (delay + TICK) / FELIX_TICK + EXACT
        one_second_after = frames_between(frames, gap_end + 1000)[0]
        assert behind(one_second_after) <= allowed, (gap_end, behind(one_second_after))
        next_gap = min([a for a, _ in long_gaps if a > gap_end], default=arrivals[-1])
        later = frames_between(frames, gap_end + 1500, next_gap)
        assert all(behind(frame) <= allowed for frame in later), gap_end


@needs_node
def test_after_frames_paused_for_five_seconds_the_drawing_is_not_seconds_behind():
    # A hidden tab: the browser draws no frames, the messages keep coming.
    count = 160
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), FELIX_STEP)]
    messages = felix(places)
    paused = (2000, 7000)
    frames = run_world(messages, until=messages[-1][0] + 600, players=["Mara"], own="Mara", paused=paused)

    resumed = frames_between(frames, paused[1])[0]
    newest = [p for t, p in messages if t <= resumed["t"]][-1][0]
    # At most one longest delay plus one tick of walking behind the newest position.
    assert newest["x"] - resumed["camera"]["x"] <= FELIX_STEP * (LONGEST_DELAY + TICK) / FELIX_TICK
    assert_stops_on_time(frames, messages, (places[-1][0]["x"], places[-1][0]["y"]))


# ---- Leaving and the list of players -------------------------------------------


@needs_node
def test_a_long_gap_before_stop_does_not_slow_the_drawing_after_start():
    # Walking, a gap of 380 ms (long, but no pause), then stop() and start().
    before = walk("Mara", 21, SPAWN, (1, 0), 6)
    messages = [(k * TICK, [place]) for k, place in enumerate(before[:20])]
    messages.append((19 * TICK + 380, [before[20]]))
    stop_at = messages[-1][0] + 100
    start_at = stop_at + 100
    # After the new start: a new walk with messages on time.
    first_at = start_at + 100
    after = walk("Mara", 30, (SPAWN[0], SPAWN[1] + 40), (1, 0), 6)
    messages += [(first_at + k * TICK, [place]) for k, place in enumerate(after)]
    steps = [["stop", stop_at], ["start", start_at], ["players", start_at, lobby(["Mara"])]]
    frames = run_world(messages, until=messages[-1][0] + 500, players=["Mara"], own="Mara", steps=steps)

    # The old gap is forgotten: the smallest delay, the same distance in every frame.
    moves = moves_per_frame(frames, camera, first_at + TICK + 110 + FRAME, messages[-1][0])
    normal = 6 / TICK * FRAME
    assert all(abs(move - normal) <= 0.1 * normal for move in moves), (min(moves), max(moves))
    last = (after[-1]["x"], after[-1]["y"])
    there = frames_between(frames, messages[-1][0] + 110 + FRAME)
    assert there and all(math.dist(camera(frame), last) < EXACT for frame in there)


@needs_node
def test_a_player_who_leaves_with_queued_positions_is_no_longer_drawn():
    count = 30
    mara = [{"name": "Mara", "x": SPAWN[0], "y": SPAWN[1]}] * count
    tiago = walk("Tiago", count, (300, 400), (1, 0), FELIX_STEP)
    messages = felix([[m, t] for m, t in zip(mara, tiago)])
    leaves_at = messages[-1][0] + 1  # his last positions are still queued
    steps = [["players", leaves_at, lobby(["Mara"])]]
    frames = run_world(messages, until=leaves_at + 500, players=["Mara", "Tiago"], own="Mara", steps=steps)

    just_before = frames_between(frames, 0, leaves_at)[-1]
    assert drawn(just_before, TIAGO)["x"] < tiago[-1]["x"] - 1  # still behind
    after = frames_between(frames, leaves_at)
    assert after and all(drawn(frame, TIAGO) is None for frame in after)
    assert all(drawn(frame, MARA) is not None for frame in after)


@needs_node
def test_a_standing_player_starts_at_once_while_another_player_walks():
    # Tiago walks the whole time, so every tick brings Mara's same place too.
    count = 60
    starts = 30
    mara = [{"name": "Mara", "x": SPAWN[0], "y": SPAWN[1]}] * starts
    mara += walk("Mara", count - starts + 1, SPAWN, (1, 0), 6)[1:]
    tiago = walk("Tiago", count, (300, 400), (1, 0), 6)
    messages = on_time([[m, t] for m, t in zip(mara, tiago)])
    first_step_at = messages[starts][0]
    frames = run_world(messages, until=messages[-1][0], players=["Mara", "Tiago"], own="Mara")

    standing = frames_between(frames, 0, first_step_at - EXACT)
    assert all(math.dist(camera(frame), SPAWN) < EXACT for frame in standing)
    first_after = frames_between(frames, first_step_at)[0]
    assert first_after["t"] - first_step_at < FRAME
    assert first_after["camera"]["x"] > SPAWN[0] + 0.01


@needs_node
@pytest.mark.parametrize("bursts", [[35], [15]], ids=["at the end", "in the middle"])
def test_a_burst_while_walking_left_keeps_the_character_facing_left_and_walking(bursts):
    # Five messages at once make one queue entry that covers several steps:
    # still a step, not the server putting the player somewhere else.
    count = 40
    places = [[place] for place in walk("Mara", count, SPAWN, (-1, 0), 6)]
    held = {first + k: first + 4 for first in bursts for k in range(4)}
    messages = delivered(places, TICK, lambda k: (held[k] - k) * TICK if k in held else 0)
    last = (places[-1][0]["x"], places[-1][0]["y"])
    frames = run_world(messages, until=messages[-1][0] + 800, players=["Mara"], own="Mara")

    first_step_drawn = messages[1][0] + 2 * FRAME
    shown = frames_between(frames, first_step_drawn)
    assert all(drawn(frame, MARA)["mirrored"] is True for frame in shown)
    # Whenever the character moves, also through the burst, its feet move.
    # (During the hold-up before a burst it may really stand for a moment.)
    moving = [frame for before, frame in zip(shown, shown[1:]) if math.dist(camera(before), camera(frame)) > EXACT]
    merged_glide = [frame for frame in moving if frame["t"] > messages[bursts[0] + 4][0]]
    assert moving and merged_glide
    assert all(drawn(frame, MARA)["stride"] > 0 for frame in moving)
    # After the stop: still facing left, and the feet fade to still.
    reached_at = next(frame["t"] for frame in frames if math.dist(camera(frame), last) < EXACT)
    stopped = frames_between(frames, reached_at)
    assert all(drawn(frame, MARA)["mirrored"] is True for frame in stopped)
    still = frames_between(frames, reached_at + STRIDE_FADES + FRAME)
    assert still and all(drawn(frame, MARA)["stride"] == 0 for frame in still)


@needs_node
def test_after_the_start_of_a_round_the_same_place_as_before_still_ends_the_drawing_there():
    # Mara walks; the round starts while her last positions are still queued,
    # so the drawing stops short of them. The server then sends her same
    # last place again, but only after the placement window (1 s).
    count = 20
    places = [[place] for place in walk("Mara", count, SPAWN, (1, 0), 6)]
    messages = on_time(places)
    round_at = messages[-1][0] + 1
    again_at = round_at + 1000 + 100
    last = (places[-1][0]["x"], places[-1][0]["y"])
    messages.append((again_at, [places[-1][0]]))
    frames = run_world(messages, until=again_at + 600, players=["Mara"], own="Mara", start_of_round=round_at)

    waiting = frames_between(frames, round_at + FRAME, again_at - EXACT)
    assert waiting and all(camera(frame)[0] < last[0] - 1 for frame in waiting)  # stopped short
    ended = frames_between(frames, again_at + LONGEST_DELAY + TICK)
    assert ended and all(math.dist(camera(frame), last) < EXACT for frame in ended)
    xs = [frame["camera"]["x"] for frame in frames_between(frames, messages[0][0])]
    assert all(x <= last[0] + EXACT for x in xs)
