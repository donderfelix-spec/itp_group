/* Members list and invite code. Owner: area 4 (profile and admin).
   Planned: move this into an admin area per group (see TODO.md). */

function membersTab(g) {
  return '<div class="card list">' + g.members.map(u => '<div class="row"><span>' + esc(nm(u)) + '</span>' + (u === g.admin ? '<span class="tag">Admin</span>' : '') + '</div>').join('') + '</div>' +
    '<div class="card"><span class="small mut">Invite code</span><div class="row"><span class="code" id="code">' + esc(g.code) + '</span><button class="btn sm" data-a="copy">Copy</button></div></div>' +
    '<div class="demo"><span class="tag">Demo</span><span class="small mut">The prototype has no real invitations. This simulates someone joining.</span><div class="btns"><button class="btn" data-a="addMember">Add example member</button></div></div>';
}

Object.assign(A, {
  addMember() {
    const g = grp(), n = POOL.find(x => !g.members.includes(x.toLowerCase()));
    if (!n) return toast('No more example members.');
    const id = n.toLowerCase(); db.users[id] = n; g.members.push(id); g.bal[id] = 0; toast(n + ' joined.');
  },
  copy() {
    const t = grp().code;
    try { navigator.clipboard.writeText(t).then(() => toast('Code copied.'), () => toast('Code: ' + t)); } catch (e) { toast('Code: ' + t); }
    return false;
  }
});
