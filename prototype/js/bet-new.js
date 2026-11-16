/* "Create bet" form for real-life and event bets. Owner: area 2 (creating and joining bets). */

VIEWS.newBet = function () {
  const d = ui.draft, opts = d.type === 'event' ? EVENTS[d.ev].opts : [d.o1 || 'Option 1', d.o2 || 'Option 2'];
  if (d.side >= opts.length) d.side = 0;
  const typeBtn = (k, t) => '<button role="tab" data-a="type" data-t="' + k + '" aria-selected="' + (d.type === k) + '">' + t + '</button>';
  const specific = d.type === 'event'
    ? '<label>Choose event<select id="d-ev" data-d="ev">' + EVENTS.map((e, i) => '<option value="' + i + '"' + (i === +d.ev ? ' selected' : '') + '>' + esc(e.name + ' · ' + e.when) + '</option>').join('') + '</select></label>' +
      '<p class="small mut">Entries close when the event starts. The result comes in automatically afterwards. The events here are examples.</p>'
    : '<div class="two"><label>Outcome 1<input id="d-o1" data-d="o1" value="' + esc(d.o1) + '" maxlength="24"></label><label>Outcome 2<input id="d-o2" data-d="o2" value="' + esc(d.o2) + '" maxlength="24"></label></div>' +
      '<label>Deadline<input id="d-dl" type="datetime-local" data-d="deadline" value="' + esc(d.deadline) + '"></label>' +
      '<p class="small mut">Entries close 24 hours before the deadline. After the deadline you report the result and the group confirms it.</p>';
  return head('Create bet', true) + '<div class="wrap">' +
    '<div class="tabs" role="tablist">' + typeBtn('real', 'Real-life bet') + typeBtn('event', 'Event bet') + '</div>' +
    '<label>Bet name<input id="d-name" data-d="name" value="' + esc(d.name) + '" maxlength="80" placeholder="What is it about?"></label>' +
    '<label>Description (optional)<textarea id="d-desc" data-d="desc" maxlength="200" placeholder="Rules, proof, special cases">' + esc(d.desc) + '</textarea></label>' +
    specific +
    '<div class="two"><label>Minimum stake (€)<input id="d-min" type="number" inputmode="numeric" min="1" data-d="min" value="' + esc(d.min) + '"></label><label>Maximum stake (€)<input id="d-max" type="number" inputmode="numeric" min="1" data-d="max" value="' + esc(d.max) + '"></label></div>' +
    '<h2>Your side</h2><div class="chips">' + opts.map((o, i) => '<button class="chip" data-a="dside" data-i="' + i + '" aria-pressed="' + (d.side === i) + '">' + esc(o) + '</button>').join('') + '</div>' +
    '<label>Your stake (€)<input id="d-stake" type="number" inputmode="numeric" min="1" data-d="stake" value="' + esc(d.stake) + '"></label>' +
    '<div class="btns"><button class="btn pri" data-a="createBet">Publish bet</button></div></div>';
};

Object.assign(A, {
  newBet() {
    ui.draft = { type: 'real', name: '', desc: '', o1: 'Yes', o2: 'No', min: 10, max: 100, deadline: localInput(new Date(Date.now() + 72 * 3600e3)), ev: 0, side: 0, stake: 10 };
    go('newBet', cur().g);
  },
  type(d) { ui.draft.type = d.t; ui.draft.side = 0; },
  dside(d) { ui.draft.side = +d.i; },
  createBet() {
    const d = ui.draft, g = grp(), min = Math.floor(+d.min), max = Math.floor(+d.max), stake = Math.floor(+d.stake);
    if (g.members.length < 2) return toast('Bets need at least 2 members.');
    if (!d.name.trim()) return toast('Give the bet a name.');
    if (!(min >= 1) || !(max >= min)) return toast('Check the minimum and maximum stake.');
    if (!(stake >= min && stake <= max)) return toast('Your stake has to be between ' + eur(min) + ' and ' + eur(max) + '.');
    const b = { id: uid(), type: d.type, name: d.name.trim(), desc: d.desc.trim(), min, max, creator: 'me', status: 'open', entries: [{ u: 'me', o: d.side, s: stake }] };
    if (d.type === 'event') { const e = EVENTS[+d.ev]; b.opts = e.opts.slice(); b.event = e.name + ' · ' + e.when; }
    else {
      if (!d.o1.trim() || !d.o2.trim() || d.o1.trim() === d.o2.trim()) return toast('Enter two different outcomes.');
      if (!d.deadline || isNaN(new Date(d.deadline))) return toast('Set a deadline.');
      b.opts = [d.o1.trim(), d.o2.trim()]; b.deadline = new Date(d.deadline).toISOString();
    }
    g.bets.push(b); ui.nav.pop(); ui.tab = 'bets'; ui.filter = 'all'; go('bet', g.id, b.id);
    toast('Bet is open. The group gets notified.');
  }
});

/* Picking another event changes the available outcomes, so the form has to re-render. */
document.addEventListener('change', e => {
  if (e.target.dataset.d === 'ev') { ui.draft.ev = +e.target.value; ui.draft.side = 0; render(); }
});
