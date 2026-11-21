// The task navigator (client/js/minigames/task_navigation.js) and its hooks
// in world.js and draw.js. Run with: node game/tests/test_task_navigation.js
// (pytest does it in tests/test_node_harnesses_area4.py). The runner at the
// end loads the real files; no browser, server or package is needed.
function testTaskNavigation(navigation, campus) {
  let checked = 0;
  function expect(condition, message) {
    if (!condition) throw new Error(message);
    checked += 1;
  }
  const original = JSON.stringify(campus);
  const navigator = navigation.create(campus);
  const destinations = campus.stations;

  function assertRoute(start, target) {
    const route = navigator.route(start, target.id);
    expect(route !== null, 'Missing route to station ' + target.id);
    expect(route.station === target.id, 'Route points to wrong task');
    expect(route.path.length > 0, 'A route needs a position');
    expect(route.distance >= 0 && Number.isFinite(route.distance), 'Distance must be finite');
    for (let index = 1; index < route.path.length; index += 1) {
      expect(navigator.segmentIsFree(route.path[index - 1], route.path[index]), 'Route cuts through furniture or a wall');
    }
    if (!route.arrived) {
      expect(navigator.segmentIsFree(start, route.waypoint), 'Arrow points through an obstacle');
      const last = route.path[route.path.length - 1];
      expect(Math.hypot(last.x - target.x, last.y - target.y) <= campus.use_range,
        'Route ends outside the station use range');
      const arrival = navigator.route(last, target.id);
      expect(arrival.arrived && arrival.distance === 0, 'Arrival should show E Use');
    }
    return route;
  }

  // Every task is reachable from spawn and from every other room, including
  // every original and newly added room station, without changing routes.
  for (const target of destinations) {
    const first = assertRoute(campus.spawn, target);
    expect(first.room === (target.room === 'deck' ? 'Main Deck' : campus.rooms.find((room) => room.id === target.room).name),
      'Navigator room label is wrong');
    const end = first.path[first.path.length - 1];
    for (const other of destinations) assertRoute(end, other);
  }

  // A route to the library must go around the pool/long wall and use the
  // doorway, rather than point straight across the wall into the room.
  const library = destinations.find((station) => station.id === 4);
  const libraryRoute = assertRoute(campus.spawn, library);
  expect(libraryRoute.path.some((point) => point.x >= 75 && point.x <= 105 && point.y >= 222 && point.y <= 240),
    'Library route misses its only doorway');
  expect(libraryRoute.distance > Math.hypot(library.x - campus.spawn.x, library.y - campus.spawn.y),
    'Library distance ignores the walls');

  // Invalid/unassigned targets and blocked/nonfinite positions show no route.
  expect(navigator.route(campus.spawn, null) === null, 'No task must mean no route');
  expect(navigator.route(campus.spawn, 999) === null, 'Unknown task must mean no route');
  expect(navigator.route(null, 1) === null, 'No player position must mean no route');
  expect(navigator.route({ x: NaN, y: 200 }, 1) === null, 'NaN position must be rejected');
  const wall = campus.solids[0];
  expect(navigator.route({ x: wall.x + 1, y: wall.y + 1 }, 1) === null, 'Blocked position must be rejected');
  expect(JSON.stringify(campus) === original, 'Navigation must never change the authoritative map');

  // Same collision semantics as the server: touching a solid is allowed,
  // but a diagonal segment across its expanded corner is not.
  const tiny = navigation.create({ width: 100, height: 100, rooms: [],
    solids: [{ x: 40, y: 40, w: 20, h: 20 }], stations: [{ id: 1, x: 80, y: 80, room: 'deck', name: 'Test' }], use_range: 10 });
  expect(tiny.isFree(35, 50), 'Touching a solid should be allowed');
  expect(!tiny.isFree(35.01, 50), 'Overlapping a solid should be rejected');
  expect(tiny.segmentIsFree({ x: 35, y: 35 }, { x: 35, y: 65 }), 'Walking along an edge should be allowed');
  expect(!tiny.segmentIsFree({ x: 30, y: 50 }, { x: 50, y: 30 }), 'Diagonal corner cut should be rejected');
  const around = tiny.route({ x: 20, y: 20 }, 1);
  expect(around !== null && around.path.length > 2, 'Obstacle must be walked around');
  for (let index = 1; index < around.path.length; index += 1) {
    expect(tiny.segmentIsFree(around.path[index - 1], around.path[index]), 'Small-map route cuts a corner');
  }
  return { assertions: checked, targets: destinations.length, routes: destinations.length * (destinations.length + 1) + 1 };
}


