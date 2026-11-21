// The world on the canvas: the drawing loop, the camera, the keyboard, the
// smoothing of the players' movement and the task stations a player can use.
//
// The browser decides nothing here (AGENTS.md, rule 1). The keyboard only
// tells the server where the player wants to go, and every position that is
// drawn, also the own one, comes from the server. (While the server's
// positions are held up, the own character walks on for a moment by the
// server's own rule and then takes the server's positions, see "Bridging
// the gaps" below.)

"use strict";

window.Game = window.Game || {};
Game.world = Game.world || {};

(function () {
  var MAP_FILE = "js/world/campus.json";

  // The camera shows about one room: this many map units along the longer
  // side of the canvas.
  var VIEW_SIZE = 260;

  // Shown until the map file has arrived (background colour of DESIGN.md).
  var BACKGROUND = "#EADFC8";
  var OUTLINE = "#2E2A3B";
  var SURFACE = "#F4EFE3"; // cream, behind the names
  var LOADING_TEXT = "Loading the campus…";
  // After a failed download of the map, try again after this time.
  var RETRY_MILLISECONDS = 2000;

  // Height of a drawn character, in map units: one size for all. With it a
  // character is about as tall as a door is wide (40) and stands clearly
  // above a table (24). Only the drawing is this big: the server still
  // counts a player as a square of 10 by 10 units (S-86), which is about
  // as wide as the drawn body and legs.
  var CHARACTER_HEIGHT = 39;
  // The server's position is the middle of that 10 x 10 square. The feet are
  // drawn at its lower edge, so a character stands in front of a wall the
  // way it collides with it.
  var FEET_BELOW_POSITION = 5;

  // The server sends positions once per tick, 15 times per second (S-72).
  var TICK_MILLISECONDS = 1000 / 15;
  // Over the internet the messages often arrive bunched: one is held back
  // and comes together with the next. A character can only be drawn
  // smoothly up to the last position that has arrived, so the positions
  // are not drawn when they arrive. They wait in a short queue per player
  // and are played back at the server's pace, one tick each, a little later
  // (M2-1.14). How much later is the playback delay: the largest gap
  // between two messages lately, plus a margin, see playbackDelay().
  //
  // The smallest playback delay. With messages on time the characters are
  // drawn this far behind their arrival, so a message up to about 40 ms
  // late still changes nothing. It is also how long the glide of a
  // position lasts that is not played from the queue.
  var GLIDE_MILLISECONDS = 110;
  // The largest playback delay. A gap longer than this (Felix measured
  // 300 to 500 ms about every 3 s) still makes the character stop for a
  // moment; a larger delay would cover it, but the own character would then
  // always be drawn 330 to 450 ms behind the keys.
  var LONGEST_DELAY_MILLISECONDS = 250;
  // After a gap the queue catches up at most this many times faster than
  // the server's pace, so a character never rushes or jumps.
  var FASTEST_PACE = 1.5;
  var FASTEST_GLIDE_MILLISECONDS = TICK_MILLISECONDS / FASTEST_PACE;
  // A queue reaching further than the delay plus this would take too long
  // to catch up at FASTEST_PACE (after a hold-up of about a second or
  // more): the character then snaps to the newest position instead.
  var LONGEST_CATCH_UP_MILLISECONDS = 600;
  // Added to the largest gap, so the next message is there a moment before
  // the character has reached the position before it.
  var DELAY_MARGIN_MILLISECONDS = 15;
  // Only the gaps of this last stretch of time count: when the connection
  // gets better, the delay shrinks again.
  var GAP_MEMORY_MILLISECONDS = 3000;
  // A longer gap is no hold-up: the server sends nothing while everybody
  // stands, so it does not count.
  var PAUSE_MILLISECONDS = 400;
  // A longer way than this in one message is a respawn: jump, do not glide.
  var JUMP_DISTANCE = 60;
  // A real step is at most 9 map units on an axis: the server moves a player
  // by at most 0.1 seconds x 90 units per second in one go. A larger change
  // is the server putting the player somewhere else (the spawn at the start
  // of a round): not a step, so the character neither walks nor turns.
  var LONGEST_STEP = 15;
  // The feet take full steps while the character glides. With the first
  // step the steps grow to full size within this time; when no further step
  // arrives they shrink to nothing within the second time, so the feet are
  // put down softly instead of snapping to the ground.
  var STRIDE_GROWS_MILLISECONDS = GLIDE_MILLISECONDS;
  var STRIDE_FADES_MILLISECONDS = 150;
  // One cycle of the run is two steps: left foot, right foot. It runs on
  // the way the drawn character covers, not on the time. So the feet keep
  // pace with the ground on every screen, however often messages arrive and
  // however long a glide takes, and they stop when the character stops,
  // also against a wall. One cycle takes this many map units: 18 per step,
  // 5 steps per second at 90 units per second. It belongs to how far the
  // feet move in characters.js (FOOT_TRAVEL, GROUND_FRACTION): together
  // they decide how much a foot slides on the ground.
  var WALK_CYCLE_LENGTH = 36;
  // A change of position smaller than this, in map units, is not a step: it
  // neither turns the character nor moves its feet. A real step is about 6
  // units (90 units per second, 15 messages per second, S-86).
  var SMALLEST_STEP = 1;
  // Free room between the top of a standing character and its name, in map
  // units. A running character rises on every step, by at most BODY_BOB in
  // characters.js: 3 of its 112 design units, which is 1.05 map units at
  // CHARACTER_HEIGHT. This room must be at least that rise, so a head never
  // touches its name. The name is placed from the position, not from the
  // drawing, so it stays still while the body bobs.
  var HEAD_ROOM_BELOW_NAME = 1.5;

  // Which keys walk where. `event.code` names the place of a key on the
  // keyboard, so WASD also sits right on a keyboard with another layout.
  var KEY_DIRECTIONS = {
    KeyW: "up", ArrowUp: "up",
    KeyS: "down", ArrowDown: "down",
    KeyA: "left", ArrowLeft: "left",
    KeyD: "right", ArrowRight: "right"
  };

  // The key that uses a station, and the text on its button (DESIGN.md,
  // section 4).
  var USE_KEY_CODE = "KeyE"; // `event.code` of the key in the E position
  var USE_BUTTON_TEXT = "E Use";

  // ---- State -----------------------------------------------------------

  var campus = null; // the map data, once loaded
  var isLoadingCampus = false; // a download of the map is on its way
  var retryTimer = 0; // id of the timer that waits for the next try
  var canvas = null;
  var ctx = null;
  var sendMove = null;
  var running = false;
  var frameRequest = 0; // id of the waiting requestAnimationFrame
  var ownName = null;
  var players = new Map(); // name -> player record, see newPlayer()
  var pressedKeys = {}; // event.code -> true while the key is held down
  var sentDirection = { dx: 0, dy: 0 }; // what the server heard last
  // When the player started to walk: the time at which the direction last
  // changed from (0, 0) to something else. Only the walking diagnostic reads it.
  var walkingSince = null;
  var usableStations = null; // ids of the stations that count, null = all
  var useHandler = null; // called with the id of the station that is opened
  var useButton = null; // the button "E Use", while the world runs
  var inputPaused = false; // true while a minigame is open, see setInputPaused()
  // When the positions messages of the last GAP_MEMORY_MILLISECONDS arrived,
  // oldest first. One list for the world: every message lists all players.
  var arrivalTimes = [];

  // Only the target assigned to this player is passed to the navigator.
  var taskTarget = null;
  var taskTitle = null;

  function setTaskTarget(stationId, title) {
    var next = Number.isInteger(stationId) ? stationId : null;
    taskTarget = next;
    taskTitle = typeof title === "string" ? title : null;
    if (next === null && canvas && typeof canvas.setAttribute === "function") canvas.setAttribute("aria-label", "Campus map");
  }

  // The compass follows the direct destination vector on every frame,
  // using only the latest position the server sent for this player.
  function updateGuidance() {
    if (taskTarget === null || inputPaused || !Game.world.navigation) return null;
    var own = ownName !== null && players.has(ownName) ? players.get(ownName).server : null;
    if (!own) return null;
    var guidance = Game.world.navigation.directGuidance(campus, own, taskTarget);
    if (guidance) {
      var label = "Campus map. " + (taskTitle || guidance.title) + " in " + guidance.room + ". "
        + (guidance.arrived ? "Press E to use." : "The arrow points to your task.");
      if (typeof canvas.setAttribute === "function"
        && (typeof canvas.getAttribute !== "function" || canvas.getAttribute("aria-label") !== label)) {
        canvas.setAttribute("aria-label", label);
      }
    }
    return guidance;
  }

  // ---- Players and smoothing -------------------------------------------

  function newPlayer(name) {
    return {
      name: name,
      character: null,
      // The character glides from `from` to `to`. Both are null until the
      // first position has arrived; until then the player is not drawn.
      from: null,
      to: null,
      arrivedAt: 0, // when the glide to `to` started, in milliseconds
      glideMilliseconds: GLIDE_MILLISECONDS, // how long that glide lasts
      // The newest position the server sent. The drawing is behind it.
      server: null,
      // Positions waiting to be drawn, oldest first:
      // [{x, y, startAt, endAt}], see schedulePosition().
      queue: [],
      // When the last scheduled position is reached; null when there is none.
      queueEndsAt: null,
      snappedAt: -Infinity, // when snapTo() last put it on the newest position
      lastStepAt: -Infinity, // when the character last took a step
      stepMilliseconds: GLIDE_MILLISECONDS, // how long the glide of that step lasts
      strideAtLastStep: 0, // how big its steps were at that moment, 0 to 1
      // How far the drawn character had walked, in map units, when the
      // current glide started (see walkedDistance()) ...
      walkedBeforeGlide: 0,
      // ... and how far it had walked when it started to walk; the walking
      // cycle starts there.
      walkedWhenItStarted: 0,
      // Until this time the next position is a placement by the server and
      // not a step, see startOfRound().
      placedUntil: -Infinity,
      // Which side the character faces. It only ever faces left or right,
      // keeps the side after it stopped, and faces right until it has moved.
      facingLeft: false
    };
  }

  function playerNamed(name) {
    if (!players.has(name)) {
      players.set(name, newPlayer(name));
    }
    return players.get(name);
  }

  function isName(value) {
    return typeof value === "string" && value !== "";
  }

  function isNumber(value) {
    return typeof value === "number" && isFinite(value);
  }

  // Where the player is drawn at the time `now`: on the way from `from` to
  // `to`, and at `to` once the glide time is over. Null without a position.
  function drawnPosition(player, now) {
    if (!player.to) {
      return null;
    }
    var progress = (now - player.arrivedAt) / player.glideMilliseconds;
    progress = Math.max(0, Math.min(1, progress));
    return {
      x: player.from.x + (player.to.x - player.from.x) * progress,
      y: player.from.y + (player.to.y - player.from.y) * progress
    };
  }

  // Takes one new position from the server. The glide starts where the
  // character is drawn right now, so it never jumps, also when messages
  // arrive early or late.
  function moveTo(player, x, y, now) {
    // Counted before the glide changes: the way up to this moment.
    var walked = walkedDistance(player, now);
    var start = drawnPosition(player, now) || { x: x, y: y };
    var isJump = Math.abs(x - start.x) > JUMP_DISTANCE || Math.abs(y - start.y) > JUMP_DISTANCE;
    var isPlacement = now < player.placedUntil;
    player.placedUntil = -Infinity; // it counts for one position only
    if (isJump || isPlacement) {
      start = { x: x, y: y };
    }
    if (player.to) {
      var dx = x - player.to.x;
      var dy = y - player.to.y;
      if (isJump || isPlacement || isLongerThanAStep(dx, dy)) {
        standStill(player);
      } else {
        takeStep(player, dx, dy, now);
      }
    }
    player.from = start;
    player.to = { x: x, y: y };
    player.arrivedAt = now;
    player.walkedBeforeGlide = walked;
  }

  // How far the drawn character has walked up to the time `now`, in map
  // units: the way of all earlier glides and the part of the current glide
  // covered so far. A jump or a placement starts its glide where it ends,
  // so it adds nothing. Like drawnPosition() it only depends on the time,
  // so it is the same however often the screen is redrawn, and it does not
  // depend on how long a glide takes.
  function walkedDistance(player, now) {
    var position = drawnPosition(player, now);
    if (!position) {
      return 0;
    }
    var dx = position.x - player.from.x;
    var dy = position.y - player.from.y;
    return player.walkedBeforeGlide + Math.sqrt(dx * dx + dy * dy);
  }

  // Further apart than a walk can go in one message: a jump.
  function isFarApart(place, x, y) {
    return Math.abs(x - place.x) > JUMP_DISTANCE || Math.abs(y - place.y) > JUMP_DISTANCE;
  }

  // Starts the glide to (x, y) at `startAt`; it lasts `milliseconds`.
  function startGlide(player, x, y, startAt, milliseconds) {
    moveTo(player, x, y, startAt);
    // Set only after moveTo: moveTo still needs the length of the glide
    // before, to find where the character is drawn at `startAt`.
    player.glideMilliseconds = milliseconds;
    if (player.lastStepAt === startAt) {
      // moveTo took a step: the feet move until this glide is over, see stride().
      player.stepMilliseconds = milliseconds;
    }
  }

  // Looks at the way between the last two positions from the server, (dx, dy),
  // and remembers that the character walks and which side it faces.
  // The same position again, or a tiny change, is not a step and changes
  // nothing: so a character pressing against a wall does not twitch.
  function takeStep(player, dx, dy, now) {
    var stepsSideways = Math.abs(dx) >= SMALLEST_STEP;
    var stepsUpOrDown = Math.abs(dy) >= SMALLEST_STEP;
    if (!stepsSideways && !stepsUpOrDown) {
      return;
    }
    if (!isWalking(player, now)) {
      player.walkedWhenItStarted = walkedDistance(player, now);
    }
    // Remember how big the steps are right now: they grow on from there.
    player.strideAtLastStep = stride(player, now);
    player.lastStepAt = now;
    // Only the sideways part of a step turns the character, so a diagonal
    // takes the side of its sideways part. Walking straight up or down
    // keeps the side the character faced and still moves its feet.
    if (stepsSideways) {
      player.facingLeft = dx < 0;
    }
  }

  function isLongerThanAStep(dx, dy) {
    return Math.abs(dx) > LONGEST_STEP || Math.abs(dy) > LONGEST_STEP;
  }

  // The server put the player somewhere else. That is not a step: the
  // character stands there and faces right, like everybody else who was
  // put there and like a character that has not moved yet.
  function standStill(player) {
    player.lastStepAt = -Infinity;
    player.strideAtLastStep = 0;
    player.facingLeft = false;
  }

  // A round starts: the server puts everybody on the spawn. From far away
  // that shows as a jump, but a player who stood on the spawn or next to
  // it would keep the side it faced, or be drawn taking a step there. So
  // the lobby page says when a round starts: every character then stands
  // and faces right, and its next position, if it comes within a moment,
  // is a placement and not a step. Positions still come only from the
  // server; this decides nothing about them.
  var PLACEMENT_MILLISECONDS = 1000;

  function startOfRound() {
    var now = performance.now();
    players.forEach(function (player) {
      standStill(player);
      player.placedUntil = now + PLACEMENT_MILLISECONDS;
      // The positions still waiting in the queue are from before the round.
      // Played now, the first of them would count as the placement, and
      // the real placement would then be drawn as a step.
      emptyQueue(player);
    });
    forgetTheBridge(now);
  }

  // How big the steps of the player are at the time `now`, from 0 (it
  // stands) to 1 (full steps). After a step they grow to full size; once the
  // glide of that step is over and no new step has come, they fade away.
  // It only depends on the time, like drawnPosition(), so it looks the same
  // on every screen, however often that screen is redrawn.
  function stride(player, now) {
    // Never below 0: the time of a frame can lie a moment before the time
    // at which the step started.
    var sinceStep = Math.max(0, now - player.lastStepAt);
    var grown = Math.min(1, player.strideAtLastStep + sinceStep / STRIDE_GROWS_MILLISECONDS);
    // The glides of the queue last from 44 to 250 ms. The fade waits
    // for the end of the glide of this step: the feet neither stop while
    // the character still moves nor walk on after it stopped.
    var faded = (sinceStep - player.stepMilliseconds) / STRIDE_FADES_MILLISECONDS;
    faded = Math.max(0, Math.min(1, faded));
    // Slow at the start and at the end (the curve 3t² - 2t³). A message that
    // is a little late then hardly shrinks the steps before it arrives.
    var easedFade = faded * faded * (3 - 2 * faded);
    return grown * (1 - easedFade);
  }

  function isWalking(player, now) {
    return stride(player, now) > 0;
  }

  // How far the player is in its running cycle, from 0 to 1, or null when
  // it stands. It starts at 0, the moment the left foot lands (see
  // runningMoment() in characters.js), and moves on only while the drawn
  // character moves.
  function walkPhase(player, now) {
    if (!isWalking(player, now)) {
      return null;
    }
    var walked = Math.max(0, walkedDistance(player, now) - player.walkedWhenItStarted);
    return (walked / WALK_CYCLE_LENGTH) % 1;
  }

  // ---- Playing the positions back at the server's pace (M2-1.14) -------

  function clamp(value, lowest, highest) {
    return Math.max(lowest, Math.min(highest, value));
  }

  // Writes down that a positions message arrived at `now`, and forgets the
  // arrivals that are too old to count.
  function rememberArrival(now) {
    arrivalTimes.push(now);
    while (arrivalTimes[0] < now - GAP_MEMORY_MILLISECONDS) {
      arrivalTimes.shift();
    }
  }

  // How long a new position waits before it is drawn: one largest gap
  // between two messages lately, plus a margin. Then the next message has
  // usually arrived before the character has reached the position before.
  function playbackDelay() {
    var largestGap = 0;
    for (var i = 1; i < arrivalTimes.length; i++) {
      var gap = arrivalTimes[i] - arrivalTimes[i - 1];
      if (gap <= PAUSE_MILLISECONDS && gap > largestGap) {
        largestGap = gap;
      }
    }
    return clamp(largestGap + DELAY_MARGIN_MILLISECONDS, GLIDE_MILLISECONDS, LONGEST_DELAY_MILLISECONDS);
  }

  function emptyQueue(player) {
    player.queue = [];
    player.queueEndsAt = null;
  }

  // Takes one new position of `player`, arrived at `now`.
  function receivePosition(player, x, y, now, delay) {
    // Positions whose time has come are drawn first, so the queue stays
    // short also while no frames are drawn (a hidden tab).
    playQueue(player, now);
    var previous = player.server;
    player.server = { x: x, y: y };
    var isPlacement = now < player.placedUntil;
    // receiveOwnPosition() has the same test: CHANGE BOTH TOGETHER.
    if (!previous || isFarApart(previous, x, y) || isPlacement) {
      // The first position, a respawn or the start of a round: shown at
      // once, without waiting behind the queue. moveTo() puts it there.
      // (moveTo() measures a jump from the drawn place, which is a little
      // behind; a jump just over JUMP_DISTANCE may then glide instead.)
      emptyQueue(player);
      startGlide(player, x, y, now, GLIDE_MILLISECONDS);
      return;
    }
    // While anybody walks, the server sends every player's position on
    // every tick. The place where the drawing will end anyway adds nothing
    // to draw; queued, it would only make this player's next real step
    // wait behind it.
    var drawingEnds = drawingEndsAt(player);
    if (drawingEnds && drawingEnds.x === x && drawingEnds.y === y) {
      return;
    }
    schedulePosition(player, x, y, now, delay);
  }

  // Where the drawing of the player will stand once its queue is played:
  // the target of the last queued entry, or else the current glide's.
  // Not player.server: startOfRound() can empty the queue before the
  // drawing got there.
  function drawingEndsAt(player) {
    if (player.queue.length > 0) {
      return player.queue[player.queue.length - 1];
    }
    return player.to;
  }

  // Puts the position into the player's queue with the time its glide
  // starts and ends. The glides follow each other, one tick each, so the
  // character walks at the server's pace however the messages arrive.
  function schedulePosition(player, x, y, now, delay) {
    var lastEnd = player.queueEndsAt;
    var startAt = now;
    var endAt;
    if (lastEnd === null || now - lastEnd >= PAUSE_MILLISECONDS) {
      // A start after standing: one delay behind this arrival, so the
      // next messages are there before the character needs them.
      endAt = now + delay;
    } else if (lastEnd + TICK_MILLISECONDS < now) {
      // The queue ran dry while walking (a gap longer than the delay): the
      // character has stood already, so it goes on at once at the normal
      // pace instead of taking one slow step over the whole delay.
      endAt = now + TICK_MILLISECONDS;
    } else {
      // Follow on from the end of the queue. Every glide takes at least
      // FASTEST_GLIDE_MILLISECONDS, so catching up is at most 1.5 times
      // the normal speed, never a jump.
      startAt = Math.max(lastEnd, now);
      endAt = Math.max(lastEnd + nextSpacing(lastEnd, now, delay), startAt + FASTEST_GLIDE_MILLISECONDS);
    }
    // Within half a tick of a snap is the same burst: snap too, so its rest does not queue up again.
    var isSameBurst = now - player.snappedAt < TICK_MILLISECONDS / 2;
    if (isSameBurst || endAt - now > delay + LONGEST_CATCH_UP_MILLISECONDS) {
      snapTo(player, x, y, now);
      return;
    }
    player.queue.push({ x: x, y: y, startAt: startAt, endAt: endAt });
    player.queueEndsAt = endAt;
  }

  // After a long hold-up: forget the queue and show the newest position at
  // once. moveTo() still decides the step and the facing; its glide then
  // starts where it ends, so the character stands there in the next frame.
  function snapTo(player, x, y, now) {
    emptyQueue(player);
    startGlide(player, x, y, now, GLIDE_MILLISECONDS);
    player.from = player.to;
    player.snappedAt = now;
  }

  // How long the next glide in the queue lasts: one tick, a little longer
  // while the queue is shorter than the delay (so it fills up again) and a
  // little shorter while it is longer (so the drawing catches up). `lead` is
  // how far ahead of this arrival the queue reaches with one more tick.
  function nextSpacing(lastEnd, now, delay) {
    var lead = lastEnd + TICK_MILLISECONDS - now;
    var factor = clamp(1 + 0.3 * (delay - lead) / delay, 1 / FASTEST_PACE, 1.25);
    return TICK_MILLISECONDS * factor;
  }

  // Starts the glides of the queued positions whose time has come. Each one
  // starts at its own startAt, not at `now`: a late frame then draws the
  // character exactly where it would have been.
  function playQueue(player, now) {
    while (player.queue.length > 0 && player.queue[0].startAt <= now) {
      var entry = player.queue.shift();
      startGlide(player, entry.x, entry.y, entry.startAt, entry.endAt - entry.startAt);
    }
  }

  function playAllQueues(now) {
    players.forEach(function (player) {
      playQueue(player, now);
    });
  }

  // ---- Bridging the gaps of the own character (M2-1.16) ----------------

  // Now and then the messages stop for 260 to 690 ms (measured) and then
  // arrive all at once. No playback delay covers that, so the own
  // character and the camera stood that long. Instead the own character
  // walks on by itself with the server's own movement and wall rule, for
  // at most about 700 ms ("bridged steps"). When the server's positions
  // arrive they take the place of the bridged steps, and the character
  // always ends on the server's position: the server still decides (rule
  // 1). Because of the bridge the own character needs no growing delay and
  // is played at the smallest one, see ownDelay().
  //
  // The rules are plain functions in bridge.js (Game.world.bridge); the
  // functions here apply them to the own player's record. Without
  // bridge.js, or with `bridge=off` in the page's address, none of this
  // happens and the own character is played from the queue like the others.

  var bridge = Game.world.bridge || null;
  // Read once. `bridge=off` is for comparing on the deployed game.
  var bridgingSwitchedOff = isBridgingSwitchedOffInTheAddress();
  // What the bridge remembers about the own character, see newWalk() in
  // bridge.js: the directions sent, the bridged steps waiting for the server.
  var ownWalk = bridge ? bridge.newWalk() : null;
  // The last start delays measured, in ms, see rememberStartDelay() in
  // bridge.js. They describe the connection, so they outlive a lobby.
  var startDelays = [];
  // How long the server's last ticks were, in seconds, read from its own
  // steps, see rememberServerStep() in bridge.js.
  var serverStepTimes = [];
  // What the ?debug panel shows, see newTally() in bridge.js.
  var bridgeTally = bridge ? bridge.newTally() : null;

  function isBridgingSwitchedOffInTheAddress() {
    // The tests run this file without a page address: then it is not off.
    if (typeof location !== "object" || typeof URLSearchParams !== "function") {
      return false;
    }
    return new URLSearchParams(location.search).get("bridge") === "off";
  }

  function isBridging() {
    return bridge !== null && !bridgingSwitchedOff;
  }

  function ownPlayer() {
    return ownName !== null && players.has(ownName) ? players.get(ownName) : null;
  }

  // How far the drawn character is behind the keys, in ms.
  function currentInputLag() {
    return bridge.inputLag(startDelays, GLIDE_MILLISECONDS, TICK_MILLISECONDS);
  }

  // The time one step of the server covers, in seconds.
  function serverStepSeconds() {
    return bridge.stepSeconds(serverStepTimes, TICK_MILLISECONDS);
  }

  // reportDirection() tells every direction it sends: `before` and `after`
  // are {dx, dy}. A bridged step uses the direction of a moment ago.
  function rememberOwnDirection(before, after, now) {
    if (!isBridging()) {
      return;
    }
    ownWalk.history = bridge.rememberDirection(ownWalk.history, now, after.dx, after.dy);
    ownWalk.startedAt = bridge.walkStart(ownWalk.startedAt, before, after, now, ownWalk.lastMoveArrivedAt);
  }

  // The playback delay of the own character. While the player walks, a gap
  // is bridged, so the fixed smallest delay is enough and the character
  // follows the keys sooner. In every other case it is `delay`, the one of
  // the other players.
  function ownDelay(delay, now) {
    var canBridge = Boolean(campus) && !inputPaused;
    if (canBridge && bridge.isWalkingAt(ownWalk.history, now, currentInputLag())) {
      return GLIDE_MILLISECONDS;
    }
    return delay;
  }

  // Takes one new position of the own player, arrived at `now`. Only
  // called while isBridging().
  function receiveOwnPosition(player, x, y, now, delay) {
    // First everything that was due before this arrival, as a frame would
    // do it. So the result does not depend on when the frames are drawn.
    playQueue(player, now);
    bridgeOwnGaps(player, ownWalk, now, bridgeTally);
    var previous = player.server;
    // The same test as in receivePosition(): CHANGE BOTH TOGETHER.
    var isShownAtOnce = !previous || isFarApart(previous, x, y) || now < player.placedUntil;
    noteOwnArrival(isShownAtOnce ? null : { dx: x - previous.x, dy: y - previous.y }, now);
    if (isShownAtOnce) {
      // The first position, a respawn or the start of a round: nothing of
      // the walk before counts any more. Handled like for everybody.
      forgetTheBridge(now);
      receivePosition(player, x, y, now, delay);
    } else if (ownWalk.waiting.length > 0) {
      // The drawing is at this position or beyond it already: it is not
      // queued. The station in range still uses it, see stationInRange().
      player.server = { x: x, y: y };
      replaceBridgedStep(player, ownWalk, x, y, now, bridgeTally);
    } else {
      receivePosition(player, x, y, now, ownDelay(delay, now));
    }
  }

  // Writes down that an own position arrived. `change` is how far it is
  // from the position before, {dx, dy} in map units, or null for a
  // position that is shown at once (no walk). A change that is one step of
  // the server tells how long its tick was. If it is the first change of a
  // walk that started from standing, the time since the key is one sample
  // of the start delay.
  function noteOwnArrival(change, now) {
    ownWalk.lastArrivalAt = now;
    var hasMoved = change !== null && bridge.differs({ x: 0, y: 0 }, { x: change.dx, y: change.dy });
    if (!hasMoved) {
      return;
    }
    ownWalk.lastMoveArrivedAt = now;
    var isOneStep = bridge.isOneServerStep(change.dx, change.dy);
    serverStepTimes = bridge.rememberServerStep(serverStepTimes, change.dx, change.dy, TICK_MILLISECONDS);
    if (ownWalk.startedAt !== null && isOneStep) {
      startDelays = bridge.rememberStartDelay(startDelays, now - ownWalk.startedAt);
    }
    // The walk has begun, also when its first message held two steps
    // (then it is no sample): later positions are not its start.
    ownWalk.startedAt = null;
  }

  // Where the server is believed to be once the drawing has ended: at the
  // newest bridged step, or at its newest position when no step waits.
  function believedPlace(player, walk) {
    var waiting = walk.waiting;
    return waiting.length > 0 ? waiting[waiting.length - 1] : player.server;
  }

  // The server's position (x, y) takes the place of the oldest waiting
  // bridged step. Where they differ, the bridge was wrong from there on.
  function replaceBridgedStep(player, walk, x, y, now, tally) {
    var result = bridge.takeServerPosition(walk.waiting, x, y, campus, serverStepSeconds());
    walk.waiting = result.waiting;
    tally.replaced += 1;
    if (result.size === "none") {
      return;
    }
    tally.corrections += 1;
    tally.largestCorrection = Math.max(tally.largestCorrection, result.distance);
    if (result.size === "small") {
      // The server's ticks are not all equally long. The glide is left
      // alone: turned now by a fraction of a unit, it would speed up or
      // slow down for a moment. The next glide starts where the character
      // is drawn and ends on the right place.
      return;
    }
    // A wrong guess: the drawing turns towards the right place softly.
    tally.largeCorrections += 1;
    var left = player.arrivedAt + player.glideMilliseconds - now;
    var milliseconds = bridge.correctionMilliseconds(left, TICK_MILLISECONDS);
    aimDrawingAt(player, believedPlace(player, walk), now, milliseconds);
  }

  // Lets the drawing glide from where it is at `startAt` to `target`. This
  // is a correction, not a step: it never turns the character and never
  // starts, restarts or stops the run of its feet. Afterwards the glide is
  // no walking step any more, so the bridge does not go on from it.
  function aimDrawingAt(player, target, startAt, milliseconds) {
    var walked = walkedDistance(player, startAt);
    var start = drawnPosition(player, startAt);
    if (isFarApart(start, target.x, target.y)) {
      start = target; // too far to glide: shown there at once
    }
    player.from = { x: start.x, y: start.y };
    player.to = { x: target.x, y: target.y };
    player.arrivedAt = startAt;
    player.glideMilliseconds = milliseconds;
    player.walkedBeforeGlide = walked;
  }

  // Everything the bridge does when time has passed, up to `now`. Called
  // before every frame and before every own position is taken. It only
  // changes `player`, `walk` and `tally`, so ownDrawnPosition() can run it
  // on copies.
  function bridgeOwnGaps(player, walk, now, tally) {
    takeBridgedSteps(player, walk, now, tally);
    takeBackUnansweredSteps(walk, now, tally);
    returnToTheServerPosition(player, walk, now);
  }

  function bridgeOwnCharacter(now) {
    var own = ownPlayer();
    if (own && isBridging()) {
      bridgeOwnGaps(own, ownWalk, now, bridgeTally);
    }
  }

  // What nextStep() in bridge.js needs to know.
  function bridgeSituation(player, walk, now) {
    return {
      now: now,
      campus: campus,
      switchedOff: bridgingSwitchedOff,
      inputPaused: inputPaused,
      queueLength: player.queue.length,
      glideEndsAt: player.arrivedAt + player.glideMilliseconds,
      // takeStep() writes the start of the glide of a step into lastStepAt.
      glideWasAStep: player.lastStepAt === player.arrivedAt,
      from: believedPlace(player, walk),
      waitingSteps: walk.waiting.length,
      history: walk.history,
      inputLag: currentInputLag(),
      stepSeconds: serverStepSeconds()
    };
  }

  // Makes the bridged steps that are due. Usually that is none, or one;
  // after a late frame there is room for several, one after the other.
  function takeBridgedSteps(player, walk, now, tally) {
    for (var made = 0; made < bridge.MOST_BRIDGED_STEPS; made++) {
      var step = bridge.nextStep(bridgeSituation(player, walk, now));
      if (!step) {
        return;
      }
      takeBridgedStep(player, walk, step, tally);
    }
  }

  // The character glides to the bridged place. For its feet and the side
  // it faces this is a step like one from the server.
  function takeBridgedStep(player, walk, step, tally) {
    var milliseconds = step.endAt - step.startAt;
    startGlide(player, step.x, step.y, step.startAt, milliseconds);
    // Later server positions are scheduled behind this glide.
    player.queueEndsAt = step.endAt;
    walk.waiting = walk.waiting.concat([{ x: step.x, y: step.y, dx: step.dx, dy: step.dy }]);
    walk.lastBridgedEndsAt = step.endAt;
    walk.mayBeOffServer = true;
    tally.steps += 1;
    tally.milliseconds += milliseconds;
  }

  // Bridged steps the server has not answered for a second were never
  // walked by the server: they are forgotten.
  function takeBackUnansweredSteps(walk, now, tally) {
    if (walk.waiting.length === 0) {
      return;
    }
    var takeBackAt = bridge.takeBackAt(walk.lastBridgedEndsAt, walk.lastArrivalAt);
    if (now >= takeBackAt) {
      walk.waiting = [];
      walk.forgottenAt = takeBackAt;
      tally.takenBack += 1;
    }
  }

  // The rule that makes every bridge end right: once nothing is waiting,
  // the queue is empty and the glide is over, the character stands on the
  // newest server position. If it does not, it glides there.
  function returnToTheServerPosition(player, walk, now) {
    var isPlayedOut = walk.waiting.length === 0 && player.queue.length === 0;
    var glideEndsAt = player.arrivedAt + player.glideMilliseconds;
    if (!walk.mayBeOffServer || !isPlayedOut || glideEndsAt > now) {
      return;
    }
    walk.mayBeOffServer = false;
    // Compared exactly: a hair beside the server's position is not on it.
    if (player.to.x !== player.server.x || player.to.y !== player.server.y) {
      // From the moment this became due, not from `now`: a late frame
      // then draws the character where it would have been.
      var startAt = Math.max(glideEndsAt, walk.forgottenAt);
      aimDrawingAt(player, player.server, startAt, TICK_MILLISECONDS);
    }
  }

  // The bridged steps are not waited for any longer. The drawing still
  // returns to the server's position, see returnToTheServerPosition().
  function forgetBridgedSteps(now) {
    if (isBridging()) {
      ownWalk.waiting = [];
      ownWalk.forgottenAt = now;
    }
  }

  // The server put the own player somewhere else (the start of a round, a
  // respawn): nothing is waited for and nothing is returned to.
  function forgetTheBridge(now) {
    forgetBridgedSteps(now);
    if (isBridging()) {
      ownWalk.mayBeOffServer = false;
    }
  }

  // What the bridge did since the page loaded or since the last reset, for
  // the walking diagnostic: the counts of newTally() in bridge.js, `on`
  // (is the own character bridged?), `loaded` (did bridge.js load?),
  // `inputLagMs` and `serverStepMs` (the time one step of the server covers).
  function bridgeNumbers() {
    if (!bridge) {
      return { on: false, loaded: false };
    }
    var measured = { inputLagMs: currentInputLag(), serverStepMs: serverStepSeconds() * 1000 };
    return Object.assign({ on: isBridging(), loaded: true }, measured, bridgeTally);
  }

  function resetBridgeNumbers() {
    bridgeTally = bridge ? bridge.newTally() : null;
  }

  // ---- What the lobby page tells the world -----------------------------

  function setOwnName(name) {
    ownName = isName(name) ? name : null;
  }

  // The players of the lobby with their characters: [{name, character}].
  // Whoever is not in the list any more disappears.
  function setPlayers(list) {
    var listed = new Set();
    (Array.isArray(list) ? list : []).forEach(function (entry) {
      if (entry && isName(entry.name)) {
        playerNamed(entry.name).character = entry.character;
        listed.add(entry.name);
      }
    });
    players.forEach(function (player, name) {
      if (!listed.has(name)) {
        players.delete(name);
      }
    });
  }

  // Positions from the server, in map units: [{name, x, y}]. They are not
  // drawn at once but queued and played back a little later, see
  // receivePosition().
  // Ignored while the world is stopped: a message that arrives late, after
  // the player left a lobby, must not bring the players of that lobby back.
  function setPositions(list) {
    if (!running) {
      return;
    }
    var now = performance.now();
    rememberArrival(now);
    var delay = playbackDelay();
    (Array.isArray(list) ? list : []).forEach(function (entry) {
      if (entry && isName(entry.name) && isNumber(entry.x) && isNumber(entry.y)) {
        var player = playerNamed(entry.name);
        // Only the own character is bridged (M2-1.16); the others are
        // played from the queue as before.
        var receive = isOwn(player) && isBridging() ? receiveOwnPosition : receivePosition;
        receive(player, entry.x, entry.y, now, delay);
      }
    });
  }

  // ---- Stations: which one is in range, and opening it -----------------

  // The id of the station a player at (x, y) can use, or null: the closest
  // station whose centre is at most `useRange` away. Exactly at the range
  // still counts, and an exact tie goes to the smaller id. `usableIds` is an
  // array of the ids that count at all, or null for all stations.
  //
  // The server has the very same rule in server/world/stations.py, function
  // station_in_range. Change both together.
  function nearestStationInRange(x, y, stations, useRange, usableIds) {
    var bestId = null;
    var bestDistance = null;
    for (var i = 0; i < stations.length; i++) {
      var station = stations[i];
      if (usableIds !== null && usableIds.indexOf(station.id) === -1) {
        continue;
      }
      var distance = squaredDistance(x, y, station);
      // Written as "not at most" so that a broken position (not a number)
      // is in range of nothing: every comparison with it is false.
      if (!(distance <= useRange * useRange)) {
        continue;
      }
      if (isBetter(distance, station.id, bestDistance, bestId)) {
        bestId = station.id;
        bestDistance = distance;
      }
    }
    return bestId;
  }

  // Squared distances are compared instead of real ones: no square root is
  // needed, and JavaScript and Python then calculate exactly the same numbers.
  function squaredDistance(x, y, station) {
    var dx = station.x - x;
    var dy = station.y - y;
    return dx * dx + dy * dy;
  }

  // Is this station closer than the best one so far, or as close with a
  // smaller id?
  function isBetter(distance, stationId, bestDistance, bestId) {
    if (bestId === null) {
      return true;
    }
    if (distance !== bestDistance) {
      return distance < bestDistance;
    }
    return stationId < bestId;
  }

  // The id of the station the own player can use right now, or null. It
  // counts from the position the server sent last, not from where the
  // character is drawn (a little behind), so what glows is what the server
  // will accept.
  function stationInRange() {
    var own = ownName !== null && players.has(ownName) ? players.get(ownName).server : null;
    if (!running || !campus || !own || !Array.isArray(campus.stations)) {
      return null;
    }
    return nearestStationInRange(own.x, own.y, campus.stations, campus.use_range, usableStations);
  }

  function stationWithId(id) {
    var stations = campus.stations;
    for (var i = 0; i < stations.length; i++) {
      if (stations[i].id === id) {
        return stations[i];
      }
    }
    return null;
  }

  // Which stations count as targets. Only the current private target is
  // drawn; the others have no marker or glow. Only `null` means all of them. An array or a Set is the list of
  // ids. Anything else (nothing at all, a number, a text, an object) is a
  // mistake of the caller and means no station: a mistake must never open
  // every station.
  function setUsableStations(ids) {
    if (ids === null) {
      usableStations = null;
    } else if (Array.isArray(ids) || ids instanceof Set) {
      usableStations = Array.from(ids);
    } else {
      usableStations = [];
    }
  }

  // `handler(stationId)` is called when the player opens a station. Another
  // area sets it (the minigames); it stays set when the world stops.
  function setUseHandler(handler) {
    useHandler = typeof handler === "function" ? handler : null;
  }

  // Opens the station in range: with the key E or a click on the button.
  // Without a station in range or without a handler nothing happens, and
  // there is no message either (DESIGN.md, section 4).
  function useStationInRange() {
    var id = stationInRange();
    if (id !== null && useHandler && !inputPaused) {
      useHandler(id);
    }
  }

  // The button "E Use" at the bottom right of the map. It is made here and
  // not in index.html, so it only exists while the world runs.
  function addUseButton() {
    if (useButton) {
      return; // never two buttons
    }
    var button = document.createElement("button");
    button.type = "button";
    button.className = "button use-button";
    button.textContent = USE_BUTTON_TEXT;
    button.disabled = true; // grey until a station is in range
    button.addEventListener("click", onUseButtonClick);
    canvas.parentNode.appendChild(button);
    useButton = button; // remembered only once it is on the page
  }

  // A clicked button keeps the keyboard focus. Space and Enter would then
  // "click" it again (and again while held), so the focus is taken off
  // before the station opens.
  function onUseButtonClick() {
    useButton.blur();
    useStationInRange();
  }

  function removeUseButton() {
    if (useButton) {
      useButton.remove();
      useButton = null;
    }
  }

  // Grey and switched off while it would do nothing, yellow otherwise. The
  // stylesheet gives the two looks.
  function updateUseButton(idInRange) {
    var shouldBeDisabled = idInRange === null || inputPaused;
    if (!useButton || useButton.disabled === shouldBeDisabled) {
      return;
    }
    // Some browsers swallow key events while a switched-off button has the
    // focus. A lost release of a walk key would leave the player walking,
    // so the focus goes first.
    if (shouldBeDisabled && document.activeElement === useButton) {
      useButton.blur();
    }
    useButton.disabled = shouldBeDisabled;
  }

  // ---- Keyboard --------------------------------------------------------

  // Is the player writing into a field right now?
  function isTyping(event) {
    var target = event.target;
    if (!target || !target.tagName) {
      return false;
    }
    var tag = target.tagName.toUpperCase();
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable === true;
  }

  function isHeld(direction) {
    for (var code in KEY_DIRECTIONS) {
      if (KEY_DIRECTIONS[code] === direction && pressedKeys[code]) {
        return true;
      }
    }
    return false;
  }

  // Tells the server the direction, but only when it differs from the last
  // one sent. Opposite keys cancel each other: 1 - 1 = 0.
  function reportDirection() {
    var dx = (isHeld("right") ? 1 : 0) - (isHeld("left") ? 1 : 0);
    var dy = (isHeld("down") ? 1 : 0) - (isHeld("up") ? 1 : 0);
    if (dx === sentDirection.dx && dy === sentDirection.dy) {
      return;
    }
    if (sentDirection.dx === 0 && sentDirection.dy === 0) {
      walkingSince = performance.now(); // a new walk; turning keeps the old time
    }
    rememberOwnDirection(sentDirection, { dx: dx, dy: dy }, performance.now());
    sentDirection = { dx: dx, dy: dy };
    if (typeof sendMove === "function") {
      sendMove(dx, dy);
    }
  }

  // The Cmd key of a Mac (or the Windows key). While it is held, macOS does
  // not report the release of other keys, so a walk key could stay "pressed".
  function isMetaKey(event) {
    return event.key === "Meta";
  }

  // `event.code` names the place of the key on the keyboard, like the walk
  // keys do: this is the key in the E position (next to W), whatever letter
  // the layout writes with it. Caps Lock and Shift do not change the code.
  function isUseKey(event) {
    return event.code === USE_KEY_CODE;
  }

  function onKeyDown(event) {
    if (isMetaKey(event)) {
      releaseAllKeys();
      return;
    }
    // With Ctrl, Alt or Cmd held, the key is a shortcut of the browser.
    var isShortcut = event.ctrlKey || event.altKey || event.metaKey;
    if (isShortcut || isTyping(event)) {
      return;
    }
    if (inputPaused) {
      // A minigame is open: the keys do nothing on the map, but the arrow
      // keys must not scroll the page behind the window either.
      if (event.code.indexOf("Arrow") === 0) {
        event.preventDefault();
      }
      return;
    }
    if (isUseKey(event)) {
      // A key that is held down reports itself again and again: only the
      // first press opens the station.
      if (!event.repeat) {
        useStationInRange();
      }
      return;
    }
    if (!Object.prototype.hasOwnProperty.call(KEY_DIRECTIONS, event.code)) {
      return;
    }
    if (event.code.indexOf("Arrow") === 0) {
      event.preventDefault(); // otherwise the arrow keys scroll the page
    }
    pressedKeys[event.code] = true;
    reportDirection();
  }

  // A release always counts, also inside a text field: the key may have been
  // pressed before the player clicked into the field.
  function onKeyUp(event) {
    if (isMetaKey(event)) {
      releaseAllKeys();
    } else if (pressedKeys[event.code]) {
      delete pressedKeys[event.code];
      reportDirection();
    }
  }

  // There are moments after which the browser no longer reports the release
  // of a key: the window loses the focus, the tab is hidden, the menu of the
  // right mouse button opens, Cmd is pressed. Then all keys count as
  // released, so nobody keeps walking. (0, 0) is sent only if the player
  // was walking.
  function releaseAllKeys() {
    pressedKeys = {};
    reportDirection();
  }

  // While a minigame is open, the keys belong to it: the walk keys and E do
  // nothing and the button "E Use" is switched off (the next frame greys it).
  // Keys that are held count as released, so the server hears (0, 0) once
  // and the player does not walk on when the minigame closes.
  function setInputPaused(paused) {
    inputPaused = paused === true;
    if (inputPaused) {
      releaseAllKeys();
      // The server makes the player stand now: steps the browser made up
      // are not waited for any longer.
      forgetBridgedSteps(performance.now());
    }
  }

  function onVisibilityChange() {
    if (document.hidden) {
      releaseAllKeys();
    }
  }

  function listenToKeyboard() {
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", releaseAllKeys);
    window.addEventListener("contextmenu", releaseAllKeys);
    document.addEventListener("visibilitychange", onVisibilityChange);
  }

  function stopListeningToKeyboard() {
    window.removeEventListener("keydown", onKeyDown);
    window.removeEventListener("keyup", onKeyUp);
    window.removeEventListener("blur", releaseAllKeys);
    window.removeEventListener("contextmenu", releaseAllKeys);
    document.removeEventListener("visibilitychange", onVisibilityChange);
  }

  // ---- Canvas and camera -----------------------------------------------

  // Gives the canvas as many pixels as its box on the page has, times the
  // pixel density of the screen, so the drawing is sharp. Checked on every
  // frame, which also covers a resized window; the size is only set when the
  // box or the density has changed. The stylesheet must give the canvas its
  // size on the page (width and height).
  function fitCanvasToItsBox() {
    var density = window.devicePixelRatio || 1;
    var width = Math.round(canvas.clientWidth * density);
    var height = Math.round(canvas.clientHeight * density);
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
  }

  // The camera looks at the own character, or at the spawn point as long as
  // the server has not sent the own position.
  function cameraCentre(now) {
    var own = ownName !== null && players.has(ownName) ? drawnPosition(players.get(ownName), now) : null;
    return own || campus.spawn || { x: campus.width / 2, y: campus.height / 2 };
  }

  // Moves and scales the context so that drawing in map units puts `centre`
  // in the middle of the canvas. Returns the visible part of the world.
  function aimCamera(centre) {
    var scale = Math.max(canvas.width, canvas.height) / VIEW_SIZE;
    var viewWidth = canvas.width / scale;
    var viewHeight = canvas.height / scale;
    ctx.setTransform(scale, 0, 0, scale, canvas.width / 2 - centre.x * scale, canvas.height / 2 - centre.y * scale);
    return { x: centre.x - viewWidth / 2, y: centre.y - viewHeight / 2, w: viewWidth, h: viewHeight };
  }

  // ---- Drawing the players ---------------------------------------------

  // The name labels, in map units.
  var NAME_TEXT_SIZE = 5.5;
  var LABEL_HEIGHT = 8;
  var LABEL_OUTLINE = 0.7;

  // The names whose labels were hidden in the previous frame, because they
  // would have covered another label. Game.world.chooseLabels() needs them
  // so that a hidden name does not flicker back at the edge.
  var hiddenNames = new Set();

  // In the drawing order the own character counts as standing this many map
  // units further down. Everyone starts on the same spawn point; this way a
  // player sees their own character on top of the pile.
  var OWN_IN_FRONT = 4;

  function isOwn(player) {
    return player.name === ownName;
  }

  // Every player that has a position, with where to draw it right now.
  function visiblePlayers(now) {
    var visible = [];
    players.forEach(function (player) {
      var position = drawnPosition(player, now);
      if (position) {
        visible.push({ player: player, x: position.x, y: position.y });
      }
    });
    // Further down the screen means closer to the viewer: drawn later, on top.
    visible.sort(function (a, b) {
      var depthA = a.y + (isOwn(a.player) ? OWN_IN_FRONT : 0);
      var depthB = b.y + (isOwn(b.player) ? OWN_IN_FRONT : 0);
      return depthA - depthB;
    });
    return visible;
  }

  // The middle of the drawn character: above the position, feet at the
  // lower edge of the player's square.
  function figureMiddleY(y) {
    return y + FEET_BELOW_POSITION - CHARACTER_HEIGHT / 2;
  }

  // The pose passed to drawCharacter(). One object, filled in again for
  // every character, so that drawing makes no new object per frame.
  var pose = { mirrored: false, walkPhase: null, stride: 0 };

  // Every player is drawn by the same rule, from the positions the server
  // sent: the turned view, mirrored when the character faces left.
  function drawPlayer(entry, now) {
    var player = entry.player;
    pose.mirrored = player.facingLeft;
    pose.walkPhase = walkPhase(player, now);
    pose.stride = stride(player, now);
    if (!canDrawCharacter(player.character)) {
      drawStandIn(entry.x, entry.y);
      return;
    }
    var camera = ctx.getTransform();
    ctx.save();
    try {
      Game.world.drawCharacter(ctx, player.character, entry.x, figureMiddleY(entry.y), CHARACTER_HEIGHT, pose);
      ctx.restore();
    } catch (problem) {
      // The drawing may have stopped inside one of its own save() calls.
      // restore() then undoes only that last one, so the camera and full
      // opacity are set again by hand: the stand-in, the names and every
      // later player must land in their place.
      ctx.restore();
      ctx.setTransform(camera);
      ctx.globalAlpha = 1;
      // Not tried again: it would fail on every frame (M1-1.11).
      brokenCharacters.add(player.character);
      warnOnce("The character \"" + player.character + "\" could not be drawn; it is shown as a circle.", problem);
      drawStandIn(entry.x, entry.y);
    }
  }

  // ---- Stand-in when a character cannot be drawn (M1-1.11) -------------

  // If characters.js did not load, or its drawing fails for a character,
  // that player is drawn as a plain circle instead. The map keeps working
  // and every player stays visible.
  var STAND_IN_RADIUS = 7;
  var brokenCharacters = new Set(); // characters whose drawing failed once
  var hasWarned = false; // one warning in total, not one per frame

  function canDrawCharacter(characterId) {
    if (typeof Game.world.drawCharacter !== "function") {
      warnOnce("characters.js is missing; players are shown as circles.");
      return false;
    }
    return !brokenCharacters.has(characterId);
  }

  function warnOnce(text, problem) {
    if (!hasWarned) {
      hasWarned = true;
      console.warn(text, problem || "");
    }
  }

  // A circle in the outline colour where the body of the character would be.
  function drawStandIn(x, y) {
    ctx.beginPath();
    ctx.arc(x, figureMiddleY(y), STAND_IN_RADIUS, 0, Math.PI * 2);
    ctx.fillStyle = OUTLINE;
    ctx.fill();
  }

  function useNameFont() {
    ctx.font = "bold " + NAME_TEXT_SIZE + "px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
  }

  // The label of one player where it belongs: centred directly above the
  // head. `x` and `y` are the middle of the label; `width` and `height` are
  // the whole space it covers, the dark outline included.
  function labelAboveHead(entry) {
    var headTop = figureMiddleY(entry.y) - CHARACTER_HEIGHT / 2 - HEAD_ROOM_BELOW_NAME;
    var height = LABEL_HEIGHT + 2 * LABEL_OUTLINE;
    return {
      name: entry.player.name,
      x: entry.x,
      y: headTop - height / 2,
      width: ctx.measureText(entry.player.name).width + 6 + 2 * LABEL_OUTLINE,
      height: height,
      own: isOwn(entry.player)
    };
  }

  // One name: dark letters on a light pill.
  function drawLabel(label) {
    // A line with round ends, as thick as the pill is high, is a pill. Drawn
    // twice: a slightly thicker dark one below gives the cream one its
    // outline, so the pill shows on every floor. The round ends stick out
    // half the thickness beyond the two points of the line.
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(label.x - label.width / 2 + label.height / 2, label.y);
    ctx.lineTo(label.x + label.width / 2 - label.height / 2, label.y);
    ctx.lineWidth = LABEL_HEIGHT + 2 * LABEL_OUTLINE;
    ctx.strokeStyle = OUTLINE;
    ctx.stroke();
    ctx.lineWidth = LABEL_HEIGHT;
    ctx.strokeStyle = SURFACE;
    ctx.stroke();

    ctx.fillStyle = OUTLINE;
    ctx.fillText(label.name, label.x, label.y + 0.3);
  }

  function drawPlayers(now) {
    var visible = visiblePlayers(now);
    visible.forEach(function (entry) {
      drawPlayer(entry, now);
    });
    // All names after all characters, so no name is hidden behind a head.
    // Where labels would cover each other, only one of them is drawn; a
    // label never moves away from its own head (S-117).
    useNameFont();
    var choice = Game.world.chooseLabels(visible.map(labelAboveHead), hiddenNames);
    hiddenNames = choice.hidden;
    choice.shown.forEach(drawLabel);
  }

  // ---- The loop --------------------------------------------------------

  function drawFrame(now) {
    // Before anything is drawn: the camera, the names and the characters
    // must all use the same positions.
    playAllQueues(now);
    bridgeOwnCharacter(now);
    fitCanvasToItsBox();
    if (canvas.width === 0 || canvas.height === 0) {
      return; // the canvas is hidden
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = BACKGROUND;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (!campus) {
      drawLoadingText(); // the map file is still on its way
      return;
    }
    var view = aimCamera(cameraCentre(now));
    // The one private usable station is already the player's current task.
    // Older callers need not also set the optional navigator target.
    var visibleStation = Array.isArray(usableStations) && usableStations.length === 1
      ? usableStations[0] : null;
    Game.world.drawMap(ctx, campus, view, visibleStation);
    var idInRange = stationInRange();
    if (idInRange !== visibleStation) idInRange = null;
    if (idInRange !== null) {
      Game.world.drawStationGlow(ctx, stationWithId(idInRange), now);
    }
    updateUseButton(idInRange);
    var taskGuidance = updateGuidance();
    var ownPosition = cameraCentre(now);
    if (taskGuidance) Game.world.navigation.drawArrow(ctx, taskGuidance, ownPosition);
    drawPlayers(now);
    if (taskGuidance) Game.world.navigation.drawOverlay(ctx, taskGuidance, taskTitle, canvas);
  }

  // The browser calls this before every repaint of the screen, and not at
  // all while the tab is hidden. `now` is the same clock as performance.now().
  function onFrame(now) {
    if (!running) {
      return;
    }
    frameRequest = window.requestAnimationFrame(onFrame);
    drawFrame(now);
  }

  // Shown in the middle of the canvas, in canvas pixels, while there is no map.
  function drawLoadingText() {
    var textSize = Math.max(14, Math.round(canvas.height / 30));
    ctx.font = "bold " + textSize + "px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = OUTLINE;
    ctx.fillText(LOADING_TEXT, canvas.width / 2, canvas.height / 2);
  }

  // Downloads the map; it is needed only once. While the world runs, a
  // failed download is tried again every two seconds until it works.
  function loadCampus() {
    if (campus || isLoadingCampus) {
      return;
    }
    isLoadingCampus = true;
    fetch(MAP_FILE)
      .then(function (response) {
        if (!response.ok) {
          throw new Error("The map file answered with status " + response.status + ".");
        }
        return response.json();
      })
      .then(function (data) {
        isLoadingCampus = false;
        campus = data;
      })
      .catch(function (problem) {
        isLoadingCampus = false;
        console.warn("The map could not be loaded.", problem);
        if (running) {
          window.clearTimeout(retryTimer); // never two timers at once
          retryTimer = window.setTimeout(loadCampus, RETRY_MILLISECONDS);
        }
      });
  }

  // Starts drawing on `canvasElement` and listening to the keyboard.
  // `sendMoveFunction(dx, dy)` is called with -1, 0 or 1 whenever the
  // direction changes. Calling start again while running only swaps the two.
  function start(canvasElement, sendMoveFunction) {
    if (!canvasElement || typeof canvasElement.getContext !== "function") {
      return;
    }
    canvas = canvasElement;
    ctx = canvas.getContext("2d");
    sendMove = sendMoveFunction;
    if (running || !ctx) {
      return;
    }
    // The button comes first: if it cannot be made, nothing has started yet.
    addUseButton();
    running = true;
    // A retry may still wait from an earlier start: begin afresh.
    window.clearTimeout(retryTimer);
    loadCampus();
    listenToKeyboard();
    frameRequest = window.requestAnimationFrame(onFrame);
  }

  // Stops the loop and the keyboard, takes the button "E Use" away and
  // forgets players (with their queued positions), the arrival times of
  // the messages, hidden name labels, pressed keys and which stations were
  // usable.
  // Nothing is sent: whoever stops the world has left the lobby already.
  function stop() {
    if (running) {
      window.cancelAnimationFrame(frameRequest);
      window.clearTimeout(retryTimer);
      stopListeningToKeyboard();
    }
    removeUseButton();
    running = false;
    usableStations = null; // the next lobby starts with all stations again
    setTaskTarget(null);
    players.clear();
    arrivalTimes = [];
    hiddenNames = new Set(); // in the next lobby nobody counts as hidden before
    pressedKeys = {};
    sentDirection = { dx: 0, dy: 0 };
    sendMove = null;
    ownWalk = bridge ? bridge.newWalk() : null;
  }

  // ---- Read-only views for the walking diagnostic (diagnostic.js) ------

  // Where the frame at the time `now` draws the own character: {x, y}, or
  // null. It changes nothing, so it may be asked at any time, any number of
  // times.
  function ownDrawnPosition(now) {
    var own = ownPlayer();
    if (!own) {
      return null;
    }
    // The diagnostic's frame callback runs before drawFrame(), which starts
    // the queued glides whose time has come (playQueue) and bridges a gap
    // (bridgeOwnGaps). The very same functions run here, but on copies of
    // what they change: the answer is what the frame will draw, and the
    // real player is left as it was. (They change no object in place
    // except the queue, so the copies can be shallow.)
    var copy = Object.assign({}, own, { queue: own.queue.slice() });
    playQueue(copy, now);
    if (isBridging()) {
      bridgeOwnGaps(copy, Object.assign({}, ownWalk), now, bridge.newTally());
    }
    return drawnPosition(copy, now);
  }

  // The direction the server heard last, as a copy so it cannot be changed,
  // and `since`: when this walk started (the clock of performance.now()),
  // or null while the direction is (0, 0).
  function walkingDirection() {
    var isMoving = sentDirection.dx !== 0 || sentDirection.dy !== 0;
    return { dx: sentDirection.dx, dy: sentDirection.dy, since: isMoving ? walkingSince : null };
  }

  Game.world.start = start;
  Game.world.stop = stop;
  Game.world.setTaskTarget = setTaskTarget;
  Game.world.setOwnName = setOwnName;
  Game.world.setPlayers = setPlayers;
  Game.world.setPositions = setPositions;
  Game.world.startOfRound = startOfRound;
  Game.world.setUsableStations = setUsableStations;
  Game.world.setUseHandler = setUseHandler;
  Game.world.stationInRange = stationInRange;
  Game.world.setInputPaused = setInputPaused;
  Game.world.nearestStationInRange = nearestStationInRange;
  Game.world.ownDrawnPosition = ownDrawnPosition;
  Game.world.walkingDirection = walkingDirection;
  Game.world.bridgeNumbers = bridgeNumbers;
  Game.world.resetBridgeNumbers = resetBridgeNumbers;
})();
