// Runs the page's own js/world/world.js in Node, without a browser, for
// test_walking_diagnostic_world.py (M2-1.15): the two things world.js offers
// the walking diagnostic, Game.world.ownDrawnPosition() and
// Game.world.walkingDirection(), and on request the real diagnostic.js on
// top of it, loaded in the order of index.html.
//
// It is world_playback_in_node.js (M2-1.14) with keys, with questions to
// ownDrawnPosition() before each frame, and with the frame callbacks called
// in the order they were requested: the diagnostic asks for its frame when
// the page loads, so in every frame it runs before the world draws.
//
// Input (stdin): JSON
//   {
//     "own": "Mara",                                   the own player's name
//     "players": [{"name": "Mara", "character": "c1"}, ...],
//     "debug": true,                                   load diagnostic.js with `?debug` (default false)
//     "ask": [0, 40],                                  before the frame at t, ask ownDrawnPosition(t + each);
//                                                      null (default): never ask
//     "steps": [
//       ["positions", t, [{"name", "x", "y"}, ...]]    a message arrives at time t (ms)
//       ["frames", from, to]                           frames every 1000/60 ms from `from` up to `to`
//       ["key", t, "down" or "up", code]               a key of the keyboard, for example "KeyD"
//       ["direction", t]                               write down Game.world.walkingDirection()
//       ["stop", t]                                    Game.world.stop()
//       ["start", t]                                   Game.world.start() again
//     ]
//   }
// Output (stdout): JSON
//   {
//     "frames": [{t, camera: {x, y}, asked: [{x, y} or null, ...]}],   one per frame drawn
//     "directions": [{dx, dy, since}],                                 one per "direction" step
//     "moves": [[dx, dy], ...],                                        what the world told the server
//     "numbers": Game.diagnostic.numbers() or null without "debug"
//   }

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
let frameCallbacks = []; // [{id, callback}] in the order they were requested
let lastFrameId = 0;
let current = null; // what the frame being drawn records
const frames = [];
const directions = [];
const moves = [];
const windowListeners = new Map(); // type -> [listener]
const netHandlers = new Map(); // type -> [handler]

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

// Enough of an element for the button "E Use" and the diagnostic's panel.
function newElement() {
  return {
    style: {},
    disabled: true,
    textContent: '',
    appendChild() {},
    addEventListener() {},
    remove() {},
    blur() {},
  };
}

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
  URLSearchParams: URLSearchParams,
  location: { search: input.debug ? '?debug' : '' },
  navigator: { userAgent: 'Node stand-in browser' },
  requestAnimationFrame(callback) {
    lastFrameId += 1;
    frameCallbacks.push({ id: lastFrameId, callback: callback });
    return lastFrameId;
  },
  cancelAnimationFrame(id) {
    frameCallbacks = frameCallbacks.filter((waiting) => waiting.id !== id);
  },
  setTimeout: () => 0,
  clearTimeout: () => {},
  setInterval: () => 0,
  addEventListener(type, listener) {
    if (!windowListeners.has(type)) windowListeners.set(type, []);
    windowListeners.get(type).push(listener);
  },
  removeEventListener(type, listener) {
    windowListeners.set(type, (windowListeners.get(type) || []).filter((other) => other !== listener));
  },
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve(campus) }),
  document: {
    hidden: false,
    activeElement: null,
    body: newElement(),
    createElement: newElement,
    getElementById: (id) => (id === 'map' ? canvas : null),
    addEventListener: () => {},
    removeEventListener: () => {},
  },
};
page.window = page;
// The drawing functions of draw.js and characters.js draw nothing here: the
// camera, which looks at the own character, is what these tests read.
page.Game = {
  world: {
    drawMap: () => {},
    drawStationGlow: () => {},
    chooseLabels: (labels) => ({ shown: labels || [], hidden: new Set() }),
    drawCharacter: () => {},
  },
  net: {
    on(type, handler) {
      if (!netHandlers.has(type)) netHandlers.set(type, []);
      netHandlers.get(type).push(handler);
    },
    send: () => true,
  },
};
vm.createContext(page);

function load(name) {
  const file = path.join(WORLD, name);
  vm.runInContext(fs.readFileSync(file, 'utf8'), page, { filename: file });
}

// The order of index.html: the diagnostic comes right after world.js, and
// requests its first frame at once, long before the world is started.
load('world.js');
load('diagnostic.js');
const world = page.Game.world;

function tell(type, message) {
  (netHandlers.get(type) || []).forEach((handler) => handler(message));
}

function sendMove(dx, dy) {
  moves.push([dx, dy]);
}

function drawFrame(t) {
  clock = t;
  const asked = (input.ask || []).map((later) => world.ownDrawnPosition(t + later));
  const waiting = frameCallbacks;
  frameCallbacks = [];
  current = { t: t, camera: null, asked: asked };
  waiting.forEach((entry) => entry.callback(t));
  if (current.camera) frames.push(current); // nothing is written down while the world is stopped
  current = null;
}

const STEPS = {
  positions(t, players) {
    clock = t;
    // As in the lobby page: the world and the diagnostic both get the message.
    world.setPositions(players);
    tell('positions', { type: 'positions', players: players });
  },
  frames(from, to) {
    for (let t = from; t <= to + 1e-9; t += FRAME_MILLISECONDS) drawFrame(t);
  },
  key(t, upOrDown, code) {
    clock = t;
    const event = { code: code, key: code, target: null, repeat: false, preventDefault() {} };
    (windowListeners.get('key' + upOrDown) || []).forEach((listener) => listener(event));
  },
  direction(t) {
    clock = t;
    directions.push(world.walkingDirection());
  },
  stop(t) {
    clock = t;
    world.stop();
  },
  start(t) {
    clock = t;
    world.start(canvas, sendMove);
  },
};

async function main() {
  world.setOwnName(input.own);
  tell('signed_in', { type: 'signed_in', name: input.own, guest: true });
  world.start(canvas, sendMove);
  world.setPlayers(input.players);
  // Let the map "download": fetch() and json() above are promises.
  await new Promise((resolve) => setImmediate(resolve));
  input.steps.forEach(([name, ...values]) => STEPS[name](...values));
  const diagnostic = page.Game.diagnostic;
  process.stdout.write(JSON.stringify({
    frames: frames,
    directions: directions,
    moves: moves,
    numbers: diagnostic.active ? diagnostic.numbers() : null,
  }));
}

main();
