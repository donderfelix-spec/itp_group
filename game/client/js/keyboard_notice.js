// The notice for phones and tablets (M4-2.2, S-219). Walking needs W, A, S, D
// or the arrow keys (js/world/world.js), so on a device that most likely has
// no keyboard the page first shows a full-screen notice instead of a game
// nobody can walk in. "Play anyway" closes it for this visit; so does a real
// key press of a walking key, because then a keyboard evidently exists.
// Only the page decides this: the server blocks nothing.

window.Game = window.Game || {};

(function (root) {
  // Remembers "Play anyway" for this visit (until the tab is closed).
  const STORAGE_KEY = 'groupProject.keyboardNoticeClosed';
  const WALKING_KEYS = ['KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'];

  // True when the device most likely has no keyboard: its primary pointer is
  // coarse (a finger) and it cannot hover. A laptop with a touchscreen keeps
  // a fine pointer that hovers, so it is not caught, however many touch
  // points it has. Inputs are the answers of the browser, passed in so a
  // test can choose them: `coarsePointer` and `noHover` are the results of
  // matchMedia('(pointer: coarse)') and matchMedia('(hover: none)'), or
  // null when the browser cannot answer; `maxTouchPoints` is
  // navigator.maxTouchPoints.
  function looksTouchOnly(coarsePointer, noHover, maxTouchPoints) {
    if (coarsePointer !== true || noHover !== true) return false;
    // A coarse pointer without any touch point is an odd report (an old
    // browser or a stylus-only setting): trust it only when touch is there.
    return typeof maxTouchPoints === 'number' && maxTouchPoints > 0;
  }

  // Reads the inputs of looksTouchOnly from a browser window. A missing
  // matchMedia counts as "cannot answer", so the notice stays away.
  function browserSignals(win) {
    const ask = (query) => {
      if (!win || typeof win.matchMedia !== 'function') return null;
      try {
        return win.matchMedia(query).matches === true;
      } catch (error) {
        return null;
      }
    };
    const navigator = win && win.navigator;
    return {
      coarsePointer: ask('(pointer: coarse)'),
      noHover: ask('(hover: none)'),
      maxTouchPoints: navigator ? navigator.maxTouchPoints : undefined,
    };
  }

  // Storage can throw (private mode, blocked site data): then the notice
  // simply closes and shows again on the next load.
  function wasClosedThisVisit(win) {
    try {
      return win.sessionStorage.getItem(STORAGE_KEY) === '1';
    } catch (error) {
      return false;
    }
  }

  function rememberClosed(win) {
    try {
      win.sessionStorage.setItem(STORAGE_KEY, '1');
    } catch (error) {
      // Nothing to do: the notice is closed for this page only.
    }
  }

  function start(win) {
    const doc = win.document;
    const notice = doc.getElementById('keyboard-notice');
    if (!notice || wasClosedThisVisit(win)) return;
    const signals = browserSignals(win);
    if (!looksTouchOnly(signals.coarsePointer, signals.noHover, signals.maxTouchPoints)) return;

    // Everything behind the notice is out of reach for taps, Tab and
    // screen readers while it shows.
    const behind = Array.from(doc.body.children).filter((element) => element !== notice);
    const button = doc.getElementById('keyboard-notice-play');

    function close() {
      if (notice.hidden) return;
      notice.hidden = true;
      behind.forEach((element) => element.removeAttribute('inert'));
      win.removeEventListener('keydown', onKey, true);
      rememberClosed(win);
    }

    // Only a key really pressed counts, not one sent by a script.
    function onKey(event) {
      if (event.isTrusted && WALKING_KEYS.includes(event.code)) close();
    }

    behind.forEach((element) => element.setAttribute('inert', ''));
    notice.hidden = false;
    button.addEventListener('click', close);
    win.addEventListener('keydown', onKey, true);
    button.focus();
  }

  const api = { looksTouchOnly, browserSignals, start, STORAGE_KEY, WALKING_KEYS };
  root.Game.keyboardNotice = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;

  if (root.document && root.document.getElementById) start(root);
})(typeof window !== 'undefined' ? window : globalThis);
