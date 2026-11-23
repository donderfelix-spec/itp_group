// S-224: the Players list of the lobby shows a name of 16 letters whole when
// the panel is beside the map (1280x800, 1024x700), with 2 and 8 players, and
// no name runs under a marker ("Host", "You"). Below the map, in a narrow
// window (360x700), the list keeps its two columns. The page's own lobby.js
// draws the list (Game.lobby.show); no round is played.
// Run by tests/test_play_player_names_whole.py with the server's address.
const { chromium } = require('playwright');

const base = process.argv[2];
const NAMES = ['Abcdefghijklm918', 'Zyxwvutsrqpon918', 'Mmmmmmmmmmmmmm18', 'Wilhelmina2026ab',
  'Guestlike12345ab', 'Ophelia9Ramirez1', 'Bartholomew19xyz', 'Q1w2e3r4t5y6u7i8'];
const CHARACTERS = ['consultant', 'finance_bro', 'exchange_student', 'surfer', 'founder', 'overachiever', 'latecomer', 'library_local'];

(async () => {
  const browser = await chromium.launch();
  const problems = [];
  const result = {};
  try {
    for (const [width, height] of [[1280, 800], [1024, 700], [360, 700]]) {
      const page = await browser.newPage({ viewport: { width, height } });
      page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) problems.push(m.text()); });
      page.on('pageerror', (e) => problems.push(e.message));
      await page.goto(base);
      await page.waitForFunction(() => window.Game && Game.lobby && Game.screens);
      for (const count of [2, 8]) {
        result[`${width}x${height} ${count}`] = await page.evaluate(({ names, characters, count }) => {
          const players = names.slice(0, count).map((name, index) => ({ name, character: characters[index] }));
          Game.screens.show('lobby');
          Game.lobby.show({ code: 'ABCD', host: names[0], players, mode: 'duel', phase: 'lobby' });
          const rows = [...document.querySelectorAll('#lobby-players li')];
          const cut = rows.map((row) => row.querySelector('.player-name'))
            .filter((name) => name.scrollWidth > name.clientWidth + 0.5).map((name) => name.textContent);
          const underMarker = rows.some((row) => {
            const name = row.querySelector('.player-name').getBoundingClientRect();
            return [...row.querySelectorAll('.marker')].some((marker) => marker.getBoundingClientRect().left < name.right - 0.5);
          });
          const columns = getComputedStyle(document.getElementById('lobby-players')).gridTemplateColumns.split(' ').length;
          return { rows: rows.length, cut, underMarker, columns };
        }, { names: NAMES, characters: CHARACTERS, count });
      }
      await page.close();
    }
  } finally {
    await browser.close();
  }
  process.stdout.write(JSON.stringify({ problems, result }));
})().catch((error) => {
  process.stderr.write(String(error && error.stack ? error.stack : error));
  process.exit(1);
});
