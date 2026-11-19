// The one WebSocket connection to the server.
//
// Other files use it like this:
//   Game.net.on('lobby_state', showLobby);   // run showLobby for every message of that type
//   Game.net.ask({ type: 'create_lobby' });  // an action of the player that the server answers
//   Game.net.send({ type: 'move', ... });    // a message without an answer
//
// Besides the message types of the server there are two events of the
// connection itself: 'open' (connected) and 'close' (connection lost).

window.Game = window.Game || {};

// The function around this file keeps its helpers private: only what is put
// on `Game` at the bottom can be seen by other files.
(function () {
  const FIRST_RETRY_MS = 1000;
  const LONGEST_RETRY_MS = 10000;
  const CONNECTION_EVENTS = ['open', 'close'];
  // Messages the server sends on its own. They answer no action of the player.
  // (The host's "Start game" is answered by the `lobby_state` before `countdown`.)
  const NOT_ANSWERS = ['positions', 'notice', 'countdown'];

  // A Map and not a plain object: a message type like "constructor" would
  // find something in a plain object that is not a list of handlers.
  const handlers = new Map();
  let socket = null;
  let retryDelay = FIRST_RETRY_MS;
  let lossWasTold = false;
  let waitingForAnswer = false;

  function on(type, handler) {
    if (!handlers.has(type)) handlers.set(type, []);
    handlers.get(type).push(handler);
  }

  function tell(type, message) {
    (handlers.get(type) || []).forEach((handler) => {
      try {
        handler(message);
      } catch (problem) {
        // One failing handler must not stop the others or the connection.
        console.error('A handler for "' + type + '" failed:', problem);
      }
    });
  }

  function connect() {
    const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
    socket = new WebSocket(scheme + '//' + location.host + '/ws');
    socket.addEventListener('open', whenOpened);
    socket.addEventListener('message', readMessage);
    socket.addEventListener('close', whenClosed);
  }

  function whenOpened() {
    retryDelay = FIRST_RETRY_MS;
    lossWasTold = false;
    tell('open');
  }

  // Tries again after a pause that doubles each time, so a server that is
  // down is not flooded with attempts.
  function whenClosed() {
    setTimeout(connect, retryDelay);
    retryDelay = Math.min(retryDelay * 2, LONGEST_RETRY_MS);
    waitingForAnswer = false;
    // Every failed attempt to reconnect closes a socket again. The page is
    // told only once per lost connection.
    if (lossWasTold) return;
    lossWasTold = true;
    tell('close');
  }

  function readMessage(event) {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch (problem) {
      return; // Not JSON: nothing we can show.
    }
    if (!message || typeof message.type !== 'string') return;
    // A message must never be able to pretend the connection opened or closed.
    if (CONNECTION_EVENTS.includes(message.type)) return;
    if (!NOT_ANSWERS.includes(message.type)) waitingForAnswer = false;
    tell(message.type, message);
  }

  // Returns false when there is no connection, so the caller knows that no
  // answer will come.
  function send(message) {
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify(message));
    return true;
  }

  // Like `send`, for actions the server answers (log in, create lobby, ...).
  // Until the answer arrives further actions are ignored, so a double click
  // cannot send the same action twice. Returns whether the message was sent.
  function ask(message) {
    if (waitingForAnswer) return false;
    waitingForAnswer = send(message);
    return waitingForAnswer;
  }

  Game.net = { connect: connect, send: send, ask: ask, on: on };
})();
