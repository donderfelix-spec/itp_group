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

  // Height of a drawn character, in map units. Its body is then about as
  // wide as the 10 units the server counts for a player (S-86).
  var CHARACTER_HEIGHT = 26;
  // The server's position is the middle of that 10 x 10 square. The feet are
  // drawn at its lower edge, so a character stands in front of a wall the
  // way it collides with it.
  var FEET_BELOW_POSITION = 5;

  // The server sends positions about 15 times per second (S-72). A character
  // glides to each new position within one such interval.
  var GLIDE_MILLISECONDS = 1000 / 15;
  // A longer way than this in one message is a respawn: jump, do not glide.
  var JUMP_DISTANCE = 60;
  // How long after its last step a character still counts as walking. Longer
  // than one interval, so the bobbing does not flicker between two messages.
  var STILL_WALKING_MILLISECONDS = 160;
  var BOB_HEIGHT = 1.2; // map units
  var BOB_MILLISECONDS = 280; // one step up and down

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
  var USE_KEY = "e";
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
      lastStepAt: -Infinity, // when the position last changed
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
    var start = drawnPosition(player, now) || { x: x, y: y };
    var isJump = Math.abs(x - start.x) > JUMP_DISTANCE || Math.abs(y - start.y) > JUMP_DISTANCE;
    if (isJump) {
      start = { x: x, y: y };
    }
    var hasStepped = player.to && (player.to.x !== x || player.to.y !== y);
    if (hasStepped && !isJump) {
      player.lastStepAt = now;
      // Walking straight up or down keeps the side the character faced.
      if (x < player.to.x) {
        player.facingLeft = true;
      } else if (x > player.to.x) {
        player.facingLeft = false;
      }
    }
    player.from = start;
    player.to = { x: x, y: y };
    player.arrivedAt = now;
  }

  function isWalking(player, now) {
    return now - player.lastStepAt < STILL_WALKING_MILLISECONDS;
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

  // Which stations count as targets: an array of station ids, or null for
  // all of them. The others are still drawn but never glow.
  function setUsableStations(ids) {
    usableStations = Array.isArray(ids) ? ids.slice() : null;
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
    if (id !== null && useHandler) {
      useHandler(id);
    }
  }

  // The button "E Use" at the bottom right of the map. It is made here and
  // not in index.html, so it only exists while the world runs.
  function addUseButton() {
    if (useButton) {
      return; // never two buttons
    }
    useButton = document.createElement("button");
    useButton.type = "button";
    useButton.className = "button use-button";
    useButton.textContent = USE_BUTTON_TEXT;
    useButton.disabled = true; // grey until a station is in range
    useButton.addEventListener("click", useStationInRange);
    canvas.parentNode.appendChild(useButton);
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
    var shouldBeDisabled = idInRange === null;
    if (useButton && useButton.disabled !== shouldBeDisabled) {
      useButton.disabled = shouldBeDisabled;
    }
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

  // `event.key` is the letter the key writes, so this is the key with an E
  // on it on every keyboard layout. With Caps Lock or Shift it is "E".
  function isUseKey(event) {
    return typeof event.key === "string" && event.key.toLowerCase() === USE_KEY;
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
  var LABEL_GAP = 1; // free space between two labels above each other

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

  function drawPlayer(entry, now) {
    var bob = 0;
    if (isWalking(entry.player, now)) {
      bob = Math.abs(Math.sin(now / BOB_MILLISECONDS * Math.PI)) * BOB_HEIGHT;
    }
    ctx.save();
    ctx.translate(entry.x, figureMiddleY(entry.y) - bob);
    if (entry.player.facingLeft) {
      ctx.scale(-1, 1); // mirrored: the character looks to the left
    }
    Game.world.drawCharacter(ctx, entry.player.character, 0, 0, CHARACTER_HEIGHT);
    ctx.restore();
  }

  function useNameFont() {
    ctx.font = "bold " + NAME_TEXT_SIZE + "px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
  }

  // The label of one player where it belongs: centred directly above the
  // head. `x` and `y` are the middle of the label.
  function labelAboveHead(entry) {
    var headTop = figureMiddleY(entry.y) - CHARACTER_HEIGHT / 2 - BOB_HEIGHT;
    return {
      name: entry.player.name,
      x: entry.x,
      y: headTop - LABEL_OUTLINE - LABEL_HEIGHT / 2,
      width: ctx.measureText(entry.player.name).width + 6
    };
  }

  function labelsOverlap(a, b) {
    var besideEachOther = Math.abs(a.x - b.x) >= (a.width + b.width) / 2 + 2 * LABEL_OUTLINE;
    var aboveEachOther = Math.abs(a.y - b.y) >= LABEL_HEIGHT + 2 * LABEL_OUTLINE;
    return !besideEachOther && !aboveEachOther;
  }

  // Decides where every label goes, so that no label covers another one.
  // The labels are placed one after the other, the own one first: it always
  // stays directly above the own head. A label that would cover one already
  // placed moves up, one label height at a time, until its place is free.
  // Nothing is remembered between frames, so a label is back above its
  // figure as soon as the figures stand apart.
  function placeLabels(visible) {
    var ownFirst = visible.filter(function (entry) { return isOwn(entry.player); })
      .concat(visible.filter(function (entry) { return !isOwn(entry.player); }));
    var placed = [];
    ownFirst.forEach(function (entry) {
      var label = labelAboveHead(entry);
      var isCovered = function (other) { return labelsOverlap(label, other); };
      while (placed.some(isCovered)) {
        label.y -= LABEL_HEIGHT + 2 * LABEL_OUTLINE + LABEL_GAP;
      }
      placed.push(label);
    });
    return placed;
  }

  // One name: dark letters on a light pill.
  function drawLabel(label) {
    // A line with round ends, as thick as the pill is high, is a pill. Drawn
    // twice: a slightly thicker dark one below gives the cream one its
    // outline, so the pill shows on every floor.
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(label.x - label.width / 2 + LABEL_HEIGHT / 2, label.y);
    ctx.lineTo(label.x + label.width / 2 - LABEL_HEIGHT / 2, label.y);
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
    useNameFont();
    placeLabels(visible).forEach(drawLabel);
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
    running = true;
    // A retry may still wait from an earlier start: begin afresh.
    window.clearTimeout(retryTimer);
    loadCampus();
    listenToKeyboard();
    addUseButton();
    frameRequest = window.requestAnimationFrame(onFrame);
  }

  // Stops the loop and the keyboard, takes the button "E Use" away and
  // forgets players, pressed keys and which stations were usable.
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
    pressedKeys = {};
    sentDirection = { dx: 0, dy: 0 };
    sendMove = null;
  }

  Game.world.start = start;
  Game.world.stop = stop;
  Game.world.setOwnName = setOwnName;
  Game.world.setPlayers = setPlayers;
  Game.world.setPositions = setPositions;
  Game.world.setUsableStations = setUsableStations;
  Game.world.setUseHandler = setUseHandler;
  Game.world.stationInRange = stationInRange;
  Game.world.nearestStationInRange = nearestStationInRange;
})();
