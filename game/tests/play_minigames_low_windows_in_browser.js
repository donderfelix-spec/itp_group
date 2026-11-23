// Browser part of test_play_minigames_low_windows.py (M2-4.25; station 6 since M4-4.0).
// Needs Playwright and Chromium.
//
// Usage: node play_minigames_low_windows_in_browser.js <base-url> <openings.json>
// <openings.json> is a list of { station, title, content } drawn by the server's
// own minigames. Each is opened with the real frame (Game.minigames.open) over
// the map of a guest's lobby, in windows of 1280x800, 1024x700, 1280x600,
// 1024x600 and 320x640. Prints one JSON object:
//   console   every console error or warning and page error
//   seen      per window size and opening: the viewport, the window's box and
//             its visible box (inside its border), how far its content
//             reaches past it sideways, and the box of every control
//             (button, select) and of the instruction
const { chromium } = require('playwright');
const fs = require('fs');

const [base, openingsFile] = process.argv.slice(2);
const openings = JSON.parse(fs.readFileSync(openingsFile, 'utf8'));
const SIZES = [
  { width: 1280, height: 800 }, { width: 1024, height: 700 },
  { width: 1280, height: 600 }, { width: 1024, height: 600 }, { width: 320, height: 640 },
];
const problems = [];

// What one open window shows. Runs in the page.
function look() {
  const card = document.querySelector('.minigame-window');
  const box = (el) => {
    const r = el.getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height };
  };
  const shown = (el) => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
  const name = (el) => (el.getAttribute('aria-label') || el.textContent || el.tagName).trim().slice(0, 40);
  const outer = box(card);
  // The part of the window that shows content: inside its border.
  const inner = { x: outer.x + card.clientLeft, y: outer.y + card.clientTop, w: card.clientWidth, h: card.clientHeight };
  // The sentence in the header (station 6), or the task's own brief (7 to 12,
  // whose header sentence is empty and not shown).
  const instructions = [...card.querySelectorAll('.minigame-instructions, .campus-instruction, .challenge-brief')].filter(shown);
  return {
    viewport: { w: innerWidth, h: innerHeight },
    window: outer,
    inside: inner,
    sideways: card.scrollWidth - card.clientWidth,
    controls: [...card.querySelectorAll('button, select')].filter(shown).map((el) => ({ name: name(el), ...box(el) })),
    instructions: instructions.map((el) => ({ name: name(el), ...box(el) })),
  };
}

(async () => {
  const browser = await chromium.launch();
  const seen = {};
  try {
    for (const viewport of SIZES) {
      const label = `${viewport.width}x${viewport.height}`;
      const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
      const page = await context.newPage();
      page.on('console', (m) => {
        if (m.type() === 'error' || m.type() === 'warning') problems.push(`${label} ${m.type()}: ${m.text()}`);
      });
      page.on('pageerror', (e) => problems.push(`${label} page error: ${e.message}`));
      await page.goto(base + '/');
      await page.click('#start-guest');
      await page.waitForSelector('#screen-home:not([hidden])');
      await page.click('#home-create');
      await page.waitForSelector('#screen-lobby:not([hidden])');
      seen[label] = [];
      for (const opening of openings) {
        const shownNow = await page.evaluate(({ station, title, content }) => Game.minigames.open(station, title, content), opening);
        await page.waitForTimeout(150); // fonts and layout settle
        seen[label].push({ station: opening.station, shown: shownNow, ...(await page.evaluate(look)) });
        await page.evaluate(() => Game.minigames.close());
      }
      await context.close();
    }
  } finally {
    console.log(JSON.stringify({ console: problems, seen }));
    await browser.close();
  }
})().catch((e) => { console.error(e); process.exit(1); });
