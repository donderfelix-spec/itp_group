"""Rule 1 in Classic: every browser receives only what its player may know (M3-2.1).

Two scripted Classic rounds are played over the real WebSocket endpoint:
5 players with 1 Free Rider and 6 players with 2, with fixed roles and the
server's clock in the test's hand. Every message each connection receives
is recorded with the step it arrived in and the viewer's state at that
step: "HP" or "FR" for a living player, "ghost", or "left" for a player
who left the round. Then every record is checked against
KNOWN_CLASSIC_TYPES, which says for each message type who may receive it
and what it may contain. A type that is not in the table fails the test.

All waits are bounded: a step waits up to WAIT_SECONDS for the messages
it expects, then for the server's background sends, then a short quiet
moment, and takes whatever else has arrived by then. Nothing here waits
for a `welcome` as a sign that everything has arrived.
"""

import json
import re
import time
from collections import Counter
from dataclasses import dataclass

import anyio
import pytest

from rules import FAIL_COOLDOWN_SECONDS
from server import protocol
from server.classic import round as classic_round_module
from server.classic.meeting import DISCUSSION_SECONDS, VOTING_SECONDS
from server.main import app
from task_helpers import PASSWORD, client, clock, connect, placeholder_at_every_station, put, put_at_station  # noqa: F401
from test_classic_leaving import wait_for_background_sends
from test_classic_server_features import classic_for
from test_server_duel import REAL_TICK

FIVE = ("Mara", "Tiago", "Ines", "Rui", "Luca")
SIX = FIVE + ("Sofia",)
# Far from every hiding spot and more than the fail range from each other.
FAR_PLACES = [(100.0, 330.0), (300.0, 330.0), (300.0, 400.0), (200.0, 300.0), (400.0, 300.0), (150.0, 420.0)]
FAIL_PLACE = (500.0, 450.0)
SHEET_PLACE = (FAIL_PLACE[0] + 1, FAIL_PLACE[1])  # where the victim stands
HEDGE = (float(app.state.campus["hiding_spots"][0]["x"]), float(app.state.campus["hiding_spots"][0]["y"]))
# 45 units right of the hedge, in clear sight of it (S-185) but beyond the
# reveal range of 35: who stands here sees the hider only by rule, never by
# being close.
HEDGE_WATCHER = (HEDGE[0] + 45.0, HEDGE[1])

WAIT_SECONDS = 10.0  # the longest a step waits for the messages it expects
SIGN_UP_SECONDS = 30.0  # hashing a password takes a while, more so with several test runs at once
QUIET_SECONDS = 0.2  # after the expected messages, late ones still get this long
MOST_MESSAGES_AT_ONCE = 1000  # a limit for emptying a queue, so that it can never loop forever

ROLE_KEYS = {"role", "roles", "revealed_role", "other_free_riders"}
NOTICE_TEXTS = [r"The host left\. \w+ is the new host\.", re.escape("Too many players left. The round was stopped.")]
DYNAMIC_REJECTIONS = [r"You can fail again in \d+ seconds?\.", r"The emergency button unlocks in \d+ seconds?\."]


# Reading from a connection, always with a limit
#
# Starlette's test connection has no receive with a time limit, so these
# read its queue (`_send_rx`, an anyio memory stream) on the server's own
# event loop, through the connection's portal.


def decoded(raw: dict) -> dict:
    assert raw["type"] == "websocket.send", f"the server closed a connection: {raw}"
    return json.loads(raw["text"])


def receive_within(connection, seconds: float):
    """The next message on this connection, or None if none arrives within `seconds`."""
    async def receive():
        with anyio.move_on_after(seconds):
            return await connection._send_rx.receive()
        return None

    raw = connection.portal.call(receive)
    return None if raw is None else decoded(raw)


def waiting_messages(connection) -> list:
    """Every message already waiting on this connection, without waiting for more."""
    messages = []
    while len(messages) < MOST_MESSAGES_AT_ONCE:
        try:
            raw = connection.portal.call(connection._send_rx.receive_nowait)
        except anyio.WouldBlock:
            return messages
        messages.append(decoded(raw))
    raise AssertionError(f"more than {MOST_MESSAGES_AT_ONCE} messages were waiting")


def read_until_type(connection, wanted: str, seconds: float = WAIT_SECONDS) -> list:
    """The messages up to and including the next one of type `wanted`. Fails after `seconds`."""
    deadline = time.monotonic() + seconds
    messages = []
    while not messages or messages[-1]["type"] != wanted:
        remaining = deadline - time.monotonic()
        assert remaining > 0, f"no {wanted} within {seconds} s, only {types_of(messages)}"
        message = receive_within(connection, remaining)
        if message is not None:
            messages.append(message)
    return messages


def request(connection, message: dict, wanted: str, seconds: float = WAIT_SECONDS) -> list:
    connection.send_json(message)
    return read_until_type(connection, wanted, seconds)


def settle(connections):
    """Throw away everything sent so far, once the server is done sending it."""
    wait_for_background_sends()
    time.sleep(QUIET_SECONDS)
    for connection in connections:
        waiting_messages(connection)


