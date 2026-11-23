// Browser part of test_play_meeting_chat.py (S-210): how many chat messages
// the Classic meeting window shows, and where, in Chromium.
// Needs Playwright and Chromium.
//
// The page comes from the real server, but its WebSocket is answered by this
// script (Playwright's routeWebSocket), as in
// meeting_window_and_end_screen_in_browser.js: it sends the page the
// messages a server would send, so every chat message is exactly as wanted.
// Every fillText and moveTo on the meeting canvas is recorded from its last
// clearRect on, so the script reads what the last draw put where.
//
// Usage: node meeting_chat_in_browser.js <base-url> [shots-folder]
// Prints one JSON object:
//   console    every console error or warning and page error
//   seen       per situation (e.g. "report short8 1280x800"): the canvas's size,
//              the y of the line above the chat, the heading, the player
//              list texts, the chat messages drawn (name, y and lines with
//              their y and width), the text's x and the messages sent
// With a shots folder it saves <reason>_short8_<viewport>.png and
// <reason>_mixed8_<viewport>.png (the meeting window only) there.
const { chromium } = require('playwright');

const base = process.argv[2];
const shotsFolder = process.argv[3];
const problems = [];

const OWN = 'Ana';
const FIVE = ['Ana', 'Bo', 'Cy', 'Di', 'Ed'];
// Four living players with long names and many dead ones: the lists need all
// three rows (eight dead), with the vote buttons of four living players.
const LONG_LIVING = ['Ana', 'Bartholomew', 'Constantina', 'Dimitrios'];
const LONG_GHOSTS = ['Evangelina', 'Florentino', 'Gwendolyn', 'Hieronymus', 'Ignatius', 'Josephina', 'Konstantin', 'Leopoldine'];
const CHARACTERS = ['consultant', 'finance_bro', 'surfer', 'founder'];
const VIEWPORTS = {
  '1280x800': { width: 1280, height: 800 },
  '1024x700': { width: 1024, height: 700 },
  '1366x768': { width: 1366, height: 768 },
  '320x640': { width: 320, height: 640 },
  // Short enough for the compact layout (canvas under 340 px).
  '1280x560': { width: 1280, height: 560 },
};

const SHORT8 = [
  ['Bo', 'Where was everyone?'],
  ['Cy', 'Library, doing slides.'],
  ['Di', 'I was at the canteen.'],
  ['Di', 'Bo was near the sheet.'],
  ['Bo', 'No, I was not.'],
  ['Ana', 'Who found it?'],
  ['Cy', 'Di reported it.'],
  ['Di', 'Vote Bo then?'],
].map(([player, text]) => ({ player_id: player, text }));

const LONG_TEXT = 'I walked from the library to the main deck and saw Bo standing right next to the sheet, '
  + 'then he ran towards the canteen before anyone else came, which is why I think he is the Free Rider here.';
const MIXED8 = [
  ['Bo', 'Where was everyone when it happened?'],
  ['Cy', 'I was in the library the whole time, finishing the chart for our slides, ask Di because Di saw me there.'],
  ['Di', 'True.'],
  ['Bo', LONG_TEXT.slice(0, 200)],
  ['Bo', 'That is not true at all.'],
  ['Ana', 'Di, did you see the sheet yourself or only Bo near it? That matters a lot for the vote today.'],
  ['Cy', 'Skip?'],
  ['Di', 'No, vote Bo.'],
].map(([player, text]) => ({ player_id: player, text }));

// Records what the meeting canvas draws, from its last clearRect on.
function recordMeetingCanvas() {
  const proto = CanvasRenderingContext2D.prototype;
  const fillText = proto.fillText;
  const clearRect = proto.clearRect;
  const moveTo = proto.moveTo;
  const mine = (context) => context.canvas && context.canvas.id === 'classic-meeting-canvas';
  window.__meetingDraw = { texts: [], moves: [] };
  proto.clearRect = function (...args) {
    if (mine(this)) window.__meetingDraw = { texts: [], moves: [] };
    return clearRect.apply(this, args);
  };
  proto.fillText = function (text, x, y, ...rest) {
    if (mine(this)) {
      window.__meetingDraw.texts.push({ text: String(text), x, y, font: this.font, width: this.measureText(text).width });
    }
    return fillText.call(this, text, x, y, ...rest);
  };
  proto.moveTo = function (x, y) {
    if (mine(this)) window.__meetingDraw.moves.push({ x, y });
    return moveTo.call(this, x, y);
  };
}

function players(names) {
  return names.map((name, index) => ({ name, character: CHARACTERS[index % CHARACTERS.length] }));
}

function lobbyState(phase, names) {
  return { type: 'lobby_state', code: 'ABCD', host: OWN, mode: 'classic', phase, players: players(names) };
}

function meeting(reason, living, ghosts, messages, secondsLeft) {
  return {
    type: 'meeting_state', phase: 'discussion', seconds_left: secondsLeft || 40,
    living, ghosts, messages, voted: [], vote_targets: {}, skip_voted: [],
    characters: Object.fromEntries([...living, ...ghosts].map((name, index) => [name, CHARACTERS[index % 4]])),
    reason, trigger_player_id: 'Di', reported_sheet_id: null,
    ejected_id: null, revealed_role: null, tie: false, winner: null,
  };
}

