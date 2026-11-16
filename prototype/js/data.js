/* Example data and constants. Owner: area 4 (foundation).
   Changes to the shape of groups or bets affect every area: announce them first. */

const LS = 'webeat-draft-v1';
const POOL = ['Anna', 'Ben', 'Clara', 'Jonas', 'Mia', 'Leon'];
const EVENTS = [
  { name: 'Bayern – Dortmund', when: 'Sat, 18:30', opts: ['Bayern', 'Draw', 'Dortmund'] },
  { name: 'Leipzig – Leverkusen', when: 'Sun, 15:30', opts: ['Leipzig', 'Draw', 'Leverkusen'] },
  { name: 'Darts World Championship final', when: '3 Jan, 21:00', opts: ['Favourite wins', 'Underdog wins'] }
];
/* status key -> [label, pill style] */
const STATUS = {
  open: ['Open', 'open'], locked: ['Locked', 'wait'], resolving: ['Resolving', 'wait'], disputed: ['Disputed', 'bad'],
  resolved: ['Resolved', 'done'], void: ['Void', 'bad'], infeasible: ['Not feasible', 'bad']
};

/* Group: { id, name, desc, code, admin, members[], bal{user: euros}, ledger[{t, d{user: delta}}], pay[{id, from, to, amt}], bets[] }
   Bet:   { id, type: 'real'|'event', name, desc, opts[], min, max, deadline|event, creator, status,
            entries[{u, o: option index, s: stake}], proposed?, result?, deltas? } */
function seed() {
  const d = h => new Date(Date.now() + h * 3600e3).toISOString();
  return {
    users: { me: 'You', anna: 'Anna', ben: 'Ben', clara: 'Clara' },
    groups: [
      { id: 'g1', name: 'Southside Flatmates', desc: 'Everything you can bet on in a shared flat', code: 'SOUT-4821', admin: 'me',
        members: ['me', 'anna', 'ben', 'clara'], bal: { me: 50, anna: 100, ben: 0, clara: -150 },
        ledger: [{ t: 'Bet “Will Ben run the half marathon in under 2 hours?” resolved', d: { anna: 100, me: 50, clara: -150 } }],
        pay: [],
        bets: [
          { id: 'b1', type: 'real', name: 'Will Ben cook for everyone by Sunday?', desc: 'Only counts if all four of us sit at the table.', opts: ['Yes', 'No'], min: 10, max: 100, deadline: d(96), creator: 'ben', status: 'open',
            entries: [{ u: 'ben', o: 0, s: 50 }, { u: 'anna', o: 1, s: 30 }] },
          { id: 'b2', type: 'event', name: 'Bayern – Dortmund: who wins?', desc: '', opts: ['Bayern', 'Draw', 'Dortmund'], min: 10, max: 50, event: 'Bayern – Dortmund · Sat, 18:30', creator: 'me', status: 'open',
            entries: [{ u: 'me', o: 0, s: 40 }, { u: 'clara', o: 2, s: 40 }] },
          { id: 'b3', type: 'real', name: 'Can Anna do 10 pull-ups in a row?', desc: 'Video as proof.', opts: ['Yes', 'No'], min: 10, max: 50, deadline: d(-2), creator: 'anna', status: 'resolving', proposed: 0,
            entries: [{ u: 'anna', o: 0, s: 20 }, { u: 'me', o: 1, s: 20 }, { u: 'ben', o: 1, s: 10 }] },
          { id: 'b0', type: 'real', name: 'Will Ben run the half marathon in under 2 hours?', desc: '', opts: ['Yes', 'No'], min: 10, max: 200, deadline: d(-200), creator: 'clara', status: 'resolved', result: 0,
            entries: [{ u: 'anna', o: 0, s: 100 }, { u: 'me', o: 0, s: 50 }, { u: 'clara', o: 1, s: 150 }], deltas: { anna: 100, me: 50, clara: -150 } }
        ] },
      { id: 'g2', name: 'Football Crew', desc: '', code: 'FOOT-1907', admin: 'me', members: ['me'], bal: { me: 0 }, ledger: [], pay: [], bets: [] }
    ]
  };
}
