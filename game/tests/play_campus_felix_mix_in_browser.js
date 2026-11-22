// Browser part of test_play_campus_felix_mix.py (M2-1.19). Needs Playwright and Chromium.
//
// Usage: node play_campus_felix_mix_in_browser.js <base-url> [screenshot-folder]
//
// Two guests play the "Felix mix" map in Chromium with real key presses, the
// way a person would: hold a walk key, let go when the character is where it
// should be. Where it is, is what the server says: every `positions` message
// the page receives is read along (the page itself is not changed). A route
// is planned on the map file with the server's walking rule (a 10 x 10 box,
// touching allowed), as a few straight legs with room to spare at the turns.
//
// Prints one JSON object:
//   console     every console error or warning and page error of every page
//   doors       per room: reached behind the door, and back out on the deck
//   openings    per corridor opening: walked through it upwards and downwards
//   stations    per station 1-5: the server position, the distance to it
//   straight    every straight walk of the new walkways: start and end
//   hedge       where guest B stopped right below the hedge
//   duel        per guest: the next station glows in range, E twice opens one
//               window; after_leave: B left mid-round, A walked on
//   narrow      a 320 x 568 window: page width, map drawn
//   misses      planned walks that did not end where they should
//   rejections  every `error` message a page received, with what it sent before
// With a screenshot folder, pictures for a person are saved there as well.
// PLAY_ONLY=doors,stations plays only those parts; PLAY_DEBUG=1 prints every leg.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const base = process.argv[2];
const shots = process.argv[3] || null;
const campus = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'client', 'js', 'world', 'campus.json'), 'utf8'));
const W = campus.width;
const H = campus.height;
const HALF = 5; // server/world/movement.py PLAYER_HALF_SIZE

// ---- The map as a grid of unit cells, with sums for quick rectangle checks ----

const sums = new Int32Array((W + 1) * (H + 1));
(function fillSums() {
  const cells = new Uint8Array(W * H);
  for (const s of campus.solids) {
    for (let y = s.y; y < s.y + s.h; y++) for (let x = s.x; x < s.x + s.w; x++) {
      if (x >= 0 && x < W && y >= 0 && y < H) cells[y * W + x] = 1;
    }
  }
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    sums[(y + 1) * (W + 1) + x + 1] = cells[y * W + x] + sums[y * (W + 1) + x + 1] + sums[(y + 1) * (W + 1) + x] - sums[y * (W + 1) + x];
  }
})();

// Is the open rectangle (x0..x1, y0..y1) clear of every solid and inside the map?
function rectFree(x0, x1, y0, y1) {
  if (x0 < 0 || y0 < 0 || x1 > W || y1 > H) return false;
  const ix0 = Math.floor(x0); const ix1 = Math.ceil(x1); const iy0 = Math.floor(y0); const iy1 = Math.ceil(y1);
  const count = sums[iy1 * (W + 1) + ix1] - sums[iy0 * (W + 1) + ix1] - sums[iy1 * (W + 1) + ix0] + sums[iy0 * (W + 1) + ix0];
  return count === 0;
}

// The box of a player at (x, y) swept to (x2, y2) along one axis.
function sweepFree(x, y, x2, y2) {
  return rectFree(Math.min(x, x2) - HALF, Math.max(x, x2) + HALF, Math.min(y, y2) - HALF, Math.max(y, y2) + HALF);
}

// How many units of room a player at the whole-number place (x, y) has, up to 4.
function clearance(x, y) {
  for (let c = 0; c <= 4; c++) if (!rectFree(x - HALF - c, x + HALF + c, y - HALF - c, y + HALF + c)) return c - 1;
  return 4;
}

// ---- Planning: few turns, keep off the furniture (Dial's algorithm) ----

const DIRS = [[1, 0], [-1, 0], [0, 1], [0, -1]];
const TURN_COST = 15;
const NEAR_COST = [30, 12, 6, 2, 0, 0]; // by clearance 0..4 (index c + 1); narrow places are hard to stop in