def types_of(messages) -> list:
    return [message["type"] for message in messages]


# What the recording holds


@dataclass(frozen=True)
class Step:
    """One step of a scripted round, as the test knows it at the end of the step."""
    name: str
    actor: str | None  # who acted in this step, if anybody
    members: frozenset  # who is in the lobby
    ghosts: frozenset  # who has failed, was voted out or left
    ejected: tuple  # (name, role) of everybody voted out so far
    hidden: str | None  # a Free Rider who pressed E in the hedge and hides (S-191, S-192)
    victim: str | None  # who was failed in this step
    final: bool  # the round ends in this step
    roles: tuple  # (name, role) of everybody, fixed by the test
    tasks: tuple  # (name, stations) of everybody's task list at the start

    def role_of(self, name):
        return dict(self.roles)[name]

    def own_tasks(self, name):
        return {int(station) for station in dict(self.tasks)[name]}

    def free_riders(self):
        return {name for name, role in self.roles if role == "FR"}


@dataclass(frozen=True)
class Record:
    step: Step
    viewer: str
    state: str  # "HP", "FR", "ghost" or "left"
    message: dict


class Recorder:
    """Plays the steps of one round and records every message every connection receives."""

    def __init__(self, connections: dict, roles: dict):
        self.connections = dict(connections)  # the members of the lobby
        self.left = {}  # connections of players who left; they must hear nothing more
        self.roles = dict(roles)
        self.tasks = {}
        self.ghosts = set()
        self.ejected = {}
        self.hidden = None
        self.records = []
        self.steps = []

    def listeners(self) -> dict:
        return {**self.connections, **self.left}

    def state_of(self, name: str) -> str:
        if name in self.left:
            return "left"
        if name in self.ghosts:
            return "ghost"
        return self.roles[name]

    def tick(self):
        """Run the server's real tick once. Its own loop is switched off in the tests (conftest.py)."""
        next(iter(self.connections.values())).portal.call(REAL_TICK, 0.0)

    def place(self, special=None):
        """Put every member far from everybody else, except the players in `special`.

        A Free Rider placed in the hedge counts as hidden for the checks; he
        hides by pressing E (see `walk`). One who hid and is placed elsewhere
        first steps out with E again (`leave_hiding`, S-191).
        """
        special = special or {}
        was_hidden = self.hidden
        for name, place in zip(self.connections, FAR_PLACES):
            put(name, special.get(name, place))
        self.hidden = next((name for name, place in special.items() if place == HEDGE), None)
        classic = classic_for(next(iter(self.connections)))
        if was_hidden and was_hidden != self.hidden and classic is not None and classic.is_hidden(was_hidden):
            self.connections[was_hidden].send_json({"type": "leave_hiding"})
            self.step(f"{was_hidden} steps out of hiding", {was_hidden: ["classic_hiding"]}, actor=was_hidden)

    def everybody_needs_positions(self):
        app.state.lobbies.lobby_of(next(iter(self.connections))).walkers._everybody_needs_news()

    def step(self, name, expected, actor=None, victim=None, final=False, quiet_for_others=False) -> dict:
        """Collect what arrived for this step and record it. Returns `{viewer: [messages]}`.

        `expected` is `{viewer: [types]}`: the messages that must arrive
        (others may come too). With `quiet_for_others`, nobody but the
        actor may receive anything in this step.
        """
        arrived = collect(self.listeners(), expected, name)
        if not self.tasks:
            # The task lists are drawn at random when the round starts.
            classic = classic_for(next(iter(self.connections)))
            self.tasks = {player: tuple(stations) for player, stations in classic.tasks.items()}

        step = Step(
            name=name, actor=actor, members=frozenset(self.connections), ghosts=frozenset(self.ghosts),
            ejected=tuple(sorted(self.ejected.items())), hidden=self.hidden, victim=victim, final=final,
            roles=tuple(sorted(self.roles.items())), tasks=tuple(sorted(self.tasks.items())),
        )
        self.steps.append(step)
        for viewer, messages in arrived.items():
            self.records += [Record(step, viewer, self.state_of(viewer), message) for message in messages]
        self.agrees_with_the_server(final)
        if quiet_for_others:
            heard = {viewer: types_of(messages) for viewer, messages in arrived.items() if viewer != actor and messages}
            assert heard == {}, f"step {name}: only {actor} may hear about it, but {heard}"
        return arrived

    def agrees_with_the_server(self, final):
        """The test's own list of ghosts is the server's, while the round runs."""
        classic = classic_for(next(iter(self.connections)))
        if final:
            assert classic is None, "the round should have ended"
            return
        assert classic is not None, "the round ended too early"
        assert classic.eliminated == self.ghosts


