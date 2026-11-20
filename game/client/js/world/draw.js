// Draws the campus map from the data in campus.json (decision S-79).
//
// Places and sizes are never written down here: they all come from the map
// file, which the server also reads for collision. This file only knows how a
// "bench" or a "tree" looks. Everything is drawn in map units; world.js sets
// the scale and the camera before it calls drawMap().

"use strict";

window.Game = window.Game || {};
Game.world = Game.world || {};

(function () {
  var OUTLINE = "#2E2A3B";
  var FONT = "system-ui, sans-serif";

  // Colours from DESIGN.md, section 1, and from the sketch design/map.svg.
  var YELLOW = "#FFD23F";
  var CORAL = "#F2695C";
  var GREEN = "#5FA86B";
  var WATER = "#9CD3E6";
  var WATER_SHINE = "#DDF0FA";
  var PAVING_LINE = "#E1DBCD";
  var PAVING_TILE = 24; // side of one paving tile, in map units

  // Furniture that is a plain box or circle: colour, outline width, corner radius.
  var SIMPLE_KINDS = {
    "board": { fill: OUTLINE, line: 0, radius: 0 },
    "bench": { fill: "#FFFFFF", line: 2, radius: 3 },
    "table": { fill: "#FFFFFF", line: 2.5, radius: 3 },
    "table-row": { fill: "#8DB4E8", line: 2, radius: 3 },
    "bookshelf": { fill: "#5C7FB8", line: 0, radius: 2 },
    "shelf": { fill: "#7DB55A", line: 2, radius: 3 },
    "checkout": { fill: OUTLINE, line: 0, radius: 3 },
    "hedge": { fill: GREEN, line: 2.5, radius: 8 },
    "column": { fill: "#FFFFFF", line: 2.5, round: true },
    "round-table": { fill: "#D9A85F", line: 2, round: true }
  };

  // A counter has the colour of its room: wood in the café, green in the canteen.
  var COUNTER_COLOURS = { "mon-cafe": "#B98A5E", "canteen": "#7FBF9A" };
  var COUNTER_COLOUR_ELSEWHERE = "#B98A5E";

  // Furniture that needs more than one shape has its own function.
  var SPECIAL_KINDS = {
    "wall": drawWall,
    "glass": drawGlass,
    "counter": drawCounter,
    "machine": drawMachine,
    "pool": drawPool,
    "tree": drawTree,
    "logo": drawLogo
  };

  // ---- Small drawing helpers -------------------------------------------

  function paint(ctx, fill, lineWidth) {
    if (fill) {
      ctx.fillStyle = fill;
      ctx.fill();
    }
    if (lineWidth) {
      ctx.strokeStyle = OUTLINE;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    }
  }

  function box(ctx, rect, radius, fill, lineWidth) {
    // A corner cannot be rounder than half the shorter side.
    var r = Math.min(radius, rect.w / 2, rect.h / 2);
    ctx.beginPath();
    ctx.moveTo(rect.x + r, rect.y);
    ctx.arcTo(rect.x + rect.w, rect.y, rect.x + rect.w, rect.y + rect.h, r);
    ctx.arcTo(rect.x + rect.w, rect.y + rect.h, rect.x, rect.y + rect.h, r);
    ctx.arcTo(rect.x, rect.y + rect.h, rect.x, rect.y, r);
    ctx.arcTo(rect.x, rect.y, rect.x + rect.w, rect.y, r);
    ctx.closePath();
    paint(ctx, fill, lineWidth);
  }

  function circle(ctx, x, y, radius, fill, lineWidth) {
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    paint(ctx, fill, lineWidth);
  }

  // The circle that fits into a rectangle. The map file stores round things
  // as their bounding squares.
  function circleIn(ctx, rect, fill, lineWidth) {
    circle(ctx, rect.x + rect.w / 2, rect.y + rect.h / 2, Math.min(rect.w, rect.h) / 2, fill, lineWidth);
  }

  function line(ctx, x1, y1, x2, y2, colour, lineWidth) {
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.strokeStyle = colour;
    ctx.lineWidth = lineWidth;
    ctx.stroke();
  }

  function text(ctx, words, x, y, size) {
    ctx.font = "bold " + size + "px " + FONT;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = OUTLINE;
    ctx.fillText(words, x, y);
  }

  function list(value) {
    return Array.isArray(value) ? value : [];
  }

  // The room a point lies in, or null on the deck.
  function roomAt(campus, x, y) {
    var rooms = list(campus.rooms);
    for (var i = 0; i < rooms.length; i++) {
      var room = rooms[i];
      if (x >= room.x && x <= room.x + room.w && y >= room.y && y <= room.y + room.h) {
        return room;
      }
    }
    return null;
  }

  // ---- Ground: lawn, beach, deck, rooms --------------------------------

  // `view` is the part of the world the camera shows. The lawn and the bands
  // fill it to its edges, so there is ground beside and below the map too.
  function drawGround(ctx, campus, view) {
    ctx.fillStyle = campus.colours.lawn;
    ctx.fillRect(view.x, view.y, view.w, view.h);
    var bands = list(campus.bands);
    for (var i = 0; i < bands.length; i++) {
      var band = bands[i];
      var isLast = i === bands.length - 1;
      // The last band (the sea) goes on to the lower edge of the view.
      var bottom = isLast ? Math.max(band.y + band.h, view.y + view.h) : band.y + band.h;
      ctx.fillStyle = band.colour;
      ctx.fillRect(view.x, band.y, view.w, bottom - band.y);
      if (band.id === "sea") {
        drawWaves(ctx, band, view);
      }
    }
  }

  // One wavy light line across the sea.
  function drawWaves(ctx, sea, view) {
    var waveLength = 34;
    var waveHeight = 3.5;
    var y = sea.y + sea.h * 0.4;
    // Start on a whole wave left of the view, so the line does not slide
    // when the camera moves.
    var x = Math.floor(view.x / waveLength) * waveLength;
    ctx.beginPath();
    ctx.moveTo(x, y);
    for (; x < view.x + view.w; x += waveLength) {
      ctx.quadraticCurveTo(x + waveLength / 4, y - waveHeight, x + waveLength / 2, y);
      ctx.quadraticCurveTo(x + waveLength * 3 / 4, y + waveHeight, x + waveLength, y);
    }
    ctx.strokeStyle = WATER_SHINE;
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  function traceDeck(ctx, corners) {
    ctx.beginPath();
    for (var i = 0; i < corners.length; i++) {
      ctx.lineTo(corners[i].x, corners[i].y); // the first lineTo only sets the start
    }
    ctx.closePath();
  }

  // The paved deck: its colour, with the joints between the tiles on top.
  function drawDeck(ctx, campus) {
    var corners = list(campus.deck);
    if (corners.length < 3) {
      return;
    }
    traceDeck(ctx, corners);
    ctx.fillStyle = campus.colours.deck;
    ctx.fill();
    ctx.save();
    ctx.clip(); // the joints are drawn across the whole map but show only on the deck
    for (var x = PAVING_TILE; x < campus.width; x += PAVING_TILE) {
      line(ctx, x, 0, x, campus.height, PAVING_LINE, 1.5);
    }
    for (var y = PAVING_TILE; y < campus.height; y += PAVING_TILE) {
      line(ctx, 0, y, campus.width, y, PAVING_LINE, 1.5);
    }
    ctx.restore();
    // The deck's name has its own place in the map file, away from the spawn
    // point, so players who appear there do not stand on it.
    var label = campus.deck_label;
    if (label && label.name) {
      text(ctx, label.name, label.x, label.y, 13);
    }
  }

  function drawRoomFloors(ctx, campus) {
    var rooms = list(campus.rooms);
    for (var i = 0; i < rooms.length; i++) {
      ctx.fillStyle = rooms[i].floor;
      ctx.fillRect(rooms[i].x, rooms[i].y, rooms[i].w, rooms[i].h);
    }
  }

  // A door is an opening in the wall, shown as a strip of deck paving.
  function drawDoors(ctx, campus) {
    var doors = list(campus.doors);
    for (var i = 0; i < doors.length; i++) {
      ctx.fillStyle = campus.colours.deck;
      ctx.fillRect(doors[i].x, doors[i].y, doors[i].w, doors[i].h);
    }
  }

  // Each room's name stands at its `label` from the map file: the middle of
  // the text, placed by hand where the sketch has it.
  function drawRoomNames(ctx, campus) {
    var rooms = list(campus.rooms);
    for (var i = 0; i < rooms.length; i++) {
      var room = rooms[i];
      if (!room.label) {
        continue;
      }
      // A long name gets smaller letters in a narrow room.
      var size = room.name.length * 8 > room.w ? 12 : 13;
      text(ctx, room.name, room.label.x, room.label.y, size);
    }
  }

  // ---- Solids: walls and furniture -------------------------------------

  function drawWall(ctx, wall) {
    ctx.fillStyle = OUTLINE;
    ctx.fillRect(wall.x, wall.y, wall.w, wall.h);
  }

  // The glass front to the beach: light blue, two posts, a few glints.
  function drawGlass(ctx, glass) {
    box(ctx, glass, 2, "#8FD0EC", 2);
    var bottom = glass.y + glass.h;
    line(ctx, glass.x + glass.w / 3, glass.y, glass.x + glass.w / 3, bottom, OUTLINE, 2);
    line(ctx, glass.x + glass.w * 2 / 3, glass.y, glass.x + glass.w * 2 / 3, bottom, OUTLINE, 2);
    ctx.lineCap = "round";
    // Two slanted white strokes in the middle of each of the three panes.
    for (var pane = 0; pane < 3; pane++) {
      var middle = glass.x + glass.w * (pane * 2 + 1) / 6;
      line(ctx, middle - 10, bottom - 2, middle - 3, glass.y + 2, "#FFFFFF", 2);
      line(ctx, middle + 4, bottom - 2, middle + 11, glass.y + 2, "#FFFFFF", 2);
    }
    ctx.lineCap = "butt";
  }

  function drawCounter(ctx, counter, campus) {
    var room = roomAt(campus, counter.x + counter.w / 2, counter.y + counter.h / 2);
    var colour = (room && COUNTER_COLOURS[room.id]) || COUNTER_COLOUR_ELSEWHERE;
    box(ctx, counter, 3, colour, 2.5);
  }

  // The coffee machine: a grey box with a red and a yellow light.
  function drawMachine(ctx, machine) {
    box(ctx, machine, 3, "#5E6472", 2.5);
    var y = machine.y + machine.h / 2;
    var lightRadius = machine.h / 6;
    circle(ctx, machine.x + machine.w * 0.3, y, lightRadius, CORAL, 0);
    circle(ctx, machine.x + machine.w * 0.7, y, lightRadius, YELLOW, 0);
  }

  // The reflecting pool with two highlights on the water.
  function drawPool(ctx, pool) {
    box(ctx, pool, 4, WATER, 2.5);
    ctx.lineCap = "round";
    var upper = pool.y + pool.h * 0.36;
    var lower = pool.y + pool.h * 0.68;
    line(ctx, pool.x + pool.w * 0.09, upper, pool.x + pool.w * 0.4, upper, WATER_SHINE, 2);
    line(ctx, pool.x + pool.w * 0.51, lower, pool.x + pool.w * 0.88, lower, WATER_SHINE, 2);
    ctx.lineCap = "butt";
  }

  // A young tree: a square gravel bed with the green crown in the middle.
  function drawTree(ctx, bed) {
    box(ctx, bed, 3, "#D9D2C2", 2);
    circle(ctx, bed.x + bed.w / 2, bed.y + bed.h / 2, bed.w * 0.32, GREEN, 2);
  }

  // The letters N, O, V, A as thick lines, each in a quarter of the logo's
  // rectangle. As in the real logo, the O is small and underlined and the A
  // has no bar.
  function drawLogo(ctx, logo) {
    var thickness = logo.h * 0.21;
    var cell = (logo.w - thickness) / 4;
    var letterWidth = cell * 0.74;
    var top = logo.y + logo.h * 0.12;
    var bottom = logo.y + logo.h * 0.97;
    // The pointed ends of V and A stick out past the line, so they end early.
    var tip = thickness * 0.75;

    ctx.strokeStyle = OUTLINE;
    ctx.lineWidth = thickness;
    ctx.lineJoin = "miter";
    for (var i = 0; i < 4; i++) {
      var left = logo.x + thickness / 2 + cell * i + (cell - letterWidth) / 2;
      var right = left + letterWidth;
      var middle = (left + right) / 2;
      ctx.beginPath();
      if (i === 0) { // N
        ctx.moveTo(left, bottom);
        ctx.lineTo(left, top);
        ctx.lineTo(right, bottom);
        ctx.lineTo(right, top);
      } else if (i === 1) { // O: a ring, with a line under it
        var radius = Math.min(letterWidth / 2, (bottom - top) * 0.3);
        ctx.arc(middle, top + radius, radius, 0, Math.PI * 2);
        ctx.moveTo(middle - radius - thickness / 2, bottom - thickness * 0.4);
        ctx.lineTo(middle + radius + thickness / 2, bottom - thickness * 0.4);
      } else if (i === 2) { // V
        ctx.moveTo(left, top);
        ctx.lineTo(middle, bottom - tip);
        ctx.lineTo(right, top);
      } else { // A
        ctx.moveTo(left, bottom);
        ctx.lineTo(middle, top + tip);
        ctx.lineTo(right, bottom);
      }
      ctx.stroke();
    }
    ctx.lineJoin = "round";
  }

  // A kind this file does not know is still drawn, as a grey box: something
  // the server treats as solid must never be invisible.
  function drawSolid(ctx, solid, campus) {
    var special = SPECIAL_KINDS[solid.kind];
    var simple = SIMPLE_KINDS[solid.kind];
    if (special) {
      special(ctx, solid, campus);
    } else if (simple && simple.round) {
      circleIn(ctx, solid, simple.fill, simple.line);
    } else if (simple) {
      box(ctx, solid, simple.radius, simple.fill, simple.line);
    } else {
      box(ctx, solid, 2, "#B9B4A6", 2);
    }
  }

  function drawSolids(ctx, campus) {
    var solids = list(campus.solids);
    for (var i = 0; i < solids.length; i++) {
      drawSolid(ctx, solids[i], campus);
    }
  }

  // ---- Things to walk up to --------------------------------------------

  // Hiding spots: half transparent white circles with a dashed outline.
  function drawHidingSpots(ctx, campus) {
    var spots = list(campus.hiding_spots);
    ctx.setLineDash([4, 3]);
    for (var i = 0; i < spots.length; i++) {
      circle(ctx, spots[i].x, spots[i].y, spots[i].r, "rgba(255, 255, 255, 0.55)", 2);
    }
    ctx.setLineDash([]);
  }

  // The red button for the emergency meeting.
  function drawButton(ctx, campus) {
    if (campus.button) {
      circle(ctx, campus.button.x, campus.button.y, campus.button.r, CORAL, 2.5);
    }
  }

  // Task stations: yellow dots with their number.
  function drawStations(ctx, campus) {
    var stations = list(campus.stations);
    for (var i = 0; i < stations.length; i++) {
      var station = stations[i];
      circle(ctx, station.x, station.y, station.r, YELLOW, 2.5);
      text(ctx, String(station.id), station.x, station.y + 0.5, station.r * 1.1);
    }
  }

  // How long one pulse of the glowing border takes, in milliseconds
  // (DESIGN.md, section 4: "pulses slowly").
  var PULSE_MILLISECONDS = 1400;

  // The border around the station the player can use right now: a yellow
  // ring that grows and shrinks a little. `now` is the time of the frame in
  // milliseconds; nothing is remembered between two frames.
  function drawStationGlow(ctx, station, now) {
    if (!ctx || !station) {
      return;
    }
    // Swings between 0 and 1 and back, once per pulse.
    var pulse = 0.5 - 0.5 * Math.cos(now / PULSE_MILLISECONDS * Math.PI * 2);
    var radius = station.r + 3.5 + pulse * 2;
    ctx.save();
    // A soft, see-through yellow halo that gets stronger with the pulse.
    ctx.globalAlpha = 0.25 + 0.4 * pulse;
    circle(ctx, station.x, station.y, radius, null, 0);
    ctx.strokeStyle = YELLOW;
    ctx.lineWidth = 7 + 3 * pulse;
    ctx.stroke();
    ctx.globalAlpha = 1;
    // The ring itself: yellow on a slightly thicker dark ring, so it has an
    // outline and shows on every floor colour.
    ctx.strokeStyle = OUTLINE;
    ctx.lineWidth = 4.4;
    ctx.stroke();
    ctx.strokeStyle = YELLOW;
    ctx.lineWidth = 2.2;
    ctx.stroke();
    ctx.restore();
  }

  // ---- The whole map ---------------------------------------------------

  // Draws the map in map units. `view` ({x, y, w, h}, optional) is the part
  // of the world that is visible; without it the whole map is assumed.
  // The order matters: what is drawn later lies on top.
  function drawMap(ctx, campus, view) {
    if (!ctx || !campus || !campus.colours) {
      return;
    }
    view = view || { x: 0, y: 0, w: campus.width, h: campus.height };
    ctx.save();
    ctx.lineJoin = "round";
    drawGround(ctx, campus, view);
    drawDeck(ctx, campus);
    drawRoomFloors(ctx, campus);
    drawDoors(ctx, campus);
    drawRoomNames(ctx, campus);
    drawSolids(ctx, campus);
    drawHidingSpots(ctx, campus);
    drawButton(ctx, campus);
    drawStations(ctx, campus);
    ctx.restore();
  }

  Game.world.drawMap = drawMap;
  Game.world.drawStationGlow = drawStationGlow;
})();
