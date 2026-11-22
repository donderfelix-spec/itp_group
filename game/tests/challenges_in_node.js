// Run the actual challenge handlers with a controlled clock and a small DOM.
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('node:assert/strict');
const samples = JSON.parse(fs.readFileSync(0, 'utf8'));

class Element {
  constructor(tag) {
    this.tagName = tag.toUpperCase(); this.children = []; this.attributes = {};
    this.style = {}; this.events = {}; this.className = ''; this.disabled = false;
    this.value = ''; this._text = ''; this.parent = null;
    this.classList = { add: (name) => { this.className += ' ' + name; } };
  }
  append(...children) { children.forEach((child) => { child.parent = this; this.children.push(child); }); }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map((child) => child.textContent).join(''); }
  setAttribute(name, value) { this.attributes[name] = String(value); if (name === 'class') this.className = value; }
  getAttribute(name) { return this.attributes[name]; }
  addEventListener(name, action) { this.events[name] = action; }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter((child) => child !== this); }
  querySelectorAll(selector) {
    const matches = (child) => selector.split(',').some((part) => {
      const value = part.trim();
      return value.startsWith('.') ? child.className.split(' ').includes(value.slice(1)) : child.tagName === value.toUpperCase();
    });
    return this.children.flatMap((child) => [...(matches(child) ? [child] : []), ...child.querySelectorAll(selector)]);
  }
  click() { if (!this.disabled && this.events.click) this.events.click(); }
  choose(value) { if (!this.disabled) { this.value = String(value); this.events.change(); } }
}

function open(content) {
  let clock = 0; let id = 0; let done = 0; let registered;
  const timers = new Map(); const listeners = new Map();
  const document = { createElement: (tag) => new Element(tag), createElementNS: (_ns, tag) => new Element(tag),
    addEventListener: (type, fn) => listeners.set(type, fn),
    removeEventListener: (type, fn) => { if (listeners.get(type) === fn) listeners.delete(type); } };
  const Game = { minigames: { register: (_kind, renderer) => { registered = renderer; } } };
  const context = { Game, window: { Game }, document, performance: { now: () => clock },
    setTimeout: (fn, delay) => { const key = ++id; timers.set(key, { fn, at: clock + delay }); return key; },
    clearTimeout: (key) => timers.delete(key) };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../client/js/minigames/campus_challenges.js'), 'utf8'), context);
  const body = new Element('div');
  const stop = registered.start(body, content, () => { done += 1; });
  return { body, stop, timers, listeners, done: () => done, now: () => clock,
    advance(ms) {
      const end = clock + ms;
      for (;;) {
        const next = [...timers].sort((a, b) => a[1].at - b[1].at)[0];
        if (!next || next[1].at > end) break;
        timers.delete(next[0]); clock = next[1].at; next[1].fn();
      }
      clock = end;
    } };
}

const buttons = (game) => game.body.querySelectorAll('button');
const textButton = (game, text) => buttons(game).find((button) => button.textContent === text);

// Fixing a chart requires honest values, unique labels and a zero baseline.
const chart = open(samples.chart);
textButton(chart, 'Publish honest chart').click();
assert.equal(chart.done(), 0);
const chartSelects = chart.body.querySelectorAll('select');
samples.chart.rows.forEach((row, index) => {
  chartSelects[index].choose(row.label);
  const difference = row.count * 10 - samples.chart.initial_values[index];
  const action = buttons(chart).filter((button) => button.textContent === (difference > 0 ? '+10' : '−10'))[index];
  for (let step = 0; step < Math.abs(difference) / 10; step++) action.click();
});
textButton(chart, 'Publish honest chart').click();
assert.equal(chart.done(), 0, 'nonzero baseline must still fail');
chartSelects[3].choose(0);
textButton(chart, 'Publish honest chart').click();
chart.advance(1200);
assert.equal(chart.done(), 1);
chart.advance(10000);
assert.equal(chart.done(), 1);

// Empty and duplicate schedules fail. Solving the clues completes once.
const chat = open(samples.chat);
textButton(chat, 'Pin the schedule').click();
assert.equal(chat.done(), 0);
const selects = chat.body.querySelectorAll('select');
samples.chat.people.forEach((person, index) => {
  const answer = samples.chat.schedule.find((entry) => entry.person === person);
  selects[index * 2].choose(answer.slot + ':00');
  selects[index * 2 + 1].choose(answer.job);
});
selects[0].choose(selects[2].value);
textButton(chat, 'Pin the schedule').click();
assert.equal(chat.done(), 0);
selects[0].choose(samples.chat.schedule.find((entry) => entry.person === samples.chat.people[0]).slot + ':00');
textButton(chat, 'Pin the schedule').click();
chat.advance(1200);
assert.equal(chat.done(), 1);

// Reaction game can fail, retry, win, and cancel while timers are active.
const rescue = open(samples.rescue);
textButton(rescue, 'Protect the draft').click();
for (let index = 0; index < 3; index++) textButton(rescue, '1 · Left').click();
assert.ok(textButton(rescue, 'Try another rescue'));
assert.equal(rescue.timers.size, 0, 'a failed round must cancel its flights');
textButton(rescue, 'Try another rescue').click();
samples.rescue.waves.forEach((wave) => {
  rescue.advance(wave.duration * 0.65);
  if (wave.cargo === 'page') {
    const name = ['Left', 'Middle', 'Right'][wave.lane];
    textButton(rescue, (wave.lane + 1) + ' · ' + name).click();
  }
  rescue.advance(wave.duration * 0.35 + 250);
});
rescue.advance(1200);
assert.equal(rescue.done(), 1);
assert.equal(rescue.timers.size, 0);
rescue.stop();
assert.equal(rescue.listeners.size, 0);
const closed = open(samples.rescue);
textButton(closed, 'Protect the draft').click();
closed.stop();
closed.advance(60000);
assert.equal(closed.done(), 0);
assert.equal(closed.timers.size, 0);
assert.equal(closed.listeners.size, 0);

// A malformed packet never constructs playable controls.
const invalid = open({ ...samples.rescue, waves: [] });
assert.equal(buttons(invalid).length, 0);
assert.ok(invalid.body.textContent.includes('could not be loaded'));
console.log('Challenge interactions, retries, completion and cancellation passed.');
