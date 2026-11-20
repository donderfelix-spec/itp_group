// The world on the canvas: the drawing loop, the camera, the keyboard, the
// smoothing of the players' movement and the task stations a player can use.
//
// The browser decides nothing here (AGENTS.md, rule 1). The keyboard only
// tells the server where the player wants to go, and every position that is
// drawn, also the own one, comes from the server.

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

  // How long a character glides to each new position. The server sends
  // positions about every 67 ms (15 times per second, S-72), but over the
  // internet a message often arrives later. The glide lasts longer than one
  // interval, so a message up to about 40 ms late does not leave the
  // character and the camera standing still. Every glide starts where the
  // character is drawn, so the speed stays the same: the character is only
  // drawn about 40 ms further behind the server than with a glide of one
  // interval.
  var GLIDE_MILLISECONDS = 110;
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
  // Some ways of walking start and stop at once instead (see
  // walkStartsInstantly()). Their steps end this long after the glide of
  // the last step, so a message that comes a little late does not make the
  // legs stand still for a moment.
  var STEP_GRACE_MILLISECONDS = 40;
  // One walking cycle is two steps: left foot, right foot. It runs on the
  // way the drawn character covers, not on the time, so a foot on the
  // ground moves with the ground on every screen, also when a message is
  // late or the character stops against a wall. How many map units one
  // cycle takes comes from the drawing (walkCycleLength() in
  // characters.js); this one is used if the drawing gives none, as when
  // characters.js did not load (the players are circles then anyway).
  var WALK_CYCLE_LENGTH_WITHOUT_DRAWING = 38;
  // A change of position smaller than this, in map units, is not a step: it
  // neither turns the character nor moves its feet. A real step is about 6
  // units (90 units per second, 15 messages per second, S-86).
  var SMALLEST_STEP = 1;
  // Free room between the top of a standing character and its name, in map
  // units. A walking character rises on every step (BODY_BOB in
  // characters.js: 3 of its 112 design units, which is 1.05 map units at
  // CHARACTER_HEIGHT). This room must be at least that rise, so a head
  // never touches its name.
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
  var usableStations = null; // ids of the stations that count, null = all
  var useHandler = null; // called with the id of the station that is opened
  var useButton = null; // the button "E Use", while the world runs
  var inputPaused = false; // true while a minigame is open, see setInputPaused()

  // ---- Players and smoothing -------------------------------------------

  function newPlayer(name) {
    return {
      name: name,
      character: null,
      // The character glides from `from` to `to`. Both are null until the
      // first position has arrived; until then the player is not drawn.
      from: null,
      to: null,
      arrivedAt: 0, // when `to` arrived, in milliseconds
      lastStepAt: -Infinity, // when the character last took a step
      strideAtLastStep: 0, // how big its steps were at that moment, 0 to 1
      // How far the drawn character had walked, in map units, when the
      // current glide started (see walkedDistance()) ...
      walkedBeforeGlide: 0,
      // ... and when it started to walk; the walking cycle starts here.
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
    var progress = (now - player.arrivedAt) / GLIDE_MILLISECONDS;
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
    });
  }

  // How big the steps of the player are at the time `now`, from 0 (it
  // stands) to 1 (full steps). After a step they grow to full size; once the
  // glide of that step is over and no new step has come, they fade away.
  // For a way of walking that starts and stops at once they are 1 from the
  // step until STEP_GRACE_MILLISECONDS after its glide, and 0 after that.
  // It only depends on the time, like drawnPosition(), so it looks the same
  // on every screen, however often that screen is redrawn.
  function stride(player, now) {
    // Never below 0: the time of a frame can lie a moment before the time
    // at which the message with the step arrived.
    var sinceStep = Math.max(0, now - player.lastStepAt);
    if (walkStartsInstantly()) {
      return sinceStep <= GLIDE_MILLISECONDS + STEP_GRACE_MILLISECONDS ? 1 : 0;
    }
    var grown = Math.min(1, player.strideAtLastStep + sinceStep / STRIDE_GROWS_MILLISECONDS);
    var faded = (sinceStep - GLIDE_MILLISECONDS) / STRIDE_FADES_MILLISECONDS;
    faded = Math.max(0, Math.min(1, faded));
    // Slow at the start and at the end (the curve 3t² - 2t³). A message that
    // is a little late then hardly shrinks the steps before it arrives.
    var easedFade = faded * faded * (3 - 2 * faded);
    return grown * (1 - easedFade);
  }

  function isWalking(player, now) {
    return stride(player, now) > 0;
  }

  // How far the player is in its walking cycle, from 0 to 1, or null when
  // it stands. The cycle starts with the feet side by side and moves on only
  // while the drawn character moves.
  function walkPhase(player, now) {
    if (!isWalking(player, now)) {
      return null;
    }
    var walked = Math.max(0, walkedDistance(player, now) - player.walkedWhenItStarted);
    return (walked / walkCycleLength()) % 1;
  }

  // TEMPORARY (M2-1.13 proposals): true if the drawing asks for steps that
  // are full at once and gone at once (the variants O1 and O2), false for
  // the steps that grow and shrink (also when characters.js did not load).
  // Called outside the protection of drawPlayer(), so it never fails.
  function walkStartsInstantly() {
    var fromDrawing = Game.world.walkStartsInstantly;
    return typeof fromDrawing === "function" && fromDrawing() === true;
  }

  // Map units per walking cycle, from the drawing if it gives a usable
  // number. Called outside the protection of drawPlayer(), so it checks
  // everything and never fails.
  function walkCycleLength() {
    var fromDrawing = Game.world.walkCycleLength;
    var length = typeof fromDrawing === "function" ? Number(fromDrawing()) : NaN;
    return isFinite(length) && length > 0 ? length : WALK_CYCLE_LENGTH_WITHOUT_DRAWING;
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

  // Positions from the server, in map units: [{name, x, y}].
  // Ignored while the world is stopped: a message that arrives late, after
  // the player left a lobby, must not bring the players of that lobby back.
  function setPositions(list) {
    if (!running) {
      return;
    }
    var now = performance.now();
    (Array.isArray(list) ? list : []).forEach(function (entry) {
      if (entry && isName(entry.name) && isNumber(entry.x) && isNumber(entry.y)) {
        moveTo(playerNamed(entry.name), entry.x, entry.y, now);
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
  // gliding character is drawn, so what glows is what the server will accept.
  function stationInRange() {
    var own = ownName !== null && players.has(ownName) ? players.get(ownName).to : null;
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

  // Which stations count as targets. The others are still drawn but never
  // glow. Only `null` means all of them. An array or a Set is the list of
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
    Game.world.drawMap(ctx, campus, view);
    var idInRange = stationInRange();
    if (idInRange !== null) {
      Game.world.drawStationGlow(ctx, stationWithId(idInRange), now);
    }
    updateUseButton(idInRange);
    drawPlayers(now);
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
  // forgets players, hidden name labels, pressed keys and which stations
  // were usable.
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
    players.clear();
    hiddenNames = new Set(); // in the next lobby nobody counts as hidden before
    pressedKeys = {};
    sentDirection = { dx: 0, dy: 0 };
    sendMove = null;
  }

  Game.world.start = start;
  Game.world.stop = stop;
  Game.world.setOwnName = setOwnName;
  Game.world.setPlayers = setPlayers;
  Game.world.setPositions = setPositions;
  Game.world.startOfRound = startOfRound;
  Game.world.setUsableStations = setUsableStations;
  Game.world.setUseHandler = setUseHandler;
  Game.world.stationInRange = stationInRange;
  Game.world.setInputPaused = setInputPaused;
  Game.world.nearestStationInRange = nearestStationInRange;
  // TEMPORARY (M2-1.13 proposals): the numbers the comparison page needs to
  // walk a character the way this file does, without a server.
  // Removed with the variant Felix does not choose, before the pull request.
  Game.world.walkingProposal = {
    glideMs: GLIDE_MILLISECONDS,
    strideFadesMs: STRIDE_FADES_MILLISECONDS,
    stepGraceMs: STEP_GRACE_MILLISECONDS
  };
})();
