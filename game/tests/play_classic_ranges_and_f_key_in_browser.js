// Four guests play Classic in Chromium against the real server (S-180, S-181).
// Run by test_play_classic_ranges_and_f_key.py:
//
//   node play_classic_ranges_and_f_key_in_browser.js <base url> [screenshot folder]
//
// When a player must stand somewhere, it prints {"put": [[name, [x, y]], ...]}
// and waits for "ok" on stdin. Its last line is the result:
//   roles      label -> role
//   fail26     the Free Rider 26 map units from the victim: button, F sent a fail?
//   fail25     at 25: button text and whether F failed the victim
//   report85   a High Performer 40.5 from the sheet: Report button shown? (S-229, was 8.5)
//   report8    the Free Rider 40 from the sheet: Report shown, R started a meeting? (S-229, was 8)
//   sheetBox   per page: where the F-sheet is on the screen and the viewport size
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

async function guest(browser, label, viewport) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
  const page = await context.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') problems.push(`${label} ${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`${label} page error: ${e.message}`));
  const g = { page, label, viewport, received: [] };
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

// The newest classic_fail_status this page got.
function lastFailStatus(g) {
  const all = g.received.filter((m) => m.type === 'classic_fail_status');
  return all.length ? all[all.length - 1] : null;
}

async function buttons(g) {
  return g.page.evaluate(() => {
    const use = document.querySelector('.use-button');
    const report = document.querySelector('.report-button');
    return {
      useText: use ? use.textContent : null,
      useDisabled: use ? use.disabled : null,
      reportShown: report ? !report.hidden : null,
    };
  });
}

(async () => {
  const browser = await chromium.launch();
  const out = { roles: {}, problems, sheetBox: {} };
  try {
    const sizes = [
      { width: 1280, height: 800 }, { width: 1024, height: 700 },
      { width: 1280, height: 800 }, { width: 1024, height: 700 },
    ];
    const pages = [await guest(browser, 'host', sizes[0])];
    await pages[0].page.click('#home-create');
    await pages[0].page.waitForFunction(() => /[A-Z]{4}/.test(document.getElementById('lobby-code').textContent));
    const code = (await pages[0].page.textContent('#lobby-code')).match(/[A-Z]{4}/)[0];
    for (let i = 1; i < 4; i++) {
      const g = await guest(browser, 'guest' + i, sizes[i]);
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
    const highPerformers = pages.filter((g) => g.role === 'HP');
    const [victim, finder, third] = highPerformers;
    // Open paving on the Main Deck, left of the spawn; the others stand far away.
    const spot = [470, 340];
    const far = [[finder.name, [120, 560]], [third.name, [600, 560]]];

    // 1. 26 map units: out of range, F does nothing (the range is 25, S-194).
    await put([[victim.name, spot], [freeRider.name, [spot[0] + 26, spot[1]]], ...far]);
    await pause(800);
    await freeRider.page.keyboard.press('KeyF');
    await pause(600);
    out.fail26 = {
      status: lastFailStatus(freeRider), buttons: await buttons(freeRider),
      failed: victim.received.some((m) => m.type === 'classic_fail'),
    };

    // 2. 25 map units: in range, F fails the victim.
    await put([[freeRider.name, [spot[0] + 25, spot[1]]]]);
    await freeRider.page.waitForFunction(() => {
      const use = document.querySelector('.use-button');
      return use && !use.disabled;
    }, null, { timeout: 5000 }).catch(() => {});
    const before = await buttons(freeRider);
    await freeRider.page.keyboard.press('KeyF');
    let failed = null;
    for (let i = 0; i < 20 && !failed; i++) {
      await pause(100);
      failed = victim.received.find((m) => m.type === 'classic_fail');
    }
    out.fail25 = { status: lastFailStatus(freeRider), buttonsBefore: before,
      failed: Boolean(failed && failed.target_id === victim.name) };
    if (!failed) throw new Error('F at 25 did not fail: ' + JSON.stringify(out.fail25));
    const sheet = failed.position;

    // 3. A High Performer 40.5 from the sheet sees no Report button (S-229, was 8.5).
    await put([[finder.name, [sheet.x, sheet.y + 40.5]], [freeRider.name, [sheet.x + 60, sheet.y]]]);
    await pause(900);
    out.report85 = await buttons(finder);

    // Screenshots of the larger sheet on every page; the finder steps back so
    // its character does not cover the sheet.
    await put([[finder.name, [sheet.x - 45, sheet.y + 45]]]);
    await pause(900);
    for (const g of pages) {
      out.sheetBox[g.label] = await g.page.evaluate(() => {
        const canvas = document.querySelector('canvas');
        const r = canvas.getBoundingClientRect();
        return { canvas: { x: r.x, y: r.y, w: r.width, h: r.height }, viewport: { w: innerWidth, h: innerHeight },
          scrollWidth: document.documentElement.scrollWidth, scrollHeight: document.documentElement.scrollHeight };
      });
      if (shots) await g.page.screenshot({ path: path.join(shots, `sheet-${g.label}-${g.viewport.width}x${g.viewport.height}.png`) });
    }
    // The finder's page at both sizes, the sheet in view.
    for (const size of [{ width: 1280, height: 800 }, { width: 1024, height: 700 }]) {
      await finder.page.setViewportSize(size);
      await pause(400);
      const label = `finder-${size.width}x${size.height}`;
      out.sheetBox[label] = await finder.page.evaluate(() => ({ viewport: { w: innerWidth, h: innerHeight },
        scrollWidth: document.documentElement.scrollWidth, scrollHeight: document.documentElement.scrollHeight }));
      if (shots) await finder.page.screenshot({ path: path.join(shots, `sheet-${label}.png`) });
    }
    if (shots) {
      await finder.page.screenshot({ path: path.join(shots, `sheet-closeup-${finder.viewport.width}.png`),
        clip: await finder.page.evaluate(() => {
          const r = document.querySelector('canvas').getBoundingClientRect();
          return { x: r.x + r.width / 2 - 150, y: r.y + r.height / 2 - 150, width: 300, height: 300 };
        }) });
    }

    // 4. The Free Rider 40 from the sheet sees Report and starts the meeting with R (S-229, was 8).
    await put([[freeRider.name, [sheet.x + 40, sheet.y]]]);
    await freeRider.page.waitForSelector('.report-button:not([hidden])', { timeout: 5000 }).catch(() => {});
    const reportBefore = await buttons(freeRider);
    await freeRider.page.keyboard.press('KeyR');
    let meeting = null;
    for (let i = 0; i < 30 && !meeting; i++) {
      await pause(100);
      meeting = finder.received.find((m) => m.type === 'meeting_state');
    }
    out.report8 = { buttonsBefore: reportBefore, meetingReason: meeting ? meeting.reason : null,
      trigger: meeting ? meeting.trigger_player_id === freeRider.name : false };
  } finally {
    await browser.close();
    answers.close();
  }
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
