/* Balances, history and "Settle up". Owner: area 3 (resolution and balances). */

function balancesTab(g) {
  const rows = g.members.map(u => {
    const pend = pendingStakes(g, u);
    return '<div class="row"><span class="who">' + avatarUser(u) + '<span class="col"><span>' + esc(nm(u)) + '</span>' + (pend ? '<span class="small mut">' + eur(pend) + ' at stake in running bets</span>' : '') + '</span></span>' +
      '<span class="num ' + cls(g.bal[u] || 0) + '">' + sg(g.bal[u] || 0) + '</span></div>';
  }).join('');
  const entry = l => {
    const inner = '<span>' + esc(l.t) + '</span><div class="chips small">' + Object.keys(l.d).map(u => '<span class="num ' + cls(l.d[u]) + '">' + esc(nm(u)) + ' ' + sg(l.d[u]) + '</span>').join('') + '</div>';
    /* Entries that belong to a bet open that bet. */
    return l.b && g.bets.some(b => b.id === l.b)
      ? '<button class="card" data-a="go" data-v="bet" data-g="' + g.id + '" data-b="' + l.b + '">' + inner + '<span class="small mut">Open bet ›</span></button>'
      : '<div class="card">' + inner + '</div>';
  };
  return '<div class="card list">' + rows + '</div>' +
    (g.limit ? '<p class="small mut">Debt limit in this group: ' + eur(g.limit) + '. Stakes in running bets count towards it.</p>' : '') +
    '<h2>History</h2>' + (g.ledger.length ? g.ledger.slice().reverse().map(entry).join('') : '<p class="mut">Nothing booked yet.</p>');
}

VIEWS.settle = function () {
  const g = grp(), sug = suggestions(g);
  const row = (p, btn) => '<div class="card"><div class="row"><span>' + esc(nm(p.from)) + ' → ' + esc(nm(p.to)) + '</span><span class="num">' + eur(p.amt) + '</span></div>' + btn + '</div>';
  const sugHtml = sug.map((p, i) => row(p, '<div class="btns"><button class="btn ' + (p.from === 'me' || p.to === 'me' ? 'pri' : '') + '" data-a="paid" data-i="' + i + '">' +
    (p.from === 'me' ? 'Mark as paid' : p.to === 'me' ? 'Confirm receipt' : 'Demo: paid and confirmed') + '</button></div>')).join('');
  const pend = g.pay.map(p => row(p, '<span class="small mut">Marked as paid, waiting for ' + esc(nm(p.to)) + ' to confirm.</span><div class="btns"><button class="btn" data-a="payConfirm" data-id="' + p.id + '">Demo: ' + esc(nm(p.to)) + ' confirms</button></div>')).join('');
  return head('Settle up', true) + '<div class="wrap">' +
    '<p class="mut">The app suggests the fewest payments that bring everyone back to €0. You pay outside the app. A balance only changes once the recipient confirms.</p>' +
    (pend ? '<h2>Waiting for confirmation</h2>' + pend : '') +
    '<h2>Suggested payments</h2>' + (sugHtml || '<div class="card"><span class="pos title">All settled</span><span class="small mut">' + (pend ? 'Only confirmations are still pending.' : 'Every balance is at €0.') + '</span></div>') + '</div>';
};

Object.assign(A, {
  paid(d) {
    const g = grp(), p = suggestions(g)[+d.i]; if (!p) return;
    const pay = { id: uid(), from: p.from, to: p.to, amt: p.amt };
    g.pay.push(pay);
    if (p.from === 'me') toast('Marked as paid. ' + nm(p.to) + ' has to confirm.');
    else A.payConfirm({ id: pay.id });
  },
  payConfirm(d) {
    const g = grp(), i = g.pay.findIndex(p => p.id === d.id); if (i < 0) return;
    const p = g.pay.splice(i, 1)[0], dl = {}; dl[p.from] = p.amt; dl[p.to] = -p.amt;
    g.bal[p.from] += p.amt; g.bal[p.to] -= p.amt;
    g.ledger.push({ t: 'Settlement: ' + nm(p.from) + ' paid ' + nm(p.to), d: dl }); toast('Payment confirmed. Balances updated.');
  }
});
