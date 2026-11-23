/* Example data and constants. Owner: area 4 (foundation).
   Changes to the shape of groups or bets affect every area: announce them first. */

const LS = 'webeat-draft-v2';
const POOL = ['Anna', 'Ben', 'Clara', 'Jonas', 'Mia', 'Leon'];
/* score: true means the event has a scoreline, so "Exact score" bets are possible. */
const EVENTS = [
  { name: 'Bayern – Dortmund', when: 'Sat, 18:30', opts: ['Bayern', 'Draw', 'Dortmund'], score: true },
  { name: 'Leipzig – Leverkusen', when: 'Sun, 15:30', opts: ['Leipzig', 'Draw', 'Leverkusen'], score: true },
  { name: 'Darts World Championship final', when: '3 Jan, 21:00', opts: ['Favourite wins', 'Underdog wins'], score: false }
];
/* Proof a real-life bet asks for. */
const PROOFS = { participants: 'Confirmed by participants', photo: 'Photo proof', video: 'Video proof' };
/* status key -> [label, pill style] */
const STATUS = {
  open: ['Open', 'open'], locked: ['Locked', 'wait'], resolving: ['Resolving', 'wait'], disputed: ['Disputed', 'bad'],
  resolved: ['Resolved', 'done'], void: ['Void', 'bad'], infeasible: ['Not feasible', 'bad']
};

/* db:    { profile{name}, users{id: name}, groups[], joinable[] (groups you can join by code) }
   Group: { id, name, desc, code, admin, limit (debt limit in euros, 0 = none), members[], bal{user: euros},
            ledger[{t, d{user: delta}, b?: bet id}], pay[{id, from, to, amt}], bets[] }
   Bet:   { id, type: 'real'|'event', mode: 'pick'|'score', name, desc, opts[], min, max, creator, status,
            deadline + proof (real) | event (event),
            entries[{u, s: stake, o: option index (pick) | tip: [home, away] (score)}],
            proposed?, result? (option index), score? ([home, away]), winners?[], deltas? } */
function seed() {
  const d = h => new Date(Date.now() + h * 3600e3).toISOString();
  return {
    profile: { name: 'You' },
    users: { me: 'You', anna: 'Anna', ben: 'Ben', clara: 'Clara', leon: 'Leon', mia: 'Mia' },
    groups: [
      { id: 'g1', name: 'Southside Flatmates', desc: 'Everything you can bet on in a shared flat', code: 'SOUT-4821', admin: 'me', limit: 500,
        members: ['me', 'anna', 'ben', 'clara'], bal: { me: 50, anna: 100, ben: 0, clara: -150 },
        ledger: [{ t: 'Bet “Will Ben run the half marathon in under 2 hours?” resolved', d: { anna: 100, me: 50, clara: -150 }, b: 'b0' }],
        pay: [],
        bets: [
          { id: 'b1', type: 'real', mode: 'pick', proof: 'participants', name: 'Will Ben cook for everyone by Sunday?', desc: 'Only counts if all four of us sit at the table.', opts: ['Yes', 'No'], min: 10, max: 100, deadline: d(96), creator: 'ben', status: 'open',
            entries: [{ u: 'ben', o: 0, s: 50 }, { u: 'anna', o: 1, s: 30 }] },
          { id: 'b2', type: 'event', mode: 'pick', name: 'Bayern – Dortmund: who wins?', desc: '', opts: ['Bayern', 'Draw', 'Dortmund'], min: 10, max: 50, event: 'Bayern – Dortmund · Sat, 18:30', creator: 'me', status: 'open',
            entries: [{ u: 'me', o: 0, s: 40 }, { u: 'clara', o: 2, s: 40 }] },
          { id: 'b4', type: 'event', mode: 'score', name: 'Leipzig – Leverkusen: exact score', desc: 'Closest tip wins.', opts: ['Leipzig', 'Draw', 'Leverkusen'], min: 10, max: 50, event: 'Leipzig – Leverkusen · Sun, 15:30', creator: 'clara', status: 'open',
            entries: [{ u: 'clara', tip: [2, 1], s: 20 }, { u: 'anna', tip: [1, 1], s: 20 }] },
          { id: 'b3', type: 'real', mode: 'pick', proof: 'video', name: 'Can Anna do 10 pull-ups in a row?', desc: 'One clean set, no kipping.', opts: ['Yes', 'No'], min: 10, max: 50, deadline: d(-2), creator: 'anna', status: 'resolving', proposed: 0,
            entries: [{ u: 'anna', o: 0, s: 20 }, { u: 'me', o: 1, s: 20 }, { u: 'ben', o: 1, s: 10 }] },
          { id: 'b0', type: 'real', mode: 'pick', proof: 'photo', name: 'Will Ben run the half marathon in under 2 hours?', desc: '', opts: ['Yes', 'No'], min: 10, max: 200, deadline: d(-200), creator: 'clara', status: 'resolved', result: 0, winners: ['anna', 'me'],
            entries: [{ u: 'anna', o: 0, s: 100 }, { u: 'me', o: 0, s: 50 }, { u: 'clara', o: 1, s: 150 }], deltas: { anna: 100, me: 50, clara: -150 } }
        ] },
      { id: 'g2', name: 'Football Crew', desc: '', code: 'FOOT-1907', admin: 'me', limit: 500, members: ['me'], bal: { me: 0 }, ledger: [], pay: [], bets: [] }
    ],
    joinable: [
      { id: 'g3', name: 'Sunday Kickers', desc: 'Five-a-side on Sundays, bets on everything around it', code: 'KICK-3305', admin: 'leon', limit: 200,
        members: ['leon', 'mia'], bal: { leon: 0, mia: 0 }, ledger: [], pay: [],
        bets: [
          { id: 'k1', type: 'real', mode: 'pick', proof: 'participants', name: 'Will Mia score on Sunday?', desc: '', opts: ['Yes', 'No'], min: 5, max: 30, deadline: d(120), creator: 'leon', status: 'open',
            entries: [{ u: 'leon', o: 1, s: 10 }, { u: 'mia', o: 0, s: 10 }] }
        ] }
    ]
  };
}
