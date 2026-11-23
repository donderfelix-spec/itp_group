// The role card (DESIGN.md, screen 5): with one Free Rider the line
// "Other Free Riders:" is left out, never "None"; with two each reads the
// other one's name; a High Performer never has the line. Runs the real
// client/js/classic/round.js in Node with a small stand-in for the page.
// Run with: node game/tests/classic_role_card_in_node.js
// (pytest does it in tests/test_classic_role_card.py).
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');

function element() {
  return {
    hidden: false, textContent: '', children: [], style: {},
    appendChild(child) { this.children.push(child); return child; },
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
    addEventListener() {}, setAttribute() {}, querySelector: () => element(),
    classList: { add() {}, remove() {}, toggle() {} },
  };
}

const elements = new Map();
const handlers = new Map();
const Game = { net: { on: (type, handler) => handlers.set(type, handler), send() {} } };
const context = vm.createContext({
  Game, window: { Game, setTimeout: () => 1, clearTimeout() {} }, console,
  document: {
    getElementById: (id) => { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); },
    createElement: () => element(),
  },
});
context.window.Game = Game;
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'client', 'js', 'classic', 'round.js'), 'utf8'), context);
Game.classicRound.setup();
const partners = elements.get('classic-role-partners');
const showRole = handlers.get('classic_role');

let checked = 0;
function check(condition, message) { assert.ok(condition, message); checked += 1; }

// Accepted: two Free Riders name each other.
showRole({ type: 'classic_role', role: 'FR', other_free_riders: ['Tiago'] });
check(partners.textContent === 'Other Free Riders: Tiago' && partners.hidden === false, 'two Free Riders: the other one is named');

// Rejected: one Free Rider gets no "None".
showRole({ type: 'classic_role', role: 'FR', other_free_riders: [] });
check(partners.textContent === '' && partners.hidden === true, 'one Free Rider: the line is left out');
check(!partners.textContent.includes('None'), 'never "None"');

// Edge cases: a High Performer, and a card without the list.
showRole({ type: 'classic_role', role: 'HP' });
check(partners.textContent === '' && partners.hidden === true, 'a High Performer has no such line');
showRole({ type: 'classic_role', role: 'FR' });
check(partners.textContent === '' && partners.hidden === true, 'a Free Rider card without the list: no line');
showRole({ type: 'classic_role', role: 'FR', other_free_riders: ['Tiago'] });
check(partners.hidden === false, 'the line comes back for the next round with two Free Riders');

console.log(`classic_role_card_in_node.js: all ${checked} checks passed`);
