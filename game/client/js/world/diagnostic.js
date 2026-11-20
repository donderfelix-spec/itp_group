// A walking diagnostic for the developers (M2-1.15).
//
// It only runs when the address of the page has the parameter `debug`, for
// example http://localhost:8000/?debug. Then it measures in this browser:
//   - how the `positions` messages of the server arrive while the player walks,
//   - how long a message to the server and back takes (a `hello` probe),
//   - how evenly the browser draws its frames,
//   - how smoothly the own character is drawn while it walks, starts and stops,
// and shows the numbers in a small panel with the buttons Copy, Reset and
// Hide (Hide folds the panel down to its title; the recording goes on).
//
// Without `debug` it does nothing at all: no handler on Game.net, no timer,
// no frame loop, no element, no message. It only puts its pure helper
// functions on Game.diagnostic, so the tests can call them.
//
// It decides nothing in the game and changes nothing in it: it only reads
// (AGENTS.md, rule 1). The report holds no player name, no lobby code and
// nothing secret.

window.Game = window.Game || {};

(function () {
  // ---- Settings ----------------------------------------------------------

  // The first moments of a walk are not judged: the character only starts
  // to glide once the server's answer to the key has arrived.
  const WALK_SETTLE_MS = 400;
  // A drawn character that moved less than this, in map units, stood still.
  const SAME_PLACE = 0.01;
  // After the key is released, the character counts as stopped once it has
  // not moved for this long. A walk counts as a start from standing only
  // when the character had not moved for this long before the key.
  const STOPPED_FOR_MS = 200;
  const LARGE_GAP_MS = 150;
  // On a connection with a large gap several times a second, the list of the
  // last large gaps holds only a few seconds. The rare long gaps (the ones
  // that make the character stop) get a list of their own.
  const LONG_GAP_MS = 250;
  const LAST_ONES_SHOWN = 12;
  // A frame is "uneven" when the character is drawn at less than half or
  // more than one and a half times the server's walking speed (90 units/s).
  const SLOW_SPEED = 45;
  const FAST_SPEED = 135;
  // Own steps between two messages: shorter ones are standing still, longer
  // ones are the server putting the player somewhere (JUMP_DISTANCE in
  // world.js), not a step.
  const SMALLEST_STEP = 0.5;
  const LONGEST_STEP = 60;

  const PROBE_EVERY_MS = 1000;
  const PROBE_LOST_AFTER_MS = 5000;
  // Every probe has its own name, which the server sends back: "debug0",
  // "debug1", ... up to "debug9999", then from "debug0" again. (A name is
  // 3 to 16 letters and digits, see server/protocol.py.)
  const PROBE_NAME = 'debug';
  const PROBE_NAMES = 10000;
  const REFRESH_EVERY_MS = 500;
  const COPIED_SHOWN_MS = 1500;
  // Shown in the panel and in the report: the tool cannot tell these apart.
  const WALL_NOTE = 'Walk in the open: pressing against a wall counts as a gap and a stall.';

  // Memory and the time a refresh of the panel takes stay bounded: older
  // samples are forgotten. On a screen with 60 frames per second every list
  // keeps about the last three minutes of walking. A faster screen fills
  // the frames sooner (at 120 frames per second they are 90 seconds), so
  // the report says how many seconds each full list covers.
  const MOST_FRAMES = 10800; // three minutes at 60 frames per second
  const MOST_MESSAGES = 2700; // three minutes at 15 `positions` messages per second
  const MOST_ROUND_TRIPS = 180; // three minutes at one probe per second

  // The buckets of the gap histogram, in ms. A gap belongs to the bucket
  // with from <= gap < to. About 67 ms is a message on time.
  const GAP_BUCKETS = [
    { label: '<20', from: 0, to: 20 }, // bunched: arrived together with the one before
    { label: '20–50', from: 20, to: 50 },
    { label: '50–90', from: 50, to: 90 }, // on time
    { label: '90–130', from: 90, to: 130 },
    { label: '130–200', from: 130, to: 200 },
    { label: '200–300', from: 200, to: 300 },
    { label: '300–500', from: 300, to: 500 },
    { label: '≥500', from: 500, to: Infinity },
  ];

  // ---- Pure helpers: statistics of a list of numbers ------------------------

  // The panel is refreshed twice a second over thousands of values, and the
  // tool must not disturb what it measures. So each list is sorted only once
  // per refresh, and the median, the percentiles and the largest value are
  // all read from that one sorted copy.

  // A sorted copy, smallest first; the list itself keeps its order. A
  // Float64Array sorts by number (a plain array would sort by text: 10
  // before 9).
  function sortedCopy(values) {
    return new Float64Array(values).sort();
  }

  // The middle value; for an even count the mean of the two middle ones.
  // Null for an empty list.
  function medianOfSorted(sorted) {
    if (sorted.length === 0) return null;
    const middle = Math.floor(sorted.length / 2);
    if (sorted.length % 2 === 1) return sorted[middle];
    return (sorted[middle - 1] + sorted[middle]) / 2;
  }

  // The smallest value that at least `percent` % of the values are not
  // above ("nearest rank"). It is always one of the values, also in a short
  // list: the 95th percentile of 3 values is the largest. Null when empty.
  function percentileOfSorted(sorted, percent) {
    if (sorted.length === 0) return null;
    const rank = Math.ceil((percent / 100) * sorted.length);
    return sorted[Math.max(0, rank - 1)];
  }

  function largestOfSorted(sorted) {
    return sorted.length === 0 ? null : sorted[sorted.length - 1];
  }

  function median(values) {
    return medianOfSorted(sortedCopy(values));
  }

  function percentile(values, percent) {
    return percentileOfSorted(sortedCopy(values), percent);
  }

  // Not Math.max(...values): a very long list would be too many arguments.
  function maximum(values) {
    if (values.length === 0) return null;
    let largest = values[0];
    values.forEach((value) => {
      if (value > largest) largest = value;
    });
    return largest;
  }

  function summary(values) {
    const sorted = sortedCopy(values);
    return {
      count: sorted.length,
      median: medianOfSorted(sorted),
      p95: percentileOfSorted(sorted, 95),
      max: largestOfSorted(sorted),
    };
  }

  function countAbove(values, limit) {
    let count = 0;
    values.forEach((value) => {
      if (value > limit) count += 1;
    });
    return count;
  }

  // How many values fall into each bucket: [{label, count}].
  function histogram(values, buckets) {
    const used = buckets || GAP_BUCKETS;
    const counts = used.map((bucket) => ({ label: bucket.label, count: 0 }));
    values.forEach((value) => {
      const index = used.findIndex((bucket) => value >= bucket.from && value < bucket.to);
      if (index !== -1) counts[index].count += 1;
    });
    return counts;
  }

  function lastOnes(list) {
    return list.slice(-LAST_ONES_SHOWN);
  }

  // ---- Pure helpers: walking ------------------------------------------------

  function isWalkingDirection(direction) {
    return Boolean(direction) && (direction.dx !== 0 || direction.dy !== 0);
  }

  // Since when the player has been walking without a break, or null while
  // the direction is (0, 0). `direction` is what Game.world.walkingDirection()
  // returns: {dx, dy, since}. world.js sets `since` at the key itself, so a
  // release and a new key between two frames is still seen as a new walk.
  function walkingSinceOf(direction) {
    if (!isWalkingDirection(direction) || typeof direction.since !== 'number') return null;
    return direction.since;
  }

  function hasPosition(sample) {
    return typeof sample.x === 'number' && typeof sample.y === 'number';
  }

  // Pythagoras; `** 0.5` is the square root. Not Math.hypot: it is many times
  // slower, and this runs for every frame kept each time the panel is refreshed.
  function distance(a, b) {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    return (dx * dx + dy * dy) ** 0.5;
  }

  function hasMoved(previous, current) {
    return hasPosition(previous) && hasPosition(current) && distance(previous, current) >= SAME_PLACE;
  }

  // The own entry {x, y} in a `positions` message, or null.
  function ownPositionIn(message, ownName) {
    const players = message && Array.isArray(message.players) ? message.players : [];
    const own = players.find((entry) => entry && entry.name === ownName);
    if (!own || typeof own.x !== 'number' || typeof own.y !== 'number') return null;
    return { x: own.x, y: own.y };
  }

  // ---- Pure helpers: messages -------------------------------------------------

  // `messages` is [{time, walkingSince}] in the order they arrived. A gap
  // counts only when the player walked at both messages without a break in
  // between (the same `walkingSince`, see walkingSinceOf): the server sends
  // positions only when somebody moves, so a gap while standing means nothing.
  // Returns [{at, gap}]: `at` is the arrival of the later message.
  function walkingGaps(messages) {
    const gaps = [];
    for (let i = 1; i < messages.length; i++) {
      const before = messages[i - 1];
      const after = messages[i];
      if (before.walkingSince !== null && before.walkingSince === after.walkingSince) {
        gaps.push({ at: after.time, gap: after.time - before.time });
      }
    }
    return gaps;
  }

  // Messages per second during the walking gaps.
  function messagesPerSecond(gapLengths) {
    const total = gapLengths.reduce((sum, gap) => sum + gap, 0);
    return total > 0 ? gapLengths.length / (total / 1000) : null;
  }

  // How far the own player got from one message to the next, in map units.
  // `messages` is [{own}], `own` being {x, y} or null. Only real steps count.
  function ownSteps(messages) {
    const withOwn = messages.filter((message) => message.own);
    const steps = [];
    for (let i = 1; i < withOwn.length; i++) {
      const step = distance(withOwn[i - 1].own, withOwn[i].own);
      if (step > SMALLEST_STEP && step <= LONGEST_STEP) steps.push(step);
    }
    return steps;
  }

  // ---- Pure helpers: frames ---------------------------------------------------

  // `frames` is [{time, x, y, walkingSince}]: one per frame, x and y where
  // the own character was drawn (null without a position), walkingSince as
  // walkingSinceOf() gave it in that frame.

  function frameTimes(frames) {
    const times = [];
    for (let i = 1; i < frames.length; i++) times.push(frames[i].time - frames[i - 1].time);
    return times;
  }

  // A frame is judged when the player has walked for WALK_SETTLE_MS without
  // a break and the character is drawn in this frame and the one before.
  function isJudged(previous, frame) {
    const settled = frame.walkingSince !== null && frame.time - frame.walkingSince >= WALK_SETTLE_MS;
    return settled && hasPosition(previous) && hasPosition(frame);
  }

  // Frozen frames are judged frames in which the character did not move. A
  // stall is a run of at least 2 of them that ends with the character moving
  // again in the same walk. (A run that ends because the key was released is
  // more likely a wall than a stall.) Its length runs from the last frame
  // that moved to the first frame that moves again.
  // Returns {walkingFrames, frozenFrames, walkingMs, stalls: [{at, length}]}.
  function stallsOf(frames) {
    const result = { walkingFrames: 0, frozenFrames: 0, walkingMs: 0, stalls: [] };
    let lastMovedAt = null;
    let frozenRun = 0;
    let runStartedAt = 0;
    for (let i = 1; i < frames.length; i++) {
      const previous = frames[i - 1];
      const frame = frames[i];
      const judged = isJudged(previous, frame);
      const moved = hasMoved(previous, frame);
      if (judged) {
        result.walkingFrames += 1;
        result.walkingMs += frame.time - previous.time;
      }
      if (judged && !moved) {
        if (frozenRun === 0) runStartedAt = stallStart(lastMovedAt, previous, frame);
        frozenRun += 1;
        result.frozenFrames += 1;
      } else {
        if (frozenRun >= 2 && judged) result.stalls.push({ at: runStartedAt, length: frame.time - runStartedAt });
        frozenRun = 0;
      }
      if (moved) lastMovedAt = frame.time;
    }
    return result;
  }

  // Where a stall began: the last frame that moved, but not before this walk
  // began (a character that has not moved since then is late to start).
  function stallStart(lastMovedAt, previous, frame) {
    const lastMoved = lastMovedAt === null ? previous.time : lastMovedAt;
    return Math.max(lastMoved, frame.walkingSince);
  }

  // The speed at which the character is drawn in each judged frame, in map
  // units per second.
  function drawnSpeeds(frames) {
    const speeds = [];
    for (let i = 1; i < frames.length; i++) {
      const previous = frames[i - 1];
      const frame = frames[i];
      const milliseconds = frame.time - previous.time;
      if (isJudged(previous, frame) && milliseconds > 0) {
        speeds.push(distance(previous, frame) / (milliseconds / 1000));
      }
    }
    return speeds;
  }

  function unevenPercent(speeds) {
    if (speeds.length === 0) return null;
    const uneven = speeds.filter((speed) => speed < SLOW_SPEED || speed > FAST_SPEED).length;
    return (100 * uneven) / speeds.length;
  }

  // For every walk that began while the character stood: the time from the
  // key (walkingSince) to the first later frame in which the character
  // moves. In ms. A walk that began while the character was still gliding
  // out of the walk before (a quick turn) is not a start: the character
  // "moves" in the very next frame, whatever the connection does.
  function startDelays(frames) {
    const delays = [];
    let waitingSince = null; // the key of a start that has not moved yet
    // Since when the character has not been seen moving: at first only
    // since the first frame, later since the last frame in which it moved.
    let stillSince = frames.length > 0 ? frames[0].time : null;
    for (let i = 1; i < frames.length; i++) {
      const previous = frames[i - 1];
      const frame = frames[i];
      const moved = hasMoved(previous, frame);
      if (moved) stillSince = frame.time;
      if (frame.walkingSince !== previous.walkingSince) {
        // A walk began or ended, or both, since the frame before.
        waitingSince = isStartFromStanding(frame, stillSince) ? frame.walkingSince : null;
      } else if (waitingSince !== null && moved) {
        delays.push(frame.time - waitingSince);
        waitingSince = null;
      }
    }
    return delays;
  }

  // Did a walk begin in this frame with the character standing for
  // STOPPED_FOR_MS before the key? (A move in this same frame counts as
  // "still moving": the server cannot have answered the key yet.)
  function isStartFromStanding(frame, stillSince) {
    return frame.walkingSince !== null && frame.walkingSince - stillSince >= STOPPED_FOR_MS;
  }

  // For every stop (direction back to zero): how far the character still
  // went and for how long, until it had not moved for STOPPED_FOR_MS.
  // A stop is dropped when the player walks again before that.
  // Returns [{distance, duration}].
  function stops(frames) {
    const found = [];
    let stop = null; // {startedAt, distance, lastMovedAt} while it settles
    for (let i = 1; i < frames.length; i++) {
      const previous = frames[i - 1];
      const frame = frames[i];
      if (frame.walkingSince !== null) {
        stop = null;
      } else if (previous.walkingSince !== null) {
        stop = { startedAt: frame.time, distance: 0, lastMovedAt: frame.time };
      } else if (stop && hasMoved(previous, frame)) {
        stop.distance += distance(previous, frame);
        stop.lastMovedAt = frame.time;
      } else if (stop && frame.time - stop.lastMovedAt >= STOPPED_FOR_MS) {
        found.push({ distance: stop.distance, duration: stop.lastMovedAt - stop.startedAt });
        stop = null;
      }
    }
    return found;
  }

  // ---- Pure helpers: all numbers and the text --------------------------------

  // `recording` is {startedAt, tabWasHidden, frames, messages, roundTrips,
  // lostProbes}; `now` is the time of the report.
  function summarize(recording, now) {
    const secondsIn = (time) => (time - recording.startedAt) / 1000;
    return {
      recordedSeconds: (now - recording.startedAt) / 1000,
      fullBuffers: fullBuffers(recording, now),
      tabWasHidden: recording.tabWasHidden,
      walkingGaps: gapNumbers(walkingGaps(recording.messages), secondsIn),
      ownStep: shortSummary(ownSteps(recording.messages)),
      roundTrip: Object.assign(summary(recording.roundTrips), { lost: recording.lostProbes }),
      frames: frameNumbers(frameTimes(recording.frames)),
      walking: walkingNumbers(recording.frames, secondsIn),
      startDelay: shortSummary(startDelays(recording.frames)),
      stop: stopNumbers(stops(recording.frames)),
    };
  }

  // Which lists are full. Their numbers then cover only the newest part of
  // the recording: the last `kept` entries, which are the last `seconds`.
  // Returns [{what, kept, seconds}]; round trips carry no time, so no seconds.
  function fullBuffers(recording, now) {
    const full = [];
    const secondsSince = (sample) => (now - sample.time) / 1000;
    if (recording.frames.length >= MOST_FRAMES) {
      full.push({ what: 'frames', kept: MOST_FRAMES, seconds: secondsSince(recording.frames[0]) });
    }
    if (recording.messages.length >= MOST_MESSAGES) {
      full.push({ what: 'positions messages', kept: MOST_MESSAGES, seconds: secondsSince(recording.messages[0]) });
    }
    if (recording.roundTrips.length >= MOST_ROUND_TRIPS) {
      full.push({ what: 'round trips', kept: MOST_ROUND_TRIPS, seconds: null });
    }
    return full;
  }

  function shortSummary(values) {
    const sorted = sortedCopy(values);
    return { count: sorted.length, median: medianOfSorted(sorted), max: largestOfSorted(sorted) };
  }

  function speedNumbers(speeds) {
    const sorted = sortedCopy(speeds);
    return { median: medianOfSorted(sorted), p5: percentileOfSorted(sorted, 5), p95: percentileOfSorted(sorted, 95) };
  }

  function gapNumbers(gaps, secondsIn) {
    const lengths = gaps.map((gap) => gap.gap);
    return Object.assign(summary(lengths), {
      perSecond: messagesPerSecond(lengths),
      histogram: histogram(lengths),
      largeGaps: lastGapsFrom(gaps, LARGE_GAP_MS, secondsIn),
      longGaps: lastGapsFrom(gaps, LONG_GAP_MS, secondsIn),
    });
  }

  // The last gaps of at least `limit` ms, oldest first: [{atSeconds, ms}].
  function lastGapsFrom(gaps, limit, secondsIn) {
    const found = lastOnes(gaps.filter((gap) => gap.gap >= limit));
    return found.map((gap) => ({ atSeconds: secondsIn(gap.at), ms: gap.gap }));
  }

  function frameNumbers(times) {
    return Object.assign(summary(times), { over25: countAbove(times, 25), over50: countAbove(times, 50) });
  }

  function walkingNumbers(frames, secondsIn) {
    const found = stallsOf(frames);
    const speeds = drawnSpeeds(frames);
    const lengths = found.stalls.map((stall) => stall.length);
    return {
      frames: found.walkingFrames,
      frozenFrames: found.frozenFrames,
      stalls: found.stalls.length,
      stallsPerSecond: found.walkingMs > 0 ? found.stalls.length / (found.walkingMs / 1000) : null,
      longestStallMs: maximum(lengths),
      lastStalls: lastOnes(found.stalls).map((stall) => ({ atSeconds: secondsIn(stall.at), ms: stall.length })),
      speed: speedNumbers(speeds),
      unevenPercent: unevenPercent(speeds),
    };
  }

  function stopNumbers(found) {
    return {
      distance: shortSummary(found.map((stop) => stop.distance)),
      duration: shortSummary(found.map((stop) => stop.duration)),
    };
  }

  // A number with one decimal, or "-" when there is none yet.
  function shown(value, decimals) {
    if (value === null || value === undefined) return '-';
    return value.toFixed(decimals === undefined ? 1 : decimals);
  }

  function shownSummary(numbers) {
    return 'median ' + shown(numbers.median) + ', p95 ' + shown(numbers.p95) + ', max ' + shown(numbers.max);
  }

  function shownMoments(list) {
    if (list.length === 0) return 'none';
    return list.map((item) => 'at ' + shown(item.atSeconds) + ' s: ' + shown(item.ms, 0) + ' ms').join(', ');
  }

  // The numbers as lines of text, for the panel and the report.
  function numberLines(numbers) {
    const gaps = numbers.walkingGaps;
    const trip = numbers.roundTrip;
    const frames = numbers.frames;
    const walk = numbers.walking;
    return [
      WALL_NOTE,
      // A hidden tab draws no frames and delays its timers: its numbers mislead.
      'Tab hidden during recording: ' + (numbers.tabWasHidden ? 'yes' : 'no'),
      'Positions messages while walking',
      '  walking gaps: ' + gaps.count + ', messages per second: ' + shown(gaps.perSecond),
      '  gap ms: ' + shownSummary(gaps),
      '  histogram ms: ' + gaps.histogram.map((bucket) => bucket.label + ': ' + bucket.count).join(' | '),
      '  last large gaps (>= ' + LARGE_GAP_MS + ' ms): ' + shownMoments(gaps.largeGaps),
      '  last long gaps (>= ' + LONG_GAP_MS + ' ms): ' + shownMoments(gaps.longGaps),
      '  own step per message (units): count ' + numbers.ownStep.count + ', median ' + shown(numbers.ownStep.median, 2) +
        ', max ' + shown(numbers.ownStep.max, 2),
      'Round trip (hello to welcome)',
      '  answered: ' + trip.count + ', lost: ' + trip.lost + ', ms: ' + shownSummary(trip),
      'Frames',
      '  frames: ' + frames.count + ', ms: ' + shownSummary(frames),
      '  longer than 25 ms: ' + frames.over25 + ', longer than 50 ms: ' + frames.over50,
      'Own character while walking',
      '  walking frames: ' + walk.frames + ', frozen frames: ' + walk.frozenFrames,
      '  stalls: ' + walk.stalls + ', per second of walking: ' + shown(walk.stallsPerSecond, 2) +
        ', longest ms: ' + shown(walk.longestStallMs, 0),
      '  last stalls: ' + shownMoments(walk.lastStalls),
      '  drawn speed (units/s): median ' + shown(walk.speed.median) + ', p5 ' + shown(walk.speed.p5) +
        ', p95 ' + shown(walk.speed.p95) + ', uneven frames: ' + shown(walk.unevenPercent) + ' %',
      'Start and stop',
      '  start delay ms: count ' + numbers.startDelay.count + ', median ' + shown(numbers.startDelay.median, 0) +
        ', max ' + shown(numbers.startDelay.max, 0),
      '  stop distance units: count ' + numbers.stop.distance.count + ', median ' + shown(numbers.stop.distance.median, 2) +
        ', max ' + shown(numbers.stop.distance.max, 2),
      '  stop time ms: count ' + numbers.stop.duration.count + ', median ' + shown(numbers.stop.duration.median, 0) +
        ', max ' + shown(numbers.stop.duration.max, 0),
    ];
  }

  // Says which lists are full and what their numbers then cover, for example
  // "Buffers full: frames: the last 10800 only (180.0 s)".
  function fullBuffersLine(full) {
    if (full.length === 0) return 'Buffers full: none';
    const parts = full.map((buffer) => {
      const seconds = buffer.seconds === null ? '' : ' (' + shown(buffer.seconds) + ' s)';
      return buffer.what + ': the last ' + buffer.kept + ' only' + seconds;
    });
    return 'Buffers full: ' + parts.join('; ');
  }

  // The first lines of the report: what browser and screen it came from.
  // `facts` is {date, userAgent, devicePixelRatio, canvas}; canvas is
  // {width, height, pageWidth, pageHeight} or null.
  function headerLines(facts, numbers) {
    const canvas = facts.canvas;
    const canvasText = canvas
      ? canvas.width + ' x ' + canvas.height + ' pixels (' + canvas.pageWidth + ' x ' + canvas.pageHeight + ' on the page)'
      : 'none';
    return [
      'Group Project walking diagnostic',
      'Date: ' + facts.date,
      'Recorded: ' + shown(numbers.recordedSeconds) + ' s',
      fullBuffersLine(numbers.fullBuffers),
      'Browser: ' + facts.userAgent,
      'Device pixel ratio: ' + facts.devicePixelRatio,
      'Canvas: ' + canvasText,
    ];
  }

  function reportText(facts, numbers) {
    return headerLines(facts, numbers).concat(numberLines(numbers)).join('\n');
  }

  function isDebugAddress(search) {
    return new URLSearchParams(search).has('debug');
  }

  Game.diagnostic = {
    active: false,
    GAP_BUCKETS: GAP_BUCKETS,
    MOST_FRAMES: MOST_FRAMES,
    MOST_MESSAGES: MOST_MESSAGES,
    MOST_ROUND_TRIPS: MOST_ROUND_TRIPS,
    median: median,
    percentile: percentile,
    maximum: maximum,
    histogram: histogram,
    walkingSinceOf: walkingSinceOf,
    ownPositionIn: ownPositionIn,
    walkingGaps: walkingGaps,
    messagesPerSecond: messagesPerSecond,
    ownSteps: ownSteps,
    frameTimes: frameTimes,
    stallsOf: stallsOf,
    drawnSpeeds: drawnSpeeds,
    unevenPercent: unevenPercent,
    startDelays: startDelays,
    stops: stops,
    summarize: summarize,
    reportText: reportText,
    isDebugAddress: isDebugAddress,
  };

  // Everything below runs only with `?debug`.
  if (!isDebugAddress(location.search)) return;

  // ---- Recording ------------------------------------------------------------

  let recording = null;
  let ownName = null; // only to find the own entry in `positions`; never shown
  let probeInFlight = null; // {name, sentAt}, or null: never more than one
  let probesSent = 0; // numbers the probes, see PROBE_NAME

  function newRecording(now) {
    return {
      startedAt: now,
      tabWasHidden: document.hidden === true,
      frames: [],
      messages: [],
      roundTrips: [],
      lostProbes: 0,
    };
  }

  // Adds `item` and forgets the oldest entry once there are more than `most`.
  function pushBounded(list, item, most) {
    list.push(item);
    if (list.length > most) list.shift();
  }

  // The world may be missing (world.js failed to load): then nobody walks
  // and nothing is drawn.
  function currentDirection() {
    const world = Game.world;
    return world && typeof world.walkingDirection === 'function' ? world.walkingDirection() : null;
  }

  function ownDrawnPosition(now) {
    const world = Game.world;
    return world && typeof world.ownDrawnPosition === 'function' ? world.ownDrawnPosition(now) : null;
  }

  function whenPositions(message) {
    const sample = {
      time: performance.now(),
      walkingSince: walkingSinceOf(currentDirection()),
      own: ownPositionIn(message, ownName),
    };
    pushBounded(recording.messages, sample, MOST_MESSAGES);
  }

  function onFrame(now) {
    window.requestAnimationFrame(onFrame);
    const position = ownDrawnPosition(now);
    const frame = {
      time: now,
      x: position ? position.x : null,
      y: position ? position.y : null,
      walkingSince: walkingSinceOf(currentDirection()),
    };
    pushBounded(recording.frames, frame, MOST_FRAMES);
  }

  // Once per second: a `hello`, which the server answers with `welcome` and
  // nothing else. A probe without an answer after PROBE_LOST_AFTER_MS is lost.
  function probe() {
    const now = performance.now();
    if (probeInFlight !== null) {
      if (now - probeInFlight.sentAt < PROBE_LOST_AFTER_MS) return; // still waiting for it
      recording.lostProbes += 1;
      probeInFlight = null;
    }
    const name = PROBE_NAME + (probesSent % PROBE_NAMES);
    // send() is false without a connection: then nothing is in flight.
    if (Game.net.send({ type: 'hello', name: name })) {
      probeInFlight = { name: name, sentAt: now };
      probesSent += 1;
    }
  }

  // Only the answer that carries the name of the probe in flight counts. A
  // late answer to a probe given up as lost has an older name: counted, it
  // would make the round trip of the next probe look far too short.
  function whenWelcome(message) {
    if (probeInFlight === null || !message || message.name !== probeInFlight.name) return;
    pushBounded(recording.roundTrips, performance.now() - probeInFlight.sentAt, MOST_ROUND_TRIPS);
    probeInFlight = null;
  }

  // The connection is gone, and with it the answer to the probe in flight.
  // That says nothing about a lost message, so it is forgotten, not counted.
  function whenConnectionCloses() {
    probeInFlight = null;
  }

  function whenVisibilityChanges() {
    if (document.hidden) recording.tabWasHidden = true;
  }

  // ---- What other code (and the measuring script) can ask --------------------

  function canvasFacts() {
    const canvas = document.getElementById('map');
    if (!canvas) return null;
    return { width: canvas.width, height: canvas.height, pageWidth: canvas.clientWidth, pageHeight: canvas.clientHeight };
  }

  function facts() {
    return {
      date: new Date().toString(),
      userAgent: navigator.userAgent,
      devicePixelRatio: window.devicePixelRatio || 1,
      canvas: canvasFacts(),
    };
  }

  function numbers() {
    return Object.assign(facts(), summarize(recording, performance.now()));
  }

  function report() {
    return reportText(facts(), summarize(recording, performance.now()));
  }

  function reset() {
    recording = newRecording(performance.now());
    probeInFlight = null; // an answer to an earlier probe is not counted
    refreshPanel(); // at once: the old numbers must not stay until the next refresh
  }

  // ---- The panel ------------------------------------------------------------

  let panelTitle = null;
  let panelNumbers = null;
  let isCollapsed = false; // true after "Hide": only the title and the buttons show

  // The title and the buttons come first and the numbers below them: the
  // panel cannot be scrolled (it lets the mouse through), so in a low window
  // its lower end is cut off. That must never be the buttons.
  function makePanel() {
    const panel = document.createElement('div');
    Object.assign(panel.style, {
      position: 'fixed', top: '4px', left: '4px', zIndex: '1000',
      maxWidth: '460px', maxHeight: 'calc(100vh - 8px)', overflow: 'hidden',
      padding: '6px 8px', background: 'rgba(20, 20, 30, 0.82)', color: '#f4efe3',
      font: '11px/1.35 ui-monospace, Menlo, Consolas, monospace', borderRadius: '4px',
      // Clicks go through the text to the game below; only the buttons catch them.
      pointerEvents: 'none',
    });
    panelTitle = document.createElement('div');
    panel.appendChild(panelTitle);
    const buttons = document.createElement('div');
    buttons.style.margin = '4px 0';
    buttons.appendChild(makeButton('Copy', copyReport));
    buttons.appendChild(makeButton('Reset', reset));
    buttons.appendChild(makeButton('Hide', hideOrShow));
    panel.appendChild(buttons);
    panelNumbers = document.createElement('pre');
    Object.assign(panelNumbers.style, { margin: '0', whiteSpace: 'pre-wrap', font: 'inherit' });
    panel.appendChild(panelNumbers);
    document.body.appendChild(panel);
  }

  // The buttons are never reached with Tab, and give up the focus after a
  // click, like "E Use" in world.js: Space and Enter would otherwise click
  // them again, and the walking keys must keep working.
  function makeButton(text, action) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = text;
    button.tabIndex = -1;
    Object.assign(button.style, {
      font: 'inherit', marginRight: '6px', padding: '1px 8px', cursor: 'pointer', pointerEvents: 'auto',
    });
    button.addEventListener('click', () => {
      button.blur();
      action(button);
    });
    return button;
  }

  function refreshPanel() {
    const now = performance.now();
    panelTitle.textContent = 'Walking diagnostic, ' + shown((now - recording.startedAt) / 1000) + ' s recorded';
    if (isCollapsed) {
      // No numbers are worked out while they are not shown: the recording
      // goes on, and Copy and Show work them out when they are asked for.
      panelNumbers.textContent = '';
      return;
    }
    const all = summarize(recording, now);
    const lines = [];
    if (all.fullBuffers.length > 0) lines.push(fullBuffersLine(all.fullBuffers));
    panelNumbers.textContent = lines.concat(numberLines(all)).join('\n');
  }

  // The panel covers a part of the map: "Hide" folds it down to its title
  // line and the buttons, "Show" brings the numbers back.
  function hideOrShow(button) {
    isCollapsed = !isCollapsed;
    button.textContent = isCollapsed ? 'Show' : 'Hide';
    refreshPanel();
  }

  function copyReport(button) {
    const text = report();
    const tell = (worked) => showForAMoment(button, worked ? 'Copied' : 'Copy failed');
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      navigator.clipboard.writeText(text).then(() => tell(true), () => tell(copyWithTextarea(text)));
    } else {
      tell(copyWithTextarea(text));
    }
  }

  // The older way to copy, for browsers that refuse the clipboard (for
  // example on a page without https): select the text in a hidden field.
  function copyWithTextarea(text) {
    const field = document.createElement('textarea');
    field.value = text;
    Object.assign(field.style, { position: 'fixed', top: '0', left: '-9999px', opacity: '0' });
    document.body.appendChild(field);
    field.select();
    let worked = false;
    try {
      worked = document.execCommand('copy') === true;
    } catch (problem) {
      worked = false;
    }
    field.remove(); // with it the focus goes back to the page
    return worked;
  }

  function showForAMoment(button, text) {
    button.textContent = text;
    window.setTimeout(() => {
      button.textContent = 'Copy';
    }, COPIED_SHOWN_MS);
  }

  // ---- Start ----------------------------------------------------------------

  recording = newRecording(performance.now());
  Game.net.on('signed_in', (message) => {
    ownName = message.name;
  });
  Game.net.on('signed_out', () => {
    ownName = null;
  });
  Game.net.on('positions', whenPositions);
  Game.net.on('welcome', whenWelcome);
  Game.net.on('close', whenConnectionCloses);
  document.addEventListener('visibilitychange', whenVisibilityChanges);
  makePanel();
  refreshPanel();
  window.setInterval(refreshPanel, REFRESH_EVERY_MS);
  window.setInterval(probe, PROBE_EVERY_MS);
  window.requestAnimationFrame(onFrame);

  Object.assign(Game.diagnostic, { active: true, report: report, numbers: numbers, reset: reset });
})();
