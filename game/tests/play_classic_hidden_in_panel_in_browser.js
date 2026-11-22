// Five guests play Classic in Chromium; the Free Rider stands in a hiding
// spot and the real "Hidden" of M3-1.4 (S-135) is measured in the Classic
// panel of M2-2.11 (S-143). Run by test_play_classic_hidden_in_panel.py:
//
//   node play_classic_hidden_in_panel_in_browser.js <base url>
//
// With CLASSIC_HIDDEN_SCREENSHOT set, the Free Rider's page while hidden
// (1280 x 800) is saved there.
//
// When a player must stand somewhere, it prints {"put": [[name, [x, y]], ...]}
// and waits for "ok" on stdin. Its last line is the result:
//   roles      the role of every page
//   hidden     per window size (1280x800, 1024x700, 320x640): where "Hidden",
//              the bar, the panel and the "Players" heading are on the Free
//              Rider's page while he hides
//   hpInSpot   whether a High Performer standing in a hiding spot sees "Hidden"
//   hpPages    whether any High Performer page shows "Hidden" meanwhile
//   afterLeaving  whether the Free Rider still sees "Hidden" after stepping out
//   problems   console errors and warnings, page errors
const readline = require('readline');
const { chromium } = require('playwright');

const base = process.argv[2];
const screenshotPath = process.env.CLASSIC_HIDDEN_SCREENSHOT || '';
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

// Is "Hidden" shown on this page (in the panel, with a size)?
async function hintShown(g) {
  return g.page.evaluate(() => {
    const hint = document.getElementById('classic-hidden-hint');
    const panel = document.getElementById('classic-progress');
    return Boolean(hint && panel && !hint.hidden && !panel.hidden && hint.getBoundingClientRect().height > 0);
  });
}

async function waitForHint(g, shown, timeout = 5000) {
  const until = Date.now() + timeout;
  for (;;) {
    if ((await hintShown(g)) === shown) return true;
    if (Date.now() > until) return false;
    await pause(50);
  }
}

// Where "Hidden" and its neighbours are, as the page is first shown (no scrolling).
async function layout(g) {
  return g.page.evaluate(() => {
    const box = (el) => { const r = el.getBoundingClientRect(); return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height }; };
    const panel = document.getElementById('classic-progress');
    const hint = document.getElementById('classic-hidden-hint');
    const bar = panel.querySelector('[role="progressbar"]');
    let players = panel.nextElementSibling;
    while (players && !(players.tagName === 'H2' && players.textContent.trim() === 'Players')) players = players.nextElementSibling;
    // Every scrolled ancestor of the hint, and the page itself.
    const scrolled = [];
    for (let el = hint; el; el = el.parentElement) if (el.scrollTop) scrolled.push(el.id || el.className || el.tagName);
    if (window.scrollY) scrolled.push('window');
    const h = hint.getBoundingClientRect();
    const atCentre = document.elementFromPoint(h.left + h.width / 2, h.top + h.height / 2);
    return {
      text: hint.textContent,
      parentId: hint.parentElement && hint.parentElement.id,
      lastInPanel: panel.lastElementChild === hint,
      hint: box(hint), bar: box(bar), panel: box(panel), players: players ? box(players) : null,
      viewport: { width: window.innerWidth, height: window.innerHeight },
      scrolled,
      onTop: atCentre === hint || hint.contains(atCentre),
    };
  });
}

(async () => {
  const browser = await chromium.launch();
  const out = { roles: [], hidden: {}, hpInSpot: null, hpPages: null, afterLeaving: null, problems };
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
    }
    for (const g of pages) {
      g.role = (await frame(g, 'classic_role')).role;
      out.roles.push(g.role);
    }
    const fr = pages.find((g) => g.role === 'FR');
    const hps = pages.filter((g) => g.role === 'HP');

    // 1. The Free Rider stands in the first hiding spot (the hedge).
    await put([[fr.name, 'spot']]);
    const frShown = await waitForHint(fr, true);
    out.frShown = frShown;  // "Hidden" appeared within 5 seconds
    out.hpPages = [];
    for (const g of hps) out.hpPages.push(await hintShown(g));
    for (const [width, height] of [[1280, 800], [1024, 700], [320, 640]]) {
      await fr.page.setViewportSize({ width, height });
      await pause(400);
      out.hidden[`${width}x${height}`] = { shown: await hintShown(fr), ...(await layout(fr)) };
      if (width === 1280 && screenshotPath) await fr.page.screenshot({ path: screenshotPath });
    }
    await fr.page.setViewportSize({ width: 1280, height: 800 });

    // 2. A High Performer in the other hiding spot sees no "Hidden".
    await put([[hps[0].name, 'spot2']]);
    await pause(800);
    out.hpInSpot = await hintShown(hps[0]);

    // 3. The Free Rider steps out of the spot: "Hidden" goes.
    await put([[fr.name, 'outside']]);
    out.goneAfterLeaving = await waitForHint(fr, false);
    out.afterLeaving = await hintShown(fr);
  } finally {
    await browser.close();
    answers.close();
  }
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
