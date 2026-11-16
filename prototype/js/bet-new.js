/* "Create bet" form for real-life and event bets. Owner: area 2 (creating and joining bets). */

const MAX_OUTCOMES = 5;

VIEWS.newBet = function () {
  const d = ui.draft, ev = EVENTS[+d.ev];
  if (d.type === 'event' && !ev.score) d.mode = 'pick';
  const score = d.type === 'event' && d.mode === 'score';
  const opts = d.type === 'event' ? ev.opts : d.outs.map((o, i) => o.trim() || 'Outcome ' + (i + 1));
  if (d.side >= opts.length) d.side = 0;
  const tab = (action, k, t, on) => '<button role="tab" data-a="' + action + '" data-t="' + k + '" aria-selected="' + on + '">' + t + '</button>';

  let specific;
  if (d.type === 'event') {
    specific = '<label>Choose event<select id="d-ev" data-m="draft.ev">' + EVENTS.map((e, i) => '<option value="' + i + '"' + (i === +d.ev ? ' selected' : '') + '>' + esc(e.name + ' · ' + e.when) + '</option>').join('') + '</select></label>' +
      (ev.score ? '<h2>What do you bet on?</h2><div class="tabs" role="tablist">' + tab('mode', 'pick', 'Winner', d.mode === 'pick') + tab('mode', 'score', 'Exact score', d.mode === 'score') + '</div>' : '') +
      '<p class="small mut">' + (score ? 'Everyone tips a scoreline. The closest tip wins: the right tendency counts first, then the goal distance. Equally close tips share the pot. ' : '') +
      'Entries close when the event starts. The result comes in automatically afterwards. The events here are examples.</p>';
  } else {
    specific = '<h2>Outcomes</h2>' + d.outs.map((o, i) => '<div class="row"><input id="d-out' + i + '" data-m="draft.outs.' + i + '" value="' + esc(o) + '" maxlength="24" aria-label="Outcome ' + (i + 1) + '">' +
        (d.outs.length > 2 ? '<button class="btn sm" data-a="rmOut" data-i="' + i + '">Remove</button>' : '') + '</div>').join('') +
      (d.outs.length < MAX_OUTCOMES ? '<div class="btns"><button class="btn sm" data-a="addOut">Add outcome</button></div>' : '') +
      '<label>Deadline<input id="d-dl" type="datetime-local" data-m="draft.deadline" value="' + esc(d.deadline) + '"></label>' +
      '<label>Proof<select id="d-proof" data-m="draft.proof">' + Object.keys(PROOFS).map(k => '<option value="' + k + '"' + (d.proof === k ? ' selected' : '') + '>' + PROOFS[k] + '</option>').join('') + '</select></label>' +
      '<p class="small mut">Entries close 24 hours before the deadline. After the deadline you report the result with the agreed proof and the group confirms it.</p>';
  }

  const side = score
    ? '<h2>Your tip</h2><div class="score"><label>' + esc(ev.opts[0]) + '<input id="d-th" type="number" inputmode="numeric" min="0" max="20" data-m="draft.th" value="' + esc(d.th) + '"></label><b>:</b>' +
      '<label>' + esc(ev.opts[ev.opts.length - 1]) + '<input id="d-ta" type="number" inputmode="numeric" min="0" max="20" data-m="draft.ta" value="' + esc(d.ta) + '"></label></div>'
    : '<h2>Your side</h2><div class="chips">' + opts.map((o, i) => '<button class="chip" data-a="dside" data-i="' + i + '" aria-pressed="' + (d.side === i) + '">' + esc(o) + '</button>').join('') + '</div>';

  return head('Create bet', true) + '<div class="wrap">' +
    '<div class="tabs" role="tablist">' + tab('type', 'real', 'Real-life bet', d.type === 'real') + tab('type', 'event', 'Event bet', d.type === 'event') + '</div>' +
    '<label>Bet name<input id="d-name" data-m="draft.name" value="' + esc(d.name) + '" maxlength="80" placeholder="What is it about?"></label>' +
    '<label>Description (optional)<textarea id="d-desc" data-m="draft.desc" maxlength="200" placeholder="Rules and special cases">' + esc(d.desc) + '</textarea></label>' +
    specific +
    '<div class="two"><label>Minimum stake (€)<input id="d-min" type="number" inputmode="numeric" min="1" data-m="draft.min" value="' + esc(d.min) + '"></label><label>Maximum stake (€)<input id="d-max" type="number" inputmode="numeric" min="1" data-m="draft.max" value="' + esc(d.max) + '"></label></div>' +
    side +
    '<label>Your stake (€)<input id="d-stake" type="number" inputmode="numeric" min="1" data-m="draft.stake" value="' + esc(d.stake) + '"></label>' +
    '<div class="btns"><button class="btn pri" data-a="createBet">Publish bet</button></div></div>';
};

