// Dependency-free renderer tests: node game/tests/test_client_room_tasks.js.
// A tiny DOM runs the actual client modules, including click handlers and
// cancellation callbacks. No game-only hooks or browser packages are needed.
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
    this.style = { setProperty: (name, value) => { this.style[name] = value; } };
    this.disabled = false;
    this.events = {};
    this.hidden = false;
    this._text = '';
    this.classList = {
      add: (...values) => { this.className = [...new Set([...this.classes(), ...values])].join(' '); },
      remove: (...values) => { this.className = this.classes().filter((value) => !values.includes(value)).join(' '); },
      contains: (value) => this.classes().includes(value),
      toggle: (value, on) => {
        const enabled = on === undefined ? !this.classes().includes(value) : on;
        if (enabled) this.classList.add(value); else this.classList.remove(value);
      },
    };
  }
  classes() { return this.className.split(/\s+/).filter(Boolean); }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.children.push(child); return child; }
  getContext() { return { scale() {}, beginPath() {}, arc() {}, fill() {}, stroke() {}, clearRect() {} }; }
  replaceChildren(...children) { this._text = ''; this.children = children; }
  set textContent(text) { this._text = String(text); this.children = []; }
  get textContent() { return this._text + this.children.map((child) => child.textContent).join(''); }
  setAttribute(name, value) { this.attributes[name] = String(value); if (name === 'class') this.className = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  addEventListener(type, action) { this.events[type] = action; }
  click() { if (!this.disabled && this.events.click) this.events.click(); }
  querySelectorAll(selector) {
    const matches = (node) => selector.startsWith('.') ? node.classes().includes(selector.slice(1)) : node.tagName === selector;
    return this.children.flatMap((child) => [...(matches(child) ? [child] : []), ...child.querySelectorAll(selector)]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

function environment() {
  const ids = new Map();
  const timers = new Map();
  const handlers = new Map();
  const worldCalls = [];
  let clock = 0;
  let nextTimer = 1;
  let registered;
  const Game = {
    minigames: { register: (kind, game) => { if (kind === 'campus_task') registered = game; }, close() {}, showDone() {} },
    forms: { setup() {}, showSignedIn() {}, showHome() {}, putCodeInJoinField() {} },
    lobby: { setup() {}, setOwnName() {}, show() {} },
    duel: { setup() {}, setOwnName() {}, noteLobby() {}, nextStation: () => 2, reset() {}, showState() {}, showProgress() {}, formatTime: (seconds) => String(seconds) },
    screens: { current: () => 'lobby', hideMessage() {}, showMessage() {} },
    statistics: { setup() {}, setOwnName() {}, showProfile() {}, showLeaderboard() {} },
    countdown: { setup() {}, noteLobby() {}, show() {}, reset() {} },
    roster: { setup() {}, setOwnName() {}, show() {}, reset() {} },
    world: { setOwnName() {}, setPlayers() {}, start() {}, setUseHandler() {}, stop() {},
      setTaskTarget: (...args) => worldCalls.push(['target', ...args]),
      setUsableStations: (...args) => worldCalls.push(['usable', ...args]) },
    net: { connect() {}, ask: () => true, send() {}, on: (type, action) => handlers.set(type, action) },
  };
  const context = vm.createContext({
    Game, window: { Game }, console,
    document: { createElement: (tag) => new Element(tag), createElementNS: (_namespace, tag) => new Element(tag),
      addEventListener() {}, removeEventListener() {}, getElementById: (id) => {
      if (!ids.has(id)) ids.set(id, new Element('div'));
      return ids.get(id);
    } },
    performance: { now: () => clock },
    setTimeout: (action, delay) => { const id = nextTimer++; timers.set(id, { action, when: clock + delay }); return id; },
    clearTimeout: (id) => timers.delete(id),
    clearInterval() {},
  });
  function load(file) { vm.runInContext(fs.readFileSync(path.join(client, file), 'utf8'), context, { filename: file }); }
  function flush() {
    while (timers.size) {
      const [id, timer] = [...timers].sort((a, b) => a[1].when - b[1].when)[0];
      timers.delete(id); clock = timer.when; timer.action();
    }
  }
  load('minigames/room_tasks.js');
  return { Game, context, load, registered, ids, timers, handlers, worldCalls, flush, now: () => clock };
}

function open(content) {
  const env = environment();
  const body = new Element('div');
  let done = 0;
  const stop = env.registered.start(body, content, () => { done += 1; });
  return { ...env, body, stop, done: () => done };
}

function controls(game) { return game.body.querySelectorAll('button'); }
function labelled(game, text) { return controls(game).find((piece) => piece.textContent.includes(text)); }
function finish(game) {
  assert.equal(game.done(), 0, 'completing synchronously would fail the server minimum');
  game.flush();
  assert.equal(game.done(), 1);
  assert.ok(game.now() >= 1100);
  controls(game).forEach((piece) => piece.click());
  game.flush();
  assert.equal(game.done(), 1, 'completion must be reported once');
}

const food = { kind: 'campus_task', puzzle: 'cleanup', theme: 'food', items:
  [['rice', 'Rice grain', 10, 3], ['vegetable', 'Vegetable piece', 3, 1], ['chicken', 'Chicken piece', 3, 1]]
    .flatMap(([kind, label, count, bad]) => Array.from({ length: count }, (_, index) => ({
      id: kind + '-' + index, label, remove: index < bad,
    }))) };
const slide = { kind: 'campus_task', puzzle: 'cleanup', theme: 'slides', items: [
  { id: 0, label: 'Mouldy pasta', remove: true }, { id: 1, label: 'Fresh rice', remove: false },
  { id: 2, label: 'Walking bread', remove: true },
] };
{
  const game = open(slide);
  labelled(game, 'Fresh rice').click();
  assert.match(game.body.querySelector('.campus-feedback').textContent, /actually/);
  assert.equal(game.done(), 0);
  labelled(game, 'Mouldy pasta').click();
  assert.equal(game.done(), 0, 'one wrong or missing piece must not complete');
  labelled(game, 'Walking bread').click();
  finish(game);
}

function foodPiece(game, id) {
  return controls(game).find((piece) => piece.getAttribute('data-food-id') === id);
}
{
  // Payload order must not affect where a piece is placed on the shared tray.
  const game = open({ ...food, items: [...food.items].reverse() });
  assert.equal(game.body.querySelectorAll('.campus-meal-tray').length, 1);
  assert.equal(game.body.querySelector('.campus-plate'), null, 'no individual plates remain');
  assert.equal(game.body.querySelectorAll('.campus-tray-compartment').length, 3);
  assert.equal(controls(game).length, 16);
  for (const [kind, expected] of [['rice', 10], ['vegetable', 3], ['chicken', 3]]) {
    const compartment = game.body.querySelector('.campus-tray-compartment-' + kind);
    assert.equal(compartment.querySelectorAll('button').length, expected);
  }
  controls(game).forEach((piece) => {
    assert.equal(piece.type, 'button', 'native buttons provide Tab/Enter/Space interaction');
    assert.match(piece.getAttribute('aria-label'), /^(Rice grain|Vegetable piece|Chicken piece) [0-9]+$/);
    assert.doesNotMatch(piece.getAttribute('aria-label'), /fresh|mouldy|discard|keep/i);
    assert.equal(piece.getAttribute('title'), null);
    assert.equal(piece.title, undefined);
    assert.equal(piece.querySelectorAll('.campus-tray-food-art').length, 1);
    assert.equal(piece.querySelector('.campus-piece-state'), null, 'food has no visible status badges');
  });
  assert.equal(game.body.querySelector('.campus-tray-rice-bed'), null, 'no decorative extra grains');
  assert.equal(game.body.querySelector('.campus-tray-engraving'), null, 'no engraved food labels');
  assert.equal(game.body.querySelector('.campus-tray-legend'), null, 'no answer legend');
  assert.doesNotMatch(game.body.textContent, /Fresh|Mouldy|fuzz/i, 'no visible answer text');
  const grains = game.body.querySelector('.campus-tray-compartment-rice').querySelectorAll('.campus-tray-food-art');
  assert.equal(grains.length, 10, 'exactly ten visible rice grains');
  grains.forEach((grain) => assert.equal(grain.querySelectorAll('ellipse').length, 1));
  game.body.querySelectorAll('svg').forEach((drawing) => drawing.children.forEach((part) => {
    assert.equal(part.getAttribute('stroke-dasharray'), null, 'no fuzz or cross markers');
  }));
  const fresh = foodPiece(game, 'rice-3');
  fresh.click();
  assert.match(game.body.querySelector('.campus-feedback').textContent, /Leave that piece/);
  assert.equal(fresh.hidden, false, 'fresh food is kept after a mistaken click');
  assert.equal(fresh.disabled, false);
  assert.equal(game.body.querySelector('.campus-lunch-count').textContent, '0 / 5 discarded');
  const firstBad = foodPiece(game, 'rice-0');
  firstBad.click();
  firstBad.click();
  assert.equal(firstBad.hidden, true, 'discarded grains disappear rather than becoming cards');
  assert.equal(firstBad.disabled, true);
  assert.equal(game.body.querySelector('.campus-lunch-count').textContent, '1 / 5 discarded', 'the same piece cannot count twice');
  assert.equal(game.done(), 0, 'one removed grain must not complete the whole tray');
  food.items.filter((item) => item.remove && item.id !== 'rice-0').forEach((item) => foodPiece(game, item.id).click());
  assert.equal(game.body.querySelector('.campus-lunch-count').textContent, '5 / 5 discarded');
  assert.equal(controls(game).filter((piece) => !piece.hidden).length, 11, 'all fresh rice, veg and chicken remain');
  finish(game);
}

{
  const changed = { ...food, items: food.items.map((item) => ['rice-0', 'rice-3'].includes(item.id)
    ? { ...item, remove: !item.remove } : item) };
  const original = open(food);
  const alternate = open(changed);
  const shape = (piece) => piece.querySelector('.campus-tray-food-art').children.map((part) => ({
    tag: part.tagName,
    attributes: Object.fromEntries(Object.entries(part.attributes).filter(([key]) => !['fill', 'stroke'].includes(key))),
  }));
  assert.deepEqual(shape(foodPiece(original, 'rice-0')), shape(foodPiece(alternate, 'rice-0')),
    'discolouration changes colours, not shapes or extra marks');
  assert.notEqual(foodPiece(original, 'rice-0').querySelector('ellipse').getAttribute('fill'),
    foodPiece(alternate, 'rice-0').querySelector('ellipse').getAttribute('fill'));
}

{
  const game = open({ puzzle: 'recipe', drink: 'Panic latte', controls: ['Cup', 'Espresso', 'Milk'], recipe: ['Cup', 'Espresso', 'Espresso', 'Milk'] });
  labelled(game, 'Milk').click();
  for (const step of ['Cup', 'Espresso', 'Espresso', 'Milk']) labelled(game, step).click();
  finish(game);
}

{
  const game = open({ puzzle: 'order', words: ['dog', 'My', 'it', 'ate'], order: ['My', 'dog', 'ate', 'it'], hint: 'My dog ate it' });
  labelled(game, 'dog').click();
  assert.equal(game.body.querySelector('.campus-sentence').children.length, 0);
  for (const word of ['My', 'dog', 'ate', 'it']) labelled(game, word).click();
  assert.equal(game.body.querySelector('.campus-sentence').children.length, 4);
  finish(game);
}

{
  const game = open({ puzzle: 'budget', products: [
    { name: 'Coffee', price: 250 }, { name: 'Noodles', price: 150 }, { name: 'Company car', price: 900 },
  ], target: 400 });
  labelled(game, 'Company car').click();
  assert.match(game.body.querySelector('.campus-feedback').textContent, /Over budget/);
  labelled(game, 'Coffee').click();
  labelled(game, 'Coffee').click();
  assert.equal(labelled(game, 'Coffee').getAttribute('aria-pressed'), 'false');
  labelled(game, 'Coffee').click();
  labelled(game, 'Noodles').click();
  finish(game);
}

{
  const game = open({ puzzle: 'seagull', pages: 5 });
  const bird = game.body.querySelector('.campus-seagull');
  const firstPlace = bird.style.left;
  bird.click();
  assert.notEqual(bird.style.left, firstPlace);
  assert.match(bird.getAttribute('aria-label'), /page 2/);
  for (let i = 1; i < 5; i += 1) bird.click();
  assert.equal(game.body.querySelector('.campus-rescued-pages').children.length, 5);
  finish(game);
}

{
  const game = open(food);
  foodPiece(game, 'rice-3').click(); // a wrong-action feedback timer
  food.items.filter((item) => item.remove).forEach((item) => foodPiece(game, item.id).click()); // a pending completion timer
  game.stop();
  assert.equal(game.timers.size, 0, 'closing must cancel every callback');
  game.flush();
  assert.equal(game.done(), 0, 'closing a solved window must not finish a later opening');
}

for (const content of [null, {}, { puzzle: 'unknown' }, { puzzle: 'seagull', pages: -1 },
  { ...food, items: [food.items[0], food.items[0]] },
  { ...food, items: food.items.map((item, index) => index === 0 ? { ...item, id: 'rice-10' } : item) },
  { ...food, items: food.items.map((item) => item.id.startsWith('chicken-') ? { ...item, remove: false } : item) },
  { puzzle: 'recipe', controls: ['Cup'], recipe: ['Bad'], drink: 'No' },
  { puzzle: 'budget', products: [{ name: 'NaN', price: NaN }], target: 0 },
  { puzzle: 'order', words: ['same', 'same', 'same'], order: ['same'], hint: '' }]) {
  const game = open(content);
  assert.match(game.body.textContent, /could not be loaded/);
  assert.equal(controls(game).length, 0);
  assert.equal(game.done(), 0);
}

for (const mode of ['duel', 'solo']) {
  const env = environment();
  env.load('main.js');
  const emit = (type, payload) => env.handlers.get(type)(payload);
  emit('signed_in', { name: 'Guest1', guest: true });
  emit('lobby_state', { code: 'ABCD', players: [{ name: 'Guest1' }], mode, phase: 'round' });
  assert.deepEqual(env.worldCalls.at(-1), ['target', 2], mode + ' gets its assigned target');
  emit('lobby_state', { code: 'ABCD', players: [{ name: 'Guest1' }], mode, phase: 'lobby' });
  assert.deepEqual(env.worldCalls.at(-1), ['target', null], 'navigation hides outside a round');
}

{
  const env = environment();
  // A resolved map download, delivered immediately so this unit test needs
  // neither the network nor an event loop. The real Duel module formats it.
  const campus = { rooms: [{ id: 'canteen', name: 'Canteen' }], stations: [
    { id: 3, room: 'canteen', name: 'Build the tray' },
    { id: 12, room: 'deck', name: 'Seagull quality control' },
  ] };
  env.context.fetch = () => ({ then: (readResponse) => {
    const map = readResponse({ ok: true, json: () => campus });
    return { then: (remember) => { remember(map); return { catch() {} }; } };
  } });
  env.load('minigames/duel.js');
  env.Game.duel.setup();
  env.Game.duel.noteLobby({ phase: 'round', mode: 'duel' });
  env.Game.duel.showState({ next_station: 12, done: 0, total: 3 });
  assert.equal(env.ids.get('duel-next').textContent, 'Next: Seagull quality control (Main Deck)');
  env.Game.duel.showState({ next_station: 3, done: 1, total: 3 });
  assert.equal(env.ids.get('duel-next').textContent, 'Next: Build the tray (Canteen)');
  env.Game.duel.noteLobby({ phase: 'lobby', mode: 'solo' });
  env.Game.duel.noteLobby({ phase: 'round', mode: 'solo' });
  env.Game.duel.showState({ next_station: 12, done: 0, total: 3 });
  assert.equal(env.Game.duel.nextStation(), 12, 'Solo uses the private server-assigned destination');
  assert.equal(env.ids.get('duel-next').textContent, 'Next: Seagull quality control (Main Deck)');
  assert.equal(env.ids.get('duel-panel').hidden, false, 'Solo must display the existing task HUD');
  env.Game.duel.noteLobby({ phase: 'lobby', mode: 'solo' });
  assert.equal(env.Game.duel.nextStation(), null, 'solo target clears when the round ends');
  assert.equal(env.ids.get('duel-panel').hidden, true);
}

{
  const env = environment();
  const requests = [];
  env.Game.net.ask = (message) => requests.push(message);
  env.load('lobby/lobby.js');
  env.Game.lobby.setup();
  env.Game.lobby.setOwnName('Guest1');
  const soloButton = env.ids.get('lobby-modes').children.find((control) => control.textContent.includes('Solo'));
  // Felix, 2026-11-21: the button reads only "Solo", without a note under it.
  assert.equal(soloButton.textContent, 'Solo');
  soloButton.click();
  assert.equal(requests.at(-1).type, 'choose_mode');
  assert.equal(requests.at(-1).mode, 'solo');
  const state = { code: 'ABCD', host: 'Guest1', players: [{ name: 'Guest1', character: 'consultant' }], phase: 'lobby' };
  env.Game.lobby.show({ ...state, mode: 'solo' });
  assert.equal(env.ids.get('lobby-start').disabled, false, 'one player may start Solo');
  env.Game.lobby.show({ ...state, mode: 'solo', phase: 'countdown' });
  assert.equal(env.ids.get('lobby-start').disabled, true, 'Solo also respects the server countdown');
  assert.equal(soloButton.disabled, true, 'mode changes are disabled during the countdown');
  env.Game.lobby.show({ ...state, mode: 'duel' });
  assert.equal(env.ids.get('lobby-start').disabled, true, 'normal Duel still requires a second player');
  assert.match(env.ids.get('lobby-start-hint').textContent, /Duel needs 1 more player/);
}

{
  const env = environment();
  const screens = [];
  env.Game.screens.current = () => 'home';
  env.Game.screens.show = (screen) => screens.push(screen);
  env.load('lobby/statistics.js');
  env.load('main.js');
  const emit = (type, payload) => env.handlers.get(type)(payload);
  emit('signed_in', { name: 'Guest1', guest: true });
  assert.equal(env.handlers.get('profile'), env.Game.statistics.showProfile);
  assert.equal(env.handlers.get('leaderboard'), env.Game.statistics.showLeaderboard);
  emit('profile', { name: 'Guest1', modes: [{ title: 'Duel', rounds: 2, wins: 1 }], best_duel_seconds: 80 });
  assert.equal(env.ids.get('profile-name').textContent, 'Guest1');
  assert.equal(screens.at(-1), 'profile', 'upstream profile still opens from home');
  env.Game.screens.current = () => 'lobby';
  emit('lobby_state', { code: 'ABCD', players: [{ name: 'Guest1' }], mode: 'solo', phase: 'round' });
  assert.deepEqual(env.worldCalls.at(-1), ['target', 2]);
  const screenCount = screens.length;
  emit('profile', { name: 'Late response', modes: [], best_duel_seconds: null });
  assert.equal(screens.length, screenCount, 'late statistics cannot hide a running task');
  assert.equal(env.ids.get('profile-name').textContent, 'Guest1');
  assert.deepEqual(env.worldCalls.at(-1), ['target', 2], 'statistics leave private navigation intact');
}

console.log('Room task checks passed: six puzzles, wrong actions, one completion, minimum time, cancellation, malformed content, Main Deck labels, Duel and Solo HUD/navigation, Solo lobby gating and upstream statistics integration.');
