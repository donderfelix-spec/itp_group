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

  let worldIsRunning = false;

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

  function stopWorld() {
    if (!worldIsRunning) return;
    worldIsRunning = false;
    callWorld('stop');
  }

  function whenSignedIn(message) {
    Game.lobby.setOwnName(message.name);
    callWorld('setOwnName', message.name);
    Game.forms.showSignedIn(message.name, message.guest);
  }

  function whenSignedOut() {
    stopWorld();
    Game.forms.showStart();
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

  function whenError(message) {
    Game.forms.stopWaiting(); // Every error is an answer, also one that belongs to no field.
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
    stopWorld();
    Game.forms.showStart();
    Game.screens.showLastingMessage('Connection lost. Reconnecting…', true);
  }

  Game.forms.setup();
  Game.lobby.setup();

  Game.net.on('open', Game.screens.hideMessage);
  Game.net.on('close', whenConnectionLost);
  Game.net.on('signed_in', whenSignedIn);
  Game.net.on('signed_out', whenSignedOut);
  Game.net.on('lobby_state', whenLobbyChanged);
  Game.net.on('left_lobby', whenLeftLobby);
  Game.net.on('positions', whenPositions);
  Game.net.on('notice', (message) => Game.screens.showMessage(message.message, false));
  Game.net.on('error', whenError);

  Game.net.connect();
})();
