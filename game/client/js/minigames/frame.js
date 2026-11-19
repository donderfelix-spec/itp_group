// The window every minigame is played in, and the list of minigames.
//
// The server decides when a station opens and sends the content of its
// minigame (S-93). This file shows the window over the map with the header
// all minigames share (title, one sentence of instructions, close button),
// and tells the server when the player closes it or has solved it.
//
// How to add a minigame: one new file in this folder, loaded with its own
// <script> tag in index.html after this file, that registers itself:
//
//   Game.minigames.register('sort_slides', {
//     instructions: 'Drag the slides into the right order.',
//     start: function (body, content, done) {
//       // Build the minigame inside the element `body`, from `content`
//       // (what the server drew for it). Use createElement and textContent,
//       // never innerHTML. Call done() once, when the player has solved it.
//       // Optional: return a function that stops timers when the window closes.
//     },
//   });
//
// 'sort_slides' is the "kind" in the content the server's part of the
// minigame draws (server/modes/minigames.py says how to add that part).
//
// main.js uses the rest:
//   Game.minigames.open(station, title, content)   the server opened a station;
//                                                  false if no window could be shown
//   Game.minigames.showDone()                      the server counted the task
//   Game.minigames.close()                         take the window away now
//   Game.minigames.isOpen()

window.Game = window.Game || {};

