// Runs the page's own world.js, lobby.js, meeting.js, round.js and main.js in
// Node, without a browser, for test_classic_round_end_cleanup.py (PR #72):
// what of a Classic round is still shown once the round is over, after the
// player left the lobby, and in a Duel that follows?
//
// The document, the canvases, the clock and the server are small stand-ins.
// The parts of the page that are not about Classic (net.js, forms, screens,
// Duel, countdown, statistics, the map drawing of draw.js) are stand-ins too.
// The minigame window is a stand-in that pauses and frees the world's input
// like js/minigames/frame.js does.
//
// Input (stdin): a JSON list of steps, each a list:
//   ["receive", message]   the server sends this message
//   ["wait", ms]           the clock moves on by `ms`, one frame every 16 ms
//   ["key", code]          the player presses and releases this key
//   ["openMinigame"]       a minigame window opens (the world's input pauses)
//   ["click", id]          the player clicks the element with this id
//   ["clickUseButton"]     the player clicks the button "E Use" on the map
//   ["call", part, name]   calls Game[part][name]() directly; world.start
//                          gets the map canvas and a sender of moves
//   ["look"]               writes down what the page shows now
//   ["lookAtDrawing"]      writes down the characters of the last frame and
//                          whether "Hidden" is shown (output `drawings`)
// Output (stdout): JSON {looks: [...], sent: [...], errors: [...], drawings: [...]}, where
// every look has the fields listed in look() below. `drawings` holds what
// each "lookAtDrawing" saw, for test_classic_hiding_hint.py (M3-1.4).

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const CLIENT = path.join(__dirname, '..', 'client', 'js');
const PAGE_FILES = [
  'classic/fail-button.js',
  'classic/hud-actions.js',
  'world/world.js',
  'lobby/lobby.js',
  'classic/meeting.js',
  'classic/round.js',
  'main.js',
];
const FREE_RIDER_RED = '#C43E3E';
const FRAME_MILLISECONDS = 16;

const sent = [];
const errors = [];
const handlers = {};
let clock = 0;
let nextTimer = 1;
const timers = new Map();

// ---- A canvas context that writes down every text it draws ------------

function newContext() {
  const state = { fillStyle: '#000000', globalAlpha: 1, texts: [] };
  const saved = []; // what save() kept of the transparency, for restore()
  const doesNothing = () => undefined;
  const methods = {
    fillText(text) { state.texts.push({ text: String(text), colour: state.fillStyle }); },
    measureText(text) { return { width: String(text).length * 7 }; },
    getTransform() { return {}; },
    save() { saved.push(state.globalAlpha); },
    restore() { if (saved.length) state.globalAlpha = saved.pop(); },
  };
  return new Proxy(state, {
    get(target, key) {
      if (key in methods) return methods[key];
      if (key in target) return target[key];
      return doesNothing; // fillRect, save, translate, stroke, ...
    },
    set(target, key, value) {
      target[key] = value;
      return true;
    },
  });
}

// ---- The document ------------------------------------------------------

class FakeClassList {
  constructor() { this.names = new Set(); }
  add(name) { this.names.add(name); }
  remove(name) { this.names.delete(name); }
  contains(name) { return this.names.has(name); }
  toggle(name, on) {
    const wanted = on === undefined ? !this.names.has(name) : Boolean(on);
    if (wanted) this.names.add(name); else this.names.delete(name);
    return wanted;
  }
}

class FakeElement {
  constructor(id) {
    this.id = id || '';
    this.hidden = false;
    this.disabled = false;
    this.textContent = '';
    this.value = '';
    this.title = '';
    this.children = [];
    this.parentNode = null;
    this.listeners = {};
    this.dataset = {};
    this.attributes = {};
    this.classList = new FakeClassList();
    this.style = { setProperty() {} };
    this.clientWidth = 800;
    this.clientHeight = 600;
    this.width = 0;
    this.height = 0;
    this.context = null;
  }

  // world.js and lobby.js set `className` and read the classes back.
  set className(text) {
    this.classList = new FakeClassList();
    String(text).split(/\s+/).filter(Boolean).forEach((name) => this.classList.add(name));
  }

  get className() { return [...this.classList.names].join(' '); }

