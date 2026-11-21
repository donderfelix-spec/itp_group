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

  // Calls `visit(x, y, row)` for every piece of a running bond: rows of
  // `height`, cut into pieces of `length`, each row shifted by `shiftOf(row)`.
  function eachPiece(area, length, height, shiftOf, visit) {
    var firstRow = Math.floor((area.y - CELL_OVERHANG) / height);
    var lastRow = Math.floor((area.y + area.h + CELL_OVERHANG) / height);
    for (var row = firstRow; row <= lastRow; row++) {
      var shift = shiftOf(row);
      var first = Math.floor((area.x - CELL_OVERHANG - shift) / length);
      var last = Math.floor((area.x + area.w + CELL_OVERHANG - shift) / length);
      for (var piece = first; piece <= last; piece++) {
        visit(shift + piece * length, row * height, row);
      }
    }
  }

  // Wooden planks running left to right, joints staggered from row to row.
  // First all planks, then all joints, so no plank covers a joint.
  art.floors.planks = function (ctx, area, room) {
    var floor = room ? room.floor : "#EAD3AE";
    var plankHeight = 6;
    var plankLength = 42;
    var shiftOf = function (row) { return Math.floor(noise(row, 7) * plankLength); };
    eachPiece(area, plankLength, plankHeight, shiftOf, function (x, y, row) {
      var tone = noise(x, row);
      ctx.fillStyle = tone < 0.5 ? darker(floor, 0.02 + tone * 0.05) : lighter(floor, (tone - 0.5) * 0.3);
      ctx.fillRect(x, y, plankLength, plankHeight);
    });
    strokeAll(ctx, darker(floor, 0.16), 0.5, function () {
      eachPiece(area, plankLength, plankHeight, shiftOf, function (x, y) {
        ctx.moveTo(x, y + plankHeight);
        ctx.lineTo(x, y);
        ctx.lineTo(x + plankLength, y);
      });
    });
  };

  // Polished concrete: big slabs with faint joints and a few speckles.
  art.floors.concrete = function (ctx, area, room) {
    var floor = room ? room.floor : "#EDEAE4";
    var slab = 30;
    eachCell(area, 0, 0, slab, slab, function (x, y, column, row) {
      ctx.fillStyle = mix(floor, "#C9C6C0", 0.22 + noise(column, row) * 0.12);
      ctx.fillRect(x, y, slab, slab);
    });
    strokeAll(ctx, mix(floor, "#B8B3AA", 0.45), 0.5, function () {
      eachCell(area, 0, 0, slab, slab, function (x, y) {
        ctx.rect(x, y, slab, slab);
      });
    });
    speckles(ctx, area, mix(floor, "#9C978F", 0.5), 5, 0.35);
  };

  // Small dots spread over the floor, one at most in every cell of `cell`.
  function speckles(ctx, area, colour, cell, share) {
    ctx.fillStyle = colour;
    eachCell(area, 0, 0, cell, cell, function (x, y, column, row) {
      if (noise(column * 3.1, row * 1.7) < share) {
        var dotX = x + noise(column, row * 2.3) * cell;
        var dotY = y + noise(column * 1.9, row) * cell;
        ctx.fillRect(dotX, dotY, 0.7, 0.7);
      }
    });
  }

  // Square tiles with light joints (the canteen).
  art.floors["mint-tiles"] = function (ctx, area, room) {
    var floor = room ? room.floor : "#D7EDDF";
    var tile = 10;
    ctx.fillStyle = darker(floor, 0.035);
    eachCell(area, 0, 0, tile, tile, function (x, y, column, row) {
      if ((column + row) % 2 === 0) {
        ctx.fillRect(x, y, tile, tile);
      }
    });
    strokeAll(ctx, lighter(floor, 0.4), 0.5, function () {
      eachCell(area, 0, 0, tile, tile, function (x, y) {
        ctx.rect(x, y, tile, tile);
      });
    });
  };

  // A pale floor with fine dark and light speckles (CTT, terrazzo).
  art.floors.speckled = function (ctx, area, room) {
    var floor = room ? room.floor : "#E4DED2";
    speckles(ctx, area, darker(floor, 0.28), 3, 0.45);
    speckles(ctx, area, lighter(floor, 0.7), 4, 0.4);
  };

  // Pingo Doce: small white tiles with a regular pattern of grey diamonds,
  // and a band of darker tiles along the walls.
  art.floors["diamond-tiles"] = function (ctx, area, room) {
    var floor = room ? room.floor : "#DCEFC8";
    var tile = 5;
    var diamondEvery = 20;
    var base = lighter(floor, 0.62);
    ctx.fillStyle = base;
    ctx.fillRect(area.x, area.y, area.w, area.h);
    // The joints of the small tiles.
    strokeAll(ctx, darker(base, 0.07), 0.35, function () {
      eachCell(area, 0, 0, tile, tile, function (x, y) {
        ctx.rect(x, y, tile, tile);
      });
    });
    // A grey diamond on every fourth crossing of the joints.
    ctx.beginPath();
    eachCell(area, 0, 0, diamondEvery, diamondEvery, function (x, y) {
      ctx.moveTo(x, y - tile / 2 - 0.6);
      ctx.lineTo(x + tile / 2 + 0.6, y);
      ctx.lineTo(x, y + tile / 2 + 0.6);
      ctx.lineTo(x - tile / 2 - 0.6, y);
      ctx.closePath();
    });
    ctx.fillStyle = mix(base, "#8E978F", 0.38);
    ctx.fill();
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

  // The Main Deck: light stone slabs laid in a running bond, each a little
  // lighter or darker than the next.
  art.floors.paving = function (ctx, area, room, campus) {
    var deck = campus && campus.colours ? campus.colours.deck : "#F3F0E9";
    var slabLength = 24;
    var slabHeight = 12;
    var joint = "#E1DBCD";
    // Every other row is shifted by half a slab.
    var shiftOf = function (row) { return Math.abs(row % 2) * slabLength / 2; };
    eachPiece(area, slabLength, slabHeight, shiftOf, function (x, y, row) {
      var tone = noise(x, row);
      ctx.fillStyle = tone < 0.5 ? darker(deck, tone * 0.05) : lighter(deck, (tone - 0.5) * 0.5);
      ctx.fillRect(x, y, slabLength, slabHeight);
    });
    strokeAll(ctx, joint, 0.9, function () {
      eachPiece(area, slabLength, slabHeight, shiftOf, function (x, y) {
        ctx.moveTo(x, y + slabHeight);
        ctx.lineTo(x, y);
        ctx.lineTo(x + slabLength, y);
      });
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

  // Lecture Hall: light bamboo slats.
  addFace("bamboo-slats", function (ctx, band) {
    slats(ctx, band, "#E2BD7C", 1.6);
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

  // The deck side of the buildings: a light facade with a row of windows.
  addFace("facade", function (ctx, band) {
    ctx.fillStyle = "#EEE7DA";
    ctx.fillRect(band.x, band.y, band.w, band.h);
    ctx.fillStyle = "rgba(46, 42, 59, 0.15)";
    ctx.fillRect(band.x, band.y, band.w, 1);
    var every = 14;
    var windowWidth = 10;
    var start = Math.floor(band.x / every) * every;
    for (var x = start; x < band.x + band.w; x += every) {
      var left = x + (every - windowWidth) / 2;
      box(ctx, left, band.y + 1.8, windowWidth, band.h - 3.4, 0.4, "#A9D3E6", 0.6);
      line(ctx, left + windowWidth / 2, band.y + 1.8, left + windowWidth / 2, band.y + band.h - 1.6, OUTLINE, 0.4);
      line(ctx, left + 1.5, band.y + band.h - 2.4, left + 3.5, band.y + 2.6, "#FFFFFF", 0.5);
    }
  });

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

  // An upright digital sign: a bright screen with a white line drawing of
  // an apple on it.
  art.decor.screen = function (ctx, item) {
    box(ctx, item.x, item.y, item.w, item.h, 0.6, OUTLINE, 0);
    box(ctx, item.x + 0.6, item.y + 0.6, item.w - 1.2, item.h - 1.2, 0.4, item.colour || "#7CC7EC", 0);
    var middleX = item.x + item.w / 2;
    var middleY = item.y + item.h / 2 + 0.2;
    var r = Math.min(item.w, item.h) * 0.24;
    ctx.strokeStyle = "#FFFFFF";
    ctx.lineWidth = 0.45;
    ctx.beginPath();
    ctx.arc(middleX - r * 0.35, middleY, r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(middleX + r * 0.35, middleY, r, 0, Math.PI * 2);
    ctx.stroke();
    line(ctx, middleX, middleY - r, middleX + r * 0.5, middleY - r * 1.6, "#FFFFFF", 0.45);
  };

  // A doormat with ribs, flat on the floor.
  art.decor.mat = function (ctx, item) {
    box(ctx, item.x, item.y, item.w, item.h, 1, "#5E6270", 0.6);
    for (var x = item.x + 2; x < item.x + item.w - 1; x += 2) {
      line(ctx, x, item.y + 1.2, x, item.y + item.h - 1.2, "#747988", 0.6);
    }
  };

  // The light of a pendant lamp on the floor: a soft warm pool.
  art.decor["light-pool"] = function (ctx, item) {
    var x = item.x + item.w / 2;
    var y = item.y + item.h / 2;
    var radius = Math.min(item.w, item.h) / 2;
    var glow = ctx.createRadialGradient(x, y, 0, x, y, radius);
    glow.addColorStop(0, "rgba(255, 246, 214, 0.55)");
    glow.addColorStop(1, "rgba(255, 246, 214, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(item.x, item.y, item.w, item.h);
  };
})();
