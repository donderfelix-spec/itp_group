// The own Classic task card in the side panel (S-154, briefs 3 and 4 of M2-2.11):
// lobby.js's classicTaskCard and main.js's handling of `classic_role` and
// `station_done`. Runs the real lobby/lobby.js, minigames/duel.js,
// lobby/countdown.js and main.js with a small stand-in for the page (the
// Element class and the environment are those of test_client_player_progress.js).
// Run with: node game/tests/classic_task_card_in_node.js
// (pytest does it in tests/test_classic_task_card.py).
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
    net: { connect() {}, on: (type, action) => handlers.set(type, action), send() {}, ask: (message) => { asked.push(message); return true; } },
    world: { characters: [], setOwnName() {}, setPlayers() {}, start() {}, stop() {}, setUseHandler() {}, setPositions() {},
      setUsableStations() {}, startOfRound: () => { roundStarts += 1; } },
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
    Game, ids, list, rows, progressOf, asked, document: context.document,
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

// ---- classicTaskCard: a plain function ----
{
  const env = environment();
  const card = (...values) => JSON.stringify(env.Game.lobby.classicTaskCard(...values));
  const item = (station, done) => ({ station, done });
  check(card('HP', [3, 1, 8], [3, 1, 8]) === JSON.stringify({ items: [item(3, false), item(1, false), item(8, false)], note: null, allDone: false }),
    'every task open, in the order of the start list');
  check(card('HP', [3, 1, 8], [8, 3]) === JSON.stringify({ items: [item(3, false), item(1, true), item(8, false)], note: null, allDone: false }),
    'a finished task stays in its place, marked done; the order of the open list does not matter');
  check(card('HP', [3, 1], []) === JSON.stringify({ items: [item(3, true), item(1, true)], note: 'All your tasks are done.', allDone: true }),
    'all done: the list stays and the done line comes');
  check(card('HP', [], [5, 2]) === JSON.stringify({ items: [item(5, false), item(2, false)], note: null, allDone: false }),
    'without a start list only the open ones are shown, none is made up as done');
  check(card('HP', [3], [3, 9]) === JSON.stringify({ items: [item(3, false), item(9, false)], note: null, allDone: false }),
    'an open station missing from the start list is added at the end');
  check(card('FR', [], []) === JSON.stringify({ items: [], note: 'Fake tasks: stand at a station to look busy.', allDone: false }),
    'the Free Rider fakes');
  check(card('FR', [3], [3]).includes('Fake tasks') && !card('FR', [3], [3]).includes('"station"'), 'a Free Rider never lists stations');
}

// What the card element shows: its lines (with a done mark), its note, its colour.
function readCard(card) {
  const list = card.children.find((child) => child.tagName === 'ul');
  const note = card.children.find((child) => child.tagName === 'p');
  return {
    lines: list ? list.children.map((row) => (row.classes().includes('round-task-done') ? 'DONE ' : '') + row.textContent) : [],
    note: note ? note.textContent : null,
    green: card.classList.contains('duel-next-finished'),
  };
}

async function main() {
  // ---- main.js: a High Performer's round ----
  {
    const env = environment();
    await new Promise((resolve) => setImmediate(resolve)); // the map file is read
    env.emit('signed_in', { name: 'Mara', guest: true });
    env.emit('lobby_state', lobbyState(['Mara', 'Tiago', 'Ines', 'Rui']));
    const card = env.document.getElementById('classic-task');
    check(card.hidden === true || card.children.length === 0, 'no card before the role is known');
    env.emit('classic_role', { role: 'HP', task_stations: [3, 1, 8] });
    check(card.hidden === false, 'the card is shown');
    let seen = readCard(card);
    check(JSON.stringify(seen.lines) === JSON.stringify(['Build the tray (Canteen)', 'Sort the slides (Main Deck)', 'Station 8']),
      'one bullet per task, names and rooms of the map file; a station without a name falls back to its number: ' + seen.lines);
    check(seen.note === null && !seen.green, 'no done line and not green while tasks remain');
    env.emit('station_done', { station: 3, task_stations: [1, 8] });
    seen = readCard(card);
    check(JSON.stringify(seen.lines) === JSON.stringify(['DONE Build the tray (Canteen) (done)', 'Sort the slides (Main Deck)', 'Station 8']),
      'a finished station stays in its place, marked done (faded), with a hidden "(done)": ' + seen.lines);
    env.emit('station_done', { station: 8 }); // no list (malformed): the finished one is marked all the same
    seen = readCard(card);
    check(JSON.stringify(seen.lines) === JSON.stringify(['DONE Build the tray (Canteen) (done)', 'Sort the slides (Main Deck)', 'DONE Station 8 (done)']),
      'the station finished here is marked even without a new list; the order stays: ' + seen.lines);
    env.emit('station_done', { station: 1, task_stations: [] });
    seen = readCard(card);
    check(seen.lines.every((line) => line.startsWith('DONE ')) && seen.lines.length === 3, 'all three marked done, in place');
    check(seen.note === 'All your tasks are done.' && seen.green, 'the done line under the list, the card green');
    env.emit('classic_role', { role: 'XX', task_stations: [3] });
    check(readCard(card).note === 'All your tasks are done.', 'an unknown role changes nothing');
    env.emit('lobby_state', lobbyState(['Mara', 'Tiago', 'Ines', 'Rui'], 'lobby'));
    check(card.hidden === true && card.children.length === 0, 'back in the lobby the card is hidden and empty');
  }

  // ---- main.js: the Free Rider ----
  {
    const env = environment();
    env.emit('signed_in', { name: 'Tiago', guest: true });
    env.emit('lobby_state', lobbyState(['Mara', 'Tiago', 'Ines', 'Rui']));
    env.emit('classic_role', { role: 'FR', task_stations: [], other_free_riders: [] });
    const card = env.document.getElementById('classic-task');
    const seen = readCard(card);
    check(card.hidden === false && seen.lines.length === 0 && seen.note === 'Fake tasks: stand at a station to look busy.', 'the Free Rider card');
    check(!seen.green, 'the Free Rider card is not green');
    env.emit('left_lobby');
    check(card.hidden === true && card.children.length === 0, 'leaving hides the card');
  }

  // ---- Edge: a role outside a Classic round is ignored ----
  {
    const env = environment();
    env.emit('signed_in', { name: 'Mara', guest: true });
    env.emit('lobby_state', { ...lobbyState(['Mara', 'Tiago']), mode: 'duel' });
    env.emit('classic_role', { role: 'HP', task_stations: [3] });
    const card = env.document.getElementById('classic-task');
    check(card.hidden === true || card.children.length === 0, 'no card in a Duel');
  }

  console.log('Classic task card checks passed: ' + checked + ' assertions.');
}

main().catch((problem) => { console.error(problem); process.exit(1); });
