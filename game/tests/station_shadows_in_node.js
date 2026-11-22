// Where draw.js puts the soft shadow below a station's object (M2-1.20).
// Runs the real art/common.js, art/stations.js and draw.js in Node with a
// canvas stand-in that writes down every ellipse 11 by 3.5 units (the
// shadow's size) at its place on the map.
//
// Usage: node station_shadows_in_node.js
// Reads from stdin {"stations": [{id, x, y}, ...], "shadows": {id: value}}:
// `shadows` sets `shadow` on the drawing of that station before drawing
// ("default" takes the property away). Prints {id: [[x, y], ...]}, the
// shadows drawn for each station.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const world = path.join(__dirname, '..', 'client', 'js', 'world');

// A context that keeps track of translate, save and restore, and writes
// down the ellipses of the shadow's size.
function recordingContext(shadows) {
  let offset = { x: 0, y: 0 };
  const saved = [];
  const state = {};
  return new Proxy(state, {
    get(target, key) {
      if (key === 'save') return () => saved.push({ ...offset });
      if (key === 'restore') return () => { offset = saved.pop() || { x: 0, y: 0 }; };
      if (key === 'translate') return (x, y) => { offset = { x: offset.x + x, y: offset.y + y }; };
      if (key === 'ellipse') {
        return (x, y, radiusX, radiusY) => {
          if (radiusX === 11 && radiusY === 3.5) shadows.push([offset.x + x, offset.y + y]);
        };
      }
      if (key === 'measureText') return (text) => ({ width: String(text).length * 3 });
      if (key in target) return target[key];
      return () => {};
    },
    set(target, key, value) { target[key] = value; return true; },
  });
}

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = { console };
context.window = context;
vm.createContext(context);
for (const file of ['art/common.js', 'art/stations.js', 'draw.js']) {
  vm.runInContext(fs.readFileSync(path.join(world, file), 'utf8'), context, { filename: file });
}
const drawings = context.Game.world.art.stations;
for (const [id, value] of Object.entries(input.shadows || {})) {
  if (value === 'default') delete drawings[id].shadow;
  else drawings[id].shadow = value;
}
const result = {};
for (const station of input.stations) {
  const shadows = [];
  context.Game.world.drawStationGlow(recordingContext(shadows), station);
  result[station.id] = shadows;
}
console.log(JSON.stringify(result));
