// The countdown before a round (DESIGN.md, section 4, screen 4, and S-102):
// "Round starts in" and a large number over the map.
//
// The server counts. Its `countdown` message says how many seconds are left;
// between two messages this file only counts the display down by itself.
// The round starts when the server says so (a `lobby_state` with phase
// "round"), never because the display has run out.
//
// main.js uses:
//   Game.countdown.setup()
//   Game.countdown.show(message)     the `countdown` message of the server
//   Game.countdown.noteLobby(state)  every `lobby_state`: is a countdown still running?
//   Game.countdown.reset()           the player left the lobby

window.Game = window.Game || {};

(function () {
  const DISPLAY_TICK_MS = 100;
  // No countdown of the game is this long. A larger number is unreadable news.
  const LONGEST_SECONDS = 60;

  let container = null; // the elements in index.html, looked up in setup()
  let numberText = null;
  let lobbyIsCounting = false; // the last `lobby_state` had phase "countdown"
  let endsAt = null; // when the display reaches zero, on the clock of performance.now()
  let timer = null;

  function setup() {
    container = document.getElementById('countdown');
    numberText = document.getElementById('countdown-number');
  }

  function isCountdown(message) {
    return Number.isInteger(message.seconds) && message.seconds > 0 && message.seconds <= LONGEST_SECONDS;
  }

  // The number stays at 1 until the server starts the round: a 0 would say
  // the round is running when it is not yet.
  function secondsShown() {
    const left = (endsAt - performance.now()) / 1000;
    return Math.max(1, Math.ceil(left));
  }

  function showNumber() {
    numberText.textContent = String(secondsShown());
  }

  function show(message) {
    // Late or unreadable: without a lobby that counts down nothing is shown.
    if (!container || !lobbyIsCounting || !isCountdown(message)) return;
    endsAt = performance.now() + message.seconds * 1000;
    showNumber();
    container.hidden = false;
    if (timer === null) timer = setInterval(showNumber, DISPLAY_TICK_MS);
  }

  function hide() {
    clearInterval(timer);
    timer = null;
    endsAt = null;
    if (container) container.hidden = true;
  }

  // Every `lobby_state` comes through here. Any phase but "countdown" ends
  // the display: the round started, or the countdown was cancelled.
  function noteLobby(lobbyState) {
    lobbyIsCounting = lobbyState.phase === 'countdown';
    if (!lobbyIsCounting) hide();
  }

  function reset() {
    lobbyIsCounting = false;
    hide();
  }

  Game.countdown = { setup: setup, show: show, noteLobby: noteLobby, reset: reset };
})();