function plan(from, to) {
  const start = [Math.round(from.x), Math.round(from.y)];
  const target = { x: Math.round(to.x), y: Math.round(to.y) };
  const n = W * H * 4;
  const cost = new Int32Array(n).fill(-1);
  const back = new Int32Array(n).fill(-1);
  const room = new Int8Array(W * H).fill(-2);
  const roomAt = (x, y) => {
    const i = y * W + x;
    if (room[i] === -2) room[i] = clearance(x, y);
    return room[i];
  };
  const buckets = [];
  const push = (c, s) => { (buckets[c] = buckets[c] || []).push(s); };
  for (let d = 0; d < 4; d++) { const s = (start[1] * W + start[0]) * 4 + d; cost[s] = 0; push(0, s); }
  let goal = -1;
  for (let c = 0; c < buckets.length && goal < 0; c++) {
    const bucket = buckets[c];
    if (!bucket) continue;
    for (let k = 0; k < bucket.length; k++) {
      const s = bucket[k];
      if (cost[s] !== c) continue;
      const d = s % 4; const cell = (s - d) / 4; const x = cell % W; const y = (cell - x) / W;
      if (x === target.x && y === target.y) { goal = s; break; }
      for (let nd = 0; nd < 4; nd++) {
        const nx = x + DIRS[nd][0]; const ny = y + DIRS[nd][1];
        if (nx < HALF || ny < HALF || nx > W - HALF || ny > H - HALF) continue;
        const r = roomAt(nx, ny);
        if (r < 0) continue;
        const nc = c + 1 + NEAR_COST[r + 1] + (nd === d ? 0 : TURN_COST);
        const ns = (ny * W + nx) * 4 + nd;
        if (cost[ns] < 0 || nc < cost[ns]) { cost[ns] = nc; back[ns] = s; push(nc, ns); }
      }
    }
  }
  if (goal < 0) return null;
  const cells = [];
  for (let s = goal; s >= 0; s = back[s]) { const cell = (s - (s % 4)) / 4; cells.push([cell % W, (cell - (cell % W)) / W]); }
  cells.reverse();
  // Straight legs: one per change of direction.
  const legs = [];
  for (let i = 1; i < cells.length; i++) {
    const axis = cells[i][0] !== cells[i - 1][0] ? 'x' : 'y';
    const dir = axis === 'x' ? cells[i][0] - cells[i - 1][0] : cells[i][1] - cells[i - 1][1];
    const at = axis === 'x' ? cells[i][0] : cells[i][1];
    const last = legs[legs.length - 1];
    if (last && last.axis === axis && last.dir === dir) last.to = at; else legs.push({ axis, dir, to: at });
  }
  return legs;
}

// ---- Reading the server's position, pressing keys ----

// Runs in the page before its own scripts: reads along every message.
function listenAlong() {
  const Original = window.WebSocket;
  window.__own = null; window.__pos = null; window.__types = []; window.__sent = [];
  window.WebSocket = class extends Original {
    constructor(...args) {
      super(...args);
      this.addEventListener('message', (event) => {
        let message;
        try { message = JSON.parse(event.data); } catch (e) { return; }
        if (message.type === 'signed_in') window.__own = message.name;
        if (message.type === 'positions' && Array.isArray(message.players)) {
          const own = message.players.find((p) => p.name === window.__own);
          if (own) window.__pos = { x: own.x, y: own.y };
        }
        if (message.type === 'error') window.__types.push({ ...message, after: window.__sent.slice(-3) });
      });
    }

    send(data) {
      window.__sent.push(String(data));
      if (window.__sent.length > 20) window.__sent.shift();
      super.send(data);
    }
  };
}

const KEY = { x: { 1: 'KeyD', '-1': 'KeyA' }, y: { 1: 'KeyS', '-1': 'KeyW' } };
// Every walk that did not end where it should (the test expects none).
const misses = [];
const debug = (...parts) => { if (process.env.PLAY_DEBUG) console.error(...parts); };
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function where(page) {
  return page.evaluate(() => window.__pos);
}

async function waitForPosition(page) {
  await page.waitForFunction(() => window.__pos !== null, null, { timeout: 15000 });
  return where(page);
}

