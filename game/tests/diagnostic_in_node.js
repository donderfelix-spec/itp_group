// Runs the page's own js/world/diagnostic.js in Node, without a browser, for
// test_walking_diagnostic.py (M2-1.15).
//
// The window, the document, Game.net and Game.world are small stand-ins that
// record what the diagnostic does with them, so a test can check that it
// does nothing at all without `?debug`, and play frames, messages and clicks
// with it. The diagnostic is the real code.
//
// Input (stdin): JSON {search, clipboard, calls, steps}
//   search      the `location.search` of the page, for example "" or "?debug"
//   clipboard   "works" (default), "refuses" (writeText fails) or "missing"
//   calls       [[name, ...arguments]]: pure functions of Game.diagnostic to call.
//               The script also checks that a call left its arguments as they
//               were (output `changedArguments`: the names of calls that did not).
//   steps       a list of steps, each a list:
//     ["frame", time]          the browser draws a frame at this time
//     ["clock", time]          performance.now() returns this from now on
//     ["direction", dx, dy]    Game.world.walkingDirection() returns this; as in world.js, its
//                              `since` is the clock when it changed from zero, null while zero
//     ["position", x, y]       Game.world.ownDrawnPosition() returns this (x null: no position)
//     ["receive", message]     Game.net hands this message to the handlers
//     ["tick", delay]          the interval timers with this delay run once
//     ["timeouts"]             the waiting timeouts run
//     ["connected", yes]       whether Game.net.send() can send
//     ["long_walk", seconds]   the player walks this long: frames, `positions` messages and
//                              answered probes with a little jitter, enough to fill the buffers
//     ["time_refresh", runs]   runs the panel's refresh timer this often and writes down how
//                              long each run really took (output `record.refreshMs`)
//     ["hide"]                 the tab is hidden
//     ["click", text]          the player clicks the panel's button with this text
//     ["reset"]                Game.diagnostic.reset()
// Output (stdout): JSON with what the diagnostic registered, sent and made,
// the results of the calls, and, when active, its numbers and report.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const DIAGNOSTIC = path.join(__dirname, '..', 'client', 'js', 'world', 'diagnostic.js');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));

const record = {
  handlers: [], // message types given to Game.net.on
  sent: [], // messages given to Game.net.send
  created: [], // tag names given to document.createElement
  frameRequests: 0,
  intervals: [], // delays of setInterval
  timeouts: 0,
  listeners: [], // "window:type" or "document:type"
  elementListeners: [], // "TAG:type" for every listener put on an element the diagnostic made
  refreshMs: [], // how long each refresh of ["time_refresh"] took, in real ms
  copied: [], // texts given to navigator.clipboard.writeText
  execCommands: [],
  focusAfterClicks: [], // was the clicked button still focused afterwards?
};

let clock = 0;
let direction = { dx: 0, dy: 0, since: null };
let drawn = null;
let connected = true;
const netHandlers = new Map();
let frameCallbacks = [];
const intervalTimers = [];
let timeoutTimers = [];

class FakeElement {
  constructor(tagName) {
    this.tagName = tagName.toUpperCase();
    this.style = {};
    this.children = [];
    this.listeners = {};
    this.textContent = '';
    this.value = '';
    this.parent = null;
  }

  appendChild(child) {
    child.parent = this;
    this.children.push(child);
    return child;
  }

  remove() {
    if (this.parent) this.parent.children = this.parent.children.filter((child) => child !== this);
    if (document.activeElement === this) document.activeElement = document.body;
  }

