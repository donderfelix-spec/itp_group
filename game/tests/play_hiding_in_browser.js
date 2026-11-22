// Browser part of test_play_hiding.py (M3-1.4). Needs Playwright and Chromium.
//
// Usage: node play_hiding_in_browser.js <base-url>
//
// The Python test drives the pages: it writes one JSON command per line on
// stdin and reads one JSON answer per line on stdout ({"ok": value} or
// {"error": text}). Every page records, from before its first script runs:
//   window.__received  every message its WebSocket got, with the time
//   window.__drawn     every character the map canvas drew, with the time,
//                      the place on the map and the transparency
//   window.__hintShown the times (every 50 ms) at which "Hidden" was shown
// and the driver keeps every console error or warning and page error.
//
// Commands: open {label}, goto_guest {label}, eval {label, js}, click
// {label, selector}, fill {label, selector, text}, down/up {label, key},
// screenshot {label, path}, problems {}, close_page {label}, quit {}.
const readline = require('readline');
const { chromium } = require('playwright');

const base = process.argv[2];
const pages = {};
const problems = [];
let browser = null;

// Runs in the page before any of its own scripts.
function recorder() {
  window.__received = [];
  window.__drawn = [];
  const NativeSocket = window.WebSocket;
  window.WebSocket = function (...args) {
    const socket = new NativeSocket(...args);
    socket.addEventListener('message', (event) => {
      try {
        window.__received.push({ t: performance.now(), m: JSON.parse(event.data) });
      } catch (e) { /* not JSON: nothing to record */ }
    });
    window.__socket = socket;
    return socket;
  };
  window.WebSocket.prototype = NativeSocket.prototype;
  Object.assign(window.WebSocket, { OPEN: 1, CLOSED: 3, CONNECTING: 0, CLOSING: 2 });
  // Game.world.drawCharacter is looked up at every call, so wrapping it
  // records every character the page draws.
  const wrap = () => {
    const world = window.Game && window.Game.world;
    if (!world || typeof world.drawCharacter !== 'function' || world.drawCharacter.__recorded) return false;
    const original = world.drawCharacter;
    const recorded = function (ctx, character, x, y, height, pose) {
      if (ctx && ctx.canvas && ctx.canvas.id === 'map') {
        // x and y are map units; px and py are the pixels on the canvas.
        const at = new DOMPoint(x, y).matrixTransform(ctx.getTransform());
        window.__drawn.push({ t: performance.now(), character, x, y, alpha: ctx.globalAlpha, px: at.x, py: at.y });
        if (window.__drawn.length > 20000) window.__drawn.splice(0, 10000);
      }
      return original.apply(this, arguments);
    };
    recorded.__recorded = true;
    world.drawCharacter = recorded;
    return true;
  };
  document.addEventListener('DOMContentLoaded', wrap);
  window.addEventListener('load', wrap);
  // Every 50 ms: is the word "Hidden" on the screen? (window.__hintShown)
  window.__hintShown = [];
  setInterval(() => {
    const hint = document.getElementById('classic-hidden-hint');
    const panel = document.getElementById('classic-progress');
    if (hint && panel && !hint.hidden && !panel.hidden && hint.getBoundingClientRect().width > 0) {
      window.__hintShown.push(performance.now());
    }
  }, 50);
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
    await pages[label].page.click(selector);
    return true;
  },
  async fill({ label, selector, text }) {
    await pages[label].page.fill(selector, text);
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
