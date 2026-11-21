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
    // Sent for log-ins and for lobby codes alike: `attempts` is the log-in
    // form on the Log in screen and the code field on the Home screen.
    too_many_attempts: 'attempts',
  };

  // The stations with a minigame (station 6 is not in use yet). Must equal
  // the stations of MINIGAMES in server/modes/minigames.py (checked by
  // tests/test_client_stations_in_use.py). Only Classic uses it; M3-3.17
  // will replace it with the player's own task list from the server.
  const STATIONS_IN_USE = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12];
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
  // True from the click on "Leave lobby" until the world starts in the next
  // lobby. The world only stops when the answer `left_lobby` arrives, and
  // until then no `move` may be sent (see sendMove).
  let leaveWasAsked = false;
  // The code of the lobby this player is in, from the last `lobby_state`.
  // null outside a lobby.
  let lobbyCode = null;
  // The code of the lobby the player was in when the connection was lost
  // (S-109). The page joins it once by itself after the next sign-in. It
  // lives in memory only, so reloading the page forgets it.
  let codeToRejoin = null;

  // The map is built by another part of the team and may be missing or
  // unfinished. The page must work without it, so every call goes through here.
  function callWorld(functionName, ...values) {
    if (Game.world && typeof Game.world[functionName] === 'function') {
      Game.world[functionName](...values);
    }
  }

  function sendMove(dx, dy) {
    // On the way out of the lobby: a walking key released now must send
    // nothing. The server may have taken the player out already and would
    // answer "You are not in a lobby." (M2-2.12)
    // world.js still updates its own direction and prediction for about one
    // round trip; harmless, because the world stops at `left_lobby`.
    if (leaveWasAsked) return;
    Game.net.send({ type: 'move', dx: dx, dy: dy });
  }

  // From lobby.js, right after "Leave lobby" has sent `leave_lobby`.
  function whenLeaveWasAsked() {
    leaveWasAsked = true;
  }

  function startWorld() {
    if (worldIsRunning) return;
    worldIsRunning = true;
    leaveWasAsked = false; // a new lobby: walking is sent again
    callWorld('start', document.getElementById('map'), sendMove);
  }

  // Also the end of the round for this player: every way out of a lobby
  // (leaving, logging out, a lost connection) comes through here.
  function stopWorld() {
    Game.minigames.close(); // before the world stops, so its keys are not left paused
    clearClassicLeftovers();
    Game.classicRound.hide();
    Game.duel.reset();
    callTaskNavigation('reset');
    Game.countdown.reset();
    roundIsRunning = false;
    finishedStations = new Set();
    if (!worldIsRunning) return;
    worldIsRunning = false;
    callWorld('stop');
  }

  // What a Classic round leaves in the browser belongs to that round only:
  // the meeting window (and the stop it put on walking), the F-sheets, the
  // time the red button unlocks, and the own Free Rider marker in the world,
  // the lobby list, the meeting and the round's name label. Outside a round
  // none of it may stay, or the lobby and the next round, also a Duel, would
  // show it. The end screen is not part of this: it stays until the next
  // countdown (S-101, see Game.classicRound.setLobby).
  function clearClassicLeftovers() {
    Game.classicMeeting.hide();
    Game.classicRound.resetRoleMarker();
    callWorld('clearClassicRound');
  }

  function openStation(station) {
    Game.net.ask({ type: 'open_station', station: station });
  }

  function requestFail() {
    if (mode === 'classic' && roundIsRunning) Game.net.send({ type: 'fail' });
  }

  function requestReport(sheetId, position) {
    if (mode === 'classic' && roundIsRunning) {
      Game.net.send({ type: 'report', sheet_id: sheetId, position: position });
    }
  }

  function requestEmergency() {
    if (mode === 'classic' && roundIsRunning) Game.net.send({ type: 'emergency' });
  }

  function whenClassicFail(message) {
    if (mode === 'classic' && roundIsRunning) callWorld('addBloodSheet', message);
  }

  function whenClassicFailStatus(message) {
    if (mode === 'classic' && roundIsRunning) callWorld('setFailStatus', message);
  }

  function whenClassicEmergencyStatus(message) {
    if (mode === 'classic' && roundIsRunning) callWorld('setEmergencyStatus', message);
  }

  function whenClassicProgress(message) {
    if (mode === 'classic' && roundIsRunning) callWorld('setEmergencyStatus', message);
  }

  // Which stations glow and can be used: outside a round none. In a Duel
  // only the player's next station, and none once all are done (S-94). In
  // any other round the ones in use that this player has not finished yet.
  function usableStations() {
    if (!roundIsRunning) return [];
    if (hasOneTaskAtATime()) {
      const next = Game.duel.nextStation();
      return next === null ? [] : [next];
    }
    return STATIONS_IN_USE.filter((station) => !finishedStations.has(station));
  }

  function showUsableStations() {
    const stations = usableStations();
    callWorld('setUsableStations', stations);
    // Only Duel and Solo have one next task to point at; in Classic the
    // card and arrow stay away, also when one station is left.
    callTaskNavigation('setTarget', hasOneTaskAtATime() && stations.length === 1 ? stations[0] : null);
  }

  // Duel and Solo give each player one next station at a time.
  function hasOneTaskAtATime() {
    return mode === 'duel' || mode === 'solo';
  }

  // The card and the arrow (minigames/task_navigation.js) show the one
  // station this player has to go to next, or none. Like callWorld.
  function callTaskNavigation(functionName, ...values) {
    if (Game.taskNavigation && typeof Game.taskNavigation[functionName] === 'function') {
      Game.taskNavigation[functionName](...values);
    }
  }

  function noteThePhase(phase) {
    const isRound = phase === 'round';
    if (isRound && !roundIsRunning) { // a new round
      finishedStations = new Set();
      callWorld('startOfRound'); // everybody stands and faces right
    }
    if (!isRound) Game.minigames.close(); // no round, no task
    roundIsRunning = isRound;
  }

  function whenSignedIn(message) {
    Game.lobby.setOwnName(message.name);
    Game.duel.setOwnName(message.name);
    Game.classicMeeting.setOwnName(message.name);
    Game.classicRound.setOwnName(message.name);
    Game.statistics.setOwnName(message.name);
    callWorld('setOwnName', message.name);
    Game.forms.showSignedIn(message.name, message.guest);
    rejoinTheLostLobby(); // after showSignedIn, whose Home screen empties the join field
  }

  // S-109: a player whose connection was lost in a lobby is put back into
  // it after signing in again, without typing the code. There is one try
  // only: the code is forgotten at once. It also goes into the join field,
  // so after a refusal ("This round has already started.") the player can
  // press Join later. The server's answer does the rest, as for a click.
  // `ask` always sends here: net.js stops waiting for an answer before it
  // hands `signed_in` to this handler, and nothing runs in between.
  function rejoinTheLostLobby() {
    if (codeToRejoin === null) return;
    const code = codeToRejoin;
    codeToRejoin = null;
    Game.forms.putCodeInJoinField(code);
    Game.net.ask({ type: 'join_lobby', code: code });
  }

  // Leaving with the button, logging out and being signed in somewhere else
  // are wanted by the player or by the account: none of them may lead to
  // joining the lobby again by itself (S-109).
  function forgetTheLobby() {
    lobbyCode = null;
    codeToRejoin = null;
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
    forgetTheLobby();
    stopWorld();
    Game.forms.showStart();
    if (!wasAsked) Game.screens.showMessage('You were signed in somewhere else.', false);
  }

  const PHASES = ['lobby', 'countdown', 'round'];

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
    lobbyCode = message.code;
    Game.lobby.show(message);
    // Switching screens moves the keyboard focus, so it happens only on
    // entering the lobby and not on every change in it.
    if (Game.screens.current() !== 'lobby') Game.screens.show('lobby');
    callWorld('setPlayers', message.players);
    startWorld(); // After the screen is visible, so the canvas has its size.
    // After the start: a world that stops forgets which stations were usable.
    noteThePhase(message.phase);
    // After noteThePhase, which closes a minigame: the meeting may then let
    // the character walk again (classicMeeting.hide).
    if (message.phase !== 'round') clearClassicLeftovers();
    mode = message.mode;
    Game.duel.noteLobby(message);
    Game.classicRound.setLobby(message);
    Game.countdown.noteLobby(message);
    showUsableStations();
  }

  function whenLeftLobby() {
    forgetTheLobby();
    stopWorld();
    Game.forms.showHome();
  }

  function whenPositions(message) {
    // After leaving a lobby a late message may still arrive. The map is
    // stopped then and must not be handed anything.
    if (worldIsRunning) callWorld('setPositions', message.players);
  }

  function whenClassicRoster(message) {
    if (!message || !Array.isArray(message.players)) return;
    Game.lobby.setPlayers(message.players);
    callWorld('setPlayers', message.players);
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

  // Everybody's progress: the clock of the Duel panel and, from what
  // duel.js could read of it, the "2/3" and the bar in the player list.
  function whenDuelProgress(message) {
    Game.duel.showProgress(message);
    Game.lobby.showProgress(Game.duel.progress());
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
    rememberTheLobbyToRejoin();
    stopWorld();
    Game.forms.showStart();
    Game.screens.showLastingMessage('Connection lost. Reconnecting…', true);
  }

  // S-109: only a player who was in a lobby (in any phase) gets back into it.
  // A connection lost on another screen adds nothing. A code still waiting
  // for its one try is kept: the player has not signed in since, so it is
  // still the last lobby. That happens when a new connection opens and is
  // lost again before the player signs in.
  function rememberTheLobbyToRejoin() {
    if (lobbyCode !== null) codeToRejoin = lobbyCode;
    lobbyCode = null;
  }

  Game.forms.setup(askToLogOut);
  Game.lobby.setup(whenLeaveWasAsked);
  Game.duel.setup();
  Game.classicMeeting.setup();
  Game.classicRound.setup();
  Game.countdown.setup();
  Game.statistics.setup();
  callWorld('setUseHandler', openStation);
  callWorld('setFailHandler', requestFail);
  callWorld('setReportHandler', requestReport);
  callWorld('setEmergencyHandler', requestEmergency);

  Game.net.on('open', Game.screens.hideMessage);
  Game.net.on('close', whenConnectionLost);
  Game.net.on('signed_in', whenSignedIn);
  Game.net.on('signed_out', whenSignedOut);
  Game.net.on('lobby_state', whenLobbyChanged);
  Game.net.on('countdown', Game.countdown.show);
  Game.net.on('left_lobby', whenLeftLobby);
  Game.net.on('positions', whenPositions);
  Game.net.on('classic_roster', whenClassicRoster);
  Game.net.on('station_opened', whenStationOpened);
  Game.net.on('station_closed', Game.minigames.close);
  Game.net.on('station_done', whenStationDone);
  Game.net.on('duel_state', whenDuelState);
  Game.net.on('duel_progress', whenDuelProgress);
  Game.net.on('duel_result', whenDuelResult);
  Game.net.on('classic_fail', whenClassicFail);
  Game.net.on('classic_fail_status', whenClassicFailStatus);
  Game.net.on('classic_emergency_status', whenClassicEmergencyStatus);
  Game.net.on('classic_progress', whenClassicProgress);
  Game.net.on('profile', Game.statistics.showProfile);
  Game.net.on('leaderboard', Game.statistics.showLeaderboard);
  Game.net.on('notice', (message) => Game.screens.showMessage(message.message, false));
  Game.net.on('error', whenError);
  Game.net.on('you_are_fr', () => Game.classicRound.setOwnFreeRider(true));

  Game.net.connect();
})();
