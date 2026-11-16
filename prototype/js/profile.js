/* Profile screen, opened from the avatar top right. Owner: area 4 (profile and admin). */

VIEWS.profile = function () {
  const total = db.groups.reduce((a, g) => a + (g.bal.me || 0), 0);
  const running = db.groups.reduce((a, g) => a + g.bets.filter(b => isActive(b) && mine(b)).length, 0);
  return head('Profile', true, true) + '<div class="wrap">' +
    '<div class="ghead">' + avatarUser('me', 'lg') + '<span class="small mut">Profile picture: placeholder with your initials. Uploads come later.</span></div>' +
    '<label>Display name<input id="p-name" data-m="pdraft.name" value="' + esc(ui.pdraft.name) + '" maxlength="30"></label>' +
    '<div class="btns"><button class="btn pri" data-a="saveProfile">Save</button></div>' +
    '<h2>Your numbers</h2>' +
    '<div class="card list">' +
      '<div class="row"><span>Balance across all groups</span><span class="num ' + cls(total) + '">' + sg(total) + '</span></div>' +
      '<div class="row"><span>Groups</span><span class="num">' + db.groups.length + '</span></div>' +
      '<div class="row"><span>Running bets you are in</span><span class="num">' + running + '</span></div></div>' +
    '<p class="small mut">There are no accounts yet. Your profile is only stored in this browser.</p>' +
    '<div class="btns"><button class="btn danger" data-a="logout">Log out</button></div></div>';
};

/* Shown instead of every other screen while logged out. There are no accounts yet, so "Log in" simply lets you back in. */
VIEWS.login = function () {
  return '<div class="wrap" style="min-height:80vh;justify-content:center">' +
    '<p class="brand" style="font-size:40px">' + BRAND + '</p>' +
    '<p class="mut">You are logged out.</p>' +
    '<div class="btns"><button class="btn pri" data-a="login">Log in</button></div>' +
    '<p class="small mut">The prototype has no accounts yet. Logging in takes you straight back to your groups, and your data in this browser is kept.</p></div>';
};

Object.assign(A, {
  logout() { db.loggedOut = true; ui.nav = [{ v: 'home' }]; toast('You are logged out.'); },
  login() { db.loggedOut = false; ui.nav = [{ v: 'home' }]; },
  saveProfile() {
    const n = ui.pdraft.name.trim();
    if (!n) return toast('Enter a display name.');
    db.profile.name = n; toast('Profile saved.');
  }
});
