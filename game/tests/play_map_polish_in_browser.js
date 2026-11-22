// Browser part of test_map_polish.py (M2-1.20). Needs Playwright and Chromium.
//
// Usage: node play_map_polish_in_browser.js <base-url>
// Prints one JSON object:
//   console    every console error or warning and page error of the page
//   stations   for every station with an object, for each part of its
//              drawing (the object alone, the object with its outline at the
//              low and at the high point of the pulse, and the shadow and
//              number tag that draw.js adds, together and each alone): the
//              box of the part as offsets from the station's centre in whole
//              map units, and the units where a pixel of the part lies on
//              drawn furniture or a wall
//   roomNames  for every room the box of its drawn name, in map units
//   coverage   for every solid other than a wall: its id, kind and the share
//              of its rectangle that is drawn
//
// How it is measured: the page's own Game.world.drawMap draws the map at 4
// pixels per unit, the same way as play_campus_detail_in_browser.js:
//   - with the stations, not pulsing, pulsing low and pulsing high,
//   - with the stations' drawings replaced by nothing (shadow and tag only),
//   - without the stations,
//   - without the stations and with only the walls as solids (and without
//     the decor that stands on solids).
// A pixel counts when it differs clearly between two of these pictures, a
// unit (for the boxes) when 6 of its 16 pixels do. The last two pictures
// give the drawn furniture; a wall is the rectangle of a wall solid.
const { chromium } = require('playwright');

const base = process.argv[2];

