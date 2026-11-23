/* Bet rules: pot split, exact-score ranking, resolution, entry deadline, debt limit, settlement suggestions.
   Owner: area 3 (resolution and balances). No HTML in this file. */

/* Splits the pot among the winning entries in proportion to their stake.
   Returns { user: change in euros }. Rounding leftovers go to the highest stake. */
function split(b, win) {
  const p = pot(b), ws = win.reduce((a, e) => a + e.s, 0), d = {};
  b.entries.forEach(e => { d[e.u] = -e.s; });
  let rest = p;
  win.forEach(e => { const sh = Math.floor(p * e.s / ws); d[e.u] += sh; rest -= sh; });
  if (rest) d[win.slice().sort((a, c) => c.s - a.s)[0].u] += rest;
  return d;
}

/* Pick bets: everyone on the winning outcome wins. Returns null if nobody backed it. */
function payout(b, w) {
  const win = b.entries.filter(e => e.o === w);
  return win.length ? split(b, win) : null;
}

/* Exact-score bets: the closest tip wins. The right tendency (home win, draw, away win) beats any wrong one;
   within the same tendency the smaller goal distance wins. Equally close tips share the pot. */
function scoreRank(tip, sc) {
  const wrong = Math.sign(tip[0] - tip[1]) === Math.sign(sc[0] - sc[1]) ? 0 : 1;
  return wrong * 1000 + Math.abs(tip[0] - sc[0]) + Math.abs(tip[1] - sc[1]);
}
function scoreWinners(b, sc) {
  const best = Math.min.apply(null, b.entries.map(e => scoreRank(e.tip, sc)));
  return b.entries.filter(e => scoreRank(e.tip, sc) === best);
}
function payoutScore(b, sc) { return split(b, scoreWinners(b, sc)); }

/* Reads a scoreline from two inputs. Returns [home, away] or null if it is not a valid score. */
function parseTip(h, a) {
  const H = Number(h), Aw = Number(a);
  if (h === '' || a === '' || !Number.isInteger(H) || !Number.isInteger(Aw) || H < 0 || Aw < 0 || H > 20 || Aw > 20) return null;
  return [H, Aw];
}

/* Books the result into the group balances. w is an option index (pick) or [home, away] (score).
   Balances of a group always add up to 0. */
function resolve(g, b, w) {
  const score = b.mode === 'score';
  const win = score ? scoreWinners(b, w) : b.entries.filter(e => e.o === w);
  if (score) b.score = w; else b.result = w;
  if (!win.length) { b.status = 'void'; toast('Nobody backed this outcome. Bet void, nothing booked.'); return; }
  const d = split(b, win);
  b.status = 'resolved'; b.deltas = d; b.winners = win.map(e => e.u);
  Object.keys(d).forEach(u => { g.bal[u] = (g.bal[u] || 0) + d[u]; });
  g.ledger.push({ t: 'Bet “' + b.name + '” resolved', d, b: b.id });
  toast('Bet resolved, balances booked.');
}

/* Entry deadline: without an opponent (nobody joined, or everyone on the same side or tip) the bet is closed as not feasible. */
function lock(b) {
  const sides = new Set(b.entries.map(e => b.mode === 'score' ? tipStr(e.tip) : e.o));
  if (sides.size < 2) { b.status = 'infeasible'; toast('No opponent. Bet not feasible and closed.'); }
  else { b.status = 'locked'; toast('Entry deadline reached. Bet locked.'); }
}

/* Stakes a member has in bets that are not resolved yet. */
function pendingStakes(g, u) {
  return g.bets.filter(isActive).reduce((a, b) => a + b.entries.filter(e => e.u === u).reduce((x, e) => x + e.s, 0), 0);
}

/* Debt limit: your balance minus everything you have at stake may not fall below −limit.
   Returns an error message, or null if the stake is fine. A limit of 0 means no limit. */
function limitError(g, stake) {
  if (!g.limit) return null;
  const worst = (g.bal.me || 0) - pendingStakes(g, 'me') - stake;
  return worst < -g.limit ? 'That would take you past this group’s debt limit of ' + eur(g.limit) + '. Settle up first.' : null;
}

/* Fewest payments that bring everyone back to 0. Payments already marked as paid are taken into account. */
function suggestions(g) {
  const bal = Object.assign({}, g.bal);
  g.pay.forEach(p => { bal[p.from] += p.amt; bal[p.to] -= p.amt; });
  const deb = g.members.filter(u => bal[u] < 0).map(u => ({ u, a: -bal[u] })).sort((a, b) => b.a - a.a);
  const cre = g.members.filter(u => bal[u] > 0).map(u => ({ u, a: bal[u] })).sort((a, b) => b.a - a.a);
  const out = []; let i = 0, j = 0;
  while (i < deb.length && j < cre.length) {
    const amt = Math.min(deb[i].a, cre[j].a);
    out.push({ from: deb[i].u, to: cre[j].u, amt });
    deb[i].a -= amt; cre[j].a -= amt;
    if (!deb[i].a) i++; if (!cre[j].a) j++;
  }
  return out;
}
