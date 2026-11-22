// Five guests play Classic in Chromium against the real server (M3-4.22):
// the arrow of a High Performer points at its nearest own open station.
// Run by test_play_classic_arrow_end_to_end.py:
//
//   node play_classic_arrow_end_to_end_in_browser.js <base url> [screenshot]
//
// When a player must stand somewhere, it prints {"put": [[name, station or
// [x, y]], ...]} and waits for "ok" on stdin. Its last line is the result:
//   worker    a High Performer: its list, the spot it stands on, and the
//             arrow seen there at the start, after finishing its nearest
//             station, and after finishing all of them
//   ghost     another High Performer failed by the Free Rider: its arrow
//   freeRider whether the Free Rider's page ever drew an arrow
//   problems  console errors and warnings, page errors
//
// The page is only watched: after loading, Game.taskNavigation.draw is
// wrapped, and every turn of the canvas inside it is one drawn arrow.
const readline = require('readline');
const { chromium } = require('playwright');

const base = process.argv[2];
const screenshot = process.argv[3] || null;
const problems = [];
const answers = readline.createInterface({ input: process.stdin });
const waiting = [];
answers.on('line', () => { const next = waiting.shift(); if (next) next(); });

function put(places) {
  return new Promise((resolve) => {
    waiting.push(resolve);
    process.stdout.write(JSON.stringify({ put: places }) + '\n');
  });
}

// Notes each frame's arrow (its angle, or null), the drawn and the server position.
const PROBE = () => {
  window.__arrow = { frame: null, ever: false };
  window.addEventListener('load', () => {
    const navigation = window.Game && window.Game.taskNavigation;
    if (!navigation) return;
    const draw = navigation.draw;
    const rotate = CanvasRenderingContext2D.prototype.rotate;
    let angle = null;
    CanvasRenderingContext2D.prototype.rotate = function (value) {
      if (angle === undefined) angle = value; // only inside navigation.draw
      return rotate.apply(this, arguments);
    };
    navigation.draw = function (ctx, campus, drawn, server) {
      angle = undefined;
      try { return draw.apply(this, arguments); } finally {
        const arrow = angle === undefined ? null : angle;
        window.__campus = campus;
        window.__arrow.frame = { angle: arrow, drawn: drawn && { x: drawn.x, y: drawn.y },
          server: server && { x: server.x, y: server.y } };
        if (arrow !== null) window.__arrow.ever = true;
        angle = null;
      }
    };
  });
};

async function guest(browser, label) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') problems.push(`${label} ${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`${label} page error: ${e.message}`));
  await page.addInitScript(PROBE);
  const g = { page, label, received: [] };
  await page.routeWebSocket(/\/ws$/, (ws) => {
    const server = ws.connectToServer();
    server.onMessage((text) => {
      g.received.push(JSON.parse(text));
      ws.send(text);
    });
  });
  await page.goto(base + '/');
  await page.click('#start-guest');
  await page.waitForSelector('#screen-home:not([hidden])');
  g.name = g.received.find((m) => m.type === 'signed_in').name;
  return g;
}

async function frame(g, type, timeout = 10000) {
  const until = Date.now() + timeout;
  for (;;) {
    const found = g.received.find((m) => m.type === type);
    if (found) return found;
    if (Date.now() > until) throw new Error(`${g.label} never got ${type}`);
    await new Promise((r) => setTimeout(r, 50));
  }
}

const pause = (ms) => new Promise((r) => setTimeout(r, ms));

// The arrow of the newest frame once the character stands at `spot`: the
// server has sent the new position and the drawn character has reached it.
async function arrowOf(g, spot) {
  await g.page.waitForFunction(([x, y]) => {
    const frame = window.__arrow.frame;
    const at = (position, near) => position && Math.abs(position.x - x) <= near && Math.abs(position.y - y) <= near;
    return Boolean(frame) && at(frame.server, 0.01) && at(frame.drawn, 0.5);
  }, spot, { timeout: 10000 });
  return g.page.evaluate(() => window.__arrow.frame);
}

// The arrow fades out from 60 units on, so the spot keeps this far from
// every station of the player's own list: there the arrow is fully drawn.
const AWAY_FROM_EVERY_OWN_STATION = 70;

// A free spot 90 to 200 map units from the first of `stationIds` and at
// least AWAY_FROM_EVERY_OWN_STATION from all of them, found with the page's own map.
async function spotNear(g, stationIds) {
  const spot = await g.page.evaluate(([ids, away]) => {
    const campus = window.__campus;
    const free = Game.taskNavigation.create(campus);
    const own = ids.map((id) => campus.stations.find((entry) => entry.id === id));
    const farFromAll = (x, y) => own.every((station) => Math.hypot(station.x - x, station.y - y) >= away);
    for (let distance = 90; distance <= 200; distance += 10) {
      for (let turn = 0; turn < 16; turn++) {
        const x = Math.round(own[0].x + Math.cos(turn * Math.PI / 8) * distance);
        const y = Math.round(own[0].y + Math.sin(turn * Math.PI / 8) * distance);
        if (free.isFree(x, y) && farFromAll(x, y)) return [x, y];
      }
    }
    return null;
  }, [stationIds, AWAY_FROM_EVERY_OWN_STATION]);
  if (!spot) throw new Error('No free spot away from stations ' + stationIds);
  return spot;
}

