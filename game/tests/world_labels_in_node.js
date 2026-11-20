// Runs the page's own characters.js, draw.js and world.js in Node, without a
// browser, for test_name_labels_drawn.py (M2-1.8, checked by the tester).
//
// tests/labels_in_node.js runs only Game.world.chooseLabels(). This runs the
// whole drawing loop of world.js: positions as the server sends them, the
// drawing order (own character in front), the label above each head, the
// choice of labels and the names finally written on the canvas.
//
// The canvas, the document, the clock and the frame timer are stand-ins.
// The canvas writes down every text drawn in the font of the name labels;
// every other drawing call does nothing. measureText() counts 3 map units
// per letter.
//
// Input (stdin): JSON {"campus": map, "steps": [step, ...]}. A step is a list:
//   ["start"]                   Game.world.start() on the stand-in canvas
//   ["own", name]               Game.world.setOwnName(name)
//   ["players", [{name, character}]]  Game.world.setPlayers(list)
//   ["positions", [{name, x, y}]]     Game.world.setPositions(list)
//   ["frame", milliseconds]     the clock moves on by this much, then one frame is drawn
//   ["stop"]                    Game.world.stop()
// Output (stdout): JSON list with one entry per "frame" step: the names
// drawn in that frame, each {name, x, y}, in the order they were drawn.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const WORLD = path.join(__dirname, '..', 'client', 'js', 'world');
const FILES = ['characters.js', 'draw.js', 'world.js'];
const NAME_FONT = 'bold 5.5px';
const UNITS_PER_LETTER = 3;

const input = JSON.parse(fs.readFileSync(0, 'utf8'));

// A stand-in for anything with methods: every method does nothing and
// returns the stand-in again (paths, gradients, ...).
function anything() {
  const thing = new Proxy(function () {}, {
    get: () => thing,
    apply: () => thing,
    construct: () => thing,
  });
  return thing;
}

let drawnNames = null; // the names of the frame being drawn
function recordingContext() {
  const state = {};
  return new Proxy(state, {
    get(target, key) {
      if (key === 'fillText') {
        return (text, x, y) => {
          if (drawnNames && String(target.font).startsWith(NAME_FONT)) {
            drawnNames.push({ name: String(text), x, y });
          }
        };
      }
      if (key === 'measureText') return (text) => ({ width: String(text).length * UNITS_PER_LETTER });
      if (key === 'getTransform') return () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 });
      if (key in target) return target[key];
      return () => anything();
    },
    set(target, key, value) {
      target[key] = value;
      return true;
    },
  });
}

function element() {
  return {
    addEventListener() {},
    removeEventListener() {},
    appendChild() {},
    remove() {},
    blur() {},
    focus() {},
    classList: { add() {}, remove() {}, toggle() {} },
    style: {},
  };
}

let clock = 1000;
let waitingFrame = null;
const context = recordingContext();
const canvas = Object.assign(element(), {
  clientWidth: 800,
  clientHeight: 600,
  width: 0,
  height: 0,
  parentNode: element(),
  getContext: () => context,
});

const page = {
  console,
  Path2D: function Path2D() { return anything(); },
  performance: { now: () => clock },
  requestAnimationFrame: (callback) => { waitingFrame = callback; return 1; },
  cancelAnimationFrame: () => { waitingFrame = null; },
  setTimeout: () => 0,
  clearTimeout: () => {},
  devicePixelRatio: 1,
  addEventListener() {},
  removeEventListener() {},
  document: Object.assign(element(), { createElement: element, activeElement: null, hidden: false }),
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve(input.campus) }),
};
page.window = page;
vm.createContext(page);
FILES.forEach((file) => {
  const fullPath = path.join(WORLD, file);
  vm.runInContext(fs.readFileSync(fullPath, 'utf8'), page, { filename: fullPath });
});

async function run() {
  const world = page.Game.world;
  const frames = [];
  for (const [kind, value] of input.steps) {
    if (kind === 'start') {
      world.start(canvas, () => {});
      // Lets the stand-in fetch hand over the map.
      await new Promise((resolve) => setImmediate(resolve));
    } else if (kind === 'own') {
      world.setOwnName(value);
    } else if (kind === 'players') {
      world.setPlayers(value);
    } else if (kind === 'positions') {
      world.setPositions(value);
    } else if (kind === 'frame') {
      clock += value;
      drawnNames = [];
      const callback = waitingFrame;
      waitingFrame = null;
      if (callback) callback(clock);
      frames.push(drawnNames);
      drawnNames = null;
    } else if (kind === 'stop') {
      world.stop();
    } else {
      throw new Error('Unknown step: ' + kind);
    }
  }
  return frames;
}

run().then(
  (frames) => process.stdout.write(JSON.stringify(frames)),
  (problem) => { console.error(problem); process.exit(1); },
);
