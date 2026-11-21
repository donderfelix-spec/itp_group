// Browser part of test_play_campus_detail.py (M2-1.4). Needs Playwright and Chromium.
//
// Usage: node play_campus_detail_in_browser.js <base-url>
// Prints one JSON object:
//   console    every console error or warning and page error of both pages
//   coverage   for every solid other than a wall: the share of its rectangle
//              that is drawn (an invisible blocker has almost nothing drawn)
//   overhang   the farthest a drawing reaches from the nearest solid into
//              floor that a player's box can cover, in map units, with where
//
// What is "drawn": the page's own Game.world.drawMap draws the map twice at
// 4 pixels per unit, once as it is and once with only the walls as solids and
// without the decor that stands on solids. Units that differ are furniture.
const { chromium } = require('playwright');

const base = process.argv[2];
const KEYS = ['KeyD', 'KeyS', 'KeyA', 'KeyW'];
const SIZES = [[900, 700], [1600, 1000], [1280, 800]];

async function guest(browser, problems, label) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2 });
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

// Both guests hold each walk key in turn, while the first window is resized.
async function walkAndResize(a, b) {
  for (let i = 0; i < KEYS.length; i++) {
    await Promise.all([a.keyboard.down(KEYS[i]), b.keyboard.down(KEYS[(i + 2) % 4])]);
    await a.waitForTimeout(400);
    const [w, h] = SIZES[i % SIZES.length];
    await a.setViewportSize({ width: w, height: h });
    await a.waitForTimeout(400);
    await Promise.all([a.keyboard.up(KEYS[i]), b.keyboard.up(KEYS[(i + 2) % 4])]);
  }
}

function drawingCheck() {
  return (async () => {
    const campus = await (await fetch('js/world/campus.json')).json();
    const S = 4; const W = campus.width; const H = campus.height; const HALF = 5;
    function render(map) {
      const canvas = document.createElement('canvas');
      canvas.width = W * S; canvas.height = H * S;
      const ctx = canvas.getContext('2d');
      ctx.setTransform(S, 0, 0, S, 0, 0);
      Game.world.drawMap(ctx, map);
      return ctx.getImageData(0, 0, W * S, H * S).data;
    }
    const full = render(campus);
    const bare = render({
      ...campus,
      solids: campus.solids.filter((s) => s.kind === 'wall'),
      decor: (campus.decor || []).filter((d) => d.layer !== 'on'),
    });
    const drawn = new Uint8Array(W * H);
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      let differing = 0;
      for (let py = 0; py < S; py++) for (let px = 0; px < S; px++) {
        const i = ((y * S + py) * W * S + x * S + px) * 4;
        const d = Math.abs(full[i] - bare[i]) + Math.abs(full[i + 1] - bare[i + 1]) + Math.abs(full[i + 2] - bare[i + 2]);
        if (d > 60) differing++;
      }
      drawn[y * W + x] = differing >= 6 ? 1 : 0;
    }
    const solids = campus.solids;
    const free = (x, y) => x >= HALF && x <= W - HALF && y >= HALF && y <= H - HALF &&
      !solids.some((s) => x + HALF > s.x && x - HALF < s.x + s.w && y + HALF > s.y && y - HALF < s.y + s.h);
    // Every unit a player's box covers on some place reachable from the spawn.
    const seen = new Uint8Array((W + 1) * (H + 1));
    const covered = new Uint8Array(W * H);
    const waiting = [[campus.spawn.x, campus.spawn.y]];
    seen[campus.spawn.y * (W + 1) + campus.spawn.x] = 1;
    while (waiting.length) {
      const [x, y] = waiting.pop();
      for (let cy = y - HALF; cy < y + HALF; cy++) for (let cx = x - HALF; cx < x + HALF; cx++) covered[cy * W + cx] = 1;
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const nx = x + dx; const ny = y + dy;
        if (!seen[ny * (W + 1) + nx] && free(nx, ny)) { seen[ny * (W + 1) + nx] = 1; waiting.push([nx, ny]); }
      }
    }
    const coverage = solids.filter((s) => s.kind !== 'wall').map((s) => {
      let count = 0;
      for (let y = s.y; y < s.y + s.h; y++) for (let x = s.x; x < s.x + s.w; x++) count += drawn[y * W + x];
      return { id: s.id, share: count / (s.w * s.h) };
    });
    let overhang = { distance: 0 };
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      if (!drawn[y * W + x] || !covered[y * W + x]) continue;
      let nearest = null;
      for (const s of solids) {
        const gx = Math.max(s.x - (x + 1), 0, x - (s.x + s.w));
        const gy = Math.max(s.y - (y + 1), 0, y - (s.y + s.h));
        const distance = Math.hypot(gx, gy) + 1; // the unit itself lies outside the solid
        if (!nearest || distance < nearest.distance) nearest = { distance, id: s.id };
      }
      if (nearest.distance > overhang.distance) overhang = { distance: nearest.distance, at: [x, y], nearest: nearest.id };
    }
    return { coverage, overhang };
  })();
}

(async () => {
  const browser = await chromium.launch();
  const problems = [];
  const a = await guest(browser, problems, 'A');
  await a.click('#home-create');
  await a.waitForSelector('#screen-lobby:not([hidden])');
  await a.waitForFunction(() => /[A-Z0-9]{4}/.test(document.getElementById('lobby-code').textContent));
  const code = (await a.textContent('#lobby-code')).match(/[A-Z0-9]{4}/)[0];
  const b = await guest(browser, problems, 'B');
  await b.fill('#join-code', code);
  await b.click('#join-submit');
  await b.waitForSelector('#screen-lobby:not([hidden])');
  await walkAndResize(a, b);
  const check = await a.evaluate(drawingCheck);
  console.log(JSON.stringify({ console: problems, ...check }));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
