// Bridging the gaps (M2-1.16): the plain rules with which the own character
// walks on by itself while the server's positions are held up.
//
// Over the internet the `positions` messages sometimes stop for a moment
// (260 to 690 ms measured) and then arrive all at once. The own character
// and the camera would stand that long. So world.js lets the own character
// walk on with the server's own movement rule, for at most about 700 ms.
// When the server's positions arrive, they take the place of the steps the
// browser made up, one by one.
//
// The server still decides every position (AGENTS.md, rule 1). The browser
// only fills in what the server is computing anyway, sends nothing new, and
// the character always ends on the server's position.
//
// Everything in this file is a plain function: no page, no canvas and no
// clock. Times are passed in, so the tests can call every function directly
// (tests/bridge_in_node.js).

"use strict";

window.Game = window.Game || {};
Game.world = Game.world || {};

(function () {
  // ---- The server's movement rule ---------------------------------------

  // step() below is a line-by-line copy of step() in
  // server/world/movement.py: the same numbers, the same arithmetic in the
  // same order. CHANGE BOTH TOGETHER. tests/test_bridge_rule.py runs
  // thousands of random steps through both and fails when they differ.

  // The player is a square of 10 x 10 units around its position.
  var PLAYER_HALF_SIZE = 5;
  // Units of the map per second, the same in every direction.
  var PLAYER_SPEED = 90;
  // The longest time one step may cover.
  var MAX_STEP_SECONDS = 0.1;

  // Moves a player for `seconds` and returns the new position {x, y}.
  // `dx` and `dy` say where the player wants to go: -1, 0 or 1 on each axis.
  // The player stops at solids and at the edge of the map.
  function step(x, y, dx, dy, seconds, solids, mapWidth, mapHeight) {
    if (!isFiniteNumber(x) || !isFiniteNumber(y)) {
      throw new Error("A player's position must be two finite numbers.");
    }
    // A solid the player already overlaps does not block this step, so the
    // player can walk out of it instead of being stuck forever.
    var blocking = solids.filter(function (solid) {
      return !overlaps(x, y, solid);
    });

    dx = direction(dx);
    dy = direction(dy);
    var distance = PLAYER_SPEED * capped(seconds);
    if (dx !== 0 && dy !== 0) {
      // A diagonal step is split over both axes so that it is not faster
      // than a straight one (Pythagoras: side = diagonal / sqrt(2)).
      distance = distance / Math.sqrt(2);
    }

    // One axis after the other: when a wall blocks one axis, the other axis
    // still moves, so the player slides along the wall instead of sticking.
    x = moveOnAxis("x", x, y, dx, distance, blocking, mapWidth);
    y = moveOnAxis("y", y, x, dy, distance, blocking, mapHeight);
    return { x: x, y: y };
  }

  // Does the player square at (x, y) overlap this solid? Touching is not
  // overlapping.
  function overlaps(x, y, solid) {
    return (
      x + PLAYER_HALF_SIZE > solid.x &&
      x - PLAYER_HALF_SIZE < solid.x + solid.w &&
      y + PLAYER_HALF_SIZE > solid.y &&
      y - PLAYER_HALF_SIZE < solid.y + solid.h
    );
  }

  function isFiniteNumber(value) {
    return typeof value === "number" && isFinite(value);
  }

  // Turns what the player wants into exactly -1, 0 or 1.
  function direction(value) {
    if (typeof value !== "number") {
      return 0;
    }
    // Only comparisons: every comparison with NaN is false, so NaN ends as 0.
    if (value > 0) {
      return 1;
    }
    if (value < 0) {
      return -1;
    }
    return 0;
  }

  // The time this step may cover: never negative, never more than the cap.
  function capped(seconds) {
    if (typeof seconds !== "number") {
      return 0;
    }
    // Written as "not above 0" so that NaN counts as no time.
    if (!(seconds > 0)) {
      return 0;
    }
    if (seconds > MAX_STEP_SECONDS) {
      return MAX_STEP_SECONDS;
    }
    return seconds;
  }

  // Moves along one axis and stops at the first solid or at the edge of the
  // map. `position` is the coordinate on the axis that moves,
  // `otherPosition` the coordinate on the axis that stays.
  function moveOnAxis(axis, position, otherPosition, wanted, distance, solids, mapSize) {
    if (wanted === 0 || distance === 0) {
      return position;
    }
    var along = axis === "x" ? "x" : "y";
    var length = axis === "x" ? "w" : "h";
    var across = axis === "x" ? "y" : "x";
    var breadth = axis === "x" ? "h" : "w";

    // The lowest and highest coordinate the player's centre may have.
    var lowest = PLAYER_HALF_SIZE;
    var highest = mapSize - PLAYER_HALF_SIZE;

    for (var i = 0; i < solids.length; i++) {
      var solid = solids[i];
      // A solid that lies beside the player's lane cannot stop this move.
      var beside =
        solid[across] >= otherPosition + PLAYER_HALF_SIZE ||
        solid[across] + solid[breadth] <= otherPosition - PLAYER_HALF_SIZE;
      if (beside) {
        continue;
      }
      var nearSide = solid[along];
      var farSide = solid[along] + solid[length];
      // Only solids ahead of the player count, not those already behind.
      if (wanted > 0 && farSide > position - PLAYER_HALF_SIZE) {
        highest = Math.min(highest, nearSide - PLAYER_HALF_SIZE);
      }
      if (wanted < 0 && nearSide < position + PLAYER_HALF_SIZE) {
        lowest = Math.max(lowest, farSide + PLAYER_HALF_SIZE);
      }
    }

    // A blocked player stays where they are and is never pushed backwards.
    if (wanted > 0) {
      return Math.max(position, Math.min(position + distance, highest));
    }
    return Math.min(position, Math.max(position - distance, lowest));
  }

  // ---- Settings of the bridge --------------------------------------------

  // At most this many bridged steps wait for the server: about 700 ms.
  // After a longer hold-up the character stands, as it did before.
  var MOST_BRIDGED_STEPS = 10;
  // The first step of a bridge is drawn this much slower than the server
  // walks. Often the positions are not held up but only a little later
  // than the queue expected (the connection got slower, or the server
  // skipped this browser for a tick). Then each position arrives a moment
  // after the glide before it ended. At the server's exact pace the bridge
  // would step in before every single one, for the rest of the walk, and
  // guess every turn a step late (the input lag assumes the queue's usual
  // wait). On the slower first step the next position arrives before the
  // glide is over, so the queue takes over again and rebuilds its delay.
  var FIRST_STEP_SLOWER = 1.1;
  // A bridged step only follows a glide that ended at most this long ago.
  // After a hidden tab or a long pause the character does not walk on.
  var LONGEST_WAIT_MILLISECONDS = 250;
  // Bridged steps that the server has not answered after this time were
  // never walked by the server: they are taken back.
  var TAKE_BACK_MILLISECONDS = 1000;
  // Less than this, in map units, is the same place: far below one pixel.
  var SAME_PLACE = 0.05;
  // The server's ticks are not all equally long, so a bridged step can
  // differ from the server's by a little. Up to this difference, in map
  // units, the bridge was right about the walk; a larger one is a wrong
  // guess (the server stood, turned or met a wall).
  var SMALL_CORRECTION = 1.5;
  // A wrong guess is corrected within the time the glide has left, but
  // never faster than this, so it does not look like a jump.
  var SHORTEST_CORRECTION_MILLISECONDS = 50;
  // How many of the server's last steps tell how long its ticks are.
  var SERVER_STEPS_KEPT = 8;

  // The input lag before it was measured, and the limits of one sample.
  var START_DELAY_BEFORE_MEASURED = 100;
  var SHORTEST_START_DELAY = 30;
  var LONGEST_START_DELAY = 400;
  var START_DELAYS_KEPT = 5;
  // A walk starts "from standing" when the server has not moved the own
  // player for this long. Otherwise the first position that moves may still
  // belong to the walk before, and the sample would be far too short.
  var STANDING_MILLISECONDS = 400;

  // How many changes of direction are remembered, and for how long. The
  // bridge looks back by the input lag, at most about half a second.
  var DIRECTIONS_KEPT = 64;
  var DIRECTION_MEMORY_MILLISECONDS = 2000;

  // ---- The direction the player held a moment ago ------------------------

  // The drawn character is behind the keys: a key reaches the server after
  // the way there, takes effect at the server's next tick and is drawn
  // after the way back plus the queue's delay. A bridged step stands in for
  // a step of the server, so it must use the direction the server knew
  // then: the one the player held a little earlier, not the keys of this
  // instant.

  // `history` is the list of directions the browser reported to the server,
  // oldest first: [{time, dx, dy}]. Returns a new list with one more entry;
  // entries too old to be asked for are dropped.
  function rememberDirection(history, time, dx, dy) {
    var kept = history.concat([{ time: time, dx: dx, dy: dy }]);
    // The newest entry older than the memory is still the direction of
    // that time, so only the entries before it go.
    while (kept.length > 1 && kept[1].time < time - DIRECTION_MEMORY_MILLISECONDS) {
      kept.shift();
    }
    while (kept.length > DIRECTIONS_KEPT) {
      kept.shift();
    }
    return kept;
  }

  // The direction that was current at `time`: {dx, dy}. Before the first
  // entry, and with an empty history, the player stood: (0, 0).
  function directionAt(history, time) {
    var found = { dx: 0, dy: 0 };
    for (var i = 0; i < history.length && history[i].time <= time; i++) {
      found = { dx: history[i].dx, dy: history[i].dy };
    }
    return found;
  }

  function isStanding(someDirection) {
    return someDirection.dx === 0 && someDirection.dy === 0;
  }

  // Is the player walking at `time`, by the keys of that instant or by the
  // keys `inputLag` earlier? Then the server moves the own character (or is
  // about to, or still does), and a gap can be bridged.
  function isWalkingAt(history, time, inputLag) {
    return !isStanding(directionAt(history, time)) || !isStanding(directionAt(history, time - inputLag));
  }

  // ---- Measuring the input lag -------------------------------------------

  // Every time a walk starts from standing, the time from the key to the
  // arrival of the first own position that moved is one sample: the "start
  // delay".

  // The time of the key that started a walk whose first position is still
  // awaited, or null. `waitingSince` is the value so far, `before` and
  // `after` the direction before and after this change of keys, `now` its
  // time, and `lastMoveArrivedAt` when the last own position arrived that
  // had moved.
  function walkStart(waitingSince, before, after, now, lastMoveArrivedAt) {
    if (isStanding(after)) {
      return null; // released before the server answered: no sample
    }
    if (!isStanding(before)) {
      return waitingSince; // a turn: still the same walk
    }
    var wasStanding = now - lastMoveArrivedAt >= STANDING_MILLISECONDS;
    return wasStanding ? now : null;
  }

  // Returns a new list with one more start delay, in ms. A sample is
  // clamped to sensible limits, and only the newest few are kept, so the
  // lag follows the connection.
  function rememberStartDelay(samples, milliseconds) {
    var clamped = Math.max(SHORTEST_START_DELAY, Math.min(LONGEST_START_DELAY, milliseconds));
    return samples.concat([clamped]).slice(-START_DELAYS_KEPT);
  }

  // The middle value; for an even count the mean of the two middle ones.
  function median(values) {
    var sorted = values.slice().sort(function (a, b) {
      return a - b;
    });
    var middle = Math.floor(sorted.length / 2);
    if (sorted.length % 2 === 1) {
      return sorted[middle];
    }
    return (sorted[middle - 1] + sorted[middle]) / 2;
  }

  // How far the drawn character is behind the keys, in ms: the start
  // delay, plus the time a position waits in the queue before its glide
  // starts (the smallest playback delay minus the glide of one tick).
  //
  // The start delay is the smallest of the last samples, not their middle.
  // A sample can only be too long: it contains the wait for the server's
  // next tick, sometimes a hold-up, and the whole time at a wall when a
  // walk starts against one. And only a lag that is too long does harm: the
  // character walks on after a release and slides back a second later. With
  // a lag that is too short the bridge stops a step early and walks that
  // step when the positions arrive.
  function inputLag(samples, glideMilliseconds, tickMilliseconds) {
    var startDelay = samples.length > 0 ? Math.min.apply(null, samples) : START_DELAY_BEFORE_MEASURED;
    return startDelay + glideMilliseconds - tickMilliseconds;
  }

  // ---- How long a tick of the server is -----------------------------------

  // Is a change of the own position by (dx, dy) one step of the server?
  // It has to move at all, and not further on an axis than the server can
  // walk in one step (its speed times its cap: 9 units). A longer change is
  // two steps in one message (the server skipped this browser for a tick)
  // or the server putting the player somewhere: neither tells how long a
  // tick is or when a walk started.
  function isOneServerStep(dx, dy) {
    var further = Math.max(Math.abs(dx), Math.abs(dy));
    var longest = PLAYER_SPEED * MAX_STEP_SECONDS;
    return further > SAME_PLACE && further <= longest + SAME_PLACE;
  }

  // The server moves a player by its speed times the time it measured
  // since its last tick. That is a little more than 1/15 s (on the deployed
  // game 68 ms: 6.1 units per step instead of 6.0). A bridge that walked
  // shorter steps than the server would leave the character a tenth of a
  // unit further behind with every step. So it walks for as long per step
  // as the server's own steps did lately.

  // `samples` are the times of the server's last steps, in seconds. Returns
  // a new list with the time of one more step, which moved the own player
  // by (dx, dy) map units; only the newest few are kept.
  //
  // The time is read from the axis that moved further. A straight step
  // covers speed x time on it; a diagonal step, also one that slides along
  // a wall, covers that divided by the square root of 2. A tick is never
  // shorter than `tickMilliseconds`. So at least a full tick's way on an
  // axis is read as a straight step, and at least a diagonal tick's way as
  // a diagonal one. A shorter step was stopped by a wall and tells
  // nothing, and neither does a change that is no single step (see
  // isOneServerStep()): the list is returned as it is.
  //
  // Two kinds of step are read wrongly. A straight step that a wall
  // shortened to between a diagonal tick's way and a full one (4.24 to 6
  // units) is read as a diagonal: too long a time. A diagonal step of a
  // tick of 94 ms or more is read as straight: too short a time. Both are
  // single steps among the eight kept, and stepSeconds() takes the median.
  function rememberServerStep(samples, dx, dy, tickMilliseconds) {
    if (!isOneServerStep(dx, dy)) {
      return samples;
    }
    var further = Math.max(Math.abs(dx), Math.abs(dy));
    var straight = PLAYER_SPEED * (tickMilliseconds / 1000); // the way of a straight tick
    var almost = 1e-6; // room for the last digits of a float
    var seconds;
    if (further >= straight - almost) {
      seconds = further / PLAYER_SPEED;
    } else if (further >= straight / Math.sqrt(2) - almost) {
      seconds = (further * Math.sqrt(2)) / PLAYER_SPEED;
    } else {
      return samples;
    }
    return samples.concat([seconds]).slice(-SERVER_STEPS_KEPT);
  }

  // The time one step of the server covers, in seconds: the median of the
  // samples, so one unusual tick does not count. Before the first sample
  // it is one tick. Never shorter than a tick, never longer than the
  // server's own cap.
  function stepSeconds(samples, tickMilliseconds) {
    var tickSeconds = tickMilliseconds / 1000;
    if (samples.length === 0) {
      return tickSeconds;
    }
    return Math.max(tickSeconds, Math.min(MAX_STEP_SECONDS, median(samples)));
  }

  // ---- Would a bridged step be made? -------------------------------------

  // Decides whether the own character takes a bridged step, and to where.
  // It changes nothing, so world.js can also ask it for a frame that has
  // not been drawn yet. `situation` is:
  //   now               the time of the frame (ms)
  //   campus            the map {solids, width, height}, or null while it loads
  //   switchedOff       true with `bridge=off` in the page's address
  //   inputPaused       true while a minigame has the keys
  //   queueLength       how many server positions wait in the own queue
  //   glideEndsAt       when the current glide of the own character is over
  //   glideWasAStep     whether that glide was a walking step
  //   from              {x, y}: where the server is believed to be at the
  //                     end of that glide (the newest waiting bridged step,
  //                     or the newest server position when none waits)
  //   waitingSteps      how many bridged steps wait for the server
  //   history           the direction history, see rememberDirection()
  //   inputLag          see inputLag(), in ms
  //   stepSeconds       see stepSeconds(): the time one step of the server
  //                     covers, which is also how long the step's glide lasts
  // Returns null, or the step {x, y, dx, dy, startAt, endAt}: the glide to
  // (x, y) starts at the end of the glide before, not at `now`, so the pace
  // stays even on every screen. (dx, dy) is the direction it walked.
  function nextStep(situation) {
    if (!isReady(situation) || !continuesAWalk(situation)) {
      return null;
    }
    if (situation.waitingSteps >= MOST_BRIDGED_STEPS) {
      return null; // a hold-up longer than the bridge may cover
    }
    var startAt = situation.glideEndsAt;
    var wanted = bridgedDirection(situation, startAt);
    if (isStanding(wanted)) {
      return null;
    }
    var from = situation.from;
    var place = oneStepOn(from, wanted, situation.campus, situation.stepSeconds);
    if (place.x === from.x && place.y === from.y) {
      return null; // against a wall the character stands, like on the server
    }
    return {
      x: place.x,
      y: place.y,
      dx: wanted.dx,
      dy: wanted.dy,
      startAt: startAt,
      endAt: startAt + glideMilliseconds(situation)
    };
  }

  // How long the glide of a bridged step lasts: as long as the server
  // takes for a step, so the bridge walks at the server's speed. (With a
  // shorter glide the drawing gained on the server, a whole step every few
  // seconds.) The first step of a bridge is a little slower, see
  // FIRST_STEP_SLOWER.
  function glideMilliseconds(situation) {
    var serverStep = situation.stepSeconds * 1000;
    return situation.waitingSteps === 0 ? serverStep * FIRST_STEP_SLOWER : serverStep;
  }

  // Where a player at `from` {x, y} is after one step of `seconds` in the
  // direction `wanted` {dx, dy}, by the server's rule on the map `campus`.
  function oneStepOn(from, wanted, campus, seconds) {
    return step(from.x, from.y, wanted.dx, wanted.dy, seconds, campus.solids, campus.width, campus.height);
  }

  // May the own character be bridged at all right now?
  function isReady(situation) {
    var campus = situation.campus;
    var hasMap = Boolean(campus) && Array.isArray(campus.solids);
    return hasMap && !situation.switchedOff && !situation.inputPaused && Boolean(situation.from);
  }

  // A bridge only ever continues a walk and never starts one: the queue is
  // empty, and the glide before was a walking step that is over, but not
  // for long.
  function continuesAWalk(situation) {
    if (situation.queueLength > 0 || !situation.glideWasAStep) {
      return false;
    }
    var overFor = situation.now - situation.glideEndsAt;
    return overFor >= 0 && overFor <= LONGEST_WAIT_MILLISECONDS;
  }

  // The direction of a bridged step that starts at `startAt`: the one the
  // player held one input lag earlier. With one exception: when the keys
  // are released by then and no bridged step is waiting, there is no step.
  // That is an ordinary stop. The queue runs empty then too, but the server
  // sends nothing more, and a step made up here would walk the character
  // on and bring it back a second later.
  function bridgedDirection(situation, startAt) {
    var releasedByThen = isStanding(directionAt(situation.history, startAt));
    if (releasedByThen && situation.waitingSteps === 0) {
      return { dx: 0, dy: 0 };
    }
    return directionAt(situation.history, startAt - situation.inputLag);
  }

  // ---- When the server's position arrives --------------------------------

  // Do the two places {x, y} differ by more than a hair on an axis?
  function differs(a, b) {
    return Math.abs(a.x - b.x) > SAME_PLACE || Math.abs(a.y - b.y) > SAME_PLACE;
  }

  // The server sends one own position per tick while the player moves. So
  // the first position after the queue ran dry belongs to the oldest
  // waiting bridged step, the next one to the next: by count.
  //
  // `waiting` is the list of bridged steps [{x, y, dx, dy}], oldest first,
  // and (x, y) the server's position. Returns
  //   waiting   the steps still waiting: without the oldest. If the server
  //             is at another place, the bridge was wrong from there on,
  //             and the steps are walked again from the server's place,
  //             see walkAgain()
  //   distance  how far the server's position is from the bridged step
  //   size      "none" (the same place), "small" or "large", see SMALL_CORRECTION
  function takeServerPosition(waiting, x, y, campus, seconds) {
    var oldest = waiting[0];
    var rest = waiting.slice(1);
    var server = { x: x, y: y };
    if (!differs(server, oldest)) {
      return { waiting: rest, distance: 0, size: "none" };
    }
    var dx = x - oldest.x;
    var dy = y - oldest.y;
    var isLarge = Math.abs(dx) > SMALL_CORRECTION || Math.abs(dy) > SMALL_CORRECTION;
    return {
      waiting: walkAgain(rest, server, campus, seconds),
      distance: Math.sqrt(dx * dx + dy * dy),
      size: isLarge ? "large" : "small"
    };
  }

  // The same steps, walked again from the place `from` with the server's
  // rule, as a new list. In the open that moves every step by the same
  // difference. It is not done by adding the difference: next to a wall
  // that could put a step inside the wall, and a player inside a solid is
  // not stopped by it (see step()), so the bridge would walk through. A
  // step that no longer moves is dropped: for a tick against a wall the
  // server sends no position either.
  function walkAgain(steps, from, campus, seconds) {
    var again = [];
    var place = from;
    steps.forEach(function (one) {
      var next = oneStepOn(place, one, campus, seconds);
      if (next.x !== place.x || next.y !== place.y) {
        again.push({ x: next.x, y: next.y, dx: one.dx, dy: one.dy });
        place = next;
      }
    });
    return again;
  }

  // How long the glide of a correction lasts: the time the glide had left,
  // but not too short; one tick when the glide was over already.
  function correctionMilliseconds(leftMilliseconds, tickMilliseconds) {
    if (leftMilliseconds <= 0) {
      return tickMilliseconds;
    }
    return Math.max(leftMilliseconds, SHORTEST_CORRECTION_MILLISECONDS);
  }

  // When the waiting steps are taken back: some time after the last sign of
  // life, which is the end of the last bridged glide or the arrival of the
  // last own position from the server, whichever is later.
  function takeBackAt(lastBridgedEndsAt, lastArrivalAt) {
    return Math.max(lastBridgedEndsAt, lastArrivalAt) + TAKE_BACK_MILLISECONDS;
  }

  // ---- What world.js remembers and counts --------------------------------

  // What the bridge remembers about the own character. world.js owns it.
  function newWalk() {
    return {
      // Directions reported to the server, see rememberDirection().
      history: [],
      // The key that started a walk whose first position is awaited, see walkStart().
      startedAt: null,
      // When the last own position arrived, and the last one that had moved.
      lastArrivalAt: -Infinity,
      lastMoveArrivedAt: -Infinity,
      // Bridged steps waiting for the server, oldest first: [{x, y, dx, dy}].
      waiting: [],
      lastBridgedEndsAt: -Infinity, // the end of the last bridged glide
      forgottenAt: -Infinity, // when waiting steps were last forgotten
      // True from a bridged step until the drawing is known to stand on
      // the server's position again.
      mayBeOffServer: false
    };
  }

  // What the ?debug panel shows about the bridge.
  function newTally() {
    return {
      steps: 0, // bridged steps made
      milliseconds: 0, // the time they covered
      replaced: 0, // server positions that took the place of a bridged step
      corrections: 0, // of those, how many were at another place
      largeCorrections: 0, // and how many of those were wrong guesses
      largestCorrection: 0, // the largest difference, in map units
      takenBack: 0 // how often waiting steps were taken back
    };
  }

  Game.world.bridge = {
    PLAYER_HALF_SIZE: PLAYER_HALF_SIZE,
    PLAYER_SPEED: PLAYER_SPEED,
    MAX_STEP_SECONDS: MAX_STEP_SECONDS,
    MOST_BRIDGED_STEPS: MOST_BRIDGED_STEPS,
    FIRST_STEP_SLOWER: FIRST_STEP_SLOWER,
    LONGEST_WAIT_MILLISECONDS: LONGEST_WAIT_MILLISECONDS,
    TAKE_BACK_MILLISECONDS: TAKE_BACK_MILLISECONDS,
    SAME_PLACE: SAME_PLACE,
    SMALL_CORRECTION: SMALL_CORRECTION,
    step: step,
    overlaps: overlaps,
    rememberDirection: rememberDirection,
    directionAt: directionAt,
    isWalkingAt: isWalkingAt,
    walkStart: walkStart,
    rememberStartDelay: rememberStartDelay,
    inputLag: inputLag,
    isOneServerStep: isOneServerStep,
    rememberServerStep: rememberServerStep,
    stepSeconds: stepSeconds,
    nextStep: nextStep,
    differs: differs,
    takeServerPosition: takeServerPosition,
    correctionMilliseconds: correctionMilliseconds,
    takeBackAt: takeBackAt,
    newWalk: newWalk,
    newTally: newTally
  };
})();
