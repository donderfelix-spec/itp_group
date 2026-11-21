// The one player list in the side panel (brief B, part 3): in a Duel or
// Solo round each row shows "n/3" and a bar; in the lobby and in Classic it
// is main's list. Runs the real lobby/lobby.js, minigames/duel.js,
// lobby/countdown.js and main.js with a small stand-in for the page.
// Run with: node game/tests/test_client_player_progress.js
// (pytest does it in tests/test_node_harnesses_area4.py).
//
// It takes over what tests/test_client_roster.js checked that still applies
// to a list of players: names only as text, nothing private shown, broken
// messages, a player who left, eight players, and main.js's handling of the
// countdown and of leaving.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const client = path.join(__dirname, '..', 'client', 'js');

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
    fetch: () => new Promise(() => {}), // the station names are not needed here
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

function lobbyState(names, mode = 'duel', phase = 'round') {
  return { code: 'ABCD', host: names[0], mode, phase, players: names.map((name) => ({ name, character: 'surfer' })) };
}
function progress(done, total = 3) {
  return { players: Object.entries(done).map(([name, count]) => ({ name, done: count })), total, seconds_left: 170 };
}
function inRound(env, names, mode = 'duel') {
  env.emit('signed_in', { name: names[0], guest: true });
  env.emit('lobby_state', lobbyState(names, mode));
}

let checked = 0;
function check(condition, message) {
  assert.ok(condition, message);
  checked += 1;
}

// The lobby: main's list, without progress, two columns.
{
  const env = environment();
  env.emit('signed_in', { name: 'Mara', guest: true });
  env.emit('lobby_state', lobbyState(['Mara', 'Tiago'], 'duel', 'lobby'));
  check(env.rows().length === 2 && env.rows().every((row) => env.progressOf(row) === null), 'no progress in the lobby');
  check(!env.list.classList.contains('players-progress'), 'the lobby list keeps its columns');
  check(env.rows()[0].children.map((child) => child.className).join('|') === 'icon|player-name|marker marker-host|marker',
    'a lobby row is icon, name and markers, as on main');
  // Progress that comes too early or late shows nothing in the lobby.
  env.emit('duel_progress', progress({ Mara: 1, Tiago: 2 }));
  check(env.rows().every((row) => env.progressOf(row) === null), 'a late duel_progress changes nothing in the lobby');
}

// A Duel round: "n/3" and a bar per player, one column; 0/3, 3/3, a count above the total.
{
  const env = environment();
  inRound(env, ['Mara', 'Tiago', 'Ines']);
  env.emit('duel_progress', progress({ Mara: 0, Tiago: 3, Ines: 2 }));
  check(env.list.classList.contains('players-progress'), 'one column in the round');
  check(JSON.stringify(env.rows().map(env.progressOf)) === JSON.stringify([['0/3', '0%'], ['3/3', '100%'], ['2/3', '67%']]),
    'every row shows its progress: ' + JSON.stringify(env.rows().map(env.progressOf)));
  check(env.rows()[0].querySelector('.player-bar').getAttribute('aria-hidden') === 'true', 'the bar is not read out twice');
  env.emit('duel_progress', progress({ Mara: 7, Tiago: 3, Ines: 2 }));
  check(env.progressOf(env.rows()[0])[0] === '3/3', 'a count above the total is shown as the total');
  check(env.ids.get('duel-players') === undefined, 'duel.js no longer fills a list of its own');
  // A lobby_state during the round (somebody left) keeps the progress of the others.
  env.emit('lobby_state', lobbyState(['Mara', 'Ines']));
  check(env.rows().length === 2 && env.progressOf(env.rows()[1])[0] === '2/3', 'the player who left is gone, the others keep theirs');
  // Progress of a player who is no longer in the lobby is not shown.
  env.emit('duel_progress', progress({ Mara: 1, Tiago: 3, Ines: 2 }));
  check(!env.rows().some((row) => row.textContent.includes('Tiago')), 'nobody who left comes back from duel_progress');
  // The round ends: main's list again.
  env.emit('lobby_state', lobbyState(['Mara', 'Ines'], 'duel', 'lobby'));
  check(env.rows().every((row) => env.progressOf(row) === null) && !env.list.classList.contains('players-progress'),
    'after the round the list is main\'s again');
  // The next round starts without the old progress.
  env.emit('lobby_state', lobbyState(['Mara', 'Ines']));
  check(env.rows().every((row) => env.progressOf(row) === null), 'a new round shows no progress of the last one');
}

