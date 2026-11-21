"""To-do M2-1.16 "Bridge the gaps": the cases in which the bridge must not simply walk on.

- a wall ahead, a wall alongside and a doorway during a hold-up,
- a server that never walked the steps the browser made up,
- a player the server stopped itself (a task opened),
- the start of a round and a respawn while bridged steps are waiting,
- the station in range, which is still taken from the server's position,
- and what the bridge counts for the walking diagnostic.

Like test_bridge_gaps.py these tests run the page's own bridge.js, world.js
and diagnostic.js in Node (tests/world_bridge_in_node.js) against a server
played with the server's own rule (tests/bridge_helpers.py). Without Node
they are skipped; CI has Node.
"""

import math

import pytest

from bridge_helpers import (
    CAMPUS,
    EXACT,
    FELIX_DEBUG_RUN,
    KEY_AT,
    NODE,
    OPEN_LENGTH,
    OPEN_START,
    OWN,
    OWN_CHARACTER,
    SERVER_STEP,
    SERVER_TICK,
    SOLIDS,
    SPAWN,
    TICK,
    WAY_DOWN,
    WAY_UP,
    Scenario,
    between,
    distance_to_path,
    drawn,
    frozen,
    held,
    held_from,
    looped,
    on_time,
    overlapping,
    pairs,
    place,
    speeds,
    walk_right,
    wall_ahead,
    way_back,
)
from server.world import movement

pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

RIGHT = (1, 0)
BOTH_KEYS = [(KEY_AT, "down", "KeyD"), (KEY_AT, "down", "KeyS")]  # right and down: a diagonal


def own(frame):
    return drawn(frame, OWN_CHARACTER)


def moved(before, frame):
    return math.dist(place(before), place(frame)) >= 0.01


# ---- g. A wall ahead ---------------------------------------------------------------------

# From the spawn to the right there is a wall. The server reaches it about
# 1.9 s after the key. Each of these hold-ups of 600 ms covers that moment.
WALL = wall_ahead(SPAWN, 1, 0)
HOLD_UPS_AT_THE_WALL = [2400, 2500, 2600, 2700]


def into_the_wall(hold_up_from):
    return Scenario([(KEY_AT, "down", "KeyD")], held_from(hold_up_from, 600), until=5500, start=SPAWN)


def test_the_wall_scenario_meets_the_wall_during_the_hold_up():
    assert WALL[0] > SPAWN[0] + 100 and WALL[1] == SPAWN[1]
    for hold_up_from in HOLD_UPS_AT_THE_WALL:
        walk = into_the_wall(hold_up_from)
        reached_at = next(time for time, at, _ in walk.ticks if at == WALL)
        held_message = next(arrives for arrives, _, sent_at in walk.messages if sent_at >= hold_up_from)
        assert hold_up_from < reached_at < held_message - 100


@pytest.mark.parametrize("hold_up_from", HOLD_UPS_AT_THE_WALL)
def test_a_bridged_character_stops_touching_the_wall_and_is_never_drawn_inside_it(hold_up_from):
    walk = into_the_wall(hold_up_from)
    result = walk.run()
    frames = result["frames"]
    assert result["bridge"]["steps"] >= 3
    assert overlapping(frames) == []
    assert max(place(frame)[0] for frame in frames) <= WALL[0] + EXACT
    # It reached the wall by itself, before the held messages arrived ...
    held_message = next(arrives for arrives, _, sent_at in walk.messages if sent_at >= hold_up_from)
    assert place(between(frames, 0, held_message - 1)[-1]) == pytest.approx(WALL, abs=0.05)
    # ... never went back, and stands on the server's position.
    assert way_back(frames, RIGHT) == 0
    assert place(frames[-1]) == pytest.approx(walk.server_place(), abs=EXACT)
    assert walk.server_place() == WALL


