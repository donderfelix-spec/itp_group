/* Core: state, storage, helpers, navigation, event wiring. Owner: area 4 (foundation).
   Every other file registers its screens in VIEWS and its click handlers in A. */

let db;
try { db = JSON.parse(localStorage.getItem(LS)); } catch (e) { db = null; }
if (!db || !db.groups || !db.profile || !db.joinable) db = seed();

/* UI state that is not saved: navigation stack, selected tab, form drafts.
   An input with data-m="draft.name" writes its value to ui.draft.name. */
const ui = {
  nav: [{ v: 'home' }], tab: 'bets', filter: 'all',
  draft: null,                               /* create bet */
  gdraft: { name: '', desc: '' },            /* create group */
  jcode: '',                                 /* join group */
  join: { o: null, s: '', h: '', a: '' },    /* join bet */
  res: { h: '', a: '' },                     /* result of a score bet */
  pdraft: { name: '' },                      /* profile */
  adraft: { name: '', desc: '', limit: 0 },  /* admin area */
  confirmDel: false
};
function save() { try { localStorage.setItem(LS, JSON.stringify(db)); } catch (e) {} }

/* ---------- Helpers ---------- */
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
/* All amounts are fictional euros, stored as whole numbers. */
const eur = n => '€' + Math.abs(n).toLocaleString('en-US');
const sg = n => (n > 0 ? '+' : n < 0 ? '−' : '') + eur(n);
const cls = n => n > 0 ? 'pos' : n < 0 ? 'neg' : '';
const uid = () => Math.random().toString(36).slice(2, 9);
const nm = u => db.users[u] || u;
const cur = () => ui.nav[ui.nav.length - 1];
const grp = () => db.groups.find(g => g.id === cur().g);
const bet = () => { const g = grp(); return g && g.bets.find(b => b.id === cur().b); };
const pot = b => b.entries.reduce((a, e) => a + e.s, 0);
const mine = b => b.entries.find(e => e.u === 'me');
const isActive = b => ['open', 'locked', 'resolving', 'disputed'].includes(b.status);
const tipStr = t => t[0] + ':' + t[1];
/* What an entry is betting on: an outcome name, or a scoreline. */
const entryLabel = (b, e) => b.mode === 'score' ? tipStr(e.tip) : b.opts[e.o];
const fdate = iso => new Date(iso).toLocaleString('en-GB', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
const localInput = d => { const p = n => String(n).padStart(2, '0'); return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + 'T' + p(d.getHours()) + ':' + p(d.getMinutes()); };

let toastTimer;
function toast(msg) { const t = document.getElementById('toast'); t.textContent = msg; t.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 2800); }

/* ---------- Shared building blocks ---------- */
/* Picture placeholders: initials in a circle (people) or rounded square (groups). Add 'lg' for the large size. */
const initials = s => { const w = String(s).trim().split(/\s+/).filter(Boolean); return ((w.length > 1 ? w[0][0] + w[1][0] : (w[0] || '?').slice(0, 2))).toUpperCase(); };
const avatar = (name, extra) => '<span class="av' + (extra ? ' ' + extra : '') + '" aria-hidden="true">' + esc(initials(name)) + '</span>';
/* Your own avatar shows your uploaded picture if there is one, otherwise your initials. */
const avatarUser = (u, extra) => u === 'me' && db.profile.photo
  ? '<span class="av' + (extra ? ' ' + extra : '') + '" aria-hidden="true"><img src="' + esc(db.profile.photo) + '" alt=""></span>'
  : avatar(u === 'me' ? db.profile.name : nm(u), extra);
const avatarGroup = (g, extra) => avatar(g.name, 'g' + (extra ? ' ' + extra : ''));

/* Wordmark. The letters are type, the two square brackets are drawn shapes, so their weight and height are exact
   and they sit on the centre of the capitals instead of wherever the typeface puts its brackets. */
const bracket = d => '<svg viewBox="0 0 30 100" fill="none" stroke="currentColor" stroke-width="11" stroke-linecap="butt" stroke-linejoin="miter" aria-hidden="true"><path d="' + d + '"/></svg>';
const BRAND = '<span class="bm" role="img" aria-label="We Be(a)t"><span>WE BE</span>' + bracket('M24 7H9V93H24') + '<span class="a">A</span>' + bracket('M6 7H21V93H6') + '<span>T</span></span>';

const profileBtn = () => '<button class="avbtn" data-a="go" data-v="profile" aria-label="Profile">' + avatarUser('me') + '</button>';
/* Top bar. The profile button sits top right on every screen unless noProfile is set. */
const head = (title, back, noProfile) => '<header class="top">' + (back ? '<button class="back" data-a="back" aria-label="Back"><svg width="11" height="18" viewBox="0 0 11 18" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 2 2 9l7 7"/></svg></button>' : '') +
  '<h1>' + esc(title) + '</h1><span class="sp"></span>' + (noProfile ? '' : profileBtn()) + '</header>';
const pill = s => '<span class="pill ' + STATUS[s][1] + '">' + STATUS[s][0] + '</span>';

/* ---------- Navigation and rendering ---------- */
const VIEWS = {};   /* view name -> function returning HTML */
const A = {};       /* action name -> handler(dataset); return false to skip re-rendering */

function render() {
  /* Logged out: only the login screen is reachable (see profile.js). */
  if (db.loggedOut) { document.getElementById('app').innerHTML = VIEWS.login(); return; }
  const c = cur();
  if ((c.g && !grp()) || (c.b && !bet())) ui.nav = [{ v: 'home' }];
  document.getElementById('app').innerHTML = VIEWS[cur().v]();
}
function go(v, g, b) { ui.nav.push({ v, g, b }); window.scrollTo(0, 0); }

Object.assign(A, {
  go(d) {
    if (d.v === 'bet') { ui.join = { o: null, s: '', h: '', a: '' }; ui.res = { h: '', a: '' }; }
    if (d.v === 'profile') { if (cur().v === 'profile') return; ui.pdraft = { name: db.profile.name }; ui.confirmAcc = false; }
    if (d.v === 'admin') { const g = db.groups.find(x => x.id === d.g); ui.adraft = { name: g.name, desc: g.desc, limit: g.limit }; ui.confirmDel = false; }
    go(d.v, d.g, d.b);
  },
  back() { if (ui.nav.length > 1) ui.nav.pop(); },
  reset() { db = seed(); ui.nav = [{ v: 'home' }]; toast('Example data reset.'); }
});

/* Clicks: any element with data-a="name" calls A.name with its data attributes. */
document.addEventListener('click', e => {
  const el = e.target.closest('[data-a]'); if (!el || el.disabled) return;
  const fn = A[el.dataset.a]; if (!fn) return;
  const r = fn(el.dataset);
  save(); if (r !== false) render();
});
/* Inputs write straight into ui via data-m="path.to.field", without re-rendering (keeps focus). */
document.addEventListener('input', e => {
  const m = e.target.dataset.m; if (!m) return;
  const p = m.split('.'); let o = ui;
  for (let i = 0; i < p.length - 1; i++) o = o[p[i]];
  o[p[p.length - 1]] = e.target.value;
});
