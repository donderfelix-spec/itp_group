/* Bet detail from the entry deadline onwards: report result, confirm, dispute, vote, final result.
   Owner: area 3 (resolution and balances). Everything before the deadline is in bet-detail.js (area 2). */

/* Returns { info, act, demo } HTML blocks for a bet that is no longer open. */
function resolveBlock(b) {
  const iAmCreator = b.creator === 'me';
  const pick = (action, label) => '<span class="small mut">' + label + '</span><div class="chips">' + b.opts.map((o, i) => '<button class="chip" data-a="' + action + '" data-i="' + i + '">' + esc(o) + '</button>').join('') + '</div>';
  let info = isActive(b) ? positionCard(b) : '', act = '', demo = '';

  if (b.status === 'resolved') {
    info = '<div class="card"><span class="small mut">Result: ' + esc(b.opts[b.result]) + '</span><div class="list">' + Object.keys(b.deltas).map(u => '<div class="row"><span>' + esc(nm(u)) + '</span><span class="num ' + cls(b.deltas[u]) + '">' + sg(b.deltas[u]) + '</span></div>').join('') + '</div></div>';
  } else if (b.status === 'infeasible') {
    info = '<div class="hint">There was no opponent by the entry deadline. The bet was marked as not feasible and closed. Nothing was booked.</div>';
  } else if (b.status === 'void') {
    info = '<div class="hint">This bet is void. Nothing was booked.</div>';
  } else if (b.status === 'locked') {
    if (b.type === 'event') demo = pick('result', 'Simulate the result from the sports API:');
    else if (iAmCreator) act = '<h2>Report result</h2><div class="card">' + pick('propose', 'What happened?') + '</div>';
    else demo = pick('propose', esc(nm(b.creator)) + ' reports the result:');
  } else if (b.status === 'resolving') {
    act = '<div class="card"><span>' + (iAmCreator ? 'You' : esc(nm(b.creator))) + ' reported “' + esc(b.opts[b.proposed]) + '” as the result.</span>' +
      (iAmCreator ? '<span class="small mut">The other participants have to confirm. Without a reaction it counts as confirmed after 48 hours.</span>' :
        '<div class="btns"><button class="btn pri" data-a="confirm">Confirm</button><button class="btn danger" data-a="dispute">Dispute</button></div>') + '</div>';
    if (iAmCreator) demo = '<div class="btns"><button class="btn" data-a="confirm">Group confirms</button><button class="btn" data-a="dispute">Someone disputes</button></div>';
  } else if (b.status === 'disputed') {
    act = '<div class="hint">The result was disputed. All participants vote and the majority decides.</div>';
    demo = pick('result', 'Simulate the vote. Majority for:') + '<div class="btns"><button class="btn" data-a="nomajority">No majority</button></div>';
  }
  return { info, act, demo };
}

Object.assign(A, {
  propose(d) { const b = bet(); b.proposed = +d.i; b.status = 'resolving'; toast('Result reported. Waiting for confirmation.'); },
  confirm() { const b = bet(); resolve(grp(), b, b.proposed); },
  dispute() { bet().status = 'disputed'; toast('Result disputed. The group votes.'); },
  result(d) { resolve(grp(), bet(), +d.i); },
  nomajority() { bet().status = 'void'; toast('No majority. Bet void, nothing booked.'); }
});