@pytest.mark.parametrize("hold_up_from", HOLD_UPS_AT_THE_WALL)
def test_against_the_wall_the_feet_stop_and_nothing_more_is_bridged(hold_up_from):
    walk = into_the_wall(hold_up_from)
    walk.steps = [["numbers", 3600]]
    result = walk.run()
    # The key is held to the end, but the character stands: no steps of the
    # feet, like without the bridge.
    for frame in between(result["frames"], 3600):
        assert place(frame) == pytest.approx(WALL, abs=EXACT)
        assert own(frame)["stride"] == 0 and own(frame)["walkPhase"] is None
    assert result["bridge"]["steps"] == result["numbers"][0]["steps"]
    # Without the bridge the walk ends later (the held messages are played
    # back first), and the feet stand in the same way.
    without = walk.run(search="?bridge=off")["frames"]
    assert [own(frame)["stride"] for frame in between(without, 5000)] == [0] * len(between(without, 5000))


# ---- g. A diagonal along a wall -----------------------------------------------------------

# A little left of that wall, walking right and down: the player meets the
# wall at once and slides down along it for more than a second.
BESIDE_THE_WALL = (WALL[0] - 12, WALL[1] - 6)
HOLD_UPS_ALONG_THE_WALL = [1300, 1500, 1700]


def along_the_wall(hold_up_from):
    return Scenario(BOTH_KEYS, held_from(hold_up_from, 600), until=5000, start=BESIDE_THE_WALL)


def test_the_slide_scenario_slides_along_the_wall_during_the_hold_ups():
    assert not any(movement.overlaps(*BESIDE_THE_WALL, solid) for solid in SOLIDS)
    walk = along_the_wall(1300)
    sliding = [at for time, at, was_moved in walk.ticks if was_moved and at[0] == WALL[0]]
    assert len(sliding) > 18  # more than 1.2 s
    slid_until = max(time for time, at, was_moved in walk.ticks if was_moved)
    assert slid_until > max(HOLD_UPS_ALONG_THE_WALL) + 600 + 100


@pytest.mark.parametrize("hold_up_from", HOLD_UPS_ALONG_THE_WALL)
def test_a_bridged_diagonal_along_a_wall_slides_like_on_the_server(hold_up_from):
    walk = along_the_wall(hold_up_from)
    result = walk.run()
    frames = result["frames"]
    held_message = next(arrives for arrives, _, sent_at in walk.messages if sent_at >= hold_up_from)
    bridged = pairs(frames, held_message - 400, held_message - 1)
    assert len(bridged) > 20 and result["bridge"]["steps"] >= 8
    for before, frame in bridged:
        # Touching the wall, and moving down at the speed of a diagonal:
        # 90 units per second divided by the square root of 2.
        assert place(frame)[0] == pytest.approx(WALL[0], abs=EXACT)
        speed = (place(frame)[1] - place(before)[1]) / ((frame["t"] - before["t"]) / 1000)
        assert speed == pytest.approx(90 / math.sqrt(2), rel=0.02)
    assert overlapping(frames) == []
    for frame in frames:
        assert distance_to_path(place(frame), walk.server_path()) <= 0.1, frame["t"]
    assert place(frames[-1]) == pytest.approx(walk.server_place(), abs=EXACT)
    assert result["bridge"]["largeCorrections"] == 0


# ---- g. Through a doorway ------------------------------------------------------------------


def door_below_the_spawn():
    """The door a player reaches who walks right and down from the spawn."""
    return next(door for door in CAMPUS["doors"] if door["room"] == "pingo-doce")


def in_the_doorway(at, door):
    """Is a player at `at` between the two ends of the wall the door is in?"""
    half = movement.PLAYER_HALF_SIZE
    return door["y"] - half < at[1] < door["y"] + door["h"] + half


