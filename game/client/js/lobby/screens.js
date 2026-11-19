// Which screen is visible, and the short messages at the top centre.
//
// Every screen is a <section class="screen" id="screen-..."> in index.html.
// Exactly one of them is visible at a time.

window.Game = window.Game || {};

(function () {
  const MESSAGE_VISIBLE_MS = 4000;

  const messageElement = document.getElementById('message');
  let currentScreen = 'start';
  let hideTimer = null;

  function show(name) {
    currentScreen = name;
    document.querySelectorAll('.screen').forEach((screen) => {
      screen.hidden = screen.id !== 'screen-' + name;
    });
    focusFirstControl(name);
  }

  function current() {
    return currentScreen;
  }

  // Puts the keyboard where the player continues, so nobody needs the mouse.
  function focusFirstControl(name) {
    if (name === 'lobby') {
      // In the lobby the keys are for walking. A focused button would react
      // to Enter and Space, so nothing is focused until the player presses Tab.
      if (document.activeElement) document.activeElement.blur();
      return;
    }
    const screen = document.getElementById('screen-' + name);
    const first = screen.querySelector('input, button:not([disabled])');
    if (first) first.focus();
  }

  // A message that disappears by itself. Errors are coral.
  function showMessage(text, isError) {
    putMessage(text, isError);
    hideTimer = setTimeout(hideMessage, MESSAGE_VISIBLE_MS);
  }

  // A message that stays until `hideMessage` is called (connection lost).
  function showLastingMessage(text, isError) {
    putMessage(text, isError);
  }

  function putMessage(text, isError) {
    clearTimeout(hideTimer);
    messageElement.textContent = text;
    messageElement.classList.toggle('message-error', Boolean(isError));
    messageElement.hidden = false;
  }

  function hideMessage() {
    clearTimeout(hideTimer);
    messageElement.hidden = true;
    messageElement.textContent = '';
  }

  Game.screens = {
    show: show,
    current: current,
    showMessage: showMessage,
    showLastingMessage: showLastingMessage,
    hideMessage: hideMessage,
  };
})();
