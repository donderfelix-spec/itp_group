// Runs client/js/world/vision.js in Node, for tests/test_classic_soft_wall_shadow.py.
// Reads {"places": [[x, y], ...]} on stdin and prints one JSON line:
//   points       sightPoints() of every place
//   radius       SAMPLE_RADIUS
//   noDocument   darkenSoftly() without a document: its answer and the calls on ctx
//   soft         darkenSoftly() with recording canvases: the calls on every canvas
'use strict';
const path = require('path');

global.Game = { world: {} };
require(path.join(__dirname, '..', 'client', 'js', 'world', 'vision.js'));
const campus = require(path.join(__dirname, '..', 'client', 'js', 'world', 'campus.json'));
const vision = Game.world.vision;

// A 2D context that records every call with the state it was made in.
function recordingContext(name, log) {
  const saved = [];
  const ctx = {
    fillStyle: '#000000',
    globalAlpha: 1,
    globalCompositeOperation: 'source-over',
    imageSmoothingEnabled: true,
    depth: () => saved.length,
  };
  const state = () => [ctx.globalCompositeOperation, ctx.globalAlpha];
  const record = (call, args) => log.push([name, call, args, state()]);
  ctx.save = () => { saved.push([ctx.fillStyle, ctx.globalAlpha, ctx.globalCompositeOperation, ctx.imageSmoothingEnabled]); record('save', []); };
  ctx.restore = () => {
    [ctx.fillStyle, ctx.globalAlpha, ctx.globalCompositeOperation, ctx.imageSmoothingEnabled] = saved.pop();
    record('restore', []);
  };
  ['beginPath', 'rect', 'moveTo', 'closePath', 'clip', 'clearRect', 'setTransform'].forEach((call) => {
    ctx[call] = (...args) => record(call, args);
  });
  ctx.lineTo = () => {};
  ctx.fill = (rule) => record('fill', [rule === undefined ? null : rule, typeof ctx.fillStyle === 'string' ? ctx.fillStyle : 'gradient']);
  ctx.fillRect = (...args) => record('fillRect', [...args, ctx.fillStyle]);
  ctx.drawImage = (image, ...args) => record('drawImage', [image.label, ...args, ctx.imageSmoothingEnabled]);
  ctx.createRadialGradient = (...args) => {
    record('createRadialGradient', args);
    return { addColorStop() {} };
  };
  return ctx;
}

function recordedDarkenSoftly(origin) {
  const log = [];
  let made = 0;
  global.document = {
    createElement(tag) {
      const label = ['fog', 'layer', 'smooth'][made++];
      const canvas = { label, tag, width: 300, height: 150 };
      const context = recordingContext(label, log);
      canvas.getContext = () => context;
      return canvas;
    },
  };
  const main = recordingContext('main', log);
  const view = { x: origin.x - 130.5, y: origin.y - 92.25, w: 261, h: 184.5 };
  const answer = vision.darkenSoftly(main, view, campus, origin);
  delete global.document;
  return { answer, view, log, mainDepth: main.depth(), mainSmoothing: main.imageSmoothingEnabled };
}

let input = '';
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => {
  const places = JSON.parse(input || '{"places": []}').places;
  const bare = [];
  const noDocumentAnswer = vision.darkenSoftly(recordingContext('main', bare), { x: 0, y: 0, w: 260, h: 185 }, campus, { x: 505, y: 248 });
  process.stdout.write(JSON.stringify({
    radius: vision.SAMPLE_RADIUS,
    points: places.map(([x, y]) => vision.sightPoints({ x, y })),
    noDocument: { answer: noDocumentAnswer, calls: bare },
    soft: recordedDarkenSoftly({ x: 505, y: 248 }),
  }) + '\n');
});
