// The art of the Canteen (M2-1.4, rough pass): the serving line with food
// and trays, and square tables with four chairs each.
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

  // Stainless steel: pans of food behind a glass guard, and in front the
  // rail where the trays slide along.
  art.kinds["canteen:counter"] = function (ctx, counter) {
    var foodDepth = counter.h * 0.6;
    util.shadowBelow(ctx, counter.x + 1, counter.y + counter.h, counter.w - 2, 1.4);
    util.box(ctx, counter.x, counter.y, counter.w, counter.h, 1, "#C3CAD3", 1);
    var foods = ["#E07B39", "#F2D06B", "#6DB65B", "#C9493B", "#B9773D", "#F6EEDC"];
    var pans = Math.floor((counter.w - 4) / 11);
    var panWidth = (counter.w - 4) / pans;
    for (var i = 0; i < pans; i++) {
      var left = counter.x + 2 + i * panWidth;
      util.box(ctx, left + 0.4, counter.y + 1.4, panWidth - 0.8, foodDepth - 2, 0.6, "#8F97A3", 0.4);
      util.box(ctx, left + 1.2, counter.y + 2.1, panWidth - 2.4, foodDepth - 3.4, 0.8, foods[i % foods.length], 0);
    }
    // The glass guard in front of the food.
    ctx.fillStyle = "rgba(156, 211, 230, 0.6)";
    ctx.fillRect(counter.x + 1, counter.y + foodDepth - 0.4, counter.w - 2, 1.2);
    // The tray rail with a few trays on it.
    var railY = counter.y + foodDepth + 1;
    util.line(ctx, counter.x + 1, railY + 1.6, counter.x + counter.w - 1, railY + 1.6, "#9AA1AC", 0.6);
    [0.12, 0.4, 0.7].forEach(function (share) {
      util.box(ctx, counter.x + counter.w * share, railY, 9, counter.h - foodDepth - 2, 0.6, "#E9A15A", 0.5);
    });
  };

  // A square table with a chair on each side; the chairs overhang the
  // table's square by at most 2 units.
  art.kinds.table = function (ctx, table) {
    var inset = table.w * 0.17;
    var chairSize = Math.min(table.w, table.h) * 0.22;
    var x = table.x + table.w / 2;
    var y = table.y + table.h / 2;
    var reach = table.w / 2 + 0.6 - chairSize / 2;
    var chairColour = "#5FA88A";
    util.chair(ctx, x, y - reach, chairSize, chairColour, "up");
    util.chair(ctx, x, y + reach, chairSize, chairColour, "down");
    util.chair(ctx, x - reach, y, chairSize, chairColour, "left");
    util.chair(ctx, x + reach, y, chairSize, chairColour, "right");
    util.shadowBelow(ctx, table.x + inset, table.y + table.h - inset, table.w - 2 * inset, 0.8);
    util.box(ctx, table.x + inset, table.y + inset, table.w - 2 * inset, table.h - 2 * inset, 1.4, "#F4EBDA", 1);
  };
})();
