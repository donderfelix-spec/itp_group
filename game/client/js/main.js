// Starts the page and connects the parts: each message of the server is
// handed to the screen (js/lobby/) and to the map (js/world/) it belongs to.

window.Game = window.Game || {};

(function () {
  // Where the text of an error is shown, by the error's code.
  // Every other error appears at the top centre.
  const ERROR_PLACES = {
    bad_name: 'name',
    name_taken: 'name',
    bad_password: 'password',
    wrong_credentials: 'form',
    accounts_unavailable: 'form',
    no_lobby: 'code',
    lobby_full: 'code',
    // Joining a running round. In the lobby itself there is no code field,
    // so the same error there appears at the top centre.
    round_running: 'code',
    bad_code: 'code',
  };

  // The stations with a minigame (1 to 5; station 6 is not in use yet).
  const STATIONS_IN_USE = [1, 2, 3, 4, 5];
  // Errors after which no task is open on the server, so no window may stay.
  // `task_failed` is in the list because a fault while closing or finishing
  // is answered with this error only: no `station_closed` follows it.
  const ERRORS_THAT_CLOSE_THE_TASK = ['no_task_open', 'not_in_round', 'not_in_lobby', 'not_signed_in', 'task_failed'];

  let worldIsRunning = false;
  let roundIsRunning = false;
  let mode = null; // the lobby's mode, from the last `lobby_state`
  // The stations this player has finished in the running round. The server
  // keeps the real list; this one only decides which stations glow.
  let finishedStations = new Set();
  // True from the moment this browser asked to log out until the server
  // answers. It tells a wanted `signed_out` from one that came unasked.
  let logOutWasAsked = false;

  // The map is built by another part of the team and may be missing or
  // unfinished. The page must work without it, so every call goes through here.
  function callWorld(functionName, ...values) {
    if (Game.world && typeof Game.world[functionName] === 'function') {
      Game.world[functionName](...values);
    }
  }

  function sendMove(dx, dy) {
    Game.net.send({ type: 'move', dx: dx, dy: dy });
  }

  function startWorld() {
    if (worldIsRunning) return;
    worldIsRunning = true;
    callWorld('start', document.getElementById('map'), sendMove);
  }

  // Also the end of the round for this player: every way out of a lobby
  // (leaving, logging out, a lost connection) comes through here.
  function stopWorld() {
    Game.minigames.close(); // before the world stops, so its keys are not left paused
    Game.duel.reset();
    roundIsRunning = false;
    finishedStations = new Set();
    if (!worldIsRunning) return;
    worldIsRunning = false;
    callWorld('stop');
  }

  function openStation(station) {
    Game.net.ask({ type: 'open_station', station: station });
  }

  // Which stations glow and can be used: outside a round none. In a Duel
  // only the player's next station, and none once all are done (S-94). In
  // any other round the ones in use that this player has not finished yet.
  function usableStations() {
    if (!roundIsRunning) return [];
    if (mode === 'duel') {
      const next = Game.duel.nextStation();
      return next === null ? [] : [next];
    }
    return STATIONS_IN_USE.filter((station) => !finishedStations.has(station));
  }

  function showUsableStations() {
    callWorld('setUsableStations', usableStations());
  }

  function noteThePhase(phase) {
    const isRound = phase === 'round';
    if (isRound && !roundIsRunning) finishedStations = new Set(); // a new round
    if (!isRound) Game.minigames.close(); // no round, no task
    roundIsRunning = isRound;
  }

  function whenSignedIn(message) {
    Game.lobby.setOwnName(message.name);
    Game.duel.setOwnName(message.name);
    Game.statistics.setOwnName(message.name);
    callWorld('setOwnName', message.name);
    Game.forms.showSignedIn(message.name, message.guest);
  }

  // The "Log out" button. `ask` sends nothing while another answer is
  // awaited or the connection is down, and then no `signed_out` will come.
  function askToLogOut() {
    if (Game.net.ask({ type: 'log_out' })) logOutWasAsked = true;
  }

  // The server sends `signed_out` without being asked in one case only: the
  // same account logged in on another connection, and this older one was
  // signed out (S-76). So a `signed_out` this browser did not ask for can
  // be explained to the player without the server saying why.
  function whenSignedOut() {
    const wasAsked = logOutWasAsked;
    logOutWasAsked = false;
    stopWorld();
    Game.forms.showStart();
    if (!wasAsked) Game.screens.showMessage('You were signed in somewhere else.', false);
  }

  const PHASES = ['lobby', 'round'];

  // Says whether a `lobby_state` has the parts the page reads from it.
  function isLobbyState(message) {
    const isPlayer = (player) => Boolean(player) && typeof player.name === 'string';
    return typeof message.code === 'string'
      && Array.isArray(message.players)
      && message.players.every(isPlayer)
      && typeof message.mode === 'string'
      && PHASES.includes(message.phase);
  }

  function whenLobbyChanged(message) {
    if (!isLobbyState(message)) return; // Unreadable: keep what is shown.
    Game.lobby.show(message);
    // Switching screens moves the keyboard focus, so it happens only on
    // entering the lobby and not on every change in it.
    if (Game.screens.current() !== 'lobby') Game.screens.show('lobby');
    callWorld('setPlayers', message.players);
    startWorld(); // After the screen is visible, so the canvas has its size.
    // After the start: a world that stops forgets which stations were usable.
    noteThePhase(message.phase);
    mode = message.mode;
    Game.duel.noteLobby(message);
    showUsableStations();
  }

  function whenLeftLobby() {
    stopWorld();
    Game.forms.showHome();
  }

  function whenPositions(message) {
    // After leaving a lobby a late message may still arrive. The map is
    // stopped then and must not be handed anything.
    if (worldIsRunning) callWorld('setPositions', message.players);
  }

  function whenStationOpened(message) {
    const isReadable = Number.isInteger(message.station)
      && typeof message.title === 'string'
      && Boolean(message.content) && typeof message.content === 'object';
    // A late answer after the player left the round opens nothing.
    const canBeShown = isReadable && worldIsRunning && roundIsRunning;
    const wasShown = canBeShown && Game.minigames.open(message.station, message.title, message.content);
    if (!wasShown) closeTaskWithoutWindow();
  }

  // The server has a task open for this player, but the page shows no
  // window for it. The server lets a player with an open task stand still,
  // and without a window there is no × to end that: so the page closes the
  // task itself. `send` and not `ask`: this must not wait behind another action.
  function closeTaskWithoutWindow() {
    Game.net.send({ type: 'close_station' });
  }

  function whenStationDone(message) {
    finishedStations.add(message.station);
    showUsableStations();
    Game.minigames.showDone();
  }

  // The player's own next station in a Duel: only that one glows from now on.
  function whenDuelState(message) {
    Game.duel.showState(message);
    showUsableStations();
  }

  // The round is over. The server has closed an open task already; the
  // window goes too, so the ranking is not hidden behind it.
  function whenDuelResult(message) {
    Game.minigames.close();
    Game.duel.showResult(message);
  }

  function whenError(message) {
    Game.forms.stopWaiting(); // Every error is an answer, also one that belongs to no field.
    logOutWasAsked = false; // The log-out was refused: no `signed_out` follows it.
    if (ERRORS_THAT_CLOSE_THE_TASK.includes(message.code)) Game.minigames.close();
    // "Close your current task first." with no window to close: see above.
    if (message.code === 'task_open' && !Game.minigames.isOpen()) closeTaskWithoutWindow();
    const place = ERROR_PLACES[message.code];
    const shownAtField = Boolean(place) && Game.forms.showError(place, message.message);
    if (!shownAtField) Game.screens.showMessage(message.message, true);
  }

  // Being signed in belongs to the connection (S-78): when it is lost, the
  // player is signed out and starts again at the Start screen. This runs once
  // per lost connection, not for every failed attempt to reconnect, so what
  // the player types while waiting stays. The message stays visible until the
  // connection is back; it is the feedback for every click in that time.
  function whenConnectionLost() {
    logOutWasAsked = false; // The answer to a log-out can no longer arrive.
    stopWorld();
    Game.forms.showStart();
    Game.screens.showLastingMessage('Connection lost. Reconnecting…', true);
  }

  Game.forms.setup(askToLogOut);
  Game.lobby.setup();
  Game.duel.setup();
  Game.statistics.setup();
  callWorld('setUseHandler', openStation);

  Game.net.on('open', Game.screens.hideMessage);
  Game.net.on('close', whenConnectionLost);
  Game.net.on('signed_in', whenSignedIn);
  Game.net.on('signed_out', whenSignedOut);
  Game.net.on('lobby_state', whenLobbyChanged);
  Game.net.on('left_lobby', whenLeftLobby);
  Game.net.on('positions', whenPositions);
  Game.net.on('station_opened', whenStationOpened);
  Game.net.on('station_closed', Game.minigames.close);
  Game.net.on('station_done', whenStationDone);
  Game.net.on('duel_state', whenDuelState);
  Game.net.on('duel_progress', Game.duel.showProgress);
  Game.net.on('duel_result', whenDuelResult);
  Game.net.on('profile', Game.statistics.showProfile);
  Game.net.on('leaderboard', Game.statistics.showLeaderboard);
  Game.net.on('notice', (message) => Game.screens.showMessage(message.message, false));
  Game.net.on('error', whenError);

  Game.net.connect();
})();