def collect(listeners: dict, expected: dict, step_name: str) -> dict:
    """Wait (with a limit) until every expected message has arrived, then take the rest too."""
    arrived = {viewer: [] for viewer in listeners}
    deadline = time.monotonic() + WAIT_SECONDS
    for viewer, wanted in expected.items():
        while not wanted_all(arrived[viewer], wanted):
            remaining = deadline - time.monotonic()
            assert remaining > 0, (
                f"step {step_name}: {viewer} expected {wanted} but got only {types_of(arrived[viewer])}"
            )
            message = receive_within(listeners[viewer], remaining)
            if message is not None:
                arrived[viewer].append(message)
    # What the server sends in tasks of its own, and anything a little late.
    wait_for_background_sends()
    time.sleep(QUIET_SECONDS)
    for viewer, connection in listeners.items():
        arrived[viewer] += waiting_messages(connection)
    return arrived


def wanted_all(messages, wanted) -> bool:
    return not (Counter(wanted) - Counter(types_of(messages)))


def everybody(rec, *types) -> dict:
    return {name: list(types) for name in rec.connections}


def with_extra(expected: dict, names, *types) -> dict:
    """`expected` with `types` added for each of `names`."""
    result = {name: list(wanted) for name, wanted in expected.items()}
    for name in names:
        result.setdefault(name, [])
        result[name] += list(types)
    return result


def free_rider_members(rec) -> list:
    """The Free Riders still in the lobby: they get `classic_fail_status`, also as a ghost (finding 5)."""
    return [name for name in rec.connections if rec.roles[name] == "FR"]


def living_free_riders(rec) -> list:
    return [name for name in free_rider_members(rec) if name not in rec.ghosts]


# Checks: one per message type


def check_lobby_state(record):
    message, step = record.message, record.step
    names = {entry["name"] for entry in message["players"]}
    assert all(set(entry) == {"name", "character"} for entry in message["players"])
    if message["phase"] == "lobby":
        assert step.final, "the lobby opened again before the round ended"
        assert names == step.members
    elif record.state == "ghost":
        assert names == step.members
    else:
        assert names == step.members - step.ghosts, "a living player was sent a ghost in lobby_state (S-155)"


def check_classic_role(record):
    message, step, viewer = record.message, record.step, record.viewer
    assert step.name == "start" and record.state in ("HP", "FR")
    keys = {"type", "role", "task_stations"} | ({"other_free_riders"} if message["role"] == "FR" else set())
    assert set(message) == keys
    assert message["role"] == step.role_of(viewer), "classic_role names somebody else's role"
    if message["role"] == "FR":
        assert sorted(message["other_free_riders"]) == sorted(step.free_riders() - {viewer})
        assert message["task_stations"] == []
    else:
        assert "other_free_riders" not in message
        assert set(message["task_stations"]) == step.own_tasks(viewer), "a task list went to somebody else (S-154)"


def check_you_are_fr(record):
    assert record.step.name == "start" and record.state == "FR"


def check_classic_fail_status(record):
    # Also a Free Rider who was voted out gets it, only he (finding 5, left as it is).
    assert record.step.role_of(record.viewer) == "FR", "classic_fail_status went to a High Performer"
    assert set(record.message) == {"type", "available", "in_range", "cooldown_until", "server_time"}


def check_classic_progress(record):
    assert set(record.message) == {"type", "progress", "server_time", "emergency_ready_at"}


def check_positions(record):
    step = record.step
    for entry in record.message["players"]:
        assert set(entry) in ({"name", "x", "y"}, {"name", "x", "y", "hidden"}), entry
        assert entry.get("hidden", True) is True, entry
    names = {entry["name"] for entry in record.message["players"]}
    flagged = {entry["name"] for entry in record.message["players"] if entry.get("hidden")}
    assert names <= step.members
    if record.state != "ghost":
        assert not names & step.ghosts, f"a living player was sent ghost positions {names & step.ghosts} (S-155)"
    if record.state == "HP":
        assert not flagged, f"a living High Performer was told that {sorted(flagged)} hides (S-192)"
    else:
        assert flagged <= {step.hidden}, f"{sorted(flagged)} flagged as hidden, but only {step.hidden} hides"
    if step.hidden is not None and step.hidden not in step.ghosts:
        if record.state == "HP":
            assert step.hidden not in names, "a High Performer was sent the hidden Free Rider (S-192)"
        else:
            # The hider himself, the other Free Rider (S-137) and the ghosts
            # (S-136) see him, and are told that he hides (S-192).
            assert step.hidden in names
            assert step.hidden in flagged, f"{record.viewer} was not told that {step.hidden} hides (S-192)"


def check_classic_hiding(record):
    """Only a living Free Rider is told whether he himself hides (S-191)."""
    assert record.state == "FR", "somebody who is no living Free Rider was told about hiding"
    assert set(record.message) == {"type", "hidden"}
    assert record.message["hidden"] is (record.viewer == record.step.hidden)


def check_classic_roster(record):
    step = record.step
    players = record.message["players"]
    assert all(set(entry) == {"name", "character", "ghost"} for entry in players)
    assert all(entry["ghost"] == (entry["name"] in step.ghosts) for entry in players)
    names = {entry["name"] for entry in players}
    if record.state == "ghost":
        assert names == step.members
    else:
        assert names == step.members - step.ghosts, "a living player was sent a ghost in classic_roster (S-164)"


