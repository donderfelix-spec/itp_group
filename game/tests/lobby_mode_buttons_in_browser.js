// Browser part of test_lobby_mode_buttons.py (M2-2.13): how the mode
// buttons of the lobby look. Needs Playwright and Chromium.
//
// Usage: node lobby_mode_buttons_in_browser.js <base-url> [shots-folder]
// Prints one JSON object:
//   console     every console error or warning and page error of every page
//   situations  per viewport ("wide" 1280x800, "narrow" 320x640) and lobby
//               state ("alone_duel", "alone_solo", "two"):
//               every mode button (classes, colours, shadow, the pixel colour
//               of an empty spot) and every visible "?" (its gaps to the
//               button's inner border edge, whether a 24 x 24 box around its
//               centre hits it, whether a click on a corner of its tap square opens
//               (and pins) its text and a second click closes it, its
//               outline on keyboard focus, and that the room for the
//               button's text ends left of it), and the start button
//               "counts"    the same at 1280x800 with 1 to 4 players, with
//               Classic chosen by 4 ("four_classic") and after one of
//               them left ("three_classic")
// With a shots folder, it also saves the mode area of the host's panel at
// deviceScaleFactor 2 as modes_alone_duel.png, modes_two.png,
// modes_two_classic_locked.png, modes_four.png and
// modes_three_classic_chosen.png there.
const { chromium } = require('playwright');

const base = process.argv[2];
const shotsFolder = process.argv[3];
const problems = [];

async function guest(browser, label, viewport, scale) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: scale });
  const page = await context.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') problems.push(`${label} ${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`${label} page error: ${e.message}`));
  // How many lobby_state messages the page has received.
  page.lobbyStates = 0;
  page.on('websocket', (ws) => ws.on('framereceived', (f) => {
    if (String(f.payload).includes('"lobby_state"')) page.lobbyStates += 1;
  }));
  await page.goto(base + '/');
  await page.click('#start-guest');
  await page.waitForSelector('#screen-home:not([hidden])');
  return page;
}

async function createLobby(page) {
  await page.click('#home-create');
  await page.waitForSelector('#screen-lobby:not([hidden])');
  await page.waitForFunction(() => /[A-Z]{4}/.test(document.getElementById('lobby-code').textContent));
  return (await page.textContent('#lobby-code')).match(/[A-Z]{4}/)[0];
}

async function join(page, code) {
  await page.fill('#join-code', code);
  await page.click('#join-submit');
  await page.waitForSelector('#screen-lobby:not([hidden])');
}

async function chooseMode(page, modeId) {
  await page.click(`#lobby-modes > .mode[data-mode="${modeId}"]`);
  await page.waitForFunction((id) => document.querySelector(`#lobby-modes > .mode[data-mode="${id}"]`).classList.contains('mode-own'), modeId);
}

// The colour of one CSS pixel of the page, read from a screenshot drawn on
// a canvas (no image package needed).
async function pixelColours(page, points, scale) {
  const shot = (await page.screenshot()).toString('base64');
  return page.evaluate(async ({ shot, points, scale }) => {
    const image = new Image();
    image.src = 'data:image/png;base64,' + shot;
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = image.width;
    canvas.height = image.height;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(image, 0, 0);
    return points.map((p) => [...ctx.getImageData(Math.round(p.x * scale), Math.round(p.y * scale), 1, 1).data.slice(0, 3)]);
  }, { shot, points, scale });
}

// Every mode button: its look, and a spot without text to sample: in the
// bottom padding, a third of the way across.
async function readButtons(page, scale) {
  const buttons = await page.evaluate(() => [...document.querySelectorAll('#lobby-modes > .mode')].map((button) => {
    const r = button.getBoundingClientRect();
    const style = getComputedStyle(button);
    return {
      mode: button.dataset.mode,
      chosen: button.classList.contains('mode-own'),
      unfit: button.classList.contains('mode-unfit'),
      disabled: button.disabled,
      background: style.backgroundColor,
      opacity: style.opacity,
      boxShadow: style.boxShadow,
      borderColor: style.borderTopColor,
      spot: { x: r.left + r.width / 3, y: r.bottom - parseFloat(style.borderBottomWidth) - 2 },
    };
  }));
  const colours = await pixelColours(page, buttons.map((b) => b.spot), scale);
  buttons.forEach((b, i) => { b.pixel = colours[i]; });
  return buttons;
}

