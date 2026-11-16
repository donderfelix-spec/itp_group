/* Group detail: group header, your balance, actions, tabs, list of bets, leaving a group. Owner: area 1 (groups).
   The balances tab lives in settle.js (area 3), the admin area in admin.js (area 4). */

function betCard(b) {
  const m = mine(b);
  /* All cards look the same. Open bets you are not part of show a green "Tap to join". */
  return '<button class="card" data-a="go" data-v="bet" data-g="' + cur().g + '" data-b="' + b.id + '"><div class="row"><span class="tag">' + (b.type === 'event' ? (b.mode === 'score' ? 'Event · exact score' : 'Event') : 'Real life') + '</span>' +
    pill(b.status) + '</div>' +
    '<span class="title">' + esc(b.name) + '</span>' +
    '<div class="row small mut"><span>' + (m ? 'You: ' + esc(entryLabel(b, m)) + ' · ' + eur(m.s) : b.status === 'open' ? '<span class="joinhint">Tap to join ›</span>' : 'You did not take part') + '</span><span class="num">Pot ' + eur(pot(b)) + '</span></div></button>';
}

function betsTab(g, solo) {
  const fs = { all: 'All', mine: 'Mine', done: 'Finished' };
  const list = g.bets.filter(b => ui.filter === 'mine' ? mine(b) && isActive(b) : ui.filter === 'done' ? !isActive(b) : true)
    .slice().sort((a, b) => (isActive(b) ? 1 : 0) - (isActive(a) ? 1 : 0));
  return '<div class="chips">' + Object.keys(fs).map(k => '<button class="chip" data-a="filter" data-f="' + k + '" aria-pressed="' + (ui.filter === k) + '">' + fs[k] + '</button>').join('') +
    '<button class="plus" data-a="newBet" aria-label="Create bet" title="Create bet"' + (solo ? ' disabled' : '') + '>+</button></div>' +
    (list.length ? list.map(betCard).join('') : '<p class="mut">' + (solo ? 'No bets yet. Invite someone first.' : 'Nothing here yet. Create the first bet.') + '</p>');
}

VIEWS.group = function () {
  const g = grp(), solo = g.members.length < 2, bal = g.bal.me || 0, admin = g.admin === 'me';
  if (ui.tab !== 'bal') ui.tab = 'bets';
  const tabs = { bets: 'Bets', bal: 'Balances' };
  return head(g.name, true) + '<div class="wrap">' +
    '<div class="ghead">' + avatarGroup(g, 'lg') + '<div class="col"><p>' + (g.desc ? esc(g.desc) : '<span class="mut">No description yet.</span>') + '</p>' +
      '<span class="small mut">' + g.members.length + (g.members.length === 1 ? ' member' : ' members') + ' · Admin: ' + esc(nm(g.admin)) + '</span></div></div>' +
    '<div class="hero split"><div class="col"><span class="small mut">Your balance in this group</span><span class="big ' + cls(bal) + '">' + sg(bal) + '</span><span class="small mut">fictional euros</span></div>' +
      '<button class="btn sm" data-a="go" data-v="settle" data-g="' + g.id + '"' + (solo ? ' disabled' : '') + '>Settle up</button></div>' +
    (solo ? '<div class="hint">You are the only member of this group. Bets need at least 2 members. Invite someone in the admin area.</div>' : '') +
    '<div class="tabs" role="tablist">' + Object.keys(tabs).map(k => '<button role="tab" data-a="tab" data-t="' + k + '" aria-selected="' + (ui.tab === k) + '">' + tabs[k] + '</button>').join('') + '</div>' +
    (ui.tab === 'bets' ? betsTab(g, solo) : balancesTab(g)) +
    '<div class="btns">' + (admin ? '<button class="btn" data-a="go" data-v="admin" data-g="' + g.id + '">Admin area</button>' : '<button class="btn danger" data-a="leave">Leave group</button>') + '</div></div>';
};

Object.assign(A, {
  tab(d) { ui.tab = d.t; },
  filter(d) { ui.filter = d.f; },
  /* Leaving is only possible with a balance of 0 and no stake in a running bet. */
  leave() {
    const g = grp();
    if (g.bal.me) return toast('Settle your balance to €0 before you leave.');
    if (g.bets.some(b => isActive(b) && mine(b))) return toast('You still have a stake in a running bet.');
    if (g.pay.some(p => p.from === 'me' || p.to === 'me')) return toast('A payment of yours is still waiting for confirmation.');
    g.members = g.members.filter(u => u !== 'me'); delete g.bal.me;
    db.groups = db.groups.filter(x => x.id !== g.id); db.joinable.push(g);
    ui.nav = [{ v: 'home' }]; toast('You left ' + g.name + '.');
  }
});