// drawMap draws exactly the stations it is given (world.js gives the ones
// the player may use now) and never one of another player's task.
// All non-station map details remain independently drawn by the real renderer.
function testTaskStationVisibility(drawMap) {
  const stations = [{ id: 1, room: 'lecture-hall', x: 30, y: 40 },
    { id: 7, room: 'lecture-hall', x: 80, y: 40 }];
  const map = { width: 100, height: 100, colours: {}, stations: stations };
  let checked = 0;
  // Where the yellow circles of the stations are drawn.
  function drawn(shown) {
    const circles = [];
    const ctx = new Proxy({ arc: function (x, y) { circles.push([x, y]); } }, {
      get: function (target, key) { return key in target ? target[key] : function () {}; }
    });
    drawMap(ctx, map, null, false, shown); // no emergency button
    return JSON.stringify(circles);
  }
  function expect(condition, message) {
    if (!condition) throw new Error(message);
    checked += 1;
  }
  expect(drawn([7]) === '[[80,40]]', 'Only the assigned new station may be drawn');
  expect(drawn([1]) === '[[30,40]]', 'Only the assigned original station may be drawn');
  // Classic: several usable stations are all drawn, never none (brief A).
  expect(drawn([1, 7]) === '[[30,40],[80,40]]', 'Every usable station must be drawn');
  for (const absent of [undefined, null, 7, 999, '7', [], [999], ['7']]) {
    expect(drawn(absent) === '[]', 'No assignment must show no task markers');
  }
  return { assertions: checked };
}


// Live guidance is a direct compass, not a walking route. In particular a
// wall between the character and station must not redirect its arrow.
function testDirectTaskNavigator(navigation, campus) {
  let checked = 0;
  function expect(condition, message) {
    if (!condition) throw new Error(message);
    checked += 1;
  }
  const target = campus.stations.find((station) => station.id === 4);
  const position = campus.spawn;
  const direct = navigation.directGuidance(campus, position, target.id);
  const expected = Math.atan2(target.y - position.y, target.x - position.x);
  const mapCheck = navigation.create(campus);
  expect(!mapCheck.segmentIsFree(position, target), 'This test needs a wall between player and task');
  expect(direct.angle === expected, 'Compass must point directly through the wall towards the task');
  expect(direct.target.x === target.x && direct.target.y === target.y, 'Compass needs the actual station centre');
  expect(!('path' in direct), 'Live guidance must not calculate a route');

  function record() {
    const calls = { translations: [], rotations: [], texts: [], lines: [], rectangles: [] };
    const ctx = new Proxy({
      translate: (x, y) => calls.translations.push([x, y]),
      rotate: (angle) => calls.rotations.push(angle),
      fillText: (text) => calls.texts.push(text),
      lineTo: (x, y) => calls.lines.push([x, y]),
      fillRect: (x, y, width, height) => calls.rectangles.push([x, y, width, height]),
      measureText: (text) => ({ width: text.length * 6 }),
      setLineDash: () => { throw new Error('The compass must not draw a trail'); }
    }, { get: (object, key) => key in object ? object[key] : function () {} });
    return { ctx: ctx, calls: calls };
  }
  const compass = record();
  navigation.drawArrow(compass.ctx, direct, position);
  expect(compass.calls.translations.length === 1, 'Only one near-player arrow should be drawn');
  expect(compass.calls.rotations[0] === expected, 'Rendered arrow points at a waypoint instead of the target');
  const placed = compass.calls.translations[0];
  expect(Math.abs(Math.hypot(placed[0] - position.x, placed[1] - position.y) - 21) < 1e-8,
    'Compass must stay beside the player');
  expect(compass.calls.lines.length === 3, 'Only arrow vertices may be drawn, no route line');

  const close = { x: target.x + 1, y: target.y };
  const arrived = navigation.directGuidance(campus, close, target.id);
  const nearby = record();
  navigation.drawArrow(nearby.ctx, arrived, close);
  expect(arrived.arrived && nearby.calls.translations.length === 1, 'Arrow must remain visible inside the use range');
  expect(nearby.calls.rotations[0] === Math.PI, 'Nearby compass must still point at the target centre');
  const exactlyThere = record();
  navigation.drawArrow(exactlyThere.ctx, navigation.directGuidance(campus, target, target.id), target);
  expect(exactlyThere.calls.translations.length === 0, 'A zero-length direction should hide the arrow');

  const moved = { x: position.x - 20, y: position.y + 30 };
  const changed = navigation.directGuidance(campus, moved, 9);
  const changedTarget = campus.stations.find((station) => station.id === 9);
  expect(changed.angle === Math.atan2(changedTarget.y - moved.y, changedTarget.x - moved.x),
    'Compass must update when the player or current task changes');
  const hidden = record();
  navigation.drawArrow(hidden.ctx, null, position);
  expect(hidden.calls.translations.length === 0 && navigation.cardLines(null) === null,
    'No task must hide the compass and its card');
  for (const id of [null, undefined, 999]) expect(navigation.directGuidance(campus, position, id) === null, 'No assignment should mean no live guidance');
  expect(navigation.directGuidance(campus, { x: NaN, y: 0 }, target.id) === null, 'Invalid position must hide guidance');

  // The card is now an element of the page (#task-card); these are its lines.
  const card = navigation.cardLines(direct);
  expect(card.length === 3, 'The task card should have three lines');
  expect(card.includes('CTT Student Hall') && card.includes(target.name), 'Room and task must remain visible');
  expect(card.every((text) => !/trail|steps|about/i.test(text)), 'Trail and distance instructions must be removed');
  expect(card.every((text) => typeof text === 'string' && text.length > 0), 'The shorter task card should not retain a blank instruction row');
  expect(navigation.cardLines(arrived)[0].includes('E Use'), 'Arrival should still explain how to open the task');
  return { assertions: checked };
}

