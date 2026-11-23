// Browser part of test_play_keyboard_notice.py (M4-2.2). Needs Playwright
// and Chromium.
//
// Usage: node play_keyboard_notice_in_browser.js <base-url> [<screenshot-folder>]
// Prints one JSON object: per scenario what the page showed (see `look`),
// plus `console` with every console error or warning and page error.
// With a screenshot folder it also saves phone_notice.png and
// phone_after_play_anyway.png (390x844).
const { chromium } = require('playwright');

const base = process.argv[2];
const shots = process.argv[3];
const problems = [];

// A phone as Chromium emulates it: a finger as the only pointer, no hover.
const PHONE = { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 };
const DESKTOP = { viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 };
// Touch screens in portrait and landscape at the sizes of the brief.
const SIZES = [[320, 640], [640, 320], [800, 1000], [1000, 800]];

async function open(browser, options, label, before) {
  const context = await browser.newContext(options);
  if (before) await context.addInitScript(before);
  const page = await context.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') problems.push(`${label} ${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`${label} page error: ${e.message}`));
  await page.goto(base + '/');
  await page.waitForSelector('#screen-start:not([hidden])', { state: 'attached' });
  return { context, page };
}

// What the page shows now: the notice, its parts and whether they fit.
function look(page) {
  return page.evaluate(() => {
    const notice = document.getElementById('keyboard-notice');
    const box = (id) => {
      const r = document.getElementById(id).getBoundingClientRect();
      return { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
    };
    const main = document.querySelector('main');
    return {
      shown: !notice.hidden && getComputedStyle(notice).display !== 'none',
      role: notice.getAttribute('role'),
      modal: notice.getAttribute('aria-modal'),
      heading: document.getElementById('keyboard-notice-title').textContent,
      text: document.getElementById('keyboard-notice-text').textContent,
      buttonText: document.getElementById('keyboard-notice-play').textContent,
      focused: document.activeElement && document.activeElement.id,
      behindInert: main.hasAttribute('inert'),
      viewport: { width: window.innerWidth, height: window.innerHeight },
      scrollWidth: document.documentElement.scrollWidth,
      noticeScrollWidth: notice.scrollWidth,
      noticeClientWidth: notice.clientWidth,
      title: box('keyboard-notice-title'),
      paragraph: box('keyboard-notice-text'),
      button: box('keyboard-notice-play'),
      card: (() => {
        const r = document.querySelector('.keyboard-notice-card').getBoundingClientRect();
        return { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
      })(),
    };
  });
}

// Signs in as a guest and creates a lobby: the page is usable.
async function reachLobby(page) {
  await page.click('#start-guest');
  await page.waitForSelector('#screen-home:not([hidden])');
  await page.click('#home-create');
  await page.waitForSelector('#screen-lobby:not([hidden])');
  return (await page.textContent('#lobby-code')).trim();
}

(async () => {
  const browser = await chromium.launch();
  const result = {};
  try {
    // 1. Phone: the notice, "Play anyway", the lobby, a reload in the same tab.
    {
      const { context, page } = await open(browser, PHONE, 'phone');
      const first = await look(page);
      if (shots) await page.screenshot({ path: `${shots}/phone_notice.png` });
      // A tap behind the notice reaches nothing while it shows.
      let tapBehind = 'reached';
      try {
        await page.click('#start-guest', { timeout: 800 });
      } catch (error) {
        tapBehind = 'blocked';
      }
      const homeAfterTap = await page.isVisible('#screen-home');
      await page.tap('#keyboard-notice-play');
      const closed = await look(page);
      if (shots) await page.screenshot({ path: `${shots}/phone_after_play_anyway.png` });
      const lobbyCode = await reachLobby(page);
      await page.reload();
      await page.waitForSelector('#screen-start:not([hidden])', { state: 'attached' });
      const afterReload = await look(page);
      await context.close();
      result.phone = { first, tapBehind, homeAfterTap, closed, lobbyCode, afterReload };
    }

    // 2. A new tab of the same phone is a new visit: the notice is back.
    {
      const { context, page } = await open(browser, PHONE, 'phone again');
      result.newVisit = await look(page);
      await context.close();
    }

    // 3. Sizes in portrait and landscape: everything fits, nothing overlaps.
    result.sizes = [];
    for (const [width, height] of SIZES) {
      const { context, page } = await open(browser, { ...PHONE, viewport: { width, height } }, `touch ${width}x${height}`);
      result.sizes.push({ width, height, seen: await look(page) });
      await context.close();
    }

    // 4. A real key press of a walking key closes it; a script's does not.
    {
      const { context, page } = await open(browser, PHONE, 'key');
      await page.evaluate(() => window.dispatchEvent(new KeyboardEvent('keydown', { code: 'KeyD', key: 'd' })));
      const afterScriptKey = await look(page);
      await page.keyboard.press('KeyE');
      const afterOtherKey = await look(page);
      await page.keyboard.press('ArrowUp');
      const afterWalkingKey = await look(page);
      await context.close();
      result.keys = { afterScriptKey, afterOtherKey, afterWalkingKey };
    }

    // 5. Storage that fails: "Play anyway" still closes, the next load asks again.
    {
      const breakStorage = () => {
        Storage.prototype.getItem = () => { throw new Error('blocked'); };
        Storage.prototype.setItem = () => { throw new Error('blocked'); };
      };
      const { context, page } = await open(browser, PHONE, 'no storage', breakStorage);
      const first = await look(page);
      await page.tap('#keyboard-notice-play');
      const closed = await look(page);
      await page.reload();
      await page.waitForSelector('#screen-start:not([hidden])', { state: 'attached' });
      const afterReload = await look(page);
      await context.close();
      result.noStorage = { first, closed, afterReload };
    }

    // 6. Desktop browser: never a notice, the game as before.
    {
      const { context, page } = await open(browser, DESKTOP, 'desktop');
      const seen = await look(page);
      const lobbyCode = await reachLobby(page);
      await context.close();
      result.desktop = { seen, lobbyCode };
    }

    // 7. A narrow desktop window (as test_narrow_windows): no notice either.
    {
      const { context, page } = await open(browser, { viewport: { width: 320, height: 640 } }, 'narrow desktop');
      result.narrowDesktop = await look(page);
      await context.close();
    }
  } finally {
    await browser.close();
  }
  result.console = problems;
  process.stdout.write(JSON.stringify(result));
})().catch((error) => {
  process.stderr.write(String(error && error.stack || error));
  process.exit(1);
});
