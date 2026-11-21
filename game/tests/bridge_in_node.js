// Runs the page's own js/world/bridge.js in Node, without a browser, for
// test_bridge_rule.py (M2-1.16). bridge.js holds only plain functions, so
// there is nothing to stand in for: no page, no canvas, no clock.
//
// Input (stdin): JSON {calls, steps}
//   calls   [[name, ...arguments]]: functions of Game.world.bridge to call.
//           An argument that is an object with "campus": "real" gets the
//           real map of the game (client/js/world/campus.json) instead.
//           The script also checks that a call left its arguments as they
//           were (output `changedArguments`: the names of calls that did not).
//   steps   [[x, y, dx, dy, seconds], ...]: each is one call of step() on
//           the real map, as the server makes it.
// Output (stdout): JSON {results, changedArguments, steps, exported}
//   results   what each call returned; a call that threw gives {"threw": message}
//   steps     [[x, y], ...]: the result of each step
//   exported  the names on Game.world.bridge

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const WORLD = path.join(__dirname, '..', 'client', 'js', 'world');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const campus = JSON.parse(fs.readFileSync(path.join(WORLD, 'campus.json'), 'utf8'));

const page = { console: console };
page.window = page;
vm.createContext(page);
const file = path.join(WORLD, 'bridge.js');
vm.runInContext(fs.readFileSync(file, 'utf8'), page, { filename: file });
const bridge = page.Game.world.bridge;

function withRealCampus(value) {
  if (value && typeof value === 'object' && value.campus === 'real') {
    return Object.assign({}, value, { campus: campus });
  }
  return value;
}

const changedArguments = [];
const results = (input.calls || []).map(([name, ...values]) => {
  const before = JSON.stringify(values);
  let result;
  try {
    result = bridge[name](...values.map(withRealCampus));
  } catch (problem) {
    result = { threw: problem.message };
  }
  if (JSON.stringify(values) !== before) changedArguments.push(name);
  return result === undefined ? null : result;
});

const steps = (input.steps || []).map(([x, y, dx, dy, seconds]) => {
  const place = bridge.step(x, y, dx, dy, seconds, campus.solids, campus.width, campus.height);
  return [place.x, place.y];
});

process.stdout.write(JSON.stringify({
  results: results,
  changedArguments: changedArguments,
  steps: steps,
  exported: Object.keys(bridge),
}));
