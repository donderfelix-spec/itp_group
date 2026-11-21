// The art of the CTT Student Hall (M2-1.4, rough pass): long white tables
// with green (a few black) chairs on both sides and laptops, and the
// bookshelf at the end.
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

  // A long white table with chairs on both long sides; the chairs overhang
  // the row's rectangle by at most 2 units.
  art.kinds["table-row"] = function (ctx, row) {
    var chairSize = 4.4;
    var tableTop = row.y + 3;
    var tableDepth = row.h - 6;
    var seats = [];
    for (var x = row.x + 6; x <= row.x + row.w - 5; x += 11.5) {
      seats.push(x);
    }
    seats.forEach(function (x, index) {
      var black = util.noise(row.y, index) < 0.2;
      var colour = black ? "#34313E" : "#4FA36B";
      util.chair(ctx, x, row.y + chairSize / 2 - 0.6, chairSize, colour, "up");
      util.chair(ctx, x, row.y + row.h - chairSize / 2 + 0.6, chairSize, colour, "down");
    });
    util.shadowBelow(ctx, row.x + 1, tableTop + tableDepth, row.w - 2, 0.8);
    util.box(ctx, row.x, tableTop, row.w, tableDepth, 1, "#FFFFFF", 1);
    // Laptops at some of the seats.
    seats.forEach(function (x, index) {
      if (util.noise(index, row.y) < 0.45) {
        var top = util.noise(row.x, index * 3 + row.y) < 0.5;
        var laptopY = top ? tableTop + 0.8 : tableTop + tableDepth - 3.3;
        util.box(ctx, x - 2, laptopY, 4, 2.5, 0.4, "#9AA1AC", 0.4);
        util.line(ctx, x - 1.5, top ? laptopY + 0.6 : laptopY + 1.9, x + 1.5, top ? laptopY + 0.6 : laptopY + 1.9, "#3A3646", 0.6);
      }
    });
  };

  // A wooden bookshelf, full of books of many colours.
  art.kinds.bookshelf = function (ctx, shelf) {
    util.box(ctx, shelf.x, shelf.y, shelf.w, shelf.h, 1, "#9B6B45", 1);
    var colours = ["#E8574B", "#4C8FD6", "#F2C53D", "#6DB65B", "#9B6BC9", "#F6EEDC", "#F08A3C"];
    var x = shelf.x + 1.2;
    while (x < shelf.x + shelf.w - 2) {
      var width = 1.2 + util.noise(x, shelf.y) * 1.4;
      width = Math.min(width, shelf.x + shelf.w - 1.2 - x);
      ctx.fillStyle = util.pick(colours, x, shelf.x);
      ctx.fillRect(x, shelf.y + 1.2, width - 0.25, shelf.h - 2.4);
      x += width;
    }
  };
})();
