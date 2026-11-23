// Four guests play Classic in Chromium against the real server (M3-4.23):
// the red emergency button appears after 45 seconds at campus.button, a
// living player in range sees "E Emergency", and E opens the meeting for all.
// Run by test_play_emergency_button_centre.py:
//
//   node play_emergency_button_centre_in_browser.js <base url> [screenshot dir] [label]
//
// When a player must stand somewhere, it prints {"put": [[name, [x, y]], ...]}
// and waits for "ok" on stdin. Its last line is the result (see `out`).
// With a screenshot dir it keeps <label>-deck.png (the Main Deck with the
// button) and <label>-hint.png (the moment "E Emergency" shows), both at
// deviceScaleFactor 2.
//
// The page is only watched: Game.world.drawMap is wrapped to note, per frame,
// whether the button may be drawn and whether a circle of the button's radius
// was drawn at its place.
const readline = require('readline');
const path = require('path');
const { chromium } = require('playwright');

const base = process.argv[2];
const shots = process.argv[3] || null;
const label = process.argv[4] || 'branch';
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

const PROBE = () => {
  window.__button = { frame: null, look: null };
  window.addEventListener('load', () => {
    const world = window.Game && window.Game.world;
    if (!world || !world.drawMap) return;
    const drawMap = world.drawMap;
    const arc = CanvasRenderingContext2D.prototype.arc;
    let arcs = null;
    CanvasRenderingContext2D.prototype.arc = function (x, y, r) {
      if (arcs) arcs.push([x, y, r]);
      return arc.apply(this, arguments);
    };
    world.drawMap = function (ctx, campus, view, emergencyVisible) {
      arcs = [];
      try { return drawMap.apply(this, arguments); } finally {
        const b = campus && campus.button;
        const drawn = Boolean(b) && arcs.some(([x, y, r]) => x === b.x && y === b.y && r === b.r);
        window.__campus = campus;
        window.__button.frame = { visible: emergencyVisible === true, drawn };
        window.__button.look = emergencyVisible === true ? 'ready' : emergencyVisible === 'locked' ? 'locked' : 'none';
        arcs = null;
      }
    };
    // The own drawn and server position, as the arrow test reads them.
    const navigation = window.Game.taskNavigation;
    if (!navigation) return;
    const draw = navigation.draw;
    navigation.draw = function (ctx, campus, drawn, server) {
      window.__button.me = { drawn: drawn && { x: drawn.x, y: drawn.y }, server: server && { x: server.x, y: server.y } };
      return draw.apply(this, arguments);
    };
  });
};

async function guest(browser, name, scale) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: scale });
  const page = await context.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') problems.push(`${name} ${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`${name} page error: ${e.message}`));
  await page.addInitScript(PROBE);
  const g = { page, label: name, received: [] };
  await page.routeWebSocket(/\/ws$/, (ws) => {
    const server = ws.connectToServer();
    server.onMessage((text) => {
      const message = JSON.parse(text);
      message.__at = Date.now();
      g.received.push(message);
      ws.send(text);
    });
  });
  await page.goto(base + '/');
  await page.click('#start-guest');
  await page.waitForSelector('#screen-home:not([hidden])');
  g.name = g.received.find((m) => m.type === 'signed_in').name;
  return g;
}

const pause = (ms) => new Promise((r) => setTimeout(r, ms));

async function frame(g, type, timeout = 10000) {
  const until = Date.now() + timeout;
  for (;;) {
    const found = g.received.find((m) => m.type === type);
    if (found) return found;
    if (Date.now() > until) throw new Error(`${g.label} never got ${type}`);
    await pause(50);
  }
}

// Puts `g` at `spot` and waits until the page draws it there (server and drawn position).
async function standAt(g, spot) {
  await put([[g.name, spot]]);
  await g.page.waitForFunction(([x, y]) => {
    const me = window.__button.me;
    const at = (position, near) => position && Math.abs(position.x - x) <= near && Math.abs(position.y - y) <= near;
    return window.__button.frame !== null && Boolean(me) && at(me.server, 0.01) && at(me.drawn, 0.5);
  }, spot, { timeout: 10000 });
  await pause(300); // the HUD button follows on the next frames
}

const useText = (g) => g.page.textContent('.use-button');

function meetingsSince(g, count) {
  return g.received.slice(count).filter((m) => m.type === 'meeting_state');
}

