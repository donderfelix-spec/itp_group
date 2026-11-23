// Station 6, "Catch the wave", played in Chromium against the real server
// (M4-4.0, S-221). Run by test_play_catch_the_wave.py:
//
//   node play_catch_the_wave_in_browser.js <base url>
//
// The test makes station 6 the first station of every route and task list.
// When a player must stand somewhere, this prints {"put": [[name, station or
// "button" or "spawn"], ...]} and waits for "ok" on stdin. Its last line is:
//   duel      a Duel of two guests (1280x800 and 1024x600): the card, the window,
//             a click too early, three catches with the Space key, "Done",
//             the next station and the other guest's player list
//   classic   a Classic round of four guests: a High Performer catches three
//             waves with the mouse and the group bar grows; E of the Free
//             Rider at station 6 opens nothing; a second High Performer's open
//             window closes when a third player calls an emergency meeting
//   problems  console errors and warnings, page errors
const readline = require('readline');
const { chromium } = require('playwright');

const base = process.argv[2];
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

const pause = (ms) => new Promise((r) => setTimeout(r, ms));

async function guest(browser, label, viewport) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
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

async function frame(g, type, timeout = 10000, after = 0) {
  const until = Date.now() + timeout;
  for (;;) {
    const found = g.received.slice(after).find((m) => m.type === type);
    if (found) return found;
    if (Date.now() > until) throw new Error(`${g.label} never got ${type}`);
    await pause(50);
  }
}

async function lobbyOf(pages, mode) {
  const host = pages[0].page;
  await host.click('#home-create');
  await host.waitForFunction(() => /[A-Z]{4}/.test(document.getElementById('lobby-code').textContent));
  const code = (await host.textContent('#lobby-code')).match(/[A-Z]{4}/)[0];
  for (const g of pages.slice(1)) {
    await g.page.fill('#join-code', code);
    await g.page.click('#join-submit');
    await g.page.waitForSelector('#screen-lobby:not([hidden])');
  }
  await host.click(`#lobby-modes .mode:has-text("${mode}")`);
  await host.waitForSelector(`#lobby-modes .mode[aria-pressed="true"]:has-text("${mode}")`);
  await host.click('#lobby-start');
}

// Presses E until the server opened a station (or answered with an error).
async function useHere(g) {
  const from = g.received.length;
  for (let attempt = 0; attempt < 20; attempt++) {
    await g.page.keyboard.press('KeyE');
    await pause(300);
    const answer = g.received.slice(from).find((m) => m.type === 'station_opened' || m.type === 'error');
    if (answer) return answer;
  }
  throw new Error(g.label + ': E got no answer');
}

function lookAtWindow() {
  const card = document.querySelector('.minigame-window');
  if (!card) return null;
  const r = card.getBoundingClientRect();
  const button = card.querySelector('.surf-catch');
  const b = button.getBoundingClientRect();
  return {
    title: card.querySelector('.minigame-title').textContent,
    instructions: card.querySelector('.minigame-instructions').textContent,
    window: { x: r.x, y: r.y, w: r.width, h: r.height },
    viewport: { w: innerWidth, h: innerHeight },
    button: { x: b.x, y: b.y, w: b.width, h: b.height },
    focused: document.activeElement === button,
    score: card.querySelector('.surf-score').textContent,
  };
}

// Waits until the crest is over the board, then catches with `how`.
async function catchOne(g, how) {
  await g.page.waitForFunction(() => {
    const scene = document.querySelector('.surf-scene');
    return scene && scene.classList.contains('surf-in-range');
  }, null, { timeout: 8000, polling: 'raf' });
  if (how === 'space') await g.page.keyboard.press('Space');
  else await g.page.click('.surf-scene');
  await g.page.waitForFunction(() => !document.querySelector('.surf-scene')
    || !document.querySelector('.surf-scene').classList.contains('surf-in-range'), null, { timeout: 8000, polling: 'raf' });
}

async function playWave(g, how) {
  // A click at once: the first wave is still far left of the board.
  await g.page.click('.surf-scene');
  const early = await g.page.textContent('.surf-feedback');
  const scores = [];
  for (let i = 0; i < 3; i++) {
    await catchOne(g, how);
    scores.push(await g.page.evaluate(() => {
      const score = document.querySelector('.surf-score');
      return score ? score.textContent : 'window closed';
    }));
  }
  return { early, scores };
}

