/* Bet detail: header, pot, sides, and everything up to the entry deadline (join, withdraw, cancel).
   Owner: area 2 (creating and joining bets). From "locked" onwards see bet-resolve.js (area 3). */

/* Your own stake and what you would win with the current pot. */
function positionCard(b) {
  const m = mine(b);
  if (!m) return '';
  const d = payout(b, m.o);
  return '<div class="card"><div class="row"><span>You bet ' + eur(m.s) + ' on “' + esc(b.opts[m.o]) + '”</span><span class="num pos">' + (d ? sg(d.me) : '') + '</span></div><span class="small mut">Possible win with the current pot. Your balance only changes when the bet is resolved.</span></div>';
}

/* Returns { info, act, demo } HTML blocks for an open bet. */
function openBlock(b) {
  const m = mine(b);
  let act;
  if (!m) {
    act = '<h2>Join</h2><div class="chips">' + b.opts.map((o, i) => '<button class="chip" data-a="pick" data-i="' + i + '" aria-pressed="' + (ui.join.o === i) + '">' + esc(o) + '</button>').join('') + '</div>' +
      '<label>Your stake (' + eur(b.min) + ' to ' + eur(b.max) + ')<input id="j-stake" type="number" inputmode="numeric" data-j="s" value="' + esc(ui.join.s) + '" min="' + b.min + '" max="' + b.max + '"></label>' +
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
  const b = bet(), p = pot(b), won = i => b.status === 'resolved' && b.result === i;
  const when = b.type === 'event'
    ? '<dt>Event</dt><dd>' + esc(b.event) + '</dd><dt>Entries close</dt><dd>At event start</dd>'
    : '<dt>Deadline</dt><dd>' + esc(fdate(b.deadline)) + '</dd><dt>Entries close</dt><dd>' + esc(fdate(new Date(new Date(b.deadline).getTime() - 864e5).toISOString())) + '</dd>';
  const optsHtml = b.opts.map((o, i) => {
    const es = b.entries.filter(e => e.o === i), sum = es.reduce((a, e) => a + e.s, 0);
    return '<div class="opt' + (won(i) ? ' win' : '') + '"><div class="row"><span class="title">' + esc(o) + (won(i) ? ' ✓' : '') + '</span><span class="num">' + eur(sum) + '</span></div>' +
      '<div class="bar"><i style="width:' + (p ? Math.round(sum / p * 100) : 0) + '%"></i></div>' +
      '<span class="small mut">' + (es.length ? es.map(e => esc(nm(e.u)) + ' ' + eur(e.s)).join(' · ') : 'nobody yet') + '</span></div>';
  }).join('');
  const blk = b.status === 'open' ? openBlock(b) : resolveBlock(b);
  return head('Bet', true) + '<div class="wrap">' +
    '<div class="row"><span class="tag">' + (b.type === 'event' ? 'Event bet' : 'Real-life bet') + ' · by ' + esc(nm(b.creator)) + '</span>' + pill(b.status) + '</div>' +
    '<p class="brand" style="font-size:24px;line-height:1.2;margin:0">' + esc(b.name) + '</p>' + (b.desc ? '<p class="mut">' + esc(b.desc) + '</p>' : '') +
    '<div class="hero"><span class="small mut">Pot</span><span class="big">' + eur(p) + '</span><span class="small mut">Stake ' + eur(b.min) + ' to ' + eur(b.max) + ' · fictional euros</span></div>' +
    '<div class="card">' + optsHtml + '</div>' + blk.info +
    '<div class="card"><dl class="kv" style="margin:0">' + when + '</dl></div>' + blk.act +
    (blk.demo ? '<div class="demo"><span class="tag">Demo controls</span>' + blk.demo + '</div>' : '') + '</div>';
};

Object.assign(A, {
  pick(d) { ui.join.o = +d.i; },
  join() {
    const b = bet(), s = Math.floor(+ui.join.s);
    if (ui.join.o == null) return toast('Pick a side first.');
    if (!(s >= b.min && s <= b.max)) return toast('Your stake has to be between ' + eur(b.min) + ' and ' + eur(b.max) + '.');
    b.entries.push({ u: 'me', o: ui.join.o, s }); toast('You are in. Stake noted.');
  },
  withdraw() { const b = bet(); b.entries = b.entries.filter(e => e.u !== 'me'); ui.join = { o: null, s: '' }; toast('Stake withdrawn.'); },
  cancel() { bet().status = 'void'; toast('Bet cancelled. Nothing booked.'); },
  demoJoin() {
    const g = grp(), b = bet(), u = g.members.find(x => x !== 'me' && !b.entries.some(e => e.u === x));
    if (!u) return toast('Every member is already in.');
    const counts = b.opts.map((o, i) => b.entries.filter(e => e.o === i).length), o = counts.indexOf(Math.min.apply(null, counts));
    b.entries.push({ u, o, s: Math.min(b.max, Math.max(b.min, 20)) }); toast(nm(u) + ' bets on “' + b.opts[o] + '”.');
  },
  lock() { lock(bet()); }
});
