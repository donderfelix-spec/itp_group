// Browser part of test_play_meeting_window_and_end_screen.py (Felix,
// 2026-11-22): the Classic meeting window and the end screen in Chromium.
// Needs Playwright and Chromium.
//
// The page comes from the real server, but its WebSocket is answered by this
// script (Playwright's routeWebSocket): it sends the page the messages a
// server would send (signed_in, lobby_state, meeting_state, classic_result),
// so every vote and every host change happens exactly when wanted.
//
// Usage: node meeting_window_and_end_screen_in_browser.js <base-url> [shots-folder]
// Prints one JSON object:
//   console    every console error or warning and page error
//   viewports  per viewport ("1280x800", "1024x700", "320x640"):
//     votes4, votes8   the boxes of the vote buttons (and of the window, the
//                      chat input and Send) after each step of votes that
//                      arrive, change and are withdrawn, with 4 and with 8
//                      living players (one with a long name), and what the
//                      buttons show (count, label, title, voter icons, whether
//                      the name is cut with "…")
//     fit              for a report discussion with 8 living players (chat,
//                      Skip and votes at once) and for a vote with 8: the
//                      boxes of the window, the input, Send, the Skip row and
//                      every vote button, the viewport, whether the window
//                      scrolls inside and whether the page itself scrolls
//     canvas           the canvas's size on screen and in pixels, and the
//                      device pixel ratio
//     end              the end screen as host, as a non-host and after the
//                      host changed twice while it was open
// With a shots folder it saves vote4_<viewport>.png, vote8_<viewport>.png,
// report8_<viewport>.png, end_host_<viewport>.png and end_guest_<viewport>.png there.
const { chromium } = require('playwright');

const base = process.argv[2];
const shotsFolder = process.argv[3];
const problems = [];

const OWN = 'Ana';
const LONG_NAME = 'Maximilianaaaaaa';
const FOUR = ['Ana', 'Bo', 'Cy', 'Di'];
const EIGHT = ['Ana', 'Bo', 'Cy', 'Di', 'Ed', 'Flo', 'Gus', LONG_NAME];
const CHARACTERS = ['consultant', 'finance_bro', 'surfer', 'founder', 'consultant', 'finance_bro', 'surfer', 'founder'];
const VIEWPORTS = [
  { name: '1280x800', width: 1280, height: 800, scale: 1 },
  { name: '1024x700', width: 1024, height: 700, scale: 2 },
  { name: '320x640', width: 320, height: 640, scale: 1 },
];
// Votes that arrive, change and are withdrawn, one meeting_state each.
const VOTE_STEPS = [
  {},
  { Bo: 'Cy' },
  { Bo: 'Cy', Cy: 'Bo' },
  { Bo: 'Cy', Cy: 'Bo', Ana: 'Cy', Di: 'Cy' },
  { Bo: 'Ana', Cy: 'Bo', Ana: 'Cy', Di: 'Cy' }, // Bo changes
  { Bo: 'Ana', Ana: 'Cy' }, // Cy and Di take theirs back
  {},
];

function players(names) {
  return names.map((name, index) => ({ name, character: CHARACTERS[index] }));
}

function lobbyState(phase, host, names) {
  return { type: 'lobby_state', code: 'ABCD', host, mode: 'classic', phase, players: players(names) };
}

function meetingState(living, voteTargets, changes) {
  return Object.assign({
    type: 'meeting_state', phase: 'voting', seconds_left: 30,
    living, ghosts: [], voted: Object.keys(voteTargets), vote_targets: voteTargets, skip_voted: [],
    messages: [
      { player_id: 'Bo', text: 'I saw Cy near the library.' },
      { player_id: 'Cy', text: 'I was doing my task at the canteen the whole time.' },
      { player_id: 'Ana', text: 'Let us vote.' },
    ],
    characters: Object.fromEntries(living.map((name, index) => [name, CHARACTERS[index]])),
    reason: 'emergency', trigger_player_id: 'Bo', reported_sheet_id: null,
    ejected_id: null, revealed_role: null, tie: false, winner: null,
  }, changes || {});
}

const RESULT = {
  type: 'classic_result', winner: 'HP', reason: 'all_free_riders_eliminated',
  roles: { Ana: 'HP', Bo: 'FR', Cy: 'HP', Di: 'HP' },
  stats: { failures: 1, completed_tasks: 3, meetings: 2 },
};

async function openPage(browser, viewport) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: viewport.scale,
  });
  let server = null;
  await context.routeWebSocket(/\/ws$/, (ws) => {
    server = ws;
    ws.onMessage(() => {}); // the page's own messages need no answer here
  });
  const page = await context.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') problems.push(`${viewport.name} ${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`${viewport.name} page error: ${e.message}`));
  await page.goto(base + '/');
  while (server === null) await page.waitForTimeout(20);
  // Waits until the page's socket is open, so nothing sent is lost.
  await page.waitForFunction(() => window.Game && window.Game.net && window.Game.net.send({ type: 'probe' }));
  page.receive = async (message) => {
    server.send(JSON.stringify(message));
    await page.waitForTimeout(60);
  };
  page.closeContext = () => context.close();
  return page;
}

async function startClassicRound(page, names, host) {
  await page.receive({ type: 'signed_in', name: OWN, guest: false });
  await page.receive(lobbyState('lobby', host, names));
  await page.receive(lobbyState('round', host, names));
  await page.receive({ type: 'classic_role', role: 'HP', task_stations: [1, 2, 3, 4] });
  // The role card closes after 3 seconds.
  await page.waitForTimeout(3100);
}

