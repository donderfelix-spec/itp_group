/* Core: state, storage, helpers, navigation, event wiring. Owner: area 4 (foundation).
   Every other file registers its screens in VIEWS and its click handlers in A. */

let db;
try { db = JSON.parse(localStorage.getItem(LS)); } catch (e) { db = null; }
if (!db || !db.groups) db = seed();

/* UI state that is not saved: navigation stack, selected tab, form drafts. */
const ui = { nav: [{ v: 'home' }], tab: 'bets', filter: 'all', draft: null, gdraft: { name: '', desc: '' }, join: { o: null, s: '' } };
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
const fdate = iso => new Date(iso).toLocaleString('en-GB', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
const localInput = d => { const p = n => String(n).padStart(2, '0'); return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + 'T' + p(d.getHours()) + ':' + p(d.getMinutes()); };

let toastTimer;
function toast(msg) { const t = document.getElementById('toast'); t.textContent = msg; t.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 2800); }

/* ---------- Shared building blocks ---------- */
const head = (title, back) => '<header class="top">' + (back ? '<button class="back" data-a="back" aria-label="Back">‹</button>' : '') + '<h1>' + esc(title) + '</h1></header>';
const pill = s => '<span class="pill ' + STATUS[s][1] + '">' + STATUS[s][0] + '</span>';

/* ---------- Navigation and rendering ---------- */
const VIEWS = {};   /* view name -> function returning HTML */
const A = {};       /* action name -> handler(dataset); return false to skip re-rendering */

function render() {
  const c = cur();
  if ((c.g && !grp()) || (c.b && !bet())) ui.nav = [{ v: 'home' }];
  document.getElementById('app').innerHTML = VIEWS[cur().v]();
}
function go(v, g, b) { ui.nav.push({ v, g, b }); window.scrollTo(0, 0); }

Object.assign(A, {
  go(d) { if (d.v === 'bet') ui.join = { o: null, s: '' }; go(d.v, d.g, d.b); },
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
/* Inputs write straight into the matching draft, without re-rendering (keeps focus). */
document.addEventListener('input', e => {
  const t = e.target;
  if (t.dataset.d) ui.draft[t.dataset.d] = t.value;
  else if (t.dataset.gd) ui.gdraft[t.dataset.gd] = t.value;
  else if (t.dataset.j) ui.join[t.dataset.j] = t.value;
});
