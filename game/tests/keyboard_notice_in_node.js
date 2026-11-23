// Runs looksTouchOnly() and browserSignals() from the page's own
// js/keyboard_notice.js in Node, without a browser, for
// test_keyboard_notice.py (M4-2.2).
//
// Input (stdin): JSON list of cases, each either
//   {"signals": [coarsePointer, noHover, maxTouchPoints]}  -> looksTouchOnly
//   {"window": {"media": {query: matches} | null, "maxTouchPoints": n,
//               "throws": true?}}                         -> both, from a stand-in window
// Output (stdout): JSON list of true/false, one per case.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const NOTICE_JS = path.join(__dirname, '..', 'client', 'js', 'keyboard_notice.js');

// As in a browser, `window` is the global object; without a document the
// script only defines its functions and shows nothing.
const page = {};
page.window = page;
vm.runInNewContext(fs.readFileSync(NOTICE_JS, 'utf8'), page, { filename: NOTICE_JS });
const notice = page.Game.keyboardNotice;

function standInWindow(spec) {
  const win = { navigator: { maxTouchPoints: spec.maxTouchPoints } };
  if (spec.media) {
    win.matchMedia = (query) => {
      if (spec.throws) throw new Error('matchMedia failed');
      return { matches: spec.media[query] === true };
    };
  }
  return win;
}

const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = cases.map((item) => {
  if (item.signals) return notice.looksTouchOnly(...item.signals);
  const signals = notice.browserSignals(standInWindow(item.window));
  return notice.looksTouchOnly(signals.coarsePointer, signals.noHover, signals.maxTouchPoints);
});
process.stdout.write(JSON.stringify(results));