// A new server position may already be in range while its queued drawing
// is still outside. The card and Use button follow the server; the arrow
// stays beside the smoothly drawn character. Runs the real world.js and the
// real task_navigation.js; only the drawing of the map is a stand-in.
async function testWorldTaskArrival(vm, worldSource, navigationSource, campus) {
  let checked = 0;
  function expect(condition, message) {
    if (!condition) throw new Error(message);
    checked += 1;
  }
  let now = 0;
  let nextFrame = null;
  let shownStations = null;
  let glowingStation = null;
  let navigationCall = null; // the arguments of the last Game.taskNavigation.draw
  let arrowPlaces = []; // ctx.translate during that call: only the arrow does it
  let insideNavigation = false;
  const labels = { 'aria-label': 'Campus map' };
  const target = campus.stations.find((station) => station.id === 8);
  const button = { disabled: true, addEventListener() {}, remove() {}, blur() {} };
  const ctx = new Proxy({
    measureText: (text) => ({ width: text.length * 3 }),
    translate: (x, y) => { if (insideNavigation) arrowPlaces.push({ x: x, y: y }); },
  }, { get: (object, key) => key in object ? object[key] : function () {} });
  const canvas = { clientWidth: 1000, clientHeight: 700, width: 1000, height: 700,
    getContext: () => ctx, parentNode: { appendChild() {} },
    setAttribute: (key, value) => { labels[key] = value; }, getAttribute: (key) => labels[key] };
  // The card of index.html: one element and its three lines.
  const elements = {};
  for (const id of ['task-card', 'task-card-kicker', 'task-card-room', 'task-card-title']) {
    const classes = new Set();
    elements[id] = { hidden: true, textContent: '', classList: {
      toggle: (name, on) => { if (on) classes.add(name); else classes.delete(name); },
      contains: (name) => classes.has(name) } };
  }
  const card = elements['task-card'];
  const page = { console: console, devicePixelRatio: 1,
    performance: { now: () => now }, requestAnimationFrame: (callback) => { nextFrame = callback; return 1; },
    cancelAnimationFrame: () => {}, setTimeout: () => 0, clearTimeout: () => {},
    addEventListener: () => {}, removeEventListener: () => {},
    fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve(campus) }),
    document: { hidden: false, activeElement: null, createElement: () => button,
      getElementById: (id) => elements[id] || null,
      addEventListener: () => {}, removeEventListener: () => {} } };
  page.window = page;
  page.Game = { world: {
    drawMap(context, map, view, emergencyVisible, shown) { shownStations = shown; },
    drawStationGlow(context, station) { glowingStation = station.id; },
    drawCharacter() {},
    chooseLabels: (entries) => ({ shown: entries, hidden: new Set() }),
  } };
  vm.createContext(page);
  vm.runInContext(navigationSource, page);
  vm.runInContext(worldSource, page);
  const navigation = page.Game.taskNavigation;
  const realDraw = navigation.draw;
  navigation.draw = (...values) => {
    navigationCall = values;
    arrowPlaces = [];
    insideNavigation = true;
    try { realDraw(...values); } finally { insideNavigation = false; }
  };
  const world = page.Game.world;
  world.setOwnName('Mara');
  world.start(canvas, () => {});
  world.setPlayers([{ name: 'Mara', character: 'consultant' }]);
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
  world.setUsableStations([target.id]);
  navigation.setTarget(target.id);
  world.setPositions([{ name: 'Mara', x: target.x, y: target.y + 26 }]);
  nextFrame(now);
  now = 66;
  world.setPositions([{ name: 'Mara', x: target.x, y: target.y + 20 }]);
  nextFrame(now);
  const [, , drawnPosition, serverPosition, paused] = navigationCall;
  expect(serverPosition.y === target.y + 20, 'Arrival guidance must use the latest authoritative server position');
  expect(!card.hidden && elements['task-card-kicker'].textContent.includes('E Use')
    && card.classList.contains('task-card-arrived') && !button.disabled && world.stationInRange() === target.id,
    'Card, button and server range must agree while the drawing is queued');
  expect(elements['task-card-room'].textContent === 'Mon Café' && elements['task-card-title'].textContent === target.name,
    'The card names the room and the task');
  expect(drawnPosition.y !== serverPosition.y && paused === false, 'The test needs a queued drawing behind the server');
  const drawn = world.ownDrawnPosition(now);
  expect(drawnPosition.x === drawn.x && drawnPosition.y === drawn.y, 'Arrow must follow the drawn position');
  expect(arrowPlaces.length === 1 && Math.abs(Math.hypot(arrowPlaces[0].x - drawn.x, arrowPlaces[0].y - drawn.y) - 21) < 1e-8,
    'Arrow must be drawn beside the drawn character');
  world.setInputPaused(true);
  nextFrame(now + 1);
  expect(arrowPlaces.length === 0 && card.hidden, 'An open minigame must hide navigation');
  world.setInputPaused(false);
  nextFrame(now + 2);
  expect(arrowPlaces.length === 1 && !card.hidden, 'Closing the minigame shows the navigation again');
  navigation.setTarget(null);
  expect(card.hidden, 'No navigator target hides the card at once, also when no frame follows');
  nextFrame(now + 3);
  expect(arrowPlaces.length === 0 && card.hidden && labels['aria-label'] === 'Campus map',
    'No navigator target must hide guidance and reset its accessible label');
  expect(JSON.stringify(shownStations) === JSON.stringify([target.id]) && !button.disabled,
    'A sole private usable station must remain visible without the optional navigator API');
  for (const usable of [[], null]) {
    world.setUsableStations(usable);
    nextFrame(now + 4);
    expect(!Array.isArray(shownStations) || shownStations.length === 0, 'Without usable stations no marker is drawn');
  }
  world.setUsableStations([]);
  glowingStation = null;
  nextFrame(now + 5);
  expect(glowingStation === null && button.disabled, 'Without usable stations nothing glows and Use is off');
  // Classic: several usable stations are all drawn, and the one in range glows.
  world.setUsableStations([target.id, 7]);
  glowingStation = null;
  nextFrame(now + 6);
  expect(JSON.stringify(shownStations) === JSON.stringify([target.id, 7]) && glowingStation === target.id && !button.disabled,
    'Several usable stations must all be drawn, never none');
  world.stop();
  return { assertions: checked };
}

