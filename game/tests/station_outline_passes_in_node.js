// How much work draw.js does to make the pulsing outline of a station, at
// different zooms (M2-1.20). Runs the real art/common.js, art/stations.js
// and draw.js in Node with a canvas stand-in that counts every drawImage
// on the small canvases draw.js makes for the outlines.
//
// Usage: node station_outline_passes_in_node.js
// Reads from stdin {"stations": [{id, x, y}, ...], "zooms": [pixels per unit, ...]}.
// Prints {zoom: {id: {"copies": n, "canvases": n}}}: for each zoom and
// station, how many times a shape was copied (drawImage) to make its four
// outline layers, and how many canvases were made for them.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const world = path.join(__dirname, '..', 'client', 'js', 'world');

// A context that does nothing but count drawImage calls and say its zoom.
function countingContext(count, zoom) {
  const state = {};
  return new Proxy(state, {
    get(target, key) {
      if (key === 'getTransform') return () => ({ a: zoom, b: 0, c: 0, d: zoom, e: 0, f: 0 });
      if (key === 'drawImage') return () => { count.copies += 1; };
      if (key === 'measureText') return (text) => ({ width: String(text).length * 3 });
      if (key in target) return target[key];
      return () => {};
    },
    set(target, key, value) { target[key] = value; return true; },
  });
}

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const result = {};
for (const zoom of input.zooms) {
  result[zoom] = {};
  for (const station of input.stations) {
    // A fresh page for each count, so nothing is kept from before.
    const count = { copies: 0, canvases: 0 };
    const context = {
      console,
      document: {
        createElement: () => {
          count.canvases += 1;
          const canvas = { width: 0, height: 0 };
          canvas.getContext = () => countingContext(count, zoom);
          return canvas;
        },
      },
    };
    context.window = context;
    vm.createContext(context);
    for (const file of ['art/common.js', 'art/stations.js', 'draw.js']) {
      vm.runInContext(fs.readFileSync(path.join(world, file), 'utf8'), context, { filename: file });
    }
    // The page's own context: its drawImage calls (the finished layers) do
    // not count, only those on the outline canvases.
    const page = { copies: 0 };
    context.Game.world.drawStationGlow(countingContext(page, zoom), station);
    result[zoom][station.id] = count;
  }
}
console.log(JSON.stringify(result));
