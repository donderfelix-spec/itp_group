/* Flow tests for the prototype. Runs after all prototype scripts are loaded (see tests/run.js).
   Each check() names a rule from the workflow; a failed check fails the CI run.
   Add a check here whenever you change a rule in logic.js or add a flow. */

var __fail = [], __count = 0;
function check(name, got, want) {
  __count++;
  var g = JSON.stringify(got), w = JSON.stringify(want);
  if (g !== w) __fail.push(name + ': expected ' + w + ', got ' + g);
}
/* Triggers an action the way a click on data-a="name" would, then redraws. */
var act = function (a, d) { A[a](d || {}); render(); };
var page = function () { return __els.app.innerHTML; };
var toastText = function () { return __els.toast.textContent; };
var sum = function (g) { return Object.keys(g.bal).reduce(function (a, u) { return a + g.bal[u]; }, 0); };
var g1 = db.groups[0];

/* --- Every screen renders --- */
render();
check('start screen lists groups', page().indexOf('Your groups') > -1, true);
act('go', { v: 'profile' }); check('profile renders', page().indexOf('Log out') > -1, true); act('back');
act('go', { v: 'group', g: 'g1' });
ui.tab = 'bal'; render(); check('balances tab shows stakes in running bets', page().indexOf('at stake in running bets') > -1, true);
ui.tab = 'bets'; render();
['b0', 'b1', 'b2', 'b3', 'b4'].forEach(function (id) { act('go', { v: 'bet', g: 'g1', b: id }); act('back'); });
act('go', { v: 'settle', g: 'g1' }); act('back');
act('go', { v: 'admin', g: 'g1' }); check('admin area renders for the admin', page().indexOf('Danger zone') > -1, true); act('back');

/* --- Pot split --- */
check('pot is split in proportion to the stake',
  payout({ entries: [{ u: 'a', o: 0, s: 100 }, { u: 'b', o: 0, s: 50 }, { u: 'c', o: 1, s: 150 }] }, 0), { a: 100, b: 50, c: -150 });
check('rounding leftover goes to the highest stake',
  payout({ entries: [{ u: 'a', o: 1, s: 30 }, { u: 'b', o: 1, s: 33 }, { u: 'c', o: 0, s: 50 }] }, 1), { a: 23, b: 27, c: -50 });
check('nobody backed the winning outcome', payout({ entries: [{ u: 'a', o: 0, s: 10 }, { u: 'b', o: 1, s: 10 }] }, 2), null);

/* --- Exact score: closest tip wins --- */
var tips = { entries: [{ u: 'a', tip: [2, 1], s: 10 }, { u: 'b', tip: [1, 1], s: 10 }, { u: 'c', tip: [0, 2], s: 10 }] };
var winners = function (sc) { return scoreWinners(tips, sc).map(function (e) { return e.u; }); };
check('exact tip wins', winners([2, 1]), ['a']);
check('right tendency beats a closer wrong one', winners([1, 0]), ['a']);
check('draw tip wins a draw', winners([0, 0]), ['b']);
check('equally close tips share the pot',
  payoutScore({ entries: [{ u: 'a', tip: [1, 0], s: 10 }, { u: 'b', tip: [3, 2], s: 10 }, { u: 'c', tip: [0, 1], s: 10 }] }, [2, 1]), { a: 5, b: 5, c: -10 });
check('scoreline needs two whole numbers', [parseTip('2', '1'), parseTip('2', ''), parseTip('1.5', '0'), parseTip('-1', '0')], [[2, 1], null, null, null]);

/* --- Debt limit --- */
g1.limit = 60;   /* balance 50, already 40 + 20 at stake */
act('go', { v: 'bet', g: 'g1', b: 'b1' });
ui.join.o = 1; ui.join.s = '51'; act('join');
check('stake past the debt limit is refused', mine(bet()) === undefined, true);
ui.join.s = '50'; act('join');
check('stake up to the debt limit is accepted', mine(bet()).s, 50);
act('withdraw'); check('withdrawing removes the stake', mine(bet()) === undefined, true);
act('back'); g1.limit = 500;

/* --- Exact score bet from joining to resolution --- */
act('go', { v: 'bet', g: 'g1', b: 'b4' });
ui.join.h = '3'; ui.join.a = '1'; ui.join.s = '30'; act('join');
act('lock'); check('bet with different tips gets locked', bet().status, 'locked');
ui.res.h = '4'; ui.res.a = '1'; act('resultScore');
check('closest tip takes the pot', bet().deltas, { clara: -20, anna: -20, me: 40 });
check('balances add up to 0 after a score bet', sum(g1), 0);
act('back');

