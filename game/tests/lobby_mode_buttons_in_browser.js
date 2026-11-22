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
//               button's text ends left of it)
// With a shots folder, it also saves the mode area of the host's panel at
// deviceScaleFactor 2 as modes_alone_duel.png and modes_two.png there.
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
  return { buttons, whys };
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

(async () => {
  const browser = await chromium.launch();
  const situations = {};
  try {
    if (shotsFolder) {
      situations.wide = await playViewport(browser, 'wide', { width: 1280, height: 800 }, 2);
    } else {
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
