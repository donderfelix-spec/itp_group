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
  var CREAM = "#F4EFE3";
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

  // ---- Rectangles and the art files (M2-1.4) ----------------------------

  // How far a drawing may reach past its rectangle: outlines, a chair that
  // overhangs its table, a shadow. Things are drawn when this much of a
  // margin reaches into the area being drawn.
  var DRAWING_OVERHANG = 4;

  // True when the rectangle `thing`, with the overhang, reaches into `area`.
  function reaches(thing, area) {
    return thing.x - DRAWING_OVERHANG < area.x + area.w && thing.x + thing.w + DRAWING_OVERHANG > area.x
      && thing.y - DRAWING_OVERHANG < area.y + area.h && thing.y + thing.h + DRAWING_OVERHANG > area.y;
  }

  // The part two rectangles have in common, or null when they do not meet.
  function overlap(a, b) {
    var left = Math.max(a.x, b.x);
    var top = Math.max(a.y, b.y);
    var right = Math.min(a.x + a.w, b.x + b.w);
    var bottom = Math.min(a.y + a.h, b.y + b.h);
    if (right <= left || bottom <= top) {
      return null;
    }
    return { x: left, y: top, w: right - left, h: bottom - top };
  }

  // The smallest rectangle around a list of points.
  function boundsOf(points) {
    var xs = points.map(function (point) { return point.x; });
    var ys = points.map(function (point) { return point.y; });
    var left = Math.min.apply(null, xs);
    var top = Math.min.apply(null, ys);
    return { x: left, y: top, w: Math.max.apply(null, xs) - left, h: Math.max.apply(null, ys) - top };
  }

  // True when the point lies inside the polygon (the deck's outline): a line
  // from the point to the right crosses the outline an odd number of times.
  function insidePolygon(corners, x, y) {
    var inside = false;
    for (var i = 0, j = corners.length - 1; i < corners.length; j = i++) {
      var a = corners[i];
      var b = corners[j];
      var crosses = (a.y > y) !== (b.y > y) && x < (b.x - a.x) * (y - a.y) / (b.y - a.y) + a.x;
      if (crosses) {
        inside = !inside;
      }
    }
    return inside;
  }

  // The art files in js/world/art/ register their drawings in Game.world.art,
  // in four groups: "kinds" (solids), "decor", "floors" and "faces". A
  // drawing for one room is registered as "room-id:name" and wins over the
  // drawing for every room ("name"). Returns null when nothing is registered.
  function artFor(group, room, name) {
    var art = Game.world.art;
    if (!name || !art || !art[group]) {
      return null;
    }
    var forThisRoom = room ? art[group][room.id + ":" + name] : null;
    return forThisRoom || art[group][name] || null;
  }

  var artHasFailed = false; // warn once, not on every tile

  // Runs one drawing of an art file. If it fails, the canvas is put back as
  // it was and false is returned, so the caller can draw the plain version
  // instead: a broken art file never hides a wall or stops the map.
  function drawWithArt(ctx, drawing, thing, room, campus) {
    ctx.save();
    try {
      drawing(ctx, thing, room, campus);
      return true;
    } catch (problem) {
      if (!artHasFailed) {
        artHasFailed = true;
        console.warn("A drawing of the map failed; it is drawn plain.", problem);
      }
      return false;
    } finally {
      ctx.restore();
    }
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
  // When the map names a `deck_pattern` that an art file draws, that pattern
  // takes the place of the plain joints.
  function drawDeck(ctx, campus, area) {
    var corners = list(campus.deck);
    if (corners.length < 3) {
      return;
    }
    traceDeck(ctx, corners);
    ctx.fillStyle = campus.colours.deck;
    ctx.fill();
    ctx.save();
    ctx.clip(); // the joints are drawn across the whole map but show only on the deck
    var pattern = artFor("floors", null, campus.deck_pattern);
    var deckArea = overlap(area, boundsOf(corners));
    if (!pattern || !deckArea || !drawWithArt(ctx, pattern, deckArea, null, campus)) {
      drawPlainJoints(ctx, campus);
    }
    ctx.restore();
    // The deck's name has its own place in the map file, away from the spawn
    // point, so players who appear there do not stand on it.
    var label = campus.deck_label;
    if (label && label.name) {
      text(ctx, label.name, label.x, label.y, 13);
    }
  }

  function drawPlainJoints(ctx, campus) {
    for (var x = PAVING_TILE; x < campus.width; x += PAVING_TILE) {
      line(ctx, x, 0, x, campus.height, PAVING_LINE, 1.5);
    }
    for (var y = PAVING_TILE; y < campus.height; y += PAVING_TILE) {
      line(ctx, 0, y, campus.width, y, PAVING_LINE, 1.5);
    }
  }

  // Each room's floor colour, and on top its `pattern` (planks, tiles, ...)
  // when an art file draws one. The pattern is only drawn where the room and
  // `area` overlap, so a tile of the map does not draw the whole room.
  function drawRoomFloors(ctx, campus, area) {
    var rooms = list(campus.rooms);
    for (var i = 0; i < rooms.length; i++) {
      var room = rooms[i];
      ctx.fillStyle = room.floor;
      ctx.fillRect(room.x, room.y, room.w, room.h);
      var pattern = artFor("floors", room, room.pattern);
      var floorArea = overlap(area, room);
      if (pattern && floorArea) {
        ctx.save();
        ctx.beginPath();
        ctx.rect(room.x, room.y, room.w, room.h);
        ctx.clip();
        drawWithArt(ctx, pattern, floorArea, room, campus);
        ctx.restore();
      }
    }
  }

  // A door is an opening in the wall, shown as a strip of deck paving.
  // With the art files, a door is drawn in two parts: its "opening" (the
  // threshold in the wall) here, and its "frame" (posts and open glass
  // leaves) after the furniture, see drawDoorFrames().
  function drawDoors(ctx, campus, area) {
    var doors = list(campus.doors);
    for (var i = 0; i < doors.length; i++) {
      var door = doors[i];
      var room = roomOfDoor(campus, door);
      var opening = artFor("doors", room, "opening");
      if (!reachesDoor(door, area)) {
        continue;
      }
      if (!opening || !drawWithArt(ctx, opening, door, room, campus)) {
        ctx.fillStyle = campus.colours.deck;
        ctx.fillRect(door.x, door.y, door.w, door.h);
      }
    }
  }

  // The posts and the open glass leaves of every door, on top of the walls.
  function drawDoorFrames(ctx, campus, area) {
    var doors = list(campus.doors);
    for (var i = 0; i < doors.length; i++) {
      var door = doors[i];
      var room = roomOfDoor(campus, door);
      var frame = artFor("doors", room, "frame");
      if (frame && reachesDoor(door, area)) {
        drawWithArt(ctx, frame, door, room, campus);
      }
    }
  }

  // A door's leaves stand open beside it, so its drawing reaches this far
  // past the door's own rectangle.
  var DOOR_LEAF_REACH = 16;

  function reachesDoor(door, area) {
    var reach = DOOR_LEAF_REACH;
    return reaches({ x: door.x - reach, y: door.y - reach, w: door.w + 2 * reach, h: door.h + 2 * reach }, area);
  }

  function roomOfDoor(campus, door) {
    var rooms = list(campus.rooms);
    for (var i = 0; i < rooms.length; i++) {
      if (rooms[i].id === door.room) {
        return rooms[i];
      }
    }
    return null;
  }

  // Each room's name stands at its `label` from the map file: the middle of
  // the text, placed by hand where the sketch has it.
  // Without `area` every name is drawn; with it, only the names that reach
  // into it (a generous guess of the space a name takes).
  function drawRoomNames(ctx, campus, area) {
    var rooms = list(campus.rooms);
    for (var i = 0; i < rooms.length; i++) {
      var room = rooms[i];
      if (!room.label) {
        continue;
      }
      // A long name gets smaller letters in a narrow room.
      var size = room.name.length * 8 > room.w ? 12 : 13;
      var halfWidth = room.name.length * size * 0.4;
      var space = { x: room.label.x - halfWidth, y: room.label.y - size, w: 2 * halfWidth, h: 2 * size };
      if (!area || reaches(space, area)) {
        text(ctx, room.name, room.label.x, room.label.y, size);
      }
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

  // A tree, drawn plain when art/deck.js is missing: a light square the size
  // of its solid with a round green crown in the middle.
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
  // the server treats as solid must never be invisible. When an art file
  // (js/world/art/) draws the kind, its drawing is used instead.
  function drawSolid(ctx, solid, campus) {
    var room = roomAt(campus, solid.x + solid.w / 2, solid.y + solid.h / 2);
    var drawing = artFor("kinds", room, solid.kind);
    if (drawing && drawWithArt(ctx, drawing, solid, room, campus)) {
      return;
    }
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

  // Only the solids that reach into `area` are drawn.
  function drawSolids(ctx, campus, area) {
    var solids = list(campus.solids);
    for (var i = 0; i < solids.length; i++) {
      if (reaches(solids[i], area)) {
        drawSolid(ctx, solids[i], campus);
      }
    }
  }

  // ---- Wall faces and decor (M2-1.4) -----------------------------------

  // How far below its band a wall face may throw its shadow onto the floor.
  var FACE_SHADOW = 4;

  // The camera looks from the south, so below every wall running left to
  // right the side of that wall is seen: a band `wall_face_height` units
  // high, in the style the room (or the deck) names as `wall_face`. A face is
  // only drawn, never solid. Walls running up and down show only their top.
  function drawWallFaces(ctx, campus, area) {
    var height = campus.wall_face_height;
    if (typeof height !== "number" || height <= 0) {
      return;
    }
    var rooms = list(campus.rooms);
    for (var i = 0; i < rooms.length; i++) {
      var room = rooms[i];
      var face = artFor("faces", room, room.wall_face);
      if (face && overlap(area, room)) {
        drawFacesOf(ctx, campus, area, room, face, height, function (x, y) {
          return y > room.y && y < room.y + room.h && x > room.x && x < room.x + room.w;
        });
      }
    }
    var corners = list(campus.deck);
    var deckFace = artFor("faces", null, campus.deck_wall_face);
    if (deckFace && corners.length >= 3) {
      drawFacesOf(ctx, campus, area, null, deckFace, height, function (x, y) {
        return insidePolygon(corners, x, y);
      });
    }
  }

  // Draws the face of every wall running left to right whose lower edge lies
  // in one place (`isInside` asks about the point just below the middle of
  // the wall), clipped to that place (the room, or the deck). Only faces that
  // reach into `area` are drawn.
  function drawFacesOf(ctx, campus, area, room, face, height, isInside) {
    ctx.save();
    ctx.beginPath();
    if (room) {
      ctx.rect(room.x, room.y, room.w, room.h);
    } else {
      traceDeck(ctx, list(campus.deck));
    }
    ctx.clip();
    var solids = list(campus.solids);
    for (var i = 0; i < solids.length; i++) {
      var wall = solids[i];
      var runsLeftToRight = wall.kind === "wall" && wall.w > wall.h;
      var band = { x: wall.x, y: wall.y + wall.h, w: wall.w, h: height };
      if (runsLeftToRight && reaches(band, area) && isInside(wall.x + wall.w / 2, wall.y + wall.h + 0.5)) {
        // Only the part of a long wall that this area shows. Faces line their
        // slats and windows up on the map, not on the band, so the parts of
        // one face drawn in two tiles meet without a seam.
        var left = Math.max(band.x, area.x - DRAWING_OVERHANG);
        var right = Math.min(band.x + band.w, area.x + area.w + DRAWING_OVERHANG);
        band.x = left;
        band.w = right - left;
        // A face stays in its band, but for its shadow on the floor below.
        ctx.save();
        ctx.beginPath();
        ctx.rect(band.x, band.y, band.w, band.h + FACE_SHADOW);
        ctx.clip();
        drawWithArt(ctx, face, band, room, campus);
        ctx.restore();
      }
    }
    ctx.restore();
  }

  // Decor is only drawn: fittings the browser shows and the server ignores
  // (signs, mats, a coffee machine on a counter). Each entry has a `layer`:
  // "floor" lies flat on the floor, "wall" hangs on a wall or its face, "on"
  // stands on a solid. A kind without a drawing is left out. A drawing that
  // reaches further past its entry's rectangle than DRAWING_OVERHANG says so
  // in its `reach` (in map units), so that a tile of the map next to it
  // still draws the part that falls into it.
  function drawDecor(ctx, campus, area, layer) {
    var decor = list(campus.decor);
    for (var i = 0; i < decor.length; i++) {
      var item = decor[i];
      if (item.layer !== layer) {
        continue;
      }
      var room = roomAt(campus, item.x + item.w / 2, item.y + item.h / 2);
      var drawing = artFor("decor", room, item.kind);
      var reach = drawing && typeof drawing.reach === "number" ? drawing.reach : 0;
      var space = { x: item.x - reach, y: item.y - reach, w: item.w + 2 * reach, h: item.h + 2 * reach };
      if (drawing && reaches(space, area)) {
        drawWithArt(ctx, drawing, item, room, campus);
      }
    }
  }

  // ---- The part of the map that never changes --------------------------

  // Ground, floors, wall faces, furniture, decor and the room names: all of
  // it inside `area` (in map units). The order matters: what is drawn later
  // lies on top.
  function drawStaticLayers(ctx, campus, area) {
    drawLowerLayers(ctx, campus, area);
    drawUpperLayers(ctx, campus, area);
  }

  // The two halves of drawStaticLayers(): a tile drawn ahead is drawn one
  // half per frame, so no frame has to draw a whole tile.
  function drawLowerLayers(ctx, campus, area) {
    drawGround(ctx, campus, area);
    drawDeck(ctx, campus, area);
    drawRoomFloors(ctx, campus, area);
    drawDoors(ctx, campus, area);
    drawDecor(ctx, campus, area, "floor");
    drawWallFaces(ctx, campus, area);
  }

  function drawUpperLayers(ctx, campus, area) {
    drawRoomNames(ctx, campus, area);
    drawSolids(ctx, campus, area);
    drawDecor(ctx, campus, area, "wall");
    drawDecor(ctx, campus, area, "on");
    drawDoorFrames(ctx, campus, area);
  }

  // The map is drawn on every frame, but most of it never changes. So the
  // static part is drawn once into square tiles of TILE_PIXELS canvas pixels
  // (at the current zoom), and each frame only copies the tiles it needs.
  // Tiles sit on whole canvas pixels, so no seam shows between two of them.
  // In a frame that needed no new tile, a tile of the ring just outside the
  // picture is drawn ahead: the one nearest to where the camera is heading,
  // half of it in one frame and the other half in the next. So walking on
  // seldom has to draw a tile while the player waits, and no frame draws
  // more than half a tile ahead.
  var TILE_PIXELS = 512;
  // How much memory the canvases of the tiles may take, kept and spare
  // together: 64 tiles of 512 x 512 pixels at 4 bytes are 64 MiB. Some
  // browsers (Safari on iOS) refuse canvases beyond a total limit. Only a
  // very large canvas, whose picture and ring need more tiles, goes beyond.
  var TILE_BYTES = TILE_PIXELS * TILE_PIXELS * 4;
  var TILE_MEMORY_BUDGET = 64 * 1024 * 1024;
  var MOST_TILES = Math.floor(TILE_MEMORY_BUDGET / TILE_BYTES);
  // Of those, this many are spare canvases of forgotten tiles, ready to be
  // drawn into: making a new canvas costs more than drawing into an old one.
  var SPARE_TILES = 8;

  var tiles = {
    campus: null, // the map and the zoom the tiles were drawn for
    scale: 0,
    kept: new Map(), // "column,row" -> canvas; the most recently used last
    spare: [], // canvases of forgotten tiles, to draw new tiles into
    work: 0, // how many halves of tiles were drawn so far
    pending: null, // a tile drawn ahead whose upper half is still missing
    lastOrigin: null, // where the map's corner was on the canvas last frame
    heading: { x: 0, y: 0 }, // the way the camera moved last, in canvas pixels
    unavailable: false // true when this browser cannot make tiles
  };

  function drawStaticPart(ctx, campus, view) {
    if (!tiles.unavailable && canUseTiles(ctx)) {
      ctx.save();
      try {
        drawFromTiles(ctx, campus);
        return;
      } catch (problem) {
        tiles.unavailable = true;
        console.warn("The map is drawn without tiles.", problem);
      } finally {
        ctx.restore();
      }
    }
    // Without a page (tests in Node) or without tiles: draw it directly.
    drawStaticLayers(ctx, campus, view);
  }

  // Tiles need a page that can make canvases and a camera that only scales
  // and moves (no turning, the same scale both ways).
  function canUseTiles(ctx) {
    if (typeof document === "undefined" || typeof document.createElement !== "function") {
      return false;
    }
    if (typeof ctx.getTransform !== "function" || typeof ctx.drawImage !== "function") {
      return false;
    }
    if (!ctx.canvas || typeof ctx.canvas.width !== "number" || typeof ctx.canvas.height !== "number") {
      return false;
    }
    var camera = ctx.getTransform();
    var isPlainNumber = function (value) { return typeof value === "number" && isFinite(value); };
    var allNumbers = camera && [camera.a, camera.b, camera.c, camera.d, camera.e, camera.f].every(isPlainNumber);
    return Boolean(allNumbers) && camera.b === 0 && camera.c === 0 && camera.a === camera.d && camera.a > 0;
  }

  // Copies the tiles that cover the canvas. Tile (column, row) holds the map
  // from column * TILE_PIXELS to (column + 1) * TILE_PIXELS canvas pixels,
  // counted from the map's corner (0, 0) at this zoom.
  function drawFromTiles(ctx, campus) {
    var camera = ctx.getTransform();
    var scale = camera.a;
    if (tiles.campus !== campus || tiles.scale !== scale) {
      startAgain(campus, scale);
    }
    // Where the map's corner lands on the canvas, rounded to a whole pixel.
    var originX = Math.round(camera.e);
    var originY = Math.round(camera.f);
    noteHeading(originX, originY);
    var firstColumn = Math.floor(-originX / TILE_PIXELS);
    var lastColumn = Math.floor((ctx.canvas.width - originX - 1) / TILE_PIXELS);
    var firstRow = Math.floor(-originY / TILE_PIXELS);
    var lastRow = Math.floor((ctx.canvas.height - originY - 1) / TILE_PIXELS);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    var workBefore = tiles.work;
    for (var row = firstRow; row <= lastRow; row++) {
      for (var column = firstColumn; column <= lastColumn; column++) {
        var tile = tileAt(campus, scale, column, row);
        ctx.drawImage(tile, originX + column * TILE_PIXELS, originY + row * TILE_PIXELS);
      }
    }
    if (tiles.work === workBefore && tiles.pending) {
      var finished = tiles.pending;
      tiles.kept.set(finished.key, finishTile(campus, finished));
    } else if (tiles.work === workBefore) {
      drawOneTileAhead(campus, scale, ctx.canvas, originX, originY, firstColumn - 1, lastColumn + 1, firstRow - 1, lastRow + 1);
    }
    // Keep the tiles of the picture and of the ring around it, and as many
    // again of those seen last, as far as the memory budget allows.
    var ring = (lastColumn - firstColumn + 3) * (lastRow - firstRow + 3);
    forgetOldTiles(Math.max(ring, Math.min(ring * 2, MOST_TILES - SPARE_TILES)));
  }

  // A new map or a new zoom: every tile is out of date. Their canvases are
  // all the same size, so they become spares for the new tiles (within the
  // budget) instead of being made again. The heading is forgotten too: the
  // corner of the map moves on the canvas when the zoom changes.
  function startAgain(campus, scale) {
    var canvases = tiles.spare.slice();
    tiles.kept.forEach(function (canvas) { canvases.push(canvas); });
    if (tiles.pending) {
      canvases.push(tiles.pending.canvas);
    }
    tiles.spare = canvases.slice(0, MOST_TILES);
    // (More spares than SPARE_TILES are fine here: the new tiles use them up.)
    tiles.kept.clear();
    tiles.pending = null;
    tiles.lastOrigin = null;
    tiles.campus = campus;
    tiles.scale = scale;
  }

  // Remembers which way the camera moves. When the map's corner moves left
  // on the canvas, the camera moves right. Standing still keeps the heading.
  function noteHeading(originX, originY) {
    var last = tiles.lastOrigin;
    if (last && (last.x !== originX || last.y !== originY)) {
      tiles.heading = { x: last.x - originX, y: last.y - originY };
    }
    tiles.lastOrigin = { x: originX, y: originY };
  }

  // Draws the missing tile of the ring around the picture that lies nearest
  // to a point one tile ahead of the picture's middle, in the heading.
  function drawOneTileAhead(campus, scale, canvas, originX, originY, firstColumn, lastColumn, firstRow, lastRow) {
    var heading = tiles.heading;
    var length = Math.sqrt(heading.x * heading.x + heading.y * heading.y) || 1;
    // The aim, in canvas pixels counted from the map's corner.
    var aimX = canvas.width / 2 - originX + heading.x / length * TILE_PIXELS;
    var aimY = canvas.height / 2 - originY + heading.y / length * TILE_PIXELS;
    var best = null;
    for (var row = firstRow; row <= lastRow; row++) {
      for (var column = firstColumn; column <= lastColumn; column++) {
        var onTheRing = row === firstRow || row === lastRow || column === firstColumn || column === lastColumn;
        if (!onTheRing || tiles.kept.has(column + "," + row)) {
          continue;
        }
        var dx = (column + 0.5) * TILE_PIXELS - aimX;
        var dy = (row + 0.5) * TILE_PIXELS - aimY;
        var distance = dx * dx + dy * dy;
        if (best === null || distance < best.distance) {
          best = { column: column, row: row, distance: distance };
        }
      }
    }
    if (best) {
      tiles.pending = startTile(campus, scale, best.column, best.row);
    }
  }

  // The tile, from the store or drawn now.
  function tileAt(campus, scale, column, row) {
    var key = column + "," + row;
    var tile = tiles.kept.get(key);
    if (tile) {
      tiles.kept.delete(key); // put it back at the end: used most recently
    } else if (tiles.pending && tiles.pending.key === key) {
      tile = finishTile(campus, tiles.pending); // half drawn ahead: finish it now
    } else {
      tile = finishTile(campus, startTile(campus, scale, column, row));
    }
    tiles.kept.set(key, tile);
    return tile;
  }

  // Starts a tile: makes (or reuses) its canvas and draws the lower half of
  // the layers. Returns what finishTile() needs.
  function startTile(campus, scale, column, row) {
    tiles.work += 1;
    // A canvas of a forgotten tile is used again: making a new one costs more
    // than drawing into an old one. The lawn drawn first covers it all.
    var tile = tiles.spare.pop();
    if (!tile) {
      tile = document.createElement("canvas");
      tile.width = TILE_PIXELS;
      tile.height = TILE_PIXELS;
    }
    var tileCtx = typeof tile.getContext === "function" ? tile.getContext("2d") : null;
    if (!tileCtx) {
      throw new Error("A canvas for a tile of the map could not be made.");
    }
    tileCtx.setTransform(scale, 0, 0, scale, -column * TILE_PIXELS, -row * TILE_PIXELS);
    tileCtx.lineJoin = "round";
    var size = TILE_PIXELS / scale;
    var area = { x: column * size, y: row * size, w: size, h: size };
    drawLowerLayers(tileCtx, campus, area);
    return { key: column + "," + row, canvas: tile, ctx: tileCtx, area: area };
  }

  // Draws the upper half of the layers of a started tile. Returns its canvas.
  function finishTile(campus, started) {
    tiles.work += 1;
    if (tiles.pending === started) {
      tiles.pending = null;
    }
    drawUpperLayers(started.ctx, campus, started.area);
    return started.canvas;
  }

  // Keeps only the `count` tiles used most recently, so walking across the
  // whole map does not fill the memory. A forgotten tile's canvas becomes a
  // spare, up to SPARE_TILES of them; spares beyond that (left over from a
  // new zoom) are let go once the kept tiles and spares exceed the budget.
  function forgetOldTiles(count) {
    while (tiles.kept.size > count) {
      var oldest = tiles.kept.keys().next().value;
      if (tiles.spare.length < SPARE_TILES) {
        tiles.spare.push(tiles.kept.get(oldest));
      }
      tiles.kept.delete(oldest);
    }
    var budget = Math.max(MOST_TILES, count + SPARE_TILES);
    while (tiles.spare.length > SPARE_TILES && tiles.kept.size + tiles.spare.length > budget) {
      tiles.spare.pop();
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
  function drawButton(ctx, campus, visible) {
    if (visible && campus.button) {
      circle(ctx, campus.button.x, campus.button.y, campus.button.r, CORAL, 2.5);
    }
  }

  // ---- Task stations (Felix, 2026-11-21) -------------------------------

  // Every station shows its object from art/stations.js and a small tag
  // with its number (M2-1.10), always: in the lobby, in a round and after
  // the last task. The stations that matter to the player now get a thick
  // yellow outline with a dark edge around the object's own shape, which
  // pulses. Objects are drawings only: they are not solid.

  // How long one pulse of the outline takes, in milliseconds
  // (DESIGN.md, section 4: "pulses slowly").
  var PULSE_MILLISECONDS = 1400;
  // How far the outline reaches beyond the object, in map units: the dark
  // edge and the yellow inside it, when the pulse is low and when it is high.
  // These are the widths the outline has had on screen so far: it was grown
  // by 2.6, 1.6, 4.2 and 3.1, and its soft edge added about a fifth. Since
  // its edge is made hard (see hardenEdge), it grows by all of it (M2-1.20).
  var OUTLINE_GROWTH = { low: { dark: 3.1, yellow: 1.9 }, high: { dark: 5, yellow: 3.7 } };
  // Half the size of the square an object (and its outline) is drawn into.
  var OBJECT_HALF_SIZE = 20;
  // How the outline grows (see grownBy): in passes of at most this many map
  // units, each in GROW_DIRECTIONS directions, the last pass of a layer in
  // LAST_PASS_DIRECTIONS (rounder). Counted in map units, the four layers of
  // a station need the same five passes at every zoom (2, 1, 1 and 1).
  var GROW_PASS_UNITS = 1.5;
  var GROW_DIRECTIONS = 16;
  var LAST_PASS_DIRECTIONS = 32;

  function stationObject(station) {
    var art = Game.world.art;
    var drawings = art && art.stations;
    return drawings && typeof drawings[station.id] === "function" ? drawings[station.id] : null;
  }

  // Swings between 0 and 1 and back, once per pulse.
  function pulseAt(now) {
    return 0.5 - 0.5 * Math.cos((Number(now) || 0) / PULSE_MILLISECONDS * Math.PI * 2);
  }

  // The soft shadow below an object is the furniture's shadow
  // (shadowBelow in art/common.js): a strip `w` wide whose top left corner
  // lies at (x, y), from the station's centre in map units. Without a place
  // of its own a drawing gets this one.
  var DEFAULT_SHADOW = { x: -9, y: 10, w: 18 };
  // How deep each of the shadow's two bands is: as below small furniture.
  var SHADOW_DEPTH = 1.2;

  // The middle of the number tag, from the station's centre in map units,
  // for a drawing without a place of its own.
  var DEFAULT_TAG = { x: 11, y: 9 };
  // The tag (the lead, 2026-11-22: smaller than before, 4.2 with a ring of 1).
  var TAG_RADIUS = 3.5;
  var TAG_RING = 0.7;
  var TAG_FONT = 4.2;

  function isNumber(value) {
    return typeof value === "number" && isFinite(value);
  }

  // The shadow of a drawing from art/stations.js (M2-1.20). A drawing may
  // say where its shadow lies with `drawing.shadow = {x, y, w}`, or that it
  // has none with `drawing.shadow = null`, so that the shadow stays off the
  // furniture next to it. Without it (or with anything else) the shadow
  // lies at DEFAULT_SHADOW.
  function shadowOf(drawObject) {
    if (!("shadow" in drawObject)) {
      return DEFAULT_SHADOW;
    }
    var shadow = drawObject.shadow;
    if (shadow === null) {
      return null;
    }
    var isStrip = typeof shadow === "object"
      && isNumber(shadow.x) && isNumber(shadow.y) && isNumber(shadow.w) && shadow.w > 0;
    return isStrip ? shadow : DEFAULT_SHADOW;
  }

  // Where the number tag of a drawing lies (M2-1.20): a drawing may give the
  // tag's middle with `drawing.tag = {x, y}`, so that the tag sits at the
  // lower right of a small object. Anything else gives DEFAULT_TAG: the
  // number is always shown.
  function tagOf(drawObject) {
    var tag = drawObject.tag;
    var isPlace = tag !== null && typeof tag === "object" && isNumber(tag.x) && isNumber(tag.y);
    return isPlace ? tag : DEFAULT_TAG;
  }

  // The object of a station, its soft shadow and its number tag.
  function drawStationObject(ctx, station, drawObject) {
    ctx.save();
    ctx.translate(station.x, station.y);
    var shadow = shadowOf(drawObject);
    var util = Game.world.art.util; // from art/common.js, which art/stations.js needs too
    if (shadow && util) {
      util.shadowBelow(ctx, shadow.x, shadow.y, shadow.w, SHADOW_DEPTH);
    }
    drawObject(ctx);
    ctx.restore();
    var tag = tagOf(drawObject);
    drawNumberTag(ctx, station, station.x + tag.x, station.y + tag.y);
  }

  // The station's number in a small cream tag at (x, y) on the map.
  function drawNumberTag(ctx, station, x, y) {
    circle(ctx, x, y, TAG_RADIUS, CREAM, TAG_RING);
    text(ctx, String(station.id), x, y + 0.25, TAG_FONT);
  }

  // ---- The outline: the object's shape, grown a little -----------------

  // Silhouettes already made: "station id/pixels per unit/growth/colour" -> canvas.
  var silhouettes = new Map();
  // The zoom the kept silhouettes were made for. Only one zoom is kept: a
  // window being resized passes many, and each would hold its own canvases.
  var silhouetteScale = null;

  function newCanvas(size) {
    if (typeof document === "undefined" || typeof document.createElement !== "function") {
      return null; // no page (a test in Node): no outline, the object stays
    }
    var made = document.createElement("canvas");
    made.width = size;
    made.height = size;
    return made;
  }

  // The four layers of an outline, from the narrowest to the widest.
  var OUTLINE_LAYERS = [
    { growth: OUTLINE_GROWTH.low.yellow, colour: YELLOW },
    { growth: OUTLINE_GROWTH.low.dark, colour: OUTLINE },
    { growth: OUTLINE_GROWTH.high.yellow, colour: YELLOW },
    { growth: OUTLINE_GROWTH.high.dark, colour: OUTLINE }
  ];

  function silhouetteKey(station, scale, growth, colour) {
    return station.id + "/" + scale + "/" + growth + "/" + colour;
  }

  // The object drawn in one colour and grown by `growth` map units, as a
  // canvas of the square around the station, at `scale` pixels per unit.
  // The four layers of a station are made together, once, and kept:
  // drawing them again each frame is cheap.
  function silhouette(station, drawObject, scale, growth, colour) {
    if (scale !== silhouetteScale) {
      silhouettes.clear();
      silhouetteScale = scale;
    }
    var key = silhouetteKey(station, scale, growth, colour);
    if (!silhouettes.has(key)) {
      makeSilhouettes(station, drawObject, scale);
    }
    return silhouettes.get(key) || null;
  }

  // Makes the four layers of a station's outline. Each layer grows from
  // the one before it (only the shape counts, not its colour), so the widest
  // needs only what the narrower one lacks: five short passes in all.
  function makeSilhouettes(station, drawObject, scale) {
    var size = Math.ceil(OBJECT_HALF_SIZE * 2 * scale);
    var shape = newCanvas(size);
    if (!shape) {
      return;
    }
    var shapeCtx = shape.getContext("2d");
    shapeCtx.setTransform(scale, 0, 0, scale, size / 2, size / 2);
    drawObject(shapeCtx);
    var source = shape;
    var grownSoFar = 0;
    for (var i = 0; i < OUTLINE_LAYERS.length; i++) {
      var layer = OUTLINE_LAYERS[i];
      // The reach in whole pixels, so the edge lies as far out at every zoom.
      var pixels = reachInPixels(layer.growth, scale) - reachInPixels(grownSoFar, scale);
      var grown = grownBy(source, pixels, growPasses(layer.growth - grownSoFar), size);
      // The next layer grows from the hard edge: a soft one would spread.
      var shown = grown && softened(grown, size);
      if (!shown) {
        return;
      }
      var shownCtx = shown.getContext("2d");
      shownCtx.globalCompositeOperation = "source-in";
      shownCtx.fillStyle = layer.colour;
      shownCtx.fillRect(0, 0, size, size);
      silhouettes.set(silhouetteKey(station, scale, layer.growth, layer.colour), shown);
      source = grown;
      grownSoFar = layer.growth;
    }
  }

  // The shape on the canvas `source` grown by `pixels`, in `passes` passes,
  // on a new canvas. Each pass draws the shape of the last pass in many
  // directions, at most GROW_PASS_UNITS away. Neighbouring copies then lie
  // at most about 0.6 units apart (0.3 in the last pass), less than a thin
  // leg or handle is wide (0.7 units), so its tip grows round; one wide pass
  // left a fringe of stripes there (M2-1.20). Two canvases take turns, so a pass
  // never draws onto the shape it reads.
  function grownBy(source, pixels, passes, size) {
    var canvases = [newCanvas(size), newCanvas(size)];
    if (!canvases[0] || !canvases[1]) {
      return null;
    }
    var current = source;
    for (var pass = 0; pass < passes; pass++) {
      // Whole pixels per pass that add up to `pixels`.
      var step = Math.round((pass + 1) * pixels / passes) - Math.round(pass * pixels / passes);
      var directions = pass === passes - 1 ? LAST_PASS_DIRECTIONS : GROW_DIRECTIONS;
      var next = canvases[pass % 2];
      var nextCtx = next.getContext("2d");
      nextCtx.clearRect(0, 0, size, size);
      nextCtx.drawImage(current, 0, 0);
      for (var direction = 0; direction < directions; direction++) {
        var angle = direction / directions * Math.PI * 2;
        // On whole pixels: a copy between pixels is blurred, and the blur
        // of many copies would push the edge out further at a low zoom.
        nextCtx.drawImage(current, Math.round(Math.cos(angle) * step), Math.round(Math.sin(angle) * step));
      }
      current = next;
    }
    hardenEdge(current, size);
    return current;
  }

  // The hard-edged shape on `source` drawn again on a new canvas, a little
  // soft (as much as a line drawn by the canvas), so that it does not look
  // stepped: four copies, half a pixel apart, each a quarter of it, added
  // up. The edge stays where it was.
  function softened(source, size) {
    var target = newCanvas(size);
    if (!target) {
      return null;
    }
    var ctx = target.getContext("2d");
    ctx.clearRect(0, 0, size, size);
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = 0.25;
    ctx.drawImage(source, -0.5, -0.5);
    ctx.drawImage(source, 0.5, -0.5);
    ctx.drawImage(source, -0.5, 0.5);
    ctx.drawImage(source, 0.5, 0.5);
    ctx.restore();
    return target;
  }

  // Makes the soft edge of a grown shape hard: a pixel at least three
  // quarters covered becomes solid, one at most a quarter covered empty, and
  // one half covered stays half (a narrow soft step). The edge then lies
  // where the shape really ends, at every zoom and after any number of
  // passes; the copies of a pass add up their soft edges and would push it
  // out.
  function hardenEdge(canvas, size) {
    var ctx = canvas.getContext("2d");
    var image = typeof ctx.getImageData === "function" ? ctx.getImageData(0, 0, size, size) : null;
    if (!image || !image.data) {
      return; // a canvas stand-in (a test in Node)
    }
    var pixels = image.data;
    for (var i = 3; i < pixels.length; i += 4) {
      pixels[i] = Math.max(0, Math.min(255, (pixels[i] - 64) * 2));
    }
    ctx.putImageData(image, 0, 0);
  }

  // How far a layer that reaches `growth` map units past the object is
  // grown, in whole pixels: one pixel less, because softening its edge (see
  // softened) makes it reach about one pixel further on screen.
  function reachInPixels(growth, scale) {
    return growth > 0 ? Math.max(0, Math.round(growth * scale) - 1) : 0;
  }

  // How many passes the outline grows `growth` map units in: the same at
  // every zoom.
  function growPasses(growth) {
    return Math.max(1, Math.ceil(growth / GROW_PASS_UNITS));
  }

  // Pixels per map unit of the drawing now, rounded so that zooming a
  // little does not make new silhouettes every frame.
  function pixelsPerUnit(ctx) {
    var matrix = typeof ctx.getTransform === "function" ? ctx.getTransform() : null;
    var scale = matrix ? Math.hypot(matrix.a, matrix.b) : 1;
    return Math.max(0.5, Math.round(scale * 4) / 4);
  }

  function drawSilhouette(ctx, station, drawObject, growth, colour, alpha) {
    var scale = pixelsPerUnit(ctx);
    var shape = silhouette(station, drawObject, scale, growth, colour);
    if (!shape || alpha <= 0) {
      return;
    }
    ctx.save();
    ctx.globalAlpha = alpha;
    var half = OBJECT_HALF_SIZE;
    ctx.drawImage(shape, station.x - half, station.y - half, half * 2, half * 2);
    ctx.restore();
  }

  // The outline of one station: `strength` from 0 (pulse low) to 1 (high).
  // The wide outline fades in over the narrow one, so the yellow seems to
  // grow and shrink.
  function drawOutline(ctx, station, drawObject, strength) {
    drawSilhouette(ctx, station, drawObject, OUTLINE_GROWTH.high.dark, OUTLINE, strength);
    drawSilhouette(ctx, station, drawObject, OUTLINE_GROWTH.low.dark, OUTLINE, 1);
    drawSilhouette(ctx, station, drawObject, OUTLINE_GROWTH.high.yellow, YELLOW, strength);
    drawSilhouette(ctx, station, drawObject, OUTLINE_GROWTH.low.yellow, YELLOW, 1);
  }

  // Every station's object; the ones in `pulsing` (a list of ids; anything
  // else means none) with the pulsing outline. `now` is the frame's time.
  function drawStations(ctx, campus, pulsing, now) {
    var stations = list(campus.stations);
    var strength = pulseAt(now);
    for (var i = 0; i < stations.length; i++) {
      var station = stations[i];
      var drawObject = stationObject(station);
      if (!drawObject) {
        continue; // station 6, or the art file did not load
      }
      if (list(pulsing).indexOf(station.id) !== -1) {
        drawOutline(ctx, station, drawObject, strength);
      }
      drawStationObject(ctx, station, drawObject);
    }
  }

  // The station the player can use right now ("E Use"): its outline at
  // full strength, without pulsing, and the object again on top of it.
  function drawStationGlow(ctx, station) {
    var drawObject = ctx && station ? stationObject(station) : null;
    if (!drawObject) {
      return;
    }
    ctx.save();
    ctx.lineJoin = "round";
    drawOutline(ctx, station, drawObject, 1);
    drawStationObject(ctx, station, drawObject);
    ctx.restore();
  }

  // ---- The whole map ---------------------------------------------------

  // Draws the map in map units. `view` ({x, y, w, h}, optional) is the part
  // of the world that is visible; without it the whole map is assumed.
  // `pulsingStations` is the list of station ids whose outline pulses and
  // `now` the time of the frame (see drawStations).
  // The order matters: what is drawn later lies on top.
  function drawMap(ctx, campus, view, emergencyVisible, pulsingStations, now) {
    if (!ctx || !campus || !campus.colours) {
      return;
    }
    view = view || { x: 0, y: 0, w: campus.width, h: campus.height };
    ctx.save();
    ctx.lineJoin = "round";
    drawStaticPart(ctx, campus, view);
    drawHidingSpots(ctx, campus);
    drawButton(ctx, campus, emergencyVisible === true);
    drawStations(ctx, campus, pulsingStations, now);
    ctx.restore();
  }

  // The overview only needs scenery. Draw it directly once, without changing
  // the camera's tile cache or adding live markers such as the emergency button.
  function drawOverviewBase(ctx, campus) {
    ctx.save();
    ctx.lineJoin = "round";
    drawStaticLayers(ctx, campus, { x: 0, y: 0, w: campus.width, h: campus.height });
    ctx.restore();
  }

  // ---- Which name labels are drawn (S-117) -------------------------------

  // A label that was hidden in the previous frame comes back only when it is
  // this many map units clear of every chosen label, on every side. Without
  // this margin a label at the very edge would appear and vanish from one
  // frame to the next.
  var LABEL_COME_BACK_MARGIN = 4;

  // True when the two labels cover each other. Labels that only touch at an
  // edge do not. `margin` makes `a` that much larger on every side.
  function labelsOverlap(a, b, margin) {
    var apartSideways = Math.abs(a.x - b.x) >= (a.width + b.width) / 2 + margin;
    var apartUpAndDown = Math.abs(a.y - b.y) >= (a.height + b.height) / 2 + margin;
    return !apartSideways && !apartUpAndDown;
  }

  // The order in which the labels are decided: the own label first, then the
  // others, the character drawn later (on top) first.
  function decidingOrder(labels) {
    var onTopFirst = labels.slice().reverse();
    var own = onTopFirst.filter(function (label) { return label.own; });
    var others = onTopFirst.filter(function (label) { return !label.own; });
    return own.concat(others);
  }

  // Decides which name labels are drawn, so that no two drawn labels cover
  // each other. A label never moves: it is drawn above its own head or not at
  // all.
  //
  // `labels` is in drawing order (first drawn first). Each label is
  // {name, x, y, width, height, own}: x and y are its middle, and width and
  // height the whole space it covers on the map, outline included.
  // `hiddenBefore` is a Set of the names hidden in the previous frame; a name
  // not in it, also a player not seen before, needs no margin.
  //
  // Returns {shown: the labels to draw, hidden: a Set of the names hidden now}.
  // The own label is always shown. Every other label is shown when it is clear
  // of the labels chosen before it; one that was hidden needs the margin. The
  // margin only delays a name coming back: it never lets the label of a
  // lower character beat one drawn on top, because the lower one is decided
  // later.
  function chooseLabels(labels, hiddenBefore) {
    var wasHidden = hiddenBefore || new Set();
    var shown = [];
    var hidden = new Set();
    decidingOrder(labels || []).forEach(function (label) {
      var margin = wasHidden.has(label.name) ? LABEL_COME_BACK_MARGIN : 0;
      var covers = function (chosen) { return labelsOverlap(label, chosen, margin); };
      if (label.own || !shown.some(covers)) {
        shown.push(label);
      } else {
        hidden.add(label.name);
      }
    });
    return { shown: shown, hidden: hidden };
  }

  Game.world.drawMap = drawMap;
  Game.world.drawOverviewBase = drawOverviewBase;
  Game.world.drawStationGlow = drawStationGlow;
  Game.world.roomAt = roomAt;
  // How many outline silhouettes are kept, for tests/test_station_objects.js.
  Game.world.outlineCacheSize = function () { return silhouettes.size; };
  Game.world.chooseLabels = chooseLabels;
})();
