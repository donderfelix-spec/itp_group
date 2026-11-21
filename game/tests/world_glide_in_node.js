// Runs the page's own js/world/world.js in Node, without a browser, for
// test_play_walking_glide.py (M2-1.12).
//
// The clock, the frames, the canvas and the drawing functions of the other
// files are stand-ins, so a test decides exactly when a `positions` message
// arrives and when a frame is drawn. world.js itself is the real code: its
// glide, its camera, its steps and its station glow.
//
// Input (stdin): JSON
//   {
//     "own": "Mara",                                   the own player's name
//     "players": [{"name": "Mara", "character": "c1"}, ...],
//     "usable": [2] or null,                           stations that may glow
//     "steps": [
//       ["positions", t, [{"name", "x", "y"}, ...]]    a message arrives at time t (ms)
//       ["frames", from, to]                           frames every 1000/60 ms from `from` up to `to`
//       ["start_of_round", t]                          the lobby page says a round starts
//     ]
//   }
// Output (stdout): JSON list with one entry per frame:
//   {t, camera: {x, y}, glow: id or null, useButtonOn: bool,
//    characters: [{character, x, middleY, mirrored, stride, walkPhase}]}

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const WORLD = path.join(__dirname, '..', 'client', 'js', 'world');
const FRAME_MILLISECONDS = 1000 / 60;
const CANVAS_WIDTH = 1280;
const CANVAS_HEIGHT = 800;

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const campus = JSON.parse(fs.readFileSync(path.join(WORLD, 'campus.json'), 'utf8'));

let clock = 0;
let frameCallback = null;
let current = null; // what the frame being drawn records
const frames = [];

// The canvas context: only setTransform is read back (it carries the camera).
const context = new Proxy({}, {
  get(target, key) {
    if (key === 'setTransform') {
      return (scale, b, c, d, e, f) => {
        if (current && scale !== 1) {
          current.camera = { x: (CANVAS_WIDTH / 2 - e) / scale, y: (CANVAS_HEIGHT / 2 - f) / d };
        }
      };
    }
    if (key === 'measureText') return (text) => ({ width: String(text).length * 3 });
    if (key in target) return target[key];
    return () => {};
  },
  set(target, key, value) {
    target[key] = value;
    return true;
  },
});

const button = { disabled: true, addEventListener() {}, remove() {}, blur() {} };
const canvas = {
  clientWidth: CANVAS_WIDTH,
  clientHeight: CANVAS_HEIGHT,
  width: 0,
  height: 0,
  getContext: () => context,
  parentNode: { appendChild() {} },
};

const page = {
  console: console,
  devicePixelRatio: 1,
  performance: { now: () => clock },
  requestAnimationFrame: (callback) => { frameCallback = callback; return 1; },
  cancelAnimationFrame: () => { frameCallback = null; },
  setTimeout: () => 0,
  clearTimeout: () => {},
  addEventListener: () => {},
  removeEventListener: () => {},
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve(campus) }),
  document: {
    hidden: false,
    activeElement: null,
    createElement: () => button,
    addEventListener: () => {},
    removeEventListener: () => {},
  },
};
page.window = page;
// The drawing functions of draw.js and characters.js: they only write down
// what world.js asks them to draw.
page.Game = {
  world: {
    drawMap: () => {},
    drawStationGlow: (ctx, station) => { if (current) current.glow = station.id; },
    // The labels are not what these tests look at: every label is shown.
    chooseLabels: (labels) => ({ shown: labels || [], hidden: new Set() }),
    drawCharacter: (ctx, character, x, middleY, size, pose) => {
      if (current) {
        current.characters.push({
          character: character,
          x: x,
          middleY: middleY,
          size: size,
          mirrored: pose.mirrored,
          stride: pose.stride,
          walkPhase: pose.walkPhase,
        });
      }
    },
  },
};
vm.createContext(page);
const file = path.join(WORLD, 'world.js');
vm.runInContext(fs.readFileSync(file, 'utf8'), page, { filename: file });
const world = page.Game.world;

function drawFrame(t) {
  clock = t;
  const callback = frameCallback;
  frameCallback = null;
  current = { t: t, camera: null, glow: null, characters: [] };
  callback(t);
  current.useButtonOn = !button.disabled;
  frames.push(current);
  current = null;
}

const STEPS = {
  positions(t, players) {
    clock = t;
    world.setPositions(players);
  },
  frames(from, to) {
    for (let t = from; t <= to + 1e-9; t += FRAME_MILLISECONDS) drawFrame(t);
  },
  start_of_round(t) {
    clock = t;
    world.startOfRound();
  },
};

async function main() {
  world.setOwnName(input.own);
  world.start(canvas, () => {});
  world.setPlayers(input.players);
  world.setUsableStations(input.usable === undefined ? null : input.usable);
  // Let the map "download": fetch() and json() above are promises.
  await new Promise((resolve) => setImmediate(resolve));
  input.steps.forEach(([name, ...values]) => STEPS[name](...values));
  process.stdout.write(JSON.stringify(frames));
}

main();
