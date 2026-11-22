// Runs the page's own js/world/characters.js in Node, without a browser, for
// test_characters_drawn.py (M2-1.11).
//
// The canvas is a stand-in that draws nothing but writes down every fill,
// stroke and text: its colour, its line width and where it lands. For that
// it keeps the transform like a real canvas does (save, restore, translate,
// scale, rotate), and a small Path2D stand-in reads the SVG path texts the
// drawing code uses (M L H V Q T C A Z, also in lower case). Curves and arcs
// are written down as many points along them, so the boxes below are exact
// to a hundredth of a unit. Clipping is ignored: a clipped shape counts with
// its whole path.
//
// Every character is drawn with its middle at (0, 0) and a height of 112,
// the height of the design, so one unit of the canvas is one unit of the
// design. Then each drawing is reported in two frames:
//   design  x and y as in the design: y = -12 is the top, the middle of the
//           portrait's body is x = 0. A mirrored drawing is mirrored back, so
//           the side the character is turned to is always +x.
//   body    the frame the body box was drawn in. On it the body does not move,
//           whether the character walks, leans or is mirrored.
//
// Output (stdout): JSON {characterId: {poseName: [drawing, ...]}} where a
// drawing is {op, colour, width, alpha, text, part, design: [minX, minY,
// maxX, maxY], body: [...], screenMiddleX}. `part` is "clothes" for what is
// drawn on the body box before the first arm, "before" and "after" for the
// rest. `alpha` is the canvas's globalAlpha at the moment of the drawing.
// screenMiddleX is the middle on the screen: > 0 is on the right.
//
// The environment variable CHARACTER_IDS can hold a JSON list of ids to
// draw instead of the eight characters (test_outfit_details.py, M2-1.18):
// an id the page does not know is drawn as its plain grey figure.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

// An other file to draw from can be given as the first argument (to compare
// with an older version by hand); the tests always use the page's own file.
const CHARACTERS_JS = process.argv[2] || path.join(__dirname, '..', 'client', 'js', 'world', 'characters.js');
const OUTLINE = '#2E2A3B';
const STEPS = 24; // points written down along each curve

// ---- 2D transforms: [a, b, c, d, e, f] as in a canvas -------------------

const IDENTITY = [1, 0, 0, 1, 0, 0];

function multiply(m, n) {
  return [
    m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1],
    m[0] * n[2] + m[2] * n[3], m[1] * n[2] + m[3] * n[3],
    m[0] * n[4] + m[2] * n[5] + m[4], m[1] * n[4] + m[3] * n[5] + m[5],
  ];
}

function apply(m, [x, y]) {
  return [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]];
}

function inverse(m) {
  const det = m[0] * m[3] - m[1] * m[2];
  return [
    m[3] / det, -m[1] / det, -m[2] / det, m[0] / det,
    (m[2] * m[5] - m[3] * m[4]) / det, (m[1] * m[4] - m[0] * m[5]) / det,
  ];
}

// ---- Paths ---------------------------------------------------------------

// Builds a list of points in the coordinates it is given. `place` turns
// those into the coordinates the points are kept in.
class PointPath {
  constructor(place) {
    this.place = place || ((point) => point);
    this.points = [];
    this.start = null;
    this.current = null;
  }

  add(point) {
    this.points.push(this.place(point));
    this.current = point;
  }

  moveTo(x, y) { this.start = [x, y]; this.add([x, y]); }

  lineTo(x, y) { this.add([x, y]); }

  closePath() { if (this.start) this.add(this.start); }

  quadraticCurveTo(cx, cy, x, y) {
    const [x0, y0] = this.current || [cx, cy];
    for (let i = 1; i <= STEPS; i++) {
      const t = i / STEPS;
      const u = 1 - t;
      this.add([u * u * x0 + 2 * u * t * cx + t * t * x, u * u * y0 + 2 * u * t * cy + t * t * y]);
    }
  }

