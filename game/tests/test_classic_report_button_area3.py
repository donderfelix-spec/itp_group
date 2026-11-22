"""Area 3: the Report button stays for a living player near a sheet after a meeting.

Bug: client/js/classic/meeting.js cleared every F-sheet of the client when a
meeting snapshot arrived. A living player standing next to a sheet that was
still on the map then lost the Report button, even though the server still
had the sheet.

The test drives the real client files (draw.js, hud-actions.js, world.js,
meeting.js) in a Node vm with a small DOM stub; only the map and character
drawing are stand-ins. Sheet A is reported in a meeting, sheet B is not;
both stay on the map (S-150), and the living player stands next to sheet B.
"""

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

NODE_SCRIPT = r"""
const fs = require('fs');
const vm = require('vm');
const root = __ROOT__;

// A fresh fake element per call; unknown properties become fake elements or no-op functions.
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

const created = [];
const handlers = {};
let clock = 0;
let frames = [];
const canvas = makeEl();
canvas.getContext = () => makeEl();
canvas.parentNode = makeEl();
canvas.parentNode.clientWidth = 800;
canvas.parentNode.clientHeight = 600;
canvas.clientWidth = 800;
canvas.clientHeight = 600;
canvas.width = 800;
canvas.height = 600;

const sandbox = {
  console, Math, JSON, Array, Map, Set, Object, String, Number, Symbol, Promise, Proxy,
  setImmediate, Infinity, NaN,
  document: {
    getElementById: () => makeEl(),
    createElement: () => { const el = makeEl(); created.push(el); return el; },
    body: makeEl(),
    addEventListener() {},
    removeEventListener() {},
  },
  performance: { now: () => clock },
  requestAnimationFrame: (cb) => { frames.push(cb); return frames.length; },
  cancelAnimationFrame() {},
  setTimeout: () => 0,
  clearTimeout() {},
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({
    width: 1000, height: 1000, spawn: { x: 0, y: 0 }, stations: [], button: null,
  }) }),
  innerWidth: 800,
  innerHeight: 600,
  Game: { net: { on(name, fn) { handlers[name] = fn; }, send() {}, ask() {} } },
};
sandbox.window = sandbox;
sandbox.addEventListener = () => {};
sandbox.removeEventListener = () => {};
vm.createContext(sandbox);
// draw.js comes before world.js, as in index.html: world.js takes the real
// Game.world.chooseLabels (which name labels are drawn) from it.
vm.runInContext(fs.readFileSync(root + '/client/js/world/draw.js', 'utf8'), sandbox);
vm.runInContext(fs.readFileSync(root + '/client/js/classic/hud-actions.js', 'utf8'), sandbox);
vm.runInContext(fs.readFileSync(root + '/client/js/world/world.js', 'utf8'), sandbox);
vm.runInContext(fs.readFileSync(root + '/client/js/classic/meeting.js', 'utf8'), sandbox);
const world = sandbox.Game.world;
// Stand-ins for the map and character drawing (draw.js, characters.js): the
// test is about the Report button, not about what the canvas shows.
world.drawMap = () => {};
world.drawCharacter = () => {};
world.drawStationGlow = () => {};
sandbox.Game.classicMeeting.setup();

function runFrame(advance) {
  clock += advance;
  const cb = frames.pop();
  if (cb) cb(clock);
}
const tick = () => new Promise((resolve) => setImmediate(resolve));
function reportButton() {
  return created.find((el) => el.className === 'button report-button');
}
function meeting(overrides) {
  return Object.assign({
    type: 'meeting_state', phase: 'discussion', seconds_left: 45,
    living: ['Mara', 'Tiago', 'Rui'], ghosts: ['Ines'], messages: [], voted: [],
    reason: 'report', trigger_player_id: 'Tiago', reported_sheet_id: 'f-sheet-1',
    ejected_id: null, revealed_role: null, tie: false, winner: null,
  }, overrides);
}

(async () => {
  world.setOwnName('Tiago');
  world.setPlayers([
    { name: 'Mara', character: 'a', ghost: false },
    { name: 'Tiago', character: 'b', ghost: false },
    { name: 'Rui', character: 'c', ghost: false },
    { name: 'Ines', character: 'd', ghost: true },
  ]);
  world.start(canvas, () => {});
  await tick();
  // Sheet A lies under Tiago (who reports it), sheet B one unit to the side.
  world.addBloodSheet({ type: 'classic_fail', sheet_id: 'f-sheet-1', position: { x: 100, y: 100 } });
  world.addBloodSheet({ type: 'classic_fail', sheet_id: 'f-sheet-2', position: { x: 101, y: 100 } });
  world.setPositions([
    { name: 'Tiago', x: 100, y: 100 }, { name: 'Mara', x: 300, y: 300 },
    { name: 'Rui', x: 400, y: 400 }, { name: 'Ines', x: 500, y: 500 },
  ]);
  for (let i = 0; i < 5; i++) runFrame(1000);
  const button = reportButton();
  const before = button.hidden;

  handlers['meeting_state'](meeting({ phase: 'discussion', seconds_left: 45 }));
  handlers['meeting_state'](meeting({ phase: 'voting', seconds_left: 30 }));
  handlers['meeting_state'](meeting({ phase: 'result', seconds_left: 0, tie: true }));
  for (let i = 0; i < 5; i++) runFrame(1000);
  const after = button.hidden;

  process.stdout.write(JSON.stringify({
    buttonFound: Boolean(button),
    hiddenBeforeMeeting: before,
    hiddenAfterMeeting: after,
    sheetsAfter: world.bloodSheetIds ? world.bloodSheetIds() : null,
  }));
  world.stop();
})().catch((error) => {
  process.stdout.write(JSON.stringify({ error: String(error && error.stack || error) }));
});
"""


def test_report_button_stays_for_a_living_player_next_to_a_sheet_after_a_meeting():
    script = NODE_SCRIPT.replace("__ROOT__", json.dumps(str(ROOT)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    outcome = json.loads(result.stdout)
    assert "error" not in outcome, outcome
    assert outcome["buttonFound"] is True
    assert outcome["hiddenBeforeMeeting"] is False
    assert outcome["hiddenAfterMeeting"] is False
    # S-150: a reported sheet (f-sheet-1) stays on the map until the round ends.
    assert outcome["sheetsAfter"] == ["f-sheet-1", "f-sheet-2"]
