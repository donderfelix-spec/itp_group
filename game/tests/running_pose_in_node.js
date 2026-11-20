// Runs the page's own js/world/characters.js in Node, without a browser, for
// test_running_pose.py (M2-1.13): where the parts of a running character
// are drawn.
//
// The recording canvas and the reader of SVG paths are those of
// tests/characters_in_node.js: its part before "Drawing every character in
// every pose" is run here as it is, so all three harnesses measure the same
// way.
//
// Input (stdin): JSON list of poses, each {mirrored, walkPhase, stride}, or
// null for the portrait.
// Output (stdout): JSON {characterId: [drawings of pose 1, ...]}, one list of
// drawings per pose. A drawing is {op, colour, width, matrix, local}:
//   matrix  the canvas transform it was drawn with, mirrored back, so the
//           side the character is turned to is always +x;
//   local   the box [minX, minY, maxX, maxY] of its points in the
//           coordinates it was drawn in (before that transform).
// Every character is drawn with its middle at (0, 0) and a height of 112,
// so one unit of the canvas is one unit of the design (design y = canvas y + 44).
// An other characters.js can be given as the first argument (to compare
// with an older version by hand); the tests always use the page's own file.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HELPERS_FILE = path.join(__dirname, 'characters_in_node.js');
const CHARACTERS_JS = process.argv[2] || path.join(__dirname, '..', 'client', 'js', 'world', 'characters.js');
const END_OF_HELPERS = '// ---- Drawing every character in every pose';

function loadHelpers() {
  const source = fs.readFileSync(HELPERS_FILE, 'utf8');
  const end = source.indexOf(END_OF_HELPERS);
  if (end < 0) throw new Error('characters_in_node.js has changed: ' + END_OF_HELPERS + ' is missing');
  const context = { require, process, __dirname, console };
  return vm.runInNewContext(
    source.slice(0, end) + '\n({ recordingCanvas, FakePath2D, multiply, apply, inverse });',
    context,
    { filename: HELPERS_FILE },
  );
}

const { recordingCanvas, FakePath2D, multiply, apply, inverse } = loadHelpers();
const poses = JSON.parse(fs.readFileSync(0, 'utf8'));

const page = { Path2D: FakePath2D };
page.window = page;
vm.runInNewContext(fs.readFileSync(CHARACTERS_JS, 'utf8'), page, { filename: CHARACTERS_JS });
const world = page.Game.world;

const MIRROR = [-1, 0, 0, 1, 0, 0];
const round = (v) => Math.round(v * 1e9) / 1e9;

function localBox(drawing) {
  const toLocal = inverse(drawing.matrix);
  const points = drawing.points.map((p) => apply(toLocal, p));
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)].map(round);
}

const result = {};
world.characters.forEach((look) => {
  result[look.id] = poses.map((pose) => {
    const drawings = [];
    world.drawCharacter(recordingCanvas(drawings), look.id, 0, 0, 112, pose);
    const back = pose && pose.mirrored ? MIRROR : [1, 0, 0, 1, 0, 0];
    return drawings
      .filter((d) => d.points.length)
      .map((d) => ({
        op: d.op,
        colour: d.colour,
        width: round(d.width),
        matrix: multiply(back, d.matrix).map(round),
        local: localBox(d),
      }));
  });
});
process.stdout.write(JSON.stringify(result));