// Holds the key of `axis`/`dir` until `stop(position)` is true, the player
// stands still for 0.5 s (blocked) or `limitMs` is over. Returns the trail.
async function hold(page, axis, dir, stop, limitMs = 12000) {
  const key = KEY[axis][dir];
  let p = await where(page);
  const trail = [p];
  if (stop(p)) return trail;
  await page.keyboard.down(key);
  const began = Date.now();
  let lastMove = Date.now();
  try {
    for (;;) {
      await pause(3);
      const q = await where(page);
      if (q.x !== p.x || q.y !== p.y) { trail.push(q); lastMove = Date.now(); p = q; }
      if (stop(p) || Date.now() - lastMove > 500 || Date.now() - began > limitMs) break;
    }
  } finally {
    await page.keyboard.up(key);
  }
  // A step that was under way when the key went up, or (on a busy machine)
  // a key-up that reached the server a tick or two late, still moves the
  // player: wait until the server's position has stood still for 150 ms.
  const settled = await settle(page);
  if (settled.x !== p.x || settled.y !== p.y) trail.push(settled);
  return trail;
}

// Waits until the server's position has not changed for 150 ms (at most 1 s
// in all) and returns it.
async function settle(page) {
  let p = await where(page);
  let since = Date.now();
  const began = Date.now();
  while (Date.now() - since < 150 && Date.now() - began < 1000) {
    await pause(10);
    const q = await where(page);
    if (q.x !== p.x || q.y !== p.y) { p = q; since = Date.now(); }
  }
  return p;
}

// Hold a key until the player stands still against something.
async function walkUntilBlocked(page, axis, dir) {
  const trail = await hold(page, axis, dir, () => false);
  return trail;
}

// The run of stopping places v (in steps of 0.5) along `axis` from p for
// which `ok` holds also `spare` units to each side, the one nearest to `aim`.
function windowAround(p, axis, dir, aim, ok, spare) {
  const here = p[axis];
  const values = [];
  for (let v = Math.round(aim * 2) / 2 - 40; v <= aim + 40; v += 0.5) {
    if ((v - here) * dir < 0) continue; // only forwards
    values.push([v, ok(v - spare) && ok(v) && ok(v + spare)]);
  }
  let best = null;
  let run = null;
  for (const [v, good] of values) {
    if (good) { run = run ? [run[0], v] : [v, v]; } else { run = null; }
    if (run) {
      const distance = Math.max(0, run[0] - aim, aim - run[1]);
      if (!best || distance < best.distance || (distance === best.distance && run[1] - run[0] > best.run[1] - best.run[0])) {
        best = { run: run.slice(), distance };
      }
    }
  }
  return best ? best.run : null;
}

