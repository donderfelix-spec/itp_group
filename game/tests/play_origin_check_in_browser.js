// Browser part of test_play_origin_check.py (M3-2.6, S-207). Needs Playwright and Chromium.
//
// Usage: node play_origin_check_in_browser.js <game-port>
// The game server must run on 127.0.0.1:<game-port>. This script starts three
// small servers of its own on free ports:
//   - a "foreign" site: a page of another origin that tries to open the game's WebSocket;
//   - proxies in front of the game, like Render's: one keeps Host and adds
//     X-Forwarded-Proto/For; one rewrites Host to the game's own address and
//     names the public host in X-Forwarded-Host; one rewrites Host and adds nothing.
// Prints one JSON object:
//   direct    {localhost, ip}: whether the game page plays on http://localhost:<port> and http://127.0.0.1:<port>
//   foreign   {toIp, toLocalhost}: what a WebSocket from the foreign page got ({opened, code})
//   proxied   {keepHost, forwardedHost}: whether the game page plays through that proxy;
//             rewrittenHostOnly: what the page's WebSocket got through the third proxy
//   console   per page, its console errors and warnings
const http = require('http');
const net = require('net');
const { chromium } = require('playwright');

const gamePort = Number(process.argv[2]);
const GAME = '127.0.0.1';
const consoleLines = {};

function listen(server) {
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server.address().port)));
}

function foreignSite() {
  return http.createServer((request, response) => {
    response.writeHead(200, { 'Content-Type': 'text/html' });
    response.end('<!doctype html><title>Another site</title><p>Another site</p>');
  });
}

// A reverse proxy for pages and WebSockets. `changeHeaders(headers, ownHost)`
// returns the headers sent on to the game.
function proxy(changeHeaders) {
  const server = http.createServer((request, response) => {
    const headers = changeHeaders({ ...request.headers }, request.headers.host);
    const onward = http.request(
      { host: GAME, port: gamePort, path: request.url, method: request.method, headers },
      (answer) => {
        response.writeHead(answer.statusCode, answer.headers);
        answer.pipe(response);
      },
    );
    onward.on('error', () => response.destroy());
    request.pipe(onward);
  });
  server.on('upgrade', (request, socket, head) => {
    const headers = changeHeaders({ ...request.headers }, request.headers.host);
    const onward = net.connect(gamePort, GAME, () => {
      const lines = [`${request.method} ${request.url} HTTP/1.1`];
      for (const [name, value] of Object.entries(headers)) lines.push(`${name}: ${value}`);
      onward.write(lines.join('\r\n') + '\r\n\r\n');
      if (head && head.length) onward.write(head);
      onward.pipe(socket);
      socket.pipe(onward);
    });
    onward.on('error', () => socket.destroy());
    socket.on('error', () => onward.destroy());
  });
  return server;
}

const keepHost = (headers) => ({ ...headers, 'x-forwarded-proto': 'https', 'x-forwarded-for': '203.0.113.7' });
const forwardedHost = (headers, ownHost) => ({
  ...headers, host: `${GAME}:${gamePort}`, 'x-forwarded-host': ownHost, 'x-forwarded-proto': 'https',
});
const rewrittenHostOnly = (headers) => ({ ...headers, host: `${GAME}:${gamePort}` });

async function newPage(browser, label) {
  const page = await browser.newPage();
  consoleLines[label] = [];
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') consoleLines[label].push(m.text());
  });
  page.on('pageerror', (e) => consoleLines[label].push('page error: ' + e.message));
  return page;
}

// Plays as a guest and opens a lobby. True if the lobby screen comes.
async function plays(browser, label, url) {
  const page = await newPage(browser, label);
  try {
    await page.goto(url);
    await page.click('#start-guest');
    await page.waitForSelector('#screen-home:not([hidden])', { timeout: 10000 });
    await page.click('#home-create');
    await page.waitForSelector('#screen-lobby:not([hidden])', { timeout: 10000 });
    return true;
  } catch (problem) {
    return false;
  } finally {
    await page.close();
  }
}

// Opens a WebSocket from the page and tells what happened.
function trySocket(page, url) {
  return page.evaluate((address) => new Promise((resolve) => {
    const socket = new WebSocket(address);
    const timer = setTimeout(() => resolve({ opened: false, timedOut: true }), 8000);
    socket.onopen = () => { clearTimeout(timer); socket.close(); resolve({ opened: true }); };
    socket.onclose = (event) => { clearTimeout(timer); resolve({ opened: false, code: event.code }); };
  }), url);
}

(async () => {
  const foreignPort = await listen(foreignSite());
  const keepPort = await listen(proxy(keepHost));
  const forwardedPort = await listen(proxy(forwardedHost));
  const rewrittenPort = await listen(proxy(rewrittenHostOnly));
  const browser = await chromium.launch();
  const result = { direct: {}, foreign: {}, proxied: {}, console: consoleLines };

  result.direct.localhost = await plays(browser, 'localhost', `http://localhost:${gamePort}/`);
  result.direct.ip = await plays(browser, 'ip', `http://127.0.0.1:${gamePort}/`);

  const foreign = await newPage(browser, 'foreign');
  await foreign.goto(`http://127.0.0.1:${foreignPort}/`);
  result.foreign.toIp = await trySocket(foreign, `ws://127.0.0.1:${gamePort}/ws`);
  result.foreign.toLocalhost = await trySocket(foreign, `ws://localhost:${gamePort}/ws`);

  result.proxied.keepHost = await plays(browser, 'keepHost', `http://127.0.0.1:${keepPort}/`);
  result.proxied.forwardedHost = await plays(browser, 'forwardedHost', `http://127.0.0.1:${forwardedPort}/`);
  const rewritten = await newPage(browser, 'rewrittenHostOnly');
  await rewritten.goto(`http://127.0.0.1:${rewrittenPort}/`);
  result.proxied.rewrittenHostOnly = await trySocket(rewritten, `ws://127.0.0.1:${rewrittenPort}/ws`);

  await browser.close();
  process.stdout.write(JSON.stringify(result));
  process.exit(0);
})().catch((problem) => {
  console.error(problem);
  process.exit(1);
});
