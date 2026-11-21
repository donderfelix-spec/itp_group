// Runs the page's own js/world/bridge.js, world.js and diagnostic.js in Node,
// without a browser, for the tests of "bridge the gaps" (M2-1.16):
// test_bridge_gaps.py, test_bridge_gaps_edges.py and test_bridge_diagnostic.py.
//
// It is world_playback_in_node.js (M2-1.14) and world_diagnostic_in_node.js
// (M2-1.15) in one: the clock, the frames, the keyboard, the canvas and the
// drawing functions of the other files are stand-ins, so a test decides
// exactly when a key is pressed, when a `positions` message arrives and when
// a frame is drawn. The three files themselves are the real code, loaded in
// the order of index.html.
//
// Input (stdin): JSON
//   {
//     "own": "Mara",                                   the own player's name
//     "players": [{"name": "Mara", "character": "c1"}, ...],
//     "search": "?debug&bridge=off",                   the page's address after the "?" (default "")
//     "bridge": true,                                  load bridge.js (default true)
//     "ask": [0, 40],                                  before the frame at t, ask ownDrawnPosition(t + each);
//                                                      null (default): never ask
//     "usable": [2] or null,                           stations that may glow
//     "steps": [                                       in the order they happen
//       ["positions", t, [{"name", "x", "y"}, ...]]    a message arrives at time t (ms)
//       ["frame", t]                                   the browser draws a frame
//       ["key", t, "down" or "up", code]               a key of the keyboard, for example "KeyD"
//       ["pause", t, true or false]                    Game.world.setInputPaused(), as when a minigame opens
//       ["start_of_round", t]                          Game.world.startOfRound()
//       ["stop", t]                                    Game.world.stop()
//       ["start", t]                                   Game.world.start() again
//       ["numbers", t]                                 write down Game.world.bridgeNumbers()
//       ["refresh", t]                                 the panel's refresh timer runs; write down what the panel says
//       ["click", t, "Reset"]                          a click on the panel's button with this text
//     ]
//   }
// Output (stdout): JSON
//   {
//     "frames": [{t, camera: {x, y}, station, asked, characters: [{character, x, middleY, mirrored, stride, walkPhase}]}],
//                  one per frame drawn; `station` is Game.world.stationInRange() in that frame,
//                  `asked` the answers of ownDrawnPosition() asked before it
//     "moves": [[t, dx, dy], ...],                     what the world told the server, and when
//     "numbers": [...],                                one per "numbers" step
//     "panels": [...],                                 one text per "refresh" step
//     "bridge": Game.world.bridgeNumbers() at the end,
//     "diagnostic": Game.diagnostic.numbers() at the end, or null without `debug`
//     "report": Game.diagnostic.report() at the end, or null without `debug`
//     "exported": the names on Game.diagnostic
//   }

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const WORLD = path.join(__dirname, '..', 'client', 'js', 'world');
const CANVAS_WIDTH = 1280;
const CANVAS_HEIGHT = 800;

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const campus = JSON.parse(fs.readFileSync(path.join(WORLD, 'campus.json'), 'utf8'));