def check_classic_fail(record):
    # Public by decision (S-159, S-163): the victim and their character, never who failed them.
    assert set(record.message) == {"type", "target_id", "character", "sheet_id", "position"}
    assert record.message["target_id"] == record.step.victim


MEETING_STATE_KEYS = {
    "type", "phase", "seconds_left", "living", "ghosts", "reason", "trigger_player_id", "reported_sheet_id",
    "messages", "voted", "vote_targets", "skip_voted", "ejected_id", "revealed_role", "tie", "winner",
    "characters",
}


def check_meeting_state(record):
    # Public by decision: votes and Skips (S-160, S-162), the result and the
    # role of the player voted out (DESIGN 5.7). Who is living and who is a
    # ghost is public since the victim is (S-159).
    message, step = record.message, record.step
    assert set(message) == MEETING_STATE_KEYS
    assert all(set(item) == {"player_id", "text"} for item in message["messages"])
    living = set(message["living"])
    assert living == step.members - step.ghosts
    assert set(message["ghosts"]) == step.ghosts & step.members
    # The result still shows the votes that ejected a player.
    voters = living | {message["ejected_id"]} - {None}
    assert set(message["vote_targets"]) <= voters and set(message["vote_targets"].values()) <= voters
    assert set(message["skip_voted"]) <= voters
    assert all(item["player_id"] in living for item in message["messages"])
    if message["ejected_id"] is None:
        assert message["revealed_role"] is None
    else:
        assert message["ejected_id"] in dict(step.ejected)
        assert message["revealed_role"] == step.role_of(message["ejected_id"])


def check_classic_result(record):
    # Public by decision: the end screen shows everybody's role.
    assert record.step.final
    assert record.message["roles"] == dict(record.step.roles)


def check_error(record):
    message, step, viewer = record.message, record.step, record.viewer
    assert viewer == step.actor, f"a rejection went to {viewer}, who did not act"
    text = message["message"]
    assert text in protocol.REJECTIONS.values() or any(re.fullmatch(p, text) for p in DYNAMIC_REJECTIONS)
    assert not [name for name in dict(step.roles) if name in text], "a rejection names a player"


def check_left_lobby(record):
    assert record.viewer == record.step.actor


def check_notice(record):
    assert any(re.fullmatch(pattern, record.message["message"]) for pattern in NOTICE_TEXTS)


def check_own_station(record):
    message, viewer = record.message, record.viewer
    assert viewer == record.step.actor or (record.step.final and message["type"] == "station_closed")
    assert message["station"] in record.step.own_tasks(viewer), "a station message went to somebody else (S-154)"
    if "task_stations" in message:
        assert set(message["task_stations"]) <= record.step.own_tasks(viewer)


KNOWN_CLASSIC_TYPES = {
    "lobby_state": ("everybody; the living without the ghosts (S-155)", check_lobby_state),
    "classic_role": ("each player once, with only the own role; a Free Rider also the other Free Riders", check_classic_role),
    "you_are_fr": ("only a Free Rider, at the start", check_you_are_fr),
    "classic_fail_status": ("only Free Riders (also one voted out, finding 5)", check_classic_fail_status),
    "classic_progress": ("everybody, public: only the bar and the clocks", check_classic_progress),
    "positions": ("everybody; ghosts only to ghosts (S-155); a hidden Free Rider never to a living High Performer, flagged for the others (S-136, S-137, S-192)", check_positions),
    "classic_hiding": ("only the living Free Rider about himself (S-191)", check_classic_hiding),
    "classic_roster": ("everybody; the living without the ghosts (S-155, S-164)", check_classic_roster),
    "classic_fail": ("everybody, public by decision S-159 and S-163: the victim with character", check_classic_fail),
    "meeting_state": ("everybody, identical; votes and Skips public by decision S-160 and S-162", check_meeting_state),
    "classic_result": ("everybody, public by decision: all roles at the end", check_classic_result),
    "error": ("only the acting player, with a text that names nobody and no role", check_error),
    "left_lobby": ("only the player who left", check_left_lobby),
    "notice": ("everybody, public: host left or round stopped", check_notice),
    "station_opened": ("only the owner of the task (S-154)", check_own_station),
    "station_done": ("only the owner of the task, with the own list (S-154)", check_own_station),
    "station_closed": ("only the owner of the task (S-154)", check_own_station),
}


def role_keys_in(value) -> set:
    """Every key anywhere in a message that names a role."""
    if isinstance(value, dict):
        found = {key for key in value if key in ROLE_KEYS}
        for item in value.values():
            found |= role_keys_in(item)
        return found
    if isinstance(value, list):
        return set().union(*(role_keys_in(item) for item in value)) if value else set()
    return set()


# Where a role may be named at all (the checks above say whose).
ROLES_ALLOWED_IN = {
    "classic_role": {"role", "other_free_riders"},
    "meeting_state": {"revealed_role"},
    "classic_result": {"roles"},
}