  addEventListener(type, listener) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    return child;
  }

  append(...children) { children.forEach((child) => this.appendChild(child)); }

  replaceChildren(...children) {
    this.children = [];
    this.append(...children);
  }

  remove() {
    if (!this.parentNode) return;
    const siblings = this.parentNode.children;
    siblings.splice(siblings.indexOf(this), 1);
    this.parentNode = null;
  }

  getContext() {
    if (!this.context) this.context = newContext();
    return this.context;
  }

  contains(other) {
    for (let found = other; found; found = found.parentNode) {
      if (found === this) return true;
    }
    return false;
  }

  querySelector() { return new FakeElement(); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return name in this.attributes ? this.attributes[name] : null; }
  focus() { document.activeElement = this; }
  blur() { if (document.activeElement === this) document.activeElement = null; }
}

// The elements that index.html starts hidden (the meeting, the end screen,
// ...), found by their `hidden` attribute, so the stand-ins start as the page does.
const PAGE_HTML = fs.readFileSync(path.join(CLIENT, '..', 'index.html'), 'utf8');
const HIDDEN_AT_START = new Set(
  [...PAGE_HTML.matchAll(/<[^>]*\bid="([^"]+)"[^>]*>/g)]
    .filter((tag) => /\shidden[\s>=]/.test(tag[0]))
    .map((tag) => tag[1])
);

const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    const made = new FakeElement(id);
    made.hidden = HIDDEN_AT_START.has(id);
    elements.set(id, made);
  }
  return elements.get(id);
}

// The map canvas sits in a box; world.js puts its buttons into that box.
element('map-box').appendChild(element('map'));
// The buttons of the end screen are inside it, as in index.html.
element('classic-end-screen').append(element('classic-new-round'), element('classic-back-lobby'));

function everyElementBelow(parent) {
  return parent.children.flatMap((child) => [child, ...everyElementBelow(child)]);
}

const document = {
  hidden: false,
  activeElement: null,
  getElementById: element,
  createElement: (tagName) => {
    const made = new FakeElement();
    made.tagName = String(tagName || '').toUpperCase();
    return made;
  },
  addEventListener() {},
  removeEventListener() {},
};

// ---- The window --------------------------------------------------------

const windowListeners = {};
let nextFrame = null;
const campus = JSON.parse(fs.readFileSync(path.join(CLIENT, 'world', 'campus.json'), 'utf8'));
const doesNothing = new Proxy({}, { get: () => () => undefined });

// A stand-in for js/minigames/frame.js: it pauses the world's input while
// open and frees it on close, as the real window does.
let minigameIsOpen = false;
const minigames = {
  open() { minigameIsOpen = true; page.Game.world.setInputPaused(true); return true; },
  close() {
    if (!minigameIsOpen) return;
    minigameIsOpen = false;
    page.Game.world.setInputPaused(false);
  },
  isOpen: () => minigameIsOpen,
  showDone() {},
};

// The map drawing of draw.js: only the red button is written down.
let emergencyButtonDrawn = null;
// The characters drawn in the last frame: {character, x, alpha}.
let charactersDrawn = [];
// The stations the last frame let pulse (the fifth argument of drawMap).
let pulsingStations = null;

const page = {
  console: {
    warn() {},
    log() {},
    error: (...parts) => errors.push(parts.map(String).join(' ')),
  },
  document: document,
  devicePixelRatio: 1,
  performance: { now: () => clock },
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve(campus) }),
  requestAnimationFrame: (callback) => { nextFrame = callback; return 1; },
  cancelAnimationFrame: () => { nextFrame = null; },
  setTimeout(callback, delay) {
    const id = nextTimer++;
    timers.set(id, { callback, at: clock + Number(delay || 0) });
    return id;
  },
  clearTimeout(id) { timers.delete(id); },
  addEventListener(type, listener) {
    if (!windowListeners[type]) windowListeners[type] = [];
    windowListeners[type].push(listener);
  },
  removeEventListener(type, listener) {
    windowListeners[type] = (windowListeners[type] || []).filter((found) => found !== listener);
  },
};
page.window = page;
page.Game = {
  net: {
    on(type, handler) {
      if (!handlers[type]) handlers[type] = [];
      handlers[type].push(handler);
    },
    send(message) { sent.push(message); return true; },
    ask(message) { sent.push(message); return true; },
    connect() {},
  },
  screens: { show() {}, current: () => 'lobby', showMessage() {}, showLastingMessage() {}, hideMessage() {} },
  forms: doesNothing,
  countdown: doesNothing,
  statistics: doesNothing,
  // A Duel always has station 1 next, so its stations glow as in a real round.
  duel: new Proxy({}, { get: (target, key) => (key === 'nextStation' ? () => 1 : () => undefined) }),
  minigames: minigames,
  world: {
    characters: [],
    drawMap(ctx, map, view, emergencyVisible, pulsing) {
      emergencyButtonDrawn = emergencyVisible === true;
      pulsingStations = Array.isArray(pulsing) ? pulsing.slice() : pulsing;
    },
    drawStationGlow() {},
    // The character "broken" cannot be drawn, as when characters.js fails:
    // the world then draws a circle in its place.
    drawCharacter(ctx, character, x) {
      if (character === 'broken') throw new Error('This character cannot be drawn.');
      charactersDrawn.push({ character: character, x: x, alpha: ctx.globalAlpha });
    },
    chooseLabels: (labels) => ({ shown: labels, hidden: new Set() }),
  },
};
vm.createContext(page);
PAGE_FILES.forEach((file) => {
  const code = fs.readFileSync(path.join(CLIENT, file), 'utf8');
  vm.runInContext(code, page, { filename: file });
});

