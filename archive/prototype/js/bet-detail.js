/* Bet detail: header, pot, sides or tips, and everything up to the entry deadline (join, withdraw, cancel).
   Owner: area 2 (creating and joining bets). From "locked" onwards see bet-resolve.js (area 3). */

/* Your own stake and what you would win with the current pot. */
function positionCard(b) {
  const m = mine(b);
  if (!m) return '';
  const score = b.mode === 'score', d = score ? payoutScore(b, m.tip) : payout(b, m.o);
  return '<div class="card"><div class="row"><span>You bet ' + eur(m.s) + ' on “' + esc(entryLabel(b, m)) + '”</span><span class="num pos">' + (d ? sg(d.me) : '') + '</span></div>' +
    '<span class="small mut">' + (score ? 'Possible win if your tip is exactly right, with the current pot.' : 'Possible win with the current pot.') + ' Your balance only changes when the bet is resolved.</span></div>';
}

/* Pick bets: one block per outcome with everyone who backs it. */
function sidesBlock(b) {
  const p = pot(b), won = i => b.status === 'resolved' && b.result === i;
  return b.opts.map((o, i) => {
    const es = b.entries.filter(e => e.o === i), sum = es.reduce((a, e) => a + e.s, 0);
    return '<div class="opt' + (won(i) ? ' win' : '') + '"><div class="row"><span class="title">' + esc(o) + (won(i) ? ' ✓' : '') + '</span><span class="num">' + eur(sum) + '</span></div>' +
      '<div class="bar"><i style="width:' + (p ? Math.round(sum / p * 100) : 0) + '%"></i></div>' +
      '<span class="small mut">' + (es.length ? es.map(e => esc(nm(e.u)) + ' ' + eur(e.s)).join(' · ') : 'nobody yet') + '</span></div>';
  }).join('');
}

/* Exact-score bets: one block per tipped scoreline. */
function tipsBlock(b) {
  const p = pot(b), groups = {};
  b.entries.forEach(e => { (groups[tipStr(e.tip)] = groups[tipStr(e.tip)] || []).push(e); });
  return '<span class="small mut">' + esc(b.opts[0]) + ' : ' + esc(b.opts[b.opts.length - 1]) + '</span>' + Object.keys(groups).map(k => {
    const es = groups[k], sum = es.reduce((a, e) => a + e.s, 0), won = b.status === 'resolved' && es.some(e => (b.winners || []).includes(e.u));
    return '<div class="opt' + (won ? ' win' : '') + '"><div class="row"><span class="title">' + esc(k) + (won ? ' ✓' : '') + '</span><span class="num">' + eur(sum) + '</span></div>' +
      '<div class="bar"><i style="width:' + (p ? Math.round(sum / p * 100) : 0) + '%"></i></div>' +
      '<span class="small mut">' + es.map(e => esc(nm(e.u)) + ' ' + eur(e.s)).join(' · ') + '</span></div>';
  }).join('');
}

/* Returns { info, act, demo } HTML blocks for an open bet. */
function openBlock(b) {
  const m = mine(b), score = b.mode === 'score';
  let act;
  if (!m) {
    const choose = score
      ? '<div class="score"><label>' + esc(b.opts[0]) + '<input id="j-h" type="number" inputmode="numeric" min="0" max="20" data-m="join.h" value="' + esc(ui.join.h) + '"></label><b>:</b>' +
        '<label>' + esc(b.opts[b.opts.length - 1]) + '<input id="j-a" type="number" inputmode="numeric" min="0" max="20" data-m="join.a" value="' + esc(ui.join.a) + '"></label></div>'
      : '<div class="chips">' + b.opts.map((o, i) => '<button class="chip" data-a="pick" data-i="' + i + '" aria-pressed="' + (ui.join.o === i) + '">' + esc(o) + '</button>').join('') + '</div>';
    act = '<h2>' + (score ? 'Join with your tip' : 'Join') + '</h2>' + choose +
      '<label>Your stake (' + eur(b.min) + ' to ' + eur(b.max) + ')<input id="j-stake" type="number" inputmode="numeric" data-m="join.s" value="' + esc(ui.join.s) + '" min="' + b.min + '" max="' + b.max + '"></label>' +
      '<div class="btns"><button class="btn pri" data-a="join">Join bet</button></div>';
  } else if (b.creator === 'me') {
    act = '<div class="btns"><button class="btn danger" data-a="cancel">Cancel bet</button></div><p class="small mut">You can only cancel while the bet is open. It can no longer be edited once someone has joined.</p>';
  } else {
    act = '<div class="btns"><button class="btn danger" data-a="withdraw">Withdraw stake</button></div>';
  }
  const demo = '<span class="small mut">The prototype has no running clock and no other users.</span><div class="btns"><button class="btn" data-a="demoJoin">Example member joins</button><button class="btn" data-a="lock">Entry deadline now</button></div>';
  return { info: positionCard(b), act, demo };
}