  bezierCurveTo(c1x, c1y, c2x, c2y, x, y) {
    const [x0, y0] = this.current || [c1x, c1y];
    for (let i = 1; i <= STEPS; i++) {
      const t = i / STEPS;
      const u = 1 - t;
      this.add([
        u * u * u * x0 + 3 * u * u * t * c1x + 3 * u * t * t * c2x + t * t * t * x,
        u * u * u * y0 + 3 * u * u * t * c1y + 3 * u * t * t * c2y + t * t * t * y,
      ]);
    }
  }

  // Only the rounded boxes use arcTo, and their corner never reaches past
  // the corner point, so the corner point stands in for the whole corner:
  // the box of the points is the box of the shape.
  arcTo(x1, y1) { this.add([x1, y1]); }

  ellipse(x, y, rx, ry, rotation, from, to, counterclockwise) {
    let sweep = to - from;
    if (counterclockwise && sweep > 0) sweep -= 2 * Math.PI;
    for (let i = 0; i <= STEPS * 4; i++) {
      const angle = from + (sweep * i) / (STEPS * 4);
      const px = rx * Math.cos(angle);
      const py = ry * Math.sin(angle);
      this.add([
        x + px * Math.cos(rotation) - py * Math.sin(rotation),
        y + px * Math.sin(rotation) + py * Math.cos(rotation),
      ]);
    }
  }

  arc(x, y, r, from, to, counterclockwise) { this.ellipse(x, y, r, r, 0, from, to, counterclockwise); }

  rect(x, y, w, h) { this.moveTo(x, y); this.lineTo(x + w, y); this.lineTo(x + w, y + h); this.lineTo(x, y + h); this.closePath(); }

  // The "A" of SVG: from the end points to the centre (SVG 1.1, appendix F.6.5).
  svgArc(rx, ry, angleDegrees, largeArc, sweep, x, y) {
    const [x1, y1] = this.current;
    const phi = (angleDegrees * Math.PI) / 180;
    const dx = (x1 - x) / 2;
    const dy = (y1 - y) / 2;
    const x1p = Math.cos(phi) * dx + Math.sin(phi) * dy;
    const y1p = -Math.sin(phi) * dx + Math.cos(phi) * dy;
    const grow = Math.max(1, Math.sqrt((x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)));
    rx *= grow;
    ry *= grow;
    const top = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p;
    const bottom = rx * rx * y1p * y1p + ry * ry * x1p * x1p;
    const factor = (largeArc === sweep ? -1 : 1) * Math.sqrt(Math.max(0, top / bottom));
    const cxp = (factor * rx * y1p) / ry;
    const cyp = (-factor * ry * x1p) / rx;
    const cx = Math.cos(phi) * cxp - Math.sin(phi) * cyp + (x1 + x) / 2;
    const cy = Math.sin(phi) * cxp + Math.cos(phi) * cyp + (y1 + y) / 2;
    const angle = (ux, uy, vx, vy) => Math.atan2(ux * vy - uy * vx, ux * vx + uy * vy);
    const from = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry);
    let delta = angle((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry);
    if (!sweep && delta > 0) delta -= 2 * Math.PI;
    if (sweep && delta < 0) delta += 2 * Math.PI;
    this.ellipse(cx, cy, rx, ry, phi, from, from + delta, false);
    this.current = [x, y];
  }
}

