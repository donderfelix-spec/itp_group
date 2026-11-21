// Runs the page's own js/world/draw.js in Node, without a browser, for
// test_room_labels_drawn.py (M1-1.6).
//
// The canvas is a stand-in that only writes down every text it is asked to
// draw; all other drawing calls do nothing. drawMap() is the real code.
//
// Input (stdin): the map, as JSON (normally the content of campus.json).
// Output (stdout): JSON list of every text drawn: {text, x, y, font}.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const DRAW_JS = path.join(__dirname, '..', 'client', 'js', 'world', 'draw.js');

function recordingCanvas(texts) {
  const state = {};
  const doNothing = () => canvas;
  const canvas = new Proxy(state, {
    get(target, key) {
      if (key === 'fillText') {
        return (text, x, y) => texts.push({ text: String(text), x, y, font: target.font });
      }
      if (key in target) return target[key];
      return doNothing; // save, beginPath, arc, fill, stroke, ...
    },
    set(target, key, value) {
      target[key] = value; // font, fillStyle, lineWidth, ...
      return true;
    },
  });
  return canvas;
}

const campus = JSON.parse(fs.readFileSync(0, 'utf8'));
// As in a browser, `window` is the global object itself, so draw.js finds
// `Game` both as `window.Game` and as a plain name.
const page = {};
page.window = page;
vm.runInNewContext(fs.readFileSync(DRAW_JS, 'utf8'), page, { filename: DRAW_JS });
const texts = [];
page.Game.world.drawMap(recordingCanvas(texts), campus);
process.stdout.write(JSON.stringify(texts));
