// Run with the browser JS runtime (or Node vm) after navigation.js has been
// loaded: testTaskNavigation(Game.world.navigation, parsedCampusMap).
// No browser, server, package or drawing stubs are needed for the route rules.
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


// drawMap must never reveal stations belonging to another player's task.
// All non-station map details remain independently drawn by the real renderer.
function testTaskStationVisibility(drawMap) {
  const stations = [{ id: 1, room: 'lecture-hall', x: 30, y: 40 },
    { id: 7, room: 'lecture-hall', x: 80, y: 40 }];
  const map = { width: 100, height: 100, colours: {}, stations: stations };
  let checked = 0;
  function drawn(id) {
    const translates = [];
    const ctx = new Proxy({ translate: function (x, y) { translates.push([x, y]); } }, {
      get: function (target, key) { return key in target ? target[key] : function () {}; }
    });
    drawMap(ctx, map, null, id);
    return JSON.stringify(translates);
  }
  function expect(condition, message) {
    if (!condition) throw new Error(message);
    checked += 1;
  }
  expect(drawn(7) === '[[80,40]]', 'Only the assigned new station may be drawn');
  expect(drawn(1) === '[[30,40]]', 'Only the assigned original station may be drawn');
  for (const absent of [undefined, null, 999, '7', [1, 7]]) {
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
  navigation.drawOverlay(hidden.ctx, null, '', { width: 800 });
  expect(hidden.calls.translations.length === 0 && hidden.calls.texts.length === 0,
    'No task must hide the compass and its card');
  for (const id of [null, undefined, 999]) expect(navigation.directGuidance(campus, position, id) === null, 'No assignment should mean no live guidance');
  expect(navigation.directGuidance(campus, { x: NaN, y: 0 }, target.id) === null, 'Invalid position must hide guidance');

  const card = record();
  navigation.drawOverlay(card.ctx, direct, target.name, { width: 800 });
  expect(card.calls.texts.length === 3, 'The task card should have three lines');
  expect(card.calls.texts.includes('CTT Student Hall') && card.calls.texts.includes(target.name), 'Room and task must remain visible');
  expect(card.calls.texts.every((text) => !/trail|steps|about/i.test(text)), 'Trail and distance instructions must be removed');
  expect(card.calls.rectangles.every((rect) => rect[3] === 74), 'The shorter task card should not retain a blank instruction row');
  const arrivalCard = record();
  navigation.drawOverlay(arrivalCard.ctx, arrived, target.name, { width: 800 });
  expect(arrivalCard.calls.texts[0].includes('E Use'), 'Arrival should still explain how to open the task');
  return { assertions: checked };
}

// A new server position may already be in range while its queued drawing
// is still outside. The card and Use button follow the server; the arrow
// stays beside the smoothly drawn character.
async function testWorldTaskArrival(vm, worldSource, navigation, campus) {
  let checked = 0;
  function expect(condition, message) {
    if (!condition) throw new Error(message);
    checked += 1;
  }
  let now = 0;
  let nextFrame = null;
  let arrow = null;
  let overlay = null;
  let readPosition = null;
  let visibleStation = null;
  let glowingStation = null;
  const labels = {};
  const target = campus.stations.find((station) => station.id === 8);
  const button = { disabled: true, addEventListener() {}, remove() {}, blur() {} };
  const ctx = new Proxy({ measureText: (text) => ({ width: text.length * 3 }) }, {
    get: (object, key) => key in object ? object[key] : function () {}
  });
  const canvas = { clientWidth: 1000, clientHeight: 700, width: 1000, height: 700,
    getContext: () => ctx, parentNode: { appendChild() {} },
    setAttribute: (key, value) => { labels[key] = value; }, getAttribute: (key) => labels[key] };
  const page = { console: console, devicePixelRatio: 1,
    performance: { now: () => now }, requestAnimationFrame: (callback) => { nextFrame = callback; return 1; },
    cancelAnimationFrame: () => {}, setTimeout: () => 0, clearTimeout: () => {},
    addEventListener: () => {}, removeEventListener: () => {},
    fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve(campus) }),
    document: { hidden: false, activeElement: null, createElement: () => button,
      addEventListener: () => {}, removeEventListener: () => {} } };
  page.window = page;
  page.Game = { world: {
    drawMap(context, map, view, id) { visibleStation = id; },
    drawStationGlow(context, station) { glowingStation = station.id; },
    drawCharacter() {},
    chooseLabels: (entries) => ({ shown: entries, hidden: new Set() }),
    navigation: {
      directGuidance: (map, position, station) => {
        readPosition = { x: position.x, y: position.y };
        return navigation.directGuidance(map, position, station);
      },
      drawArrow: (context, guidance, position) => { arrow = { guidance: guidance, position: position }; },
      drawOverlay: (context, guidance) => { overlay = guidance; }
    } } };
  vm.createContext(page);
  vm.runInContext(worldSource, page);
  const world = page.Game.world;
  world.setOwnName('Mara');
  world.start(canvas, () => {});
  world.setPlayers([{ name: 'Mara', character: 'consultant' }]);
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
  world.setUsableStations([target.id]);
  world.setTaskTarget(target.id, target.name);
  world.setPositions([{ name: 'Mara', x: target.x, y: target.y + 26 }]);
  nextFrame(now);
  now = 66;
  world.setPositions([{ name: 'Mara', x: target.x, y: target.y + 20 }]);
  nextFrame(now);
  expect(readPosition.y === target.y + 20, 'Arrival guidance must use the latest authoritative server position');
  expect(overlay.arrived && !button.disabled && world.stationInRange() === target.id,
    'Card, button and server range must agree while the drawing is queued');
  expect(arrow.position.y !== readPosition.y, 'The test needs a queued drawing behind the server');
  const drawn = world.ownDrawnPosition(now);
  expect(arrow.position.x === drawn.x && arrow.position.y === drawn.y, 'Arrow must follow the drawn position');
  arrow = null; overlay = null;
  world.setInputPaused(true);
  nextFrame(now + 1);
  expect(arrow === null && overlay === null, 'An open minigame must hide navigation');
  world.setInputPaused(false);
  world.setTaskTarget(null);
  nextFrame(now + 2);
  expect(arrow === null && overlay === null && labels['aria-label'] === 'Campus map',
    'No navigator target must hide guidance and reset its accessible label');
  expect(visibleStation === target.id && !button.disabled,
    'A sole private usable station must remain visible without the optional navigator API');
  for (const usable of [[], null, [target.id, 7]]) {
    world.setUsableStations(usable);
    glowingStation = null;
    nextFrame(now + 3);
    expect(visibleStation === null && glowingStation === null && button.disabled,
      'Missing or multiple private tasks must not reveal markers, glow or an active Use button');
  }
  world.stop();
  return { assertions: checked };
}
