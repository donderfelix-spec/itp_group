// Runs the page's own net.js, forms.js and main.js in Node, without a browser,
// for test_play_reconnect.py (M3-2.2, S-109).
//
// The WebSocket, the document and the other parts of the page are small
// stand-ins, so a test can play the server's side: open and lose the
// connection, hand the page messages, click buttons. The page is the real code.
//
// Input (stdin): a JSON list of steps, each a list:
//   ["open"]                  the newest connection opens
//   ["receive", message]      the server sends this message on it
//   ["lose"]                  the open connection is lost; the page tries again
//   ["fail"]                  an attempt to reconnect fails before it opens
//   ["click", id]             the player clicks the button with this id
//   ["type", id, text]        the player types this text into a field
//   ["submit", id]            the player sends the form with this id
// Output (stdout): JSON with every message the page sent, the visible
// screen, the join field, the error at the join field and the top message.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const CLIENT = path.join(__dirname, '..', 'client', 'js');
const PAGE_FILES = ['net.js', 'lobby/forms.js', 'main.js'];
// The fields of each form, by the `name` the page reads: name -> element id.
const FORM_FIELDS = {
  'signup-form': { name: 'signup-name', password: 'signup-password' },
  'login-form': { name: 'login-name', password: 'login-password' },
  'join-form': { code: 'join-code' },
};

const sent = [];
const sockets = [];
const timers = [];
const elements = new Map();
let screen = 'start';
let topMessage = '';

class FakeElement {
  constructor(id) {
    this.id = id;
    this.value = '';
    this.textContent = '';
    this.disabled = false;
    this.hidden = false;
    this.type = 'password';
    this.listeners = {};
    this.elements = {};
  }

  addEventListener(type, listener) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  fire(type) {
    const event = { preventDefault() {} };
    (this.listeners[type] || []).forEach((listener) => listener(event));
  }

  reset() {
    Object.values(this.elements).forEach((field) => { field.value = ''; });
  }

  setAttribute() {}
  setSelectionRange() {}
}

function element(id) {
  if (!elements.has(id)) {
    const made = new FakeElement(id);
    elements.set(id, made);
    Object.entries(FORM_FIELDS[id] || {}).forEach(([name, fieldId]) => {
      made.elements[name] = element(fieldId);
    });
  }
  return elements.get(id);
}

const document = {
  activeElement: null,
  getElementById: element,
  // forms.js empties every `.field-error`; in index.html their ids end in "-error".
  querySelectorAll: () => [...elements.values()].filter((found) => found.id.endsWith('-error')),
};

class FakeSocket {
  constructor() {
    this.readyState = FakeSocket.CONNECTING;
    this.listeners = {};
    sockets.push(this);
  }

  addEventListener(type, listener) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  fire(type, event) {
    (this.listeners[type] || []).forEach((listener) => listener(event || {}));
  }

  send(text) {
    sent.push(JSON.parse(text));
  }
}
FakeSocket.CONNECTING = 0;
FakeSocket.OPEN = 1;
FakeSocket.CLOSED = 3;

// The screens and messages: only what main.js and forms.js read back.
const screens = {
  show: (name) => { screen = name; },
  current: () => screen,
  showMessage: (text) => { topMessage = text; },
  showLastingMessage: (text) => { topMessage = text; },
  hideMessage: () => { topMessage = ''; },
};

// The lobby, the countdown, the minigames, ...: not needed here, every call does nothing.
const doesNothing = new Proxy({}, { get: () => () => undefined });

const page = {
  document: document,
  WebSocket: FakeSocket,
  location: { protocol: 'http:', host: 'localhost:8000' },
  setTimeout: (action) => { timers.push(action); },
  clearTimeout: () => {},
  console: console,
};
page.window = page;
page.Game = {
  screens: screens,
  lobby: doesNothing,
  duel: doesNothing,
  countdown: doesNothing,
  statistics: doesNothing,
  minigames: doesNothing,
};
vm.createContext(page);
PAGE_FILES.forEach((file) => {
  const code = fs.readFileSync(path.join(CLIENT, file), 'utf8');
  vm.runInContext(code, page, { filename: file });
});

function newestSocket() {
  return sockets[sockets.length - 1];
}

// net.js waits before it tries again; here the attempt starts at once.
function runTimers() {
  timers.splice(0).forEach((action) => action());
}

function close(socket) {
  socket.readyState = FakeSocket.CLOSED;
  socket.fire('close');
  runTimers();
}

const STEPS = {
  open() {
    newestSocket().readyState = FakeSocket.OPEN;
    newestSocket().fire('open');
  },
  receive(message) {
    newestSocket().fire('message', { data: JSON.stringify(message) });
  },
  lose() {
    close(newestSocket());
  },
  fail() {
    close(newestSocket());
  },
  click(id) {
    element(id).fire('click');
  },
  type(id, text) {
    element(id).value = text;
  },
  submit(id) {
    element(id).fire('submit');
  },
};

const steps = JSON.parse(fs.readFileSync(0, 'utf8'));
steps.forEach(([name, ...values]) => STEPS[name](...values));

process.stdout.write(JSON.stringify({
  sent: sent,
  screen: screen,
  joinCode: element('join-code').value,
  codeError: element('join-code-error').textContent,
  message: topMessage,
}));