/* --- Real-life bet: three outcomes, proof, report, dispute, vote --- */
act('newBet'); ui.draft.name = 'Who cleans first?'; act('addOut'); ui.draft.outs = ['Anna', 'Ben', ''];
act('createBet'); check('empty outcome is refused', cur().v, 'newBet');
ui.draft.outs[2] = 'Clara'; ui.draft.proof = 'photo'; ui.draft.side = 2; act('createBet');
check('bet is created open', [bet().status, bet().opts.length, bet().proof], ['open', 3, 'photo']);
act('demoJoin'); act('demoJoin'); act('lock'); act('propose', { i: 2 });
check('reported result waits for confirmation', bet().status, 'resolving');
check('agreed proof is shown when confirming', page().indexOf('Agreed proof: Photo proof') > -1, true);
act('dispute'); check('dispute opens a vote', bet().status, 'disputed');
act('result', { i: 2 }); check('majority resolves the bet', bet().status, 'resolved');
check('balances add up to 0 after a real-life bet', sum(g1), 0);
act('back');

/* --- No opponent --- */
act('newBet'); ui.draft.name = 'Nobody joins'; act('createBet'); act('lock');
check('bet nobody joined is not feasible', bet().status, 'infeasible');
act('back');
act('newBet'); act('type', { t: 'event' }); act('mode', { t: 'score' }); ui.draft.name = 'Same tip'; ui.draft.th = '1'; ui.draft.ta = '0'; act('createBet');
bet().entries.push({ u: 'anna', tip: [1, 0], s: 10 }); act('lock');
check('everyone on the same tip is not feasible', bet().status, 'infeasible');
act('back');
act('newBet'); act('type', { t: 'event' }); act('mode', { t: 'score' }); ui.draft.ev = 2; render();
check('event without a scoreline has no exact-score mode', ui.draft.mode, 'pick');
act('back');

/* --- Settle up --- */
act('go', { v: 'bet', g: 'g1', b: 'b3' }); act('confirm'); act('back');
act('go', { v: 'settle', g: 'g1' });
var guard = 0;
while (suggestions(g1).length && guard++ < 20) { act('paid', { i: 0 }); if (g1.pay.length) act('payConfirm', { id: g1.pay[0].id }); }
check('settling up brings everyone to 0', g1.members.every(function (u) { return g1.bal[u] === 0; }), true);
act('back'); act('back');

/* --- Join and leave a group --- */
act('go', { v: 'joinGroup' }); ui.jcode = 'nope'; act('joinGroup');
check('unknown invite code is refused', cur().v, 'joinGroup');
ui.jcode = ' kick-3305 '; act('joinGroup');
var joined = grp();
check('joining adds you as a member', joined.members.indexOf('me') > -1, true);
check('non-admin sees "Leave group" instead of the admin area', [page().indexOf('Leave group') > -1, page().indexOf('Admin area') > -1], [true, false]);
act('go', { v: 'admin', g: joined.id }); check('admin area is closed to non-admins', page().indexOf('Only the group admin') > -1, true); act('back');
act('go', { v: 'bet', g: joined.id, b: 'k1' }); ui.join.o = 0; ui.join.s = '10'; act('join'); act('back');
act('leave'); check('cannot leave with a stake in a running bet', db.groups.indexOf(joined) > -1, true);
act('go', { v: 'bet', g: joined.id, b: 'k1' }); act('withdraw'); act('back');
act('leave'); check('can leave once nothing is at stake', db.groups.indexOf(joined), -1);

/* --- Solo group, admin, delete --- */
act('go', { v: 'newGroup' }); ui.gdraft.name = 'Solo'; act('createGroup');
check('alone in a group, creating a bet is disabled', page().indexOf('data-a="newBet" aria-label="Create bet" title="Create bet" disabled') > -1, true);
var before = db.groups.length;
act('go', { v: 'admin', g: grp().id }); act('askDelete'); act('deleteGroup');
check('empty group can be deleted', db.groups.length, before - 1);
act('go', { v: 'admin', g: 'g1' }); act('askDelete'); act('deleteGroup');
check('group with running bets cannot be deleted', db.groups.indexOf(g1) > -1, true);
act('back');

/* --- Log out and back in --- */
act('logout'); check('logged out shows only the login screen', page().indexOf('You are logged out') > -1, true);
act('login'); check('logging in returns to the groups', page().indexOf('Your groups') > -1, true);

if (__fail.length) throw new Error(__fail.length + ' of ' + __count + ' checks failed:\n- ' + __fail.join('\n- '));
'All ' + __count + ' checks passed.';
