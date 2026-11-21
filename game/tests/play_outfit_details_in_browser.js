// Browser part of test_play_outfit_details.py (M2-1.18). Needs Playwright and Chromium.
//
// Usage: node play_outfit_details_in_browser.js <base-url> [screenshot-folder]
//
// Two guests in Chromium, guest A at pixel density 2 and guest B at density 1.
// In the lobby every character icon is read: is the colour of its motif drawn
// in the torso of the icon? Then each guest in turn takes every one of the
// eight characters (the other guest gives way when it holds the one wanted,
// as a person would: a taken character is greyed out), stands, walks left
// and walks right with real key presses. While it stands and walks, every
// drawn frame of the map is read in a box on the own figure's torso (the
// camera keeps the own figure in the middle of the canvas): how many pixels
// have the motif's colour and where their middle is, in map units from the
// figure's middle.
//
// Prints one JSON object:
//   console    every console error or warning and page error of both pages
//   rejections every `error` message a page received
//   icons      per density and character: the motif in the icon's torso, as
//              drawn on its canvas and as shown on the page (see readIcons)
//   map        per guest and character: per pose (standing, left, right) the
//              frames read, each {count, lonely, x, y, scale}; `lonely` are
//              pixels of the colour that do not count (the floor)
// With a screenshot folder, pictures for a person are saved there as well.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const base = process.argv[2];
const shots = process.argv[3] || null;

// The motif of each character: its colour, the colour it lies on (`on`),
// and the band of the design (characters.js units, y down, 112 units high)
// where it lies, with 3.5 units to spare above and below for the bob of a
// step (BODY_BOB = 3). Only this band of the torso is read, so that other
// things of the same colour (a necklace, a print) are not counted. The
// floor of the Main Deck has the cream of two motifs: a group of touching pixels of the motif's colour counts only when
// it lies inside the band and partly within NEAR_DESIGN units (`near` for
// the two cream motifs) of the colour it lies on. The floor reaches the edge
// of the band or lies behind the outline of the body or an arm. For the two
// cream motifs the box is also narrower (`half`, map units): floor seen
// between a swinging arm and the body is left out.
const MOTIFS = {
  consultant: { name: 'The Consultant', colour: '#D9B45C', on: '#E0483E', top: 49, bottom: 59 },
  finance_bro: { name: 'The Finance Bro', colour: '#D9B45C', on: '#BFD9F2', top: 50, bottom: 66 },
  exchange_student: { name: 'The Exchange Student', colour: '#F2695C', on: '#F0569B', top: 52, bottom: 70 },
  surfer: { name: 'The Surfer', colour: '#FFFFFF', on: '#F08A3C', top: 66.5, bottom: 84 },
  founder: { name: 'The Founder', colour: '#8EDCC5', on: '#33333D', top: 37, bottom: 55 },
  overachiever: { name: 'The Overachiever', colour: '#F4EFE3', on: '#4E9F5B', top: 50, bottom: 76, near: 1.6, half: 4 },
  latecomer: { name: 'The Latecomer', colour: '#D9B45C', on: '#FFFFFF', top: 39, bottom: 54 },
  library_local: { name: 'The Library Local', colour: '#F4EFE3', on: '#7A5CC2', top: 38, bottom: 57, near: 1.6, half: 4 },
};
const IDS = Object.keys(MOTIFS);

// From characters.js and world.js: the design is 112 units high with its
// middle at y = 44; on the map a character is 39 units high, its middle
// 14.5 units above the position; the view is 260 units on its long side.
const DESIGN_MIDDLE = 44;
const DESIGN_HEIGHT = 112;
const MAP_HEIGHT = 39;
const MIDDLE_ABOVE_POSITION = 14.5;
const VIEW_SIZE = 260;
const ICON_PIXELS = 48;
const ICON_CHARACTER = 44;
// Half the width of the box read on the map, in map units (the turned body
// is 35 design units wide, about 12 map units).
const TORSO_HALF_WIDTH = 10; // wide enough for the lean of a step
const NEAR_DESIGN = 2.2;

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function listenAlong() {
  const Original = window.WebSocket;
  window.__errors = [];
  window.WebSocket = class extends Original {
    constructor(...args) {
      super(...args);
      this.addEventListener('message', (event) => {
        let message;
        try { message = JSON.parse(event.data); } catch (e) { return; }
        if (message.type === 'error') window.__errors.push(message);
      });
    }
  };
}