function readSvgPath(target, text) {
  const tokens = text.match(/[a-zA-Z]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?/g) || [];
  let i = 0;
  let command = null;
  let lastControl = null; // for T
  const number = () => parseFloat(tokens[i++]);
  while (i < tokens.length) {
    if (/[a-zA-Z]/.test(tokens[i])) command = tokens[i++];
    const relative = command === command.toLowerCase();
    const [cx, cy] = target.current || [0, 0];
    const ox = relative ? cx : 0;
    const oy = relative ? cy : 0;
    const upper = command.toUpperCase();
    let control = null;
    if (upper === 'M') {
      target.moveTo(ox + number(), oy + number());
      command = relative ? 'l' : 'L';
    } else if (upper === 'L') {
      target.lineTo(ox + number(), oy + number());
    } else if (upper === 'H') {
      target.lineTo(ox + number(), cy);
    } else if (upper === 'V') {
      target.lineTo(cx, oy + number());
    } else if (upper === 'Q') {
      control = [ox + number(), oy + number()];
      target.quadraticCurveTo(control[0], control[1], ox + number(), oy + number());
    } else if (upper === 'T') {
      control = lastControl ? [2 * cx - lastControl[0], 2 * cy - lastControl[1]] : [cx, cy];
      target.quadraticCurveTo(control[0], control[1], ox + number(), oy + number());
    } else if (upper === 'C') {
      target.bezierCurveTo(ox + number(), oy + number(), ox + number(), oy + number(), ox + number(), oy + number());
    } else if (upper === 'A') {
      const rx = number();
      const ry = number();
      const angle = number();
      const large = number();
      const sweep = number();
      target.svgArc(rx, ry, angle, large, sweep, ox + number(), oy + number());
    } else if (upper === 'Z') {
      target.closePath();
    } else {
      throw new Error(`Path command ${command} is not known to this stand-in: ${text}`);
    }
    lastControl = control;
  }
}

class FakePath2D extends PointPath {
  constructor(text) {
    super();
    if (typeof text === 'string') readSvgPath(this, text);
  }
}

// ---- The recording canvas ------------------------------------------------

function recordingCanvas(drawings) {
  const state = { matrix: IDENTITY.slice(), fillStyle: '#000', strokeStyle: '#000', lineWidth: 1, globalAlpha: 1, font: '' };
  const saved = [];
  let current = new PointPath((point) => apply(state.matrix, point));
  const record = (op, points, colour, extra) => {
    const scale = Math.sqrt(Math.abs(state.matrix[0] * state.matrix[3] - state.matrix[1] * state.matrix[2]));
    drawings.push({
      op, colour, width: op === 'stroke' ? state.lineWidth * scale : 0, alpha: state.globalAlpha,
      points, matrix: state.matrix.slice(), ...extra,
    });
  };
  const pointsOf = (path) => (path ? path.points.map((point) => apply(state.matrix, point)) : current.points.slice());
  return {
    get canvas() { return { width: 400, height: 400 }; },
    save() { saved.push({ ...state, matrix: state.matrix.slice() }); },
    restore() { if (saved.length) Object.assign(state, saved.pop()); },
    translate(x, y) { state.matrix = multiply(state.matrix, [1, 0, 0, 1, x, y]); },
    scale(x, y) { state.matrix = multiply(state.matrix, [x, 0, 0, y, 0, 0]); },
    rotate(a) { state.matrix = multiply(state.matrix, [Math.cos(a), Math.sin(a), -Math.sin(a), Math.cos(a), 0, 0]); },
    setTransform(a, b, c, d, e, f) { state.matrix = [a, b, c, d, e, f]; },
    getTransform() { const [a, b, c, d, e, f] = state.matrix; return { a, b, c, d, e, f }; },
    beginPath() { current = new PointPath((point) => apply(state.matrix, point)); },
    moveTo(x, y) { current.moveTo(x, y); },
    lineTo(x, y) { current.lineTo(x, y); },
    closePath() { current.closePath(); },
    quadraticCurveTo(...a) { current.quadraticCurveTo(...a); },
    bezierCurveTo(...a) { current.bezierCurveTo(...a); },
    arcTo(...a) { current.arcTo(...a); },
    arc(...a) { current.arc(...a); },
    ellipse(...a) { current.ellipse(...a); },
    rect(...a) { current.rect(...a); },
    clip() {},
    fill(path) { record('fill', pointsOf(path), state.fillStyle); },
    stroke(path) { record('stroke', pointsOf(path), state.strokeStyle); },
    fillText(text, x, y) { record('text', [apply(state.matrix, [x, y])], state.fillStyle, { text: String(text) }); },
    fillRect() {},
    clearRect() {},
    measureText(text) { return { width: String(text).length * 4 }; },
    set fillStyle(v) { state.fillStyle = v; }, get fillStyle() { return state.fillStyle; },
    set strokeStyle(v) { state.strokeStyle = v; }, get strokeStyle() { return state.strokeStyle; },
    set lineWidth(v) { state.lineWidth = v; }, get lineWidth() { return state.lineWidth; },
    set globalAlpha(v) { state.globalAlpha = v; }, get globalAlpha() { return state.globalAlpha; },
    set font(v) { state.font = v; }, get font() { return state.font; },
    lineJoin: 'miter', lineCap: 'butt', textAlign: 'start', textBaseline: 'alphabetic',
  };
}

