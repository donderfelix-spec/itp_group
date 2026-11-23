// Five guests play Classic in Chromium; the real server sends `station_done`
// (S-143, S-154). Run by test_play_classic_task_card_end_to_end.py:
//
//   node play_classic_task_card_end_to_end_in_browser.js <base url>
//
// When a player must stand somewhere, it prints {"put": [[name, station or
// [x, y]], ...]} and waits for "ok" on stdin. Its last line is the result:
//   pages   per page: label, name, role, own task_stations, their names, card
//           lines of the side panel, the task named in the card at the top left
//   done    one High Performer's card and group bar before and after it
//           finished its first station through the page (E, "Finish task")
//   ghost   another High Performer's card before and after the Free Rider
//           failed it (Q)
//   problems  console errors and warnings, page errors
const readline = require('readline');
const { chromium } = require('playwright');

const base = process.argv[2];
const problems = [];
const answers = readline.createInterface({ input: process.stdin });
const waiting = [];
answers.on('line', () => { const next = waiting.shift(); if (next) next(); });

// Asks the test to place players and waits until it has.
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
  // Every message from the server to this page is noted.
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

// Waits until the server has sent this page a message of `type`.
async function frame(g, type, timeout = 10000) {
  const until = Date.now() + timeout;
  for (;;) {
    const found = g.received.find((m) => m.type === type);
    if (found) return found;
    if (Date.now() > until) throw new Error(`${g.label} never got ${type}`);
    await new Promise((r) => setTimeout(r, 50));
  }
}

async function card(g) {
  return g.page.evaluate(() => {
    const fill = document.getElementById('classic-progress-fill');
    return {
      lines: document.getElementById('classic-task').innerText.split('\n').filter(Boolean),
      // Each bullet: its name, whether it is marked done, faded, crossed out.
      items: [...document.querySelectorAll('#classic-task li')].map((row) => ({
        name: row.firstChild ? row.firstChild.textContent : '',
        done: row.classList.contains('round-task-done'),
        faded: Number(getComputedStyle(row).opacity) < 1,
        crossed: getComputedStyle(row).textDecorationLine === 'line-through',
      })),
      // S-197: the card at the top left of the map names the own active task.
      top: document.getElementById('task-card-task').hidden ? null
        : document.getElementById('task-card-title').textContent,
      note: document.getElementById('task-card-note').hidden ? null
        : document.getElementById('task-card-note').textContent,
      label: document.getElementById('classic-progress-label').textContent,
      fill: fill.getBoundingClientRect().width,
    };
  });
}

const pause = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch();
  const out = { pages: [], done: null, ghost: null, problems };
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
      const role = await frame(g, 'classic_role');
      g.role = role.role;
      g.tasks = role.task_stations;
      g.names = await g.page.evaluate((ids) => ids.map((id) => Game.duel.stationName(id)), g.tasks);
      await pause(300); // a frame draws the card at the top left
      const seen = await card(g);
      out.pages.push({ label: g.label, name: g.name, role: g.role, tasks: g.tasks, names: g.names,
        cardLines: seen.lines, top: seen.top, note: seen.note });
    }
    const highPerformers = pages.filter((g) => g.role === 'HP');
    const freeRider = pages.find((g) => g.role === 'FR');

    // 1. A High Performer finishes its first own station through the page.
    const worker = highPerformers[0];
    const station = worker.tasks[0];
    await put([[worker.name, station]]);
    const before = await card(worker);
    let opened = null;
    for (let attempt = 0; attempt < 20 && !opened; attempt++) {
      await worker.page.keyboard.press('KeyE');
      await pause(300);
      opened = worker.received.find((m) => m.type === 'station_opened');
    }
    if (!opened) throw new Error('E did not open the station: ' + JSON.stringify(worker.received.slice(-5)));
    await pause(1300); // the placeholder counts after 1 second
    await worker.page.click('button:has-text("Finish task")');
    const stationDone = await frame(worker, 'station_done');
    await worker.page.waitForFunction((text) => document.getElementById('classic-progress-label').textContent !== text,
      before.label, { timeout: 5000 });
    await pause(1000); // the bar may glide
    const after = await card(worker);
    await put([[worker.name, 'spawn']]);
    await pause(300); // the card at the top left follows the next task
    const next = await card(worker);
    out.done = { station, tasksBefore: worker.tasks, namesBefore: worker.names, stationDone,
      cardAfter: after.lines, itemsAfter: after.items, progressBefore: before.label, progressAfter: after.label,
      fillBefore: before.fill, fillAfter: after.fill, topBefore: before.top, topAfter: next.top };

    // 2. Another High Performer stands next to the Free Rider, who presses F.
    // The first one goes back to the spawn, so it is not the nearest.
    const victim = highPerformers[1];
    const spot = victim.tasks[0];
    await put([[worker.name, 'spawn'], [victim.name, spot], [freeRider.name, spot]]);
    let failed = null;
    for (let attempt = 0; attempt < 20 && !failed; attempt++) {
      await freeRider.page.keyboard.press('KeyF'); // F lets fail (S-195; Q did before)
      await pause(300);
      failed = victim.received.find((m) => m.type === 'classic_fail');
    }
    await pause(1000);
    const ghostCard = await card(victim);
    out.ghost = { failed: Boolean(failed && failed.target_id === victim.name), namesBefore: victim.names,
      cardAfter: ghostCard.lines, topAfter: ghostCard.top, tasks: victim.tasks,
      failedWho: failed ? failed.target_id : null, victimName: victim.name,
      lastFrames: failed ? [] : freeRider.received.slice(-5) };
  } finally {
    await browser.close();
    answers.close();
  }
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