// Walks to `goal` ({x, y}) and stops within `tol` on both axes. Returns the end position.
async function walkTo(page, goal, tol = 4) {
  for (let attempt = 0; attempt < 10; attempt++) {
    const p0 = await where(page);
    if (Math.abs(p0.x - goal.x) <= tol && Math.abs(p0.y - goal.y) <= tol) return p0;
    // An axis that is close enough already is not walked on again.
    const aim = {
      x: Math.abs(p0.x - goal.x) <= tol ? Math.round(p0.x) : goal.x,
      y: Math.abs(p0.y - goal.y) <= tol ? Math.round(p0.y) : goal.y,
    };
    // Keeping the axis that is close enough can aim at a place that is not
    // free (for station 10, between two CTT tables); then aim at the goal itself.
    const legs = plan(p0, aim) || plan(p0, goal);
    if (!legs) throw new Error(`no route from ${JSON.stringify(p0)} to ${JSON.stringify(goal)}`);
    let failed = false;
    for (let i = 0; i < legs.length && !failed; i++) {
      const leg = legs[i];
      const p = await where(page);
      const other = leg.axis === 'x' ? 'y' : 'x';
      const next = legs[i + 1];
      const afterNext = legs[i + 2];
      const sweep = (v) => (leg.axis === 'x' ? sweepFree(p.x, p.y, v, p.y) : sweepFree(p.x, p.y, p.x, v));
      let ok;
      if (!next) {
        ok = (v) => Math.abs(v - goal[leg.axis]) <= tol && sweep(v) && Math.abs(p[other] - goal[other]) <= tol + 0.01;
      } else {
        const nextSweep = (v) => (leg.axis === 'x' ? sweepFree(v, p.y, v, next.to) : sweepFree(p.x, v, next.to, v));
        ok = (v) => sweep(v) && nextSweep(v) && (afterNext || Math.abs(v - goal[leg.axis]) <= tol);
      }
      // The server sends positions rounded to 0.1: the aim keeps half a unit
      // to spare on each side; a stop in the loose window is tried anyway.
      const loose = windowAround(p, leg.axis, leg.dir, leg.to, ok, 0);
      let range = windowAround(p, leg.axis, leg.dir, leg.to, ok, 0.5) || loose;
      debug('leg', JSON.stringify({ p, leg, range, loose, legs: legs.length, i }));
      if (!range) { failed = true; break; }
      // Close to the planned turn where there is room for it (a step is about 6 units).
      const narrow = [Math.max(range[0], leg.to - 4), Math.min(range[1], leg.to + 4)];
      if (narrow[1] - narrow[0] >= 7) range = narrow;
      const inRange = (q) => q[leg.axis] >= range[0] && q[leg.axis] <= range[1];
      // Past the far end: let go at once and plan again from there.
      const past = (q) => (leg.dir > 0 ? q[leg.axis] > range[1] : q[leg.axis] < range[0]);
      const trail = await hold(page, leg.axis, leg.dir, (q) => inRange(q) || past(q));
      const end = trail[trail.length - 1][leg.axis];
      if (!(end >= loose[0] && end <= loose[1])) failed = true;
    }
    const p1 = await where(page);
    if (Math.abs(p1.x - goal.x) <= tol && Math.abs(p1.y - goal.y) <= tol) return p1;
  }
  const end = await where(page);
  misses.push({ goal, tol, end });
  return end;
}

// ---- Pages ----

async function guest(browser, problems, label, viewport) {
  const context = await browser.newContext({ viewport: viewport || { width: 1280, height: 800 }, deviceScaleFactor: 2 });
  const page = await context.newPage();
  await page.addInitScript(listenAlong);
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') problems.push(`${label} ${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`${label} page error: ${e.message}`));
  await page.goto(base + '/');
  await page.click('#start-guest');
  await page.waitForSelector('#screen-home:not([hidden])');
  return page;
}

async function shoot(page, name) {
  if (shots) await page.screenshot({ path: path.join(shots, name) });
}

// The whole map, drawn by the page's own drawMap at 2 pixels per unit.
async function shootWholeMap(page, name) {
  if (!shots) return;
  const url = await page.evaluate(async () => {
    const map = await (await fetch('js/world/campus.json')).json();
    const canvas = document.createElement('canvas');
    canvas.width = map.width * 2; canvas.height = map.height * 2;
    const ctx = canvas.getContext('2d');
    ctx.setTransform(2, 0, 0, 2, 0, 0);
    Game.world.drawMap(ctx, map);
    return canvas.toDataURL('image/png');
  });
  fs.writeFileSync(path.join(shots, name), Buffer.from(url.split(',')[1], 'base64'));
}

async function unfocus(page) {
  await page.evaluate(() => { if (document.activeElement) document.activeElement.blur(); });
}

const DOOR_PLACES = {
  // room: [a place behind the door (30+ units deep, in line with it), a place
  // in front of it, how close to the first place is close enough].
  'lecture-hall': [{ x: 125, y: 117 }, { x: 125, y: 192 }, 5],
  'mon-cafe': [{ x: 350, y: 120 }, { x: 350, y: 192 }, 6],
  canteen: [{ x: 565, y: 120 }, { x: 565, y: 192 }, 6],
  ctt: [null, { x: 90, y: 205 }, 0],
  'pingo-doce': [{ x: 540, y: 445 }, { x: 540, y: 380 }, 6],
};

function behindDoor(roomId, p) {
  const door = campus.doors.find((d) => d.room === roomId);
  const room = campus.rooms.find((r) => r.id === roomId);
  const inLine = p.x >= door.x + HALF && p.x <= door.x + door.w - HALF;
  const below = room.y >= door.y;
  const depth = below ? p.y - (door.y + door.h) : door.y - p.y;
  return inLine && inRoom(roomId, p) && depth >= 30;
}

