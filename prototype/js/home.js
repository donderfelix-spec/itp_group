/* Start screen, "Create group" and "Join group". Owner: area 1 (groups). */

VIEWS.home = function () {
  const cards = db.groups.map(g => {
    const open = g.bets.filter(b => b.status === 'open').length, bal = g.bal.me || 0;
    return '<button class="card" data-a="go" data-v="group" data-g="' + g.id + '"><div class="ghead">' + avatarGroup(g) +
      '<div class="col" style="flex:1"><div class="row"><span class="title">' + esc(g.name) + '</span><span class="num ' + cls(bal) + '">' + sg(bal) + '</span></div>' +
      '<span class="small mut">' + g.members.length + (g.members.length === 1 ? ' member' : ' members') + ' · ' + open + ' open ' + (open === 1 ? 'bet' : 'bets') + '</span></div></div></button>';
  }).join('');
  return '<header class="top"><p class="brand">' + BRAND + '</p><span class="sp"></span>' + profileBtn() + '</header>' +
    '<div class="wrap"><h2>Your groups</h2>' + (cards || '<p class="mut">You are not in a group yet. Create one or join with an invite code.</p>') +
    '<div class="btns"><button class="btn pri" data-a="go" data-v="newGroup">Create group</button><button class="btn" data-a="go" data-v="joinGroup">Join group</button></div>' +
    '<p class="small mut">Prototype with example data. Anna, Ben, Clara, Leon and Mia are made up. There are no accounts and no server yet.</p>' +
    '<button class="linkbtn" data-a="reset">Reset example data</button></div>';
};

VIEWS.newGroup = function () {
  return head('Create group', true) + '<div class="wrap">' +
    '<label>Group name<input id="gd-name" data-m="gdraft.name" value="' + esc(ui.gdraft.name) + '" maxlength="40" placeholder="e.g. Friday regulars"></label>' +
    '<label>Description (optional)<textarea id="gd-desc" data-m="gdraft.desc" maxlength="140">' + esc(ui.gdraft.desc) + '</textarea></label>' +
    '<div class="hint">You can create the group on your own. Bets need at least 2 members, though. Until then you can only invite members and manage the group in the admin area.</div>' +
    '<div class="btns"><button class="btn pri" data-a="createGroup">Create group</button></div></div>';
};

VIEWS.joinGroup = function () {
  const demo = db.joinable.map(g => esc(g.code)).join(', ');
  return head('Join group', true) + '<div class="wrap">' +
    '<p class="mut">Ask someone in the group for the invite code. Admins find it in the admin area.</p>' +
    '<label>Invite code<input id="j-code" data-m="jcode" value="' + esc(ui.jcode) + '" maxlength="12" placeholder="ABCD-1234" autocapitalize="characters" autocomplete="off"></label>' +
    '<div class="btns"><button class="btn pri" data-a="joinGroup">Join group</button></div>' +
    '<div class="demo"><span class="tag">Demo</span><span class="small mut">' + (demo ? 'The prototype knows this example code: ' + demo : 'You have joined every example group.') + '</span></div></div>';
};

Object.assign(A, {
  createGroup() {
    const n = ui.gdraft.name.trim();
    if (!n) return toast('Give the group a name.');
    const code = n.replace(/[^A-Za-z]/g, '').slice(0, 4).toUpperCase().padEnd(4, 'X') + '-' + Math.floor(1000 + Math.random() * 9000);
    const g = { id: uid(), name: n, desc: ui.gdraft.desc.trim(), code, admin: 'me', limit: 500, members: ['me'], bal: { me: 0 }, ledger: [], pay: [], bets: [] };
    db.groups.push(g); ui.gdraft = { name: '', desc: '' }; ui.nav.pop(); ui.tab = 'bets'; go('group', g.id);
    toast('Group created. Bets need at least 2 members.');
  },
  joinGroup() {
    const code = ui.jcode.trim().toUpperCase();
    if (!code) return toast('Enter an invite code.');
    if (db.groups.some(g => g.code === code)) return toast('You are already in this group.');
    const i = db.joinable.findIndex(g => g.code === code);
    if (i < 0) return toast('No group found for this code.');
    const g = db.joinable.splice(i, 1)[0];
    g.members.push('me'); g.bal.me = 0; db.groups.push(g);
    ui.jcode = ''; ui.nav.pop(); ui.tab = 'bets'; go('group', g.id);
    toast('You joined ' + g.name + '.');
  }
});
