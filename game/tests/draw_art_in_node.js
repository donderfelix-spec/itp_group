// Runs the page's own js/world/draw.js together with the art files of
// js/world/art/ in Node, without a browser, for test_campus_detail.py (M2-1.4).
//
// The art files are loaded in the order of their <script> tags in
// client/index.html, as in the page. The canvas is a stand-in that writes
// down texts and copied tiles; every other drawing call does nothing.
//
// Argument: the mode.
//   "direct"  no page (no `document`): the map is drawn straight onto the
//             canvas, as in the other Node tests. Output: {texts, warnings,
//             fills: every colour something was filled with, art: the names
//             each group of Game.world.art registers}. With "failingKind" in
//             the input, the art of that kind of solid throws an error;
//             with "failingDoor", the art of a door's opening does.
//   "tiles"   a page that can make canvases: drawMap() draws the static part
//             into tiles and copies them. Input (stdin): {"frames": [{scale,
//             e, f, width, height}]}, one camera per frame. Output: {frames:
//             [{copies: [{x, y}], newTiles, drawnAt: [{x, y}]}], warnings};
//             drawnAt is where each tile drawn in that frame lands on the
//             canvas, in the order they were drawn.
// Input (stdin) in both modes also has "campus": the map.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const CLIENT = path.join(__dirname, '..', 'client');
const WORLD = path.join(CLIENT, 'js', 'world');

const mode = process.argv[2];
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const texts = [];
const warnings = [];
const fills = new Set();

// A drawing context that does nothing but write down texts and copies.
function recordingContext(extra) {
  const state = {};
  const doNothing = () => undefined;
  return new Proxy(state, {
    get(target, key) {
      if (key === 'fillText') return (text, x, y) => texts.push({ text: String(text), x, y, font: target.font });
      if (key === 'fill' || key === 'fillRect') return () => fills.add(String(target.fillStyle));
      if (key === 'measureText') return (text) => ({ width: String(text).length * (parseFloat(target.font.replace('bold ', '')) || 10) * 0.6 });
      if (key === 'createRadialGradient' || key === 'createLinearGradient') return () => ({ addColorStop: doNothing });
      if (extra && key in extra) return extra[key];
      if (key in target) return target[key];
      return doNothing; // save, beginPath, arc, fill, stroke, ...
    },
    set(target, key, value) {
      target[key] = value;
      return true;
    },
  });
}

function artFiles() {
  const page = fs.readFileSync(path.join(CLIENT, 'index.html'), 'utf8');
  return [...page.matchAll(/<script src="js\/world\/(art\/[^"]+)"><\/script>/g)].map((match) => match[1]);
}

const page = { console: { warn: (...parts) => warnings.push(parts.map(String).join(' ')), log() {}, error() {} } };
page.window = page;

// For "tiles": a document whose canvases have recording contexts.
let newTiles = 0;
let drawnAt = [];
let camera = null; // the camera of the frame being drawn
if (mode === 'tiles') {
  page.document = {
    createElement(name) {
      if (name !== 'canvas') throw new Error('only canvases are made here');
      newTiles += 1;
      const tile = { width: 0, height: 0 };
      // draw.js moves a tile's drawing by minus its place from the map's corner.
      const setTransform = (a, b, c, d, e, f) => drawnAt.push({ x: Math.round(camera.e) - e, y: Math.round(camera.f) - f });
      tile.getContext = () => recordingContext({ canvas: tile, setTransform });
      return tile;
    },
  };
}

vm.createContext(page);
['draw.js'].concat(artFiles()).forEach((file) => {
  const code = fs.readFileSync(path.join(WORLD, file), 'utf8');
  vm.runInContext(code, page, { filename: file });
});
const world = page.Game.world;

if (mode === 'direct') {
  if (input.failingKind) {
    world.art.kinds[input.failingKind] = () => { throw new Error('This drawing fails.'); };
  }
  if (input.failingDoor) {
    world.art.doors.opening = () => { throw new Error('This drawing fails.'); };
  }
  world.drawMap(recordingContext(), input.campus);
  const art = {};
  Object.keys(world.art || {}).forEach((group) => {
    if (group !== 'util') art[group] = Object.keys(world.art[group]);
  });
  process.stdout.write(JSON.stringify({ texts, warnings, fills: [...fills], art }));
} else if (mode === 'tiles') {
  const frames = input.frames.map((frameCamera) => {
    camera = frameCamera;
    const copies = [];
    const screen = { width: camera.width, height: camera.height };
    let transform = { a: camera.scale, b: 0, c: 0, d: camera.scale, e: camera.e, f: camera.f };
    const ctx = recordingContext({
      canvas: screen,
      getTransform: () => ({ ...transform }),
      setTransform: (a, b, c, d, e, f) => { transform = { a, b, c, d, e, f }; },
      drawImage: (image, x, y) => copies.push({ x, y }),
    });
    newTiles = 0;
    drawnAt = [];
    world.drawMap(ctx, input.campus);
    return { copies, newTiles, drawnAt };
  });
  process.stdout.write(JSON.stringify({ frames, warnings }));
} else {
  throw new Error('Unknown mode: ' + mode);
}
