// The art of the campus map (M2-1.4): shared helpers, floor patterns, wall
// faces, walls and the decor every room can use.
//
// draw.js looks drawings up in Game.world.art, in four groups:
//   kinds   a solid of this kind:        fn(ctx, solid, room, campus)
//   decor   a decor entry of this kind:  fn(ctx, item, room, campus)
//   floors  a floor pattern:             fn(ctx, area, room, campus)
//           (`area` is the part of the floor to fill; room is null on the deck)
//   faces   the face of a wall:          fn(ctx, band, room, campus)
//           (`band` is the strip below the wall, `wall_face_height` high)
// A name registered as "room-id:name" is used only in that room. Places and
// sizes always come from campus.json; these files only know how a thing looks.
//
// Everything here is drawn once into tiles of the map (see draw.js), so any
// variation (a darker plank, a speckle) comes from `noise()`, which gives the
// same answer for the same place every time, never from Math.random().

"use strict";

window.Game = window.Game || {};
Game.world = Game.world || {};

(function () {
  var art = Game.world.art = Game.world.art || {};
  art.kinds = art.kinds || {};
  art.decor = art.decor || {};
  art.floors = art.floors || {};
  art.faces = art.faces || {};
  art.doors = art.doors || {};

  var OUTLINE = "#2E2A3B";
  var FONT = "system-ui, sans-serif";

  // ---- Colours ---------------------------------------------------------

  function toNumbers(colour) {
    var value = parseInt(colour.slice(1), 16);
    return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
  }

  function toHex(numbers) {
    return "#" + numbers.map(function (part) {
      var hex = Math.round(Math.max(0, Math.min(255, part))).toString(16);
      return hex.length === 1 ? "0" + hex : hex;
    }).join("");
  }

  // A colour `amount` (0 to 1) of the way from colour `from` to colour `to`.
  function mix(from, to, amount) {
    var a = toNumbers(from);
    var b = toNumbers(to);
    return toHex([0, 1, 2].map(function (i) { return a[i] + (b[i] - a[i]) * amount; }));
  }

  function lighter(colour, amount) {
    return mix(colour, "#FFFFFF", amount);
  }

  // Darker towards the outline colour, so shadows match the rest of the game.
  function darker(colour, amount) {
    return mix(colour, OUTLINE, amount);
  }

  // A number from 0 to 1 that depends only on the two numbers given: the
  // same place always gets the same "random" look, also in another tile.
  function noise(x, y) {
    var n = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453;
    return n - Math.floor(n);
  }

  // One of the colours of a list, chosen by `noise`.
  function pick(colours, x, y) {
    return colours[Math.floor(noise(x, y) * colours.length) % colours.length];
  }

  // ---- Shapes ----------------------------------------------------------

  function paint(ctx, fill, lineWidth, lineColour) {
    if (fill) {
      ctx.fillStyle = fill;
      ctx.fill();
    }
    if (lineWidth) {
      ctx.strokeStyle = lineColour || OUTLINE;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    }
  }

  function roundedPath(ctx, x, y, w, h, radius) {
    var r = Math.max(0, Math.min(radius, w / 2, h / 2));
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function box(ctx, x, y, w, h, radius, fill, lineWidth, lineColour) {
    roundedPath(ctx, x, y, w, h, radius);
    paint(ctx, fill, lineWidth, lineColour);
  }

  function circle(ctx, x, y, radius, fill, lineWidth, lineColour) {
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    paint(ctx, fill, lineWidth, lineColour);
  }

  function ellipse(ctx, x, y, radiusX, radiusY, fill, lineWidth) {
    ctx.beginPath();
    ctx.ellipse(x, y, radiusX, radiusY, 0, 0, Math.PI * 2);
    paint(ctx, fill, lineWidth);
  }

  function line(ctx, x1, y1, x2, y2, colour, lineWidth) {
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.strokeStyle = colour;
    ctx.lineWidth = lineWidth;
    ctx.stroke();
  }

  // Many lines in one colour, stroked at once: much quicker than one stroke
  // per line. `addLines(ctx)` adds them with moveTo/lineTo or rect.
  function strokeAll(ctx, colour, lineWidth, addLines) {
    ctx.beginPath();
    addLines(ctx);
    ctx.strokeStyle = colour;
    ctx.lineWidth = lineWidth;
    ctx.stroke();
  }

  // Bold text with its middle at (x, y), made smaller when it would be wider
  // than `maxWidth`.
  function text(ctx, words, x, y, size, colour, maxWidth) {
    ctx.font = "bold " + size + "px " + FONT;
    if (maxWidth && typeof ctx.measureText === "function") {
      var width = ctx.measureText(words).width;
      if (typeof width === "number" && width > maxWidth) {
        size = size * maxWidth / width;
        ctx.font = "bold " + size + "px " + FONT;
      }
    }
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = colour || OUTLINE;
    ctx.fillText(words, x, y);
  }

  // How far a pattern's shape may reach out of its own cell (a joint line,
  // a diamond centred on a corner). Cells this close to the area are drawn
  // too, so a tile of the map never cuts a shape in half.
  var CELL_OVERHANG = 4;

  // Calls `visit(x, y, column, row)` for every cell of a grid of `width` by
  // `height` that reaches into `area`. The grid starts at (startX, startY),
  // so the cells stay in the same place whatever part of the map is drawn.
  function eachCell(area, startX, startY, width, height, visit) {
    var firstColumn = Math.floor((area.x - CELL_OVERHANG - startX) / width);
    var lastColumn = Math.floor((area.x + area.w + CELL_OVERHANG - startX) / width);
    var firstRow = Math.floor((area.y - CELL_OVERHANG - startY) / height);
    var lastRow = Math.floor((area.y + area.h + CELL_OVERHANG - startY) / height);
    for (var row = firstRow; row <= lastRow; row++) {
      for (var column = firstColumn; column <= lastColumn; column++) {
        visit(startX + column * width, startY + row * height, column, row);
      }
    }
  }

  // The soft shadow a thing standing up throws onto the floor below it
  // (the light comes from the top of the picture).
  function shadowBelow(ctx, x, y, w, depth) {
    ctx.fillStyle = "rgba(46, 42, 59, 0.10)";
    ctx.fillRect(x, y, w, depth);
    ctx.fillStyle = "rgba(46, 42, 59, 0.06)";
    ctx.fillRect(x, y + depth, w, depth);
  }

  // A small chair seen from above: the seat and, on the side `back`
  // ("up", "down", "left" or "right"), the backrest.
  function chair(ctx, x, y, size, colour, back) {
    var half = size / 2;
    box(ctx, x - half, y - half, size, size, size * 0.3, colour, 0.6);
    var thick = size * 0.3;
    var rest = {
      up: [x - half, y - half, size, thick],
      down: [x - half, y + half - thick, size, thick],
      left: [x - half, y - half, thick, size],
      right: [x + half - thick, y - half, thick, size]
    }[back];
    if (rest) {
      box(ctx, rest[0], rest[1], rest[2], rest[3], thick * 0.4, darker(colour, 0.35), 0);
    }
  }

  art.util = {
    OUTLINE: OUTLINE,
    mix: mix,
    lighter: lighter,
    darker: darker,
    noise: noise,
    pick: pick,
    roundedPath: roundedPath,
    box: box,
    circle: circle,
    ellipse: ellipse,
    line: line,
    strokeAll: strokeAll,
    text: text,
    eachCell: eachCell,
    shadowBelow: shadowBelow,
    chair: chair
  };

  // ---- Walls: a dark top with a lighter edge ---------------------------

  art.kinds.wall = function (ctx, wall) {
    ctx.fillStyle = OUTLINE;
    ctx.fillRect(wall.x, wall.y, wall.w, wall.h);
    // The lighter edge round the top of the wall shows its thickness.
    ctx.strokeStyle = "#5B5570";
    ctx.lineWidth = 0.8;
    ctx.strokeRect(wall.x + 1.1, wall.y + 1.1, wall.w - 2.2, wall.h - 2.2);
  };

  // ---- Floor patterns --------------------------------------------------
  // Low contrast on purpose: stations, players and names must stand out.
  //
  // Each floor repeats a square of `period` map units. That square is drawn
  // once per zoom into a small canvas, and the floor is covered with copies
  // of it, placed on whole canvas pixels: a few quick copies instead of
  // hundreds of small shapes per tile of the map. The copies start at the
  // map's corner (0, 0), so they line up from one tile of the map to the
  // next. Variation inside the square comes from noise() of the cell's place
  // in the square, so the square fits onto its neighbours.
  //
  // (A canvas pattern, ctx.createPattern, does the same; it was tried and
  // is slower here, because it resamples every pixel it fills.)

  var SQUARES_KEPT = 24;
  var squares = new Map(); // "name|colour|zoom" -> canvas

  // Fills `area` with copies of the square drawn by `drawPeriod(ctx)`, which
  // draws from (0, 0) to (period, period) in map units. Without a page that
  // can make canvases (tests in Node), the square is drawn again and again
  // over the area instead: the same picture, only slower.
  function repeating(ctx, area, key, period, drawPeriod) {
    var camera = typeof ctx.getTransform === "function" ? ctx.getTransform() : null;
    var square = camera ? squareFor(key, period, camera.a, drawPeriod) : null;
    if (square && camera.b === 0 && camera.c === 0 && camera.a === camera.d) {
      copySquares(ctx, area, square, camera);
      return;
    }
    eachCell(area, 0, 0, period, period, function (x, y) {
      ctx.save();
      ctx.translate(x, y);
      drawPeriod(ctx);
      ctx.restore();
    });
  }

  // Copies the square over `area`, in canvas pixels. The clip that is set
  // (the room) still holds.
  function copySquares(ctx, area, square, camera) {
    var size = square.width;
    var originX = Math.round(camera.e);
    var originY = Math.round(camera.f);
    var first = { x: Math.floor((area.x * camera.a + camera.e - originX) / size), y: Math.floor((area.y * camera.a + camera.f - originY) / size) };
    var last = { x: Math.floor(((area.x + area.w) * camera.a + camera.e - originX) / size), y: Math.floor(((area.y + area.h) * camera.a + camera.f - originY) / size) };
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    for (var row = first.y; row <= last.y; row++) {
      for (var column = first.x; column <= last.x; column++) {
        ctx.drawImage(square, originX + column * size, originY + row * size);
      }
    }
    ctx.restore();
  }

  // The square for this pattern at this zoom, drawn once, or null.
  function squareFor(key, period, scale, drawPeriod) {
    if (typeof document === "undefined" || typeof document.createElement !== "function" || !(scale > 0)) {
      return null;
    }
    var fullKey = key + "|" + scale;
    if (squares.has(fullKey)) {
      return squares.get(fullKey);
    }
    var pixels = Math.max(1, Math.round(period * scale));
    var square = document.createElement("canvas");
    var squareCtx = square && typeof square.getContext === "function" ? square.getContext("2d") : null;
    if (!squareCtx) {
      return null;
    }
    square.width = pixels;
    square.height = pixels;
    var pixelsPerUnit = pixels / period;
    // Drawn nine times, shifted by a whole square each way: whatever sticks
    // out of one side of the square comes back in on the other side.
    for (var dx = -1; dx <= 1; dx++) {
      for (var dy = -1; dy <= 1; dy++) {
        squareCtx.setTransform(pixelsPerUnit, 0, 0, pixelsPerUnit, dx * pixels, dy * pixels);
        squareCtx.lineJoin = "round";
        drawPeriod(squareCtx);
      }
    }
    if (squares.size >= SQUARES_KEPT) {
      squares.delete(squares.keys().next().value);
    }
    squares.set(fullKey, square);
    return square;
  }

  // Calls `visit(x, y, column, row)` for each of `count` by `count` cells
  // of `size` inside one square of a pattern.
  function eachCellOfSquare(count, size, visit) {
    for (var row = 0; row < count; row++) {
      for (var column = 0; column < count; column++) {
        visit(column * size, row * size, column, row);
      }
    }
  }

  // Small dots, at most one in every cell, inside one square of a pattern.
  function speckles(ctx, period, colour, cell, share) {
    ctx.fillStyle = colour;
    eachCellOfSquare(Math.round(period / cell), cell, function (x, y, column, row) {
      if (noise(column * 3.1, row * 1.7) < share) {
        ctx.fillRect(x + noise(column, row * 2.3) * cell, y + noise(column * 1.9, row) * cell, 0.7, 0.7);
      }
    });
  }

  // The joints of a grid of square cells, as one path.
  function gridJoints(ctx, period, cell, colour, lineWidth) {
    strokeAll(ctx, colour, lineWidth, function () {
      eachCellOfSquare(Math.round(period / cell), cell, function (x, y) {
        ctx.rect(x, y, cell, cell);
      });
    });
  }

  // Wooden planks running left to right, joints staggered from row to row.
  // The square is two plank lengths wide and 14 rows high (84 by 84).
  art.floors.planks = function (ctx, area, room) {
    var floor = room ? room.floor : "#EAD3AE";
    var plankHeight = 6;
    var plankLength = 42;
    var period = 2 * plankLength;
    var rows = period / plankHeight;
    repeating(ctx, area, "planks|" + floor, period, function (square) {
      var joint = darker(floor, 0.16);
      for (var row = 0; row < rows; row++) {
        var shift = Math.floor(noise(row, 7) * plankLength);
        var y = row * plankHeight;
        for (var piece = -1; piece <= 2; piece++) {
          var x = shift + piece * plankLength;
          var tone = noise((piece + 2) % 2, row);
          square.fillStyle = tone < 0.5 ? darker(floor, 0.02 + tone * 0.05) : lighter(floor, (tone - 0.5) * 0.3);
          square.fillRect(x, y, plankLength, plankHeight);
        }
        strokeAll(square, joint, 0.5, function () {
          square.moveTo(0, y);
          square.lineTo(period, y);
          for (var cut = -1; cut <= 2; cut++) {
            square.moveTo(shift + cut * plankLength, y);
            square.lineTo(shift + cut * plankLength, y + plankHeight);
          }
        });
      }
    });
  };

  // Polished concrete: big slabs with faint joints and a few speckles.
  art.floors.concrete = function (ctx, area, room) {
    var floor = room ? room.floor : "#EDEAE4";
    var slab = 30;
    var period = 90;
    repeating(ctx, area, "concrete|" + floor, period, function (square) {
      eachCellOfSquare(3, slab, function (x, y, column, row) {
        square.fillStyle = mix(floor, "#C9C6C0", 0.22 + noise(column, row) * 0.12);
        square.fillRect(x, y, slab, slab);
      });
      gridJoints(square, period, slab, mix(floor, "#B8B3AA", 0.45), 0.5);
      speckles(square, period, mix(floor, "#9C978F", 0.5), 5, 0.35);
    });
  };

  // Square tiles with light joints, every other one a little darker (the canteen).
  art.floors["mint-tiles"] = function (ctx, area, room) {
    var floor = room ? room.floor : "#D7EDDF";
    var tile = 10;
    repeating(ctx, area, "mint|" + floor, 2 * tile, function (square) {
      square.fillStyle = floor;
      square.fillRect(0, 0, 2 * tile, 2 * tile);
      square.fillStyle = darker(floor, 0.035);
      square.fillRect(0, 0, tile, tile);
      square.fillRect(tile, tile, tile, tile);
      gridJoints(square, 2 * tile, tile, lighter(floor, 0.4), 0.5);
    });
  };

  // A pale floor with fine dark and light speckles (CTT, terrazzo).
  art.floors.speckled = function (ctx, area, room) {
    var floor = room ? room.floor : "#E4DED2";
    var period = 48;
    repeating(ctx, area, "speckled|" + floor, period, function (square) {
      square.fillStyle = floor;
      square.fillRect(0, 0, period, period);
      speckles(square, period, darker(floor, 0.28), 3, 0.45);
      speckles(square, period, lighter(floor, 0.7), 4, 0.4);
    });
  };

  // Pingo Doce: small white tiles with a regular pattern of grey diamonds,
  // and a band of darker tiles along the walls.
  art.floors["diamond-tiles"] = function (ctx, area, room) {
    var floor = room ? room.floor : "#DCEFC8";
    var tile = 5;
    var period = 20; // a grey diamond on every fourth crossing of the joints
    var base = lighter(floor, 0.62);
    repeating(ctx, area, "diamonds|" + floor, period, function (square) {
      square.fillStyle = base;
      square.fillRect(0, 0, period, period);
      gridJoints(square, period, tile, darker(base, 0.07), 0.35);
      // One diamond on the corner; the copies of the square add the others.
      var half = tile / 2 + 0.6;
      square.beginPath();
      square.moveTo(0, -half);
      square.lineTo(half, 0);
      square.lineTo(0, half);
      square.lineTo(-half, 0);
      square.closePath();
      square.fillStyle = mix(base, "#8E978F", 0.38);
      square.fill();
    });
    if (room) {
      tileBorder(ctx, room, floor);
    }
  };

  // The band of tiles along the walls, inside the room. Walls are 6 units
  // thick and centred on the room's edge, so the band starts 3 units in.
  function tileBorder(ctx, room, floor) {
    var wallInside = 3;
    var band = 7;
    var outer = { x: room.x + wallInside, y: room.y + wallInside, w: room.w - 2 * wallInside, h: room.h - 2 * wallInside };
    ctx.save();
    ctx.beginPath();
    ctx.rect(outer.x, outer.y, outer.w, outer.h);
    ctx.rect(outer.x + band, outer.y + band, outer.w - 2 * band, outer.h - 2 * band);
    ctx.fillStyle = mix(floor, "#9AA897", 0.35);
    ctx.fill("evenodd");
    ctx.restore();
    var joint = mix(floor, "#7F8C7D", 0.55);
    strokeAll(ctx, joint, 0.6, function () {
      ctx.rect(outer.x + band, outer.y + band, outer.w - 2 * band, outer.h - 2 * band);
    });
    // Small square tiles in the band, as joints every few units.
    strokeAll(ctx, joint, 0.35, function () {
      for (var x = outer.x + 3.5; x < outer.x + outer.w; x += 3.5) {
        ctx.moveTo(x, outer.y);
        ctx.lineTo(x, outer.y + band);
        ctx.moveTo(x, outer.y + outer.h - band);
        ctx.lineTo(x, outer.y + outer.h);
      }
      for (var y = outer.y + 3.5; y < outer.y + outer.h; y += 3.5) {
        ctx.moveTo(outer.x, y);
        ctx.lineTo(outer.x + band, y);
        ctx.moveTo(outer.x + outer.w - band, y);
        ctx.lineTo(outer.x + outer.w, y);
      }
    });
  }

  // The Main Deck: large square stone slabs in a straight grid, each a
  // little lighter or darker than the next, with a few fine speckles.
  art.floors.paving = function (ctx, area, room, campus) {
    var deck = campus && campus.colours ? campus.colours.deck : "#F3F0E9";
    var slab = 24;
    var period = 4 * slab;
    repeating(ctx, area, "paving|" + deck, period, function (square) {
      eachCellOfSquare(4, slab, function (x, y, column, row) {
        var tone = noise(column, row);
        square.fillStyle = tone < 0.5 ? darker(deck, tone * 0.04) : lighter(deck, (tone - 0.5) * 0.45);
        square.fillRect(x, y, slab, slab);
      });
      speckles(square, period, darker(deck, 0.12), 6, 0.3);
      gridJoints(square, period, slab, "#E3DDD0", 0.8);
    });
  };

  // ---- Wall faces ------------------------------------------------------

  // Registers the drawing of a wall face. `drawFront(ctx, band)` paints the
  // face itself and is kept inside its band; every face then gets the same
  // dark line where it meets the floor, and a soft shadow on the floor.
  function addFace(name, drawFront) {
    art.faces[name] = function (ctx, band) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(band.x, band.y, band.w, band.h);
      ctx.clip();
      drawFront(ctx, band);
      ctx.restore();
      shadowBelow(ctx, band.x, band.y + band.h, band.w, 1.6);
      line(ctx, band.x, band.y + band.h, band.x + band.w, band.y + band.h, OUTLINE, 0.8);
    };
  }

  // Vertical slats of wood, every `gap` units, with dark grooves between.
  function slats(ctx, band, colour, gap) {
    ctx.fillStyle = colour;
    ctx.fillRect(band.x, band.y, band.w, band.h);
    var start = Math.floor(band.x / gap) * gap;
    var light = lighter(colour, 0.12);
    var dark = darker(colour, 0.06);
    for (var x = start; x < band.x + band.w; x += gap) {
      ctx.fillStyle = noise(x, 3) < 0.5 ? light : dark;
      ctx.fillRect(x + 0.4, band.y, gap - 0.8, band.h);
    }
    strokeAll(ctx, darker(colour, 0.35), 0.35, function () {
      for (var groove = start; groove < band.x + band.w; groove += gap) {
        ctx.moveTo(groove, band.y);
        ctx.lineTo(groove, band.y + band.h);
      }
    });
    // The wall's top casts a little shadow onto its own face.
    ctx.fillStyle = "rgba(46, 42, 59, 0.18)";
    ctx.fillRect(band.x, band.y, band.w, 1);
  }

  // Pingo Doce: warm wooden slats.
  addFace("wood-slats", function (ctx, band) {
    slats(ctx, band, "#C99662", 2.2);
  });

  // Square tiles, `size` units, with light joints.
  function tiledFace(ctx, band, colour, size, joint) {
    ctx.fillStyle = colour;
    ctx.fillRect(band.x, band.y, band.w, band.h);
    ctx.fillStyle = darker(colour, 0.05);
    eachCell(band, 0, band.y, size, size, function (x, y, column, row) {
      if (noise(column, row) < 0.3) {
        ctx.fillRect(x, y, size, size);
      }
    });
    strokeAll(ctx, joint, 0.4, function () {
      eachCell(band, 0, band.y, size, size, function (x, y) {
        ctx.rect(x, y, size, size);
      });
    });
    ctx.fillStyle = "rgba(46, 42, 59, 0.15)";
    ctx.fillRect(band.x, band.y, band.w, 1);
  }

  // Mon Café: pale grey-green square tiles.
  addFace("sage-tiles", function (ctx, band) {
    tiledFace(ctx, band, "#C9D8CC", 2.6, "#EEF3EF");
  });

  // Canteen: white tiles with a mint stripe.
  addFace("white-tiles", function (ctx, band) {
    tiledFace(ctx, band, "#F3F6F4", 2.6, "#D2DDD7");
    ctx.fillStyle = "#8FCBA8";
    ctx.fillRect(band.x, band.y + band.h * 0.55, band.w, band.h * 0.18);
  });

  // CTT: a plain white wall with a grey skirting board.
  addFace("white-wall", function (ctx, band) {
    ctx.fillStyle = "#F4F3EE";
    ctx.fillRect(band.x, band.y, band.w, band.h);
    ctx.fillStyle = "rgba(46, 42, 59, 0.15)";
    ctx.fillRect(band.x, band.y, band.w, 1);
    ctx.fillStyle = "#B9BCC4";
    ctx.fillRect(band.x, band.y + band.h - 1.6, band.w, 1.6);
  });

  // ---- Doors -----------------------------------------------------------
  // A door in campus.json is a rectangle across the wall line (10 deep for a
  // wall of 6). The doors of this map all lie in walls running left to
  // right, with the wall's face on the south side.

  var WALL_THICKNESS = 6;
  var DOOR_LEAF_WIDTH = 12;

  // The strip of the door that lies in the wall itself.
  function doorThreshold(door) {
    return { x: door.x, y: door.y + (door.h - WALL_THICKNESS) / 2, w: door.w, h: WALL_THICKNESS };
  }

  // The opening: a threshold in the floor colour of the room, between two
  // thin metal sills.
  art.doors.opening = function (ctx, door, room) {
    var sill = doorThreshold(door);
    ctx.fillStyle = room ? darker(room.floor, 0.06) : "#E6E0D4";
    ctx.fillRect(sill.x, sill.y, sill.w, sill.h);
    ctx.fillStyle = "#C3C7CF";
    ctx.fillRect(sill.x, sill.y, sill.w, 0.8);
    ctx.fillRect(sill.x, sill.y + sill.h - 0.8, sill.w, 0.8);
  };

  // Dark door posts at both ends of the opening, and the two glass leaves
  // standing open, flat against the wall's face on either side.
  art.doors.frame = function (ctx, door, room, campus) {
    var sill = doorThreshold(door);
    var faceHeight = campus && typeof campus.wall_face_height === "number" ? campus.wall_face_height : 8;
    var faceTop = sill.y + sill.h;
    [door.x - 1.5 - DOOR_LEAF_WIDTH, door.x + door.w + 1.5].forEach(function (leafX, index) {
      var leaf = { x: leafX, y: faceTop + 0.4, w: DOOR_LEAF_WIDTH, h: faceHeight - 0.9 };
      box(ctx, leaf.x, leaf.y, leaf.w, leaf.h, 0.4, "rgba(170, 216, 234, 0.7)", 0.5);
      ctx.strokeStyle = "#E4E8EE";
      ctx.lineWidth = 0.6;
      ctx.strokeRect(leaf.x + 0.6, leaf.y + 0.6, leaf.w - 1.2, leaf.h - 1.2);
      line(ctx, leaf.x + 2, leaf.y + leaf.h - 1.4, leaf.x + 4.5, leaf.y + 1.4, "rgba(255, 255, 255, 0.9)", 0.5);
      // The handle, on the edge next to the opening.
      var handleX = index === 0 ? leaf.x + leaf.w - 1.6 : leaf.x + 1.6;
      line(ctx, handleX, leaf.y + leaf.h * 0.35, handleX, leaf.y + leaf.h * 0.7, OUTLINE, 0.6);
    });
    [door.x - 1.5, door.x + door.w - 1.5].forEach(function (postX) {
      box(ctx, postX, sill.y - 1, 3, sill.h + faceHeight + 1, 0.6, "#4A4560", 0.6);
    });
  };

  // ---- Decor every room can use ----------------------------------------

  // A sign with a name, white letters on a dark (or `colour`) panel.
  art.decor.sign = function (ctx, item) {
    var colour = item.colour || OUTLINE;
    box(ctx, item.x, item.y, item.w, item.h, 0.8, colour, 0.6);
    if (item.text) {
      var size = item.h * 0.6;
      text(ctx, item.text, item.x + item.w / 2, item.y + item.h / 2 + 0.2, size, "#FFFFFF", item.w - 1.6);
    }
  };

  // Posters in blue, yellow and red on a white part of the wall.
  art.decor.posters = function (ctx, item) {
    box(ctx, item.x, item.y, item.w, item.h, 0.4, "#F7F6F2", 0.5);
    var colours = ["#4C8FD6", "#F2C53D", "#E8574B"];
    var gap = 1;
    var width = (item.w - gap * 4) / 3;
    colours.forEach(function (colour, index) {
      var left = item.x + gap + index * (width + gap);
      box(ctx, left, item.y + 1, width, item.h - 2, 0.3, colour, 0.4);
      // A white shape and a line of writing on each poster.
      circle(ctx, left + width / 2, item.y + item.h * 0.42, Math.min(width, item.h) * 0.2, "rgba(255, 255, 255, 0.85)", 0);
      line(ctx, left + width * 0.25, item.y + item.h - 1.9, left + width * 0.75, item.y + item.h - 1.9, "#FFFFFF", 0.4);
    });
  };

  // A doormat with ribs, flat on the floor.
  art.decor.mat = function (ctx, item) {
    box(ctx, item.x, item.y, item.w, item.h, 1, "#5E6270", 0.6);
    for (var x = item.x + 2; x < item.x + item.w - 1; x += 2) {
      line(ctx, x, item.y + 1.2, x, item.y + item.h - 1.2, "#747988", 0.6);
    }
  };

  // The light of a pendant lamp on the floor: a soft, faint warm pool.
  art.decor["light-pool"] = function (ctx, item) {
    var x = item.x + item.w / 2;
    var y = item.y + item.h / 2;
    var radius = Math.min(item.w, item.h) / 2;
    var glow = ctx.createRadialGradient(x, y, 0, x, y, radius);
    glow.addColorStop(0, "rgba(255, 248, 222, 0.45)");
    glow.addColorStop(1, "rgba(255, 246, 214, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(item.x, item.y, item.w, item.h);
  };
})();
