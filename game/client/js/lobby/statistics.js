// The Profile and Leaderboard screens (DESIGN.md, screens 12 and 13).
//
// The page only asks and draws. Who has which numbers, who may see a profile
// and in which order the leaderboard stands is decided by the server (S-40).

window.Game = window.Game || {};

(function () {
  const NO_TIME = '–'; // shown where an account has no Duel time yet
  // The screens from which an answer of the server may open these two. An
  // answer that arrives after the player has moved on (into a lobby, back
  // to Start) is not shown.
  const SCREENS_TO_OPEN_FROM = ['home', 'profile', 'leaderboard'];

  let ownName = null;

  function setup() {
    onClick('home-profile', () => Game.net.ask({ type: 'get_profile' }));
    onClick('home-leaderboard', () => Game.net.ask({ type: 'get_leaderboard' }));
    onClick('profile-back', Game.forms.showHome);
    onClick('leaderboard-back', Game.forms.showHome);
  }

  function onClick(id, action) {
    document.getElementById(id).addEventListener('click', action);
  }

  function setOwnName(name) {
    ownName = name;
  }

  // ---- Texts ----

  // A time like in the Duel ranking: "1:12.4". The Duel's own function is
  // used, so the two can never differ.
  function timeText(seconds) {
    const isTime = typeof seconds === 'number' && Number.isFinite(seconds) && seconds >= 0;
    if (!isTime) return NO_TIME;
    return Game.duel.formatTime(seconds, true);
  }

  function isCount(value) {
    return Number.isInteger(value) && value >= 0;
  }

  // A table cell. textContent, never innerHTML: a name is text from another player.
  function cell(text, className) {
    const made = document.createElement('td');
    if (className) made.className = className;
    made.textContent = text;
    return made;
  }

  function mayOpen() {
    return SCREENS_TO_OPEN_FROM.includes(Game.screens.current());
  }

  // ---- Profile ----

  function isProfile(message) {
    const isMode = (mode) => Boolean(mode)
      && typeof mode.title === 'string' && isCount(mode.rounds) && isCount(mode.wins);
    return typeof message.name === 'string' && Array.isArray(message.modes) && message.modes.every(isMode);
  }

  function modeRow(mode) {
    const row = document.createElement('tr');
    row.appendChild(cell(mode.title));
    row.appendChild(cell(String(mode.rounds), 'stats-number'));
    row.appendChild(cell(String(mode.wins), 'stats-number'));
    return row;
  }

  function showProfile(message) {
    if (!isProfile(message) || !mayOpen()) return; // Unreadable or too late: keep what is shown.
    document.getElementById('profile-name').textContent = message.name;
    document.getElementById('profile-modes').replaceChildren(...message.modes.map(modeRow));
    document.getElementById('profile-best').textContent = timeText(message.best_duel_seconds);
    Game.screens.show('profile');
  }

  // ---- Leaderboard ----

  function isLeaderboard(message) {
    const isPlayer = (player) => Boolean(player)
      && isCount(player.place) && typeof player.name === 'string'
      && isCount(player.classic_wins) && isCount(player.duel_wins);
    return Array.isArray(message.players) && message.players.every(isPlayer);
  }

  function playerRow(player) {
    const row = document.createElement('tr');
    // The player's own row is yellow, like in the Duel ranking.
    if (player.name === ownName) row.className = 'stats-row-own';
    row.appendChild(cell(String(player.place), 'stats-number'));
    const name = cell(player.name, 'stats-name');
    name.title = player.name; // A long name is cut off in a narrow window.
    row.appendChild(name);
    row.appendChild(cell(String(player.classic_wins), 'stats-number'));
    row.appendChild(cell(String(player.duel_wins), 'stats-number'));
    row.appendChild(cell(timeText(player.best_duel_seconds), 'stats-number'));
    return row;
  }

  function showLeaderboard(message) {
    if (!isLeaderboard(message) || !mayOpen()) return;
    const isEmpty = message.players.length === 0;
    document.getElementById('leaderboard-rows').replaceChildren(...message.players.map(playerRow));
    document.getElementById('leaderboard-table').hidden = isEmpty;
    document.getElementById('leaderboard-empty').hidden = !isEmpty;
    Game.screens.show('leaderboard');
  }

  Game.statistics = {
    setup: setup,
    setOwnName: setOwnName,
    showProfile: showProfile,
    showLeaderboard: showLeaderboard,
  };
})();