(function () {
  const DONE_TEXT = 'Done';
  const CLOSE_LABEL = 'Close';
  const DONE_VISIBLE_MS = 1000;
  const FALLBACK_KIND = 'placeholder';
  const DONE_RETRY_MS = 250;
  // What Tab can reach inside the window. Switched-off controls and those
  // taken out of the Tab order (tabindex -1) are left out.
  const FOCUSABLE = 'button, input, select, textarea, a[href], [tabindex]';

  // A Map and not a plain object, for the same reason as in net.js: a kind
  // like "constructor" must not find something that is no minigame.
  const minigames = new Map();

  let container = null; // the element in index.html the window is built in
  let cleanUp = null; // what the running minigame returned from start(), if a function
  let isOpenNow = false;
  let isSolved = false; // the open minigame called done()
  let doneWasSent = false; // `finish_station` went to the server; never twice per opening
  let doneRetryTimer = null;
  let isShowingDone = false; // "Done" is on show: the task is over, nothing is left to close
  let doneTimer = null;
  // Counts the openings. A minigame that calls done() after its window was
  // closed belongs to an older opening and is ignored.
  let opening = 0;

  function register(kind, minigame) {
    const isUsable = typeof kind === 'string' && Boolean(minigame) && typeof minigame.start === 'function';
    if (isUsable) minigames.set(kind, minigame);
  }

  // The minigame for this content. A kind nobody registered (a minigame that
  // is not built yet, or a file that failed to load) shows the placeholder.
  function minigameFor(content) {
    const kind = content && typeof content.kind === 'string' ? content.kind : FALLBACK_KIND;
    return minigames.get(kind) || minigames.get(FALLBACK_KIND);
  }

  function element(tag, className, text) {
    const made = document.createElement(tag);
    made.className = className;
    if (text !== undefined) made.textContent = text;
    return made;
  }

  // The header every minigame has: title and close button, then the sentence.
  function buildWindow(title, instructions) {
    const card = element('section', 'minigame-window');
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-labelledby', 'minigame-title');
    card.tabIndex = -1; // can take the focus, so the keys leave the lobby panel

    const header = element('header', 'minigame-header');
    const heading = element('h2', 'minigame-title', title);
    heading.id = 'minigame-title';
    const closeButton = element('button', 'button minigame-close', '×');
    closeButton.type = 'button';
    closeButton.setAttribute('aria-label', CLOSE_LABEL);
    closeButton.addEventListener('click', askToClose);
    header.append(heading, closeButton);

    const body = element('div', 'minigame-body');
    card.append(header, element('p', 'minigame-instructions', instructions), body);
    return { card: card, body: body };
  }

  function pauseWorld(paused) {
    if (Game.world && typeof Game.world.setInputPaused === 'function') {
      Game.world.setInputPaused(paused);
    }
  }

  // Shows the window for a station the server has just opened. Returns
  // whether a window is shown now: if not, main.js has to tell the server,
  // which otherwise keeps the task open and the player standing still.
  function open(station, title, content) {
    container = container || document.getElementById('minigame');
    close(); // never two windows
    const minigame = minigameFor(content);
    if (!container || !minigame) return false;

    const parts = buildWindow(String(title), String(minigame.instructions || ''));
    container.append(parts.card);
    container.hidden = false;
    isOpenNow = true;
    isSolved = false;
    doneWasSent = false;
    isShowingDone = false;
    opening += 1;
    pauseWorld(true);
    document.addEventListener('keydown', onKeyDown);
    parts.card.focus();
    startMinigame(minigame, parts.body, content, opening);
    return true;
  }

  function startMinigame(minigame, body, content, thisOpening) {
    const done = () => reportDone(thisOpening);
    try {
      const returned = minigame.start(body, content, done);
      cleanUp = typeof returned === 'function' ? returned : null;
    } catch (problem) {
      // A broken minigame must not break the page. The window stays, and
      // the player can still close it.
      console.error('A minigame could not start:', problem);
    }
  }

  // The minigame says the player solved it. The server decides whether it
  // counts: `station_done` or an error and `station_closed` come back.
  //
  // `Game.net.ask` sends nothing while there is no connection or another
  // action still waits for its answer. A minigame calls done() only once
  // and switches itself off after that, so a "done" that was not sent
  // would be lost: the solved window would stay open for good. That is
  // why the frame remembers that it is solved and tries again until the
  // message was sent once.
  function reportDone(thisOpening) {
    if (!isOpenNow || thisOpening !== opening || isSolved) return;
    isSolved = true;
    sendDone();
    if (!doneWasSent) doneRetryTimer = setInterval(sendDone, DONE_RETRY_MS);
  }

  function sendDone() {
    if (!isOpenNow || doneWasSent) return;
    doneWasSent = Game.net.ask({ type: 'finish_station' });
    if (doneWasSent) stopRetryingDone();
  }

  function stopRetryingDone() {
    clearInterval(doneRetryTimer);
    doneRetryTimer = null;
  }

  // The player wants to close: × or Esc. The window stays until the server
  // answers `station_closed`, so page and server never disagree.
  function askToClose() {
    if (isOpenNow && !isShowingDone) Game.net.ask({ type: 'close_station' });
  }

  function onKeyDown(event) {
    if (event.key === 'Escape') {
      event.preventDefault();
      askToClose();
    }
    if (event.key === 'Tab') {
      event.preventDefault();
      moveFocusInside(event.shiftKey ? -1 : 1);
    }
  }

  // The controls inside the window that Tab stops at, in the order of the page.
  function focusableInside(card) {
    return Array.from(card.querySelectorAll(FOCUSABLE)).filter((control) => {
      const isHidden = control.hidden || control.getClientRects().length === 0;
      return !control.disabled && control.tabIndex >= 0 && !isHidden;
    });
  }

  // Tab and Shift+Tab go round inside the window. Left to the browser, Tab
  // would walk on into the lobby panel, where Space on "Leave lobby" leaves
  // the lobby by accident. `step` is 1 for Tab and -1 for Shift+Tab.
  function moveFocusInside(step) {
    const card = container.querySelector('.minigame-window');
    const controls = focusableInside(card);
    if (controls.length === 0) {
      card.focus(); // nothing to stop at: the window itself keeps the focus
      return;
    }
    const current = controls.indexOf(document.activeElement);
    // From outside the list (the window itself, or the lobby panel after a
    // click there) Tab goes to the first control and Shift+Tab to the last.
    const start = current === -1 && step === -1 ? 0 : current;
    const next = (start + step + controls.length) % controls.length;
    controls[next].focus();
  }

  // The focus goes back to the page, not to a button of the lobby panel.
  // Only if it is inside the window: a focus elsewhere is left alone.
  function giveFocusBack() {
    const focused = document.activeElement;
    if (focused && container.contains(focused)) focused.blur();
  }

  // "Done" in green for a moment, then the window closes by itself.
  function showDone() {
    if (!isOpenNow || isShowingDone) return;
    isShowingDone = true;
    stopMinigame();
    const card = container.querySelector('.minigame-window');
    card.querySelector('.minigame-body').remove();
    card.querySelector('.minigame-instructions').remove();
    card.querySelector('.minigame-close').disabled = true;
    const doneText = element('p', 'minigame-done', DONE_TEXT);
    doneText.setAttribute('role', 'status');
    card.append(doneText);
    clearTimeout(doneTimer);
    doneTimer = setTimeout(close, DONE_VISIBLE_MS);
  }

  function stopMinigame() {
    const stop = cleanUp;
    cleanUp = null;
    if (!stop) return;
    try {
      stop();
    } catch (problem) {
      console.error('A minigame could not clean up:', problem);
    }
  }

  // Takes the window away at once. Asks nobody: main.js calls this when the
  // server closed the task, the player left or the connection is lost.
  function close() {
    if (!isOpenNow) return;
    isOpenNow = false;
    clearTimeout(doneTimer);
    stopRetryingDone();
    stopMinigame();
    document.removeEventListener('keydown', onKeyDown);
    giveFocusBack();
    container.hidden = true;
    container.replaceChildren();
    pauseWorld(false);
  }

  function isOpen() {
    return isOpenNow;
  }

  // The stand-in for every minigame that is not built yet (DESIGN.md, section 8).
  register(FALLBACK_KIND, {
    instructions: 'This task is still being built.',
    start: function (body, content, done) {
      const button = element('button', 'button button-main', 'Finish task');
      button.type = 'button';
      button.addEventListener('click', done);
      body.append(button);
    },
  });

  Game.minigames = {
    register: register,
    open: open,
    showDone: showDone,
    close: close,
    isOpen: isOpen,
  };
})();
