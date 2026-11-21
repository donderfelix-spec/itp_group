// The art of the Canteen (M2-1.4): the steel serving line with food pans
// behind a glass guard, trays, cutlery and a cash register; the menu board
// and the pass-through window to the kitchen; square tables with four
// chairs and trays; the microwave corner, a water fountain, a drinks
// fridge, the tray return and three recycling bins.
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
  var STEEL = "#C3CAD3";
  var STEEL_LIGHT = "#E3E7EC";
  var TRAY = "#E9A15A";
  var CHAIR = "#5FA88A";

  // ---- The serving line ------------------------------------------------

  // The food in the pans, from left to right: soup, rice, vegetables, a main
  // dish, salad, fruit, desserts.
  var FOODS = [
    { colour: "#E07B39", bits: "#F2B27A" },
    { colour: "#F6EEDC", bits: "#E4D9C0" },
    { colour: "#6DB65B", bits: "#F08A3C" },
    { colour: "#B9773D", bits: "#8B4F28" },
    { colour: "#8CC63F", bits: "#E8574B" },
    { colour: "#F2C53D", bits: "#E5483C" },
    { colour: "#F4E1C1", bits: "#C9493B" }
  ];

  // Steel, with the food pans behind a glass guard, and in front the tray
  // rail: a stack of trays and the cutlery at its start, the cash register
  // at its end.
  art.kinds["canteen:counter"] = function (ctx, counter) {
    var foodDepth = counter.h * 0.6;
    var railY = counter.y + foodDepth;
    util.shadowBelow(ctx, counter.x + 1, counter.y + counter.h, counter.w - 2, 1.4);
    util.box(ctx, counter.x, counter.y, counter.w, counter.h, 1, STEEL, 1);
    var start = counter.x + 16;
    var end = counter.x + counter.w - 14;
    var panWidth = (end - start) / FOODS.length;
    FOODS.forEach(function (food, index) {
      var left = start + index * panWidth;
      util.box(ctx, left + 0.4, counter.y + 1.2, panWidth - 0.8, foodDepth - 1.8, 0.6, "#8F97A3", 0.4);
      util.box(ctx, left + 1.1, counter.y + 1.9, panWidth - 2.2, foodDepth - 3.2, 0.8, food.colour, 0);
      ctx.fillStyle = food.bits;
      for (var bit = 0; bit < 3; bit++) {
        ctx.fillRect(left + 2 + bit * (panWidth - 4) / 3, counter.y + 2.6 + (bit % 2) * 1.6, 1, 1);
      }
      if (index === 0) {
        util.circle(ctx, left + panWidth - 2.4, counter.y + 3.4, 0.8, STEEL_LIGHT, 0.35); // the soup ladle
      }
    });
    // The glass guard in front of the food.
    ctx.fillStyle = "rgba(156, 211, 230, 0.65)";
    ctx.fillRect(start - 0.5, railY - 0.6, end - start + 1, 1.2);
    // The tray rail.
    util.box(ctx, counter.x + 1, railY + 1, counter.w - 2, counter.h - foodDepth - 2, 0.6, STEEL_LIGHT, 0.4);
    trayStack(ctx, counter.x + 1.5, counter.y + 1, 8, foodDepth + 2);
    cutlery(ctx, counter.x + 10.5, counter.y + 1.5, 4.5, foodDepth - 1);
    [0.35, 0.6].forEach(function (share) {
      tray(ctx, counter.x + counter.w * share, railY + 1.4, 9, counter.h - foodDepth - 2.8, true);
    });
    register(ctx, counter.x + counter.w - 11, counter.y + 1, 9.5, counter.h - 2);
  };

  function trayStack(ctx, x, y, w, h) {
    for (var i = 3; i >= 0; i--) {
      util.box(ctx, x + i * 0.3, y + i * 0.5, w, h - 1.5, 0.8, i === 0 ? TRAY : util.darker(TRAY, 0.15), 0.5);
    }
  }

  function cutlery(ctx, x, y, w, h) {
    util.box(ctx, x, y, w, h, 0.6, "#7F8592", 0.5);
    for (var i = 0; i < 3; i++) {
      util.line(ctx, x + 1 + i * 1.2, y + 0.8, x + 1 + i * 1.2, y + h - 0.8, STEEL_LIGHT, 0.5);
    }
  }

  // A tray, with a plate and a cup on it when `full` is true.
  function tray(ctx, x, y, w, h, full) {
    util.box(ctx, x, y, w, h, 0.6, TRAY, 0.5);
    if (full) {
      util.circle(ctx, x + w * 0.35, y + h / 2, Math.min(w, h) * 0.38, "#FFFFFF", 0.35);
      util.circle(ctx, x + w * 0.35, y + h / 2, Math.min(w, h) * 0.2, util.pick(["#E07B39", "#6DB65B", "#B9773D"], x, y), 0);
      util.circle(ctx, x + w * 0.78, y + h / 2, Math.min(w, h) * 0.18, "#FFFFFF", 0.35);
    }
  }

  function register(ctx, x, y, w, h) {
    util.box(ctx, x, y, w, h, 0.8, "#3A3646", 0.6);
    util.box(ctx, x + 1, y + 1, w - 2, h * 0.4, 0.4, "#8FD3F0", 0.4);
    for (var key = 0; key < 3; key++) {
      ctx.fillStyle = "#9AA1AC";
      ctx.fillRect(x + 1.4 + key * (w - 2.8) / 3, y + h * 0.62, (w - 2.8) / 3 - 0.6, 1.2);
    }
  }

  // ---- On the wall behind the counter ----------------------------------

  // A dark menu board: the heading (the entry's `text`) and lines of dishes
  // with prices.
  art.decor["menu-board"] = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 0.5, "#2F3B36", 0.6);
    if (item.text) {
      util.text(ctx, item.text, item.x + 6, item.y + 2.1, 2.2, "#F2C53D");
    }
    ctx.fillStyle = "rgba(255, 255, 255, 0.8)";
    for (var line = 0; line < 3; line++) {
      var y = item.y + 1.6 + line * 1.7;
      ctx.fillRect(item.x + 12, y, item.w * (0.35 + 0.08 * (line % 2)), 0.5);
      ctx.fillRect(item.x + item.w - 6, y, 3.6, 0.5);
    }
    ctx.fillRect(item.x + 1.5, item.y + 4, 8, 0.5);
    ctx.fillRect(item.x + 1.5, item.y + 5.6, 6, 0.5);
  };

  // The pass-through window to the kitchen: a dark opening with a steel sill,
  // a pot and a plate waiting.
  art.decor["pass-window"] = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 0.4, "#E4E8EE", 0.6);
    util.box(ctx, item.x + 1, item.y + 0.8, item.w - 2, item.h - 2.6, 0.3, "#4A4560", 0);
    ctx.fillStyle = "rgba(255, 238, 190, 0.35)";
    ctx.fillRect(item.x + 1, item.y + 0.8, item.w - 2, 1.2);
    ctx.fillStyle = STEEL;
    ctx.fillRect(item.x + 0.6, item.y + item.h - 1.8, item.w - 1.2, 1.4);
    util.box(ctx, item.x + item.w * 0.3, item.y + item.h - 4, 4, 2.4, 0.5, "#9AA1AC", 0.4); // a pot
    util.ellipse(ctx, item.x + item.w * 0.65, item.y + item.h - 2.2, 2.2, 0.8, "#FFFFFF", 0.4); // a plate
  };

  // ---- Tables ----------------------------------------------------------

  // A square table with a mint chair on each side (overhanging the table's
  // square by at most 2 units) and, on some tables, trays with plates.
  art.kinds.table = function (ctx, table) {
    var inset = table.w * 0.17;
    var chairSize = Math.min(table.w, table.h) * 0.22;
    var x = table.x + table.w / 2;
    var y = table.y + table.h / 2;
    var reach = table.w / 2 + 0.6 - chairSize / 2;
    util.chair(ctx, x, y - reach, chairSize, CHAIR, "up");
    util.chair(ctx, x, y + reach, chairSize, CHAIR, "down");
    util.chair(ctx, x - reach, y, chairSize, CHAIR, "left");
    util.chair(ctx, x + reach, y, chairSize, CHAIR, "right");
    var top = { x: table.x + inset, y: table.y + inset, w: table.w - 2 * inset, h: table.h - 2 * inset };
    util.shadowBelow(ctx, top.x, top.y + top.h, top.w, 0.8);
    util.box(ctx, top.x, top.y, top.w, top.h, 1.4, "#F4EBDA", 1);
    if (util.noise(table.x, table.y) < 0.75) {
      tray(ctx, top.x + 1.2, top.y + 1.4, top.w * 0.55, top.h * 0.36, true);
    }
    if (util.noise(table.y, table.x) < 0.5) {
      tray(ctx, top.x + top.w * 0.4, top.y + top.h * 0.56, top.w * 0.55, top.h * 0.36, true);
    }
  };

  // ---- The microwave corner and other fittings -------------------------

  // A short counter against the wall: microwaves (a door with a window and
  // a keypad), a kettle and a small sink.
  art.kinds["microwave-counter"] = function (ctx, counter) {
    util.box(ctx, counter.x, counter.y, counter.w, counter.h, 0.8, STEEL_LIGHT, 1);
    var microwaves = Math.max(1, Math.floor((counter.w - 20) / 12));
    for (var i = 0; i < microwaves; i++) {
      var left = counter.x + 1 + i * 12;
      util.box(ctx, left, counter.y + 0.8, 11, counter.h - 1.6, 0.8, "#F7F7F5", 0.7);
      util.box(ctx, left + 1, counter.y + 1.8, 6.6, counter.h - 3.6, 0.4, "#3A3646", 0.4);
      ctx.fillStyle = "rgba(255, 210, 120, 0.45)";
      ctx.fillRect(left + 1.6, counter.y + 2.4, 2.4, counter.h - 4.8);
      for (var key = 0; key < 3; key++) {
        ctx.fillStyle = "#9AA1AC";
        ctx.fillRect(left + 8.4, counter.y + 2 + key * 1.6, 1.8, 0.9);
      }
    }
    var after = counter.x + 1 + microwaves * 12;
    // The kettle: a round body with a handle.
    util.circle(ctx, after + 3, counter.y + counter.h / 2, 2.2, "#5E6672", 0.6);
    util.line(ctx, after + 5, counter.y + counter.h / 2 - 1, after + 5.8, counter.y + counter.h / 2 + 1, OUTLINE, 0.6);
    // The sink.
    util.box(ctx, after + 8, counter.y + 1.4, counter.x + counter.w - after - 9, counter.h - 2.8, 1, "#9AA3AF", 0.5);
    util.circle(ctx, after + 8 + (counter.x + counter.w - after - 9) / 2, counter.y + counter.h / 2, 0.6, "#5E6672", 0);
  };

  // A water fountain on the wall: a steel basin with a spout.
  art.kinds["water-fountain"] = function (ctx, fountain) {
    util.shadowBelow(ctx, fountain.x, fountain.y + fountain.h, fountain.w, 1.2);
    util.box(ctx, fountain.x, fountain.y, fountain.w, fountain.h, 1.6, STEEL, 0.8);
    util.ellipse(ctx, fountain.x + fountain.w / 2, fountain.y + fountain.h / 2, fountain.w * 0.3, fountain.h * 0.28, "#9CD3E6", 0.4);
    util.circle(ctx, fountain.x + fountain.w / 2, fountain.y + fountain.h * 0.3, 0.6, "#5E6672", 0);
  };

  // The tray return: a dark rack with used trays on its shelves.
  art.kinds["tray-rack"] = function (ctx, rack) {
    var upright = rack.h > rack.w;
    var across = upright ? rack.w : rack.h;
    var along = upright ? rack.h : rack.w;
    util.shadowBelow(ctx, rack.x, rack.y + rack.h, rack.w, 1);
    util.box(ctx, rack.x, rack.y, rack.w, rack.h, 0.8, "#5E6270", 0.8);
    for (var at = 1.2; at + 6 <= along - 0.8; at += 7.6) {
      var x = upright ? rack.x + 1.2 : rack.x + at;
      var y = upright ? rack.y + at : rack.y + 1.2;
      var w = upright ? across - 2.4 : 6.6;
      var h = upright ? 6.6 : across - 2.4;
      tray(ctx, x, y, w, h, false);
      util.circle(ctx, x + w / 2, y + h / 2, Math.min(w, h) * 0.3, "#FFFFFF", 0.35); // a used plate
    }
  };

  // Three recycling bins: blue (paper), yellow (plastic), green (glass).
  art.kinds["recycling-bins"] = function (ctx, bins) {
    var colours = ["#4C8FD6", "#F2C53D", "#5FA86B"];
    var upright = bins.h > bins.w;
    var size = (upright ? bins.h : bins.w) / colours.length;
    colours.forEach(function (colour, index) {
      var x = upright ? bins.x : bins.x + index * size;
      var y = upright ? bins.y + index * size : bins.y;
      var w = upright ? bins.w : size;
      var h = upright ? size : bins.h;
      util.box(ctx, x + 0.3, y + 0.3, w - 0.6, h - 0.6, 1, colour, 0.8);
      util.box(ctx, x + w * 0.25, y + h * 0.4, w * 0.5, h * 0.22, 0.6, util.darker(colour, 0.35), 0); // the slot
    });
  };

  // A slightly darker strip of floor where people queue at the counter.
  art.decor["queue-strip"] = function (ctx, item) {
    ctx.fillStyle = "rgba(46, 42, 59, 0.06)";
    ctx.fillRect(item.x, item.y, item.w, item.h);
    ctx.fillStyle = "rgba(242, 197, 61, 0.6)";
    ctx.fillRect(item.x, item.y + item.h - 0.6, item.w, 0.6);
  };
})();
