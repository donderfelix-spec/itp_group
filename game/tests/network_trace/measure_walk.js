// Measures what the own player sees while walking, frame by frame.
// Usage: NODE_PATH=$(npm root -g) node measure_walk.js PORT PLAYERS SECONDS OUT.json
// One headless Chromium guest opens the game through PORT (for example the
// delay proxy), creates a lobby and walks right and left in turns of 1.6 s.
// PLAYERS-1 bots join the lobby straight on BOTPORT (default 8000) and walk
// too. Every frame records the camera centre (the own drawn position), the
// drawing time and each character's walk phase; every positions message its
// arrival time. Needs Playwright with Chromium, which is NOT a dependency of
// the game (S-72): it is a tool for measuring by hand.
const { chromium } = require('playwright');
const fs = require('fs');
const [PORT, PLAYERS, SECONDS, OUT] = [process.argv[2], +process.argv[3], +process.argv[4], process.argv[5]];
const SEGMENT_MS = 1600;

const INSTRUMENT = () => {
  window.__m = { frames: [], msgs: [], keys: [] };
  let aim = null;
  const st = CanvasRenderingContext2D.prototype.setTransform;
  CanvasRenderingContext2D.prototype.setTransform = function (a, b, c, d, e, f) {
    if (typeof a === 'number' && a !== 1 && this.canvas.id === 'map') {
      aim = { cx: (this.canvas.width / 2 - e) / a, cy: (this.canvas.height / 2 - f) / d, scale: a };
    }
    return st.apply(this, arguments);
  };
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) => raf((now) => {
    aim = null;
    const t0 = performance.now();
    cb(now);
    const t1 = performance.now();
    if (aim) window.__m.frames.push({ t: now, dur: t1 - t0, cx: aim.cx, cy: aim.cy, scale: aim.scale, figs: window.__figs || [] });
    window.__figs = [];
  });
  const WS = window.WebSocket;
  window.WebSocket = function (url, p) {
    const ws = p ? new WS(url, p) : new WS(url);
    ws.addEventListener('message', (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === 'positions') window.__m.msgs.push({ t: performance.now(), players: m.players });
      } catch (e) {}
    });
    return ws;
  };
  window.WebSocket.prototype = WS.prototype;
  Object.assign(window.WebSocket, { OPEN: 1, CLOSED: 3, CONNECTING: 0, CLOSING: 2 });
  window.addEventListener('keydown', (e) => { if (!e.repeat) window.__m.keys.push({ t: performance.now(), key: e.code, down: true }); }, true);
  window.addEventListener('keyup', (e) => window.__m.keys.push({ t: performance.now(), key: e.code, down: false }), true);
};

function bot(code, offset) {
  return new Promise((resolve) => {
    const ws = new WebSocket('ws://127.0.0.1:' + (process.env.BOTPORT || 8000) + '/ws');
    let dir = 1, timer = null;
    ws.onopen = () => ws.send(JSON.stringify({ type: 'guest' }));
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === 'signed_in') ws.send(JSON.stringify({ type: 'join_lobby', code }));
      if (m.type === 'lobby_state' && !timer) {
        timer = 1;
        resolve({
          walk: () => {
            setTimeout(() => {
              ws.send(JSON.stringify({ type: 'move', dx: dir, dy: 0 }));
              timer = setInterval(() => { dir = -dir; ws.send(JSON.stringify({ type: 'move', dx: dir, dy: 0 })); }, SEGMENT_MS);
            }, offset);
          },
          stop: () => { clearInterval(timer); ws.close(); },
        });
      }
    };
  });
}

(async () => {
  const browser = await chromium.launch({ args: ['--disable-renderer-backgrounding', '--disable-background-timer-throttling'] });
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: +(process.env.DPR || 1) })).newPage();
  await page.addInitScript(INSTRUMENT);
  await page.goto(`http://127.0.0.1:${PORT}/`);
  await page.waitForTimeout(1500); await page.click('#start-guest');
  await page.waitForSelector('#home-create:visible');
  const ownName = (await page.textContent('#home-name')).trim();
  await page.click('#home-create');
  await page.waitForFunction(() => /\S/.test(document.querySelector('#lobby-code').textContent));
  const code = (await page.textContent('#lobby-code')).replace(/.*?([A-Z0-9]{4})\s*$/s, '$1').trim();
  const bots = [];
  for (let i = 1; i < PLAYERS; i++) bots.push(await bot(code, 100 * i));
  await page.waitForTimeout(1500);
  await page.evaluate(() => {
    const draw = Game.world.drawCharacter;
    Game.world.drawCharacter = function (ctx, character, x, y, h, pose) {
      (window.__figs = window.__figs || []).push({ x: x, phase: pose && pose.walkPhase, stride: pose && pose.stride });
      return draw.apply(this, arguments);
    };
  });
  await page.evaluate(() => { window.__m.frames = []; window.__m.msgs = []; window.__m.keys = []; });
  bots.forEach((b) => b.walk());
  const segments = Math.ceil((SECONDS * 1000) / SEGMENT_MS);
  let key = 'ArrowRight';
  for (let s = 0; s < segments; s++) {
    await page.keyboard.down(key);
    await page.waitForTimeout(SEGMENT_MS);
    await page.keyboard.up(key);
    key = key === 'ArrowRight' ? 'ArrowLeft' : 'ArrowRight';
  }
  await page.waitForTimeout(500);
  const data = await page.evaluate(() => window.__m);
  data.ownName = ownName; data.code = code; data.players = PLAYERS;
  fs.writeFileSync(OUT, JSON.stringify(data));
  bots.forEach((b) => b.stop());
  await browser.close();
  console.log('ok', code, ownName, data.frames.length, 'frames', data.msgs.length, 'msgs');
})().catch((e) => { console.error(e); process.exit(1); });
