// The objects at the task stations and their pulsing outline (brief B,
// part 1). Runs the real art/common.js, art/stations.js and draw.js in Node
// with a canvas stand-in that writes down what is drawn.
// Run with: node game/tests/test_station_objects.js
// (pytest does it in tests/test_node_harnesses_area4.py).
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const world = path.join(__dirname, '..', 'client', 'js', 'world');
const campus = JSON.parse(fs.readFileSync(path.join(world, 'campus.json'), 'utf8'));
const OBJECT_STATIONS = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12];
const station = (id) => campus.stations.find((entry) => entry.id === id);

// A context that writes down translations, circles, texts and images. The
// small canvases draw.js makes for the outlines get one each, marked `offscreen`.
function recordingContext(calls, offscreen) {
  const state = { globalAlpha: 1 };
  return new Proxy(state, {
    get(target, key) {
      if (key === 'getTransform') return () => ({ a: 2, b: 0, c: 0, d: 2, e: 0, f: 0 });
      if (key === 'createLinearGradient' || key === 'createRadialGradient') return () => ({ addColorStop() {} });
      if (key === 'measureText') return (text) => ({ width: String(text).length * 3 });
      if (key === 'translate') return (x, y) => { if (!offscreen) calls.translations.push([x, y]); };
      if (key === 'arc') return (x, y, r) => { if (!offscreen) calls.arcs.push([x, y, r]); };
      if (key === 'fillText') return (text) => { if (!offscreen) calls.texts.push(String(text)); };
      if (key === 'drawImage') {
        return (image, x, y, w, h) => { if (!offscreen) calls.images.push({ image, x, y, w, h, alpha: target.globalAlpha }); };
      }
      if (key in target) return target[key];
      return () => {};
    },
    set(target, key, value) { target[key] = value; return true; },
  });
}

function page() {
  const made = [];
  const context = {
    console,
    document: {
      createElement: () => {
        const canvas = { width: 0, height: 0 };
        canvas.getContext = () => recordingContext({ translations: [], arcs: [], texts: [], images: [] }, true);
        made.push(canvas);
        return canvas;
      },
    },
  };
  context.window = context;
  vm.createContext(context);
  for (const file of ['art/common.js', 'art/stations.js', 'draw.js']) {
    vm.runInContext(fs.readFileSync(path.join(world, file), 'utf8'), context, { filename: file });
  }
  return { world: context.Game.world, made };
}

// The floor patterns are images too; an outline is a 40 by 40 unit square
// around its station (twice OBJECT_HALF_SIZE in draw.js).
const OUTLINE_SIZE = 40;

function draw(world, pulsing, now = 0) {
  const calls = { translations: [], arcs: [], texts: [], images: [] };
  world.drawMap(recordingContext(calls, false), campus, null, false, pulsing, now);
  calls.images = calls.images.filter((image) => image.w === OUTLINE_SIZE && image.h === OUTLINE_SIZE);
  return calls;
}

// Which stations got an outline: every outline is drawn as images of the
// square around its station.
function outlined(calls) {
  const centres = new Set(calls.images.map((image) => (image.x + image.w / 2) + ',' + (image.y + image.h / 2)));
  return campus.stations.filter((entry) => centres.has(entry.x + ',' + entry.y)).map((entry) => entry.id);
}

let checked = 0;
function check(condition, message) {
  assert.ok(condition, message);
  checked += 1;
}

// B1: eleven objects, always, each with its number; no old circle markers.
{
  const { world } = page();
  for (const pulsing of [[], null, [9]]) {
    const calls = draw(world, pulsing);
    for (const id of OBJECT_STATIONS) {
      const at = station(id);
      check(calls.translations.some(([x, y]) => x === at.x && y === at.y), 'station ' + id + ' has its object');
      check(calls.texts.includes(String(id)), 'station ' + id + ' keeps its number');
      check(!calls.arcs.some(([x, y, r]) => x === at.x && y === at.y && r === at.r), 'no marker circle at station ' + id);
    }
    const six = station(6);
    check(!calls.translations.some(([x, y]) => x === six.x && y === six.y) && !calls.texts.includes('6'),
      'station 6 is not in use and has no object');
  }
  for (const id of OBJECT_STATIONS) {
    check(typeof world.art.stations[id] === 'function', 'art/stations.js draws station ' + id);
  }
  check(!(6 in world.art.stations), 'no drawing for station 6');
}

