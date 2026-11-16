/* Profile screen, opened from the avatar top right. Owner: area 4 (profile and admin). */

VIEWS.profile = function () {
  const total = db.groups.reduce((a, g) => a + (g.bal.me || 0), 0);
  const running = db.groups.reduce((a, g) => a + g.bets.filter(b => isActive(b) && mine(b)).length, 0);
  return head('Profile', true, true) + '<div class="wrap">' +
    '<div class="ghead"><label class="avup" title="Upload profile picture">' + avatarUser('me', 'lg') + '<span class="avplus" aria-hidden="true">+</span>' +
      '<input id="p-photo" type="file" accept="image/*" aria-label="Upload profile picture"></label>' +
      '<div class="col"><span class="small mut">' + (db.profile.photo ? 'Tap the picture to change it.' : 'Tap the plus to upload a profile picture. Without one, your initials are shown.') + '</span>' +
      (db.profile.photo ? '<button class="linkbtn" style="align-self:flex-start;padding:4px 0" data-a="removePhoto">Remove picture</button>' : '') + '</div></div>' +
    '<label>Display name<input id="p-name" data-m="pdraft.name" value="' + esc(ui.pdraft.name) + '" maxlength="30"></label>' +
    '<div class="btns"><button class="btn pri" data-a="saveProfile">Save</button></div>' +
    '<h2>Your numbers</h2>' +
    '<div class="card list">' +
      '<div class="row"><span>Balance across all groups</span><span class="num ' + cls(total) + '">' + sg(total) + '</span></div>' +
      '<div class="row"><span>Groups</span><span class="num">' + db.groups.length + '</span></div>' +
      '<div class="row"><span>Running bets you are in</span><span class="num">' + running + '</span></div></div>' +
    '<p class="small mut">There are no accounts yet. Your profile is only stored in this browser.</p>' +
    '<div class="btns"><button class="btn" data-a="logout">Log out</button></div>' +
    '<h2>Danger zone</h2>' + (ui.confirmAcc
      ? '<div class="hint">Delete your account? Your profile, your groups and your history on this device are removed. This cannot be undone.</div>' +
        '<div class="btns"><button class="btn danger" data-a="deleteAccount">Yes, delete</button><button class="btn" data-a="keepAccount">Keep account</button></div>'
      : '<div class="btns"><button class="btn danger" data-a="askDeleteAccount">Delete account</button></div>') + '</div>';
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
  removePhoto() { delete db.profile.photo; toast('Profile picture removed.'); },
  askDeleteAccount() { ui.confirmAcc = true; },
  keepAccount() { ui.confirmAcc = false; },
  /* An account can only be deleted once nothing is owed either way and no stake is running, so no debt disappears with it.
     The prototype has no accounts, so deleting resets this browser to the example data and logs you out. */
  deleteAccount() {
    ui.confirmAcc = false;
    if (db.groups.some(g => g.bal.me || g.pay.some(p => p.from === 'me' || p.to === 'me'))) return toast('Settle your balance to €0 in every group first.');
    if (db.groups.some(g => g.bets.some(b => isActive(b) && mine(b)))) return toast('You still have a stake in a running bet.');
    db = seed(); db.loggedOut = true; ui.nav = [{ v: 'home' }]; toast('Account deleted.');
  },
  logout() { db.loggedOut = true; ui.nav = [{ v: 'home' }]; toast('You are logged out.'); },
  login() { db.loggedOut = false; ui.nav = [{ v: 'home' }]; },
  saveProfile() {
    const n = ui.pdraft.name.trim();
    if (!n) return toast('Enter a display name.');
    db.profile.name = n; toast('Profile saved.');
  }
});

/* Profile picture upload: the chosen image is cropped to a square, scaled down and stored in this browser only. */
document.addEventListener('change', e => {
  if (e.target.id !== 'p-photo') return;
  const f = e.target.files && e.target.files[0];
  if (!f) return;
  if (!/^image\//.test(f.type)) return toast('Choose an image file.');
  const r = new FileReader();
  r.onload = () => {
    const img = new Image();
    img.onload = () => {
      const S = 192, c = document.createElement('canvas'), m = Math.min(img.width, img.height);
      c.width = c.height = S;
      c.getContext('2d').drawImage(img, (img.width - m) / 2, (img.height - m) / 2, m, m, 0, 0, S, S);
      db.profile.photo = c.toDataURL('image/jpeg', 0.85);
      save(); render(); toast('Profile picture updated.');
    };
    img.onerror = () => toast('This image could not be read.');
    img.src = r.result;
  };
  r.readAsDataURL(f);
});
