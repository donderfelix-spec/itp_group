// The real overview, with a small DOM and a canvas that records its markers.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class Element {
  constructor() {
    this.handlers = new Map();
    this.open = false;
  }
  addEventListener(type, handler) { this.handlers.set(type, handler); }
  emit(type, data) { this.handlers.get(type)(data); }
  append(...children) { this.children = children; }
  replaceChildren(...children) { this.children = children; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  matches(selector) { return selector.split(", ").includes(this.tagName); }
}

let markers = [];
let numbers = [];
const screen = new Element();
const context = {
  drawImage() { markers = []; numbers = []; },
  beginPath() {},
  arc(x, y) { markers.push([x, y]); },
  fill() {},
  stroke() {},
  fillText(number) { numbers.push(number); }
};
const elements = new Map();
const handlers = new Map();
const pauses = [];
const campus = {
  width: 680, height: 668, deck_label: { name: "Main Deck" },
  stations: [
    { id: 8, x: 90, y: 120, name: "An open task" },
    { id: 9, x: 110, y: 130, name: "Another player's task" }
  ]
};
const data = { campus, position: { x: 300, y: 280 }, stations: [8] };
let baseDrawings = 0;
let currentScreen = "lobby";
let blockingOverlay = null;
const document = {
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, new Element());
    const element = elements.get(id);
    if (id === "overview-map") element.getContext = () => context;
    return element;
  },
  querySelector() { return blockingOverlay; },
  createElement() {
    const element = new Element();
    element.getContext = () => context;
    return element;
  }
};
const Game = {
  world: {
    overviewData: () => data,
    setOverviewOpen: (open) => pauses.push(open),
    drawOverviewBase: () => { baseDrawings++; },
    roomAt: () => null
  },
  net: { on: (type, handler) => handlers.set(type, handler) },
  screens: { current: () => currentScreen }
};
const source = path.join(__dirname, "../client/js/world/overview.js");
vm.runInNewContext(fs.readFileSync(source, "utf8"), {
  window: screen, document, Game, HTMLElement: Element, queueMicrotask: (fn) => fn()
});

const dialog = elements.get("campus-overview");
const open = elements.get("overview-open");
const list = elements.get("overview-list");
const empty = elements.get("overview-empty");
const keyM = { code: "KeyM" };

handlers.get("lobby_state")({ phase: "round" });
screen.emit("keydown", keyM);
assert.equal(dialog.open, true);
assert.deepEqual(pauses, [true]);
assert.deepEqual(markers, [[300, 280], [300, 280], [90, 120]]);
assert.deepEqual(numbers, ["8"]);
assert.equal(list.children.length, 1);
assert.equal(list.children[0].children[1], "An open task");
assert.equal(elements.get("overview-location").textContent, "You · Main Deck");
assert.equal(empty.hidden, true);

data.stations = [];
handlers.get("station_done")();
assert.deepEqual(numbers, []);
assert.equal(list.children.length, 0);
assert.equal(empty.hidden, false);
assert.equal(baseDrawings, 1);

screen.emit("keydown", { ...keyM, repeat: true });
assert.equal(dialog.open, true);
screen.emit("keydown", keyM);
assert.equal(dialog.open, false);
assert.deepEqual(pauses, [true, false]);

const input = new Element();
input.tagName = "input";
screen.emit("keydown", { ...keyM, target: input });
assert.equal(dialog.open, false);
currentScreen = "home";
open.emit("click");
assert.equal(dialog.open, false);
currentScreen = "lobby";
blockingOverlay = new Element();
open.emit("click");
assert.equal(dialog.open, false);

blockingOverlay = null;
open.emit("click");
assert.equal(dialog.open, true);
handlers.get("meeting_state")();
assert.equal(dialog.open, false);
open.emit("click");
let cancelled = false;
dialog.emit("cancel", { preventDefault() { cancelled = true; } });
assert.equal(dialog.open, false);
assert.equal(cancelled, true);
