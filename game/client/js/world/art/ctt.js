// The art of the CTT Student Hall (M2-1.4): long white tables on both sides
// of a central aisle, with green (a few black) chairs, power sockets,
// laptops, books, cups and bags; white square pillars with small round
// "shh" signs; windows on both long sides with trees outside; a glass
// double door at the far end; the bookshelf with a plant.
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
  var GREEN = "#4FA36B";
  var BLACK = "#34313E";

  // ---- Tables ----------------------------------------------------------

  // A long white study table with chairs on both long sides; everything lies
  // inside the solid (the chairs overhang it by at most 2 units). The rows
  // of the left half (`table-row`) and of the right half (`study-table`)
  // look the same.
  function studyTable(ctx, table) {
    var chairSize = 6.4;
    var top = table.y + 4.4;
    var depth = table.h - 8.8;
    var seats = [];
    for (var x = table.x + 6; x <= table.x + table.w - 5; x += 12) {
      seats.push(x);
    }
    seats.forEach(function (x, index) {
      var colour = util.noise(table.y + table.x, index) < 0.2 ? BLACK : GREEN;
      util.chair(ctx, x, table.y + chairSize / 2 - 0.6, chairSize, colour, "up");
      util.chair(ctx, x, table.y + table.h - chairSize / 2 + 0.6, chairSize, colour, "down");
    });
    // A bag or a backpack on the floor beside a chair, under the table's edge.
    seats.forEach(function (x, index) {
      if (util.noise(index * 2.7, table.y) < 0.22) {
        var bagColour = util.pick(["#3A5A8C", "#C9493B", "#5E6270", "#E0A43A"], x, table.y);
        util.box(ctx, x + 3.4, table.y + table.h - 4.4, 4, 3.4, 1.1, bagColour, 0.5);
        util.line(ctx, x + 4, table.y + table.h - 4.1, x + 6.8, table.y + table.h - 4.1, util.darker(bagColour, 0.3), 0.5);
      }
    });
    util.shadowBelow(ctx, table.x + 1, top + depth, table.w - 2, 0.8);
    util.box(ctx, table.x, top, table.w, depth, 1, "#FFFFFF", 1);
    util.line(ctx, table.x + 1, top + depth - 1, table.x + table.w - 1, top + depth - 1, "#E1E4E9", 0.5);
    // Power sockets in the middle of the table, every two seats.
    for (var socket = 1; socket < seats.length; socket += 2) {
      var socketX = (seats[socket - 1] + seats[socket]) / 2;
      util.box(ctx, socketX - 1.2, top + depth / 2 - 0.8, 2.4, 1.6, 0.3, "#C3C7CF", 0.35);
      ctx.fillStyle = OUTLINE;
      ctx.fillRect(socketX - 0.6, top + depth / 2 - 0.2, 0.3, 0.4);
      ctx.fillRect(socketX + 0.3, top + depth / 2 - 0.2, 0.3, 0.4);
    }
    // Laptops (some glowing), books and cups at some of the seats.
    seats.forEach(function (x, index) {
      var look = util.noise(index, table.y + table.x);
      var front = util.noise(table.x + index * 3, table.y) < 0.5;
      var y = front ? top + 0.6 : top + depth - 2.9;
      if (look < 0.45) {
        laptop(ctx, x, y, front, look < 0.2);
      } else if (look < 0.6) {
        util.box(ctx, x - 1.5, y + 0.2, 3, 2.2, 0.3, util.pick(["#E8574B", "#4C8FD6", "#6DB65B"], x, y), 0.35);
      } else if (look < 0.72) {
        util.circle(ctx, x, y + 1.2, 0.9, "#FFFFFF", 0.35);
      }
    });
  }

  // An open laptop seen from above: the keyboard, and the screen folded up
  // on the side away from the student.
  function laptop(ctx, x, y, studentBelow, glowing) {
    var screenY = studentBelow ? y : y + 1.4;
    var keysY = studentBelow ? y + 0.9 : y;
    util.box(ctx, x - 2, keysY, 4, 1.6, 0.3, "#AEB5BF", 0.35);
    util.box(ctx, x - 2, screenY, 4, 0.9, 0.2, glowing ? "#8FD3F0" : "#3A3646", 0.35);
  }

  art.kinds["table-row"] = studyTable;
  art.kinds["study-table"] = studyTable;

  // ---- The bookshelf, pillars, runner ----------------------------------

  // A wooden bookshelf full of books of many colours, with a plant at its end.
  art.kinds.bookshelf = function (ctx, shelf) {
    util.box(ctx, shelf.x, shelf.y, shelf.w, shelf.h, 1, "#9B6B45", 1);
    var colours = ["#E8574B", "#4C8FD6", "#F2C53D", "#6DB65B", "#9B6BC9", "#F6EEDC", "#F08A3C"];
    var plantSpace = 9;
    var x = shelf.x + 1.2;
    while (x < shelf.x + shelf.w - plantSpace) {
      var width = 1.2 + util.noise(x, shelf.y) * 1.4;
      width = Math.min(width, shelf.x + shelf.w - plantSpace - x);
      ctx.fillStyle = util.pick(colours, x, shelf.x);
      ctx.fillRect(x, shelf.y + 1.2, width - 0.25, shelf.h - 2.4);
      x += width;
    }
    var plantX = shelf.x + shelf.w - plantSpace / 2 - 0.5;
    var plantY = shelf.y + shelf.h / 2;
    util.circle(ctx, plantX, plantY + 1.4, 2.6, "#B8643A", 0.6);
    util.foliage(ctx, plantX, plantY - 1, 3.6, util.LEAVES, 5);
  };

  // A white square pillar with a small black round sign saying "shh".
  art.kinds.pillar = function (ctx, pillar) {
    util.shadowBelow(ctx, pillar.x, pillar.y + pillar.h, pillar.w, 1.6);
    util.box(ctx, pillar.x, pillar.y, pillar.w, pillar.h, 0.8, "#FFFFFF", 1);
    ctx.fillStyle = "#E3E5EA";
    ctx.fillRect(pillar.x + pillar.w * 0.55, pillar.y + 0.6, pillar.w * 0.4, pillar.h - 1.2);
    var x = pillar.x + pillar.w / 2;
    var y = pillar.y + pillar.h / 2;
    var radius = Math.min(pillar.w, pillar.h) * 0.3;
    util.circle(ctx, x, y, radius, "#24222B", 0.4);
    util.text(ctx, "shh", x, y - radius * 0.05, radius * 0.95, "#FFFFFF", radius * 1.7);
  };

  // A long runner on the floor of the central aisle.
  art.decor.runner = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 0.8, "#AFC3DE", 0);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.55)";
    ctx.lineWidth = 0.5;
    ctx.strokeRect(item.x + 1, item.y + 1, item.w - 2, item.h - 2);
  };

  // ---- Outside, walls and doors ----------------------------------------

  // The crowns of trees outside the windows, on the lawn beyond the wall.
  art.decor["tree-crowns"] = function (ctx, item) {
    var radius = item.w / 2;
    for (var y = item.y + radius; y < item.y + item.h - radius; y += radius * 2.6) {
      var x = item.x + radius + (util.noise(y, 1) - 0.5) * 2;
      util.foliage(ctx, x, y, radius * 0.85, util.LEAVES, 6);
    }
  };

  // A closed glass double door in a wall running left to right.
  art.decor["glass-door"] = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 0.4, "#E4E8EE", 0.6);
    var leaf = (item.w - 3) / 2;
    [item.x + 1, item.x + 2 + leaf].forEach(function (x, index) {
      util.box(ctx, x, item.y + 1, leaf, item.h - 2, 0.2, "#A9D3E6", 0);
      util.line(ctx, x + 1.5, item.y + item.h - 1.3, x + 3.5, item.y + 1.3, "rgba(255, 255, 255, 0.85)", 0.4);
      var handleX = index === 0 ? x + leaf - 1 : x + 1;
      util.line(ctx, handleX, item.y + 1.8, handleX, item.y + item.h - 1.8, OUTLINE, 0.5);
    });
  };

  // A small black sign on the wall face with white words.
  art.decor["silence-sign"] = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 0.6, "#24222B", 0.5);
    if (item.text) {
      util.text(ctx, item.text, item.x + item.w / 2, item.y + item.h / 2 + 0.2, item.h * 0.45, "#FFFFFF", item.w - 2);
    }
  };
})();
