// The Classic arrow (M3-4.22): in Classic the arrow of
// client/js/minigames/task_navigation.js points at the nearest own open task.
// Run with: node game/tests/classic_arrow_in_node.js
// (pytest does it in tests/test_classic_arrow.py). It loads the real file in
// Node with a fake canvas context and a fake card; no browser is needed.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const client = path.join(__dirname, '..', 'client');
const campus = JSON.parse(fs.readFileSync(path.join(client, 'js', 'world', 'campus.json'), 'utf8'));
const source = fs.readFileSync(path.join(client, 'js', 'minigames', 'task_navigation.js'), 'utf8');

let checked = 0;
function expect(condition, message) {
  if (!condition) throw new Error(message);
  checked += 1;
}

// The card of index.html: the head and the task part.
const elements = {};
for (const id of ['task-card', 'task-card-here', 'task-card-task', 'task-card-kicker', 'task-card-room', 'task-card-title']) {
  elements[id] = { hidden: true, textContent: '', classList: { toggle() {} } };
}
const page = { console: console, document: { getElementById: (id) => elements[id] || null } };
page.window = page;
vm.createContext(page);
vm.runInContext(source, page);
const navigation = page.Game.taskNavigation;

// A fake context that notes every triangle: its angle and its alpha.
let arrows = [];
const ctx = new Proxy({
  rotate(angle) { arrows.push({ angle: angle, alpha: this.globalAlpha }); },
}, { get: (object, key) => key in object ? object[key] : function () {} });

function drawAt(position) {
  arrows = [];
  navigation.draw(ctx, campus, position, position, false);
  return arrows;
}

function station(id) {
  return campus.stations.find((entry) => entry.id === id);
}

function angleTo(from, id) {
  return Math.atan2(station(id).y - from.y, station(id).x - from.x);
}

// ---- nearestStation ---------------------------------------------------------

const a = station(1);
const b = station(2);
const nearA = { x: a.x + 10, y: a.y + 80 };
expect(navigation.nearestStation(campus, nearA, [2, 1]) === 1, 'The nearest station wins, wherever it is in the list');
expect(navigation.nearestStation(campus, nearA, [1, 2]) === 1, 'The nearest station wins at the start of the list too');
// Exactly between two stations: the first in the list wins.
const middle = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
expect(navigation.nearestStation(campus, middle, [2, 1]) === 2 && navigation.nearestStation(campus, middle, [1, 2]) === 1,
  'A tie goes to the first station in the list');
expect(navigation.nearestStation(campus, nearA, []) === null, 'An empty list has no nearest station');
expect(navigation.nearestStation(campus, nearA, [999]) === null, 'An unknown id is no station');
expect(navigation.nearestStation(campus, nearA, [999, 2]) === 2, 'An unknown id is skipped');
expect(navigation.nearestStation(campus, null, [1]) === null, 'Without a position there is no nearest station');
expect(navigation.nearestStation(campus, { x: NaN, y: 3 }, [1]) === null, 'A broken position has no nearest station');
expect(navigation.nearestStation(campus, nearA, null) === null, 'No list has no nearest station');

// ---- draw with a list (Classic) ---------------------------------------------

navigation.setTarget(null);
navigation.setTargets([2, 1]);
let drawn = drawAt(nearA);
expect(drawn.length === 1 && Math.abs(drawn[0].angle - angleTo(nearA, 1)) < 1e-9 && drawn[0].alpha === 1,
  'In Classic the arrow points at the nearest open task');
expect(!elements['task-card'].hidden && elements['task-card-task'].hidden && elements['task-card-kicker'].textContent === '',
  'In Classic the card shows only the room, no task');

// Station 1 finished: the arrow turns to the nearest remaining one.
navigation.setTargets([2]);
drawn = drawAt(nearA);
expect(drawn.length === 1 && Math.abs(drawn[0].angle - angleTo(nearA, 2)) < 1e-9,
  'After a finished station the arrow points at the nearest remaining one');

// Walking: chosen anew every frame.
navigation.setTargets([1, 2]);
const nearB = { x: b.x + 10, y: b.y + 80 };
drawn = drawAt(nearB);
expect(drawn.length === 1 && Math.abs(drawn[0].angle - angleTo(nearB, 2)) < 1e-9,
  'While walking the arrow switches to the station that is nearer now');

// The same fade as in Duel: 1 at 60 units and more, half at 50, gone at 40 and on arrival.
for (const [distance, alpha] of [[70, 1], [50, 0.5]]) {
  drawn = drawAt({ x: a.x, y: a.y + distance });
  expect(drawn.length === 1 && Math.abs(drawn[0].alpha - alpha) < 1e-9, 'The arrow fades like in Duel at ' + distance);
}
navigation.setTargets([1]);
expect(drawAt({ x: a.x, y: a.y + 40 }).length === 0, 'At 40 units the arrow is gone');
expect(drawAt({ x: a.x, y: a.y + 10 }).length === 0, 'On arrival at the nearest station there is no arrow');

// No open tasks (all done, a Free Rider): no arrow.
navigation.setTargets([]);
expect(drawAt(nearA).length === 0, 'Without open tasks there is no arrow');
navigation.setTargets(null);
expect(drawAt(nearA).length === 0, 'Without a list there is no arrow');

// A minigame open: nothing. Reset: the list is gone.
navigation.setTargets([1]);
arrows = [];
navigation.draw(ctx, campus, nearA, nearA, true);
expect(arrows.length === 0, 'While a minigame is open there is no arrow');
navigation.reset();
expect(drawAt(nearA).length === 0, 'Leaving the lobby forgets the list');

// Duel and Solo: one target, the card names the task, as before.
navigation.setTarget(2);
drawn = drawAt(nearA);
expect(drawn.length === 1 && Math.abs(drawn[0].angle - angleTo(nearA, 2)) < 1e-9 && !elements['task-card-task'].hidden
  && elements['task-card-kicker'].textContent === 'NEXT TASK', 'Duel and Solo keep one target and the NEXT TASK card');

console.log('Classic arrow checks passed: ' + checked + ' assertions.');
