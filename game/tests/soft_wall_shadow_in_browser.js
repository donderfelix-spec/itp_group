// Draws the Classic fog of client/js/world/vision.js in Chromium, the soft
// one (darkenSoftly, S-214) and the hard one (darken), each on an empty
// canvas, and prints the fog's colour and alpha at the map points given.
// For tests/test_classic_soft_wall_shadow.py:
//
//   node soft_wall_shadow_in_browser.js '{"origin": [x, y], "points": {"name": [x, y]}}'
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

const request = JSON.parse(process.argv[2]);
const world = path.join(__dirname, '..', 'client', 'js', 'world');

(async () => {
  const browser = await chromium.launch();
  try {
    const page = await (await browser.newContext({ viewport: { width: 1100, height: 800 }, deviceScaleFactor: 1 })).newPage();
    await page.setContent('<canvas id="soft" width="1040" height="740"></canvas><canvas id="hard" width="1040" height="740"></canvas>');
    await page.evaluate('window.Game = { world: {} }');
    await page.addScriptTag({ path: path.join(world, 'vision.js') });
    const campus = JSON.parse(fs.readFileSync(path.join(world, 'campus.json'), 'utf8'));
    const out = await page.evaluate(({ campus, request }) => {
      const vision = Game.world.vision;
      const origin = { x: request.origin[0], y: request.origin[1] };
      const scale = 4; // canvas pixels per map unit, about the game's zoom
      const read = (id, draw) => {
        const canvas = document.getElementById(id);
        const ctx = canvas.getContext('2d');
        const view = { x: origin.x - canvas.width / scale / 2, y: origin.y - canvas.height / scale / 2, w: canvas.width / scale, h: canvas.height / scale };
        ctx.setTransform(scale, 0, 0, scale, canvas.width / 2 - origin.x * scale, canvas.height / 2 - origin.y * scale);
        const answer = draw(ctx, view);
        const pixels = {};
        for (const [name, [x, y]] of Object.entries(request.points)) {
          const px = Math.round((x - view.x) * scale);
          const py = Math.round((y - view.y) * scale);
          pixels[name] = Array.from(ctx.getImageData(px, py, 1, 1).data);
        }
        const all = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
        let darkest = 0;
        for (let i = 3; i < all.length; i += 4) darkest = Math.max(darkest, all[i]);
        return { answer, pixels, darkest };
      };
      return {
        soft: read('soft', (ctx, view) => vision.darkenSoftly(ctx, view, campus, origin)),
        hard: read('hard', (ctx, view) => vision.darken(ctx, view, vision.boundary(campus, origin), origin, vision.rangeOf(campus))),
      };
    }, { campus, request });
    process.stdout.write(JSON.stringify(out) + '\n');
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
