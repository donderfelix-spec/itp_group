// The × of the minigame window while a minigame runs and in its "Done"
// state (Felix, 2026-11-21): visible and reachable with Tab before the
// solve, hidden and out of the Tab order after it. Runs the real
// client/js/minigames/frame.js with a tiny stand-in for the page.
// Run with: node game/tests/test_minigame_done_close.js
// (pytest does it in tests/test_node_harnesses_area4.py).
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');

let focused = null;

class Element {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this.parent = null;
    this.className = '';
    this.attributes = {};
    this.hidden = false;
    this.disabled = false;
    this.tabIndex = ['button', 'input', 'select', 'textarea'].includes(tag) ? 0 : -1;
    this.events = {};
    this.textContent = '';
  }
  append(...children) { children.forEach((child) => { child.parent = this; this.children.push(child); }); }
  replaceChildren() { this.children = []; }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter((child) => child !== this); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  addEventListener(type, action) { this.events[type] = action; }
  focus() { focused = this; }
  blur() { if (focused === this) focused = null; }
  contains(other) { return other === this || this.children.some((child) => child.contains(other)); }
  // A hidden element, or one inside a hidden one, takes no room on the page.
  getClientRects() {
    for (let node = this; node; node = node.parent) if (node.hidden) return [];
    return [{}];
  }
  all() { return this.children.flatMap((child) => [child, ...child.all()]); }
  // Enough of CSS selectors for frame.js: ".class" and its FOCUSABLE list.
  querySelectorAll(selector) {
    const parts = selector.split(',').map((part) => part.trim());
    const matches = (node) => parts.some((part) => {
      if (part.startsWith('.')) return node.className.split(' ').includes(part.slice(1));
      if (part === '[tabindex]') return node.tabIndex >= 0 && !['button', 'input', 'select', 'textarea'].includes(node.tagName);
      if (part === 'a[href]') return node.tagName === 'a' && 'href' in node.attributes;
      return node.tagName === part;
    });
    return this.all().filter(matches);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

const container = new Element('div');
const keyHandlers = [];
const timers = [];
const asked = [];
// The messages come from the page's own realm, so they are compared as text.
const lastAsked = () => JSON.stringify(asked.at(-1));
const page = {
  console: console,
  setTimeout: (action) => { timers.push(action); return timers.length; },
  clearTimeout: () => {},
  setInterval: () => 1,
  clearInterval: () => {},
  document: {
    createElement: (tag) => new Element(tag),
    getElementById: (id) => (id === 'minigame' ? container : null),
    addEventListener: (type, action) => { if (type === 'keydown') keyHandlers.push(action); },
    removeEventListener: () => {},
    get activeElement() { return focused; },
  },
};
page.window = page;
page.Game = { net: { ask: (message) => { asked.push(message); return true; } }, world: { setInputPaused() {} } };
vm.createContext(page);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'client', 'js', 'minigames', 'frame.js'), 'utf8'), page);
const minigames = page.Game.minigames;

function closeButton() { return container.querySelector('.minigame-close'); }
function pressTab() {
  keyHandlers.forEach((handler) => handler({ key: 'Tab', shiftKey: false, preventDefault() {} }));
  return focused;
}
// Every control Tab stops at, going once round the window.
function tabStops() {
  const stops = new Set();
  for (let step = 0; step < 6; step += 1) stops.add(pressTab());
  return stops;
}

// Before the solve: the × is there and Tab reaches it.
assert.equal(minigames.open(1, 'Sort the slides', { kind: 'placeholder' }), true);
assert.equal(closeButton().hidden, false, 'the × is visible while the minigame runs');
assert.equal(closeButton().disabled, false, 'the × works while the minigame runs');
assert.ok(tabStops().has(closeButton()), 'Tab reaches the × while the minigame runs');
closeButton().events.click();
assert.equal(lastAsked(), '{"type":"close_station"}', 'the × asks the server to close');

// After the solve: "Done", the × is hidden and Tab never stops at it.
container.querySelector('.button-main').events.click();
assert.equal(lastAsked(), '{"type":"finish_station"}');
minigames.showDone();
const button = closeButton();
assert.ok(button, 'the × stays in the window, only hidden');
assert.equal(button.hidden, true, 'the × is hidden in the Done state');
assert.equal(button.disabled, true, 'the × is switched off in the Done state');
assert.equal(container.querySelector('.minigame-done').textContent, 'Done');
const stops = tabStops();
assert.ok(!stops.has(button), 'Tab never stops at the hidden ×');
const window_ = container.querySelector('.minigame-window');
assert.ok(stops.size === 1 && stops.has(window_), 'with nothing left to reach, the window keeps the focus');
keyHandlers.forEach((handler) => handler({ key: 'Escape', preventDefault() {} }));
assert.equal(lastAsked(), '{"type":"finish_station"}', 'Esc closes nothing in the Done state');

// The window closes by itself; a new opening has its × again.
timers.forEach((action) => action());
assert.equal(minigames.isOpen(), false);
minigames.open(2, 'Brew the order', { kind: 'placeholder' });
assert.equal(closeButton().hidden, false, 'the next window has its × again');

console.log('Minigame close button checks passed: visible and reachable while running, hidden and out of the Tab order once done.');