// B2: only the stations that matter get the pulsing outline.
{
  const { world, made } = page();
  check(outlined(draw(world, [])).length === 0, 'the lobby (an empty list) outlines nothing');
  for (const wrong of [null, undefined, 7, '7', ['7'], {}, [999], [6]]) {
    check(outlined(draw(world, wrong)).length === 0, 'no outline for ' + JSON.stringify(wrong));
  }
  check(JSON.stringify(outlined(draw(world, [9]))) === '[9]', 'a Duel outlines only the next station');
  check(JSON.stringify(outlined(draw(world, [12]))) === '[12]', 'a new station can be the next one');
  check(JSON.stringify(outlined(draw(world, [1, 2, 3, 4, 5]))) === '[1,2,3,4,5]', 'a list of five outlines all five');
  check(JSON.stringify(outlined(draw(world, OBJECT_STATIONS))) === JSON.stringify(OBJECT_STATIONS),
    'Classic with eleven usable stations outlines all of them');
  // Four layers per outline: the dark edge and the yellow, narrow and wide.
  check(draw(world, [3], 700).images.length === 4, 'one outline at its widest is four images');
  // The silhouettes are made once and then kept.
  const before = made.length;
  draw(world, [1, 2, 3, 4, 5]);
  draw(world, [1, 2, 3, 4, 5], 700);
  check(made.length === before, 'no new canvases for the same stations at the same zoom');
  // It pulses: at the low point only the narrow outline is drawn, at the
  // high point the wide one too, and in between the wide one is see-through.
  check(draw(world, [3], 0).images.length === 2, 'at the low point only the narrow outline');
  check(draw(world, [3], 700).images.every((image) => image.alpha > 0.99), 'at the high point all of it, fully');
  const between = draw(world, [3], 350).images.map((image) => image.alpha);
  check(between.length === 4 && Math.min(...between) > 0.3 && Math.min(...between) < 0.7, 'half way it is half see-through');
}

// The station in range ("E Use"): the outline at full strength, the object on top.
{
  const { world } = page();
  const calls = { translations: [], arcs: [], texts: [], images: [] };
  world.drawStationGlow(recordingContext(calls, false), station(4), 0);
  check(calls.images.length === 4 && calls.images.every((image) => image.alpha === 1), 'the station in range is fully lit');
  check(calls.translations.some(([x, y]) => x === station(4).x && y === station(4).y) && calls.texts.includes('4'),
    'its object and number are drawn on top of the outline');
  const none = { translations: [], arcs: [], texts: [], images: [] };
  world.drawStationGlow(recordingContext(none, false), station(6), 0);
  world.drawStationGlow(recordingContext(none, false), null, 0);
  check(none.images.length === 0 && none.translations.length === 0, 'nothing for station 6 or no station');
}

// Without a page that can make canvases (a test in Node) the objects stay and no outline breaks.
{
  const context = { console };
  context.window = context;
  vm.createContext(context);
  for (const file of ['art/common.js', 'art/stations.js', 'draw.js']) {
    vm.runInContext(fs.readFileSync(path.join(world, file), 'utf8'), context, { filename: file });
  }
  const calls = draw(context.Game.world, [1, 2]);
  check(calls.images.length === 0 && calls.texts.includes('1'), 'no canvases: objects without outline');
}

// The room a point lies in, for the top-left card (exported for it).
{
  const { world } = page();
  const canteen = campus.rooms.find((room) => room.id === 'canteen');
  check(world.roomAt(campus, canteen.x + 5, canteen.y + 5) === canteen, 'roomAt finds the room');
  check(world.roomAt(campus, campus.spawn.x, campus.spawn.y) === null, 'the spawn lies on the deck: no room');
}

console.log('Station object checks passed: ' + checked + ' assertions.');