// Whether the world's input is paused: the last value it was given.
let inputPaused = false;
const setInputPaused = page.Game.world.setInputPaused;
page.Game.world.setInputPaused = (paused) => {
  inputPaused = paused === true;
  setInputPaused(paused);
};

// What the meeting was last told about the own role: it keeps its own copy.
let meetingKnowsFreeRider = false;
const meetingSetOwnFreeRider = page.Game.classicMeeting.setOwnFreeRider;
page.Game.classicMeeting.setOwnFreeRider = (value) => {
  meetingKnowsFreeRider = value === true;
  meetingSetOwnFreeRider(value);
};

// ---- Steps -------------------------------------------------------------

let ownName = null;
let mapTexts = [];

function runFrame() {
  const frame = nextFrame;
  if (!frame) return;
  const context = element('map').getContext();
  context.texts = [];
  charactersDrawn = [];
  try {
    frame(clock);
  } catch (problem) {
    errors.push(String(problem && problem.stack || problem));
  }
  mapTexts = context.texts;
}

function runDueTimers() {
  for (const [id, timer] of [...timers]) {
    if (timer.at > clock) continue;
    timers.delete(id);
    try {
      timer.callback();
    } catch (problem) {
      errors.push(String(problem && problem.stack || problem));
    }
  }
}

function mapButton(className) {
  return element('map-box').children.find((child) => child.classList.contains(className)) || null;
}

function look() {
  const useButton = mapButton('use-button');
  const reportButton = mapButton('report-button');
  const selectedVote = element('classic-vote-players').children.find(
    (button) => button.classList.contains('classic-vote-player-selected')
  );
  // Character icons of the voters inside a vote button: there are none
  // since Felix's fixed-size buttons (2026-11-22).
  const voterIcons = everyElementBelow(element('classic-vote-players'))
    .filter((found) => found.tagName === 'CANVAS' || found.classList.contains('classic-voter-icon')).length;
  const lobbyNames = everyElementBelow(element('lobby-players'));
  const ownOnMap = mapTexts.filter((text) => text.text === ownName);
  return {
    meetingHidden: element('classic-meeting').hidden,
    inputPaused: inputPaused,
    endScreenHidden: element('classic-end-screen').hidden,
    sheetIds: page.Game.world.bloodSheetIds(),
    sheetsDrawn: mapTexts.filter((text) => text.text === 'F').length,
    emergencyButtonDrawn: emergencyButtonDrawn,
    useButtonText: useButton ? useButton.textContent : null,
    useButtonHasFailLook: useButton ? useButton.classList.contains('fail-button') : null,
    reportButtonShown: Boolean(reportButton) && !reportButton.hidden,
    ownNameDrawn: ownOnMap.length > 0,
    ownNameRedOnMap: ownOnMap.some((text) => text.colour === FREE_RIDER_RED),
    ownNameRedInLobby: lobbyNames.some((found) => found.classList.contains('free-rider-name')),
    ownNameRedInRound: element('classic-own-name').classList.contains('free-rider-name'),
    meetingKnowsFreeRider: meetingKnowsFreeRider,
    selectedVoteTarget: selectedVote ? selectedVote.dataset.targetId : null,
    voterIcons: voterIcons,
    // Per vote target: the number in its count field and its label, e.g.
    // {count: "2", label: "Bo — votes: Ana, Cy", title: ...}.
    votes: Object.fromEntries(element('classic-vote-players').children.map((button) => {
      const count = button.children.find((child) => child.classList.contains('classic-vote-count'));
      return [button.dataset.targetId, {
        count: count ? count.textContent : null,
        countIsZero: count ? count.classList.contains('classic-vote-count-zero') : null,
        label: button.getAttribute('aria-label'),
        title: button.title,
      }];
    })),
    // The end screen's "New Round" and the hint below the buttons.
    newRound: {
      hidden: element('classic-new-round').hidden,
      disabled: element('classic-new-round').disabled,
    },
    hostHint: element('classic-host-hint').textContent,
    // The names in the side panel's Players list, in their order.
    listNames: element('lobby-players').children
      .map((row) => row.children.find((child) => child.classList.contains('player-name')).textContent),
    // The rows of the side panel's Players list marked dead, with their markers.
    deadInList: element('lobby-players').children
      .filter((row) => row.classList.contains('player-dead'))
      .map((row) => ({
        name: row.children.find((child) => child.classList.contains('player-name')).textContent,
        markers: row.children.filter((child) => child.classList.contains('marker')).map((child) => child.textContent),
      })),
    // Lennart's Skip section of the meeting window.
    skip: {
      hidden: element('classic-skip-options').hidden,
      status: element('classic-skip-status').textContent,
      text: element('classic-skip-discussion').textContent,
      disabled: element('classic-skip-discussion').disabled,
    },
    focusedId: document.activeElement ? document.activeElement.id : null,
    pulsing: pulsingStations,
    useButtonDisabled: useButton ? useButton.disabled : null,
    voteButtons: element('classic-vote-players').children.map((button) => ({
      target: button.dataset.targetId, text: button.textContent, disabled: button.disabled,
    })),
  };
}