function stationCheck() {
  return (async () => {
    const campus = await (await fetch('js/world/campus.json')).json();
    const S = 4; const W = campus.width; const H = campus.height;
    // The outline pulses between its low and its high point; the high point
    // is half way through one pulse (PULSE_MILLISECONDS in draw.js is 1400).
    const LOW_PULSE = 0; const HIGH_PULSE = 700;
    // An object and its outline are drawn into a square of 2 x 20 units
    // around the station (OBJECT_HALF_SIZE in draw.js); the number tag
    // reaches a little further. Stations lie much further apart than this.
    const REACH = 24;
    const drawings = Game.world.art.stations;
    const ids = campus.stations.map((station) => station.id);

    function render(map, pulsing, now) {
      const canvas = document.createElement('canvas');
      canvas.width = W * S; canvas.height = H * S;
      const ctx = canvas.getContext('2d');
      ctx.setTransform(S, 0, 0, S, 0, 0);
      Game.world.drawMap(ctx, map, null, false, pulsing || [], now || 0);
      return ctx.getImageData(0, 0, W * S, H * S).data;
    }

    // The map with every station's drawing replaced by nothing (with the
    // same shadow place): only the
    // shadow and the number tag that draw.js adds are left. No outline is
    // drawn here, so no outline is made (and kept) from the empty drawings.
    // With `withShadows` false the empty drawings say they have no shadow
    // (draw.js), so only the tags are left.
    function renderShadowsAndTags(withShadows) {
      const kept = {};
      ids.forEach((id) => {
        kept[id] = drawings[id];
        if (!drawings[id]) return;
        const empty = function () {};
        if (!withShadows) empty.shadow = null;
        else if ('shadow' in kept[id]) empty.shadow = kept[id].shadow;
        drawings[id] = empty;
      });
      try {
        return render(campus);
      } finally {
        ids.forEach((id) => { if (kept[id]) drawings[id] = kept[id]; });
      }
    }

    // 1 for every pixel where the two pictures differ clearly, else 0.
    function pixelDifference(first, second) {
      const pixels = new Uint8Array(W * S * H * S);
      for (let p = 0; p < pixels.length; p++) {
        const i = p * 4;
        const d = Math.abs(first[i] - second[i]) + Math.abs(first[i + 1] - second[i + 1]) + Math.abs(first[i + 2] - second[i + 2]);
        pixels[p] = d > 60 ? 1 : 0;
      }
      return pixels;
    }

    // 1 for every unit where the two pictures differ, else 0.
    function difference(first, second) {
      const units = new Uint8Array(W * H);
      for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
        let differing = 0;
        for (let py = 0; py < S; py++) for (let px = 0; px < S; px++) {
          const i = ((y * S + py) * W * S + x * S + px) * 4;
          const d = Math.abs(first[i] - second[i]) + Math.abs(first[i + 1] - second[i + 1]) + Math.abs(first[i + 2] - second[i + 2]);
          if (d > 60) differing++;
        }
        units[y * W + x] = differing >= 6 ? 1 : 0;
      }
      return units;
    }

    const walls = campus.solids.filter((solid) => solid.kind === 'wall');
    const withStations = render(campus);
    const shadowsAndTags = renderShadowsAndTags(true);
    const tagsOnly = renderShadowsAndTags(false);
    const lowOutline = render(campus, ids, LOW_PULSE);
    const highOutline = render(campus, ids, HIGH_PULSE);
    const noStations = render({ ...campus, stations: [] });
    // As in play_campus_detail_in_browser.js: only the walls (and their
    // faces) stay, so what differs from it is the furniture.
    const bare = render({
      ...campus,
      stations: [],
      solids: walls,
      decor: (campus.decor || []).filter((item) => item.layer !== 'on'),
    });
    // Each part as units (for its box) and as pixels (for what it covers).
    // The object and its outline are what art/stations.js and the outline
    // add to the shadow and the tag; the shadow and the tag are what draw.js
    // adds to the map.
    const parts = {
      object: [withStations, shadowsAndTags],
      objectAndLowOutline: [lowOutline, shadowsAndTags],
      objectAndHighOutline: [highOutline, shadowsAndTags],
      shadowAndTag: [shadowsAndTags, noStations],
      shadow: [shadowsAndTags, tagsOnly],
      tag: [tagsOnly, noStations],
    };
    const furniture = pixelDifference(noStations, bare);
    const inWall = new Uint8Array(W * S * H * S);
    for (const wall of walls) {
      for (let y = Math.max(0, wall.y * S); y < Math.min(H * S, (wall.y + wall.h) * S); y++) {
        for (let x = Math.max(0, wall.x * S); x < Math.min(W * S, (wall.x + wall.w) * S); x++) inWall[y * W * S + x] = 1;
      }
    }

    const unitMasks = {}; const pixelMasks = {};
    for (const [name, [first, second]] of Object.entries(parts)) {
      unitMasks[name] = difference(first, second);
      pixelMasks[name] = pixelDifference(first, second);
    }

    function unitsAround(station, visit) {
      for (let y = Math.max(0, station.y - REACH); y < Math.min(H, station.y + REACH); y++) {
        for (let x = Math.max(0, station.x - REACH); x < Math.min(W, station.x + REACH); x++) visit(x, y, y * W + x);
      }
    }

    // The box of the units set in `units` around the station, as offsets
    // from its centre: left and top are the first unit, right and bottom
    // the edge after the last one.
    function boxAround(units, station) {
      let box = null;
      unitsAround(station, (x, y, i) => {
        if (!units[i]) return;
        const dx = x - station.x; const dy = y - station.y;
        if (!box) box = { left: dx, top: dy, right: dx + 1, bottom: dy + 1 };
        box.left = Math.min(box.left, dx); box.top = Math.min(box.top, dy);
        box.right = Math.max(box.right, dx + 1); box.bottom = Math.max(box.bottom, dy + 1);
      });
      return box;
    }

    // The units around the station with a pixel of `pixels` that lies on
    // a pixel of drawn furniture or in a wall.
    function onFurnitureOrWall(pixels, station) {
      const found = [];
      unitsAround(station, (x, y) => {
        for (let py = y * S; py < (y + 1) * S; py++) {
          for (let px = x * S; px < (x + 1) * S; px++) {
            const p = py * W * S + px;
            if (pixels[p] && (furniture[p] || inWall[p])) { found.push([x, y]); return; }
          }
        }
      });
      return found;
    }

    const stations = campus.stations.filter((station) => drawings[station.id]).map((station) => {
      const result = { id: station.id };
      for (const name of Object.keys(parts)) {
        result[name] = {
          box: boxAround(unitMasks[name], station),
          onFurnitureOrWall: onFurnitureOrWall(pixelMasks[name], station),
        };
      }
      return result;
    });
    // The box of each room's name: the map with and without the names.
    const noNames = render({ ...campus, stations: [], rooms: campus.rooms.map((room) => ({ ...room, label: null })) });
    const names = difference(noStations, noNames);
    const roomNames = campus.rooms.map((room) => {
      let box = null;
      for (let y = Math.max(0, room.label.y - 15); y < Math.min(H, room.label.y + 15); y++) {
        for (let x = Math.max(0, room.label.x - 90); x < Math.min(W, room.label.x + 90); x++) {
          if (!names[y * W + x]) continue;
          if (!box) box = { x0: x, y0: y, x1: x + 1, y1: y + 1 };
          box.x0 = Math.min(box.x0, x); box.y0 = Math.min(box.y0, y);
          box.x1 = Math.max(box.x1, x + 1); box.y1 = Math.max(box.y1, y + 1);
        }
      }
      return { id: room.id, box };
    });
    // How much of each solid other than a wall is drawn (as in
    // play_campus_detail_in_browser.js): the share of its units that differ
    // from the map with only the walls.
    const drawnUnits = difference(noStations, bare);
    const coverage = campus.solids.filter((solid) => solid.kind !== 'wall').map((solid) => {
      let count = 0;
      for (let y = solid.y; y < solid.y + solid.h; y++) {
        for (let x = solid.x; x < solid.x + solid.w; x++) count += drawnUnits[y * W + x];
      }
      return { id: solid.id, kind: solid.kind, share: count / (solid.w * solid.h) };
    });
    return { stations, roomNames, coverage };
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
  await page.waitForFunction(() => window.Game && Game.world && typeof Game.world.drawMap === 'function');
  const check = await page.evaluate(stationCheck);
  console.log(JSON.stringify({ console: problems, ...check }));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