def check_record(record):
    message_type = record.message.get("type")
    if message_type not in KNOWN_CLASSIC_TYPES:
        raise AssertionError(
            f"unclassified Classic message type {message_type} received by {record.viewer} at step {record.step.name}"
        )
    its_own_leave = message_type == "left_lobby" and record.viewer == record.step.actor
    assert record.state != "left" or its_own_leave, f"{record.viewer} left the round but was sent {message_type}"
    unexpected = role_keys_in(record.message) - ROLES_ALLOWED_IN.get(message_type, set())
    assert not unexpected, f"{message_type} names a role ({unexpected})"
    _receivers, check = KNOWN_CLASSIC_TYPES[message_type]
    try:
        check(record)
    except AssertionError as problem:
        raise AssertionError(
            f"{message_type} to {record.viewer} ({record.state}) at step {record.step.name}: {problem}"
        ) from problem


def check_meeting_states_are_identical(records):
    """In one step every member gets the very same meeting snapshots."""
    by_step = {}
    for record in records:
        if record.message["type"] == "meeting_state" and record.viewer in record.step.members:
            by_step.setdefault(record.step, {}).setdefault(record.viewer, []).append(record.message)
    for step, by_viewer in by_step.items():
        missing = step.members - set(by_viewer)
        assert not missing, f"step {step.name}: {sorted(missing)} got no meeting_state"
        first = next(iter(by_viewer.values()))
        assert all(snapshots == first for snapshots in by_viewer.values()), (
            f"step {step.name}: the viewers got different meeting_state messages"
        )


def check_all(rec):
    for record in rec.records:
        check_record(record)
    check_meeting_states_are_identical(rec.records)


# Setting up a round


def fixed_roles(monkeypatch, free_riders):
    def assign(player_ids, rng):
        return {name: "FR" if name in free_riders else "HP" for name in player_ids}

    monkeypatch.setattr(classic_round_module, "assign_roles", assign)


def round_with_fixed_roles(connect, monkeypatch, names, free_riders) -> Recorder:
    """A lobby in Classic mode, started by its host. Recording begins with the start."""
    fixed_roles(monkeypatch, free_riders)
    connections = {}
    for name in names:
        connection = connect()
        request(connection, {"type": "sign_up", "name": name, "password": PASSWORD}, "signed_in", SIGN_UP_SECONDS)
        connections[name] = connection
    host = connections[names[0]]
    code = request(host, {"type": "create_lobby"}, "lobby_state")[-1]["code"]
    for name in names[1:]:
        request(connections[name], {"type": "join_lobby", "code": code}, "lobby_state")
    request(host, {"type": "choose_mode", "mode": "classic"}, "lobby_state")
    settle(connections.values())

    rec = Recorder(connections, {name: "FR" if name in free_riders else "HP" for name in names})
    host.send_json({"type": "start_game"})
    rec.step(
        "start",
        with_extra(everybody(rec, "lobby_state", "classic_role", "classic_progress"),
                   free_riders, "you_are_fr", "classic_fail_status"),
        actor=names[0],
    )
    return rec


# The steps both rounds share


def do_a_task(rec, clock, worker):
    station = int(rec.tasks[worker][0])
    put_at_station(worker, station)
    rec.connections[worker].send_json({"type": "open_station", "station": station})
    rec.step("task opened", {worker: ["station_opened"]}, actor=worker, quiet_for_others=True)
    clock.wait(2)  # the placeholder minigame takes at least a second
    rec.connections[worker].send_json({"type": "finish_station"})
    rec.step("task finished", with_extra(everybody(rec, "classic_progress"), [worker], "station_done"), actor=worker)


def free_rider_tries_a_task(rec, free_rider):
    put_at_station(free_rider, 1)
    rec.connections[free_rider].send_json({"type": "open_station", "station": 1})
    rec.step("Free Rider opens a station", {free_rider: ["error"]}, actor=free_rider, quiet_for_others=True)


def walk(rec, name, hidden_free_rider=None):
    """The tick sends everybody the positions; `hidden_free_rider` stands in the hedge and hides with E.

    Since S-185 a living player only gets the positions in his sight. So the
    other living Free Riders and one living High Performer watch the hedge
    from HEDGE_WATCHER: the checks of S-133 and S-137 then depend on the
    hiding rules alone, not on walls or distance. Since S-192 the High
    Performer must not get him even there.
    """
    special = {}
    if hidden_free_rider:
        special[hidden_free_rider] = HEDGE
        living = [name for name in rec.connections if name != hidden_free_rider and name not in rec.ghosts]
        watchers = [name for name in living if rec.roles[name] == "FR"]
        watchers += [name for name in living if rec.roles[name] == "HP"][:1]
        special.update({name: HEDGE_WATCHER for name in watchers})
    rec.place(special)
    if hidden_free_rider and not classic_for(hidden_free_rider).is_hidden(hidden_free_rider):
        rec.connections[hidden_free_rider].send_json({"type": "hide"})
        rec.step(f"{hidden_free_rider} presses E in the hedge", {hidden_free_rider: ["classic_hiding"]}, actor=hidden_free_rider)
    rec.everybody_needs_positions()
    rec.tick()
    rec.step(name, with_extra(everybody(rec, "positions"), living_free_riders(rec), "classic_fail_status"))


