// Play the real station 6 client with a controlled browser clock.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../client/js/minigames/catch_the_wave.js'), 'utf8');

function open(waveDuration) {
  let time = 0;
  let nextFrame = 0;
  let finished = 0;
  let focus;
  let start;
  const frames = new Map();
  // The page's keydown listeners (S-221: Space and Enter anywhere in the window).
  const keyListeners = new Set();

  function element(tag) {
    const listeners = {};
    const classes = new Set();
    return {
      tag,
      className: '',
      children: [],
      textContent: '',
      style: { setProperty(name, value) { this[name] = value; } },
      classList: {
        toggle(name, enabled) { if (enabled) classes.add(name); else classes.delete(name); },
        contains(name) { return classes.has(name); },
      },
      setAttribute() {},
      append(...children) { this.children.push(...children); },
      addEventListener(type, handler) { listeners[type] = handler; },
      focus() { focus = this; },
      fire(type, event) { listeners[type](event); },
    };
  }

  const page = {
    document: {
      createElement: element,
      addEventListener(type, handler) { if (type === 'keydown') keyListeners.add(handler); },
      removeEventListener(type, handler) { if (type === 'keydown') keyListeners.delete(handler); },
    },
    Game: { minigames: { register(kind, game) {
      assert.equal(kind, 'catch_the_wave');
      start = game.start;
    } } },
    performance: { now: () => time },
    requestAnimationFrame(callback) {
      frames.set(++nextFrame, callback);
      return nextFrame;
    },
    cancelAnimationFrame(id) { frames.delete(id); },
  };
  page.window = page;
  vm.runInNewContext(source, page);

  const body = element('div');
  const stop = start(body, { wave_duration_ms: waveDuration }, () => { finished += 1; });
  return {
    body, stop, frames,
    result: () => finished,
    focused: () => focus,
    keyListeners,
    // A key pressed while the focus is on an element with this tag name.
    press(key, tagName = 'SECTION', repeat = false) {
      let prevented = false;
      const event = { key, repeat, target: { tagName }, preventDefault() { prevented = true; } };
      keyListeners.forEach((handler) => handler(event));
      return prevented;
    },
    at(milliseconds) {
      time = milliseconds;
      const callbacks = [...frames.values()];
      frames.clear();
      callbacks.forEach((callback) => callback(time));
    },
  };
}

const duration = 2000;
const cycle = duration + 320;
const centreTime = Math.round(duration * 73 / 124);
const game = open(duration);
const [scene, controls, feedback] = game.body.children[0].children;
const [button, score] = controls.children;
assert.equal(game.focused(), button);
assert.equal(button.tag, 'button');

scene.fire('click');
assert.match(feedback.textContent, /Too early/);
game.at(centreTime);
button.fire('click');
assert.equal(score.textContent, '0 / 3 waves caught', 'Only one attempt per wave');

game.at(cycle + centreTime);
assert(scene.classList.contains('surf-in-range'));
scene.fire('click');
button.fire('click');
assert.equal(score.textContent, '1 / 3 waves caught', 'Only one catch per wave');

game.at(2 * cycle + 1900);
assert(!scene.classList.contains('surf-in-range'));
button.fire('click');
assert.match(feedback.textContent, /Too late/);
assert.equal(score.textContent, '1 / 3 waves caught', 'A miss preserves existing catches');

game.at(3 * cycle + centreTime);
button.fire('click');
assert.equal(score.textContent, '2 / 3 waves caught');
assert.equal(game.result(), 0);

game.at(4 * cycle + centreTime);
button.fire('click');
scene.fire('click');
assert.equal(game.result(), 1);
assert.equal(score.textContent, '3 / 3 waves caught');
assert.equal(button.disabled, true);
assert.equal(game.frames.size, 0, 'Completion cancels the animation');

const another = open(1800);
const [newScene, newControls] = another.body.children[0].children;
assert.equal(newControls.children[1].textContent, '0 / 3 waves caught');
another.stop();
another.at(Math.round(1800 * 73 / 124));
newScene.fire('click');
assert.equal(another.result(), 0);
assert.equal(another.frames.size, 0, 'Closing a task cancels the animation');

for (const invalid of [undefined, '2000', 1799, 2401]) {
  const unloaded = open(invalid);
  assert.equal(unloaded.body.children[0].textContent, 'This task could not be loaded.');
  assert.equal(unloaded.frames.size, 0);
}

// S-221: after a click on the water the focus is on the window, not on the
// button; Space and Enter still catch. On a button the browser clicks it, so
// the page leaves the key alone; a held key counts once.
const keys = open(2000);
const [, keyControls, keyFeedback] = keys.body.children[0].children;
const keyScore = keyControls.children[1];
assert.equal(keys.keyListeners.size, 1);
assert.equal(keys.press(' '), true, 'Space in the window is taken by the game');
assert.match(keyFeedback.textContent, /Too early/);
keys.at(cycle + centreTime);
assert.equal(keys.press(' ', 'BUTTON'), false, 'Space on a button is left to the button');
assert.equal(keyScore.textContent, '0 / 3 waves caught');
assert.equal(keys.press('Enter', 'SECTION', true), false, 'a held key does not try again');
assert.equal(keys.press('a'), false, 'other keys are left alone');
keys.press('Enter');
assert.equal(keyScore.textContent, '1 / 3 waves caught');
keys.at(2 * cycle + centreTime);
keys.press(' ');
keys.at(3 * cycle + centreTime);
keys.press(' ');
assert.equal(keys.result(), 1);
assert.equal(keys.keyListeners.size, 0, 'Completion removes the key listener');
const closedByKey = open(2000);
closedByKey.stop();
assert.equal(closedByKey.keyListeners.size, 0, 'Closing a task removes the key listener');
console.log('Catch the Wave timing, controls and cleanup passed');