def through_the_door(delays):
    """Right and down from the spawn through the door; the keys are released a few steps behind it."""
    door = door_below_the_spawn()
    ticks = Scenario(BOTH_KEYS, on_time(), until=4000, start=SPAWN).ticks
    passing = [time for time, at, _ in ticks if in_the_doorway(at, door)]
    release_at = passing[-1] + 3 * SERVER_TICK - WAY_UP
    keys = BOTH_KEYS + [(release_at, "up", "KeyD"), (release_at, "up", "KeyS")]
    return Scenario(keys, delays, until=5000, start=SPAWN), passing


def test_the_door_scenario_walks_through_the_doorway_during_the_hold_up():
    door = door_below_the_spawn()
    walk, passing = through_the_door(on_time())
    assert len(passing) >= 3
    inside = [at for _, at, _ in walk.ticks if in_the_doorway(at, door)]
    assert all(door["x"] < at[0] < door["x"] + door["w"] for at in inside)
    # The way is drawn without touching anything when the messages are on time.
    assert overlapping(walk.run(search="?bridge=off")["frames"]) == []


@pytest.mark.parametrize("ticks_before_the_door", [2, 4, 6])
def test_a_bridged_walk_through_a_doorway_never_puts_a_frame_inside_a_wall(ticks_before_the_door):
    door = door_below_the_spawn()
    _, passing = through_the_door(on_time())
    hold_up_from = passing[0] - ticks_before_the_door * SERVER_TICK
    walk, _ = through_the_door(held_from(hold_up_from, 600))
    result = walk.run()
    frames = result["frames"]
    held_message = next(arrives for arrives, _, sent_at in walk.messages if sent_at >= hold_up_from)

    assert overlapping(frames) == []
    # The character went through the doorway by itself, before the server's
    # positions of that way had arrived.
    known = walk.known_place(held_message - 1)
    assert known[1] < door["y"] - movement.PLAYER_HALF_SIZE
    bridged_in_the_doorway = [frame for frame in between(frames, 0, held_message - 1) if in_the_doorway(place(frame), door)]
    assert len(bridged_in_the_doorway) >= 5
    assert place(frames[-1]) == pytest.approx(walk.server_place(), abs=EXACT)
    assert result["bridge"]["largeCorrections"] == 0


# ---- h. The server never walked --------------------------------------------------------------


def test_steps_the_server_never_walked_are_taken_back_after_a_second():
    # From 2.5 s on the server sends nothing more although the key is held.
    walk = walk_right(on_time(), until=6500, silent_from=2500)
    result = walk.run()
    frames = result["frames"]
    numbers = result["bridge"]
    assert numbers["steps"] == 10  # never more, however long the key is held
    assert numbers["replaced"] == 0
    assert numbers["takenBack"] == 1

    known = walk.known_place(6500)
    forward = [frame["t"] for before, frame in pairs(frames, walk.last_arrival()) if place(frame)[0] > place(before)[0] + EXACT]
    back = [frame["t"] for before, frame in pairs(frames, walk.last_arrival()) if place(frame)[0] < place(before)[0] - EXACT]
    # Ten steps beyond the newest position, then it stands ...
    assert max(place(frame)[0] for frame in frames) == pytest.approx(known[0] + 10 * SERVER_STEP)
    # ... and within 1.1 s after the last step it is on its way back ...
    assert 900 < back[0] - forward[-1] <= 1100
    # ... to stand exactly on the newest position of the server.
    assert back[-1] - back[0] <= TICK + 1000 / 60
    for frame in between(frames, back[-1]):
        assert place(frame) == pytest.approx(known, abs=EXACT)
    assert len(between(frames, back[-1])) > 60


def test_the_character_that_is_taken_back_does_not_bridge_again():
    walk = walk_right(on_time(), until=8000, silent_from=2500)
    result = walk.run()
    assert result["bridge"]["steps"] == 10
    assert place(result["frames"][-1]) == pytest.approx(walk.known_place(8000), abs=EXACT)


