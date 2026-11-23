// Five guests play Classic in Chromium against the real server (S-202, M3-3.25).
// Run by test_play_fail_place_in_sight.py:
//
//   node play_fail_place_in_sight_in_browser.js <base url> [screenshot folder]
//
// When a player must stand somewhere, it prints {"put": [[name, [x, y]], ...]}
// and waits for "ok" on stdin. Its last line is the result:
//   roles      label -> role
//   names      label -> "freeRider", "victim", "near", "far" or "wall"
//   fail       label -> the classic_fail this page got (raw, from the WebSocket)
//   sheets1    label -> the classic_sheet messages before anybody walked
//   farReport  the far player at the sheet after walking there: classic_sheet, Report shown?
//   wall       the player behind the wall: classic_sheet messages, Report shown?
//   problems   console errors and warnings, page errors
const readline = require('readline');
const path = require('path');
const { chromium } = require('playwright');

const base = process.argv[2];
const shots = process.argv[3] || '';
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

async function guest(browser, label) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') problems.push(`${label} ${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`${label} page error: ${e.message}`));
  const g = { page, label, received: [] };
  // Every message from the server is recorded raw before the page gets it.
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
const sheetsOf = (g) => g.received.filter((m) => m.type === 'classic_sheet');
const reportShown = (g) => g.page.evaluate(() => {
  const report = document.querySelector('.report-button');
  return report ? !report.hidden : null;
});

(async () => {
  const browser = await chromium.launch();
  const out = { roles: {}, names: {}, fail: {}, sheets1: {}, problems };
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
      g.role = (await frame(g, 'classic_role')).role;
      out.roles[g.label] = g.role;
    }
    const freeRider = pages.find((g) => g.role === 'FR');
    const [victim, near, far, wall] = pages.filter((g) => g.role === 'HP');
    for (const [part, g] of Object.entries({ freeRider, victim, near, far, wall })) out.names[g.label] = part;

    // The sheet will lie on the Main Deck just below the lecture hall's wall:
    // `near` 59 units away in clear sight, `far` about 238 away, `wall` 60
    // away on the other side of the wall (S-185: range 120, walls block).
    const sheet = [201, 200];
    await put([
      [victim.name, sheet], [freeRider.name, [216, 200]], [near.name, [260, 200]],
      [far.name, [400, 330]], [wall.name, [201, 140]],
    ]);
    await freeRider.page.waitForFunction(() => {
      const use = document.querySelector('.use-button');
      return use && !use.disabled;
    }, null, { timeout: 8000 }).catch(() => {});
    await freeRider.page.keyboard.press('KeyF');
    for (const g of pages) out.fail[g.label] = await frame(g, 'classic_fail');
    await pause(1200); // several ticks
    for (const g of pages) out.sheets1[g.label] = sheetsOf(g);
    if (shots) {
      for (const g of [near, far, wall]) {
        await g.page.screenshot({ path: path.join(shots, `1-after-fail-${out.names[g.label]}.png`) });
      }
    }

    // The far player walks to the sheet: it comes into sight, he can report.
    await put([[far.name, [240, 220]]]);
    await pause(800);
    const whenInSight = sheetsOf(far);
    if (shots) await far.page.screenshot({ path: path.join(shots, '2-far-sees-the-sheet.png') });
    await put([[far.name, [sheet[0], sheet[1] + 3]]]);
    await far.page.waitForSelector('.report-button:not([hidden])', { timeout: 5000 }).catch(() => {});
    out.farReport = { sheets: whenInSight, reportShown: await reportShown(far) };

    // Behind the wall, still nothing: no message and no Report.
    await pause(600);
    out.wall = { sheets: sheetsOf(wall), reportShown: await reportShown(wall) };
    if (shots) await wall.page.screenshot({ path: path.join(shots, '3-behind-the-wall.png') });
  } finally {
    await browser.close();
    answers.close();
  }
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