async function guest(browser, problems, label, density) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: density });
  const page = await context.newPage();
  await page.addInitScript(listenAlong);
  await page.addInitScript(BLEND_IN_PAGE);
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') problems.push(`${label} ${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`${label} page error: ${e.message}`));
  await page.goto(base + '/');
  await page.click('#start-guest');
  await page.waitForSelector('#screen-home:not([hidden])');
  return page;
}

// Creates a lobby and returns its code.
async function createLobby(page) {
  await page.click('#home-create');
  await page.waitForSelector('#screen-lobby:not([hidden])');
  await page.waitForFunction(() => /[A-Z0-9]{4}/.test(document.getElementById('lobby-code').textContent));
  await page.waitForSelector('#lobby-characters button.character-own');
  return (await page.textContent('#lobby-code')).match(/[A-Z0-9]{4}/)[0];
}

function button(page, id) {
  return page.locator('#lobby-characters button.character', { has: page.locator('.character-name', { hasText: MOTIFS[id].name }) });
}

async function ownCharacter(page) {
  return page.evaluate((motifs) => {
    const own = document.querySelector('#lobby-characters button.character-own .character-name');
    if (!own) return null;
    return Object.keys(motifs).find((id) => motifs[id].name === own.textContent) || null;
  }, MOTIFS);
}

async function choose(page, id) {
  await button(page, id).click();
  await page.waitForFunction((name) => {
    const own = document.querySelector('#lobby-characters button.character-own .character-name');
    return own && own.textContent === name;
  }, MOTIFS[id].name, { timeout: 5000 });
  await page.evaluate(() => { if (document.activeElement) document.activeElement.blur(); });
}

// The player wants `id`; the other player gives it up first if they hold it.
async function takeCharacter(player, other, id) {
  if ((await ownCharacter(other)) === id) {
    const mine = await ownCharacter(player);
    const free = IDS.find((c) => c !== id && c !== mine);
    await choose(other, free);
  }
  await player.waitForFunction((name) => {
    const names = [...document.querySelectorAll('#lobby-characters .character-name')];
    const wanted = names.find((n) => n.textContent === name);
    return wanted && !wanted.closest('button').disabled;
  }, MOTIFS[id].name, { timeout: 5000 });
  const greyedForOther = await button(other, id).isDisabled().catch(() => null);
  await choose(player, id);
  // In the other page the character is now greyed out.
  await other.waitForFunction((name) => {
    const names = [...document.querySelectorAll('#lobby-characters .character-name')];
    const wanted = names.find((n) => n.textContent === name);
    return wanted && wanted.closest('button').disabled;
  }, MOTIFS[id].name, { timeout: 5000 });
  return { greyed_for_other_before: greyedForOther };
}

// ---- The icons in the lobby ----

// How strongly a pixel shows the motif on the colour it lies on: 0 is the
// colour below, 1 the motif's colour. A pixel far off the line between the
// two (another colour, an outline) gives null.
const BLEND_IN_PAGE = `
  (function () {
    const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
    window.__motifBlend = function (r, g, b, motifColour, onColour) {
      const m = hex(motifColour); const n = hex(onColour);
      const d = [m[0] - n[0], m[1] - n[1], m[2] - n[2]];
      const v = [r - n[0], g - n[1], b - n[2]];
      const t = (v[0] * d[0] + v[1] * d[1] + v[2] * d[2]) / (d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
      const off = Math.hypot(v[0] - t * d[0], v[1] - t * d[1], v[2] - t * d[2]);
      return off <= 30 ? t : null;
    };
    window.__sameColour = function (r, g, b, colour, tolerance) {
      const c = hex(colour);
      return Math.max(Math.abs(r - c[0]), Math.abs(g - c[1]), Math.abs(b - c[2])) <= tolerance;
    };
  })();
`;

