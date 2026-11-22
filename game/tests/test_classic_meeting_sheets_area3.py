"""Area 3: a meeting removes only the F-sheet it reports.

Bug: client/js/classic/meeting.js cleared every F-sheet of the client on each
meeting snapshot, while the server still had them. A sheet that was on the
map before a meeting then had no report button afterwards.
"""

import json
import subprocess
from pathlib import Path

from server.main import app
from task_helpers import clock, client, connect, placeholder_at_every_station  # noqa: F401
from test_classic_fail_hud_area3 import drain_fail, place_players
from test_classic_server_features import classic_for, start_classic


ROOT = Path(__file__).resolve().parents[1]
NAMES = ("Mara", "Tiago", "Ines", "Rui")

NODE_SCRIPT = r"""
const fs = require('fs');
const vm = require('vm');
const root = __ROOT__;

const handlers = {};
const dom = new Proxy(function () {}, {
  get(target, prop) {
    if (prop === Symbol.toPrimitive) return () => 0;
    if (prop === 'then') return undefined;
    if (!(prop in target)) target[prop] = dom;
    return target[prop];
  },
  set(target, prop, value) { target[prop] = value; return true; },
  apply() { return dom; },
});

const sandbox = {
  console: console, Math: Math, JSON: JSON, Array: Array, Map: Map, Set: Set,
  Object: Object, String: String, Number: Number, Symbol: Symbol,
  document: { getElementById: () => dom, createElement: () => dom, body: dom },
  performance: { now: () => 0 },
  requestAnimationFrame: () => 0,
  cancelAnimationFrame: () => {},
  setTimeout: () => 0,
  clearTimeout: () => {},
  innerWidth: 800,
  innerHeight: 600,
  Game: { net: { on(name, fn) { handlers[name] = fn; }, send() {}, ask() {} } },
};
sandbox.window = sandbox;
sandbox.addEventListener = () => {};
sandbox.removeEventListener = () => {};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(root + '/client/js/world/world.js', 'utf8'), sandbox);
vm.runInContext(fs.readFileSync(root + '/client/js/classic/meeting.js', 'utf8'), sandbox);
sandbox.Game.classicMeeting.setup();

const world = sandbox.Game.world;
const show = handlers['meeting_state'];
function snapshot(overrides) {
  return Object.assign({
    type: 'meeting_state', phase: 'discussion', seconds_left: 45,
    living: ['Mara', 'Tiago', 'Rui'], ghosts: ['Ines'], messages: [], voted: [],
    reason: 'report', trigger_player_id: 'Tiago', reported_sheet_id: 'f-sheet-1',
    ejected_id: null, revealed_role: null, tie: false, winner: null,
  }, overrides);
}

world.addBloodSheet({ type: 'classic_fail', sheet_id: 'f-sheet-1', position: { x: 100, y: 100 } });
world.addBloodSheet({ type: 'classic_fail', sheet_id: 'f-sheet-2', position: { x: 120, y: 120 } });
const seen = [];
show(snapshot({}));
seen.push(world.bloodSheetIds());
show(snapshot({ phase: 'result', seconds_left: 0 }));
seen.push(world.bloodSheetIds());
show(snapshot({ reason: 'emergency', reported_sheet_id: null }));
seen.push(world.bloodSheetIds());
world.stop();
seen.push(world.bloodSheetIds());
process.stdout.write(JSON.stringify(seen));
"""


def test_client_keeps_all_sheets_through_meetings_until_the_round_ends():
    script = NODE_SCRIPT.replace("__ROOT__", json.dumps(str(ROOT)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    after_report, after_result, after_emergency, after_stop = json.loads(result.stdout)
    assert after_report == ["f-sheet-1", "f-sheet-2"]
    assert after_result == ["f-sheet-1", "f-sheet-2"]
    assert after_emergency == ["f-sheet-1", "f-sheet-2"]
    assert after_stop == []


def test_meeting_snapshot_names_the_reported_sheet(connect, clock):
    connections, _code, _public, _start = start_classic(connect, NAMES)
    round_state = classic_for(NAMES[0])
    fr_id = next(player for player, role in round_state.roles.items() if role == "FR")
    hp_ids = [player for player, role in round_state.roles.items() if role == "HP"]
    lobby = app.state.lobbies.lobby_of(fr_id)
    place_players(lobby, NAMES, {player: (100.0, 100.0) for player in NAMES})

    connections[fr_id].send_json({"type": "fail"})
    fail = connections[fr_id].receive_json()
    drain_fail(connections, round_state, fr_id, fail["target_id"])

    reporter_id = next(player for player in hp_ids if player != fail["target_id"])
    connections[reporter_id].send_json({
        "type": "report", "sheet_id": fail["sheet_id"], "position": fail["position"],
    })
    for connection in connections.values():
        snapshot = connection.receive_json()
        assert snapshot["type"] == "meeting_state"
        assert snapshot["reason"] == "report"
        assert snapshot["reported_sheet_id"] == fail["sheet_id"]
