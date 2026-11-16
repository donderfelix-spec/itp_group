/* Start screen and "Create group". Owner: area 1 (groups). */

VIEWS.home = function () {
  const cards = db.groups.map(g => {
    const open = g.bets.filter(b => b.status === 'open').length, bal = g.bal.me || 0;
    return '<button class="card" data-a="go" data-v="group" data-g="' + g.id + '"><div class="row"><span class="title">' + esc(g.name) + '</span><span class="num ' + cls(bal) + '">' + sg(bal) + '</span></div>' +
      '<div class="row small mut"><span>' + g.members.length + (g.members.length === 1 ? ' member' : ' members') + ' · ' + open + ' open ' + (open === 1 ? 'bet' : 'bets') + '</span></div></button>';
  }).join('');
  return '<div class="wrap"><p class="brand">WE BE<b>(A)</b>T</p><p class="mut">Bets among friends. Tracked in fictional euros, settled up at the end.</p>' +
    '<h2>Your groups</h2>' + cards +
    '<div class="btns"><button class="btn pri" data-a="go" data-v="newGroup">Create group</button></div>' +
    '<p class="small mut">Prototype with example data. Anna, Ben and Clara are made up. There are no accounts and no server yet.</p>' +
    '<button class="linkbtn" data-a="reset">Reset example data</button></div>';
};

VIEWS.newGroup = function () {
  return head('Create group', true) + '<div class="wrap">' +
    '<label>Group name<input id="gd-name" data-gd="name" value="' + esc(ui.gdraft.name) + '" maxlength="40" placeholder="e.g. Friday regulars"></label>' +
    '<label>Description (optional)<textarea id="gd-desc" data-gd="desc" maxlength="140">' + esc(ui.gdraft.desc) + '</textarea></label>' +
    '<div class="hint">You can create the group on your own. Bets need at least 2 members, though. Until then you can only invite members and manage the group.</div>' +
    '<div class="btns"><button class="btn pri" data-a="createGroup">Create group</button></div></div>';
};

Object.assign(A, {
  createGroup() {
    const n = ui.gdraft.name.trim();
    if (!n) return toast('Give the group a name.');
    const code = n.replace(/[^A-Za-z]/g, '').slice(0, 4).toUpperCase().padEnd(4, 'X') + '-' + Math.floor(1000 + Math.random() * 9000);
    const g = { id: uid(), name: n, desc: ui.gdraft.desc.trim(), code, admin: 'me', members: ['me'], bal: { me: 0 }, ledger: [], pay: [], bets: [] };
    db.groups.push(g); ui.gdraft = { name: '', desc: '' }; ui.nav.pop(); ui.tab = 'mem'; go('group', g.id);
    toast('Group created. Bets need at least 2 members.');
  }
});