// Every icon of the lobby, in the band of its motif: how many pixels show
// the motif at least half strong (`strong`), in its exact colour (`exact`),
// and the strongest pixel (`strongest`, 1 = the motif's own colour). Read
// twice: on the icon's canvas (`drawn`, 48 x 48 CSS pixels times the
// density), and as the page shows it (`shown`): the stylesheet makes the icon
// of a character button smaller (36 x 36 CSS pixels), so it is copied at that
// size with smoothing, as the browser shrinks it.
async function readIcons(page, density, label) {
  const result = await page.evaluate(({ motifs, density, k }) => {
    function measure(data, width, pixelsPerCss, motif) {
      const unit = k.ICON_CHARACTER / k.DESIGN_HEIGHT; // css pixels per design unit
      const y0 = Math.floor((k.ICON_PIXELS / 2 + (motif.top - k.DESIGN_MIDDLE) * unit) * pixelsPerCss);
      const y1 = Math.ceil((k.ICON_PIXELS / 2 + (motif.bottom - k.DESIGN_MIDDLE) * unit) * pixelsPerCss);
      const x0 = Math.floor((k.ICON_PIXELS / 2 - 19 * unit) * pixelsPerCss);
      const x1 = Math.ceil((k.ICON_PIXELS / 2 + 19 * unit) * pixelsPerCss);
      let strong = 0; let exact = 0; let strongest = 0;
      for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
        const i = (y * width + x) * 4;
        if (data[i + 3] < 200) continue;
        if (window.__sameColour(data[i], data[i + 1], data[i + 2], motif.colour, 10)) exact++;
        const t = window.__motifBlend(data[i], data[i + 1], data[i + 2], motif.colour, motif.on);
        if (t === null || t > 1.3) continue;
        strongest = Math.max(strongest, Math.min(t, 1));
        if (t >= 0.5) strong++;
      }
      return { size: [width, width], strong, exact, strongest: +strongest.toFixed(2) };
    }
    const out = {};
    const crops = {};
    for (const id of Object.keys(motifs)) {
      const motif = motifs[id];
      const names = [...document.querySelectorAll('#lobby-characters .character-name')];
      const canvas = names.find((n) => n.textContent === motif.name).closest('button').querySelector('canvas');
      const drawn = measure(canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data,
        canvas.width, density, motif);
      const shownSize = Math.round(canvas.getBoundingClientRect().width * density);
      const shownCanvas = document.createElement('canvas');
      shownCanvas.width = shownSize; shownCanvas.height = shownSize;
      const shownCtx = shownCanvas.getContext('2d');
      shownCtx.imageSmoothingQuality = 'high';
      shownCtx.drawImage(canvas, 0, 0, shownSize, shownSize);
      const shown = measure(shownCtx.getImageData(0, 0, shownSize, shownSize).data,
        shownSize, shownSize / k.ICON_PIXELS, motif);
      out[id] = { drawn, shown };
      // An 8 x enlargement without smoothing of the canvas, for a person to look at.
      const big = document.createElement('canvas');
      big.width = canvas.width * 8; big.height = canvas.height * 8;
      const bctx = big.getContext('2d');
      bctx.imageSmoothingEnabled = false;
      bctx.drawImage(canvas, 0, 0, big.width, big.height);
      crops[id] = big.toDataURL('image/png');
    }
    return { out, crops };
  }, { motifs: MOTIFS, density, k: { ICON_PIXELS, ICON_CHARACTER, DESIGN_MIDDLE, DESIGN_HEIGHT } });
  if (shots) {
    await page.locator('#lobby-characters').screenshot({ path: path.join(shots, `lobby-dsf${density}-${label}-buttons.png`) });
    for (const id of IDS) {
      fs.writeFileSync(path.join(shots, `lobby-dsf${density}-${id}-icon-x8.png`), Buffer.from(result.crops[id].split(',')[1], 'base64'));
      // The icon exactly as the page shows it.
      await button(page, id).locator('canvas').screenshot({ path: path.join(shots, `lobby-dsf${density}-${id}-shown.png`) });
    }
  }
  return result.out;
}

// ---- The own figure on the map ----

