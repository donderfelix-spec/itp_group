// The art of the Lecture Hall (M2-1.4): a white front wall with two
// whiteboards and a clock, the long white table in front of them, a small
// lectern with a laptop on the stage, tiered and slightly curved rows of
// white desks with black chairs, carpeted aisles with steps, a bamboo slat
// wall with a large dark panel, and faint spotlights on the floor.
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
  var BAMBOO = "#E2BD7C";

  // ---- The front -------------------------------------------------------

  // The long white table in front of the whiteboards, with markers, papers
  // and a small projector on it.
  art.kinds.board = function (ctx, board) {
    util.shadowBelow(ctx, board.x + 1, board.y + board.h, board.w - 2, 1.2);
    util.box(ctx, board.x, board.y, board.w, board.h, 1, "#FFFFFF", 1);
    util.line(ctx, board.x + 1, board.y + board.h - 1.6, board.x + board.w - 1, board.y + board.h - 1.6, "#DADDE3", 0.6);
    var middleY = board.y + board.h * 0.42;
    ["#4C8FD6", "#E8574B", OUTLINE].forEach(function (colour, index) {
      var x = board.x + 8 + index * 3;
      util.line(ctx, x, middleY - 1.4, x + 0.6, middleY + 1.4, colour, 0.9);
    });
    util.box(ctx, board.x + board.w * 0.3, board.y + 1.4, 9, 4.4, 0.3, "#F6F4EE", 0.4); // papers
    util.box(ctx, board.x + board.w * 0.3 + 1.5, board.y + 1, 9, 4.4, 0.3, "#FFFFFF", 0.4);
    util.box(ctx, board.x + board.w * 0.62, board.y + 1.2, 8, 4.6, 0.8, "#5A5767", 0.5); // the projector
    util.circle(ctx, board.x + board.w * 0.62 + 6.2, board.y + 3.5, 1.2, "#9CD3E6", 0.4);
  };

  // A wide whiteboard on the front wall, with marker writing and a pen tray.
  art.decor.whiteboard = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 0.5, "#FFFFFF", 0.7);
    ctx.strokeStyle = "#9AA1AC";
    ctx.lineWidth = 0.5;
    ctx.strokeRect(item.x + 0.6, item.y + 0.6, item.w - 1.2, item.h - 1.2);
    var ink = util.noise(item.x, 1) < 0.5 ? "#4C8FD6" : "#E8574B";
    util.line(ctx, item.x + 3, item.y + 2, item.x + item.w * 0.4, item.y + 2, ink, 0.45);
    util.line(ctx, item.x + 3, item.y + 3.4, item.x + item.w * 0.3, item.y + 3.4, OUTLINE, 0.4);
    util.line(ctx, item.x + 3, item.y + 4.8, item.x + item.w * 0.35, item.y + 4.8, OUTLINE, 0.4);
    // A little chart on the right half.
    util.strokeAll(ctx, ink, 0.45, function () {
      ctx.moveTo(item.x + item.w * 0.58, item.y + item.h - 2.2);
      ctx.lineTo(item.x + item.w * 0.68, item.y + 3.6);
      ctx.lineTo(item.x + item.w * 0.78, item.y + 4.4);
      ctx.lineTo(item.x + item.w * 0.9, item.y + 1.8);
    });
    // The pen tray along the bottom edge, with two markers.
    ctx.fillStyle = "#B9BEC6";
    ctx.fillRect(item.x + 1, item.y + item.h - 1, item.w - 2, 0.9);
    ctx.fillStyle = "#E8574B";
    ctx.fillRect(item.x + 4, item.y + item.h - 1.1, 2, 0.6);
    ctx.fillStyle = "#4C8FD6";
    ctx.fillRect(item.x + 7, item.y + item.h - 1.1, 2, 0.6);
  };

  // A round wall clock.
  art.decor.clock = function (ctx, item) {
    var x = item.x + item.w / 2;
    var y = item.y + item.h / 2;
    var radius = Math.min(item.w, item.h) / 2;
    util.circle(ctx, x, y, radius, "#FFFFFF", 0.7);
    util.line(ctx, x, y, x, y - radius * 0.65, OUTLINE, 0.5);
    util.line(ctx, x, y, x + radius * 0.45, y + radius * 0.2, OUTLINE, 0.5);
    util.circle(ctx, x, y, 0.4, "#E8574B", 0);
  };

  // A small white lectern with an open laptop on it.
  art.kinds.lectern = function (ctx, lectern) {
    util.shadowBelow(ctx, lectern.x, lectern.y + lectern.h, lectern.w, 1.4);
    util.box(ctx, lectern.x, lectern.y, lectern.w, lectern.h, 1, "#FFFFFF", 1);
    util.box(ctx, lectern.x + 0.6, lectern.y + lectern.h - 2.2, lectern.w - 1.2, 1.6, 0.4, "#E3E5EA", 0);
    util.box(ctx, lectern.x + 1.4, lectern.y + 0.8, lectern.w - 2.8, 2.2, 0.3, "#3A3646", 0.4); // the screen
    util.box(ctx, lectern.x + 1.2, lectern.y + 3, lectern.w - 2.4, 1.8, 0.3, "#9AA1AC", 0.4); // the keys
  };

  // ---- The rows --------------------------------------------------------

  // How far the middle of a curved row lies behind its ends, in map units.
  var BOW = 2.2;

  // How far a row is curved back at `share` (0 at the left end, 1 at the right).
  function bowAt(share) {
    var fromMiddle = share * 2 - 1;
    return BOW * (1 - fromMiddle * fromMiddle);
  }

  // A long white desk, slightly curved (its middle a little further back),
  // with its row of black chairs behind it: the students face the front.
  // Desk and chairs lie inside the solid; chairs overhang it by less than 2.
  art.kinds.bench = function (ctx, bench) {
    var deskDepth = Math.min(6, bench.h * 0.4);
    var chairSize = 7.4;
    var steps = 12;
    for (var x = bench.x + 9; x <= bench.x + bench.w - 8; x += 15) {
      var chairY = bench.y + deskDepth + bowAt((x - bench.x) / bench.w) + chairSize / 2 + 0.3;
      util.chair(ctx, x, chairY, chairSize, "#34313E", "down");
    }
    // The desk: the front edge and the back edge follow the curve.
    ctx.beginPath();
    for (var i = 0; i <= steps; i++) {
      var share = i / steps;
      ctx.lineTo(bench.x + share * bench.w, bench.y + bowAt(share));
    }
    for (var j = steps; j >= 0; j--) {
      var back = j / steps;
      ctx.lineTo(bench.x + back * bench.w, bench.y + deskDepth + bowAt(back));
    }
    ctx.closePath();
    ctx.fillStyle = "#FFFFFF";
    ctx.fill();
    ctx.strokeStyle = OUTLINE;
    ctx.lineWidth = 1;
    ctx.stroke();
  };

  // ---- The floor -------------------------------------------------------

  // One level of the tiered floor, in its own (slightly darker towards the
  // back) wood tone, over the planks; its front edge is a step: a light
  // nosing line and a short dark shadow below the step above.
  art.decor.tier = function (ctx, item) {
    ctx.globalAlpha = 0.6;
    ctx.fillStyle = item.colour || "#E3C9A0";
    ctx.fillRect(item.x, item.y, item.w, item.h);
    ctx.globalAlpha = 1;
    ctx.fillStyle = "rgba(46, 42, 59, 0.16)";
    ctx.fillRect(item.x, item.y, item.w, 1.2);
    util.line(ctx, item.x, item.y, item.x + item.w, item.y, "#F8EBD3", 0.7);
  };

  // The stage at the front: a lighter, plain floor.
  art.decor.stage = function (ctx, item) {
    ctx.globalAlpha = 0.75;
    ctx.fillStyle = item.colour || "#F4E6CC";
    ctx.fillRect(item.x, item.y, item.w, item.h);
    ctx.globalAlpha = 1;
  };

  // A carpeted aisle beside the rows, with a step marking every 21 units
  // (the depth of one level).
  art.decor.aisle = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 0.6, "#A97B66", 0);
    ctx.fillStyle = "rgba(255, 255, 255, 0.06)";
    ctx.fillRect(item.x + 1, item.y, item.w - 2, item.h);
    for (var y = item.y; y < item.y + item.h - 1; y += 21) {
      util.line(ctx, item.x, y + 0.4, item.x + item.w, y + 0.4, "#F2C53D", 0.6);
    }
  };

  // A row of round spotlights of the ceiling, as very faint light on the floor.
  art.decor.spotlights = function (ctx, item) {
    var radius = item.h / 2;
    for (var x = item.x + radius; x <= item.x + item.w - radius; x += radius * 4) {
      var y = item.y + radius;
      var glow = ctx.createRadialGradient(x, y, 0, x, y, radius);
      glow.addColorStop(0, "rgba(255, 250, 230, 0.4)");
      glow.addColorStop(1, "rgba(255, 250, 230, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(x - radius, y - radius, 2 * radius, 2 * radius);
    }
  };

  // ---- The bamboo wall -------------------------------------------------

  // Warm bamboo slats with a large dark panel in the middle. On the face of
  // a wall running left to right the slats stand up; along a wall running
  // up and down (a thin strip on its inner side) they lie across.
  art.decor["bamboo-wall"] = function (ctx, item) {
    var upright = item.w >= item.h;
    ctx.fillStyle = BAMBOO;
    ctx.fillRect(item.x, item.y, item.w, item.h);
    util.strokeAll(ctx, util.darker(BAMBOO, 0.3), 0.3, function () {
      if (upright) {
        for (var x = item.x; x < item.x + item.w; x += 1.6) {
          ctx.moveTo(x, item.y);
          ctx.lineTo(x, item.y + item.h);
        }
      } else {
        for (var y = item.y; y < item.y + item.h; y += 1.6) {
          ctx.moveTo(item.x, y);
          ctx.lineTo(item.x + item.w, y);
        }
      }
    });
    // The dark panel: the middle part, a little inset.
    var panel = upright
      ? { x: item.x + item.w * 0.25, y: item.y + 1, w: item.w * 0.5, h: item.h - 2.2 }
      : { x: item.x + 0.5, y: item.y + item.h * 0.3, w: item.w - 1, h: item.h * 0.4 };
    util.box(ctx, panel.x, panel.y, panel.w, panel.h, 0.4, "#2F2C38", 0.5);
    ctx.fillStyle = "rgba(255, 255, 255, 0.12)";
    ctx.fillRect(panel.x + 0.6, panel.y + 0.6, panel.w * 0.4, 0.5);
  };
})();