// Solo and eight players.
{
  const env = environment();
  const eight = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8'];
  inRound(env, eight);
  env.emit('duel_progress', progress(Object.fromEntries(eight.map((name, index) => [name, index % 4]))));
  check(env.rows().length === 8 && env.rows().every((row, index) => env.progressOf(row)[0] === (index % 4 === 3 ? 3 : index % 4) + '/3'),
    'eight players, each with their own count');
  const solo = environment();
  inRound(solo, ['Mara'], 'solo');
  solo.emit('duel_progress', progress({ Mara: 1 }));
  check(JSON.stringify(solo.progressOf(solo.rows()[0])) === JSON.stringify(['1/3', '33%']), 'Solo shows the progress too');
}

// Classic: main's list, whatever comes.
{
  const env = environment();
  inRound(env, ['Mara', 'Tiago', 'Ines', 'Rui'], 'classic');
  env.Game.lobby.showProgress({ players: [{ name: 'Mara', done: 1 }], total: 3 });
  env.emit('duel_progress', progress({ Mara: 1 }));
  check(env.rows().length === 4 && env.rows().every((row) => env.progressOf(row) === null), 'Classic shows no Duel progress');
}

// Broken messages show no progress and break nothing.
{
  const env = environment();
  inRound(env, ['Mara', 'Tiago']);
  for (const given of [null, undefined, 3, 'x', {}, { players: 'x', total: 3 }, { players: [], total: 0 },
    { players: [{ name: 'Mara', done: 1 }], total: -3 }, { players: [{ name: 'Mara', done: 1 }], total: 1.5 }]) {
    env.Game.lobby.showProgress(given);
    check(env.rows().length === 2 && env.rows().every((row) => env.progressOf(row) === null), 'nothing for ' + JSON.stringify(given));
  }
  env.Game.lobby.showProgress({ players: [null, { name: 12, done: 1 }, { name: 'Mara', done: -1 }, { name: 'Mara', done: 1.5 },
    { name: 'Tiago', done: '2' }, { name: 'Tiago', done: 2 }], total: 3 });
  check(env.progressOf(env.rows()[0]) === null && env.progressOf(env.rows()[1])[0] === '2/3', 'only readable entries count');
  // duel.js refuses an unreadable duel_progress, and the list keeps the last readable one.
  env.emit('duel_progress', progress({ Mara: 0, Tiago: 2 }));
  env.emit('duel_progress', { players: [{ name: 'Mara' }], total: 3, seconds_left: 10 });
  check(env.progressOf(env.rows()[1])[0] === '2/3', 'an unreadable duel_progress changes nothing');
}

// Names are text, and nothing private is shown.
{
  const env = environment();
  const attacker = '<img src=x onerror=alert(1)>';
  env.emit('signed_in', { name: 'Other', guest: true });
  env.emit('lobby_state', { code: 'ABCD', host: 'Other', mode: 'duel', phase: 'round', players: [
    { name: attacker, character: 'surfer', role: 'PRIVATE FREE RIDER', task: 'SECRET TASK', x: 900, y: 42 },
    { name: 'Other', character: 'founder' }] });
  env.emit('duel_progress', progress({ [attacker]: 1, Other: 0 }));
  const row = env.rows()[0];
  check(row.querySelector('.player-name').textContent === attacker && row.querySelectorAll('img').length === 0, 'a name is only text');
  check(!env.list.textContent.includes('PRIVATE') && !env.list.textContent.includes('SECRET'), 'no role and no task in the list');
}