// Reads `frames` drawn frames of the map: the motif's pixels in the torso of
// the own figure, which the camera keeps in the middle of the canvas. The
// part is copied onto a canvas of its own first, so that the map's canvas is
// never read back (Chromium warns about many readbacks).
async function readFrames(page, id, frames, stripName) {
  const result = await page.evaluate(async ({ motif, frames, withStrip, k }) => {
    const canvas = document.getElementById('map');
    // Every frame's figure side by side, for a person to look at.
    const STRIP_CELL = 200;
    const PER_ROW = 6;
    const strip = document.createElement('canvas');
    strip.width = withStrip ? STRIP_CELL * Math.min(frames, PER_ROW) : 1;
    strip.height = withStrip ? STRIP_CELL * Math.ceil(frames / PER_ROW) : 1;
    const copy = document.createElement('canvas');
    const copyCtx = copy.getContext('2d', { willReadFrequently: true });
    const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve, 0)));
    const out = [];
    for (let f = 0; f < frames; f++) {
      await nextFrame();
      const scale = Math.max(canvas.width, canvas.height) / k.VIEW_SIZE; // canvas pixels per map unit
      const unit = k.MAP_HEIGHT / k.DESIGN_HEIGHT; // map units per design unit
      const near = Math.ceil((motif.near || k.NEAR_DESIGN) * unit * scale); // in canvas pixels
      const middleX = canvas.width / 2;
      const middleY = canvas.height / 2 - k.MIDDLE_ABOVE_POSITION * scale;
      if (withStrip) {
        const half = 20 * scale;
        strip.getContext('2d').drawImage(canvas, middleX - half, middleY - half, 2 * half, 2 * half,
          (f % PER_ROW) * STRIP_CELL, Math.floor(f / PER_ROW) * STRIP_CELL, STRIP_CELL, STRIP_CELL);
      }
      const x0 = Math.floor(middleX - (motif.half || k.TORSO_HALF_WIDTH) * scale);
      const y0 = Math.floor(middleY + (motif.top - k.DESIGN_MIDDLE) * unit * scale);
      const w = Math.ceil(2 * (motif.half || k.TORSO_HALF_WIDTH) * scale);
      const h = Math.ceil((motif.bottom - motif.top) * unit * scale);
      // The band and `near` pixels around it.
      copy.width = w + 2 * near; copy.height = h + 2 * near;
      copyCtx.drawImage(canvas, x0 - near, y0 - near, copy.width, copy.height, 0, 0, copy.width, copy.height);
      const data = copyCtx.getImageData(0, 0, copy.width, copy.height).data;
      const at = (x, y) => (y * copy.width + x) * 4;
      const isOn = (x, y) => { const i = at(x, y); return window.__sameColour(data[i], data[i + 1], data[i + 2], motif.on, 14); };
      const hasOnNearby = (x, y) => {
        for (let dy = -near; dy <= near; dy++) for (let dx = -near; dx <= near; dx++) if (isOn(x + dx, y + dy)) return true;
        return false;
      };
      // The motif's pixels in groups that touch (left, right, up, down). A
      // group counts when it lies inside the band (the floor reaches its
      // edge) and some of it lies near the colour the motif is on.
      const isMotif = new Uint8Array(copy.width * copy.height);
      for (let y = near; y < near + h; y++) for (let x = near; x < near + w; x++) {
        const i = at(x, y);
        if (window.__sameColour(data[i], data[i + 1], data[i + 2], motif.colour, 10)) isMotif[y * copy.width + x] = 1;
      }
      let count = 0; let sx = 0; let sy = 0; let lonely = 0;
      const seen = new Uint8Array(copy.width * copy.height);
      for (let start = 0; start < isMotif.length; start++) {
        if (!isMotif[start] || seen[start]) continue;
        const group = [start];
        seen[start] = 1;
        let atEdge = false; let isNearOn = false;
        for (let g = 0; g < group.length; g++) {
          const x = group[g] % copy.width; const y = (group[g] - x) / copy.width;
          if (x === near || y === near || x === near + w - 1 || y === near + h - 1) atEdge = true;
          if (!isNearOn && hasOnNearby(x, y)) isNearOn = true;
          for (const [nx, ny] of [[x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]]) {
            const n = ny * copy.width + nx;
            if (isMotif[n] && !seen[n]) { seen[n] = 1; group.push(n); }
          }
        }
        if (atEdge || !isNearOn) { lonely += group.length; continue; }
        for (const n of group) { const x = n % copy.width; count++; sx += x; sy += (n - x) / copy.width; }
      }
      const toMapX = (px) => (x0 - near + px + 0.5 - middleX) / scale;
      const toMapY = (py) => (y0 - near + py + 0.5 - middleY) / scale;
      out.push({
        count, lonely, scale: +scale.toFixed(3),
        x: count ? +toMapX(sx / count).toFixed(2) : null,
        y: count ? +toMapY(sy / count).toFixed(2) : null,
      });
    }
    return { out, strip: withStrip ? strip.toDataURL('image/png') : null };
  }, {
    motif: MOTIFS[id], frames, withStrip: Boolean(shots && stripName),
    k: { VIEW_SIZE, MAP_HEIGHT, DESIGN_HEIGHT, DESIGN_MIDDLE, MIDDLE_ABOVE_POSITION, TORSO_HALF_WIDTH, NEAR_DESIGN },
  });
  if (result.strip) fs.writeFileSync(path.join(shots, stripName), Buffer.from(result.strip.split(',')[1], 'base64'));
  return result.out;
}