  addEventListener(type, listener) {
    record.elementListeners.push(this.tagName + ':' + type);
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  fire(type) {
    (this.listeners[type] || []).forEach((listener) => listener({ target: this, preventDefault() {} }));
  }

  focus() {
    document.activeElement = this;
  }

  blur() {
    if (document.activeElement === this) document.activeElement = document.body;
  }

  select() {
    this.focus();
  }

  all() {
    return [this].concat(...this.children.map((child) => child.all()));
  }
}

const canvas = { width: 800, height: 600, clientWidth: 400, clientHeight: 300 };
const document = {
  hidden: false,
  body: new FakeElement('body'),
  activeElement: null,
  createElement(tagName) {
    record.created.push(tagName);
    return new FakeElement(tagName);
  },
  getElementById: (id) => (id === 'map' ? canvas : null),
  addEventListener(type, listener) {
    record.listeners.push('document:' + type);
    document.visibilityListeners.push(listener);
  },
  visibilityListeners: [],
  execCommand(command) {
    record.execCommands.push(command);
    return true;
  },
};
document.activeElement = document.body;

function clipboardFor(kind) {
  if (kind === 'missing') return undefined;
  return {
    writeText(text) {
      if (kind === 'refuses') return Promise.reject(new Error('not allowed'));
      record.copied.push(text);
      return Promise.resolve();
    },
  };
}

const page = {
  document: document,
  location: { search: input.search || '' },
  navigator: { userAgent: 'Node stand-in browser', clipboard: clipboardFor(input.clipboard || 'works') },
  performance: { now: () => clock },
  URLSearchParams: URLSearchParams,
  devicePixelRatio: 2,
  console: console,
  requestAnimationFrame(callback) {
    record.frameRequests += 1;
    frameCallbacks.push(callback);
    return frameCallbacks.length;
  },
  setInterval(callback, delay) {
    record.intervals.push(delay);
    intervalTimers.push({ callback: callback, delay: delay });
    return intervalTimers.length;
  },
  setTimeout(callback) {
    record.timeouts += 1;
    timeoutTimers.push(callback);
    return timeoutTimers.length;
  },
  addEventListener(type) {
    record.listeners.push('window:' + type);
  },
};
page.window = page;
page.Game = {
  net: {
    on(type, handler) {
      record.handlers.push(type);
      if (!netHandlers.has(type)) netHandlers.set(type, []);
      netHandlers.get(type).push(handler);
    },
    send(message) {
      if (!connected) return false;
      record.sent.push(message);
      return true;
    },
    ask() {
      throw new Error('The diagnostic must never use ask.');
    },
  },
  world: {
    walkingDirection: () => ({ dx: direction.dx, dy: direction.dy, since: direction.since }),
    ownDrawnPosition: () => (drawn ? { x: drawn.x, y: drawn.y } : null),
  },
};
vm.createContext(page);
vm.runInContext(fs.readFileSync(DIAGNOSTIC, 'utf8'), page, { filename: 'diagnostic.js' });

const diagnostic = page.Game.diagnostic;

function buttonWithText(text) {
  return document.body.all().find((element) => element.tagName === 'BUTTON' && element.textContent === text);
}

// Numbers from 0 up to 1 that look random but are the same in every run.
let seed = 12345;
function jitter() {
  seed = (seed * 1103515245 + 12345) % 2147483648;
  return seed / 2147483648;
}

function isZero(some) {
  return some.dx === 0 && some.dy === 0;
}

const STEPS = {
  frame(time) {
    clock = time;
    const waiting = frameCallbacks;
    frameCallbacks = [];
    waiting.forEach((callback) => callback(time));
  },
  clock(time) {
    clock = time;
  },
  direction(dx, dy) {
    const next = { dx: dx, dy: dy, since: direction.since };
    if (isZero(next)) next.since = null;
    else if (isZero(direction)) next.since = clock;
    direction = next;
  },
  position(x, y) {
    drawn = x === null ? null : { x: x, y: y };
  },
  receive(message) {
    (netHandlers.get(message.type) || []).forEach((handler) => handler(message));
  },
  tick(delay) {
    intervalTimers.filter((timer) => timer.delay === delay).forEach((timer) => timer.callback());
  },
  timeouts() {
    const waiting = timeoutTimers;
    timeoutTimers = [];
    waiting.forEach((callback) => callback());
  },
  connected(yes) {
    connected = yes;
  },
  long_walk(seconds) {
    const end = clock + seconds * 1000;
    let nextMessage = clock;
    let nextProbe = clock;
    let x = 0;
    STEPS.direction(1, 0);
    let lastFrame = clock;
    while (clock < end) {
      const frameAt = clock + 14 + 6 * jitter(); // about 60 frames per second
      x += (90 * (frameAt - lastFrame)) / 1000; // drawn at the server's walking speed
      lastFrame = frameAt;
      drawn = { x: x, y: 0 };
      STEPS.frame(frameAt);
      if (clock >= nextMessage) {
        STEPS.receive({ type: 'positions', players: [{ name: 'Ana', x: x, y: 0 }] });
        nextMessage = clock + 50 + 40 * jitter();
      }
      if (clock >= nextProbe) {
        STEPS.tick(1000);
        const sent = record.sent[record.sent.length - 1];
        clock += 20 + 40 * jitter(); // the round trip
        STEPS.receive({ type: 'welcome', name: sent.name });
        nextProbe = clock + 1000;
      }
    }
  },
  time_refresh(runs) {
    const refreshTimers = intervalTimers.filter((timer) => timer.delay === 500);
    for (let run = 0; run < runs; run++) {
      const before = process.hrtime.bigint();
      refreshTimers.forEach((timer) => timer.callback());
      record.refreshMs.push(Number(process.hrtime.bigint() - before) / 1e6);
    }
  },
  hide() {
    document.hidden = true;
    document.visibilityListeners.forEach((listener) => listener());
  },
  click(text) {
    const button = buttonWithText(text);
    button.focus(); // a click with the mouse gives a button the focus
    button.fire('click');
    record.focusAfterClicks.push(document.activeElement === button);
  },
  reset() {
    diagnostic.reset();
  },
};

async function main() {
  const changedArguments = [];
  const results = (input.calls || []).map(([name, ...values]) => {
    const before = JSON.stringify(values);
    const result = diagnostic[name](...values);
    if (JSON.stringify(values) !== before) changedArguments.push(name);
    return result;
  });
  for (const [name, ...values] of input.steps || []) {
    STEPS[name](...values);
    await new Promise((done) => setImmediate(done)); // let a copy finish
  }
  const panelTexts = document.body.all().filter((element) => element.tagName === 'PRE').map((element) => element.textContent);
  const buttons = document.body.all().filter((element) => element.tagName === 'BUTTON');
  process.stdout.write(JSON.stringify({
    active: diagnostic.active,
    exported: Object.keys(diagnostic),
    results: results,
    changedArguments: changedArguments,
    record: record,
    bodyChildren: document.body.children.length,
    panelTexts: panelTexts,
    buttons: buttons.map((button) => ({ text: button.textContent, tabIndex: button.tabIndex })),
    panelStyle: document.body.children.length ? document.body.children[0].style : null,
    numbers: diagnostic.active ? diagnostic.numbers() : null,
    report: diagnostic.active ? diagnostic.report() : null,
  }));
}

main();