function inRoom(roomId, p) {
  const r = campus.rooms.find((room) => room.id === roomId);
  return p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h;
}

// The free place nearest to a station, at least 1 unit off the furniture.
function placeAt(station) {
  let best = null;
  for (let y = station.y - 20; y <= station.y + 20; y++) for (let x = station.x - 20; x <= station.x + 20; x++) {
    const d = Math.hypot(x - station.x, y - station.y);
    if (clearance(x, y) >= 1 && (!best || d < best.d)) best = { x, y, d };
  }
  return { x: best.x, y: best.y };
}

function straightRecord(name, trail) {
  const first = trail[0]; const last = trail[trail.length - 1];
  return { name, from: first, to: last };
}

// In the CTT only x 100-105 is in line with the door and clear of the first
// table row: narrower than one step of the server (about 6 units). So the
// guest does what a person does: steps into the doorway, walks right along
// the door post until it stops them (x 105), then straight down.
async function enterTheCtt(a) {
  await walkTo(a, { x: 90, y: 230 }, 4);
  await walkUntilBlocked(a, 'x', 1);
  const trail = await hold(a, 'y', 1, (p) => p.y >= 280);
  return trail[trail.length - 1];
}

async function playDoors(a, out) {
  for (const room of Object.keys(DOOR_PLACES)) {
    const [inside, outside, tol] = DOOR_PLACES[room];
    const inPlace = inside ? await walkTo(a, inside, tol) : await enterTheCtt(a);
    const isIn = behindDoor(room, inPlace);
    await shoot(a, `door-${room}-inside.png`);
    const outPlace = await walkTo(a, outside, 4);
    out.doors[room] = { inside: inPlace, behind_door: isIn, outside: outPlace, back_out: !inRoom(room, outPlace) && Math.hypot(outPlace.x - outside.x, outPlace.y - outside.y) <= 8 };
  }
}

async function playOpenings(a, out) {
  const wallY = 227;
  for (const x of [365, 500]) {
    await walkTo(a, { x, y: 250 }, 4);
    const up = await hold(a, 'y', -1, (p) => p.y <= 205);
    const down = await hold(a, 'y', 1, (p) => p.y >= 250);
    const crossed = (trail, test) => trail.every((p) => p.x === trail[0].x) && test(trail[trail.length - 1]);
    out.openings.push({
      x,
      up: crossed(up, (p) => p.y < wallY - HALF), down: crossed(down, (p) => p.y > wallY + 6 + HALF),
      up_end: up[up.length - 1], down_end: down[down.length - 1],
    });
  }
}

async function playStations(a, out) {
  const order = [3, 2, 1, 4, 5];
  for (const id of order) {
    const station = campus.stations.find((s) => s.id === id);
    const p = await walkTo(a, placeAt(station), 5);
    const distance = Math.hypot(p.x - station.x, p.y - station.y);
    out.stations[id] = { at: p, distance: Math.round(distance * 10) / 10, in_range: distance <= campus.use_range };
    await shoot(a, `station-${id}.png`);
  }
}

