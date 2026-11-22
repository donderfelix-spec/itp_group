// Runs client/js/world/vision.js in Node with a canvas that records every
// call, for tests/test_classic_vision_soft_edge.py. Prints one JSON line.
'use strict';
const path = require('path');

global.Game = { world: {} };
require(path.join(__dirname, '..', 'client', 'js', 'world', 'vision.js'));
const campus = require(path.join(__dirname, '..', 'client', 'js', 'world', 'campus.json'));
const vision = Game.world.vision;

function recordingContext() {
  const calls = [];
  const saved = []; // what save() keeps, as on a real canvas
  const ctx = {
    calls,
    fillStyle: '#000000',
    globalAlpha: 1,
    save() { saved.push([this.fillStyle, this.globalAlpha]); calls.push(['save']); },
    restore() { [this.fillStyle, this.globalAlpha] = saved.pop(); calls.push(['restore']); },
    beginPath() { calls.push(['beginPath']); },
    rect(...a) { calls.push(['rect', ...a]); },
    moveTo(x, y) { calls.push(['moveTo', x, y]); },
    lineTo(x, y) { calls.push(['lineTo', x, y]); },
    arc(...a) { calls.push(['arc', ...a]); },
    closePath() { calls.push(['closePath']); },
    clip() { calls.push(['clip']); },
    fillRect(...a) { calls.push(['fillRect', ...a]); },
    fill(rule) { calls.push(['fill', rule === undefined ? null : rule, describe(this.fillStyle)]); },
    createRadialGradient(...a) {
      const gradient = { radial: a, stops: [], addColorStop(at, colour) { this.stops.push([at, colour]); } };
      calls.push(['createRadialGradient', ...a]);
      return gradient;
    },
    depth: () => saved.length,
  };
  return ctx;
}

function describe(style) {
  return typeof style === 'string' ? style : { radial: style.radial, stops: style.stops };
}

function draw(origin, range) {
  const ctx = recordingContext();
  const at = { x: 486, y: 296 };
  const points = vision.boundary(campus, at);
  vision.darken(ctx, { x: at.x - 130, y: at.y - 115, w: 260, h: 230 }, points, origin, range);
  return {
    calls: ctx.calls.filter((call) => call[0] !== 'lineTo'),
    lineTos: ctx.calls.filter((call) => call[0] === 'lineTo').length,
    points: points.length,
    first: points[0],
    depthAfter: ctx.depth(),
    fillStyleAfter: describe(ctx.fillStyle),
    globalAlphaAfter: ctx.globalAlpha,
  };
}

process.stdout.write(JSON.stringify({
  rangeOfCampus: vision.rangeOf(campus),
  rangeOfEmpty: vision.rangeOf({ solids: [] }),
  fadeFrom: vision.FADE_FROM,
  hard: draw(undefined, undefined),
  zeroRange: draw({ x: 486, y: 296 }, 0),
  soft: draw({ x: 486, y: 296 }, 150),
}) + '\n');
