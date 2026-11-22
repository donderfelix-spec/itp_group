"""Area 3: during a vote every player sees how many votes each living player has.

The server sends only the number per living player inside the meeting state
(S-100). Who voted for whom never leaves the server. These tests cover the
builder in server/protocol.py, the websocket rules of a vote (accepted,
rejected and edge cases) and the meeting view that shows the numbers.
"""

import json
import subprocess
from pathlib import Path

import pytest

from server import protocol
from server.classic.meeting import start_discussion
from server.main import app
from task_helpers import clock, client, connect, placeholder_at_every_station  # noqa: F401
from test_classic_server_features import classic_for, start_classic


ROOT = Path(__file__).resolve().parents[1]
NAMES = ("Mara", "Tiago", "Ines", "Rui")


def test_vote_counts_builder_lists_names_and_counts_and_nothing_else():
    assert protocol.vote_counts({"Mara": 0, "Tiago": 2}) == [
        {"name": "Mara", "votes": 0},
        {"name": "Tiago", "votes": 2},
    ]


@pytest.mark.parametrize("counts", [
    {"Mara": -1},
    {"Mara": 1.5},
    {"Mara": True},
    {7: 1},
])
def test_vote_counts_builder_rejects_values_that_are_not_counts(counts):
    with pytest.raises(ValueError):
        protocol.vote_counts(counts)


CLIENT_SCRIPT = r"""
const fs = require('fs');
const vm = require('vm');
const root = __ROOT__;

function makeEl() {
  const target = function () {};
  return new Proxy(target, {
    get(t, prop) {
      if (prop === Symbol.toPrimitive) return () => 0;
      if (prop === 'then') return undefined;
      if (!(prop in t)) t[prop] = makeEl();
      return t[prop];
    },
    set(t, prop, value) { t[prop] = value; return true; },
    apply() { return makeEl(); },
  });
}

const handlers = {};
const created = [];
const byId = {};
const sandbox = {
  console, Math, JSON, Array, Map, Set, Object, String, Number, Symbol, Promise,
  setImmediate, Infinity, NaN,
  document: {
    getElementById: (id) => (byId[id] = byId[id] || makeEl()),
    createElement: () => { const el = makeEl(); created.push(el); return el; },
    body: makeEl(),
    addEventListener() {},
    removeEventListener() {},
  },
  performance: { now: () => 0 },
  requestAnimationFrame: () => 0,
  cancelAnimationFrame() {},
  setTimeout: () => 0,
  clearTimeout() {},
  innerWidth: 800,
  innerHeight: 600,
  Game: { net: { on(name, fn) { handlers[name] = fn; }, send() { return true; }, ask() {} } },
};
sandbox.window = sandbox;
sandbox.addEventListener = () => {};
sandbox.removeEventListener = () => {};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(root + '/client/js/classic/hud-actions.js', 'utf8'), sandbox);
vm.runInContext(fs.readFileSync(root + '/client/js/world/world.js', 'utf8'), sandbox);
vm.runInContext(fs.readFileSync(root + '/client/js/classic/meeting.js', 'utf8'), sandbox);
sandbox.Game.classicMeeting.setup();

function meeting(overrides) {
  return Object.assign({
    type: 'meeting_state', phase: 'voting', seconds_left: 20,
    living: ['Mara', 'Tiago', 'Rui'], ghosts: ['Ines'], messages: [], voted: [],
    reason: 'report', trigger_player_id: 'Mara', reported_sheet_id: 'f-sheet-1',
    ejected_id: null, revealed_role: null, tie: false, winner: null,
    vote_counts: [{ name: 'Mara', votes: 0 }, { name: 'Tiago', votes: 2 }, { name: 'Rui', votes: 1 }],
  }, overrides);
}
function labels() {
  const result = {};
  created.filter((el) => el.className === 'classic-vote-player').forEach((button) => {
    result[button.dataset.targetId] = button.voteCountLabel ? button.voteCountLabel.textContent : null;
  });
  return result;
}

handlers['meeting_state'](meeting({ phase: 'discussion', seconds_left: 45, vote_counts: [] }));
handlers['meeting_state'](meeting({}));
const first = labels();
// A new count arrives while the vote is still open; the list is not rebuilt.
handlers['meeting_state'](meeting({ vote_counts: [{ name: 'Mara', votes: 3 }, { name: 'Tiago', votes: 2 }, { name: 'Rui', votes: 0 }] }));
const second = labels();
process.stdout.write(JSON.stringify({ first, second }));
"""