def test_with_somebody_else_walking_the_servers_standing_position_corrects_the_bridge_at_once():
    # The server stops the own player at 2.5 s (the key is still held) and
    # keeps sending, because another player walks. The first message after
    # the made-up step says where the own player really is.
    from bridge_helpers import circling
    walk = walk_right(on_time(), until=6000, stands_from=2500, other=circling((300, 300)))
    result = walk.run()
    frames = result["frames"]
    assert result["bridge"]["steps"] == 1
    assert result["bridge"]["largeCorrections"] == 1
    assert result["bridge"]["takenBack"] == 0
    assert way_back(frames, RIGHT) <= SERVER_STEP
    for frame in between(frames, 3000):
        assert place(frame) == pytest.approx(walk.server_place(), abs=EXACT)


# ---- i. The server stopped the player itself ---------------------------------------------------

STANDS_FROM = 3000  # the server keeps the player standing from here on (a task was opened)
PAUSED_AT = 3250  # the browser hears of it and pauses the keys


def stopped_by_the_server():
    steps = [["numbers", PAUSED_AT - 1], ["pause", PAUSED_AT, True]]
    return walk_right(on_time(), until=6000, stands_from=STANDS_FROM, steps=steps)


def test_when_the_input_is_paused_the_waiting_steps_are_forgotten_at_once():
    walk = stopped_by_the_server()
    result = walk.run()
    frames = result["frames"]
    before_the_pause = result["numbers"][0]
    # The positions stopped, the key was held: the bridge walked on.
    assert before_the_pause["steps"] >= 2
    # From the pause on no step is made up any more, and none is "taken
    # back" a second later: they were forgotten when the pause began.
    assert result["bridge"]["steps"] == before_the_pause["steps"]
    assert result["bridge"]["takenBack"] == 0
    # The glide under way ends, then the character goes back at once.
    back = [frame["t"] for before, frame in pairs(frames, PAUSED_AT) if place(frame)[0] < place(before)[0] - EXACT]
    assert PAUSED_AT < back[0] <= PAUSED_AT + TICK + 1000 / 60
    assert back[-1] <= PAUSED_AT + 2 * TICK + 1000 / 60


def test_after_the_pause_the_character_ends_on_the_servers_position():
    walk = stopped_by_the_server()
    frames = walk.run()["frames"]
    final = walk.server_place()
    assert final == walk.known_place(6000)
    settled = between(frames, PAUSED_AT + 2 * TICK + 1000 / 60)
    assert len(settled) > 100
    for frame in settled:
        assert place(frame) == pytest.approx(final, abs=EXACT)
        assert own(frame)["mirrored"] is False


def test_the_pause_tells_the_server_that_the_keys_are_released_as_before():
    walk = stopped_by_the_server()
    assert walk.run()["moves"] == [[KEY_AT, 1, 0], [PAUSED_AT, 0, 0]]


def test_while_the_input_is_paused_a_hold_up_is_not_bridged():
    # Paused while walking; the server walks on for a moment (its messages
    # are held up). Nothing is made up; the positions are drawn when they come.
    # (For the server of the test the key is released a moment later; the
    # world has released it already and ignores that.)
    steps = [["pause", 3100, True]]
    walk = walk_right(held_from(3073, 600), until=6000, release_at=3100.5, steps=steps)
    result = walk.run()
    assert result["bridge"]["steps"] == 0
    assert place(result["frames"][-1]) == pytest.approx(walk.server_place(), abs=EXACT)


# ---- j. The start of a round and a respawn while steps are waiting ------------------------------

HELD_FROM = 3073
ROUND_STARTS = 3400
PLACED_AT = 3700


def walking_left_into_a_hold_up(steps=()):
    """The player walks left; from HELD_FROM on nothing arrives any more. Bridged steps are waiting."""
    keys = [(KEY_AT, "down", "KeyA")]
    start = (OPEN_START[0] + OPEN_LENGTH, OPEN_START[1])
    return Scenario(keys, on_time(), until=6500, start=start, silent_from=HELD_FROM, steps=steps)


