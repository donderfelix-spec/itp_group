// M3-3.21: a double click or a double R on "R Report" sends the report once.
// The second one, before the answer (the meeting or a refusal), is swallowed,
// so the player never sees the red refusal of a second report. Runs the real
// main.js (with lobby/lobby.js, minigames/duel.js, lobby/countdown.js) and the
// stand-in page of classic_task_card_in_node.js.
// Run with: node game/tests/classic_report_once_in_node.js
// (pytest does it in tests/test_classic_report_once.py).
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
    screens: { current: () => 'lobby', show() {}, hideMessage() {}, showMessage() {}, showLastingMessage() {} },
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
    Game, ids, list, rows, progressOf, asked, sent, document: context.document,
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

const SHEET = 'f-sheet-1';
const PLACE = { x: 10, y: 20 };
const reports = (env) => env.sent.filter((message) => message.type === 'report');

async function main() {
  const start = async () => {
    const env = environment();
    await new Promise((resolve) => setImmediate(resolve)); // the map file is read
    env.emit('signed_in', { name: 'Mara', guest: true });
    env.emit('lobby_state', lobbyState(['Mara', 'Tiago', 'Ines', 'Rui']));
    return env;
  };

  // Accepted: the first report is sent.
  {
    const env = await start();
    env.report(SHEET, PLACE);
    check(reports(env).length === 1, 'the first report is sent');
    check(JSON.stringify(reports(env)[0]) === JSON.stringify({ type: 'report', sheet_id: SHEET, position: PLACE }), 'with the sheet and the place');
  }

  // Rejected (quietly): a second report before the answer is not sent.
  {
    const env = await start();
    env.report(SHEET, PLACE);
    env.report(SHEET, PLACE);
    env.report('f-sheet-2', PLACE);
    check(reports(env).length === 1, 'a double click or a double R sends one report');
  }

  // Edge cases: every kind of answer ends the wait.
  {
    const env = await start();
    env.report(SHEET, PLACE);
    env.emit('meeting_state', { type: 'meeting_state', phase: 'discussion' });
    env.report('f-sheet-2', PLACE);
    check(reports(env).length === 2, 'after the meeting started, a later report is sent again');
  }
  {
    const env = await start();
    env.report(SHEET, PLACE);
    env.emit('error', { type: 'error', code: 'report_rejected', message: 'You cannot report that F-sheet right now.' });
    env.report(SHEET, PLACE);
    check(reports(env).length === 2, 'after a refusal the player can try again');
  }
  {
    const env = await start();
    env.report(SHEET, PLACE);
    env.emit('lobby_state', lobbyState(['Mara', 'Tiago', 'Ines', 'Rui'], 'lobby'));
    env.emit('lobby_state', lobbyState(['Mara', 'Tiago', 'Ines', 'Rui'], 'round'));
    env.report(SHEET, PLACE);
    check(reports(env).length === 2, 'a new round does not inherit the wait of the last one');
  }
  {
    const env = await start();
    env.emit('lobby_state', lobbyState(['Mara', 'Tiago', 'Ines', 'Rui'], 'lobby'));
    env.report(SHEET, PLACE);
    check(reports(env).length === 0, 'outside a round nothing is sent, and nothing waits');
    env.emit('lobby_state', lobbyState(['Mara', 'Tiago', 'Ines', 'Rui'], 'round'));
    env.report(SHEET, PLACE);
    check(reports(env).length === 1, 'in the next round the first report is sent');
  }
  console.log(`classic_report_once_in_node.js: all ${checked} checks passed`);
}

main().catch((problem) => { console.error(problem); process.exit(1); });
