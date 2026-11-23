// The line in the card at the top left in Classic (S-197): "All your tasks
// are done." for a High Performer who finished all four, the Free Rider's
// "Fake tasks: stand at a station to look busy.", for the player concerned
// only. Part 1 runs the real minigames/task_navigation.js with a small page,
// part 2 the real main.js with the other modules as stand-ins.
// Run with: node game/tests/classic_card_note_in_node.js
// (pytest does it in tests/test_classic_card_note.py).
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const client = path.join(__dirname, '..', 'client', 'js');

const DONE = 'All your tasks are done.';
const FAKE = 'Fake tasks: stand at a station to look busy.';
let checked = 0;
function check(condition, message) {
  assert.ok(condition, message);
  checked += 1;
}

class Element {
  constructor() {
    this.hidden = true;
    this.textContent = '';
    this.names = new Set();
    this.classList = {
      toggle: (name, on) => { if (on) this.names.add(name); else this.names.delete(name); },
      contains: (name) => this.names.has(name),
      add: (name) => this.names.add(name),
      remove: (name) => this.names.delete(name),
    };
  }
}

function page(withNote = true) {
  const ids = new Map();
  return {
    ids,
    document: {
      getElementById: (id) => {
        if (id === 'task-card-note' && !withNote) return null; // an old page without the line
        if (!ids.has(id)) ids.set(id, new Element());
        return ids.get(id);
      },
    },
  };
}

// ---- Part 1: the card ----
function navigation(withNote = true) {
  const { ids, document } = page(withNote);
  const Game = {};
  const context = vm.createContext({ Game, window: { Game }, document, console, Math, Number, JSON });
  const file = 'minigames/task_navigation.js';
  vm.runInContext(fs.readFileSync(path.join(client, file), 'utf8'), context, { filename: file });
  return { nav: Game.taskNavigation, ids };
}

const CAMPUS = {
  stations: [{ id: 3, name: 'Build the tray', room: 'canteen', x: 200, y: 200 }],
  rooms: [{ id: 'canteen', name: 'Canteen' }],
  use_range: 25,
};
const HERE = { x: 20, y: 20 };
const ctx = new Proxy({}, { get: () => () => undefined }); // drawing does nothing here

{
  const { nav, ids } = navigation();
  const note = () => ids.get('task-card-note');
  const card = () => ids.get('task-card');
  const task = () => ids.get('task-card-task');

  nav.setNote(DONE, true);
  nav.draw(ctx, CAMPUS, HERE, HERE, false);
  check(!card().hidden && !note().hidden && note().textContent === DONE, 'all done: the line stands in the card');
  check(note().classList.contains('task-card-note-done'), 'all done: the line is green');
  check(task().hidden, 'no task part beside the line');

  nav.setTarget(3);
  nav.draw(ctx, CAMPUS, HERE, HERE, false);
  check(!task().hidden && ids.get('task-card-title').textContent === 'Build the tray', 'a task goes first');
  check(note().hidden && note().textContent === '', 'the line gives way to a task');

  nav.setTarget(null);
  nav.setNote(FAKE, false);
  nav.draw(ctx, CAMPUS, HERE, HERE, false);
  check(!note().hidden && note().textContent === FAKE, 'the Free Rider line');
  check(!note().classList.contains('task-card-note-done'), 'the Free Rider line is not green');

  nav.draw(ctx, CAMPUS, HERE, HERE, true);
  check(card().hidden && note().hidden, 'while a minigame or the map is open nothing is shown');
  nav.draw(ctx, CAMPUS, HERE, HERE, false);
  check(!note().hidden, 'and it comes back afterwards');

  nav.setNote(null);
  check(note().hidden && note().textContent === '', 'null takes the line away at once');
  nav.setNote('', true);
  check(note().hidden, 'an empty text is no line');

  nav.setNote(DONE, true);
  nav.reset();
  check(card().hidden && note().hidden, 'leaving the lobby hides the card');
  nav.draw(ctx, CAMPUS, HERE, HERE, false);
  check(note().hidden, 'and forgets the line');
}

{
  const { nav, ids } = navigation(false);
  nav.setNote(DONE, true);
  nav.draw(ctx, CAMPUS, HERE, HERE, false);
  check(!ids.get('task-card').hidden, 'a page without the line keeps working');
}

// ---- Part 2: main.js decides who sees which line ----
function game() {
  const handlers = new Map();
  const notes = [];
  const { document } = page();
  const nothing = new Proxy({}, { get: () => () => undefined });
  const Game = {
    minigames: { register() {}, close() {}, showDone() {}, isOpen: () => false },
    forms: nothing, lobby: { ...nothing, setup() {}, setOwnName() {}, show() {}, showClassicTasks() {} },
    duel: { setup() {}, setOwnName() {}, noteLobby() {}, nextStation: () => 2, reset() {}, showState() {}, showProgress() {} },
    screens: { current: () => 'lobby', hideMessage() {}, showMessage() {}, show() {} },
    statistics: nothing, countdown: nothing, classicMeeting: nothing, classicRound: nothing,
    taskNavigation: { setTarget() {}, setTargets() {}, reset() {}, setNote: (text, done) => notes.push([text, done]) },
    world: new Proxy({}, { get: () => () => undefined }),
    net: { connect() {}, ask: () => true, send() {}, on: (type, action) => handlers.set(type, action) },
  };
  const context = vm.createContext({
    Game, window: { Game, addEventListener() {} }, console, document: { ...document, addEventListener() {} },
    performance: { now: () => 0 }, setTimeout: () => 0, clearTimeout() {}, setInterval: () => 0, clearInterval() {},
  });
  vm.runInContext(fs.readFileSync(path.join(client, 'main.js'), 'utf8'), context, { filename: 'main.js' });
  const emit = (type, payload) => handlers.get(type)(payload);
  emit('signed_in', { name: 'Mara', guest: true });
  return { emit, last: () => notes.at(-1) };
}

const lobbyState = (mode, phase) => ({ code: 'ABCD', host: 'Mara', mode, phase, players: [{ name: 'Mara' }, { name: 'Tiago' }] });

{
  const { emit, last } = game();
  emit('lobby_state', lobbyState('classic', 'round'));
  check(last()[0] === null, 'no line before the role is known, even with no task yet');
  emit('classic_role', { role: 'HP', task_stations: [3] });
  check(last()[0] === null, 'a High Performer with a task has no line');
  emit('station_done', { station: 3, task_stations: [8] });
  check(last()[0] === null, 'nor after the first of four');
  emit('station_done', { station: 8, task_stations: [] });
  check(JSON.stringify(last()) === JSON.stringify([DONE, true]), 'after the last: "All your tasks are done.", green');
  emit('lobby_state', lobbyState('classic', 'lobby'));
  check(last()[0] === null, 'back in the lobby the line is gone');
}

{
  const { emit, last } = game();
  emit('lobby_state', lobbyState('classic', 'round'));
  emit('classic_role', { role: 'FR', task_stations: [], other_free_riders: [] });
  check(JSON.stringify(last()) === JSON.stringify([FAKE, false]), 'the Free Rider sees his hint');
  emit('lobby_state', lobbyState('classic', 'lobby'));
  check(last()[0] === null, 'and not after the round');
}

{
  const { emit, last } = game();
  emit('lobby_state', lobbyState('duel', 'round'));
  check(last()[0] === null, 'a Duel has no such line');
}

console.log('Classic card line checks passed: ' + checked + ' assertions.');