// The boxes of what must never move, and what each vote button shows.
async function readVotes(page) {
  return page.evaluate(() => {
    const box = (element) => {
      const r = element.getBoundingClientRect();
      return [r.x, r.y, r.width, r.height];
    };
    const buttons = [...document.querySelectorAll('#classic-vote-players > button')];
    return {
      boxes: {
        window: box(document.querySelector('.classic-meeting-window')),
        input: box(document.getElementById('classic-chat-input')),
        send: box(document.getElementById('classic-chat-send')),
        buttons: buttons.map(box),
      },
      buttons: buttons.map((button) => {
        const name = button.querySelector('.classic-vote-name');
        const count = button.querySelector('.classic-vote-count');
        return {
          target: button.dataset.targetId,
          count: count ? count.textContent : null,
          label: button.getAttribute('aria-label'),
          title: button.title,
          voterIcons: button.querySelectorAll('canvas, .classic-voter-icon').length,
          nameCut: name ? name.scrollWidth > name.clientWidth : null,
          nameEllipsis: name ? getComputedStyle(name).textOverflow : null,
          selected: button.classList.contains('classic-vote-player-selected'),
        };
      }),
    };
  });
}

async function playVotes(page, names, shotName) {
  const steps = [];
  for (const targets of VOTE_STEPS) {
    await page.receive(meetingState(names, targets));
    steps.push(Object.assign({ targets }, await readVotes(page)));
    if (shotName && Object.keys(targets).length === 4) await shoot(page, shotName);
  }
  return steps;
}

async function readFit(page) {
  return page.evaluate(() => {
    const box = (element) => {
      const r = element.getBoundingClientRect();
      return { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
    };
    const meetingWindow = document.querySelector('.classic-meeting-window');
    const skip = document.getElementById('classic-skip-options');
    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      window: box(meetingWindow),
      input: box(document.getElementById('classic-chat-input')),
      send: box(document.getElementById('classic-chat-send')),
      skip: skip.hidden ? null : box(skip),
      buttons: [...document.querySelectorAll('#classic-vote-players > button')].map(box),
      windowScrolls: meetingWindow.scrollHeight > meetingWindow.clientHeight + 1,
      pageScrollY: window.scrollY,
    };
  });
}

async function readCanvas(page) {
  return page.evaluate(() => {
    const canvas = document.getElementById('classic-meeting-canvas');
    return {
      clientWidth: canvas.clientWidth, clientHeight: canvas.clientHeight,
      width: canvas.width, height: canvas.height, ratio: window.devicePixelRatio,
    };
  });
}

async function readEnd(page) {
  return page.evaluate(() => {
    const newRound = document.getElementById('classic-new-round');
    const back = document.getElementById('classic-back-lobby');
    const row = back.parentElement.getBoundingClientRect();
    const b = back.getBoundingClientRect();
    return {
      endScreen: !document.getElementById('classic-end-screen').hidden,
      newRoundHidden: newRound.hidden,
      newRoundInLayout: newRound.offsetParent !== null,
      newRoundWidth: newRound.getBoundingClientRect().width,
      hint: document.getElementById('classic-host-hint').textContent,
      // "Back to the lobby" in the middle of its row when alone.
      backCentreOffset: Math.round((b.left + b.width / 2) - (row.left + row.width / 2)),
    };
  });
}

async function shoot(page, name) {
  if (!shotsFolder) return;
  await page.screenshot({ path: `${shotsFolder}/${name}.png` });
}

async function lookAtViewport(browser, viewport) {
  const seen = {};
  // Votes with 4 living players.
  let page = await openPage(browser, viewport);
  await startClassicRound(page, FOUR, OWN);
  seen.votes4 = await playVotes(page, FOUR, `vote4_${viewport.name}`);
  await page.closeContext();

  // Votes with 8 living players, then the fit of the fullest window.
  page = await openPage(browser, viewport);
  await startClassicRound(page, EIGHT, OWN);
  seen.votes8 = await playVotes(page, EIGHT, `vote8_${viewport.name}`);
  seen.fit = {};
  await page.receive(meetingState(EIGHT, { Bo: 'Cy', Cy: 'Bo' }));
  seen.fit.voting8 = await readFit(page);
  seen.canvas = await readCanvas(page);
  await page.receive(meetingState(EIGHT, { Bo: 'Cy' }, { phase: 'discussion', seconds_left: 40, reason: 'report' }));
  seen.fit.report8 = await readFit(page);
  seen.canvasReport = await readCanvas(page);
  await shoot(page, `report8_${viewport.name}`);

  // The end screen: as host, then the host changes twice while it is open.
  await page.receive(RESULT);
  await page.receive(lobbyState('lobby', OWN, EIGHT));
  seen.end = { host: await readEnd(page) };
  await shoot(page, `end_host_${viewport.name}`);
  await page.receive(lobbyState('lobby', 'Bo', EIGHT));
  seen.end.lostHost = await readEnd(page);
  await page.receive(lobbyState('lobby', OWN, EIGHT));
  seen.end.becameHostAgain = await readEnd(page);
  await page.closeContext();

  // The end screen of a player who never was the host.
  page = await openPage(browser, viewport);
  await startClassicRound(page, FOUR, 'Bo');
  await page.receive(RESULT);
  await page.receive(lobbyState('lobby', 'Bo', FOUR));
  seen.end.guest = await readEnd(page);
  await shoot(page, `end_guest_${viewport.name}`);
  await page.closeContext();
  return seen;
}

async function main() {
  const browser = await chromium.launch();
  const viewports = {};
  try {
    for (const viewport of VIEWPORTS) viewports[viewport.name] = await lookAtViewport(browser, viewport);
  } finally {
    await browser.close();
  }
  process.stdout.write(JSON.stringify({ console: problems, viewports }));
}

main().catch((problem) => {
  process.stderr.write(String(problem && problem.stack || problem));
  process.exit(1);
});
