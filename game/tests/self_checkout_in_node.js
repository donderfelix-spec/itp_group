// Runs the page's own js/minigames/self_checkout.js in Node, without a
// browser, for test_self_checkout_message_in_view.py (M2-4.12).
//
// The document and the timers are small stand-ins. Every element writes down
// each call of scrollIntoView, so a test can see when and how the minigame
// asks the browser to bring something into view. The minigame is the real code.
//
// Input (stdin): JSON {content, steps}. Each step is a list:
//   ["click", place]   the player clicks the product that started at this
//                      place of the belt (0 to 5), wherever it lies now
//   ["wait", ms]       this many milliseconds pass
// Output (stdout): JSON list with one entry per step, each:
//   {message, total, onBelt, inBag, scrolls, solved}
// where `scrolls` lists the options of every scrollIntoView call of that
// step, as [{element, options}], and onBelt / inBag list product names.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SELF_CHECKOUT_JS = path.join(__dirname, '..', 'client', 'js', 'minigames', 'self_checkout.js');

let scrolls = [];

class FakeElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.className = '';
    this.textContent = '';
    this.children = [];
    this.parent = null;
    this.attributes = {};
    this.listeners = {};
    this.classList = {
      add: (name) => { this.className += ' ' + name; },
    };
  }

  append(...children) {
    children.forEach((child) => {
      if (child.parent) {
        child.parent.children = child.parent.children.filter((other) => other !== child);
      }
      child.parent = this;
      this.children.push(child);
    });
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  addEventListener(type, listener) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  click() {
    (this.listeners.click || []).forEach((listener) => listener({}));
  }

  scrollIntoView(options) {
    scrolls.push({ element: this.className, options: options === undefined ? null : options });
  }

  // Every element below this one, in page order.
  all() {
    return this.children.flatMap((child) => [child, ...child.all()]);
  }

  find(className) {
    return this.all().find((element) => element.className.split(' ').includes(className));
  }

  findAll(className) {
    return this.all().filter((element) => element.className.split(' ').includes(className));
  }
}

// Timers run only when a step lets the time pass.
let now = 0;
let nextTimerId = 1;
const timers = new Map();

function setTimeout(callback, ms) {
  const id = nextTimerId;
  nextTimerId += 1;
  timers.set(id, { at: now + ms, callback });
  return id;
}

function clearTimeout(id) {
  timers.delete(id);
}

function wait(ms) {
  const end = now + ms;
  for (;;) {
    const due = [...timers.entries()].filter(([, timer]) => timer.at <= end)
      .sort((a, b) => a[1].at - b[1].at)[0];
    if (!due) break;
    timers.delete(due[0]);
    now = due[1].at;
    due[1].callback();
  }
  now = end;
}

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const minigames = {};
const page = {
  document: { createElement: (tag) => new FakeElement(tag) },
  setTimeout,
  clearTimeout,
  Game: { minigames: { register: (kind, minigame) => { minigames[kind] = minigame; } } },
};
page.window = page;
vm.runInNewContext(fs.readFileSync(SELF_CHECKOUT_JS, 'utf8'), page, { filename: SELF_CHECKOUT_JS });

const body = new FakeElement('div');
let solved = false;
minigames.self_checkout.start(body, input.content, () => { solved = true; });

// The product buttons in the order they started on the belt.
const products = body.findAll('checkout-product');
const belt = body.find('checkout-belt');
const bag = body.find('checkout-bag');

function namesIn(row) {
  return row.findAll('checkout-name').map((name) => name.textContent);
}

const results = input.steps.map(([kind, value]) => {
  scrolls = [];
  if (kind === 'click') products[value].click();
  else if (kind === 'wait') wait(value);
  else throw new Error('unknown step ' + kind);
  return {
    message: body.find('checkout-message').textContent,
    total: body.findAll('checkout-amount')[1].textContent,
    onBelt: namesIn(belt),
    inBag: namesIn(bag),
    scrolls,
    solved,
  };
});

process.stdout.write(JSON.stringify(results));