async function playWalkways(a, out) {
  // The Lecture Hall: down both side aisles, across both gaps between the rows.
  await walkTo(a, { x: 35, y: 50 }, 4);
  out.straight.push(straightRecord('lecture left aisle down', await hold(a, 'y', 1, (p) => p.y >= 150)));
  await walkTo(a, { x: 215, y: 50 }, 4);
  out.straight.push(straightRecord('lecture right aisle down', await hold(a, 'y', 1, (p) => p.y >= 150)));
  // The middle of each gap between two lecture rows, read from the map, so
  // that the walk stays inside the gap wherever the rows are.
  const rows = campus.solids.filter((s) => s.kind === 'bench').sort((p, q) => p.y - q.y);
  const gapMiddle = (above, below) => (above.y + above.h + below.y) / 2;
  await walkTo(a, { x: 35, y: gapMiddle(rows[0], rows[1]) }, 3);
  out.straight.push(straightRecord('lecture gap rows 1-2 left to right', await hold(a, 'x', 1, (p) => p.x >= 215)));
  await shoot(a, 'walkway-lecture-gap-1-2.png');
  await walkTo(a, { x: 215, y: gapMiddle(rows[1], rows[2]) }, 3);
  out.straight.push(straightRecord('lecture gap rows 2-3 right to left', await hold(a, 'x', -1, (p) => p.x <= 35)));
  await shoot(a, 'walkway-lecture-gap-2-3.png');
  // Mon Café: straight from the door to the counter.
  await walkTo(a, { x: 350, y: 192 }, 4);
  out.straight.push(straightRecord('cafe door to counter', await walkUntilBlocked(a, 'y', -1)));
  await shoot(a, 'walkway-cafe-at-counter.png');
  // Canteen: up the centre aisle to the counter.
  await walkTo(a, { x: 565, y: 192 }, 4);
  out.straight.push(straightRecord('canteen centre aisle to counter', await walkUntilBlocked(a, 'y', -1)));
  await shoot(a, 'walkway-canteen-at-counter.png');
  // Pingo Doce: through the lane between the posts, then against each post.
  await walkTo(a, { x: 540, y: 385 }, 4);
  out.straight.push(straightRecord('pingo lane down', await hold(a, 'y', 1, (p) => p.y >= 435)));
  await walkTo(a, { x: 540, y: 421.5 }, 5);
  out.straight.push(straightRecord('pingo lane left into post', await walkUntilBlocked(a, 'x', -1)));
  await shoot(a, 'walkway-pingo-left-post.png');
  out.straight.push(straightRecord('pingo lane right into post', await walkUntilBlocked(a, 'x', 1)));
  await shoot(a, 'walkway-pingo-right-post.png');
}

async function playLooks(a, b, out) {
  // B stands right below the hedge, A next to it on the deck.
  await walkTo(b, { x: 590, y: 280 }, 5);
  const underHedge = await walkUntilBlocked(b, 'y', -1);
  out.hedge = underHedge[underHedge.length - 1];
  await walkTo(a, { x: 520, y: 290 }, 5);
  await shoot(b, 'look-hedge-guest-b-below.png');
  await shoot(a, 'look-hedge-seen-by-a.png');
  // Next to the seated guests of Mon Café and the diners of the Canteen.
  await walkTo(a, { x: 350, y: 82 }, 5);
  await shoot(a, 'look-cafe-guests.png');
  await walkTo(a, { x: 548, y: 100 }, 5);
  await shoot(a, 'look-canteen-diners.png');
  await walkTo(a, { x: 240, y: 280 }, 5);
  await shoot(a, 'look-deck-bushes-west.png');
}

// Closes the minigame window of a guest whose window opened. If it did not
// open, there is nothing to close: test_play_campus_felix_mix.py then reports
// that guest's station as not opened, instead of every test failing on a
// click that waits for a button that is not there.
async function closeIfOpen(page, record) {
  if (!record.opened) return;
  await page.click('.minigame-close');
  await page.waitForSelector('#minigame', { state: 'hidden' });
}

async function playDuel(a, b, out) {
  await a.click('#lobby-modes button:has-text("Duel")');
  await a.waitForSelector('#lobby-start:not([disabled])');
  await a.click('#lobby-start');
  const both = [a, b];
  await Promise.all(both.map((p) => p.waitForFunction(() => Game.duel.nextStation() !== null, null, { timeout: 20000 })));
  await Promise.all(both.map(unfocus));
  out.duel = {};
  // Both walk at the same time to their first station.
  await Promise.all(both.map(async (page, i) => {
    const label = i === 0 ? 'A' : 'B';
    const next = await page.evaluate(() => Game.duel.nextStation());
    const station = campus.stations.find((s) => s.id === next);
    const p = await walkTo(page, placeAt(station), 5);
    await pause(200);
    const glowing = await page.evaluate(() => Game.world.stationInRange());
    await shoot(page, `duel-${label}-station-${next}-in-range.png`);
    // E twice quickly: one window, nothing else.
    await page.keyboard.press('KeyE');
    await page.keyboard.press('KeyE');
    let opened = true;
    try { await page.waitForSelector('#minigame:not([hidden])', { timeout: 5000 }); } catch (e) { opened = false; }
    await pause(300);
    const windows = await page.evaluate(() => document.querySelectorAll('.minigame-window').length);
    await shoot(page, `duel-${label}-station-${next}-open.png`);
    out.duel[label] = { station: next, at: p, glowing, opened, windows };
  }));
  // B leaves in the middle of the round while walking; A closes its window and walks on.
  await closeIfOpen(b, out.duel.B);
  await b.keyboard.down('KeyS');
  await pause(200);
  await b.click('#lobby-leave');
  // The key goes up only once Home shows: a release before the server's
  // `left_lobby` arrives sends a move the server refuses with "You are not
  // in a lobby." (a known fault of the walking keys, not of the map).
  await b.waitForSelector('#screen-home:not([hidden])', { timeout: 5000 });
  await b.keyboard.up('KeyS');
  await closeIfOpen(a, out.duel.A);
  await unfocus(a);
  const before = await where(a);
  const trail = await hold(a, 'y', 1, (q) => q.y >= before.y + 20, 3000);
  await shoot(a, 'duel-A-after-B-left.png');
  out.duel.after_leave = { b_at_home: true, a_from: before, a_to: trail[trail.length - 1] };
}

