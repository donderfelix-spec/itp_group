// Browser part of test_emergency_button_art.py (M3-4.24). Needs Playwright
// and Chromium.
//
// Usage: node emergency_button_art_in_browser.js <base-url>
// Prints one JSON object:
//   console   every console error or warning and page error of the page
//   scale     pixels per map unit of the pictures (4)
//   button    campus.button as the page loads it
//   drawn     the pixels the button adds, for three buttons:
//               real      the button of campus.json
//               moved     the same button 6 units to the right
//               enlarged  the same button with radius 14
//             each a list of [px, py, red, green, blue]: the pixel's place
//             on the canvas and its colour with the button
//   hidden    how many pixels change when the button is hidden: drawMap
//             with emergencyVisible false, and with it left out, against
//             the map without any button
//
// How it is measured: the page's own Game.world.drawMap draws the whole map
// at 4 pixels per unit with emergencyVisible true and false. A pixel is
// added by the button when one of its colour channels differs by more than
// CHANGED between the two pictures.
const { chromium } = require('playwright');

const base = process.argv[2];

function measure() {
  return (async () => {
    const campus = await (await fetch('js/world/campus.json')).json();
    const SCALE = 4;
    const CHANGED = 8;
    const width = campus.width * SCALE;
    const height = campus.height * SCALE;

    function render(map, emergencyVisible) {
      const canvas = document.createElement('canvas');
      canvas.width = width; canvas.height = height;
      const ctx = canvas.getContext('2d');
      ctx.setTransform(SCALE, 0, 0, SCALE, 0, 0);
      Game.world.drawMap(ctx, map, null, emergencyVisible, [], 0);
      return ctx.getImageData(0, 0, width, height).data;
    }

    function differences(withButton, without) {
      const pixels = [];
      for (let i = 0; i < withButton.length; i += 4) {
        const changed = [0, 1, 2].some((c) => Math.abs(withButton[i + c] - without[i + c]) > CHANGED);
        if (changed) {
          const index = i / 4;
          pixels.push([index % width, Math.floor(index / width), withButton[i], withButton[i + 1], withButton[i + 2]]);
        }
      }
      return pixels;
    }

    function withButton(button) {
      return Object.assign({}, campus, { button });
    }

    const noButton = Object.assign({}, campus);
    delete noButton.button;
    const bare = render(noButton, true);
    const b = campus.button;
    const buttons = {
      real: b,
      moved: { x: b.x + 6, y: b.y, r: b.r },
      enlarged: { x: b.x, y: b.y, r: 14 },
    };
    const drawn = {};
    for (const name of Object.keys(buttons)) {
      drawn[name] = differences(render(withButton(buttons[name]), true), bare);
    }
    const hidden = {
      visibleFalse: differences(render(campus, false), bare).length,
      leftOut: differences(render(campus, undefined), bare).length,
    };
    return { scale: SCALE, button: b, drawn, hidden };
  })();
}

(async () => {
  const browser = await chromium.launch();
  const problems = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    page.on('console', (m) => {
      if (m.type() === 'error' || m.type() === 'warning') problems.push(`${m.type()}: ${m.text()}`);
    });
    page.on('pageerror', (e) => problems.push(`page error: ${e.message}`));
    await page.goto(base + '/');
    await page.waitForFunction(() => window.Game && Game.world && Game.world.drawMap);
    const result = await page.evaluate(measure);
    result.console = problems;
    process.stdout.write(JSON.stringify(result) + '\n');
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
