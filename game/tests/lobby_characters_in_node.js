// Runs the page's own lobby/lobby.js in Node, without a browser, for
// test_character_list.py (M1-1.8): which character buttons does the lobby
// build, and what does a click on each of them ask the server?
//
// The document, the canvas and Game.net are small stand-ins. lobby.js is the
// real code, and so is world/characters.js when it is loaded.
//
// Arguments: "with-characters" loads world/characters.js before lobby.js, as
// index.html does; "without-characters" leaves it out.
// Output (stdout): JSON list, one entry per character button in page order:
//   { "name": shown name, "asked": the message a click sends to the server }

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const CLIENT = path.join(__dirname, '..', 'client', 'js');

// A drawing context that accepts every call and draws nothing. Every method
// returns the context again, so chained or nested calls do not fail either.
const fakeContext = new Proxy(function () {}, {
  get: () => fakeContext,
  set: () => true,
  apply: () => fakeContext,
});

class FakeElement {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.listeners = {};
    this.textContent = '';
    this.hidden = false;
    this.disabled = false;
    this.classList = { toggle() {}, add() {}, remove() {} };
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  replaceChildren() {
    this.children = [];
  }

  addEventListener(type, listener) {
    this.listeners[type] = listener;
  }

  setAttribute() {}

  getContext() {
    return fakeContext;
  }
}

const elements = new Map();
const document = {
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, new FakeElement('div'));
    return elements.get(id);
  },
  createElement(tag) {
    return new FakeElement(tag);
  },
};

const asked = [];
const window = { devicePixelRatio: 1 };
window.Game = { net: { ask: (message) => asked.push(message) } };
const context = vm.createContext({ window, document, Game: window.Game, console });

const files = ['lobby/lobby.js'];
if (process.argv[2] === 'with-characters') files.unshift('world/characters.js');
files.forEach((file) => {
  const code = fs.readFileSync(path.join(CLIENT, file), 'utf8');
  vm.runInContext(code, context, { filename: file });
});

window.Game.lobby.setup();

// The name is the text of the first <span> inside the button's text part.
function shownName(button) {
  const text = button.children.find((child) => child.className === 'character-text');
  return text.children[0].textContent;
}

const buttons = document.getElementById('lobby-characters').children;
const result = buttons.map((button) => {
  asked.length = 0;
  button.listeners.click();
  return { name: shownName(button), asked: asked[0] };
});
process.stdout.write(JSON.stringify(result));
