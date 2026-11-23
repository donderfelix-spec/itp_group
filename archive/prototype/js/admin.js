/* Admin area of a group: details, picture, members, invite code, debt limit, delete. Owner: area 4 (profile and admin).
   Only the group admin can open it. */

VIEWS.admin = function () {
  const g = grp(), d = ui.adraft;
  if (g.admin !== 'me') return head('Admin area', true) + '<div class="wrap"><div class="hint">Only the group admin can open this area.</div></div>';
  const del = ui.confirmDel
    ? '<div class="hint">Delete “' + esc(g.name) + '” for everyone? This cannot be undone.</div><div class="btns"><button class="btn danger" data-a="deleteGroup">Yes, delete</button><button class="btn" data-a="keepGroup">Keep group</button></div>'
    : '<div class="btns"><button class="btn danger" data-a="askDelete">Delete group</button></div>';
  return head('Admin area', true) + '<div class="wrap">' +
    '<h2>Group details</h2>' +
    '<div class="ghead">' + avatarGroup(g, 'lg') + '<span class="small mut">Group picture: placeholder with the group’s initials. Uploads come later.</span></div>' +
    '<label>Group name<input id="ad-name" data-m="adraft.name" value="' + esc(d.name) + '" maxlength="40"></label>' +
    '<label>Description<textarea id="ad-desc" data-m="adraft.desc" maxlength="140">' + esc(d.desc) + '</textarea></label>' +
    '<label>Debt limit in € (0 = no limit)<input id="ad-limit" type="number" inputmode="numeric" min="0" data-m="adraft.limit" value="' + esc(d.limit) + '"></label>' +
    '<p class="small mut">Nobody can place a stake that could take their balance below the debt limit.</p>' +
    '<div class="btns"><button class="btn pri" data-a="saveGroup">Save changes</button></div>' +
    '<h2>Members</h2>' +
    '<div class="card list">' + g.members.map(u => '<div class="row"><span class="who">' + avatarUser(u) + '<span>' + esc(nm(u)) + '</span></span>' + (u === g.admin ? '<span class="tag">Admin</span>' : '') + '</div>').join('') + '</div>' +
    '<div class="card"><span class="small mut">Invite code</span><div class="row"><span class="code" id="code">' + esc(g.code) + '</span><button class="btn sm" data-a="copy">Copy</button></div></div>' +
    '<div class="demo"><span class="tag">Demo</span><span class="small mut">The prototype has no real invitations. This simulates someone joining.</span><div class="btns"><button class="btn" data-a="addMember">Add example member</button></div></div>' +
    '<h2>Danger zone</h2>' + del + '</div>';
};

Object.assign(A, {
  saveGroup() {
    const g = grp(), d = ui.adraft, n = d.name.trim(), limit = Math.floor(Number(d.limit));
    if (!n) return toast('The group needs a name.');
    if (!(limit >= 0)) return toast('The debt limit has to be 0 or more.');
    g.name = n; g.desc = d.desc.trim(); g.limit = limit; d.limit = limit; toast('Group saved.');
  },
  addMember() {
    const g = grp(), n = POOL.find(x => !g.members.includes(x.toLowerCase()));
    if (!n) return toast('No more example members.');
    const id = n.toLowerCase(); db.users[id] = n; g.members.push(id); g.bal[id] = 0; toast(n + ' joined.');
  },
  copy() {
    const t = grp().code;
    try { navigator.clipboard.writeText(t).then(() => toast('Code copied.'), () => toast('Code: ' + t)); } catch (e) { toast('Code: ' + t); }
    return false;
  },
  askDelete() { ui.confirmDel = true; },
  keepGroup() { ui.confirmDel = false; },
  /* A group can only be deleted once nothing is owed and no bet is running. */
  deleteGroup() {
    const g = grp();
    ui.confirmDel = false;
    if (g.bets.some(isActive)) return toast('There are still running bets in this group.');
    if (g.members.some(u => g.bal[u]) || g.pay.length) return toast('Settle all balances to €0 first.');
    db.groups = db.groups.filter(x => x.id !== g.id); ui.nav = [{ v: 'home' }]; toast('Group deleted.');
  }
});
