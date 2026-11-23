// S-224: the page has one line for messages. When the host's leave also
// stops a Classic round the server sends "The host left. X is the new host."
// and then "Too many players left. The round was stopped."; the page shows
// both in one line, so the new host learns both. Notices further apart stay
// separate. Runs the real main.js with the stand-in page of
// classic_task_card_in_node.js.
// Run with: node game/tests/notices_together_in_node.js
// (pytest does it in tests/test_notices_together.py).
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const client = path.join(__dirname, '..', 'client', 'js');
const CAMPUS = {
  rooms: [{ id: 'canteen', name: 'Canteen' }],
  stations: [{ id: 3, name: 'Build the tray', room: 'canteen' }, { id: 1, name: 'Sort the slides', room: 'deck' }],
};

class Element {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this.className = '';
    this.attributes = {};
    this.style = {};
    this.hidden = false;
    this.disabled = false;
    this.title = '';
    this.events = {};
    this._text = '';
    this.classList = {
      add: (...values) => { this.className = [...new Set([...this.classes(), ...values])].join(' '); },
      remove: (...values) => { this.className = this.classes().filter((value) => !values.includes(value)).join(' '); },
      contains: (value) => this.classes().includes(value),
      toggle: (value, on) => {
        const enabled = on === undefined ? !this.classes().includes(value) : on;
        if (enabled) this.classList.add(value); else this.classList.remove(value);
        return enabled;
      },
    };
  }
  classes() { return this.className.split(/\s+/).filter(Boolean); }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this._text = ''; this.children = children; }
  set textContent(text) { this._text = String(text); this.children = []; }
  get textContent() { return this._text + this.children.map((child) => child.textContent).join(''); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  addEventListener(type, action) { this.events[type] = action; }
  removeEventListener() {}
  focus() {}
  blur() {}
  contains() { return false; }
  getContext() { return { scale() {}, beginPath() {}, arc() {}, fill() {}, stroke() {}, clearRect() {} }; }
  querySelectorAll(selector) {
    const matches = (node) => (selector.startsWith('.') ? node.classes().includes(selector.slice(1)) : node.tagName === selector);
    return this.children.flatMap((child) => [...(matches(child) ? [child] : []), ...child.querySelectorAll(selector)]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

function environment() {
  const ids = new Map();
  const handlers = new Map();
  const intervals = new Map();
  const asked = [];
  const sent = [];
  const shown = [];
  let reportHandler = null;
  let now = 0;
  let nextInterval = 1;
  let roundStarts = 0;
  const Game = {
    minigames: { close() {}, showDone() {}, isOpen: () => false },
    forms: { setup() {}, showSignedIn() {}, showHome() {}, showStart() {}, stopWaiting() {}, putCodeInJoinField() {}, showError: () => false },
    statistics: { setup() {}, setOwnName() {}, showProfile() {}, showLeaderboard() {} },
    classicMeeting: new Proxy({}, { get: () => () => undefined }),
    classicRound: new Proxy({}, { get: () => () => undefined }),
    screens: { current: () => 'lobby', show() {}, hideMessage() {}, showMessage: (text, isError) => shown.push([text, isError]), showLastingMessage() {} },
    net: { connect() {}, on: (type, action) => handlers.set(type, action), send: (message) => { sent.push(message); return true; }, ask: (message) => { asked.push(message); return true; } },
    world: { characters: [], setOwnName() {}, setPlayers() {}, start() {}, stop() {}, setUseHandler() {}, setPositions() {},
      setUsableStations() {}, startOfRound: () => { roundStarts += 1; },
      setReportHandler: (handler) => { reportHandler = handler; } },
  };
  const context = vm.createContext({
    Game, window: { Game, devicePixelRatio: 1 }, console,
    performance: { now: () => now },
    setInterval: (action) => { const id = nextInterval++; intervals.set(id, action); return id; },
    clearInterval: (id) => intervals.delete(id),
    setTimeout: () => 0,
    clearTimeout() {},
    // The map file with two stations, so names can be checked; read at once.
    fetch: () => Promise.resolve({ ok: true, json: () => CAMPUS }),
    document: {
      createElement: (tag) => new Element(tag),
      addEventListener() {}, removeEventListener() {},
      activeElement: null,
      getElementById: (id) => {
        if (!ids.has(id)) ids.set(id, new Element(id === 'lobby-players' ? 'ul' : 'div'));
        return ids.get(id);
      },
    },
  });
  const load = (file) => vm.runInContext(fs.readFileSync(path.join(client, file), 'utf8'), context, { filename: file });
  ['lobby/lobby.js', 'minigames/duel.js', 'lobby/countdown.js', 'main.js'].forEach(load);
  const list = ids.get('lobby-players');
  const rows = () => list.children;
  const progressOf = (row) => {
    const done = row.querySelector('.player-done');
    const fill = row.querySelector('.player-bar-fill');
    return done ? [done.textContent, fill.style.width] : null;
  };
  return {
    Game, ids, list, rows, progressOf, asked, sent, shown, document: context.document,
    report: (...values) => reportHandler(...values),
    emit: (type, payload) => handlers.get(type)(payload),
    roundStarts: () => roundStarts,
    intervalCount: () => intervals.size,
    advance: (milliseconds) => { now += milliseconds; [...intervals.values()].forEach((action) => action()); },
  };
}


function lobbyState(names, phase = 'round') {
  return { code: 'ABCD', host: names[0], mode: 'classic', phase, players: names.map((name) => ({ name, character: 'surfer' })) };
}


let checked = 0;
function check(condition, message) {
  assert.ok(condition, message);
  checked += 1;
}

const HOST = 'The host left. Tiago is the new host.';
const STOPPED = 'Too many players left. The round was stopped.';
const last = (env) => env.shown[env.shown.length - 1];

async function main() {
  const start = async () => {
    const env = environment();
    await new Promise((resolve) => setImmediate(resolve)); // the map file is read
    return env;
  };

  // Accepted: two notices that come together are one line.
  {
    const env = await start();
    env.emit('notice', { type: 'notice', message: HOST });
    env.emit('notice', { type: 'notice', message: STOPPED });
    check(last(env)[0] === HOST + ' ' + STOPPED, 'the host notice and the stop notice are shown together');
    check(last(env)[1] === false, 'a notice is no error');
  }

  // Rejected (kept apart): a notice long after the last one stands alone.
  {
    const env = await start();
    env.emit('notice', { type: 'notice', message: HOST });
    env.advance(5000);
    env.emit('notice', { type: 'notice', message: STOPPED });
    check(last(env)[0] === STOPPED, 'a later notice is shown alone');
  }

  // Edge cases: a single notice; exactly at the limit; the joined line is not joined twice.
  {
    const env = await start();
    env.emit('notice', { type: 'notice', message: HOST });
    check(last(env)[0] === HOST, 'one notice is shown as it is');
    env.advance(500);
    env.emit('notice', { type: 'notice', message: STOPPED });
    check(last(env)[0] === HOST + ' ' + STOPPED, 'exactly 500 ms apart still counts as together');
    env.advance(501);
    env.emit('notice', { type: 'notice', message: HOST });
    check(last(env)[0] === HOST, 'after more than 500 ms the next notice starts a new line');
  }
  console.log(`notices_together_in_node.js: all ${checked} checks passed`);
}

main().catch((problem) => { console.error(problem); process.exit(1); });