async function playNarrow(browser, problems, out) {
  const page = await guest(browser, problems, 'N', { width: 320, height: 568 });
  await page.click('#home-create');
  await page.waitForSelector('#screen-lobby:not([hidden])');
  await waitForPosition(page);
  await pause(500);
  await unfocus(page);
  await hold(page, 'x', 1, () => false, 800);
  const look = await page.evaluate(() => {
    const canvas = document.getElementById('map');
    const ctx = canvas.getContext('2d');
    const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    const colours = new Set();
    for (let i = 0; i < data.length; i += 4 * 97) colours.add(`${data[i]},${data[i + 1]},${data[i + 2]}`);
    const rect = canvas.getBoundingClientRect();
    return {
      scroll_width: document.documentElement.scrollWidth, client_width: document.documentElement.clientWidth,
      body_scroll_width: document.body.scrollWidth,
      canvas: { width: canvas.width, height: canvas.height, left: rect.left, right: rect.right, top: rect.top, shown_width: rect.width, shown_height: rect.height },
      colours: colours.size,
    };
  });
  await shoot(page, 'narrow-320x568.png');
  if (shots) await page.screenshot({ path: path.join(shots, 'narrow-320x568-full.png'), fullPage: true });
  out.narrow = look;
  await page.context().close();
}

(async () => {
  const browser = await chromium.launch();
  const problems = [];
  const out = { console: problems, doors: {}, openings: [], stations: {}, straight: [], duel: null, narrow: null, hedge: null };
  const a = await guest(browser, problems, 'A');
  await a.click('#home-create');
  await a.waitForSelector('#screen-lobby:not([hidden])');
  await a.waitForFunction(() => /[A-Z0-9]{4}/.test(document.getElementById('lobby-code').textContent));
  const code = (await a.textContent('#lobby-code')).match(/[A-Z0-9]{4}/)[0];
  const b = await guest(browser, problems, 'B');
  await b.fill('#join-code', code);
  await b.click('#join-submit');
  await b.waitForSelector('#screen-lobby:not([hidden])');
  await Promise.all([waitForPosition(a), waitForPosition(b)]);
  await Promise.all([unfocus(a), unfocus(b)]);
  await shoot(a, 'start-lobby-a.png');
  await shootWholeMap(a, 'whole-map.png');

  // PLAY_ONLY=walkways,duel plays only these parts (for finding a fault).
  const only = process.env.PLAY_ONLY ? process.env.PLAY_ONLY.split(',') : null;
  const part = (name) => !only || only.includes(name);
  if (part('doors')) await playDoors(a, out);
  if (part('openings')) await playOpenings(a, out);
  if (part('stations')) await playStations(a, out);
  if (part('walkways')) await playWalkways(a, out);
  if (part('looks')) await playLooks(a, b, out);
  if (part('duel')) await playDuel(a, b, out);
  if (part('narrow')) await playNarrow(browser, problems, out);
  out.misses = misses;
  out.rejections = { A: await a.evaluate(() => window.__types), B: await b.evaluate(() => window.__types) };
  console.log(JSON.stringify(out));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