VIEWS.bet = function () {
  const b = bet(), score = b.mode === 'score';
  const when = b.type === 'event'
    ? '<dt>Event</dt><dd>' + esc(b.event) + '</dd><dt>Bet on</dt><dd>' + (score ? 'Exact score, closest tip wins' : 'Winner') + '</dd><dt>Entries close</dt><dd>At event start</dd>'
    : '<dt>Deadline</dt><dd>' + esc(fdate(b.deadline)) + '</dd><dt>Entries close</dt><dd>' + esc(fdate(new Date(new Date(b.deadline).getTime() - 864e5).toISOString())) + '</dd>' +
      '<dt>Proof</dt><dd>' + esc(PROOFS[b.proof] || PROOFS.participants) + '</dd>';
  const blk = b.status === 'open' ? openBlock(b) : resolveBlock(b);
  return head('Bet', true) + '<div class="wrap">' +
    '<div class="row"><span class="tag">' + (b.type === 'event' ? 'Event bet' : 'Real-life bet') + ' · by ' + esc(nm(b.creator)) + '</span>' + pill(b.status) + '</div>' +
    '<p class="brand" style="font-size:24px;line-height:1.2;margin:0">' + esc(b.name) + '</p>' + (b.desc ? '<p class="mut">' + esc(b.desc) + '</p>' : '') +
    '<div class="hero"><span class="small mut">Pot</span><span class="big">' + eur(pot(b)) + '</span><span class="small mut">Stake ' + eur(b.min) + ' to ' + eur(b.max) + ' · fictional euros</span></div>' +
    '<div class="card">' + (score ? tipsBlock(b) : sidesBlock(b)) + '</div>' + blk.info +
    '<div class="card"><dl class="kv" style="margin:0">' + when + '</dl></div>' + blk.act +
    (blk.demo ? '<div class="demo"><span class="tag">Demo controls</span>' + blk.demo + '</div>' : '') + '</div>';
};

Object.assign(A, {
  pick(d) { ui.join.o = +d.i; },
  join() {
    const g = grp(), b = bet(), s = Math.floor(+ui.join.s), entry = { u: 'me', s };
    if (b.mode === 'score') {
      const tip = parseTip(ui.join.h, ui.join.a);
      if (!tip) return toast('Enter your tip as two whole numbers, for example 2 and 1.');
      entry.tip = tip;
    } else {
      if (ui.join.o == null) return toast('Pick a side first.');
      entry.o = ui.join.o;
    }
    if (!(s >= b.min && s <= b.max)) return toast('Your stake has to be between ' + eur(b.min) + ' and ' + eur(b.max) + '.');
    const err = limitError(g, s); if (err) return toast(err);
    b.entries.push(entry); toast('You are in. Stake noted.');
  },
  withdraw() { const b = bet(); b.entries = b.entries.filter(e => e.u !== 'me'); ui.join = { o: null, s: '', h: '', a: '' }; toast('Stake withdrawn.'); },
  cancel() { bet().status = 'void'; toast('Bet cancelled. Nothing booked.'); },
  demoJoin() {
    const g = grp(), b = bet(), u = g.members.find(x => x !== 'me' && !b.entries.some(e => e.u === x));
    if (!u) return toast('Every member is already in.');
    const s = Math.min(b.max, Math.max(b.min, 20));
    if (b.mode === 'score') {
      const used = b.entries.map(e => tipStr(e.tip)), tip = [[1, 0], [2, 2], [0, 1], [3, 1], [1, 2], [0, 0]].find(t => !used.includes(tipStr(t))) || [4, 4];
      b.entries.push({ u, tip, s }); toast(nm(u) + ' tips ' + tipStr(tip) + '.');
    } else {
      const counts = b.opts.map((o, i) => b.entries.filter(e => e.o === i).length), o = counts.indexOf(Math.min.apply(null, counts));
      b.entries.push({ u, o, s }); toast(nm(u) + ' bets on “' + b.opts[o] + '”.');
    }
  },
  lock() { lock(bet()); }
});