def refused_fail(rec, actor, beside):
    """`actor` presses Q with only `beside` in range (a Free Rider or nobody he may fail)."""
    rec.place({actor: FAIL_PLACE, beside: SHEET_PLACE})
    rec.connections[actor].send_json({"type": "fail"})
    rec.step(f"{actor} cannot fail {beside}", {actor: ["error"]}, actor=actor, quiet_for_others=True)


def fail(rec, clock, free_rider, victim, final=False):
    clock.wait(FAIL_COOLDOWN_SECONDS + 1)
    rec.place({free_rider: FAIL_PLACE, victim: SHEET_PLACE})
    rec.connections[free_rider].send_json({"type": "fail"})
    rec.ghosts.add(victim)
    expected = with_extra(
        everybody(rec, "classic_fail", "classic_progress", "classic_roster", "positions"),
        free_rider_members(rec), "classic_fail_status",
    )
    if final:
        expected = with_extra(expected, rec.connections, "classic_result", "lobby_state")
    told = rec.step(f"{free_rider} fails {victim}", expected, actor=free_rider, victim=victim, final=final)
    return next(m for m in told[free_rider] if m["type"] == "classic_fail")["sheet_id"]


def report(rec, reporter, sheet_id):
    put(reporter, SHEET_PLACE)
    rec.connections[reporter].send_json(
        {"type": "report", "sheet_id": sheet_id, "position": {"x": SHEET_PLACE[0], "y": SHEET_PLACE[1]}}
    )
    # The meeting ends hiding (S-191): the one who hid is told.
    expected = everybody(rec, "meeting_state")
    if rec.hidden is not None:
        expected = with_extra(expected, [rec.hidden], "classic_hiding")
        rec.hidden = None
    rec.step(f"{reporter} reports", expected, actor=reporter)


def meeting_action(rec, actor, message, name):
    """An accepted chat, vote or Skip: everybody gets the new snapshot."""
    rec.connections[actor].send_json(message)
    rec.step(name, everybody(rec, "meeting_state"), actor=actor)


def refused_meeting_action(rec, actor, message, name, quiet_for_others=True):
    """A refused chat, vote or Skip: only the actor hears about it (findings 1 and 2)."""
    rec.connections[actor].send_json(message)
    rec.step(name, {actor: ["error"]}, actor=actor, quiet_for_others=quiet_for_others)


def chat(text):
    return {"type": "chat", "text": text}


def vote(target):
    return {"type": "vote", "target_id": target}


SKIP = {"type": "skip_discussion"}


def ghost_tries_everything(rec, ghost, target):
    refused_meeting_action(rec, ghost, chat("I saw it!"), "ghost chats")
    refused_meeting_action(rec, ghost, vote(target), "ghost votes")
    refused_meeting_action(rec, ghost, SKIP, "ghost skips")


def meeting_result(rec, ejected=None, final=False):
    """Records the step in which a meeting's result arrives."""
    if ejected is not None:
        rec.ghosts.add(ejected)
        rec.ejected[ejected] = rec.roles[ejected]
    expected = everybody(rec, "meeting_state", "classic_roster", "positions")
    if final:
        expected = with_extra(expected, rec.connections, "classic_result", "lobby_state")
    rec.step("meeting result", expected, final=final)


def leave(rec, leaver, expected_for_others):
    connection = rec.connections.pop(leaver)
    rec.left[leaver] = connection
    rec.ghosts.add(leaver)  # a leaver counts as failed (S-158)
    connection.send_json({"type": "leave_lobby"})
    expected = {name: list(expected_for_others) for name in rec.connections}
    expected[leaver] = ["left_lobby"]
    rec.step(f"{leaver} leaves", expected, actor=leaver)


# The two rounds