async function openPage(browser, size) {
  const context = await browser.newContext({ viewport: size, deviceScaleFactor: 1 });
  await context.addInitScript(recordMeetingCanvas);
  let server = null;
  await context.routeWebSocket(/\/ws$/, (ws) => {
    server = ws;
    ws.onMessage(() => {});
  });
  const page = await context.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') problems.push(`${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`page error: ${e.message}`));
  await page.goto(base + '/');
  while (server === null) await page.waitForTimeout(20);
  await page.waitForFunction(() => window.Game && window.Game.net && window.Game.net.send({ type: 'probe' }));
  page.receive = async (message) => {
    server.send(JSON.stringify(message));
    await page.waitForTimeout(60);
  };
  page.closeContext = () => context.close();
  return page;
}

async function startClassicRound(page, names) {
  await page.receive({ type: 'signed_in', name: OWN, guest: false });
  await page.receive(lobbyState('lobby', names));
  await page.receive(lobbyState('round', names));
  await page.receive({ type: 'classic_role', role: 'HP', task_stations: [1, 2, 3, 4] });
  await page.waitForTimeout(3100); // the role card closes after 3 seconds
}

// What the last draw put on the canvas, sorted into list, heading and chat.
async function readChat(page, sent) {
  const drawn = await page.evaluate(() => {
    const canvas = document.getElementById('classic-meeting-canvas');
    return { width: canvas.clientWidth, height: canvas.clientHeight, draw: window.__meetingDraw };
  });
  const divider = drawn.draw.moves.length ? drawn.draw.moves[drawn.draw.moves.length - 1].y : null;
  const below = drawn.draw.texts.filter((t) => divider !== null && t.y > divider);
  const above = drawn.draw.texts.filter((t) => divider === null || t.y <= divider);
  const heading = below.find((t) => t.text === 'Discussion chat') || null;
  const messages = [];
  let textX = null;
  below.filter((t) => t !== heading).forEach((t) => {
    if (t.x === 24 && /^(bold|700) 14px/.test(t.font) && t.text.endsWith(':')) {
      messages.push({ name: t.text.slice(0, -1), y: t.y, lines: [] });
    } else if (messages.length) {
      textX = t.x;
      messages[messages.length - 1].lines.push({ text: t.text, y: t.y, width: t.width });
    }
  });
  return {
    canvas: { width: drawn.width, height: drawn.height },
    divider, heading: heading && { y: heading.y }, textX,
    listTexts: above.filter((t) => t.y > 110).map((t) => ({ text: t.text, y: t.y })),
    messages, sent: sent.map((m) => m.player_id + ': ' + m.text),
  };
}

async function shoot(page, name) {
  if (!shotsFolder) return;
  await page.locator('.classic-meeting-window').screenshot({ path: `${shotsFolder}/${name}.png` });
}

async function lookAt(browser, viewportName, seen) {
  const page = await openPage(browser, VIEWPORTS[viewportName]);
  await startClassicRound(page, FIVE);
  // Five players: in a report meeting the reported one (Ed) is dead, in an
  // emergency meeting all five live. Both show the vote buttons during the
  // discussion, so five living players leave a shorter canvas than four.
  for (const reason of ['report', 'emergency']) {
    const living = reason === 'report' ? FIVE.slice(0, 4) : FIVE;
    const ghosts = reason === 'report' ? ['Ed'] : [];
    const show = async (key, living, ghosts, messages, seconds) => {
      await page.receive(meeting(reason, living, ghosts, messages, seconds));
      seen[`${reason} ${key} ${viewportName}`] = await readChat(page, messages);
    };
    await show('short8', living, ghosts, SHORT8);
    await shoot(page, `${reason}_short8_${viewportName}`);
    await show('mixed8', living, ghosts, MIXED8);
    await shoot(page, `${reason}_mixed8_${viewportName}`);
    // The same lists a second later with one more message: the chat stays put.
    await show('mixed9', living, ghosts, MIXED8.concat([{ player_id: 'Bo', text: 'Fine.' }]), 39);
  }
  // The same four vote buttons (so the same canvas), once with lists of one
  // row (short names, one dead) and once with lists of three rows.
  const showRows = async (key, living, ghosts) => {
    await page.receive(meeting('report', living, ghosts, SHORT8));
    seen[`${key} ${viewportName}`] = await readChat(page, SHORT8);
  };
  await showRows('rows1', FIVE.slice(0, 4), ['Ed']);
  await showRows('rows3', LONG_LIVING, LONG_GHOSTS);
  await page.closeContext();
}

async function main() {
  const browser = await chromium.launch();
  const seen = {};
  try {
    for (const name of Object.keys(VIEWPORTS)) await lookAt(browser, name, seen);
  } finally {
    await browser.close();
  }
  process.stdout.write(JSON.stringify({ console: problems, seen }));
}

main().catch((problem) => {
  process.stderr.write(String(problem && problem.stack || problem));
  process.exit(1);
});
