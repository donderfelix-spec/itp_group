// Browser part of test_play_duel_clock.py (M2-2.11).
// Needs Playwright and Chromium.
//
// Usage: node play_duel_clock_in_browser.js <base-url>
// Prints one JSON object:
//   console   every console error or warning and page error of every page
//   lobby     the host's panel in the lobby with eight players (1280x800)
//   duel      per window size ("1280x800", "1024x700", "320x640"): the panel
//             of the host and of one other guest in a Duel with eight players
//   solo      the panel of one guest alone in a Solo round, per window size
//   classic   the host's panel in a Classic round with four players (1280x800)
//
// Every panel is measured by `measurePanel` below; nothing is clicked in it
// except what starts, leaves and joins rounds.
const { chromium } = require('playwright');

const base = process.argv[2];
const problems = [];

const SIZES = [
  { width: 1280, height: 800 },
  { width: 1024, height: 700 },
  { width: 320, height: 640 },
];

async function guest(browser, label, viewport) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
  const page = await context.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') problems.push(`${label} ${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`${label} page error: ${e.message}`));
  await page.goto(base + '/');
  await page.click('#start-guest');
  await page.waitForSelector('#screen-home:not([hidden])');
  return { page, label };
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

async function leave(g) {
  await g.page.click('#lobby-leave');
  await g.page.waitForSelector('#screen-home:not([hidden])');
}

async function startRound(host, mode) {
  await host.page.click(`#lobby-modes .mode:has-text("${mode}")`);
  await host.page.waitForTimeout(300);
  await host.page.click('#lobby-start');
  await host.page.waitForFunction(() => !document.getElementById('countdown').hidden, null, { timeout: 5000 });
  await host.page.waitForFunction(() => document.getElementById('countdown').hidden, null, { timeout: 15000 });
}

// Waits until the clock of a Duel or Solo round shows a time, so the panel
// has its final size.
async function waitForClock(g) {
  await g.page.waitForFunction(() => /\d:\d\d/.test(document.getElementById('duel-clock').textContent), null, { timeout: 5000 });
}

async function resize(g, size) {
  await g.page.setViewportSize(size);
  await g.page.waitForTimeout(300);
}

// Where the parts of the side panel stand, in CSS pixels of the window. The
// visible part of the middle is its box cut by the window: what the player
// sees without scrolling.
function measurePanel() {
  const shown = (el) => Boolean(el) && !el.hidden && el.getClientRects().length > 0;
  const rect = (el) => {
    if (!shown(el)) return null;
    const r = el.getBoundingClientRect();
    return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height };
  };
  const byId = (id) => document.getElementById(id);
  const middle = document.querySelector('.panel-middle');
  const box = middle.getBoundingClientRect();
  const firstShown = [...middle.children].find(shown);
  return {
    visible: {
      top: Math.max(box.top, 0),
      bottom: Math.min(box.bottom, window.innerHeight),
      left: Math.max(box.left, 0),
      right: Math.min(box.right, window.innerWidth),
    },
    window: { width: window.innerWidth, height: window.innerHeight },
    middleTop: box.top,
    middleScrollTop: middle.scrollTop,
    pageScrollY: window.scrollY,
    pageScrollsSideways: document.documentElement.scrollWidth > window.innerWidth,
    firstShownId: firstShown ? (firstShown.id || firstShown.textContent.trim()) : null,
    clock: rect(byId('duel-clock')),
    clockText: byId('duel-clock').textContent,
    next: rect(byId('duel-next')),
    nextText: byId('duel-next').textContent,
    heading: shown(byId('duel-panel')) ? byId('duel-heading').textContent : null,
    players: rect(byId('lobby-players')),
    playerRows: document.querySelectorAll('#lobby-players .player').length,
    progressRows: [...document.querySelectorAll('#lobby-players .player-done')].map((el) => el.textContent),
    bars: document.querySelectorAll('#lobby-players .player-bar').length,
    oldDuelList: byId('duel-players') !== null,
    modes: rect(byId('lobby-modes')),
    modeText: rect(byId('lobby-mode-text')),
    characterArea: rect(byId('lobby-character-area')),
    characterHeights: [...document.querySelectorAll('#lobby-characters > *')]
      .filter(shown).map((el) => el.getBoundingClientRect().height),
    classicProgress: rect(byId('classic-progress')),
    duelPanel: rect(byId('duel-panel')),
  };
}

const look = (g) => g.page.evaluate(measurePanel);

(async () => {
  const browser = await chromium.launch();
  const out = { lobby: null, duel: {}, solo: {}, classic: null };
  try {
    // Eight guests in one lobby. The host is measured at every size, and
    // so is one guest who is not the host (no mode buttons in its panel).
    const host = await guest(browser, 'host', SIZES[0]);
    const code = await createLobby(host);
    const others = [];
    for (let i = 1; i < 8; i++) {
      const g = await guest(browser, 'guest' + i, { width: 640, height: 480 });
      await join(g, code);
      others.push(g);
    }
    await host.page.waitForTimeout(800);
    out.lobby = await look(host);

    const watcher = others[0];
    await startRound(host, 'Duel');
    await waitForClock(host);
    await waitForClock(watcher);
    for (const size of SIZES) {
      const name = `${size.width}x${size.height}`;
      await resize(host, size);
      await resize(watcher, size);
      out.duel[name] = { host: await look(host), guest: await look(watcher) };
    }

    // Everybody leaves the Duel. One guest plays Solo alone, the host and
    // three guests play Classic.
    await resize(host, SIZES[0]);
    for (const g of [host, ...others]) await leave(g);

    const alone = others[7 - 1];
    await createLobby(alone);
    await startRound(alone, 'Solo');
    await waitForClock(alone);
    for (const size of SIZES) {
      await resize(alone, size);
      out.solo[`${size.width}x${size.height}`] = await look(alone);
    }

    const classicCode = await createLobby(host);
    for (const g of others.slice(0, 3)) await join(g, classicCode);
    await host.page.waitForTimeout(500);
    await startRound(host, 'Classic');
    await host.page.waitForTimeout(4000); // the role reveal
    out.classic = await look(host);
  } finally {
    out.console = problems;
    console.log(JSON.stringify(out));
    await browser.close();
  }
})().catch((e) => { console.error(e); process.exit(1); });