def put_on_the_spawn(walk, at):
    """The server puts the own player on the spawn: the message arrives at `at`."""
    walk.messages.append((at, [{"name": OWN, "x": SPAWN[0], "y": SPAWN[1]}], at - WAY_DOWN))


def test_the_start_of_a_round_forgets_the_waiting_steps_and_the_character_stands_facing_right():
    walk = walking_left_into_a_hold_up(steps=[["numbers", ROUND_STARTS - 1], ["start_of_round", ROUND_STARTS]])
    put_on_the_spawn(walk, PLACED_AT)
    result = walk.run()
    frames = result["frames"]
    before = result["numbers"][0]
    assert before["steps"] >= 3  # bridged steps were waiting
    assert all(own(frame)["mirrored"] is True for frame in between(frames, 2000, ROUND_STARTS - 1))

    # From the start of the round on: no step is made up, the character
    # faces right and its feet stand. As before this to-do, the glide under
    # way ends and the character waits where it is drawn for its placement.
    waiting = between(frames, ROUND_STARTS, PLACED_AT - 1)
    assert all(own(frame)["mirrored"] is False and own(frame)["stride"] == 0 for frame in waiting)
    assert frozen(frames, ROUND_STARTS + TICK + 1000 / 60, PLACED_AT - 1) == [frame["t"] for frame in between(
        frames, ROUND_STARTS + TICK + 1000 / 60, PLACED_AT - 1)]
    # The placement is shown at once, and nothing happens afterwards:
    # nothing was waiting, so nothing is taken back or returned to.
    placed = between(frames, PLACED_AT)
    assert len(placed) > 150
    for frame in placed:
        assert place(frame) == SPAWN
        assert own(frame)["mirrored"] is False and own(frame)["stride"] == 0
    assert result["bridge"]["steps"] == before["steps"]
    assert result["bridge"]["takenBack"] == 0
    assert result["bridge"]["replaced"] == 0


def test_a_respawn_while_steps_are_waiting_is_shown_at_once_as_before():
    walk = walking_left_into_a_hold_up(steps=[["numbers", ROUND_STARTS - 1]])
    put_on_the_spawn(walk, ROUND_STARTS)  # far away: a jump, without a word from the lobby page
    result = walk.run()
    frames = result["frames"]
    assert result["numbers"][0]["steps"] >= 3
    jumped = between(frames, ROUND_STARTS)
    assert len(jumped) > 150
    for frame in jumped:
        assert place(frame) == SPAWN
        assert own(frame)["mirrored"] is False and own(frame)["stride"] == 0
    # The jump did not count as the answer to a bridged step, and nothing is waiting.
    assert result["bridge"]["steps"] == result["numbers"][0]["steps"]
    assert result["bridge"]["replaced"] == 0
    assert result["bridge"]["takenBack"] == 0


def test_after_the_start_of_a_round_the_character_is_drawn_as_without_the_bridge():
    walk = walking_left_into_a_hold_up(steps=[["start_of_round", ROUND_STARTS]])
    put_on_the_spawn(walk, PLACED_AT)
    with_bridge = walk.run()["frames"]
    without = walk.run(search="?bridge=off")["frames"]
    assert [frame["characters"] for frame in between(with_bridge, PLACED_AT)] == [
        frame["characters"] for frame in between(without, PLACED_AT)]


def test_stopping_the_world_forgets_the_bridge_and_the_next_lobby_starts_afresh():
    steps = [["stop", 3300], ["start", 3400], ["numbers", 6000]]
    walk = walking_left_into_a_hold_up(steps=steps)
    put_on_the_spawn(walk, 3500)  # the first position in the next lobby
    result = walk.run()
    for frame in between(result["frames"], 3500):
        assert place(frame) == SPAWN
    # What was counted stays (the panel shows it until its Reset); nothing
    # is taken back in the next lobby for steps of the lobby before.
    assert result["bridge"]["steps"] >= 2
    assert result["bridge"]["takenBack"] == 0


