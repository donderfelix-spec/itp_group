// Runs Game.world.chooseLabels() from the page's own js/world/draw.js in
// Node, without a browser, for test_name_labels.py (M2-1.8).
//
// Input (stdin): JSON {"hiddenBefore": [names], "frames": [[label, ...], ...]}.
// Each frame is the list of labels in drawing order, each label
// {name, x, y, width, height, own}. "hiddenBefore" is optional and is the
// set of names hidden before the first frame. As in world.js, the names
// hidden in one frame are passed on to the next frame.
//
// Output (stdout): JSON list with one entry per frame:
// {"shown": [labels in the order chooseLabels returned them], "hidden": [sorted names]}.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const DRAW_JS = path.join(__dirname, '..', 'client', 'js', 'world', 'draw.js');

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
// As in a browser, `window` is the global object itself, so draw.js finds
// `Game` both as `window.Game` and as a plain name.
const page = {};
page.window = page;
vm.runInNewContext(fs.readFileSync(DRAW_JS, 'utf8'), page, { filename: DRAW_JS });

let hidden = new Set(input.hiddenBefore || []);
const results = input.frames.map((labels) => {
  const choice = page.Game.world.chooseLabels(labels, hidden);
  hidden = choice.hidden;
  return { shown: choice.shown, hidden: Array.from(choice.hidden).sort() };
});
process.stdout.write(JSON.stringify(results));