const looks = [];
const drawings = [];

const STEPS = {
  receive(message) {
    if (message.type === 'signed_in') ownName = message.name;
    (handlers[message.type] || []).forEach((handler) => {
      try {
        handler(message);
      } catch (problem) {
        errors.push(String(problem && problem.stack || problem));
      }
    });
  },
  wait(milliseconds) {
    const end = clock + milliseconds;
    while (clock < end) {
      clock = Math.min(end, clock + FRAME_MILLISECONDS);
      runDueTimers();
      runFrame();
    }
  },
  key(code) {
    const event = { code: code, repeat: false, target: null, preventDefault() {} };
    (windowListeners.keydown || []).forEach((listener) => listener(event));
    (windowListeners.keyup || []).forEach((listener) => listener(event));
  },
  openMinigame() {
    minigames.open();
  },
  // A click gives the button the focus first, as in a browser.
  click(id) {
    element(id).focus();
    (element(id).listeners.click || []).forEach((listener) => listener({ preventDefault() {} }));
  },
  // Clicks the button "E Use" on the map (it has no id), as a player would.
  clickUseButton() {
    const button = mapButton('use-button');
    if (!button) throw new Error('The use button is not on the page.');
    button.focus();
    (button.listeners.click || []).forEach((listener) => listener({ preventDefault() {} }));
  },
  // Clicks the vote button for this target ("" is Skip).
  clickVote(targetId) {
    const button = element('classic-vote-players').children.find(
      (candidate) => candidate.dataset.targetId === targetId
    );
    if (!button) throw new Error('Vote target not found: ' + JSON.stringify(targetId));
    button.focus();
    (button.listeners.click || []).forEach((listener) => listener({ preventDefault() {} }));
  },
  // Calls a function of the page directly, for example ["call", "world", "stop"].
  call(part, functionName) {
    const extra = functionName === 'start' ? [element('map'), (dx, dy) => sent.push({ type: 'move', dx, dy })] : [];
    page.Game[part][functionName](...extra);
  },
  look() {
    looks.push(look());
  },
  // The characters the last frame drew, with their transparency, and
  // whether the text "Hidden" is shown (M3-1.4).
  lookAtDrawing() {
    drawings.push({
      charactersDrawn: charactersDrawn,
      hiddenHintShown: everyElementBelow(element('classic-progress'))
        .some((found) => found.id === 'classic-hidden-hint' && !found.hidden),
    });
  },
};

// The map file arrives through a promise: let it land before the steps run
// on, so every frame has the campus.
function settle() {
  return new Promise((resolve) => setImmediate(resolve));
}

async function main() {
  const steps = JSON.parse(fs.readFileSync(0, 'utf8'));
  for (const [name, ...values] of steps) {
    STEPS[name](...values);
    await settle();
  }
  process.stdout.write(JSON.stringify({ looks: looks, sent: sent, errors: errors, drawings: drawings }));
}

main();