def test_the_meeting_view_shows_the_count_next_to_each_living_player():
    script = CLIENT_SCRIPT.replace("__ROOT__", json.dumps(str(ROOT)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    outcome = json.loads(result.stdout)
    assert outcome["first"] == {"Mara": "0", "Tiago": "2", "Rui": "1"}
    assert outcome["second"] == {"Mara": "3", "Tiago": "2", "Rui": "0"}


def vote_setup(connect, clock, names=NAMES):
    connections, _code, _public, _start = start_classic(connect, names)
    round_state = classic_for(names[0])
    ghost = names[-1]
    living = [name for name in names if name != ghost]
    lobby = app.state.lobbies.lobby_of(names[0])
    lobby.meeting = start_discussion(living, [ghost], clock.now, round_state.state())
    clock.wait(45.0)
    return connections, living, ghost


def receive_meeting_state(connection):
    while True:
        message = connection.receive_json()
        if message["type"] == "meeting_state":
            return message


def test_every_player_gets_the_same_counts_and_a_ghost_sees_them_too(connect, clock):
    connections, living, ghost = vote_setup(connect, clock)
    first, second, third = living

    connections[first].send_json({"type": "vote", "target_id": second})
    snapshots = {name: receive_meeting_state(connection) for name, connection in connections.items()}
    assert all(snapshot == snapshots[first] for snapshot in snapshots.values())
    assert snapshots[ghost]["vote_counts"] == [
        {"name": first, "votes": 0}, {"name": second, "votes": 1}, {"name": third, "votes": 0},
    ]
    assert "votes" not in snapshots[first]


def test_a_vote_for_oneself_counts_for_oneself(connect, clock):
    connections, living, _ghost = vote_setup(connect, clock)
    first, second, third = living
    connections[first].send_json({"type": "vote", "target_id": second})
    for connection in connections.values():
        receive_meeting_state(connection)
    connections[third].send_json({"type": "vote", "target_id": third})
    snapshot = receive_meeting_state(connections[first])
    for connection in list(connections.values())[1:]:
        receive_meeting_state(connection)
    assert snapshot["vote_counts"] == [
        {"name": first, "votes": 0}, {"name": second, "votes": 1}, {"name": third, "votes": 1},
    ]


def test_a_ghost_vote_is_rejected_and_changes_no_count(connect, clock):
    connections, living, ghost = vote_setup(connect, clock)
    connections[ghost].send_json({"type": "vote", "target_id": living[0]})
    assert connections[ghost].receive_json()["code"] == "vote_rejected"
    snapshot = receive_meeting_state(connections[ghost])
    assert all(entry["votes"] == 0 for entry in snapshot["vote_counts"])
    for connection in list(connections.values())[:-1]:
        assert receive_meeting_state(connection)["vote_counts"] == snapshot["vote_counts"]


def test_a_late_vote_after_the_vote_is_rejected_and_the_result_counts_stay(connect, clock):
    connections, living, _ghost = vote_setup(connect, clock)
    first, second, third = living
    connections[first].send_json({"type": "vote", "target_id": second})
    for connection in connections.values():
        receive_meeting_state(connection)
    clock.wait(30.0)
    connections[third].send_json({"type": "vote", "target_id": second})
    assert connections[third].receive_json()["code"] == "vote_rejected"
    result = receive_meeting_state(connections[third])
    assert result["phase"] == "result"
    # The player voted out keeps the count of the vote that ejected them.
    assert {entry["name"]: entry["votes"] for entry in result["vote_counts"]} == {
        first: 0, second: 1, third: 0,
    }


def test_discussion_sends_no_counts(clock):
    from server.classic.meeting import meeting_snapshot

    meeting = start_discussion(["Mara", "Tiago", "Ines"], ["Rui"], clock.now)
    assert meeting_snapshot(meeting, clock.now)["vote_counts"] == []