// duel.js gives its progress only during its round, as a copy.
{
  const env = environment();
  check(env.Game.duel.progress() === null, 'no progress before a round');
  inRound(env, ['Mara']);
  env.emit('duel_progress', progress({ Mara: 2 }));
  const given = env.Game.duel.progress();
  check(JSON.stringify(given) === JSON.stringify({ players: [{ name: 'Mara', done: 2 }], total: 3 }), 'the progress of the round');
  given.players[0].done = 99;
  check(env.Game.duel.progress().players[0].done === 2, 'a copy: the list cannot change the Duel');
  env.emit('left_lobby');
  check(env.Game.duel.progress() === null, 'nothing after leaving');
}

// The panel heading and the ranking say "Solo" in Solo and "Duel" in a Duel.
for (const [mode, name] of [['solo', 'Solo'], ['duel', 'Duel']]) {
  const env = environment();
  env.Game.duel.setup();
  inRound(env, ['Mara', 'Tiago'], mode);
  env.emit('duel_progress', progress({ Mara: 0, Tiago: 0 }));
  check(env.ids.get('duel-heading').textContent === name, mode + ': the panel heading is ' + name);
  env.emit('duel_result', { ranking: [{ place: 1, name: 'Mara', seconds: 80.2, done: 3 }], time_up: false });
  const title = env.ids.get('duel-ranking').querySelector('.duel-title');
  check(title && title.textContent === name + ' ranking', mode + ': the ranking is headed "' + name + ' ranking"');
  // After the round the ranking keeps its name; the next round names itself again.
  env.emit('lobby_state', lobbyState(['Mara', 'Tiago'], mode, 'lobby'));
  check(env.ids.get('duel-ranking').querySelector('.duel-title').textContent === name + ' ranking', mode + ': still named after the round');
}
{
  const env = environment();
  env.Game.duel.setup();
  inRound(env, ['Mara'], 'solo');
  env.emit('lobby_state', lobbyState(['Mara', 'Tiago'], 'duel', 'lobby'));
  env.emit('lobby_state', lobbyState(['Mara', 'Tiago'], 'duel'));
  env.emit('duel_progress', progress({ Mara: 0, Tiago: 0 }));
  check(env.ids.get('duel-heading').textContent === 'Duel', 'a Duel after a Solo round is called Duel again');
}

