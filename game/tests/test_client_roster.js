// Run with node game/tests/test_client_roster.js. These checks execute the
// actual roster and main message handlers with a small dependency-free DOM.
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
    this.hidden = false;
    this.attributes = {};
    this._text = '';
    this.classList = {
      add: (...values) => { this.className = [...new Set([...this.classes(), ...values])].join(' '); },
      contains: (value) => this.classes().includes(value),
    };
  }
  classes() { return this.className.split(/\s+/).filter(Boolean); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this._text = ''; this.children = children; }
  set textContent(text) { this._text = String(text); this.children = []; }
  get textContent() { return this._text + this.children.map((child) => child.textContent).join(''); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  getContext() { return { scale() {} }; }
  querySelectorAll(selector) {
    const matches = (node) => selector.startsWith('.') ? node.classes().includes(selector.slice(1)) : node.tagName === selector;
    return this.children.flatMap((child) => [...(matches(child) ? [child] : []), ...child.querySelectorAll(selector)]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

function environment({ drawing = 'works', missingMarkup = false } = {}) {
  const ids = new Map();
  const handlers = new Map();
  const portraits = [];
  const targets = [];
  const intervals = new Map();
  let now = 0;
  let nextInterval = 1;
  let roundStarts = 0;
  let nextStation = null;
  const Game = {
    minigames: { close() {}, showDone() {}, isOpen: () => false },
    forms: { setup() {}, showSignedIn() {}, showHome() {}, showStart() {}, stopWaiting() {}, putCodeInJoinField() {}, showError: () => false },
    lobby: { setup() {}, setOwnName() {}, show() {} },
    duel: { setup() {}, setOwnName() {}, noteLobby() {}, reset() {}, nextStation: () => nextStation,
      showState: (state) => { nextStation = state.next_station; }, showProgress() {}, showResult() {} },
    statistics: { setup() {}, setOwnName() {}, showProfile() {}, showLeaderboard() {} },
    countdown: { setup() {}, show() {}, noteLobby() {}, reset() {} },
    // Classic's own modules (from main): every call does nothing here.
    classicMeeting: new Proxy({}, { get: () => () => undefined }),
    classicRound: new Proxy({}, { get: () => () => undefined }),
    screens: { current: () => 'lobby', hideMessage() {}, showMessage() {}, showLastingMessage() {} },
    net: { connect() {}, on: (type, action) => handlers.set(type, action), send() {}, ask() {} },
    world: { setOwnName() {}, setPlayers() {}, start() {}, stop() {}, setUseHandler() {}, setPositions() {}, setUsableStations() {},
      startOfRound: () => { roundStarts += 1; } },
    // The task card and arrow moved to minigames/task_navigation.js.
    taskNavigation: { setTarget: (station) => targets.push(station) },
  };
  if (drawing !== 'missing') Game.world.drawCharacter = (ctx, character, x, y, size) => {
    if (drawing === 'throws') throw new Error('drawing failed');
    portraits.push({ character, x, y, size });
  };
  const context = vm.createContext({ Game, window: { Game, devicePixelRatio: 2 }, console,
    performance: { now: () => now },
    setInterval: (action) => { const id = nextInterval++; intervals.set(id, action); return id; },
    clearInterval: (id) => intervals.delete(id),
    document: {
      createElement: (tag) => {
        const made = new Element(tag);
        if (drawing === 'no-canvas' && tag === 'canvas') made.getContext = () => null;
        return made;
      },
      getElementById: (id) => {
        if (missingMarkup && id.startsWith('player-roster')) return null;
        if (!ids.has(id)) ids.set(id, new Element('div'));
        return ids.get(id);
      },
    },
  });
  const load = (file) => vm.runInContext(fs.readFileSync(path.join(client, file), 'utf8'), context, { filename: file });
  load('lobby/roster.js');
  Game.roster.setup();
  const rows = () => ids.get('player-roster-list').children;
  const status = (row) => row.querySelector('.player-roster-status').textContent;
  return { Game, context, load, ids, handlers, portraits, targets, rows, status,
    roundStarts: () => roundStarts, intervalCount: () => intervals.size,
    advance: (milliseconds) => { now += milliseconds; [...intervals.values()].forEach((action) => action()); },
    emit: (type, payload) => handlers.get(type)(payload) };
}

function player(name, alive, character = 'consultant') {
  return { name, alive, character };
}
function round(players) { return { code: 'ABCD', mode: 'duel', phase: 'round', players }; }

for (const size of [1, 2, 8]) {
  const env = environment();
  env.Game.roster.setOwnName('Player1');
  env.Game.roster.show(round(Array.from({ length: size }, (_, index) => player('Player' + (index + 1), true))));
  assert.equal(env.rows().length, size);
  assert.equal(env.ids.get('player-roster').hidden, false);
  assert.equal(env.ids.get('player-roster-count').textContent, String(size));
  assert.equal(env.rows()[0].querySelector('.player-roster-you').textContent, 'You');
  assert.equal(env.rows().filter((row) => row.querySelector('.player-roster-you')).length, 1);
  env.rows().forEach((row) => {
    assert.equal(env.status(row), 'In game');
    assert.equal(row.querySelector('.player-roster-portrait').getAttribute('aria-hidden'), 'true');
    assert.equal(row.querySelectorAll('canvas').length, 1);
  });
  assert.equal(env.portraits.length, size);
}

{
  const env = environment();
  const values = [false, true, undefined, null, 0, 'false', {}, []];
  env.Game.roster.show(round(values.map((alive, index) => player('Player' + index, alive))));
  assert.deepEqual(env.rows().map(env.status), ['Dead', ...Array(7).fill('In game')]);
  assert.equal(env.rows()[0].classList.contains('player-roster-dead'), true);
  assert.equal(env.rows()[0].querySelector('.player-roster-cross').textContent, '×');
  assert.equal(env.rows().slice(1).some((row) => row.querySelector('.player-roster-cross')), false);
  // New authoritative membership replaces old status; missing alive is never
  // inferred to be dead, including at a new round.
  env.Game.roster.show(round([player('Player0', undefined)]));
  assert.equal(env.status(env.rows()[0]), 'In game');
  assert.equal(env.rows()[0].querySelector('.player-roster-cross'), null);
}

{
  const env = environment();
  const attacker = '<img src=x onerror=alert(1)>';
  env.Game.roster.show(round([{ name: attacker, character: 'surfer', alive: false,
    role: 'PRIVATE FREE RIDER', task: 'SECRET TASK', x: 900, y: 42 }, player('Other', true)]));
  assert.equal(env.rows()[0].querySelector('.player-roster-name').textContent, attacker);
  assert.equal(env.rows()[0].querySelectorAll('img').length, 0);
  assert.equal(env.rows()[0].textContent.includes('PRIVATE'), false);
  assert.equal(env.rows()[0].textContent.includes('SECRET'), false);
  env.Game.roster.setOwnName('Other');
  assert.equal(env.rows()[1].querySelector('.player-roster-you').textContent, 'You');
  env.Game.roster.show(round([player('Other', true, 'founder')]));
  assert.equal(env.rows().length, 1, 'leaving removes the row rather than marking it dead');
  assert.equal(env.status(env.rows()[0]), 'In game');
  assert.equal(env.portraits.at(-1).character, 'founder', 'server character changes redraw the portrait');
}

for (const drawing of ['missing', 'throws', 'no-canvas']) {
  const env = environment({ drawing });
  env.Game.roster.show(round([player('Guest1', false)]));
  assert.equal(env.rows()[0].querySelectorAll('.player-roster-fallback').length, 1);
  assert.equal(env.status(env.rows()[0]), 'Dead');
}

{
  const env = environment();
  env.Game.roster.show(round([null, { name: 12 }, { name: '' }, player('First', true), player('First', false)]));
  assert.equal(env.rows().length, 1);
  assert.equal(env.status(env.rows()[0]), 'In game');
  env.Game.roster.show(round(Array.from({ length: 20 }, (_, index) => player('Player' + index, true))));
  assert.equal(env.rows().length, 8);
  for (const state of [null, {}, { phase: 'round', players: null }, { phase: 'lobby', players: [player('One', false)] }, round([])]) {
    env.Game.roster.show(state);
    assert.equal(env.ids.get('player-roster').hidden, true);
    assert.equal(env.rows().length, 0);
  }
}

{
  const env = environment({ missingMarkup: true });
  assert.doesNotThrow(() => {
    env.Game.roster.setOwnName('Guest1');
    env.Game.roster.show(round([player('Guest1', false)]));
    env.Game.roster.reset();
  });
}

// Main lifecycle, with the real roster rather than a stub: unrelated
// position/task/progress messages must never manufacture or erase a death.
for (const exit of ['left_lobby', 'signed_out', 'close', 'end_round']) {
  const env = environment();
  env.load('main.js');
  env.emit('signed_in', { name: 'Guest1', guest: true });
  const state = round([player('Guest1', true), player('Other', false)]);
  env.emit('lobby_state', state);
  assert.equal(env.rows().length, 2);
  assert.equal(env.rows()[0].querySelector('.player-roster-you').textContent, 'You');
  env.emit('duel_state', { next_station: 9, done: 0, total: 3 });
  env.emit('station_done', { station: 9 });
  env.emit('duel_progress', { players: [{ name: 'Other', done: 3 }], seconds_left: 12, total: 3 });
  env.emit('positions', { players: [] });
  assert.equal(env.status(env.rows()[0]), 'In game');
  assert.equal(env.status(env.rows()[1]), 'Dead', 'unrelated messages cannot reset explicit status');
  assert.equal(env.targets.at(-1), 9, 'the roster does not change private navigation');
  if (exit === 'end_round') env.emit('lobby_state', { ...state, phase: 'lobby' });
  else env.emit(exit);
  assert.equal(env.ids.get('player-roster').hidden, true, exit + ' hides the roster');
  assert.equal(env.rows().length, 0, exit + ' forgets all previous members/status');
  env.emit('signed_in', { name: 'NewGuest', guest: true });
  env.emit('lobby_state', round([player('NewGuest', undefined)]));
  assert.equal(env.status(env.rows()[0]), 'In game');
  assert.equal(env.rows()[0].querySelector('.player-roster-you').textContent, 'You');
}

for (const mode of ['duel', 'solo']) {
  const env = environment();
  env.load('lobby/countdown.js');
  env.load('main.js');
  env.emit('signed_in', { name: 'Guest1', guest: true });
  const state = { ...round([player('Guest1', true), player('Other', false)]), mode };
  env.emit('lobby_state', { ...state, phase: 'countdown' });
  env.emit('countdown', { seconds: 5 });
  assert.equal(env.ids.get('countdown').hidden, false);
  assert.equal(env.ids.get('countdown-number').textContent, '5');
  assert.equal(env.ids.get('player-roster').hidden, true, 'roster stays hidden until server round phase');
  assert.equal(env.targets.at(-1), null, 'no private task marker during countdown');
  env.advance(6000);
  assert.equal(env.ids.get('countdown-number').textContent, '1', 'local timer never starts the round itself');
  assert.equal(env.roundStarts(), 0);
  assert.equal(env.ids.get('player-roster').hidden, true);
  env.emit('lobby_state', state);
  assert.equal(env.ids.get('countdown').hidden, true);
  assert.equal(env.intervalCount(), 0);
  assert.equal(env.roundStarts(), 1, 'server round phase resets movement/pose once');
  assert.equal(env.rows().length, 2);
  assert.equal(env.status(env.rows()[1]), 'Dead', 'explicit public status survives the phase handover');
  env.emit('duel_state', { next_station: 9, done: 0, total: 3 });
  assert.equal(env.targets.at(-1), 9);
  env.emit('lobby_state', state);
  assert.equal(env.roundStarts(), 1, 'ordinary membership messages must not reset movement again');
  env.emit('lobby_state', { ...state, phase: 'countdown' });
  env.emit('countdown', { seconds: 5 });
  assert.equal(env.ids.get('player-roster').hidden, true);
  assert.equal(env.targets.at(-1), null);
  env.emit('left_lobby');
  assert.equal(env.ids.get('countdown').hidden, true, 'leaving resets both countdown and roster');
  assert.equal(env.ids.get('player-roster').hidden, true);
  assert.equal(env.intervalCount(), 0);
}

{
  // The live hidden attribute tested above also controls the narrow layout:
  // retain upstream phone sizing until an in-round roster needs more room.
  const stylesheet = fs.readFileSync(path.join(client, '..', 'css', 'style.css'), 'utf8');
  const narrow = stylesheet.slice(stylesheet.lastIndexOf('\n@media (max-width: 800px) {'));
  assert.match(narrow, /\.screen-lobby\s*\{[^}]*grid-template-rows:\s*55vh auto;/);
  assert.match(narrow, /\.screen-lobby:has\(\.player-roster:not\(\[hidden\]\)\)\s*\{[^}]*grid-template-rows:\s*minmax\(340px,\s*55vh\) auto;/);
}

console.log('Player roster checks passed: 1/2/8 players, portraits/fallbacks, strict death status, text-only names, membership updates, privacy, malformed payloads, missing markup, main lifecycle, countdown handover/movement reset, private navigator independence and conditional narrow layout.');
