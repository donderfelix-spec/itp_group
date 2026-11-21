// The art of Mon Café (M2-1.4): the black counter on stainless-steel
// cabinets with sink, toaster oven, cash register and pastry display, the
// chrome three-group espresso machine with its grinders and cups, the "MON"
// sign and the menu screens on the tiled back wall, the white columns, the
// light wooden tables with grey-green chairs, the high table with bar stools
// along the window, black metal grid shelves with plants and cups.
// Places and sizes come from campus.json; see art/common.js for the rules.

"use strict";

window.Game = window.Game || {};
Game.world = Game.world || {};

(function () {
  var art = Game.world.art;
  if (!art || !art.util) {
    return; // common.js did not load: draw.js draws everything plain
  }
  var util = art.util;
  var OUTLINE = util.OUTLINE;

  var TEAL = "#1E8C8C";
  var STEEL = "#C3CAD3";
  var STEEL_LIGHT = "#E3E7EC";
  var CHAIR = "#9DB5A6";
  var WOOD = "#E0B77F";

  // ---- The counter -----------------------------------------------------

  // A black counter top on stainless-steel cabinets: the top seen from
  // above, and below it the front of the cabinets, with doors and handles.
  art.kinds["mon-cafe:counter"] = function (ctx, counter) {
    var topDepth = counter.h * 0.62;
    var frontTop = counter.y + topDepth;
    util.shadowBelow(ctx, counter.x + 1, counter.y + counter.h, counter.w - 2, 1.4);
    util.box(ctx, counter.x, counter.y, counter.w, counter.h, 1, STEEL, 1);
    var doors = Math.max(1, Math.round(counter.w / 15));
    var doorWidth = counter.w / doors;
    for (var i = 0; i < doors; i++) {
      var left = counter.x + i * doorWidth;
      util.box(ctx, left + 0.8, frontTop + 0.8, doorWidth - 1.6, counter.h - topDepth - 1.6, 0.4, STEEL_LIGHT, 0.4);
      util.line(ctx, left + doorWidth / 2 - 1.5, frontTop + 2.2, left + doorWidth / 2 + 1.5, frontTop + 2.2, "#8E96A3", 0.6);
    }
    util.box(ctx, counter.x, counter.y, counter.w, topDepth, 1, "#24222B", 1);
    util.line(ctx, counter.x + 2, counter.y + 1.2, counter.x + counter.w - 2, counter.y + 1.2, "#3F3B4B", 0.6);
  };

  // ---- The espresso machine --------------------------------------------

  // Chrome, with three group heads and their black handles, a drip tray,
  // steam wands, and white cups stacked on the warming top. The grinders
  // stand on its right end (decor "grinder").
  art.kinds.machine = function (ctx, machine) {
    var bodyWidth = machine.w * 0.72;
    util.shadowBelow(ctx, machine.x + 1, machine.y + machine.h, bodyWidth - 2, 1.4);
    util.box(ctx, machine.x, machine.y, bodyWidth, machine.h, 1.6, "#D4D9E0", 1);
    // The warming top with cups: two rows of white cups.
    var top = { x: machine.x + 1.2, y: machine.y + 1, w: bodyWidth - 2.4, h: machine.h * 0.34 };
    util.box(ctx, top.x, top.y, top.w, top.h, 0.8, STEEL_LIGHT, 0.5);
    for (var row = 0; row < 2; row++) {
      for (var x = top.x + 2; x < top.x + top.w - 1; x += 2.8) {
        util.circle(ctx, x + row * 1.4, top.y + 1.6 + row * 2.4, 1.1, "#FFFFFF", 0.35);
      }
    }
    // The front: three group heads with handles pointing at the viewer.
    var groupsY = machine.y + machine.h * 0.55;
    for (var group = 0; group < 3; group++) {
      var groupX = machine.x + bodyWidth * (group * 2 + 1) / 6;
      util.circle(ctx, groupX, groupsY, 1.8, "#8B929E", 0.6);
      util.line(ctx, groupX, groupsY + 1.6, groupX, groupsY + 4.4, OUTLINE, 1.1);
    }
    util.line(ctx, machine.x + 1.6, groupsY - 1, machine.x + 1.6, machine.y + machine.h - 2, "#8B929E", 0.6);
    util.line(ctx, machine.x + bodyWidth - 1.6, groupsY - 1, machine.x + bodyWidth - 1.6, machine.y + machine.h - 2, "#8B929E", 0.6);
    util.box(ctx, machine.x + 3, machine.y + machine.h - 2.6, bodyWidth - 6, 1.6, 0.4, "#3A3646", 0);
    util.circle(ctx, machine.x + bodyWidth - 3.4, machine.y + machine.h * 0.42, 0.6, "#F2695C", 0);
  };

  // A coffee grinder: a dark foot and a clear hopper of beans on top.
  art.decor.grinder = function (ctx, item) {
    util.box(ctx, item.x, item.y + item.h * 0.45, item.w, item.h * 0.55, 0.8, "#3A3646", 0.7);
    util.box(ctx, item.x + 0.4, item.y, item.w - 0.8, item.h * 0.5, 1, "rgba(220, 235, 240, 0.9)", 0.6);
    util.ellipse(ctx, item.x + item.w / 2, item.y + item.h * 0.3, item.w * 0.32, item.h * 0.14, "#6B4A2E", 0);
  };

  // ---- Things on the counter -------------------------------------------

  // A small steel sink with a tap.
  art.decor.sink = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 1, STEEL_LIGHT, 0.6);
    util.box(ctx, item.x + 1.2, item.y + 1.2, item.w - 2.4, item.h - 2.4, 1, "#9AA3AF", 0);
    util.circle(ctx, item.x + item.w / 2, item.y + item.h / 2, 0.6, "#5E6672", 0);
    util.line(ctx, item.x + item.w / 2, item.y + 0.4, item.x + item.w / 2, item.y + 2.4, "#DDE2E8", 0.9);
  };

  // A steel toaster oven with a dark window and two knobs.
  art.decor["toaster-oven"] = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 0.8, "#AEB5BF", 0.7);
    util.box(ctx, item.x + 1, item.y + 1.2, item.w * 0.62, item.h - 2.4, 0.4, "#3A3646", 0);
    ctx.fillStyle = "rgba(242, 160, 70, 0.7)";
    ctx.fillRect(item.x + 1.6, item.y + item.h - 2.6, item.w * 0.5, 0.8);
    util.circle(ctx, item.x + item.w - 2, item.y + item.h * 0.33, 0.7, OUTLINE, 0);
    util.circle(ctx, item.x + item.w - 2, item.y + item.h * 0.68, 0.7, OUTLINE, 0);
  };

  // The cash register: a small screen on a dark base.
  art.decor["cash-register"] = function (ctx, item) {
    util.box(ctx, item.x, item.y + item.h * 0.4, item.w, item.h * 0.6, 0.6, "#3A3646", 0.6);
    util.box(ctx, item.x + 1, item.y, item.w - 2, item.h * 0.5, 0.5, "#8FD3F0", 0.6);
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(item.x + 2, item.y + 1, (item.w - 4) * 0.6, 0.5);
  };

  // A glass case of croissants, cakes and custard tarts.
  art.decor["pastry-display"] = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 0.8, "rgba(225, 241, 247, 0.95)", 0.7);
    var inner = { x: item.x + 1, y: item.y + 1, w: item.w - 2, h: item.h - 2 };
    util.line(ctx, inner.x, inner.y + inner.h / 2, inner.x + inner.w, inner.y + inner.h / 2, "#B9C4CC", 0.4);
    var spacing = 4;
    for (var row = 0; row < 2; row++) {
      var y = inner.y + inner.h * (row === 0 ? 0.27 : 0.75);
      for (var x = inner.x + 2.2; x < inner.x + inner.w - 1.6; x += spacing) {
        var look = Math.floor(util.noise(x, row) * 3);
        if (look === 0) {
          ctx.beginPath(); // a croissant
          ctx.arc(x, y + 0.8, 1.4, Math.PI * 1.1, Math.PI * 1.9);
          ctx.strokeStyle = "#D08A3C";
          ctx.lineWidth = 1.1;
          ctx.stroke();
        } else if (look === 1) {
          util.box(ctx, x - 1.4, y - 1, 2.8, 2, 0.4, "#F4E1C1", 0.3); // a slice of cake
          ctx.fillStyle = "#C9493B";
          ctx.fillRect(x - 1.4, y - 0.2, 2.8, 0.5);
        } else {
          util.circle(ctx, x, y, 1.1, "#F6D36B", 0.3); // a custard tart
          util.circle(ctx, x, y, 0.45, "#C47A2C", 0);
        }
      }
    }
    ctx.fillStyle = "rgba(255, 255, 255, 0.7)";
    ctx.fillRect(item.x + 1, item.y + 0.5, item.w - 2, 0.5);
  };

  // A black pendant lamp over the counter, seen from above, with its glow.
  art.decor.pendant = function (ctx, item) {
    var x = item.x + item.w / 2;
    var y = item.y + item.h / 2;
    var radius = Math.min(item.w, item.h) / 2;
    var glow = ctx.createRadialGradient(x, y, 0, x, y, radius);
    glow.addColorStop(0, "rgba(255, 238, 190, 0.55)");
    glow.addColorStop(1, "rgba(255, 238, 190, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(item.x, item.y, item.w, item.h);
    util.circle(ctx, x, y, radius * 0.45, "#24222B", 0.5);
    util.circle(ctx, x, y, radius * 0.15, "#FFE9A8", 0);
  };

  // ---- On the back wall ------------------------------------------------

  // The sign: "MON" in teal letters, the O drawn as a coffee bean, and
  // "Café" next to it, on a white panel framed in light wood.
  art.decor["mon-sign"] = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 0.8, "#D9B27C", 0.6);
    util.box(ctx, item.x + 0.9, item.y + 0.9, item.w - 1.8, item.h - 1.8, 0.4, "#FFFFFF", 0);
    var middleY = item.y + item.h / 2 + 0.2;
    var size = item.h * 0.62;
    var left = item.x + item.w * 0.2;
    util.text(ctx, "M", left, middleY, size, TEAL);
    coffeeBean(ctx, left + size * 0.95, middleY, size * 0.36);
    util.text(ctx, "N", left + size * 1.85, middleY, size, TEAL);
    util.text(ctx, "Café", left + size * 3.75, middleY + 0.3, size * 0.8, TEAL);
  };

  function coffeeBean(ctx, x, y, radius) {
    util.ellipse(ctx, x, y, radius * 0.8, radius, "#6B4A2E", 0.4);
    ctx.beginPath();
    ctx.moveTo(x, y - radius * 0.85);
    ctx.quadraticCurveTo(x - radius * 0.45, y, x, y + radius * 0.85);
    ctx.strokeStyle = "#E9CFA6";
    ctx.lineWidth = 0.4;
    ctx.stroke();
  }

  // A dark menu screen with light lines of text and a teal heading.
  art.decor["menu-screen"] = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 0.6, "#2B2A33", 0.6);
    ctx.fillStyle = "#4FC1C1";
    ctx.fillRect(item.x + 1.4, item.y + 1.2, item.w * 0.35, 0.7);
    ctx.fillStyle = "rgba(255, 255, 255, 0.75)";
    for (var line = 0; line < 3; line++) {
      var y = item.y + 2.6 + line * 1.3;
      ctx.fillRect(item.x + 1.4, y, item.w * (0.45 + 0.1 * (line % 2)), 0.5);
      ctx.fillRect(item.x + item.w - 4, y, 2.4, 0.5); // the price
    }
  };

  // A thin black frame hanging on the wall, full of green plants.
  art.decor["plant-frame"] = function (ctx, item) {
    ctx.strokeStyle = OUTLINE;
    ctx.lineWidth = 0.5;
    ctx.strokeRect(item.x + 0.3, item.y + 0.3, item.w - 0.6, item.h - 0.6);
    for (var x = item.x + 3; x < item.x + item.w - 2; x += 4.6) {
      util.foliage(ctx, x, item.y + item.h * 0.4, 2.2, util.LEAVES, 4);
      util.ellipse(ctx, x + 1, item.y + item.h * 0.78, 0.8, 1.4, "#4E9659", 0.3); // hanging leaves
    }
  };

  // A dark poster with a light drawing.
  art.decor["dark-poster"] = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 0.4, "#2F2C38", 0.6);
    util.circle(ctx, item.x + item.w / 2, item.y + item.h * 0.42, Math.min(item.w, item.h) * 0.22, "#E9CFA6", 0);
    ctx.fillStyle = "rgba(255, 255, 255, 0.7)";
    ctx.fillRect(item.x + 2, item.y + item.h - 2, item.w - 4, 0.6);
  };

  // Large windows to the terrace in a wall running up and down: glass panes
  // in light frames over the dark top of the wall.
  art.decor.window = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 0.6, "#E4E8EE", 0.6);
    var panes = Math.max(1, Math.round(item.h / 18));
    var pane = item.h / panes;
    for (var i = 0; i < panes; i++) {
      var y = item.y + i * pane;
      util.box(ctx, item.x + 1.2, y + 1, item.w - 2.4, pane - 2, 0.3, "#A9D3E6", 0);
      util.line(ctx, item.x + 1.6, y + pane - 3, item.x + item.w - 1.6, y + 3, "rgba(255, 255, 255, 0.85)", 0.4);
    }
  };

  // ---- Columns, tables, chairs, stools, shelves ------------------------

  // A white column of the atrium: a square foot, the round shaft with a
  // shade on its lower side, and its shadow on the floor.
  art.kinds.column = function (ctx, column) {
    var x = column.x + column.w / 2;
    var y = column.y + column.h / 2;
    var radius = Math.min(column.w, column.h) / 2;
    util.ellipse(ctx, x + 1, y + radius * 0.55, radius * 0.95, radius * 0.8, "rgba(46, 42, 59, 0.14)", 0);
    util.box(ctx, column.x, column.y, column.w, column.h, 2, "#E9E9EC", 1);
    var shaft = radius * 0.74;
    util.circle(ctx, x, y, shaft, "#FFFFFF", 1.2);
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, shaft - 0.6, 0, Math.PI * 2);
    ctx.clip();
    util.circle(ctx, x + shaft * 0.35, y + shaft * 0.4, shaft * 0.85, "#E3E5EA", 0);
    ctx.restore();
    // The cap: a thin ring just inside the edge.
    util.circle(ctx, x, y, shaft * 0.72, null, 0.4, "#C9CDD4");
  };

  // A grey-green plastic chair seen from above, turned by `angle` (the way
  // it faces): a seat with small holes and a curved back behind it.
  function chair(ctx, x, y, size, angle, colour) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(angle);
    util.box(ctx, -size / 2, -size / 2, size, size, size * 0.3, colour, 0.6);
    ctx.fillStyle = util.darker(colour, 0.3);
    [-0.2, 0.2].forEach(function (holeX) {
      [-0.15, 0.2].forEach(function (holeY) {
        ctx.fillRect(holeX * size - 0.25, holeY * size - 0.25, 0.5, 0.5);
      });
    });
    // The back: behind the seat, away from the table.
    ctx.beginPath();
    ctx.arc(0, size * 0.1, size * 0.62, Math.PI * 0.62, Math.PI * 1.38);
    ctx.strokeStyle = util.darker(colour, 0.35);
    ctx.lineWidth = size * 0.26;
    ctx.lineCap = "round";
    ctx.stroke();
    ctx.restore();
  }

  // A light wooden table with four grey-green chairs around it. Table and
  // chairs lie inside the solid (the chairs overhang it by at most 2 units).
  art.kinds["round-table"] = function (ctx, table) {
    var x = table.x + table.w / 2;
    var y = table.y + table.h / 2;
    var half = Math.min(table.w, table.h) / 2;
    var chairSize = half * 0.5;
    var distance = half * 0.68;
    for (var i = 0; i < 4; i++) {
      var angle = i * Math.PI / 2; // right, below, left, above
      // The chair at this angle faces the middle: its back points outwards.
      chair(ctx, x + Math.cos(angle) * distance, y + Math.sin(angle) * distance, chairSize, angle - Math.PI, CHAIR);
    }
    var top = half * 0.55;
    util.ellipse(ctx, x + 0.6, y + 1.4, top, top * 0.85, "rgba(46, 42, 59, 0.14)", 0);
    util.circle(ctx, x, y, top, WOOD, 1);
    util.circle(ctx, x, y, top * 0.72, null, 0.3, "#C99A5E");
    util.circle(ctx, x - top * 0.3, y - top * 0.3, top * 0.25, "rgba(255, 255, 255, 0.35)", 0);
    // A cup on the table.
    util.circle(ctx, x + top * 0.35, y + top * 0.1, 0.9, "#FFFFFF", 0.35);
  };

  // A high wooden table along the window, with round bar stools on its
  // room side; everything lies inside the solid.
  art.kinds["high-table"] = function (ctx, bar) {
    var alongWall = bar.h >= bar.w;
    var depth = (alongWall ? bar.w : bar.h) * 0.5;
    var stools = Math.max(1, Math.floor((alongWall ? bar.h : bar.w) / 12));
    var spacing = (alongWall ? bar.h : bar.w) / stools;
    for (var i = 0; i < stools; i++) {
      var along = (i + 0.5) * spacing;
      var stoolX = alongWall ? bar.x + depth + (bar.w - depth) / 2 : bar.x + along;
      var stoolY = alongWall ? bar.y + along : bar.y + depth + (bar.h - depth) / 2;
      var stool = (alongWall ? bar.w : bar.h) * 0.23;
      util.circle(ctx, stoolX, stoolY + 0.8, stool * 1.1, "rgba(46, 42, 59, 0.14)", 0);
      util.circle(ctx, stoolX, stoolY, stool, "#3A3646", 0.6);
      util.circle(ctx, stoolX, stoolY, stool * 0.55, "#5A5767", 0);
    }
    if (alongWall) {
      util.box(ctx, bar.x, bar.y, depth, bar.h, 0.8, WOOD, 0.9);
    } else {
      util.box(ctx, bar.x, bar.y, bar.w, depth, 0.8, WOOD, 0.9);
    }
    // A few cups and a plant on the bar.
    for (var cup = 0; cup < stools; cup += 2) {
      var cupAlong = (cup + 0.5) * spacing;
      var cupX = alongWall ? bar.x + depth / 2 : bar.x + cupAlong;
      var cupY = alongWall ? bar.y + cupAlong : bar.y + depth / 2;
      util.circle(ctx, cupX, cupY, 0.9, "#FFFFFF", 0.35);
    }
  };

  // A shelf of thin black metal grid: square cells, some with a plant in a
  // pot, some with cups.
  art.kinds["grid-shelf"] = function (ctx, shelf) {
    util.shadowBelow(ctx, shelf.x, shelf.y + shelf.h, shelf.w, 1.2);
    // The shelf boards: see-through metal, a light dark tint.
    ctx.fillStyle = "rgba(46, 42, 59, 0.10)";
    ctx.fillRect(shelf.x, shelf.y, shelf.w, shelf.h);
    var upright = shelf.h >= shelf.w;
    var cell = upright ? shelf.w : shelf.h;
    var cells = Math.max(1, Math.round((upright ? shelf.h : shelf.w) / cell));
    var length = (upright ? shelf.h : shelf.w) / cells;
    for (var i = 0; i < cells; i++) {
      var x = upright ? shelf.x : shelf.x + i * length;
      var y = upright ? shelf.y + i * length : shelf.y;
      var w = upright ? shelf.w : length;
      var h = upright ? length : shelf.h;
      var look = util.noise(x, y);
      if (look < 0.55) {
        util.circle(ctx, x + w / 2, y + h / 2 + 0.8, Math.min(w, h) * 0.22, "#B8643A", 0.4); // a pot
        util.foliage(ctx, x + w / 2, y + h / 2 - 0.4, Math.min(w, h) * 0.36, util.LEAVES, 5);
      } else {
        util.circle(ctx, x + w * 0.35, y + h / 2, Math.min(w, h) * 0.16, "#FFFFFF", 0.35); // two cups
        util.circle(ctx, x + w * 0.68, y + h / 2, Math.min(w, h) * 0.16, "#FFFFFF", 0.35);
      }
    }
    // The grid itself, as thin black lines on top.
    util.strokeAll(ctx, OUTLINE, 0.7, function () {
      ctx.rect(shelf.x, shelf.y, shelf.w, shelf.h);
      for (var line = 1; line < cells; line++) {
        if (upright) {
          ctx.moveTo(shelf.x, shelf.y + line * length);
          ctx.lineTo(shelf.x + shelf.w, shelf.y + line * length);
        } else {
          ctx.moveTo(shelf.x + line * length, shelf.y);
          ctx.lineTo(shelf.x + line * length, shelf.y + shelf.h);
        }
      }
    });
  };
})();
