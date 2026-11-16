/* Bet rules: pot split, resolution, entry deadline, settlement suggestions. Owner: area 3 (resolution and balances).
   No HTML in this file. */

/* Returns { user: change in euros } if option w wins, or null if nobody backed w.
   The pot is split among the winners in proportion to their stake; rounding leftovers go to the highest stake. */
function payout(b, w) {
  const p = pot(b), win = b.entries.filter(e => e.o === w), ws = win.reduce((a, e) => a + e.s, 0), d = {};
  if (!ws) return null;
  b.entries.forEach(e => { d[e.u] = -e.s; });
  let rest = p;
  win.forEach(e => { const sh = Math.floor(p * e.s / ws); d[e.u] += sh; rest -= sh; });
  if (rest) d[win.slice().sort((a, c) => c.s - a.s)[0].u] += rest;
  return d;
}

/* Books the result into the group balances. Balances of a group always add up to 0. */
function resolve(g, b, w) {
  const d = payout(b, w);
  b.result = w;
  if (!d) { b.status = 'void'; toast('Nobody backed this outcome. Bet void, nothing booked.'); return; }
  b.status = 'resolved'; b.deltas = d;
  Object.keys(d).forEach(u => { g.bal[u] = (g.bal[u] || 0) + d[u]; });
  g.ledger.push({ t: 'Bet “' + b.name + '” resolved', d });
  toast('Bet resolved, balances booked.');
}

/* Entry deadline: without an opponent (nobody joined, or everyone on one side) the bet is closed as not feasible. */
function lock(b) {
  const sides = new Set(b.entries.map(e => e.o));
  if (sides.size < 2) { b.status = 'infeasible'; toast('No opponent. Bet not feasible and closed.'); }
  else { b.status = 'locked'; toast('Entry deadline reached. Bet locked.'); }
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
