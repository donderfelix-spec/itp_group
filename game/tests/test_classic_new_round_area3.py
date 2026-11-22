"""Area 3: a new round closes the meeting view and forgets the old vote.

Bug: the meeting view (client/js/classic/meeting.js) stayed open after a
round ended in a vote and the host started a new round. It only closed
after its own result timer, so the old result or vote could still cover
the new round.

The test runs the real client files in a Node vm with a small DOM stub:
a meeting ends the round (the Free Riders win by parity), the host starts
a new round, and the meeting view must be closed by then.
"""

import json
import subprocess
from pathlib import Path

from server.classic.meeting import start_discussion
from server.main import app
from task_helpers import clock, client, connect, placeholder_at_every_station  # noqa: F401
from test_classic_server_features import classic_for, start_classic


ROOT = Path(__file__).resolve().parents[1]

NODE_SCRIPT = r"""
const fs = require('fs');
const vm = require('vm');
const root = __ROOT__;

// A new fake element per call. Unknown properties become fake elements or
// no-op functions, so the real client code runs without a browser.
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
const byId = {};
const timers = [];
function elementById(id) {
  if (!byId[id]) byId[id] = makeEl();
  return byId[id];
}

const sandbox = {
  console, Math, JSON, Array, Map, Set, Object, String, Number, Symbol, Promise,
  setImmediate, Infinity, NaN,
  document: {
    getElementById: elementById,
    createElement: () => makeEl(),
    body: makeEl(),
    addEventListener() {},
    removeEventListener() {},
  },
  performance: { now: () => 0 },
  requestAnimationFrame: () => 0,
  cancelAnimationFrame() {},
  setTimeout: (fn, ms) => { timers.push({ fn, ms, cleared: false }); return timers.length; },
  clearTimeout: (id) => { if (timers[id - 1]) timers[id - 1].cleared = true; },
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
vm.runInContext(fs.readFileSync(root + '/client/js/classic/round.js', 'utf8'), sandbox);
sandbox.Game.classicMeeting.setup();
sandbox.Game.lobby = { leaveLobby() {} };
sandbox.Game.classicRound.setup();

function meeting(overrides) {
  return Object.assign({
    type: 'meeting_state', phase: 'result', seconds_left: 0,
    living: ['Mara', 'Tiago', 'Rui'], ghosts: ['Ines'], messages: [], voted: ['Mara', 'Tiago', 'Rui'],
    reason: 'report', trigger_player_id: 'Tiago', reported_sheet_id: 'f-sheet-1',
    ejected_id: 'Tiago', revealed_role: 'HP', tie: false, winner: 'FR',
    vote_counts: [{ name: 'Mara', votes: 0 }, { name: 'Tiago', votes: 2 }, { name: 'Rui', votes: 0 }],
  }, overrides);
}
function lobby(phase) {
  return {
    type: 'lobby_state', code: 'ABCD', host: 'Mara', mode: 'classic', phase: phase,
    players: [{ name: 'Mara', character: 'a' }, { name: 'Tiago', character: 'b' }],
  };
}

const screen = elementById('classic-meeting');
const seen = {};
// The round ends during the vote: the result is shown and the round is over.
handlers['meeting_state'](meeting({}));
seen.afterResult = screen.hidden;
handlers['classic_result']({
  type: 'classic_result', winner: 'FR', reason: 'free_riders_reached_parity',
  roles: { Mara: 'HP', Tiago: 'FR' }, stats: { failures: 1, completed_tasks: 0, meetings: 1 },
});
sandbox.Game.classicRound.setLobby(lobby('lobby'));
// The host starts a new round.
sandbox.Game.classicRound.setLobby(lobby('round'));
seen.afterNewRound = screen.hidden;
seen.voteResultHidden = elementById('classic-vote-result').hidden;

// A result closes by itself after its time, and a repeated copy of it stays closed.
// A new meeting starts with its discussion, then its result comes.
handlers['meeting_state'](meeting({ phase: 'discussion', seconds_left: 45, reason: 'emergency', reported_sheet_id: null }));
handlers['meeting_state'](meeting({ reason: 'emergency', reported_sheet_id: null }));
const resultTimers = timers.filter((timer) => timer.ms === 8000 && !timer.cleared);
seen.resultTimerSet = resultTimers.length === 1;
resultTimers.forEach((timer) => timer.fn());
seen.closedByTimer = screen.hidden;
handlers['meeting_state'](meeting({ reason: 'emergency', reported_sheet_id: null }));
seen.repeatedResultStaysClosed = screen.hidden;
process.stdout.write(JSON.stringify(seen));
"""


def test_a_new_round_closes_the_meeting_view_that_was_open_at_the_end():
    script = NODE_SCRIPT.replace("__ROOT__", json.dumps(str(ROOT)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    seen = json.loads(result.stdout)
    assert seen["afterResult"] is False, "the result must be shown first"
    assert seen["afterNewRound"] is True
    assert seen["voteResultHidden"] is True
    assert seen["resultTimerSet"] is True
    assert seen["closedByTimer"] is True
    assert seen["repeatedResultStaysClosed"] is True


def receive_until(connection, message_type):
    """Receive messages up to and including the first one of `message_type`."""
    received = []
    while True:
        message = connection.receive_json()
        received.append(message)
        if message["type"] == message_type:
            return received


def test_a_round_ended_by_a_vote_leaves_no_meeting_for_the_next_round(connect, clock):
    names = ("Mara", "Tiago", "Ines", "Rui")
    connections, _code, _public, _start = start_classic(connect, names)
    old_round = classic_for(names[0])
    fr_id = next(player for player, role in old_round.roles.items() if role == "FR")
    hp_ids = [player for player, role in old_round.roles.items() if role == "HP"]
    lobby = app.state.lobbies.lobby_of(fr_id)
    # One High Performer is already out. Ejecting another one leaves one
    # Free Rider and one High Performer: parity, so the Free Riders win.
    ghost = hp_ids[0]
    old_round.eliminated = {ghost}
    living = [fr_id] + hp_ids[1:]
    lobby.meeting = start_discussion(living, [ghost], clock.now, old_round.state())
    clock.wait(45.0)
    for voter in living:
        connections[voter].send_json({"type": "vote", "target_id": hp_ids[1]})
        for connection in connections.values():
            connection.receive_json()
    clock.wait(30.0)
    # Only a message from a player makes the server count the votes.
    connections[living[0]].send_json({"type": "vote", "target_id": fr_id})
    assert connections[living[0]].receive_json()["code"] == "vote_rejected"
    for connection in connections.values():
        messages = receive_until(connection, "classic_result")
        assert messages[-1]["winner"] == "FR"
    assert lobby.round_is_running() is False
    assert lobby.meeting is None
    assert lobby.meeting_clock is None

    connections[names[0]].send_json({"type": "start_game"})
    for connection in connections.values():
        receive_until(connection, "classic_progress")
    assert lobby.round_is_running()
    assert lobby.classic_round is not old_round
    assert lobby.meeting is None
    assert lobby.meeting_clock is None
