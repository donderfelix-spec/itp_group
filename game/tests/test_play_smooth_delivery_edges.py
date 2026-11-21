"""To-do M2-1.14: edge cases found while play-testing the playback queue in browsers.

The play test drove real Chromium guests through a proxy that replays Felix's
bunched messages. These tests repeat the cases it tried beyond the to-do's own
tests (test_play_smooth_delivery.py), with the page's own world.js in Node:

- the own player stops while somebody else keeps walking, so the server
  keeps sending the same own position on every tick;
- quick turnarounds with bunched messages;
- walking through the start of a round, when the server's first position of
  the round is already one step away from the spawn;
- a frozen page: no frames and no messages for 5 s, then all at once;
- leaving and joining again while walking.
"""

import math

from test_play_smooth_delivery import (
    EXACT,
    FELIX_STEP,
    FRAME,
    LONGEST_DELAY,
    MARA,
    SPAWN,
    STRIDE_FADES,
    TICK,
    TIAGO,
    camera,
    delivered,
    drawn,
    felix,
    frames_between,
    lobby,
    needs_node,
    run_world,
    walk,
)


# drawCharacter gets the middle of the figure: its feet are 5 below the
# position and it is 39 high (FEET_BELOW_POSITION and the figure in world.js).
MIDDLE_ABOVE_POSITION = 39 / 2 - 5


def place_of(character):
    """The server position at which `character` (as drawn) stands."""
    return (character["x"], character["middleY"] + MIDDLE_ABOVE_POSITION)


def turns(xs):
    """How often a list of x values changes direction."""
    count = 0
    last_sign = 0
    for a, b in zip(xs, xs[1:]):
        if abs(b - a) < EXACT:
            continue
        sign = 1 if b > a else -1
        if last_sign and sign != last_sign:
            count += 1
        last_sign = sign
    return count


@needs_node
def test_a_stop_while_another_player_walks_ends_exactly_on_the_last_position_and_stays_there():
    # Tiago walks the whole time, so every message also brings Mara's place.
    # Mara walks 40 steps, then stands: from then on her same place arrives on every tick.
    count = 90
    walking = 40
    mara = walk("Mara", walking, SPAWN, (1, 0), FELIX_STEP)
    mara += [mara[-1]] * (count - walking)
    tiago = walk("Tiago", count, (300, 400), (1, 0), FELIX_STEP)
    messages = felix([[m, t] for m, t in zip(mara, tiago)])
    last_change_at = messages[walking - 1][0]
    last = (mara[-1]["x"], mara[-1]["y"])
    frames = run_world(messages, until=messages[-1][0] + 300, players=["Mara", "Tiago"], own="Mara")

    assert all(frame["camera"]["x"] <= last[0] + EXACT for frame in frames)
    reached = [frame for frame in frames if math.dist(camera(frame), last) < EXACT]
    assert reached and reached[0]["t"] <= last_change_at + LONGEST_DELAY + TICK
    # No slow creep towards it: exactly there from then on, while the same place keeps arriving.
    assert all(math.dist(camera(frame), last) < EXACT for frame in frames_between(frames, reached[0]["t"]))
    still = frames_between(frames, reached[0]["t"] + STRIDE_FADES + FRAME)
    assert still and all(drawn(frame, MARA)["stride"] == 0 and drawn(frame, MARA)["walkPhase"] is None for frame in still)
    # Tiago, seen by Mara, still walks in every frame after the first second.
    xs = [drawn(frame, TIAGO)["x"] for frame in frames_between(frames, 1000, messages[-1][0])]
    assert all(b - a > 0.05 for a, b in zip(xs, xs[1:]))


