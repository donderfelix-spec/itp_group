// Browser part of test_play_classic_report_after_meeting_and_new_round.py.
// Needs Playwright and Chromium.
//
// Usage: node play_classic_report_after_meeting_and_new_round_in_browser.js <base-url>
//
// Built like play_classic_leaving_in_browser.js: the Python test writes one
// JSON command per line on stdin and reads one JSON answer per line on
// stdout ({"ok": value} or {"error": text}). Every page records, from before
// its first script runs:
//   window.__received   every message its WebSocket got, with the time
//   window.__sent       every message it sent, with the time
//   window.__shown      every text that appeared in the message line at the
//                       top (#message), with the time and whether it was an error
//   window.__changes    every change of the meeting window, the vote result
//                       and the end screen: shown or hidden, and the text, with
//                       the time (a MutationObserver, so even a change that
//                       lasts no frame is recorded)
//   window.__sheetsDrawn  how many F-sheets the map drew in each of the last
//                       frames (an "F" drawn on the map canvas between two
//                       calls of Game.world.drawMap)
// and the driver keeps every console error or warning and page error.
//
// Commands: open {label}, eval {label, js}, wait {label, js, timeout},
// click {label, selector}, fill {label, selector, text}, press {label, key},
// down/up {label, key}, screenshot {label, path}, problems {}, quit {}.
const readline = require('readline');
const { chromium } = require('playwright');

const base = process.argv[2];
const pages = {};
const problems = [];
let browser = null;

// Runs in the page before any of its own scripts.
function recorder() {
  window.__received = [];
  window.__sent = [];
  window.__shown = [];
  window.__changes = [];
  window.__sheetsDrawn = [];
  const NativeSocket = window.WebSocket;
  window.WebSocket = function (...args) {
    const socket = new NativeSocket(...args);
    socket.addEventListener('message', (event) => {
      try {
        window.__received.push({ t: performance.now(), m: JSON.parse(event.data) });
      } catch (e) { /* not JSON: nothing to record */ }
    });
    const send = socket.send.bind(socket);
    socket.send = (data) => {
      try {
        window.__sent.push({ t: performance.now(), m: JSON.parse(data) });
      } catch (e) { /* not JSON */ }
      return send(data);
    };
    window.__socket = socket;
    return socket;
  };
  window.WebSocket.prototype = NativeSocket.prototype;
  Object.assign(window.WebSocket, { OPEN: 1, CLOSED: 3, CONNECTING: 0, CLOSING: 2 });

  // The F of every sheet is drawn with fillText on the map canvas.
  let sheetsThisFrame = 0;
  const fillText = CanvasRenderingContext2D.prototype.fillText;
  CanvasRenderingContext2D.prototype.fillText = function (text, ...rest) {
    if (this.canvas && this.canvas.id === 'map' && text === 'F') sheetsThisFrame += 1;
    return fillText.call(this, text, ...rest);
  };
  // Game.world.drawMap is looked up at every frame: wrapping it marks where a frame starts.
  const wrap = () => {
    const world = window.Game && window.Game.world;
    if (!world || typeof world.drawMap !== 'function' || world.drawMap.__recorded) return;
    const original = world.drawMap;
    const recorded = function () {
      window.__sheetsDrawn.push(sheetsThisFrame);
      if (window.__sheetsDrawn.length > 50) window.__sheetsDrawn.shift();
      sheetsThisFrame = 0;
      return original.apply(this, arguments);
    };
    recorded.__recorded = true;
    world.drawMap = recorded;
  };
  const watch = () => {
    const line = document.getElementById('message');
    if (line) {
      const note = () => {
        if (!line.hidden && line.textContent) {
          window.__shown.push({ t: performance.now(), text: line.textContent, error: line.classList.contains('message-error') });
        }
      };
      new MutationObserver(note).observe(line, { childList: true, characterData: true, subtree: true, attributes: true });
    }
    ['classic-meeting', 'classic-vote-result', 'classic-end-screen'].forEach((id) => {
      const element = document.getElementById(id);
      if (!element) return;
      const note = () => window.__changes.push({
        t: performance.now(), id, shown: !element.hidden,
        text: id === 'classic-vote-result' ? element.textContent : '',
      });
      new MutationObserver(note).observe(element, { attributes: true, attributeFilter: ['hidden'], childList: id === 'classic-vote-result', characterData: true, subtree: id === 'classic-vote-result' });
    });
  };
  document.addEventListener('DOMContentLoaded', () => { wrap(); watch(); });
  window.addEventListener('load', wrap);
}

const commands = {
  async open({ label }) {
    if (!browser) browser = await chromium.launch();
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    page.on('console', (m) => {
      if (m.type() === 'error' || m.type() === 'warning') problems.push(`${label} ${m.type()}: ${m.text()}`);
    });
    page.on('pageerror', (e) => problems.push(`${label} page error: ${e.message}`));
    await page.addInitScript(recorder);
    pages[label] = { page, context };
    await page.goto(base + '/');
    await page.click('#start-guest');
    await page.waitForSelector('#screen-home:not([hidden])');
    return page.evaluate(() => {
      const signed = window.__received.find((r) => r.m.type === 'signed_in');
      return signed ? signed.m.name : null;
    });
  },
  async eval({ label, js }) {
    return pages[label].page.evaluate(js);
  },
  // Polled from here: the page's Content Security Policy forbids the
  // string functions of waitForFunction.
  async wait({ label, js, timeout }) {
    const page = pages[label].page;
    const end = Date.now() + (timeout || 15000);
    for (;;) {
      const value = await page.evaluate(js);
      if (value) return value;
      if (Date.now() > end) throw new Error(`timed out waiting for ${js}`);
      await page.waitForTimeout(30);
    }
  },
  async click({ label, selector }) {
    await pages[label].page.click(selector, { timeout: 5000 });
    return true;
  },
  async fill({ label, selector, text }) {
    await pages[label].page.fill(selector, text);
    return true;
  },
  async press({ label, key }) {
    await pages[label].page.keyboard.press(key);
    return true;
  },
  async down({ label, key }) {
    await pages[label].page.keyboard.down(key);
    return true;
  },
  async up({ label, key }) {
    await pages[label].page.keyboard.up(key);
    return true;
  },
  async screenshot({ label, path }) {
    await pages[label].page.screenshot({ path });
    return path;
  },
  async problems() {
    return problems;
  },
  async quit() {
    if (browser) await browser.close();
    browser = null;
    return true;
  },
};

const lines = readline.createInterface({ input: process.stdin });
let queue = Promise.resolve();
lines.on('line', (line) => {
  queue = queue.then(async () => {
    let answer;
    try {
      const command = JSON.parse(line);
      const value = await commands[command.cmd](command);
      answer = { ok: value === undefined ? null : value };
    } catch (e) {
      answer = { error: String(e && e.stack || e) };
    }
    process.stdout.write(JSON.stringify(answer) + '\n');
  });
});
// When the test ends (or dies), stdin closes: close Chromium and stop.
lines.on('close', () => {
  queue.then(() => (browser ? browser.close() : null)).finally(() => process.exit(0));
});