// Stands at `station`, presses E and clicks "Finish task"; waits for station_done.
async function finish(g, station) {
  await put([[g.name, station]]);
  const doneBefore = g.received.filter((m) => m.type === 'station_done').length;
  const openedBefore = g.received.filter((m) => m.type === 'station_opened').length;
  let opened = false;
  for (let attempt = 0; attempt < 20 && !opened; attempt++) {
    await g.page.keyboard.press('KeyE');
    await pause(300);
    opened = g.received.filter((m) => m.type === 'station_opened').length > openedBefore;
  }
  if (!opened) throw new Error('E did not open station ' + station);
  await pause(1300); // the placeholder counts after 1 second
  await g.page.click('button:has-text("Finish task")');
  const until = Date.now() + 10000;
  while (g.received.filter((m) => m.type === 'station_done').length === doneBefore) {
    if (Date.now() > until) throw new Error('No station_done for ' + station);
    await pause(50);
  }
  // "Done" closes the window by itself after a moment.
  await g.page.waitForSelector('#minigame-title', { state: 'detached', timeout: 10000 });
}

(async () => {
  const browser = await chromium.launch();
  const out = { worker: null, ghost: null, freeRider: null, problems };
  try {
    const pages = [await guest(browser, 'host')];
    await pages[0].page.click('#home-create');
    await pages[0].page.waitForFunction(() => /[A-Z]{4}/.test(document.getElementById('lobby-code').textContent));
    const code = (await pages[0].page.textContent('#lobby-code')).match(/[A-Z]{4}/)[0];
    for (let i = 1; i < 5; i++) {
      const g = await guest(browser, 'guest' + i);
      await g.page.fill('#join-code', code);
      await g.page.click('#join-submit');
      await g.page.waitForSelector('#screen-lobby:not([hidden])');
      pages.push(g);
    }
    const host = pages[0].page;
    await host.click('#lobby-modes .mode:has-text("Classic")');
    await host.waitForSelector('#lobby-modes .mode[aria-pressed="true"]:has-text("Classic")');
    await host.click('#lobby-start');
    for (const g of pages) {
      await g.page.waitForSelector('#classic-progress:not([hidden])', { timeout: 15000 });
      await g.page.waitForSelector('#classic-role-card', { state: 'hidden', timeout: 20000 });
      const role = await frame(g, 'classic_role');
      g.role = role.role;
      g.tasks = role.task_stations;
    }
    const highPerformers = pages.filter((g) => g.role === 'HP');
    const freeRider = pages.find((g) => g.role === 'FR');
    const worker = highPerformers[0];
    const victim = highPerformers[1];

    // 1. The worker stands a few tiles from its first station.
    const spot = await spotNear(worker, worker.tasks);
    await put([[worker.name, spot], [freeRider.name, spot]]);
    const start = await arrowOf(worker, spot);
    const card = await worker.page.evaluate(() => ({
      here: document.getElementById('task-card-here').textContent,
      taskHidden: document.getElementById('task-card-task').hidden,
    }));
    if (screenshot) await worker.page.screenshot({ path: screenshot });

    // 2. It finishes the nearest one and goes back to the spot.
    const open = worker.tasks.slice();
    const campus = await worker.page.evaluate(() => window.__campus);
    const distance = (id, from) => {
      const s = campus.stations.find((entry) => entry.id === id);
      return Math.hypot(s.x - from.x, s.y - from.y);
    };
    let first = open[0];
    for (const id of open) if (distance(id, start.server) < distance(first, start.server)) first = id;
    await finish(worker, first);
    open.splice(open.indexOf(first), 1);
    await put([[worker.name, spot]]);
    const afterOne = await arrowOf(worker, spot);

    // 3. It finishes all the others: no arrow any more.
    for (const id of open.slice()) await finish(worker, id);
    await put([[worker.name, spot]]);
    const afterAll = await arrowOf(worker, spot);
    out.worker = { tasks: worker.tasks, spot, start, card, first, afterOne, afterAll, campus: { stations: campus.stations } };

    // 4. The Free Rider fails another High Performer, which then walks on as a ghost.
    const at = victim.tasks[0];
    await put([[victim.name, at], [freeRider.name, at]]);
    let failed = null;
    for (let attempt = 0; attempt < 20 && !failed; attempt++) {
      await freeRider.page.keyboard.press('KeyQ');
      await pause(300);
      failed = victim.received.find((m) => m.type === 'classic_fail');
    }
    const ghostSpot = await spotNear(victim, victim.tasks);
    await put([[victim.name, ghostSpot], [freeRider.name, 'spawn']]);
    out.ghost = { failed: Boolean(failed && failed.target_id === victim.name), tasks: victim.tasks,
      arrow: await arrowOf(victim, ghostSpot) };
    out.freeRider = { ever: await freeRider.page.evaluate(() => window.__arrow.ever) };
  } finally {
    await browser.close();
    answers.close();
  }
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