# ---- k. The station in range ---------------------------------------------------------------------

USE_RANGE = CAMPUS["use_range"]


def station_with_a_free_way():
    """A station and a place 80 units left of it from which a player can walk right to it."""
    for station in CAMPUS["stations"]:
        start = (station["x"] - 80, station["y"])
        if any(movement.overlaps(*start, solid) for solid in SOLIDS):
            continue
        if wall_ahead(start, 1, 0)[0] >= station["x"] + 10:
            return station, start
    raise AssertionError("no station can be walked to in a straight line from the left")


def walk_to_the_station():
    station, start = station_with_a_free_way()
    # Message 8 is held: the newest position then is 9 steps from the start,
    # 80 - 55 = 25 and a bit away, which is out of range. The key is
    # released so that the server stops next to the station.
    ticks = Scenario([(KEY_AT, "down", "KeyD")], on_time(), until=4000, start=start).ticks
    stop_tick = next(time for time, at, _ in ticks if at[0] >= station["x"] - SERVER_STEP)
    keys = [(KEY_AT, "down", "KeyD"), (stop_tick - WAY_UP + 1, "up", "KeyD")]
    return station, Scenario(keys, held(m8=600), until=4500, start=start)


def distance_to(station, at):
    return math.dist(at, (station["x"], station["y"]))


def test_during_a_bridge_the_station_in_range_is_taken_from_the_servers_position():
    station, walk = walk_to_the_station()
    frames = walk.run()["frames"]
    arrives = walk.arrival(8)
    known = walk.known_place(arrives - 1)
    assert distance_to(station, known) > USE_RANGE + 3

    # The bridged character is drawn in range of the station, but the
    # newest position of the server is not: nothing glows, "E Use" stays off.
    drawn_in_range = [frame for frame in between(frames, 0, arrives - 1) if distance_to(station, place(frame)) < USE_RANGE - 1]
    assert len(drawn_in_range) >= 10
    assert all(frame["station"] is None for frame in drawn_in_range)
    # With the server's positions the station is in range.
    assert distance_to(station, walk.server_place()) < USE_RANGE - 3
    assert all(frame["station"] == station["id"] for frame in between(frames, arrives))


def test_the_station_in_range_is_the_same_in_every_frame_with_and_without_the_bridge():
    _, walk = walk_to_the_station()
    with_bridge = walk.run()
    without = walk.run(search="?bridge=off")
    assert with_bridge["bridge"]["steps"] >= 3
    assert [frame["station"] for frame in with_bridge["frames"]] == [frame["station"] for frame in without["frames"]]


# ---- What the bridge counts -------------------------------------------------------------------------

# As in test_bridge_gaps.py: message 25 is held 620 ms, the messages 83, 89,
# 95 and 101 are held 240 ms each.
HOLD_UPS = looped(FELIX_DEBUG_RUN, first=-5)
HELD_MESSAGES = {25: 620, 83: 240, 89: 240, 95: 240, 101: 240}


def counted_through_the_hold_ups():
    """The walk through the hold-ups, with the counts written down right before and after each held message arrives."""
    walk = walk_right(HOLD_UPS, until=KEY_AT + 9500, release_at=KEY_AT + 7100)
    for number in HELD_MESSAGES:
        walk.steps += [["numbers", walk.arrival(number) - 0.5], ["numbers", walk.arrival(number) + 0.5]]
    return walk, walk.run()


