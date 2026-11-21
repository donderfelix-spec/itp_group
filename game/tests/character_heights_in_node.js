// Runs the page's own js/world/characters.js in Node, without a browser, for
// test_running.py (M2-1.13): how high does a running character reach?
//
// The recording canvas and the reader of SVG paths are those of
// tests/characters_in_node.js: its part before "Drawing every character in
// every pose" is run here as it is, so both harnesses measure the same way.
//
// Input (stdin): JSON list of poses, each {mirrored, walkPhase, stride}.
// Output (stdout): JSON {characterId: [highest, ...]}, one number per pose:
// the highest point of the drawing in design units (y = -12 is the top of a
// standing character). A line counts with half its width above its path.
// Every character is drawn with its middle at (0, 0) and a height of 112,
// so one unit of the canvas is one unit of the design, and design y is
// canvas y + 44.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HELPERS_FILE = path.join(__dirname, 'characters_in_node.js');
const CHARACTERS_JS = path.join(__dirname, '..', 'client', 'js', 'world', 'characters.js');
const END_OF_HELPERS = '// ---- Drawing every character in every pose';

function loadHelpers() {
  const source = fs.readFileSync(HELPERS_FILE, 'utf8');
  const end = source.indexOf(END_OF_HELPERS);
  if (end < 0) throw new Error('characters_in_node.js has changed: ' + END_OF_HELPERS + ' is missing');
  const context = { require, process, __dirname, console };
  // The last line hands the two helpers this harness needs back from the script.
  return vm.runInNewContext(source.slice(0, end) + '\n({ recordingCanvas, FakePath2D });', context, { filename: HELPERS_FILE });
}

const { recordingCanvas, FakePath2D } = loadHelpers();
const poses = JSON.parse(fs.readFileSync(0, 'utf8'));

const page = { Path2D: FakePath2D };
page.window = page;
vm.runInNewContext(fs.readFileSync(CHARACTERS_JS, 'utf8'), page, { filename: CHARACTERS_JS });
const world = page.Game.world;

function highestPoint(drawings) {
  let highest = Infinity;
  drawings.forEach((drawing) => {
    drawing.points.forEach(([, y]) => {
      highest = Math.min(highest, (y - drawing.width / 2) * 104 / 112 + 48);
    });
  });
  return highest;
}

const result = {};
world.characters.forEach((look) => {
  result[look.id] = poses.map((pose) => {
    const drawings = [];
    world.drawCharacter(recordingCanvas(drawings), look.id, 0, 0, 112, pose);
    return highestPoint(drawings.filter((drawing) => drawing.points.length));
  });
});
process.stdout.write(JSON.stringify(result));
