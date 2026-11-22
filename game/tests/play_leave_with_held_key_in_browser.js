// Browser part of test_play_leave_with_held_key.py (M2-2.12).
// Needs Playwright and Chromium.
//
// Usage: node play_leave_with_held_key_in_browser.js <base-url>
// Prints one JSON object:
//   console    every console error or warning and page error
//   scenarios  per scenario (see SCENARIOS): the messages the page sent and
//              received from the creation of the lobby on, the screen and
//              the message shown at the end, and whether the Home screen
//              was already shown when the keys were released
//   again      on a page that has just left with a key held, after joining a
//              new lobby: what one short walk sent
//   refused    a `move` sent by hand on the Home screen: the answer and the
//              message shown
//
// Every scenario has its own guest on its own page, with its own log, so a
// message shown in one scenario cannot be seen in the next. The WebSocket
// of each page is routed through this script, which writes down every
// message both ways. While a scenario asks for it, the answer `left_lobby`
// is held back for HOLD_MS, so keys can be released for sure before it
// arrives.
const { chromium } = require('playwright');

const base = process.argv[2];
const problems = [];
const HOLD_MS = 800;

// keys:     walking keys held while "Leave lobby" is clicked
// hold:     whether the answer `left_lobby` is held back
// released: when each key is let go: "before" the answer, "after" the Home
//           screen shows
const SCENARIOS = {
  release_before_answer: { keys: ['KeyD'], hold: true, released: ['before'] },
  release_after_answer: { keys: ['KeyD'], hold: false, released: ['after'] },
  two_keys_before_answer: { keys: ['KeyD', 'KeyS'], hold: true, released: ['before', 'before'] },
  two_keys_one_before_one_after: { keys: ['ArrowLeft', 'ArrowUp'], hold: true, released: ['before', 'after'] },
  no_key_held: { keys: [], hold: false, released: [] },
};

// A new guest on its own page. `guest.log` holds { way: 'sent' | 'received',
// message } for its WebSocket; `guest.holdLeftLobby` holds the answer back.
async function newGuest(browser, label) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const guest = { page, log: [], holdLeftLobby: false };
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') problems.push(`${label} ${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`${label} page error: ${e.message}`));
  await routeSocket(guest);
  await page.goto(base + '/');
  await page.click('#start-guest');
  await page.waitForSelector('#screen-home:not([hidden])');
  return guest;
}

async function routeSocket(guest) {
  await guest.page.routeWebSocket(/\/ws$/, (ws) => {
    const server = ws.connectToServer();
    ws.onMessage((text) => {
      guest.log.push({ way: 'sent', message: JSON.parse(text) });
      server.send(text);
    });
    server.onMessage((text) => {
      const message = JSON.parse(text);
      const forward = () => {
        guest.log.push({ way: 'received', message });
        ws.send(text);
      };
      if (message.type === 'left_lobby' && guest.holdLeftLobby) setTimeout(forward, HOLD_MS);
      else forward();
    });
  });
}

async function createLobby(page) {
  await page.click('#home-create');
  await page.waitForSelector('#screen-lobby:not([hidden])');
  await page.waitForFunction(() => /[A-Z]{4}/.test(document.getElementById('lobby-code').textContent));
  await page.waitForTimeout(500); // the world has started and the map is drawn
}

async function screenAndMessage(page) {
  return page.evaluate(() => {
    const message = document.getElementById('message');
    return {
      home: !document.getElementById('screen-home').hidden,
      lobby: !document.getElementById('screen-lobby').hidden,
      messageShown: !message.hidden,
      messageText: message.textContent,
      messageIsError: message.classList.contains('message-error'),
    };
  });
}

async function releaseKeys(page, scenario, when) {
  for (let i = 0; i < scenario.keys.length; i++) {
    if (scenario.released[i] === when) await page.keyboard.up(scenario.keys[i]);
  }
}

async function play(guest, scenario) {
  const page = guest.page;
  await createLobby(page);
  const start = guest.log.length;
  for (const key of scenario.keys) {
    await page.keyboard.down(key);
    await page.waitForTimeout(250);
  }
  guest.holdLeftLobby = scenario.hold;
  await page.click('#lobby-leave');
  await releaseKeys(page, scenario, 'before');
  const homeAtRelease = (await screenAndMessage(page)).home;
  await page.waitForSelector('#screen-home:not([hidden])', { timeout: 5000 });
  await releaseKeys(page, scenario, 'after');
  await page.waitForTimeout(600); // time for a refusal to come back, if one were caused
  guest.holdLeftLobby = false;
  return { homeAtRelease, frames: guest.log.slice(start), ...(await screenAndMessage(page)) };
}

(async () => {
  const browser = await chromium.launch();
  const out = { scenarios: {}, again: null, refused: null };
  try {
    for (const [name, scenario] of Object.entries(SCENARIOS)) {
      out.scenarios[name] = await play(await newGuest(browser, name), scenario);
    }

    // Leaving with a key held, then a new lobby: a short walk is sent again.
    const walker = await newGuest(browser, 'again');
    await play(walker, SCENARIOS.release_before_answer);
    await createLobby(walker.page);
    const start = walker.log.length;
    await walker.page.keyboard.down('KeyD');
    await walker.page.waitForTimeout(300);
    await walker.page.keyboard.up('KeyD');
    await walker.page.waitForTimeout(400);
    out.again = { frames: walker.log.slice(start), ...(await screenAndMessage(walker.page)) };

    // The server still refuses a real `move` outside a lobby.
    const refused = await newGuest(browser, 'refused');
    await refused.page.evaluate(() => window.Game.net.send({ type: 'move', dx: 1, dy: 0 }));
    await refused.page.waitForFunction(() => !document.getElementById('message').hidden, null, { timeout: 3000 });
    out.refused = { frames: refused.log.slice(), ...(await screenAndMessage(refused.page)) };
  } finally {
    // The refusal above is wanted; a console error is still not.
    out.console = problems;
    console.log(JSON.stringify(out));
    await browser.close();
  }
})().catch((e) => { console.error(e); process.exit(1); });
