// Browser part of test_play_classic_leaving.py (M3-3.20, M3-3.9, M3-3.11,
// M3-3.8). Needs Playwright and Chromium.
//
// Usage: node play_classic_leaving_in_browser.js <base-url>
//
// Built like play_hiding_in_browser.js: the Python test writes one JSON
// command per line on stdin and reads one JSON answer per line on stdout
// ({"ok": value} or {"error": text}). Every page records, from before its
// first script runs:
//   window.__received      every message its WebSocket got, with the time
//   window.__sent          every message it sent, with the time
//   window.__drawn         every character the map canvas drew, with the time
//   window.__meetingTexts  every text drawn on the meeting canvas, with the time
//   window.__shown         every text that appeared in the message line at
//                          the top (#message), with the time and whether it
//                          was an error
// and the driver keeps every console error or warning and page error.
//
// Commands: open {label}, eval {label, js}, eval_together {labels, js} (the
// same script on several pages at the same moment), wait {label, js,
// timeout}, click {label, selector}, fill {label, selector, text}, press
// {label, key}, screenshot {label, path}, problems {}, close_page {label},
// quit {}.
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
  window.__drawn = [];
  window.__meetingTexts = [];
  window.__shown = [];
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

  // The texts of the meeting window: its canvas draws them with fillText.
  const fillText = CanvasRenderingContext2D.prototype.fillText;
  CanvasRenderingContext2D.prototype.fillText = function (text, ...rest) {
    if (this.canvas && this.canvas.id === 'classic-meeting-canvas') {
      window.__meetingTexts.push({ t: performance.now(), text: String(text) });
      if (window.__meetingTexts.length > 20000) window.__meetingTexts.splice(0, 10000);
    }
    return fillText.call(this, text, ...rest);
  };

  // Game.world.drawCharacter is looked up at every call, so wrapping it
  // records every character the page draws.
  const wrap = () => {
    const world = window.Game && window.Game.world;
    if (!world || typeof world.drawCharacter !== 'function' || world.drawCharacter.__recorded) return false;
    const original = world.drawCharacter;
    const recorded = function (ctx, character, x, y) {
      if (ctx && ctx.canvas && ctx.canvas.id === 'map') {
        window.__drawn.push({ t: performance.now(), character, x, y });
        if (window.__drawn.length > 20000) window.__drawn.splice(0, 10000);
      }
      return original.apply(this, arguments);
    };
    recorded.__recorded = true;
    world.drawCharacter = recorded;
    return true;
  };
  // The message line at the top: every text it shows, as the player reads it.
  const watchMessage = () => {
    const line = document.getElementById('message');
    if (!line) return;
    const note = () => {
      if (!line.hidden && line.textContent) {
        window.__shown.push({ t: performance.now(), text: line.textContent, error: line.classList.contains('message-error') });
      }
    };
    new MutationObserver(note).observe(line, { childList: true, characterData: true, subtree: true, attributes: true });
  };
  document.addEventListener('DOMContentLoaded', () => { wrap(); watchMessage(); });
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
  // Two players act at the same moment: the script runs on every page at once.
  async eval_together({ labels, js }) {
    return Promise.all(labels.map((label) => pages[label].page.evaluate(js)));
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
  async screenshot({ label, path }) {
    await pages[label].page.screenshot({ path });
    return path;
  },
  async problems() {
    return problems;
  },
  // Closing the tab: the page's connection is lost, as when a player closes it.
  async close_page({ label }) {
    await pages[label].context.close();
    delete pages[label];
    return true;
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