async function duel(browser) {
  const pages = [
    await guest(browser, 'duel-wide', { width: 1280, height: 800 }),
    await guest(browser, 'duel-low', { width: 1024, height: 600 }),
  ];
  await lobbyOf(pages, 'Duel');
  const [player, other] = pages;
  const first = await frame(player, 'duel_state', 20000);
  await player.page.waitForSelector('#countdown', { state: 'hidden', timeout: 20000 });
  await pause(500);
  const cardTitle = await player.page.textContent('#task-card-title');
  await put([[player.name, 6]]);
  const opened = await useHere(player);
  await pause(200);
  const window = await player.page.evaluate(lookAtWindow);
  const from = player.received.length;
  // "Done" shows for 0.5 s only (S-127): the page notes it when it appears.
  await player.page.evaluate(() => {
    window.__doneText = null;
    new MutationObserver(() => {
      const done = document.querySelector('.minigame-done');
      if (done) window.__doneText = done.textContent;
    }).observe(document.getElementById('minigame'), { childList: true, subtree: true });
  });
  const played = await playWave(player, 'space');
  const done = await frame(player, 'station_done', 5000, from);
  await pause(300);
  const doneText = await player.page.evaluate(() => window.__doneText);
  const next = await frame(player, 'duel_state', 5000, from);
  await put([[player.name, 'spawn']]);
  await pause(800);
  const nextCard = await player.page.textContent('#task-card-title');
  const rows = await other.page.evaluate(() => [...document.querySelectorAll('#lobby-players .player-done')].map((el) => el.textContent));
  return { first, cardTitle, opened, window, played, done, doneText, next, nextCard, otherRows: rows };
}

async function classic(browser) {
  const pages = [];
  for (let i = 0; i < 4; i++) pages.push(await guest(browser, 'classic' + i, { width: 1024, height: 700 }));
  await lobbyOf(pages, 'Classic');
  for (const g of pages) {
    await g.page.waitForSelector('#classic-progress:not([hidden])', { timeout: 15000 });
    await g.page.waitForSelector('#classic-role-card', { state: 'hidden', timeout: 20000 });
    const role = await frame(g, 'classic_role');
    g.role = role.role;
    g.tasks = role.task_stations;
  }
  const workers = pages.filter((g) => g.role === 'HP');
  const freeRider = pages.find((g) => g.role === 'FR');
  const [worker, second, third] = workers;
  await pause(300);
  const cardTitle = await worker.page.textContent('#task-card-title');
  const progressBefore = await worker.page.textContent('#classic-progress-label');

  // 1. A High Performer catches three waves with the mouse.
  await put([[worker.name, 6]]);
  const opened = await useHere(worker);
  await pause(200);
  const window = await worker.page.evaluate(lookAtWindow);
  const from = worker.received.length;
  const played = await playWave(worker, 'mouse');
  const done = await frame(worker, 'station_done', 5000, from);
  await worker.page.waitForFunction((text) => document.getElementById('classic-progress-label').textContent !== text,
    progressBefore, { timeout: 5000 });
  const progressAfter = await worker.page.textContent('#classic-progress-label');
  await put([[worker.name, 'spawn']]);
  await pause(800);
  const nextTitle = await worker.page.textContent('#task-card-title');

  // 2. The Free Rider at station 6 cannot open it (S-154): E there asks
  // nothing, and no window opens.
  await put([[freeRider.name, 6]]);
  const freeRiderFrom = freeRider.received.length;
  for (let attempt = 0; attempt < 5; attempt++) {
    await freeRider.page.keyboard.press('KeyE');
    await pause(300);
  }
  const freeRiderOpened = freeRider.received.slice(freeRiderFrom).some((m) => m.type === 'station_opened');
  const freeRiderWindow = await freeRider.page.evaluate(() => document.querySelector('.minigame-window') !== null);

  // 3. A second High Performer's open window closes when a meeting starts (S-199).
  await put([[freeRider.name, 'spawn'], [second.name, 6]]);
  const secondOpened = await useHere(second);
  const before = second.received.length;
  await put([[third.name, 'button']]);
  let closed = null;
  for (let attempt = 0; attempt < 20 && !closed; attempt++) {
    await third.page.keyboard.press('KeyE'); // E at the red button calls the meeting
    await pause(300);
    closed = second.received.slice(before).find((m) => m.type === 'station_closed') || null;
  }
  await pause(500);
  const meeting = second.received.slice(before).some((m) => m.type === 'meeting_state');
  const afterTypes = second.received.slice(before).map((m) => m.type);
  const windowAfterMeeting = await second.page.evaluate(() => document.querySelector('.minigame-window') !== null);
  return { roles: pages.map((g) => g.role), workerTasks: worker.tasks, cardTitle, opened, window, played, done,
    progressBefore, progressAfter, nextTitle, freeRiderOpened, freeRiderWindow, secondOpened, meeting,
    closed, windowAfterMeeting, afterTypes };
}

(async () => {
  const browser = await chromium.launch();
  const out = { problems };
  try {
    out.duel = await duel(browser);
    out.classic = await classic(browser);
  } finally {
    await browser.close();
    answers.close();
  }
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