(async () => {
  const browser = await chromium.launch();
  const out = { button: null, before: null, unlock: null, outOfRange: null, scene: null, hint: null, meeting: null, twice: null, problems };
  try {
    const pages = [await guest(browser, 'host', 2)];
    await pages[0].page.click('#home-create');
    await pages[0].page.waitForFunction(() => /[A-Z]{4}/.test(document.getElementById('lobby-code').textContent));
    const code = (await pages[0].page.textContent('#lobby-code')).match(/[A-Z]{4}/)[0];
    for (let i = 1; i < 4; i++) {
      const g = await guest(browser, 'guest' + i, 2);
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
      const role = await frame(g, 'classic_role', 20000);
      g.role = role.role;
      g.roundAt = role.__at;
    }
    for (const g of pages) await g.page.waitForSelector('#classic-role-card', { state: 'hidden', timeout: 20000 });
    // The caller is a living High Performer (every page has deviceScaleFactor 2).
    const caller = pages.find((g) => g.role === 'HP');
    out.callerScale = await caller.page.evaluate(() => window.devicePixelRatio);
    const button = await caller.page.evaluate(() => window.__campus.button);
    out.button = button;
    const hintRadius = await caller.page.evaluate(() => window.__campus.use_range);

    // 1. Before 45 s: standing on the button, it is drawn grey and locked (S-216), and E does nothing.
    await standAt(caller, [button.x, button.y]);
    const counts = pages.map((g) => g.received.length);
    out.before = {
      seconds: (Date.now() - caller.roundAt) / 1000,
      frame: await caller.page.evaluate(() => window.__button.frame),
      look: await caller.page.evaluate(() => window.__button.look),
      useText: await useText(caller),
    };
    await caller.page.keyboard.press('KeyE');
    await pause(800);
    out.before.meetings = pages.map((g, i) => meetingsSince(g, counts[i]).length);
    // Bypassing the page: the server answers with its own message, shown at the top.
    const errorsBefore = caller.received.filter((m) => m.type === 'error').length;
    await caller.page.evaluate(() => Game.net.send({ type: 'emergency' }));
    await caller.page.waitForFunction(() => !document.getElementById('message').hidden, null, { timeout: 5000 });
    out.before.rejection = caller.received.filter((m) => m.type === 'error').slice(errorsBefore)[0] || null;
    out.before.shown = await caller.page.textContent('#message');
    out.before.secondsAfterChecks = (Date.now() - caller.roundAt) / 1000;

    // 2. It appears at its place once the server's 45 s are over.
    await caller.page.waitForFunction(() => window.__button.frame && window.__button.frame.visible, null, { timeout: 60000, polling: 50 });
    await pause(200);
    out.unlock = {
      seconds: (Date.now() - caller.roundAt) / 1000,
      frame: await caller.page.evaluate(() => window.__button.frame),
      look: await caller.page.evaluate(() => window.__button.look),
      others: await Promise.all(pages.map((g) => g.page.evaluate(() => window.__button.frame))),
    };

    // 3. Just outside the hint range: no hint, E opens nothing.
    await standAt(caller, [button.x, button.y + hintRadius + 2]);
    const countsOut = pages.map((g) => g.received.length);
    out.outOfRange = { useText: await useText(caller) };
    await caller.page.keyboard.press('KeyE');
    await pause(800);
    out.outOfRange.meetings = pages.map((g, i) => meetingsSince(g, countsOut[i]).length);

    // 4. The Main Deck with the button, the caller standing below and left of it
    // (so neither the character nor its name covers the button).
    await standAt(caller, [button.x - 50, button.y + 30]);
    out.scene = { frame: await caller.page.evaluate(() => window.__button.frame) };
    if (shots) await caller.page.screenshot({ path: path.join(shots, `${label}-deck.png`) });

    // 5. At the edge of the hint range (distance use_range): "E Emergency".
    await standAt(caller, [button.x, button.y + hintRadius]);
    await caller.page.waitForFunction(() => document.querySelector('.use-button').textContent === 'E Emergency', null, { timeout: 5000 })
      .catch(() => {});
    out.hint = {
      useText: await useText(caller),
      disabled: await caller.page.$eval('.use-button', (b) => b.disabled),
    };
    if (shots) await caller.page.screenshot({ path: path.join(shots, `${label}-hint.png`) });

    // 6. E twice quickly: one meeting for all four, the second press is refused.
    const countsMeeting = pages.map((g) => g.received.length);
    const errorsMeeting = caller.received.filter((m) => m.type === 'error').length;
    await caller.page.keyboard.press('KeyE');
    await caller.page.keyboard.press('KeyE');
    for (const g of pages) await g.page.waitForSelector('#classic-meeting:not([hidden])', { timeout: 10000 });
    await pause(800);
    out.meeting = pages.map((g, i) => {
      const states = meetingsSince(g, countsMeeting[i]);
      const first = states[0] || {};
      return { label: g.label, open: true, reason: first.reason, phase: first.phase,
        trigger: first.trigger_player_id, caller: caller.name, discussions: states.filter((s) => s.phase === 'discussion' && s.reason === 'emergency').length };
    });
    out.twice = { errors: caller.received.filter((m) => m.type === 'error').slice(errorsMeeting).map((m) => m.message) };
  } finally {
    await browser.close();
    answers.close();
  }
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
