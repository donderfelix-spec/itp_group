// Browser part of test_play_task_card.py (S-125, S-126, S-128, S-129, S-130).
// Needs Playwright and Chromium.
//
// Usage: node play_task_card_in_browser.js <base-url>
// Prints one JSON object:
//   console   every console error or warning and page error of every page
//   lobby     per guest (1280x800 host, 320x640 guest): card, room, task part,
//             pulsing stations, drawn station objects; and the mode buttons
//   duel      per guest at the start of a Duel: first station, pulsing
//             stations, card lines, player rows, whether the old Duel list
//             exists, and where card, own character and walking hint are
//   solo      the panel heading of a Solo round started by one guest alone
//   classic   per guest of a 4-guest Classic round: own list, pulsing stations, card
//
// The page is only watched: an init script wraps Game.world.drawMap and the
// station drawings to read which stations pulse and which objects are drawn.
const { chromium } = require('playwright');

const base = process.argv[2];
const problems = [];

const PROBE = () => {
  window.__probe = { pulse: null, drawn: {} };
  window.addEventListener('load', () => {
    const world = window.Game && window.Game.world;
    if (!world) return;
    const drawMap = world.drawMap;
    world.drawMap = function (ctx, campus, view, emergency, pulsing) {
      window.__probe.pulse = Array.isArray(pulsing) ? pulsing.slice().sort((a, b) => a - b) : pulsing;
      return drawMap.apply(this, arguments);
    };
    const drawings = (world.art && world.art.stations) || {};
    Object.keys(drawings).forEach((id) => {
      const draw = drawings[id];
      if (typeof draw !== 'function') return;
      drawings[id] = function () { window.__probe.drawn[id] = true; return draw.apply(this, arguments); };
    });
  });
};

async function guest(browser, label, viewport) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
  const page = await context.newPage();
  await page.addInitScript(PROBE);
  const seen = { firstStation: undefined };
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') problems.push(`${label} ${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`${label} page error: ${e.message}`));
  page.on('websocket', (ws) => ws.on('framereceived', (f) => {
    let m; try { m = JSON.parse(f.payload); } catch (e) { return; }
    if (m.type === 'duel_state' && seen.firstStation === undefined) seen.firstStation = m.next_station;
    if (m.type === 'classic_role') seen.ownList = m.task_stations;
  }));
  await page.goto(base + '/');
  await page.click('#start-guest');
  await page.waitForSelector('#screen-home:not([hidden])');
  return { page, seen, label };
}

async function createLobby(g) {
  await g.page.click('#home-create');
  await g.page.waitForSelector('#screen-lobby:not([hidden])');
  await g.page.waitForFunction(() => /[A-Z]{4}/.test(document.getElementById('lobby-code').textContent));
  return (await g.page.textContent('#lobby-code')).match(/[A-Z]{4}/)[0];
}

async function join(g, code) {
  await g.page.fill('#join-code', code);
  await g.page.click('#join-submit');
  await g.page.waitForSelector('#screen-lobby:not([hidden])');
}

async function startRound(host, mode, guests) {
  await host.page.click(`#lobby-modes .mode:has-text("${mode}")`);
  await host.page.waitForTimeout(300);
  await host.page.click('#lobby-start');
  await host.page.waitForFunction(() => !document.getElementById('countdown').hidden, null, { timeout: 5000 });
  await host.page.waitForFunction(() => document.getElementById('countdown').hidden, null, { timeout: 15000 });
  for (let i = 0; i < 50 && mode !== 'Classic' && guests.some((g) => g.seen.firstStation === undefined); i++) {
    await host.page.waitForTimeout(100);
  }
  await host.page.waitForTimeout(mode === 'Classic' ? 4000 : 800); // Classic: the role reveal
}

// What one page shows now. The own character stands in the middle of the
// map; its box (CSS pixels) reaches 46 map units above its position (head
// and name) and 6 below, 12 to each side; a map unit is 1/260 of the
// longer side of the map.
async function look(g) {
  await g.page.evaluate(() => { window.__probe.drawn = {}; });
  await g.page.waitForTimeout(300);
  return g.page.evaluate(() => {
    const shown = (el) => Boolean(el) && !el.hidden && el.getClientRects().length > 0;
    const rect = (el) => { if (!shown(el)) return null; const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; };
    const text = (id) => document.getElementById(id).textContent;
    const map = rect(document.getElementById('map'));
    const unit = Math.max(map.w, map.h) / 260;
    return {
      card: shown(document.getElementById('task-card')),
      here: text('task-card-here'),
      taskPart: shown(document.getElementById('task-card-task')),
      kicker: text('task-card-kicker'),
      title: text('task-card-title'),
      pulse: window.__probe.pulse,
      drawn: Object.keys(window.__probe.drawn).map(Number).sort((a, b) => a - b),
      rows: [...document.querySelectorAll('#lobby-players .player')].map((row) => {
        const done = row.querySelector('.player-done');
        const bar = row.querySelector('.player-bar-fill');
        return { done: done ? done.textContent : null, bar: bar ? bar.style.width : null };
      }),
      oldDuelList: document.getElementById('duel-players') !== null,
      duelHeading: shown(document.getElementById('duel-panel')) ? text('duel-heading') : null,
      cardRect: rect(document.getElementById('task-card')),
      hintRect: rect(document.querySelector('.map-area .hint')),
      ownRect: { x: map.x + map.w / 2 - 12 * unit, y: map.y + map.h / 2 - 46 * unit, w: 24 * unit, h: 52 * unit },
    };
  });
}

async function modeButtons(g) {
  return g.page.evaluate(() => [...document.querySelectorAll('#lobby-modes > .mode')].map((button) => {
    const r = button.getBoundingClientRect();
    return { name: button.querySelector('.mode-name').textContent, x: r.x, y: r.y, w: r.width };
  }));
}

(async () => {
  const browser = await chromium.launch();
  const out = { lobby: {}, duel: {}, solo: null, classic: [] };
  try {
    const wide = await guest(browser, 'wide', { width: 1280, height: 800 });
    const code = await createLobby(wide);
    const narrow = await guest(browser, 'narrow', { width: 320, height: 640 });
    await join(narrow, code);
    await wide.page.waitForTimeout(800);
    out.lobby.wide = await look(wide);
    out.lobby.narrow = await look(narrow);
    out.lobby.modes = await modeButtons(wide);

    await startRound(wide, 'Duel', [wide, narrow]);
    for (const g of [wide, narrow]) out.duel[g.label] = { firstStation: g.seen.firstStation, ...(await look(g)) };

    const alone = await guest(browser, 'alone', { width: 1280, height: 800 });
    await createLobby(alone);
    await startRound(alone, 'Solo', [alone]);
    out.solo = { firstStation: alone.seen.firstStation, ...(await look(alone)) };

    const four = [];
    for (let i = 1; i <= 4; i++) four.push(await guest(browser, 'classic' + i, { width: 640, height: 480 }));
    const classicCode = await createLobby(four[0]);
    for (const g of four.slice(1)) await join(g, classicCode);
    await four[0].page.waitForTimeout(500);
    await startRound(four[0], 'Classic', four);
    for (const g of four) out.classic.push({ ownList: g.seen.ownList, ...(await look(g)) });
  } finally {
    out.console = problems;
    console.log(JSON.stringify(out));
    await browser.close();
  }
})().catch((e) => { console.error(e); process.exit(1); });