// ---- The runner -------------------------------------------------------------

if (require.main === module) {
  const fs = require('node:fs');
  const path = require('node:path');
  const vm = require('node:vm');
  const client = path.join(__dirname, '..', 'client');
  const campus = JSON.parse(fs.readFileSync(path.join(client, 'js', 'world', 'campus.json'), 'utf8'));
  const navigationSource = fs.readFileSync(path.join(client, 'js', 'minigames', 'task_navigation.js'), 'utf8');
  const worldSource = fs.readFileSync(path.join(client, 'js', 'world', 'world.js'), 'utf8');
  const drawSource = fs.readFileSync(path.join(client, 'js', 'world', 'draw.js'), 'utf8');

  // The real task_navigation.js and draw.js, each in a page of its own.
  function load(sources) {
    const page = { console: console, devicePixelRatio: 1, document: { getElementById: () => null } };
    page.window = page;
    vm.createContext(page);
    sources.forEach((source) => vm.runInContext(source, page));
    return page.Game;
  }
  const navigation = load([navigationSource]).taskNavigation;
  const drawMap = load([drawSource]).world.drawMap;

  (async () => {
    const results = [
      testTaskNavigation(navigation, campus),
      testTaskStationVisibility(drawMap),
      testDirectTaskNavigator(navigation, campus),
      await testWorldTaskArrival(vm, worldSource, navigationSource, campus),
    ];
    const assertions = results.reduce((sum, result) => sum + result.assertions, 0);
    console.log('Task navigation checks passed: ' + assertions + ' assertions.');
  })().catch((problem) => {
    console.error(problem);
    process.exit(1);
  });
}
