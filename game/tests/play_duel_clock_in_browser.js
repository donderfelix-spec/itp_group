// Browser part of test_play_duel_clock.py (M2-2.11, S-143).
// Needs Playwright and Chromium.
//
// Usage: node play_duel_clock_in_browser.js <base-url> [<screenshot-folder> <suffix>]
// Prints one JSON object:
//   console   every console error or warning and page error of every page
//   lobby     the host's panel in the lobby with eight players (1280x800)
//   duel      per window size ("1280x800", "1024x700", "320x640"): the panel
//             of the host and of one other guest in a Duel with eight players
//   solo      the panel of one guest alone in a Solo round, per window size
//   classic   per window size: the panel of the host and of one other guest
//             in a Classic round with five players
//   classicCards  per Classic page: its role and own list (as received),
//             Duel's names of those stations, the card's text and colour,
//             and all text of the page
//   classicDone   the card of one High Performer after each `station_done`
//             (with screenshots classic_hp_one_done and classic_hp_all_done)
//   classicWithHint  the other guest's Classic panel at 1280x800 with one
//             more paragraph at the end of #classic-progress, put there by
//             this script (as the "Hidden" hint of another branch will be)
//
// Every panel is measured by `measurePanel` below; nothing is clicked in it
// except what starts, leaves and joins rounds. With a screenshot folder,
// duel<suffix>.png, solo<suffix>.png, classic<suffix>.png, classic_hp<suffix>.png
// and classic_fr<suffix>.png (1280x800) are saved, from a player who is not
// the host where there is one (the Free Rider may be the host).
const { chromium } = require('playwright');

const base = process.argv[2];
const shotFolder = process.argv[3] || null;
const shotSuffix = process.argv[4] || '';
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
  // The WebSocket goes through this script: it notes every `classic_role`
  // and `task_stations` the page receives, and can hand the page a message
  // as if the server had sent it (`inject`).
  const g = { page, label, received: [], inject: null };
  await page.routeWebSocket(/\/ws$/, (ws) => {
    const server = ws.connectToServer();
    g.inject = (message) => ws.send(JSON.stringify(message));
    server.onMessage((text) => {
      const message = JSON.parse(text);
      if (message.type === 'classic_role' || 'task_stations' in message) g.received.push(message);
      ws.send(text);
    });
  });
  await page.goto(base + '/');
  await page.click('#start-guest');
  await page.waitForSelector('#screen-home:not([hidden])');
  return g;
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
  await host.page.waitForSelector(`#lobby-modes .mode[aria-pressed="true"]:has-text("${mode}")`, { timeout: 5000 });
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
  await g.page.waitForFunction(
    (want) => window.innerWidth === want.width && window.innerHeight === want.height, size, { timeout: 5000 });
  await waitForSteadyPanel(g);
}

// Waits until the parts of the panel's middle have stood still for three
// animation frames in a row (after a resize or a change of the round), at
// most 300 frames, about five seconds.
async function waitForSteadyPanel(g) {
  await g.page.evaluate(() => new Promise((resolve, reject) => {
    const where = () => JSON.stringify([...document.querySelectorAll('.panel-middle > *')].map((el) => {
      const r = el.getBoundingClientRect();
      return [r.top, r.bottom, r.left, r.right];
    }));
    let last = where();
    let steadyFrames = 0;
    let frames = 0;
    const step = () => {
      const now = where();
      steadyFrames = now === last ? steadyFrames + 1 : 0;
      last = now;
      frames += 1;
      if (steadyFrames >= 3) resolve();
      else if (frames > 300) reject(new Error('The panel did not stand still.'));
      else requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }));
}

async function waitForPlayers(g, count) {
  await g.page.waitForFunction(
    (want) => document.querySelectorAll('#lobby-players .player').length === want, count, { timeout: 5000 });
  await waitForSteadyPanel(g);
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
  const playersHeading = [...middle.children].find((el) => el.tagName === 'H2' && el.textContent === 'Players');
  const roundHeading = [byId('duel-heading'), document.querySelector('#classic-progress h2')]
    .find((el) => shown(el)) || null;
  const headingStyle = (el) => {
    if (!el) return null;
    const style = getComputedStyle(el);
    return [style.fontSize, style.fontWeight, style.letterSpacing, style.textTransform, style.lineHeight].join(' ');
  };
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
    playersHeading: rect(playersHeading),
    // The heading of the mode panel that is shown, and its look.
    roundHeading: rect(roundHeading),
    roundHeadingStyle: headingStyle(roundHeading),
    playersHeadingStyle: headingStyle(playersHeading),
    classicParts: ['classic-own-name', 'classic-task', 'classic-progress-label'].map((id) => rect(byId(id)))
      .concat([rect(document.querySelector('#classic-progress h2')), rect(document.querySelector('.classic-progress-track'))]),
    // From the top: heading, own name, task card, "Group progress", label, bar.
    classicOrder: [
      document.querySelector('#classic-progress h2'), byId('classic-own-name'), byId('classic-task'),
      document.querySelector('#classic-progress h3'), byId('classic-progress-label'),
      document.querySelector('.classic-progress-track'),
    ].map((el) => (rect(el) ? rect(el).top : null)),
    classicHeadingText: (document.querySelector('#classic-progress h2') || {}).textContent || null,
    classicTaskText: byId('classic-task') ? byId('classic-task').innerText : null,
    classicTaskGreen: byId('classic-task') ? byId('classic-task').classList.contains('duel-next-finished') : null,
    // Each bullet: its name, whether it is marked done, and how it looks.
    classicTaskItems: [...document.querySelectorAll('#classic-task li')].map((row) => ({
      name: row.firstChild ? row.firstChild.textContent : '',
      done: row.classList.contains('round-task-done'),
      saysDone: row.textContent.endsWith(' (done)'),
      line: getComputedStyle(row).textDecorationLine,
      opacity: Number(getComputedStyle(row).opacity),
      bullet: getComputedStyle(row).display === 'list-item' && getComputedStyle(row).listStyleType !== 'none',
      top: row.getBoundingClientRect().top,
    })),
    classicTaskNote: (document.querySelector('#classic-task .round-task-note') || {}).textContent || null,
    classicTaskNoteTop: document.querySelector('#classic-task .round-task-note')
      ? document.querySelector('#classic-task .round-task-note').getBoundingClientRect().top : null,
    classicOwnNameText: byId('classic-own-name').textContent,
    extraParagraph: rect(byId('test-extra-paragraph')),
    classicTrack: rect(document.querySelector('.classic-progress-track')),
  };
}

