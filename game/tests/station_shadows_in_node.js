// Where draw.js puts the soft shadow and the number tag of a station's
// object, and how wide the lines of each drawing are (M2-1.20). Runs the
// real art/common.js, art/stations.js and draw.js in Node with a canvas
// stand-in that writes down what is drawn.
//
// Usage: node station_shadows_in_node.js
// Reads from stdin {"stations": [{id, x, y}, ...], "shadows": {id: value},
// "tags": {id: value}}: `shadows` and `tags` set `shadow` and `tag` on the
// drawing of that station before drawing ("default" takes the property
// away). Prints {id: {shadows, tags, strokes}}:
//   shadows  every shadow drawn, as [x, y, w] on the map (the top left corner
//            and the width of the shadow's first band, the colour of
//            shadowBelow in art/common.js)
//   tags     every number tag drawn, as [x, y] on the map (its middle)
//   strokes  every line the drawing itself strokes, as [width, colour],
//            the width on the map (the drawing's own scaling included)
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const world = path.join(__dirname, '..', 'client', 'js', 'world');
const SHADOW_COLOUR = 'rgba(46, 42, 59, 0.10)';
const TAG_RADIUS = 3.5;

// A context that keeps track of translate, scale, save and restore, and
// writes down the shadows, the tags and the strokes.
function recordingContext(found) {
  let place = { x: 0, y: 0, scale: 1 };
  const saved = [];
  const state = {};
  return new Proxy(state, {
    get(target, key) {
      if (key === 'save') return () => saved.push({ ...place });
      if (key === 'restore') return () => { place = saved.pop() || { x: 0, y: 0, scale: 1 }; };
      if (key === 'translate') {
        return (x, y) => { place = { ...place, x: place.x + x * place.scale, y: place.y + y * place.scale }; };
      }
      if (key === 'scale') return (factor) => { place = { ...place, scale: place.scale * factor }; };
      if (key === 'fillRect') {
        return (x, y, w) => {
          if (target.fillStyle === SHADOW_COLOUR) {
            found.shadows.push([place.x + x * place.scale, place.y + y * place.scale, w * place.scale]);
          }
        };
      }
      if (key === 'arc') {
        return (x, y, radius) => {
          if (radius === TAG_RADIUS) found.tags.push([place.x + x * place.scale, place.y + y * place.scale]);
        };
      }
      if (key === 'stroke') return () => found.strokes.push([target.lineWidth * place.scale, target.strokeStyle]);
      if (key === 'measureText') return (text) => ({ width: String(text).length * 3 });
      if (key in target) return target[key];
      return () => {};
    },
    set(target, key, value) { target[key] = value; return true; },
  });
}

// Sets or takes away `name` on the drawings, as the input says.
function change(drawings, values, name) {
  for (const [id, value] of Object.entries(values || {})) {
    if (value === 'default') delete drawings[id][name];
    else drawings[id][name] = value;
  }
}

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = { console };
context.window = context;
vm.createContext(context);
for (const file of ['art/common.js', 'art/stations.js', 'draw.js']) {
  vm.runInContext(fs.readFileSync(path.join(world, file), 'utf8'), context, { filename: file });
}
const drawings = context.Game.world.art.stations;
change(drawings, input.shadows, 'shadow');
change(drawings, input.tags, 'tag');
const result = {};
for (const station of input.stations) {
  const drawn = { shadows: [], tags: [], strokes: [] };
  context.Game.world.drawStationGlow(recordingContext(drawn), station);
  // The lines of the drawing alone (the tag's ring belongs to draw.js).
  const alone = { shadows: [], tags: [], strokes: [] };
  drawings[station.id](recordingContext(alone));
  result[station.id] = { shadows: drawn.shadows, tags: drawn.tags, strokes: alone.strokes };
}
console.log(JSON.stringify(result));