let clock = 0;
let frameCallbacks = []; // [{id, callback}] in the order they were requested
let lastFrameId = 0;
let current = null; // what the frame being drawn records
const frames = [];
const moves = [];
const numbers = [];
const panels = [];
const windowListeners = new Map(); // type -> [listener]
const netHandlers = new Map(); // type -> [handler]
const intervalTimers = []; // [{callback, delay}]

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
class FakeElement {
  constructor(tagName) {
    this.tagName = String(tagName).toUpperCase();
    this.style = {};
    this.children = [];
    this.listeners = {};
    this.textContent = '';
    this.disabled = true;
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  addEventListener(type, listener) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  remove() {}

  blur() {}

  all() {
    return [this].concat(...this.children.map((child) => child.all()));
  }
}

const body = new FakeElement('body');
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
  location: { search: input.search || '' },
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
  setInterval(callback, delay) {
    intervalTimers.push({ callback: callback, delay: delay });
    return intervalTimers.length;
  },
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
    body: body,
    createElement: (tagName) => new FakeElement(tagName),
    getElementById: (id) => (id === 'map' ? canvas : null),
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
    drawStationGlow: () => {},
    chooseLabels: (labels) => ({ shown: labels || [], hidden: new Set() }),
    drawCharacter: (ctx, character, x, middleY, size, pose) => {
      if (current) {
        current.characters.push({
          character: character,
          x: x,
          middleY: middleY,
          mirrored: pose.mirrored,
          stride: pose.stride,
          walkPhase: pose.walkPhase,
        });
      }
    },
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

// The order of index.html. `"bridge": false` is a page where bridge.js did not load.
if (input.bridge !== false) load('bridge.js');
load('world.js');
load('diagnostic.js');
const world = page.Game.world;
const diagnostic = page.Game.diagnostic;

function tell(type, message) {
  (netHandlers.get(type) || []).forEach((handler) => handler(message));
}

function sendMove(dx, dy) {
  moves.push([clock, dx, dy]);
}

// What the diagnostic's panel says below its title and buttons.
function panelText() {
  const parts = body.all().filter((element) => element.tagName === 'PRE');
  return parts.map((element) => element.textContent).join('\n');
}

const STEPS = {
  positions(t, players) {
    clock = t;
    // As in the lobby page: the world and the diagnostic both get the message.
    world.setPositions(players);
    tell('positions', { type: 'positions', players: players });
  },
  frame(t) {
    clock = t;
    const asked = (input.ask || []).map((later) => world.ownDrawnPosition(t + later));
    const waiting = frameCallbacks;
    frameCallbacks = [];
    current = { t: t, camera: null, station: null, asked: asked, characters: [] };
    // In the order they were requested: the diagnostic's callback runs first.
    waiting.forEach((entry) => entry.callback(t));
    current.station = world.stationInRange();
    if (current.camera) frames.push(current); // nothing is written down while the world is stopped
    current = null;
  },
  key(t, upOrDown, code) {
    clock = t;
    const event = { code: code, key: code, target: null, repeat: false, preventDefault() {} };
    (windowListeners.get('key' + upOrDown) || []).forEach((listener) => listener(event));
  },
  pause(t, paused) {
    clock = t;
    world.setInputPaused(paused);
  },
  start_of_round(t) {
    clock = t;
    world.startOfRound();
  },
  stop(t) {
    clock = t;
    world.stop();
  },
  start(t) {
    clock = t;
    world.start(canvas, sendMove);
  },
  numbers(t) {
    clock = t;
    numbers.push(world.bridgeNumbers());
  },
  refresh(t) {
    clock = t;
    intervalTimers.filter((timer) => timer.delay === 500).forEach((timer) => timer.callback());
    panels.push(panelText());
  },
  click(t, text) {
    clock = t;
    const button = body.all().find((element) => element.tagName === 'BUTTON' && element.textContent === text);
    button.listeners.click.forEach((listener) => listener({ target: button }));
  },
};

async function main() {
  world.setOwnName(input.own);
  tell('signed_in', { type: 'signed_in', name: input.own, guest: true });
  world.start(canvas, sendMove);
  world.setPlayers(input.players);
  world.setUsableStations(input.usable === undefined ? null : input.usable);
  // Let the map "download": fetch() and json() above are promises.
  await new Promise((resolve) => setImmediate(resolve));
  input.steps.forEach(([name, ...values]) => STEPS[name](...values));
  process.stdout.write(JSON.stringify({
    frames: frames,
    moves: moves,
    numbers: numbers,
    panels: panels,
    bridge: world.bridgeNumbers(),
    diagnostic: diagnostic.active ? diagnostic.numbers() : null,
    report: diagnostic.active ? diagnostic.report() : null,
    exported: Object.keys(diagnostic),
  }));
}

main();
