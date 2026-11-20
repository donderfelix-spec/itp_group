// Runs the page's own js/world/draw.js and js/world/world.js in Node, without
// a browser, for test_draw_without_characters.py (M1-1.11): what does the map
// draw when the character drawing is missing or fails?
//
// The canvas, the document, the window and the map download are small
// stand-ins. draw.js and world.js are the real code. Game.world.drawCharacter
// is a stand-in too, chosen by the argument:
//   "with-characters"     it works and writes down every character it draws
//   "without-characters"  it is missing, as when characters.js did not load
//   "failing-character"   it fails for the character "broken" halfway through
//                         its drawing (after save and translate), and works
//                         for every other character
//   "failing-nested"      the same, but it fails inside a second save of its
//                         own, after making the drawing see-through, as the
//                         helpers of characters.js do (drawShadow, drawFace)
//
// Input (stdin): JSON {"players": [{name, character, x, y}], "frames": N}.
//   The first player is the own player.
// Output (stdout): JSON with
//   warnings    every console.warn, as text
//   errors      every console.error and every error thrown by a frame
//   characters  every drawn character: {character, x, y} on the screen
//   standIns    every filled circle: {x, y, colour, alpha} on the screen
//   names       every player name drawn: {text, x, y, alpha} on the screen

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const WORLD = path.join(__dirname, '..', 'client', 'js', 'world');
const CANVAS_WIDTH = 800;
const CANVAS_HEIGHT = 600;
const FRAME_MILLISECONDS = 16;

const mode = process.argv[2];
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const campus = JSON.parse(fs.readFileSync(path.join(WORLD, 'campus.json'), 'utf8'));
const playerNames = new Set(input.players.map((player) => player.name));

const warnings = [];
const errors = [];
const characters = [];
const standIns = [];
const names = [];

// ---- A canvas that follows only scale, move and opacity ---------------
// Enough for world.js: the camera is a scale and a move, and so is the
// stand-in drawCharacter below. Every point drawn is written down where it
// lands on the screen. save() and restore() keep the transform and the
// opacity (globalAlpha), as a real canvas does.

let transform = { scale: 1, x: 0, y: 0 };
const state = { globalAlpha: 1 }; // fillStyle, font, globalAlpha, ...
const savedStates = [];
let lastArc = null;

function onScreen(x, y) {
  return { x: transform.x + x * transform.scale, y: transform.y + y * transform.scale };
}

const doesNothing = new Proxy(function () {}, {
  get: () => doesNothing,
  set: () => true,
  apply: () => doesNothing,
});

const contextMethods = {
  // Takes six numbers, or a transform from getTransform().
  setTransform(scale, b, c, d, x, y) {
    transform = typeof scale === 'object' ? { ...scale } : { scale, x, y };
  },
  getTransform() { return { ...transform }; },
  translate(x, y) { transform = { scale: transform.scale, ...onScreen(x, y) }; },
  scale(factor) { transform = { ...transform, scale: transform.scale * factor }; },
  save() { savedStates.push({ transform, alpha: state.globalAlpha }); },
  restore() {
    if (savedStates.length) {
      const saved = savedStates.pop();
      transform = saved.transform;
      state.globalAlpha = saved.alpha;
    }
  },
  beginPath() { lastArc = null; },
  arc(x, y) { lastArc = onScreen(x, y); },
  fill() {
    if (lastArc) standIns.push({ ...lastArc, colour: state.fillStyle, alpha: state.globalAlpha });
  },
  measureText(text) { return { width: String(text).length * 7 }; },
  fillText(text, x, y) {
    if (playerNames.has(text)) names.push({ text, ...onScreen(x, y), alpha: state.globalAlpha });
  },
};

const context = new Proxy(state, {
  get(target, key) {
    if (key in contextMethods) return contextMethods[key];
    if (key in target) return target[key]; // fillStyle, font, lineWidth, ...
    return doesNothing; // fillRect, stroke, moveTo, createLinearGradient, ...
  },
  set(target, key, value) {
    target[key] = value;
    return true;
  },
});

// ---- The page around the canvas ---------------------------------------

const canvas = {
  clientWidth: CANVAS_WIDTH,
  clientHeight: CANVAS_HEIGHT,
  width: 0,
  height: 0,
  getContext: () => context,
  parentNode: { appendChild() {} },
};

let nextFrame = null;
const page = {
  console: {
    warn: (...parts) => warnings.push(parts.map(String).join(' ')),
    error: (...parts) => errors.push(parts.map(String).join(' ')),
    log() {},
  },
  document: {
    hidden: false,
    activeElement: null,
    createElement: () => ({ addEventListener() {}, remove() {}, blur() {} }),
    addEventListener() {},
    removeEventListener() {},
  },
  devicePixelRatio: 1,
  performance: { now: () => 0 },
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve(campus) }),
  requestAnimationFrame: (callback) => { nextFrame = callback; return 1; },
  cancelAnimationFrame() {},
  setTimeout: () => 0,
  clearTimeout() {},
  addEventListener() {},
  removeEventListener() {},
};
page.window = page;
vm.createContext(page);
['draw.js', 'world.js'].forEach((file) => {
  const code = fs.readFileSync(path.join(WORLD, file), 'utf8');
  vm.runInContext(code, page, { filename: file });
});

// ---- The stand-in for characters.js -----------------------------------

function recordCharacter(ctx, characterId, x, y) {
  characters.push({ character: characterId, ...onScreen(x, y) });
}

if (mode === 'with-characters') {
  page.Game.world.drawCharacter = recordCharacter;
} else if (mode === 'failing-character') {
  page.Game.world.drawCharacter = (ctx, characterId, x, y) => {
    if (characterId !== 'broken') {
      recordCharacter(ctx, characterId, x, y);
      return;
    }
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(0.5);
    throw new Error('This drawing fails halfway.');
  };
} else if (mode === 'failing-nested') {
  page.Game.world.drawCharacter = (ctx, characterId, x, y) => {
    if (characterId !== 'broken') {
      recordCharacter(ctx, characterId, x, y);
      return;
    }
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(0.5);
    ctx.save(); // a helper inside the drawing, like drawShadow
    ctx.globalAlpha = 0.14;
    throw new Error('This drawing fails inside a second save.');
  };
} else if (mode !== 'without-characters') {
  throw new Error('Unknown mode: ' + mode);
}

// ---- Play ---------------------------------------------------------------

async function play() {
  const world = page.Game.world;
  world.start(canvas, () => {});
  await new Promise((resolve) => setImmediate(resolve)); // the map arrives
  world.setOwnName(input.players[0].name);
  world.setPlayers(input.players.map((player) => ({ name: player.name, character: player.character })));
  world.setPositions(input.players.map((player) => ({ name: player.name, x: player.x, y: player.y })));
  for (let frame = 1; frame <= input.frames; frame += 1) {
    // Only the last frame is written down; the others count warnings and errors.
    characters.length = 0;
    standIns.length = 0;
    names.length = 0;
    try {
      nextFrame(1000 + frame * FRAME_MILLISECONDS);
    } catch (problem) {
      errors.push(String(problem));
    }
  }
  process.stdout.write(JSON.stringify({ warnings, errors, characters, standIns, names }));
}

play();