// Modes that do not fit the number of players (brief D): greyed, with a "?".
{
  const env = environment();
  const grid = env.ids.get('lobby-modes');
  const button = (id) => grid.children.find((child) => child.className.split(' ').includes('mode') && child.getAttribute('data-mode') === id);
  const why = (id) => grid.children.find((child) => child.className === 'mode-why' && child.getAttribute('data-mode') === id);
  const text = (id) => grid.children.find((child) => child.getAttribute('role') === 'tooltip' && child.getAttribute('data-mode') === id);
  env.emit('signed_in', { name: 'Mara', guest: true });
  env.emit('lobby_state', lobbyState(['Mara'], 'duel', 'lobby'));
  check(button('duel').disabled && button('classic').disabled && !button('solo').disabled, 'alone: Duel and Classic greyed, Solo free');
  check(button('duel').classList.contains('mode-own') && button('duel').classList.contains('mode-unfit'), 'the chosen Duel stays marked, greyed');
  check(!why('duel').hidden && !why('classic').hidden && why('solo').hidden, 'a "?" only at the greyed modes');
  check(text('duel').textContent === 'Duel needs at least 2 players.' && text('classic').textContent === 'Classic needs at least 4 players.'
    && text('solo').textContent === 'Solo is only for one player alone.', 'the reasons, with the minimums of the page');
  check(why('duel').getAttribute('aria-describedby') === text('duel').id && text('duel').getAttribute('role') === 'tooltip', 'tooltip and aria-describedby');
  check([text('duel'), text('classic'), text('solo')].every((entry) => entry.hidden), 'no text before it is asked for');
  why('duel').events.mouseenter();
  check(!text('duel').hidden, 'hover shows the text');
  why('duel').events.mouseleave();
  check(text('duel').hidden, 'leaving hides it');
  why('classic').events.focus();
  check(!text('classic').hidden, 'focus shows the text');
  why('duel').events.click();
  check(!text('duel').hidden && text('classic').hidden, 'a click opens it, and only one text is shown');
  why('duel').events.click();
  check(text('duel').hidden, 'a second click closes it');
  why('duel').events.pointerdown();
  why('duel').events.focus();
  why('duel').events.click();
  check(!text('duel').hidden, 'a tap (press, focus, click) opens it');
  grid.events.keydown({ key: 'Escape', preventDefault() {} });
  check(text('duel').hidden, 'Esc closes it, also while the "?" keeps the focus');
  why('duel').events.mouseenter();
  check(!text('duel').hidden, 'and it opens again on the next hover');
  // With a mouse: the hover shows it, and the click pins it (it does not close it).
  why('duel').events.pointerdown();
  why('duel').events.focus();
  why('duel').events.click();
  why('duel').events.mouseleave();
  check(!text('duel').hidden, 'hover, then click: the text stays open after the pointer leaves');
  why('duel').events.mouseenter();
  why('duel').events.pointerdown();
  why('duel').events.click();
  check(text('duel').hidden, 'a second click closes the pinned text');
  // Enter or Space on the focused "?" (a click without a press) toggles too.
  why('duel').events.focus();
  why('duel').events.click();
  check(text('duel').hidden, 'Enter on a "?" whose text the focus shows closes it');
  why('duel').events.click();
  check(!text('duel').hidden, 'and Enter again opens it');
  // A guest joins while the focus is on the "?" of Duel: the "?" goes, the
  // focus moves to the Duel button, which can be used now.
  let focused = null;
  button('duel').focus = () => { focused = 'duel'; };
  env.document.activeElement = why('duel');
  env.emit('lobby_state', lobbyState(['Mara', 'Tiago'], 'duel', 'lobby'));
  check(focused === 'duel', 'the focus moves from the hidden "?" to its mode button');
  env.document.activeElement = null;
  check(!button('duel').disabled && !button('classic').disabled && button('solo').disabled, 'two: Solo greyed, Duel and Classic free');
  check(why('duel').hidden && text('duel').hidden && !why('solo').hidden, 'a mode that fits again loses its "?" and text');
  env.emit('lobby_state', lobbyState(['Mara', 'Tiago', 'Ines'], 'classic', 'lobby'));
  check(!button('classic').disabled, 'Classic with three players stays selectable, as on main');
  env.emit('lobby_state', { ...lobbyState(['Mara'], 'solo', 'lobby'), host: 'Tiago' });
  check(grid.hidden, 'a player who is not host sees only the text of the mode');
}

// main.js around the round (from test_client_roster.js): the countdown, the
// movement reset at the start of a round, and leaving.
for (const mode of ['duel', 'solo']) {
  const env = environment();
  env.Game.countdown.setup();
  env.emit('signed_in', { name: 'Guest1', guest: true });
  const state = lobbyState(['Guest1', 'Other'], mode);
  env.emit('lobby_state', { ...state, phase: 'countdown' });
  env.emit('countdown', { seconds: 5 });
  check(env.ids.get('countdown').hidden === false && env.ids.get('countdown-number').textContent === '5', mode + ': the countdown shows 5');
  check(env.rows().every((row) => env.progressOf(row) === null), mode + ': no progress during the countdown');
  env.advance(6000);
  check(env.ids.get('countdown-number').textContent === '1', mode + ': the local timer never starts the round itself');
  check(env.roundStarts() === 0, mode + ': no round before the server says so');
  env.emit('lobby_state', state);
  check(env.ids.get('countdown').hidden === true && env.intervalCount() === 0, mode + ': the round phase ends the countdown');
  check(env.roundStarts() === 1, mode + ': the round phase resets the movement once');
  env.emit('lobby_state', state);
  check(env.roundStarts() === 1, mode + ': an ordinary lobby_state does not reset the movement again');
  env.emit('left_lobby');
  check(env.ids.get('countdown').hidden === true && env.intervalCount() === 0, mode + ': leaving resets the countdown');
}

console.log('Player list checks passed: ' + checked + ' assertions.');