// Every visible "?": the gaps from its circle (its border box) to the inner
// border edge of its mode button, and whether the corners of a 24 x 24 box
// around its centre all hit it.
async function readWhyButtons(page) {
  return page.evaluate(() => [...document.querySelectorAll('#lobby-modes > .mode-why:not([hidden])')].map((why) => {
    const button = document.querySelector(`#lobby-modes > .mode[data-mode="${why.dataset.mode}"]`);
    const w = why.getBoundingClientRect();
    const b = button.getBoundingClientRect();
    const border = getComputedStyle(button);
    const cx = w.left + w.width / 2;
    const cy = w.top + w.height / 2;
    const corners = [[-11.5, -11.5], [11.5, -11.5], [-11.5, 11.5], [11.5, 11.5]];
    const hits = corners.every(([dx, dy]) => {
      const hit = document.elementFromPoint(cx + dx, cy + dy);
      return hit !== null && hit.closest('.mode-why') === why;
    });
    return {
      mode: why.dataset.mode,
      text: document.getElementById('mode-why-' + why.dataset.mode).textContent,
      size: { w: w.width, h: w.height },
      gaps: {
        top: w.top - (b.top + parseFloat(border.borderTopWidth)),
        bottom: (b.bottom - parseFloat(border.borderBottomWidth)) - w.bottom,
        right: (b.right - parseFloat(border.borderRightWidth)) - w.right,
      },
      hit24: hits,
      // The room the mode's text may take ends this far left of the circle.
      textRoomEnd: (b.right - parseFloat(border.borderRightWidth) - parseFloat(border.paddingRight)) - w.left,
    };
  }));
}

// A click on a corner of the 24 x 24 tap square (outside the visible
// circle) opens the text of the "?" and pins it: it stays open when the
// mouse has gone far away and the "?" has lost the focus, so neither the
// hover nor the focus is what keeps it open. A second click closes it.
async function clickOpens(page, modeId) {
  const selector = `#lobby-modes > .mode-why[data-mode="${modeId}"]`;
  const box = await page.locator(selector).boundingBox();
  const corner = { x: box.x + box.width / 2 + 11, y: box.y + box.height / 2 - 11 };
  const blur = () => page.evaluate(() => document.activeElement && document.activeElement.blur());
  await page.mouse.click(corner.x, corner.y);
  await page.mouse.move(0, 0);
  await blur();
  const opened = await page.getAttribute(selector, 'aria-expanded');
  await page.mouse.click(corner.x, corner.y);
  await page.mouse.move(0, 0);
  await blur();
  const closed = await page.getAttribute(selector, 'aria-expanded');
  return opened === 'true' && closed === 'false';
}

// Tab from the top of the page to the "?" and read its outline.
async function focusOutline(page, modeId) {
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press('Tab');
    const reached = await page.evaluate((id) => document.activeElement && document.activeElement.matches(`.mode-why[data-mode="${id}"]`), modeId);
    if (reached) break;
  }
  const outline = await page.evaluate((id) => {
    const why = document.querySelector(`.mode-why[data-mode="${id}"]`);
    const style = getComputedStyle(why);
    return { focused: document.activeElement === why, focusVisible: why.matches(':focus-visible'), style: style.outlineStyle, width: parseFloat(style.outlineWidth) };
  }, modeId);
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  return outline;
}

async function readSituation(page, scale) {
  const buttons = await readButtons(page, scale);
  const whys = await readWhyButtons(page);
  for (const why of whys) {
    why.clickOpens = await clickOpens(page, why.mode);
    why.outline = await focusOutline(page, why.mode);
  }
  const start = await page.evaluate(() => ({
    disabled: document.getElementById('lobby-start').disabled,
    hint: document.getElementById('lobby-start-hint').hidden ? '' : document.getElementById('lobby-start-hint').textContent,
  }));
  return { buttons, whys, start };
}

async function waitForMoreLobbyStates(page, before) {
  for (let i = 0; i < 100 && page.lobbyStates <= before; i++) await page.waitForTimeout(50);
  if (page.lobbyStates <= before) throw new Error('no new lobby_state arrived');
  await page.waitForTimeout(100); // let the page draw it
}