@needs_node
def test_quick_turnarounds_with_bunched_messages_stay_on_the_server_path_and_end_on_its_last_position():
    # Mara turns around every third step, 60 steps long, on Felix's connection.
    count = 60
    x = SPAWN[0]
    places = []
    for k in range(count):
        places.append([{"name": "Mara", "x": x, "y": SPAWN[1]}])
        x += FELIX_STEP if (k // 3) % 2 == 0 else -FELIX_STEP
    messages = felix(places)
    server_xs = [p[0]["x"] for p in places]
    last = (places[-1][0]["x"], places[-1][0]["y"])
    frames = run_world(messages, until=messages[-1][0] + 600, players=["Mara"], own="Mara")

    drawn_xs = [frame["camera"]["x"] for frame in frames]
    # Never past a turning point: the drawing stays inside the way the server walked.
    assert min(server_xs) - EXACT <= min(drawn_xs) and max(drawn_xs) <= max(server_xs) + EXACT
    # No extra back and forth: at most as many turns as the server made.
    assert turns(drawn_xs) <= turns(server_xs)
    # Never a jump: at most two steps in one frame.
    assert all(abs(b - a) <= 2 * FELIX_STEP for a, b in zip(drawn_xs, drawn_xs[1:]))
    ended = frames_between(frames, messages[-1][0] + LONGEST_DELAY + TICK)
    assert ended and all(math.dist(camera(frame), last) < EXACT for frame in ended)


@needs_node
def test_walking_through_the_start_of_a_round_draws_the_first_place_of_the_round_in_one_frame():
    # Mara and Tiago walk when the round starts. The server puts them on the
    # spawn and, in the same tick, moves them one step on: the first place of
    # the round is one step off the spawn. Then they walk on.
    count = 30
    mara_before = walk("Mara", count, (SPAWN[0] - 60, SPAWN[1] + 40), (1, 0), FELIX_STEP)
    tiago_before = walk("Tiago", count, (SPAWN[0] + 50, SPAWN[1] - 50), (0, 1), FELIX_STEP)
    messages = felix([[m, t] for m, t in zip(mara_before, tiago_before)])
    round_at = messages[-1][0] + 1
    mara_after = walk("Mara", 20, (SPAWN[0] + 6, SPAWN[1]), (1, 0), 6)
    tiago_after = walk("Tiago", 20, (SPAWN[0], SPAWN[1] + 6), (0, 1), 6)
    first_at = round_at + TICK
    messages += [(first_at + k * TICK, [m, t]) for k, (m, t) in enumerate(zip(mara_after, tiago_after))]
    frames = run_world(messages, until=messages[-1][0] + 600, players=["Mara", "Tiago"], own="Mara",
                       start_of_round=round_at)

    after = frames_between(frames, first_at)
    assert after[0]["t"] - first_at < FRAME
    assert math.dist(camera(after[0]), (mara_after[0]["x"], mara_after[0]["y"])) < EXACT
    assert math.dist(place_of(drawn(after[0], TIAGO)), (tiago_after[0]["x"], tiago_after[0]["y"])) < EXACT
    # From there on they only walk on, never back towards the places before the round.
    mara_xs = [frame["camera"]["x"] for frame in after]
    tiago_ys = [drawn(frame, TIAGO)["middleY"] for frame in after]
    assert all(a <= b + EXACT for a, b in zip(mara_xs, mara_xs[1:]))
    assert all(a <= b + EXACT for a, b in zip(tiago_ys, tiago_ys[1:]))
    assert all(drawn(frame, MARA)["mirrored"] is False for frame in after)
    ended = frames_between(frames, messages[-1][0] + LONGEST_DELAY + TICK)
    assert ended and all(math.dist(camera(frame), (mara_after[-1]["x"], mara_after[-1]["y"])) < EXACT for frame in ended)


@needs_node
def test_a_frozen_page_that_gets_five_seconds_of_messages_at_once_is_not_seconds_behind():
    # Mara stands; Tiago walks right. From 1 s to 6 s the page draws nothing and
    # gets nothing (a frozen tab); then all held messages arrive at once.
    count = 150
    mara = [{"name": "Mara", "x": SPAWN[0], "y": SPAWN[1]}] * count
    tiago = walk("Tiago", count, (100, 400), (1, 0), 6)
    frozen = (1000, 6000)
    messages = delivered([[m, t] for m, t in zip(mara, tiago)], TICK,
                         lambda k: frozen[1] - k * TICK if frozen[0] <= k * TICK < frozen[1] else 0)
    frames = run_world(messages, until=messages[-1][0] + 600, players=["Mara", "Tiago"], own="Mara", paused=frozen)

    # Back after the longest delay plus one tick at the latest: from then on at most
    # that much walking behind the newest position, never seconds behind.
    behind_at_most = 6 * (LONGEST_DELAY + TICK) / TICK
    caught_up = frames_between(frames, frozen[1] + LONGEST_DELAY + TICK)
    assert caught_up
    for frame in caught_up:
        newest = [places for t, places in messages if t <= frame["t"]][-1][1]
        assert newest["x"] - drawn(frame, TIAGO)["x"] <= behind_at_most + EXACT
    xs = [drawn(frame, TIAGO)["x"] for frame in frames]
    assert all(a <= b + EXACT for a, b in zip(xs, xs[1:]))  # never back
    assert all(math.dist(camera(frame), SPAWN) < EXACT for frame in frames)
    ended = frames_between(frames, messages[-1][0] + LONGEST_DELAY + TICK)
    assert ended and all(drawn(frame, TIAGO)["x"] == tiago[-1]["x"] for frame in ended)


@needs_node
def test_joining_again_while_walking_draws_the_own_player_at_once_where_the_server_puts_it():
    # Mara walks right and leaves while positions are still queued; she joins
    # again at once and the server puts her on the spawn, 30 units from where
    # she was drawn: closer than a jump, but a new start all the same.
    count = 20
    before = walk("Mara", count, (SPAWN[0] - 30 - FELIX_STEP * (count - 1), SPAWN[1]), (1, 0), FELIX_STEP)
    messages = felix([[place] for place in before])
    stop_at = messages[-1][0] + 1
    start_at = stop_at + 200
    back_at = start_at + 100
    after = walk("Mara", 15, SPAWN, (1, 0), 6)
    messages += [(back_at + k * TICK, [place]) for k, place in enumerate(after)]
    steps = [["stop", stop_at], ["start", start_at], ["players", start_at, lobby(["Mara"])]]
    frames = run_world(messages, until=messages[-1][0] + 600, players=["Mara"], own="Mara", steps=steps)

    back = frames_between(frames, back_at)
    assert back[0]["t"] - back_at < FRAME
    assert math.dist(camera(back[0]), SPAWN) < EXACT
    # Nothing of the walk before leaving is drawn after joining again.
    assert all(frame["camera"]["x"] >= SPAWN[0] - EXACT for frame in frames_between(frames, start_at))
    ended = frames_between(frames, messages[-1][0] + LONGEST_DELAY + TICK)
    assert ended and all(math.dist(camera(frame), (after[-1]["x"], after[-1]["y"])) < EXACT for frame in ended)