def play_five(connect, clock, monkeypatch) -> Recorder:
    """5 players, Mara is the Free Rider. Ends with Mara voted out."""
    rec = round_with_fixed_roles(connect, monkeypatch, FIVE, {"Mara"})
    do_a_task(rec, clock, "Tiago")
    free_rider_tries_a_task(rec, "Mara")
    walk(rec, "walking")
    walk(rec, "walking, Mara hidden", hidden_free_rider="Mara")
    refused_fail(rec, "Rui", "Ines")  # a High Performer presses Q
    sheet = fail(rec, clock, "Mara", "Tiago")
    walk(rec, "ticks, Mara hidden", hidden_free_rider="Mara")
    clock.wait(1)
    rec.tick()
    rec.step("a tick with nothing new", {})

    report(rec, "Ines", sheet)
    meeting_action(rec, "Ines", chat("Who was near the sheet?"), "chat")
    refused_meeting_action(rec, "Ines", chat("Anyone?"), "chat during the cooldown")
    ghost_tries_everything(rec, "Tiago", "Mara")
    refused_meeting_action(rec, "Rui", vote("Tiago"), "vote for a ghost")
    meeting_action(rec, "Ines", vote("Mara"), "Ines votes Mara")
    meeting_action(rec, "Luca", SKIP, "Luca skips")
    meeting_action(rec, "Luca", vote("Mara"), "Luca votes Mara instead")
    meeting_action(rec, "Rui", vote("Mara"), "Rui votes Mara")
    meeting_action(rec, "Mara", vote("Ines"), "Mara votes Ines")
    # A living High Performer leaves: his vote is gone, Mara still has the most.
    leave(rec, "Luca", ["lobby_state", "meeting_state", "classic_roster", "classic_progress"])

    clock.wait(DISCUSSION_SECONDS + VOTING_SECONDS)
    rec.tick()
    meeting_result(rec, ejected="Mara", final=True)
    return rec


def play_six(connect, clock, monkeypatch) -> Recorder:
    """6 players, Mara and Tiago are the Free Riders. Ends with Mara failing the second last High Performer."""
    rec = round_with_fixed_roles(connect, monkeypatch, SIX, {"Mara", "Tiago"})
    do_a_task(rec, clock, "Ines")
    free_rider_tries_a_task(rec, "Tiago")
    walk(rec, "walking")
    walk(rec, "walking, Mara hidden", hidden_free_rider="Mara")
    refused_fail(rec, "Mara", "Tiago")  # a Free Rider cannot fail the other one
    sheet = fail(rec, clock, "Mara", "Ines")
    walk(rec, "ticks, Mara hidden", hidden_free_rider="Mara")

    # A report meeting that votes Tiago out.
    report(rec, "Rui", sheet)
    meeting_action(rec, "Rui", chat("Ines is gone."), "chat")
    refused_meeting_action(rec, "Rui", chat("Anyone?"), "chat during the cooldown")
    ghost_tries_everything(rec, "Ines", "Tiago")
    meeting_action(rec, "Luca", vote("Tiago"), "Luca votes Tiago")
    meeting_action(rec, "Sofia", vote("Tiago"), "Sofia votes Tiago")
    meeting_action(rec, "Rui", vote("Tiago"), "Rui votes Tiago")
    meeting_action(rec, "Tiago", vote("Rui"), "Tiago votes Rui")
    meeting_action(rec, "Mara", SKIP, "Mara skips")
    meeting_action(rec, "Mara", SKIP, "Mara takes her Skip back")
    rec.hidden = None  # Mara walks out of the hedge during the meeting
    rec.place({})
    clock.wait(DISCUSSION_SECONDS + VOTING_SECONDS)
    rec.tick()
    meeting_result(rec, ejected="Tiago")

    # The meeting is over: chat, vote and Skip are refused (finding 3).
    refused_meeting_action(rec, "Rui", chat("Too late?"), "chat after the meeting")
    refused_meeting_action(rec, "Luca", vote("Mara"), "vote after the meeting")
    refused_meeting_action(rec, "Sofia", SKIP, "Skip after the meeting")
    rec.tick()
    rec.step("a tick after the meeting", {})

    fail(rec, clock, "Mara", "Rui")

    # An emergency meeting that ends with everybody's Skip.
    rec.connections["Ines"].send_json({"type": "emergency"})
    rec.step("ghost presses the emergency button", {"Ines": ["error"]}, actor="Ines", quiet_for_others=True)
    put("Luca", (app.state.campus["button"]["x"], app.state.campus["button"]["y"]))
    rec.connections["Luca"].send_json({"type": "emergency"})
    rec.step("Luca calls an emergency meeting", everybody(rec, "meeting_state"), actor="Luca")
    refused_meeting_action(rec, "Sofia", vote("Mara"), "vote in the discussion")
    refused_meeting_action(rec, "Sofia", SKIP, "Skip in the discussion")
    meeting_action(rec, "Mara", chat("Not me."), "Free Rider chats")
    clock.wait(DISCUSSION_SECONDS)
    rec.tick()
    rec.step("the vote opens", everybody(rec, "meeting_state"))
    meeting_action(rec, "Mara", SKIP, "Mara skips")
    meeting_action(rec, "Luca", SKIP, "Luca skips")
    rec.connections["Sofia"].send_json(SKIP)
    meeting_result(rec)

    leave(rec, "Ines", ["lobby_state", "classic_roster", "classic_progress"])
    fail(rec, clock, "Mara", "Luca", final=True)
    return rec


# The tests


SEEN_IN_EVERY_ROUND = {
    "lobby_state", "classic_role", "you_are_fr", "classic_fail_status", "classic_progress", "positions",
    "classic_fail", "classic_roster", "meeting_state", "classic_result", "error", "left_lobby",
    "station_opened", "station_done", "classic_hiding",
}