Object.assign(A, {
  newBet() {
    ui.draft = { type: 'real', mode: 'pick', name: '', desc: '', outs: ['Yes', 'No'], proof: 'participants', min: 10, max: 100,
      deadline: localInput(new Date(Date.now() + 72 * 3600e3)), ev: 0, side: 0, th: '', ta: '', stake: 10 };
    go('newBet', cur().g);
  },
  type(d) { ui.draft.type = d.t; ui.draft.side = 0; },
  mode(d) { ui.draft.mode = d.t; },
  dside(d) { ui.draft.side = +d.i; },
  addOut() { if (ui.draft.outs.length < MAX_OUTCOMES) ui.draft.outs.push(''); },
  rmOut(d) { if (ui.draft.outs.length > 2) { ui.draft.outs.splice(+d.i, 1); ui.draft.side = 0; } },
  createBet() {
    const d = ui.draft, g = grp(), min = Math.floor(+d.min), max = Math.floor(+d.max), stake = Math.floor(+d.stake);
    if (g.members.length < 2) return toast('Bets need at least 2 members.');
    if (!d.name.trim()) return toast('Give the bet a name.');
    if (!(min >= 1) || !(max >= min)) return toast('Check the minimum and maximum stake.');
    if (!(stake >= min && stake <= max)) return toast('Your stake has to be between ' + eur(min) + ' and ' + eur(max) + '.');
    const b = { id: uid(), type: d.type, mode: 'pick', name: d.name.trim(), desc: d.desc.trim(), min, max, creator: 'me', status: 'open' };
    let entry = { u: 'me', o: d.side, s: stake };
    if (d.type === 'event') {
      const e = EVENTS[+d.ev]; b.opts = e.opts.slice(); b.event = e.name + ' · ' + e.when;
      if (e.score && d.mode === 'score') {
        const tip = parseTip(d.th, d.ta);
        if (!tip) return toast('Enter your tip as two whole numbers, for example 2 and 1.');
        b.mode = 'score'; entry = { u: 'me', tip, s: stake };
      }
    } else {
      const outs = d.outs.map(o => o.trim());
      if (outs.some(o => !o)) return toast('Fill in every outcome or remove the empty one.');
      if (new Set(outs.map(o => o.toLowerCase())).size < outs.length) return toast('Every outcome needs a different name.');
      if (!d.deadline || isNaN(new Date(d.deadline))) return toast('Set a deadline.');
      b.opts = outs; b.deadline = new Date(d.deadline).toISOString(); b.proof = PROOFS[d.proof] ? d.proof : 'participants';
    }
    const err = limitError(g, stake); if (err) return toast(err);
    b.entries = [entry];
    g.bets.push(b); ui.nav.pop(); ui.tab = 'bets'; ui.filter = 'all'; A.go({ v: 'bet', g: g.id, b: b.id });
    toast('Bet is open. The group gets notified.');
  }
});

/* Choosing another event or renaming an outcome changes what the rest of the form shows, so it re-renders. */
document.addEventListener('change', e => {
  const m = e.target.dataset.m || '';
  if (m === 'draft.ev') { ui.draft.ev = +e.target.value; ui.draft.side = 0; render(); }
  else if (m.indexOf('draft.outs.') === 0) render();
});
