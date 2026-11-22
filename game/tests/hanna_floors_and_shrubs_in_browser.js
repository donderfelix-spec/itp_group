// Browser part of test_hanna_floors_and_shrubs.py (M2-1.21). Needs
// Playwright and Chromium.
//
// Usage: node hanna_floors_and_shrubs_in_browser.js <base-url>
// Prints one JSON object:
//   console   every console error or warning and page error of the page
//   solids    for each deck bush, the study area and the hedge: its id, kind,
//             the share of its rectangle that is drawn, and how many pixels
//             of its drawing lie outside its rectangle
//   rooms     for every room: its floor colour from the map, the darkest and
//             the lightest colour of its floor pattern, and the darkest and
//             the lightest colour behind the letters of its name (as
//             [red, green, blue])
//   spot      the hedge's hiding spot: the colour of its dashed outline, of
//             the disc inside it and of the hedge outside it
//   floorPatterns  the names of the floor patterns the art files draw
//   corridorName  the decor entry "Academic Hall", the box of its drawn
//             letters in map units, the colour of the letters, and the
//             darkest and lightest colour of the floor behind them
//
// How it is measured: the page's own Game.world.drawMap draws the map at 4
// pixels per unit, as in play_map_polish_in_browser.js. A unit counts as
// drawn when 6 of its 16 pixels differ clearly (red + green + blue more than
// 60) from the map with only the walls and without the decor on solids. The
// pixels outside a solid are those that differ between the map with and
// without that solid, outside its rectangle.
const { chromium } = require('playwright');

const base = process.argv[2];
const CHECKED = ['deck-tree-1', 'deck-tree-2', 'deck-tree-3', 'deck-tree-4',
  'deck-tree-5', 'deck-tree-6', 'deck-pool', 'deck-hedge'];