@pytest.mark.parametrize("play", [play_five, play_six], ids=["5 players", "6 players"])
def test_every_classic_message_reaches_only_who_may_know_it(connect, clock, monkeypatch, play):
    rec = play(connect, clock, monkeypatch)
    check_all(rec)
    seen = {record.message["type"] for record in rec.records}
    assert SEEN_IN_EVERY_ROUND <= seen, f"the round never sent {SEEN_IN_EVERY_ROUND - seen}"
    states = {record.state for record in rec.records}
    assert {"HP", "FR", "ghost"} <= states


# The checks themselves catch a leak


def a_step(**changes):
    values = dict(
        name="a step", actor="Mara", members=frozenset(FIVE), ghosts=frozenset({"Tiago"}), ejected=(),
        hidden=None, victim=None, final=False, roles=tuple(sorted({"Mara": "FR", **{n: "HP" for n in FIVE[1:]}}.items())),
        tasks=tuple((name, ("1", "2", "3", "4")) for name in FIVE),
    )
    values.update(changes)
    return Step(**values)


def test_an_unclassified_type_fails_with_a_clear_message():
    record = Record(a_step(name="start"), "Ines", "HP", {"type": "mystery"})
    with pytest.raises(AssertionError, match="unclassified Classic message type mystery received by Ines at step start"):
        check_record(record)


def test_a_ghost_in_the_positions_of_a_living_player_fails():
    message = {"type": "positions", "players": [{"name": "Tiago", "x": 1.0, "y": 2.0}]}
    with pytest.raises(AssertionError, match="ghost positions"):
        check_record(Record(a_step(), "Ines", "HP", message))
    check_record(Record(a_step(), "Tiago", "ghost", message))  # a ghost may see a ghost


def test_somebody_elses_role_fails_and_the_own_role_passes():
    own = {"type": "classic_role", "role": "HP", "task_stations": [1, 2, 3, 4]}
    check_record(Record(a_step(name="start"), "Ines", "HP", own))
    with pytest.raises(AssertionError, match="names a role"):
        check_record(Record(a_step(), "Ines", "HP", {"type": "classic_roster", "players": [], "role": "FR"}))
    with pytest.raises(AssertionError, match="High Performer"):
        check_record(Record(a_step(), "Ines", "HP", {
            "type": "classic_fail_status", "available": True, "in_range": True,
            "cooldown_until": None, "server_time": 0.0,
        }))


def test_a_hidden_flag_to_a_living_high_performer_fails_and_to_a_ghost_passes():
    message = {"type": "positions", "players": [{"name": "Mara", "x": 1.0, "y": 2.0, "hidden": True}]}
    with pytest.raises(AssertionError, match="told that"):
        check_record(Record(a_step(), "Ines", "HP", message))
    check_record(Record(a_step(hidden="Mara"), "Tiago", "ghost", message))
    check_record(Record(a_step(hidden="Mara"), "Mara", "FR", message))


def test_the_hidden_free_rider_in_the_positions_of_a_high_performer_fails_at_any_distance():
    message = {"type": "positions", "players": [{"name": "Mara", "x": 1.0, "y": 2.0}, {"name": "Ines", "x": 1.0, "y": 3.0}]}
    with pytest.raises(AssertionError, match="hidden Free Rider"):
        check_record(Record(a_step(hidden="Mara"), "Ines", "HP", message))


def test_a_ghost_or_free_rider_not_told_that_he_hides_fails():
    message = {"type": "positions", "players": [{"name": "Mara", "x": 1.0, "y": 2.0}]}
    with pytest.raises(AssertionError, match="was not told"):
        check_record(Record(a_step(hidden="Mara"), "Tiago", "ghost", message))


def test_classic_hiding_to_anybody_but_a_living_free_rider_fails():
    message = {"type": "classic_hiding", "hidden": True}
    check_record(Record(a_step(hidden="Mara"), "Mara", "FR", message))
    with pytest.raises(AssertionError, match="no living Free Rider"):
        check_record(Record(a_step(hidden="Mara"), "Ines", "HP", message))
    with pytest.raises(AssertionError, match="no living Free Rider"):
        check_record(Record(a_step(hidden="Mara"), "Tiago", "ghost", message))


def test_a_rejection_for_somebody_else_fails():
    rejection = protocol.rejection("chat_rejected")
    check_record(Record(a_step(), "Mara", "FR", rejection))
    with pytest.raises(AssertionError, match="did not act"):
        check_record(Record(a_step(), "Ines", "HP", rejection))


def test_a_player_who_left_may_hear_nothing():
    with pytest.raises(AssertionError, match="left the round"):
        check_record(Record(a_step(), "Tiago", "left", {"type": "classic_progress"}))


def test_different_meeting_snapshots_in_one_step_fail():
    step = a_step(members=frozenset({"Mara", "Ines"}))
    first = {"type": "meeting_state", "seconds_left": 3}
    records = [Record(step, "Mara", "FR", first), Record(step, "Ines", "HP", {**first, "seconds_left": 2})]
    with pytest.raises(AssertionError, match="different meeting_state"):
        check_meeting_states_are_identical(records)