// The own figure, cut out of the page for a person to look at.
async function shootFigure(page, name) {
  if (!shots) return;
  const box = await page.evaluate(({ VIEW_SIZE, MIDDLE_ABOVE_POSITION }) => {
    const canvas = document.getElementById('map');
    const r = canvas.getBoundingClientRect();
    const scale = Math.max(r.width, r.height) / VIEW_SIZE;
    const x = r.left + r.width / 2; const y = r.top + r.height / 2 - MIDDLE_ABOVE_POSITION * scale;
    const half = 28 * scale;
    return { x: x - half, y: y - half, width: 2 * half, height: 2 * half };
  }, { VIEW_SIZE, MIDDLE_ABOVE_POSITION });
  await page.screenshot({ path: path.join(shots, name), clip: box });
}

async function walkAndRead(page, key, label, id) {
  await page.keyboard.down(key);
  try {
    await pause(300); // the steps grow to full size
    const side = key === 'KeyA' ? 'left' : 'right';
    const frames = await readFrames(page, id, 24, `frames-${label}-${id}-walk-${side}.png`);
    await shootFigure(page, `map-${label}-${id}-walk-${side}.png`);
    return frames;
  } finally {
    await page.keyboard.up(key);
    await pause(500); // the character comes to a stop
  }
}

async function playCharacter(player, other, label, id) {
  const taken = await takeCharacter(player, other, id);
  await pause(300);
  const standing = await readFrames(player, id, 8);
  await shootFigure(player, `map-${label}-${id}-standing.png`);
  const left = await walkAndRead(player, 'KeyA', label, id);
  const right = await walkAndRead(player, 'KeyD', label, id);
  return { ...taken, standing, left, right };
}

(async () => {
  const browser = await chromium.launch();
  const problems = [];
  const out = { console: problems, icons: {}, map: { A: {}, B: {} } };
  // Each guest reads the icons while alone in a lobby, so that no icon is
  // greyed out; B then leaves its lobby and joins A's.
  const a = await guest(browser, problems, 'A', 2);
  const code = await createLobby(a);
  out.icons.dsf2 = await readIcons(a, 2, 'A');
  const b = await guest(browser, problems, 'B', 1);
  await createLobby(b);
  out.icons.dsf1 = await readIcons(b, 1, 'B');
  await b.click('#lobby-leave');
  await b.waitForSelector('#screen-home:not([hidden])');
  await b.fill('#join-code', code);
  await b.click('#join-submit');
  await b.waitForSelector('#screen-lobby:not([hidden])');
  await pause(800);
  if (shots) {
    await a.screenshot({ path: path.join(shots, 'lobby-dsf2-A-page.png') });
    await b.screenshot({ path: path.join(shots, 'lobby-dsf1-B-page.png') });
  }
  for (const page of [a, b]) await page.evaluate(() => { if (document.activeElement) document.activeElement.blur(); });
  // B steps away from the spawn, so that only A's figure is in A's torso box.
  await b.keyboard.down('KeyS'); await pause(700); await b.keyboard.up('KeyS'); await pause(400);
  for (const id of IDS) out.map.A[id] = await playCharacter(a, b, 'A', id);
  // Then B takes every character and A steps away.
  await a.keyboard.down('KeyW'); await pause(700); await a.keyboard.up('KeyW'); await pause(400);
  for (const id of IDS) out.map.B[id] = await playCharacter(b, a, 'B', id);
  out.rejections = { A: await a.evaluate(() => window.__errors), B: await b.evaluate(() => window.__errors) };
  console.log(JSON.stringify(out));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