function measure(checked) {
  return (async () => {
    const campus = await (await fetch('js/world/campus.json')).json();
    const S = 4; const W = campus.width; const H = campus.height;
    const CLEAR = 60;
    const walls = campus.solids.filter((solid) => solid.kind === 'wall');

    function render(map) {
      const canvas = document.createElement('canvas');
      canvas.width = W * S; canvas.height = H * S;
      const ctx = canvas.getContext('2d');
      ctx.setTransform(S, 0, 0, S, 0, 0);
      Game.world.drawMap(ctx, map, null, false, [], 0);
      return ctx.getImageData(0, 0, W * S, H * S).data;
    }

    function differs(first, second, i) {
      return Math.abs(first[i] - second[i]) + Math.abs(first[i + 1] - second[i + 1])
        + Math.abs(first[i + 2] - second[i + 2]) > CLEAR;
    }

    function pixel(data, x, y) {
      const i = (Math.round(y * S) * W * S + Math.round(x * S)) * 4;
      return [data[i], data[i + 1], data[i + 2]];
    }

    const noStations = { ...campus, stations: [] };
    const plain = render(noStations);
    const bare = render({
      ...noStations,
      solids: walls,
      decor: (campus.decor || []).filter((item) => item.layer !== 'on'),
    });

    // How much of a solid is drawn, and how many pixels of it lie outside.
    function checkSolid(solid) {
      let drawn = 0;
      for (let y = solid.y; y < solid.y + solid.h; y++) {
        for (let x = solid.x; x < solid.x + solid.w; x++) {
          let differing = 0;
          for (let py = 0; py < S; py++) for (let px = 0; px < S; px++) {
            if (differs(plain, bare, ((y * S + py) * W * S + x * S + px) * 4)) differing++;
          }
          if (differing >= 6) drawn++;
        }
      }
      const without = render({ ...noStations, solids: campus.solids.filter((other) => other !== solid) });
      const MARGIN = 10;
      let outside = 0;
      for (let y = (solid.y - MARGIN) * S; y < (solid.y + solid.h + MARGIN) * S; y++) {
        for (let x = (solid.x - MARGIN) * S; x < (solid.x + solid.w + MARGIN) * S; x++) {
          const inside = x >= solid.x * S && x < (solid.x + solid.w) * S
            && y >= solid.y * S && y < (solid.y + solid.h) * S;
          if (!inside && x >= 0 && y >= 0 && x < W * S && y < H * S
            && differs(plain, without, (y * W * S + x) * 4)) outside++;
        }
      }
      return { id: solid.id, kind: solid.kind, share: drawn / (solid.w * solid.h), outside };
    }
    const solids = checked.map((id) => checkSolid(campus.solids.find((solid) => solid.id === id)));

    // The darkest and the lightest pixel of a rectangle (by luminance), after
    // leaving out the 1 % at each end (a stray speck is no tile).
    function extremes(data, box) {
      const colours = [];
      for (let y = Math.ceil(box.y * S); y < Math.floor((box.y + box.h) * S); y++) {
        for (let x = Math.ceil(box.x * S); x < Math.floor((box.x + box.w) * S); x++) {
          const i = (y * W * S + x) * 4;
          colours.push([data[i], data[i + 1], data[i + 2]]);
        }
      }
      const light = (c) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
      colours.sort((a, b) => light(a) - light(b));
      const cut = Math.floor(colours.length * 0.01);
      return { darkest: colours[cut], lightest: colours[colours.length - 1 - cut] };
    }

    // The floors alone: no solids but the walls, no decor, no names.
    const floorsOnly = render({
      ...noStations, solids: walls, decor: [],
      rooms: campus.rooms.map((room) => ({ ...room, label: null })),
    });
    // Behind the names: the map as it is, without the names.
    const noNames = render({ ...noStations, rooms: campus.rooms.map((room) => ({ ...room, label: null })) });
    // The box of the letters of a room's name: the pixels that differ
    // between the map with and without the names, near the name's place.
    function nameBox(room) {
      let box = null;
      for (let y = (room.label.y - 12) * S; y < (room.label.y + 12) * S; y++) {
        for (let x = (room.label.x - 90) * S; x < (room.label.x + 90) * S; x++) {
          if (x < 0 || x >= W * S || !differs(plain, noNames, (y * W * S + x) * 4)) continue;
          if (!box) box = { x0: x, y0: y, x1: x + 1, y1: y + 1 };
          box.x0 = Math.min(box.x0, x); box.y0 = Math.min(box.y0, y);
          box.x1 = Math.max(box.x1, x + 1); box.y1 = Math.max(box.y1, y + 1);
        }
      }
      return { x: box.x0 / S, y: box.y0 / S, w: (box.x1 - box.x0) / S, h: (box.y1 - box.y0) / S };
    }
    const rooms = campus.rooms.map((room) => {
      const label = nameBox(room);
      // The floor away from its walls' faces.
      const inner = { x: room.x + 4, y: room.y + 14, w: room.w - 8, h: room.h - 18 };
      return {
        id: room.id, floor: room.floor, pattern: room.pattern,
        floorPattern: extremes(floorsOnly, inner), behindName: extremes(noNames, label),
      };
    });

    // The hedge's hiding spot, with its dash of 4 and gap of 3 map units
    // starting at angle 0 (draw.js): the middle of every dash on the circle,
    // the disc 2 units inside it and the hedge 2 units outside it.
    const spot = campus.hiding_spots[0];
    const dashes = []; const disc = []; const around = [];
    const withSpot = plain;
    for (let middle = 2; middle < 2 * Math.PI * spot.r - 2; middle += 7) {
      const angle = middle / spot.r;
      const at = (r) => [spot.x + Math.cos(angle) * r, spot.y + Math.sin(angle) * r];
      dashes.push(pixel(withSpot, ...at(spot.r)));
      disc.push(pixel(withSpot, ...at(spot.r - 2)));
      around.push(pixel(withSpot, ...at(spot.r + 2)));
    }
    const floorPatterns = Object.keys(Game.world.art.floors).sort();

    // The corridor's name "Academic Hall" (Felix, 2026-11-22): the map with
    // and without its decor entry; the pixels that differ are its letters.
    const nameEntry = campus.decor.find((item) => item.text === 'Academic Hall');
    let corridorName = null;
    if (nameEntry) {
      const withoutName = render({ ...noStations, decor: campus.decor.filter((item) => item !== nameEntry) });
      let box = null; const ink = [];
      for (let y = 0; y < H * S; y++) {
        for (let x = 0; x < W * S; x++) {
          const i = (y * W * S + x) * 4;
          if (!differs(plain, withoutName, i)) continue;
          if (!box) box = { x0: x, y0: y, x1: x + 1, y1: y + 1 };
          box.x0 = Math.min(box.x0, x); box.y0 = Math.min(box.y0, y);
          box.x1 = Math.max(box.x1, x + 1); box.y1 = Math.max(box.y1, y + 1);
          ink.push([plain[i], plain[i + 1], plain[i + 2]]);
        }
      }
      const light = (c) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
      ink.sort((first, second) => light(first) - light(second));
      const drawnBox = { x: box.x0 / S, y: box.y0 / S, w: (box.x1 - box.x0) / S, h: (box.y1 - box.y0) / S };
      corridorName = {
        entry: nameEntry, box: drawnBox,
        // The colour of the letters: the middle of their darker half (the
        // edges of the letters are blended with the floor).
        ink: ink[Math.floor(ink.length / 4)],
        behind: extremes(withoutName, drawnBox),
      };
    }
    return { solids, rooms, spot: { x: spot.x, y: spot.y, dashes, disc, around }, floorPatterns, corridorName };
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
  const result = await page.evaluate(measure, CHECKED);
  console.log(JSON.stringify({ console: problems, ...result }));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
