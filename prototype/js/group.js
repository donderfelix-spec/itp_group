/* Group detail: balance header, actions, tabs, list of bets. Owner: area 1 (groups).
   The tab contents for balances (settle.js, area 3) and members (members.js, area 4) live in their own files. */

function betCard(b) {
  const m = mine(b);
  return '<button class="card" data-a="go" data-v="bet" data-g="' + cur().g + '" data-b="' + b.id + '"><div class="row"><span class="tag">' + (b.type === 'event' ? 'Event' : 'Real life') + '</span>' + pill(b.status) + '</div>' +
    '<span class="title">' + esc(b.name) + '</span>' +
    '<div class="row small mut"><span>' + (m ? 'You: ' + esc(b.opts[m.o]) + ' · ' + eur(m.s) : 'You are not in') + '</span><span class="num">Pot ' + eur(pot(b)) + '</span></div></button>';
}

function betsTab(g, solo) {
  const fs = { all: 'All', mine: 'Mine', done: 'Finished' };
  const list = g.bets.filter(b => ui.filter === 'mine' ? mine(b) && isActive(b) : ui.filter === 'done' ? !isActive(b) : true)
    .slice().sort((a, b) => (isActive(b) ? 1 : 0) - (isActive(a) ? 1 : 0));
  return '<div class="chips">' + Object.keys(fs).map(k => '<button class="chip" data-a="filter" data-f="' + k + '" aria-pressed="' + (ui.filter === k) + '">' + fs[k] + '</button>').join('') + '</div>' +
    (list.length ? list.map(betCard).join('') : '<p class="mut">' + (solo ? 'No bets yet. Invite someone first.' : 'Nothing here yet. Create the first bet.') + '</p>');
}

VIEWS.group = function () {
  const g = grp(), solo = g.members.length < 2, bal = g.bal.me || 0;
  const body = ui.tab === 'bets' ? betsTab(g, solo) : ui.tab === 'bal' ? balancesTab(g) : membersTab(g);
  const tabs = { bets: 'Bets', bal: 'Balances', mem: 'Members' };
  return head(g.name, true) + '<div class="wrap">' +
    '<div class="hero"><span class="small mut">Your balance in this group</span><span class="big ' + cls(bal) + '">' + sg(bal) + '</span><span class="small mut">fictional euros</span></div>' +
    (solo ? '<div class="hint">You are the only member of this group. Bets need at least 2 members. Invite someone under “Members”.</div>' : '') +
    '<div class="btns"><button class="btn pri" data-a="newBet"' + (solo ? ' disabled' : '') + '>Create bet</button><button class="btn" data-a="go" data-v="settle" data-g="' + g.id + '"' + (solo ? ' disabled' : '') + '>Settle up</button></div>' +
    '<div class="tabs" role="tablist">' + Object.keys(tabs).map(k => '<button role="tab" data-a="tab" data-t="' + k + '" aria-selected="' + (ui.tab === k) + '">' + tabs[k] + '</button>').join('') + '</div>' + body + '</div>';
};

Object.assign(A, {
  tab(d) { ui.tab = d.t; },
  filter(d) { ui.filter = d.f; }
});
