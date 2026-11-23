// Browser part of test_hiding_objects.py (M3-1.5). Needs Playwright and
// Chromium.
//
// Usage: node hiding_objects_in_browser.js <base-url>
// Prints one JSON object:
//   console  every console error or warning and page error of the page
//   spots    for each hiding spot of campus.json, in its order:
//              x, y, r      its place and radius
//              room         the id of its room, or null on the deck
//              hasObject    true when an art file draws an object for it
//              inside       how many pixels inside its circle differ from
//                           the map without hiding spots
//              outside      how many differing pixels lie further than the
//                           spot's radius plus REACH from its centre
//              onOthers     the ids of the solids (other than a walkable
//                           one) and stations whose rectangle holds a
//                           differing pixel
//              fallback     how many pixels inside the circle differ when
//                           its drawing is missing (the dashed circle)
//
// How it is measured: the page's own Game.world.drawMap draws the whole map
// at 4 pixels per unit, with and without `hiding_spots`, without stations.
// A pixel differs when red + green + blue differ by more than 30.
const { chromium } = require('playwright');

const base = process.argv[2];

function measure() {
  return (async () => {
    const campus = await (await fetch('js/world/campus.json')).json();
    const S = 4; const W = campus.width; const H = campus.height;
    const CLEAR = 30;
    const REACH = 4; // DRAWING_OVERHANG in draw.js

    // A fresh copy of the map each time, so drawMap never reuses old tiles.
    function render(map) {
      const canvas = document.createElement('canvas');
      canvas.width = W * S; canvas.height = H * S;
      const ctx = canvas.getContext('2d');
      ctx.setTransform(S, 0, 0, S, 0, 0);
      Game.world.drawMap(ctx, JSON.parse(JSON.stringify(map)), null, false, [], 0);
      return ctx.getImageData(0, 0, W * S, H * S).data;
    }

    function differing(first, second) {
      const found = [];
      for (let i = 0; i < first.length; i += 4) {
        const change = Math.abs(first[i] - second[i]) + Math.abs(first[i + 1] - second[i + 1])
          + Math.abs(first[i + 2] - second[i + 2]);
        if (change > CLEAR) {
          const pixel = i / 4;
          found.push({ x: (pixel % (W * S) + 0.5) / S, y: (Math.floor(pixel / (W * S)) + 0.5) / S });
        }
      }
      return found;
    }

    const noStations = { ...campus, stations: [] };
    const without = render({ ...noStations, hiding_spots: [] });

    function inRect(point, rect) {
      return point.x >= rect.x && point.x <= rect.x + rect.w && point.y >= rect.y && point.y <= rect.y + rect.h;
    }

    const others = campus.solids.filter((solid) => solid.walkable !== true)
      .concat(campus.stations.map((station) => ({
        id: `station ${station.id}`, x: station.x - station.r, y: station.y - station.r, w: 2 * station.r, h: 2 * station.r,
      })));

    const spots = campus.hiding_spots.map((spot) => {
      const room = Game.world.roomAt(campus, spot.x, spot.y);
      const drawing = Game.world.hidingObjectOf(campus, spot);
      const changed = differing(render({ ...noStations, hiding_spots: [spot] }), without);
      const distance = (point) => Math.hypot(point.x - spot.x, point.y - spot.y);
      const onOthers = new Set();
      changed.forEach((point) => others.forEach((other) => { if (inRect(point, other)) onOthers.add(other.id); }));

      // The same spot with its drawing taken away: the dashed circle.
      const group = Game.world.art.hiding;
      const key = Object.keys(group).find((name) => group[name] === drawing);
      let fallback = null;
      if (key) {
        delete group[key];
        fallback = differing(render({ ...noStations, hiding_spots: [spot] }), without)
          .filter((point) => distance(point) <= spot.r).length;
        group[key] = drawing;
      }
      return {
        x: spot.x, y: spot.y, r: spot.r, room: room ? room.id : null, hasObject: typeof drawing === 'function',
        inside: changed.filter((point) => distance(point) <= spot.r).length,
        outside: changed.filter((point) => distance(point) > spot.r + REACH).length,
        onOthers: [...onOthers].sort(),
        fallback,
      };
    });
    return { spots };
  })();
}

(async () => {
  const browser = await chromium.launch();
  const problems = [];
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') problems.push(`${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`page error: ${e.message}`));
  await page.goto(base + '/');
  await page.waitForFunction(() => window.Game && Game.world && typeof Game.world.hidingObjectOf === 'function');
  const result = await page.evaluate(measure);
  console.log(JSON.stringify({ console: problems, ...result }));
  await browser.close();
})();