const look = (g) => g.page.evaluate(measurePanel);

async function shoot(g, name) {
  if (shotFolder) await g.page.screenshot({ path: `${shotFolder}/${name}${shotSuffix}.png` });
}

(async () => {
  const browser = await chromium.launch();
  const out = { lobby: null, duel: {}, solo: {}, classic: {}, classicWithHint: null };
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
    await waitForPlayers(host, 8);
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
      if (size.width === 1280) await shoot(watcher, 'duel');
    }

    // Everybody leaves the Duel. One guest plays Solo alone, the host and
    // four guests play Classic.
    await resize(host, SIZES[0]);
    for (const g of [host, ...others]) await leave(g);

    const alone = others[7 - 1];
    await createLobby(alone);
    await startRound(alone, 'Solo');
    await waitForClock(alone);
    for (const size of SIZES) {
      await resize(alone, size);
      out.solo[`${size.width}x${size.height}`] = await look(alone);
      if (size.width === 1280) await shoot(alone, 'solo');
    }

    const classicCode = await createLobby(host);
    const classicGuests = others.slice(0, 4);
    for (const g of classicGuests) await join(g, classicCode);
    await waitForPlayers(host, 5);
    await startRound(host, 'Classic');
    const classicWatcher = classicGuests[0];
    for (const g of [host, classicWatcher]) {
      await g.page.waitForSelector('#classic-progress:not([hidden])', { timeout: 10000 });
      // The role card lies over the screen for a few seconds at the start.
      await g.page.waitForSelector('#classic-role-card', { state: 'hidden', timeout: 15000 });
    }
    for (const size of SIZES) {
      await resize(host, size);
      await resize(classicWatcher, size);
      out.classic[`${size.width}x${size.height}`] = { host: await look(host), guest: await look(classicWatcher) };
      if (size.width === 1280) await shoot(classicWatcher, 'classic');
    }
    // Every Classic page: its role, the own list it was sent, and its card.
    const classicPages = [host, ...classicGuests];
    out.classicCards = [];
    for (const g of classicPages) {
      await resize(g, SIZES[0]);
      const role = (g.received.find((message) => message.type === 'classic_role') || {}).role || null;
      const sent = g.received.filter((message) => 'task_stations' in message).map((message) => message.task_stations);
      const own = sent.length ? sent[sent.length - 1] : null;
      const names = await g.page.evaluate((stations) => (stations || []).map((id) => (typeof window.Game.duel.stationName === 'function' ? window.Game.duel.stationName(id) : null)), own);
      const seen = await look(g);
      out.classicCards.push({ label: g.label, isHost: g === host, role, taskStations: own, names,
        cardText: seen.classicTaskText, cardGreen: seen.classicTaskGreen, pageText: await g.page.innerText('body') });
    }
    const highPerformer = classicPages.find((g, i) => g !== host && out.classicCards[i].role === 'HP');
    const freeRider = classicPages.find((g, i) => out.classicCards[i].role === 'FR');
    if (highPerformer) await shoot(highPerformer, 'classic_hp');
    if (freeRider) await shoot(freeRider, 'classic_fr');

    // A High Performer finishes its stations: the page is handed the
    // `station_done` the server sends then (same shape, with the own list).
    out.classicDone = [];
    if (highPerformer) {
      const card = out.classicCards[classicPages.indexOf(highPerformer)];
      const remaining = (card.taskStations || []).slice();
      while (remaining.length) {
        const station = remaining.shift();
        const before = (await look(highPerformer)).classicTaskText;
        highPerformer.inject({ type: 'station_done', station, task_stations: remaining.slice() });
        // Until the card has changed; a card that never does is reported as it is.
        await highPerformer.page.waitForFunction((text) => document.getElementById('classic-task').innerText !== text,
          before, { timeout: 3000 }).catch(() => {});
        const seen = await look(highPerformer);
        out.classicDone.push({ station, left: remaining.slice(), cardText: seen.classicTaskText, cardGreen: seen.classicTaskGreen,
          items: seen.classicTaskItems, note: seen.classicTaskNote, noteTop: seen.classicTaskNoteTop });
        if (out.classicDone.length === 1) await shoot(highPerformer, 'classic_hp_one_done');
        if (remaining.length === 0) await shoot(highPerformer, 'classic_hp_all_done');
      }
    }

    await resize(classicWatcher, SIZES[0]);
    await classicWatcher.page.evaluate(() => {
      const extra = document.createElement('p');
      extra.id = 'test-extra-paragraph';
      extra.textContent = 'Hidden';
      document.getElementById('classic-progress').appendChild(extra);
    });
    await waitForSteadyPanel(classicWatcher);
    out.classicWithHint = await look(classicWatcher);
  } finally {
    out.console = problems;
    console.log(JSON.stringify(out));
    await browser.close();
  }
})().catch((e) => { console.error(e); process.exit(1); });