// ---- Drawing every character in every pose -------------------------------

const page = { Path2D: FakePath2D };
page.window = page;
vm.runInNewContext(fs.readFileSync(CHARACTERS_JS, 'utf8'), page, { filename: CHARACTERS_JS });
const world = page.Game.world;

const POSES = { portrait: null, right: { mirrored: false }, left: { mirrored: true } };
for (let k = 0; k < 8; k++) {
  POSES[`walk right ${k}/8`] = { mirrored: false, walkPhase: k / 8, stride: 1 };
  POSES[`walk left ${k}/8`] = { mirrored: true, walkPhase: k / 8, stride: 1 };
}

function box(points) {
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const round = (v) => Math.round(v * 1000) / 1000;
  return [round(Math.min(...xs)), round(Math.min(...ys)), round(Math.max(...xs)), round(Math.max(...ys))];
}

function report(look, drawings, mirrored) {
  // The body box: a fill in the body colour that is 42 units high from
  // y = 38 to 80 where it was drawn. (The Founder's hood behind the head
  // has the body colour too.)
  const isBodyBox = (d) => {
    if (d.op !== 'fill' || d.colour !== look.colour) return false;
    const [, top, , bottom] = box(d.points.map((p) => apply(inverse(d.matrix), p)));
    return Math.abs(top - 38) < 1e-6 && Math.abs(bottom - 80) < 1e-6;
  };
  const bodyIndex = drawings.findIndex(isBodyBox);
  const firstArm = drawings.findIndex((d, i) => i > bodyIndex && d.op === 'stroke' && d.colour === OUTLINE && Math.abs(d.width - 10.5) < 1e-9);
  const toBody = inverse(drawings[bodyIndex].matrix);
  // drawCharacter at (0, 0) with size 112: design y = canvas y + 44.
  const toDesign = ([x, y]) => [mirrored ? -x : x, y + 44];
  return drawings.map((d, i) => ({
    op: d.op,
    colour: d.colour,
    width: Math.round(d.width * 1000) / 1000,
    alpha: d.alpha,
    text: d.text,
    part: i <= bodyIndex + 1 ? 'before' : i < firstArm ? 'clothes' : 'after',
    design: box(d.points.map(toDesign)),
    body: box(d.points.map((p) => apply(toBody, p))),
    screenMiddleX: Math.round(((box(d.points)[0] + box(d.points)[2]) / 2) * 1000) / 1000,
  }));
}

// The body colour of the plain grey figure (PLAIN_LOOK in characters.js),
// which report() needs to find the body box of an unknown id.
const PLAIN_BODY = '#B9B4A6';

function looksToDraw() {
  if (!process.env.CHARACTER_IDS) return world.characters;
  return JSON.parse(process.env.CHARACTER_IDS).map((id) => {
    const known = world.characters.find((look) => look.id === id);
    return { id, colour: known ? known.colour : PLAIN_BODY };
  });
}

// No prototype, so that an id like "__proto__" becomes a key of its own.
const result = Object.create(null);
looksToDraw().forEach((look) => {
  const poses = {};
  Object.entries(POSES).forEach(([name, pose]) => {
    const drawings = [];
    world.drawCharacter(recordingCanvas(drawings), look.id, 0, 0, 112, pose);
    poses[name] = report(look, drawings.filter((d) => d.points.length), Boolean(pose && pose.mirrored));
  });
  result[String(look.id)] = poses;
});
process.stdout.write(JSON.stringify(result));