async function waitForPlayers(page, count) {
  await page.waitForFunction((n) => document.querySelectorAll('#lobby-players li').length === n, count);
}

async function saveModeArea(page, name) {
  const area = await page.locator('#lobby-modes').boundingBox();
  await page.screenshot({
    path: `${shotsFolder}/${name}`,
    clip: { x: area.x - 8, y: area.y - 8, width: area.width + 16, height: area.height + 16 },
  });
}

async function playViewport(browser, label, viewport, scale) {
  const host = await guest(browser, label + ' host', viewport, scale);
  const code = await createLobby(host);
  const result = {};
  await host.waitForSelector('#lobby-modes:not([hidden])');
  await host.waitForFunction(() => {
    const duel = document.querySelector('#lobby-modes > .mode[data-mode="duel"]');
    return duel.classList.contains('mode-own') && duel.classList.contains('mode-unfit');
  });
  result.alone_duel = await readSituation(host, scale);
  if (shotsFolder) await saveModeArea(host, 'modes_alone_duel.png');

  await chooseMode(host, 'solo');
  result.alone_solo = await readSituation(host, scale);

  // A second player joins while Solo is chosen. The server then switches
  // to Duel by itself (Solo is for one player alone), so Duel is chosen and
  // Solo does not fit.
  const other = await guest(browser, label + ' other', { width: 1280, height: 800 }, 1);
  await join(other, code);
  await host.waitForFunction(() => document.querySelector('#lobby-modes > .mode[data-mode="solo"]').classList.contains('mode-unfit'));
  result.two = await readSituation(host, scale);
  if (shotsFolder) await saveModeArea(host, 'modes_two.png');
  return result;
}

// 1, 2, 3 and 4 players at 1280x800 (a mode fits only between its
// minimum and maximum). With 4 the host chooses Classic, and it stays
// chosen after another lobby_state (a guest picks a character). Then one
// player leaves: Classic stays chosen, but no longer fits.
async function playCounts(browser, scale) {
  const viewport = { width: 1280, height: 800 };
  const host = await guest(browser, 'counts host', viewport, scale);
  const code = await createLobby(host);
  await host.waitForSelector('#lobby-modes:not([hidden])');
  await waitForPlayers(host, 1);
  const result = { one: await readSituation(host, scale) };
  const others = [];
  for (const [count, name] of [[2, 'two'], [3, 'three'], [4, 'four']]) {
    const other = await guest(browser, 'counts guest ' + count, viewport, 1);
    await join(other, code);
    others.push(other);
    await waitForPlayers(host, count);
    result[name] = await readSituation(host, scale);
    if (shotsFolder && count === 2) await saveModeArea(host, 'modes_two_classic_locked.png');
    if (shotsFolder && count === 4) await saveModeArea(host, 'modes_four.png');
  }

  await chooseMode(host, 'classic');
  // Another lobby_state: a guest picks another character.
  const statesBefore = host.lobbyStates;
  await others[0].click('#lobby-characters .character:not(:disabled):not(.character-own)');
  await waitForMoreLobbyStates(host, statesBefore);
  result.four_classic = await readSituation(host, scale);

  await others[2].click('#lobby-leave');
  await waitForPlayers(host, 3);
  result.three_classic = await readSituation(host, scale);
  if (shotsFolder) await saveModeArea(host, 'modes_three_classic_chosen.png');
  return result;
}

(async () => {
  const browser = await chromium.launch();
  const situations = {};
  try {
    if (shotsFolder) {
      situations.wide = await playViewport(browser, 'wide', { width: 1280, height: 800 }, 2);
      situations.counts = await playCounts(browser, 2);
    } else {
      situations.counts = await playCounts(browser, 1);
      situations.wide = await playViewport(browser, 'wide', { width: 1280, height: 800 }, 1);
      situations.narrow = await playViewport(browser, 'narrow', { width: 320, height: 640 }, 1);
    }
  } finally {
    await browser.close();
  }
  process.stdout.write(JSON.stringify({ console: problems, situations }));
})().catch((error) => {
  process.stderr.write(String(error && error.stack ? error.stack : error));
  process.exit(1);
});
