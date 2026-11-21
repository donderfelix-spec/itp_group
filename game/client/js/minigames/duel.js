// What a player sees of a Duel (DESIGN.md, section 6, and S-94).
//
// In the lobby panel, while the round runs: the next station and the clock;
// everybody's progress is shown in the player list (lobby.js, from
// `progress()`). At the end: the ranking, as a card over the map.
//
// The server decides everything. This file only draws what three messages
// say and sends nothing:
//   duel_state     the player's own next station (nobody else's)
//   duel_progress  how many stations everybody has done, and the time left
//   duel_result    the ranking at the end
//
// main.js uses:
//   Game.duel.setOwnName(name)
//   Game.duel.noteLobby(state)     every `lobby_state`: a round began or ended
//   Game.duel.showState(message), showProgress(message), showResult(message)
//   Game.duel.nextStation()        the station that may glow, or null
//   Game.duel.progress()           {players: [{name, done}], total}, or null
//   Game.duel.reset()              the player left the lobby

window.Game = window.Game || {};

(function () {
  const MAP_FILE = 'js/world/campus.json';
  const CLOCK_TICK_MS = 200;
  const DEFAULT_TOTAL = 3;

  let panel = null; // the elements in index.html, looked up in setup()
  let nextText = null;
  let clockText = null;
  let rankingContainer = null;

  let ownName = null;
  let roundIsOn = false; // a Duel is running in the lobby
  // "Duel" or "Solo": the name of the round, for the panel and the ranking.
  // Kept after the round, because `duel_result` can come after its end.
  let roundName = 'Duel';
  let state = null; // the last readable `duel_state` of this round
  let progress = null; // the last readable `duel_progress` of this round
  let total = DEFAULT_TOTAL; // how many stations a route has
  // The clock: the seconds the server last said were left, and when it said so.
  let secondsLeft = null;
  let secondsLeftSince = 0;
  let clockTimer = null;
  // Station id -> "Build the tray (Canteen)", from the map file.
  const stationNames = new Map();

  function setup() {
    panel = document.getElementById('duel-panel');
    nextText = document.getElementById('duel-next');
    clockText = document.getElementById('duel-clock');
    rankingContainer = document.getElementById('duel-ranking');
    loadStationNames();
  }

  function setOwnName(name) {
    ownName = name;
  }

  // ---- Texts ----

  // The one place a time becomes text: "1:12" for the clock, "1:12.4" for a
  // result. Works in tenths of a second, so 59.96 becomes "1:00.0" and never "0:60.0".
  function formatTime(seconds, withTenths) {
    const tenths = Math.max(0, Math.round(seconds * 10));
    const minutes = Math.floor(tenths / 600);
    const tenthsOfMinute = tenths - minutes * 600;
    const wholeSeconds = String(Math.floor(tenthsOfMinute / 10)).padStart(2, '0');
    const text = minutes + ':' + wholeSeconds;
    return withTenths ? text + '.' + (tenthsOfMinute % 10) : text;
  }

  // The names of the stations and rooms stand in the map file, once for the
  // whole game. Until it is loaded (or if it cannot be), a station is
  // shown by its number.
  function loadStationNames() {
    fetch(MAP_FILE)
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error('no map'))))
      .then(rememberStationNames)
      .catch((problem) => console.warn('The station names could not be loaded.', problem));
  }

  function rememberStationNames(campus) {
    const rooms = new Map();
    (Array.isArray(campus.rooms) ? campus.rooms : []).forEach((room) => rooms.set(room.id, room.name));
    (Array.isArray(campus.stations) ? campus.stations : []).forEach((station) => {
      const room = station.room === 'deck' ? 'Main Deck' : rooms.get(station.room);
      const isUsable = Number.isInteger(station.id) && typeof station.name === 'string' && typeof room === 'string';
      if (isUsable) stationNames.set(station.id, station.name + ' (' + room + ')');
    });
    showPanel(); // the names may arrive after the first station
  }

  function stationName(station) {
    return stationNames.get(station) || 'Station ' + station;
  }

  function element(tag, className, text) {
    const made = document.createElement(tag);
    made.className = className;
    if (text !== undefined) made.textContent = text;
    return made;
  }

  // ---- What the messages may look like ----

  function isCount(value) {
    return Number.isInteger(value) && value >= 0;
  }

  function isTime(value) {
    return typeof value === 'number' && Number.isFinite(value) && value >= 0;
  }

  function isState(message) {
    const hasStation = Number.isInteger(message.next_station);
    const isFinished = message.next_station === null && isTime(message.seconds);
    return (hasStation || isFinished) && isCount(message.done) && isCount(message.total);
  }

  function isProgress(message) {
    const isPlayer = (player) => Boolean(player) && typeof player.name === 'string' && isCount(player.done);
    return Array.isArray(message.players) && message.players.every(isPlayer)
      && isCount(message.total) && isTime(message.seconds_left);
  }

  function isResult(message) {
    const isRow = (row) => Boolean(row) && isCount(row.place) && typeof row.name === 'string'
      && (row.seconds === null || isTime(row.seconds)) && isCount(row.done);
    return Array.isArray(message.ranking) && message.ranking.every(isRow) && typeof message.time_up === 'boolean';
  }

  // ---- The panel during the round ----

  function nextLine() {
    if (!state) return '';
    if (state.next_station === null) {
      return 'Finished in ' + formatTime(state.seconds, true) + '. Waiting for the others.';
    }
    return 'Next: ' + stationName(state.next_station);
  }

  // The browser counts down by itself between two messages of the server,
  // from the seconds the server last said, and never below 0:00.
  function showClock() {
    if (secondsLeft === null) {
      clockText.textContent = '';
      return;
    }
    const passed = (performance.now() - secondsLeftSince) / 1000;
    clockText.textContent = formatTime(Math.max(0, Math.ceil(secondsLeft - passed)), false);
  }

  function showPanel() {
    if (!panel) return;
    const hasSomething = roundIsOn && (state !== null || progress !== null);
    panel.hidden = !hasSomething;
    if (!hasSomething) return;
    const heading = document.getElementById('duel-heading');
    if (heading) heading.textContent = roundName;
    nextText.textContent = nextLine();
    nextText.classList.toggle('duel-next-finished', Boolean(state) && state.next_station === null);
    showClock();
  }

  function startClock() {
    if (clockTimer === null) clockTimer = setInterval(showClock, CLOCK_TICK_MS);
  }

  function stopClock() {
    clearInterval(clockTimer);
    clockTimer = null;
  }

  function forgetRound() {
    state = null;
    progress = null;
    secondsLeft = null;
    stopClock();
  }

  // ---- The messages ----

  // Every `lobby_state` comes through here. It says whether a Duel is
  // running: the Duel's own messages follow it at the start, and at the
  // end `duel_result` comes before the state with phase "lobby".
  function noteLobby(lobbyState) {
    const isDuelRound = lobbyState.phase === 'round' && ['duel', 'solo'].includes(lobbyState.mode);
    if (isDuelRound && !roundIsOn) {
      forgetRound(); // a new round: nothing of the old one is left
      hideRanking(); // also for a player who had not clicked it away
    }
    if (!isDuelRound) forgetRound();
    if (isDuelRound) roundName = lobbyState.mode === 'solo' ? 'Solo' : 'Duel';
    roundIsOn = isDuelRound;
    showPanel();
  }

  function showState(message) {
    if (!roundIsOn || !isState(message)) return; // late or unreadable: keep what is shown
    state = message;
    total = message.total;
    showPanel();
  }

  function showProgress(message) {
    if (!roundIsOn || !isProgress(message)) return;
    progress = message;
    total = message.total;
    secondsLeft = message.seconds_left;
    secondsLeftSince = performance.now();
    startClock();
    showPanel();
  }

  function nextStation() {
    return roundIsOn && state ? state.next_station : null;
  }

  // Everybody's progress in this round, for the player list, or null.
  function progressOfPlayers() {
    if (!roundIsOn || !progress) return null;
    return { players: progress.players.map((player) => ({ name: player.name, done: player.done })), total: total };
  }

  // ---- The ranking at the end ----

  function rankingRow(row) {
    const item = element('li', row.name === ownName ? 'duel-row duel-row-own' : 'duel-row');
    const name = element('span', 'duel-row-name', row.name);
    name.title = row.name;
    // A time for a player who finished, otherwise how far the player came.
    const result = row.seconds === null ? row.done + '/' + total : formatTime(row.seconds, true);
    item.append(element('span', 'duel-row-place', row.place + '.'), name, element('span', 'duel-row-result', result));
    return item;
  }

  function showResult(message) {
    if (!rankingContainer || !isResult(message)) return;
    hideRanking(); // never two cards
    const card = element('section', 'duel-card');
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-labelledby', 'duel-ranking-title');
    const heading = element('h2', 'duel-title', roundName + ' ranking');
    heading.id = 'duel-ranking-title';
    card.append(heading);
    if (message.time_up) card.append(element('p', 'duel-time-up', 'Time is up.'));
    const rows = element('ol', 'duel-rows');
    message.ranking.forEach((row) => rows.append(rankingRow(row)));
    const back = element('button', 'button button-main', 'Back to lobby');
    back.type = 'button';
    // The lobby is open again underneath: the button only takes the card away.
    back.addEventListener('click', hideRanking);
    card.append(rows, back);
    rankingContainer.append(card);
    rankingContainer.hidden = false;
    document.addEventListener('keydown', onKeyDown);
    back.focus();
  }

  function onKeyDown(event) {
    if (event.key === 'Escape') {
      event.preventDefault();
      hideRanking();
    }
  }

  function hideRanking() {
    if (!rankingContainer || rankingContainer.hidden) return;
    document.removeEventListener('keydown', onKeyDown);
    // The focus goes back to the page, so the walking keys work at once.
    const focused = document.activeElement;
    if (focused && rankingContainer.contains(focused)) focused.blur();
    rankingContainer.hidden = true;
    rankingContainer.replaceChildren();
  }

  // The player left the lobby: nothing of its Duel stays on the page.
  function reset() {
    roundIsOn = false;
    forgetRound();
    hideRanking();
    showPanel();
  }

  Game.duel = {
    setup: setup,
    setOwnName: setOwnName,
    noteLobby: noteLobby,
    showState: showState,
    showProgress: showProgress,
    showResult: showResult,
    nextStation: nextStation,
    progress: progressOfPlayers,
    reset: reset,
    formatTime: formatTime,
  };
})();