def test_the_bridge_counts_its_steps_and_the_positions_that_took_their_place():
    walk, result = counted_through_the_hold_ups()
    counts = result["numbers"]
    steps_so_far = 0
    for index, (number, held_ms) in enumerate(HELD_MESSAGES.items()):
        before, after = counts[2 * index], counts[2 * index + 1]
        # The queue runs dry about 100 ms after the last message, then one
        # step per tick is bridged until the held message arrives.
        gap = walk.arrival(number) - walk.arrival(number - 1)
        assert gap == pytest.approx(held_ms + SERVER_TICK)
        assert before["replaced"] == steps_so_far  # all earlier ones were answered, none of these yet
        # (A step that is due is made by the next frame or, at the latest,
        # when the next message arrives: so the steps are counted afterwards.)
        made = after["steps"] - steps_so_far
        assert (gap - 110) / TICK <= made <= (gap - 95) / TICK + 1
        # The messages that were held arrive together: each takes the place of one step.
        assert after["replaced"] == after["steps"]
        steps_so_far = after["steps"]
    assert counts[1]["steps"] == 9 and counts[1]["milliseconds"] == pytest.approx(9 * TICK)


def test_the_counts_at_the_end_of_the_walk_add_up():
    _, result = counted_through_the_hold_ups()
    numbers = result["bridge"]
    assert numbers["on"] is True and numbers["loaded"] is True
    assert 9 + 4 * 3 <= numbers["steps"] <= 9 + 4 * 4 + 1
    assert numbers["milliseconds"] == pytest.approx(numbers["steps"] * TICK)
    # Every step was answered by the server or taken back (at most the one
    # after the release).
    assert numbers["steps"] - numbers["replaced"] == numbers["takenBack"] <= 1
    # The bridge walks as far per step as the server: nothing to correct.
    assert numbers["corrections"] == 0
    assert numbers["largestCorrection"] == 0
    assert numbers["largeCorrections"] == 0
    assert numbers["serverStepMs"] == pytest.approx(SERVER_STEP / 90 * 1000)


def test_before_the_first_step_of_the_server_its_tick_counts_as_a_fifteenth_of_a_second():
    assert Scenario([], on_time(), until=500).run()["bridge"]["serverStepMs"] == pytest.approx(TICK)


def test_the_input_lag_is_measured_from_the_key_to_the_first_position_that_moved():
    walk = walk_right(on_time(), until=3000)
    # The key at 1000 reaches the server 20 ms later; its next tick sends
    # the first step, which arrives 25 ms after that.
    first_step_arrives = walk.arrival(0)
    assert 20 + 25 <= first_step_arrives - KEY_AT < 20 + 25 + SERVER_TICK
    lag = walk.run()["bridge"]["inputLagMs"]
    assert lag == pytest.approx(first_step_arrives - KEY_AT + 110 - TICK)


def test_before_the_first_walk_the_input_lag_is_the_one_assumed():
    walk = Scenario([], on_time(), until=500)
    assert walk.run()["bridge"]["inputLagMs"] == pytest.approx(100 + 110 - TICK)


def test_a_first_position_held_up_is_clamped_and_later_walks_bring_the_lag_back():
    # Three walks. The first position of the first walk is held 900 ms: its
    # sample is clamped to 400 ms. The median of three samples forgets it.
    keys = [(1000, "down", "KeyD"), (2500, "up", "KeyD"), (4000, "down", "KeyD"), (4500, "up", "KeyD"),
            (6000, "down", "KeyD"), (6500, "up", "KeyD")]
    steps = [["numbers", 3500], ["numbers", 5500]]
    result = Scenario(keys, held(m0=900), until=7500, start=OPEN_START, steps=steps).run()
    after_one, after_two = result["numbers"]
    assert after_one["inputLagMs"] == pytest.approx(400 + 110 - TICK)
    good = result["bridge"]["inputLagMs"] - (110 - TICK)
    assert 45 <= good < 45 + SERVER_TICK
    assert after_two["inputLagMs"] == pytest.approx((400 + good) / 2 + 110 - TICK, abs=SERVER_TICK / 2)
