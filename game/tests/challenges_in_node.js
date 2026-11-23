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

// Only a time per person (S-223). Empty, duplicate and wrong schedules
// fail and stay editable; solving the clues completes once.
const chat = open(samples.chat);
const chatFeedback = chat.body.querySelectorAll('.challenge-feedback')[0];
textButton(chat, 'Pin the schedule').click();
assert.equal(chat.done(), 0);
assert.equal(chatFeedback.textContent, 'Give every teammate a time first.');
const selects = chat.body.querySelectorAll('select');
assert.equal(selects.length, 4, 'one select per person, no work choice');
assert.ok(!chat.body.textContent.includes('Choose work'));
assert.ok(!chat.body.textContent.includes('deliverable'));
const slotOf = (person) => samples.chat.schedule.find((entry) => entry.person === person).slot + ':00';
// One time not chosen.
samples.chat.people.slice(0, 3).forEach((person, index) => selects[index].choose(slotOf(person)));
textButton(chat, 'Pin the schedule').click();
assert.equal(chat.done(), 0);
assert.equal(chatFeedback.textContent, 'Give every teammate a time first.');
// Two people at one time.
selects[3].choose(selects[0].value);
textButton(chat, 'Pin the schedule').click();
assert.equal(chat.done(), 0);
assert.equal(chatFeedback.textContent, 'One person per slot.');
// One wrong time: two people swapped.
samples.chat.people.forEach((person, index) => selects[index].choose(slotOf(person)));
const first = selects[0].value;
selects[0].choose(selects[1].value);
selects[1].choose(first);
textButton(chat, 'Pin the schedule').click();
chat.advance(1200);
assert.equal(chat.done(), 0);
assert.ok(chatFeedback.textContent.startsWith('Someone disagrees.'));
assert.ok(selects.every((select) => !select.disabled), 'a rejected schedule stays editable');
// Corrected after the rejection: accepted.
samples.chat.people.forEach((person, index) => selects[index].choose(slotOf(person)));
textButton(chat, 'Pin the schedule').click();
chat.advance(1200);
assert.equal(chat.done(), 1);
// A packet that still carries the old work field and five clues is refused.
const oldChat = open({ ...samples.chat, clues: [...samples.chat.clues, { from: 'Pinned message', text: 'x' }] });
assert.equal(oldChat.body.querySelectorAll('select').length, 0);

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

// Coffee costs a saved page once per cup, and the sixth net page ends the attempt.
const pages = samples.rescue.waves.filter((wave) => wave.cargo === 'page');
const coffees = samples.rescue.waves.filter((wave) => wave.cargo === 'coffee');
const scoredWaves = [coffees[0], pages[0], coffees[1], ...pages.slice(1), ...coffees.slice(2)];
const scoredRescue = open({ ...samples.rescue, waves: scoredWaves });
const score = scoredRescue.body.querySelectorAll('.challenge-score')[0];
const laneNames = ['Left', 'Middle', 'Right'];
const expectedPages = [0, 1, 0, 1, 2, 3, 4, 5, 6];
textButton(scoredRescue, 'Protect the draft').click();
scoredWaves.slice(0, expectedPages.length).forEach((wave, index) => {
  scoredRescue.advance(wave.duration * 0.65);
  const lane = textButton(scoredRescue, (wave.lane + 1) + ' · ' + laneNames[wave.lane]);
  lane.click();
  lane.click();
  assert.equal(score.textContent, `${expectedPages[index]} / 6 pages · 0 / 3 mistakes · wave ${index + 1} / 12`);
  scoredRescue.advance(0);
  if (expectedPages[index] < 6) {
    assert.equal(scoredRescue.done(), 0);
    scoredRescue.advance(wave.duration * 0.35 + 250);
  } else {
    assert.equal(scoredRescue.done(), 1, 'the sixth net page completes before its flight ends');
    assert.equal(scoredRescue.timers.size, 0, 'success cancels all remaining flights');
  }
});
scoredRescue.advance(60000);
assert.equal(scoredRescue.done(), 1);

// Running out of flights below six saved pages ends the attempt with a
// retry, even without three mistakes: five pages, then four coffees caught
// (down to one), then the last three pages leave four of six.
const drained = [...pages.slice(0, 5), ...coffees, ...pages.slice(5)];
const drainedRescue = open({ ...samples.rescue, waves: drained });
const drainedScore = drainedRescue.body.querySelectorAll('.challenge-score')[0];
textButton(drainedRescue, 'Protect the draft').click();
drained.forEach((wave) => {
  drainedRescue.advance(wave.duration * 0.65);
  textButton(drainedRescue, (wave.lane + 1) + ' · ' + laneNames[wave.lane]).click();
  drainedRescue.advance(wave.duration * 0.35 + 250);
});
assert.equal(drainedRescue.done(), 0, 'four of six pages is not a finished task');
assert.ok(drainedScore.textContent.startsWith('4 / 6 pages · 0 / 3 mistakes'));
assert.ok(textButton(drainedRescue, 'Try another rescue'), 'running out offers a retry');
assert.equal(drainedRescue.timers.size, 0, 'running out cancels every flight');

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
