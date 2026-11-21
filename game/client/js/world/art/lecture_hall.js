// The art of the Lecture Hall (M2-1.4, rough pass): the front wall's two
// whiteboards and the long white desks with black chairs, facing the front.
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

  // Two wide whiteboards side by side, in grey frames, with a few lines of
  // marker on them.
  art.kinds.board = function (ctx, board) {
    var gap = 4;
    var width = (board.w - gap) / 2;
    [board.x, board.x + width + gap].forEach(function (left, index) {
      util.shadowBelow(ctx, left, board.y + board.h, width, 1.2);
      util.box(ctx, left, board.y, width, board.h, 0.8, "#FFFFFF", 1);
      util.line(ctx, left + 0.8, board.y + board.h - 1.2, left + width - 0.8, board.y + board.h - 1.2, "#9AA1AC", 0.8);
      var ink = index === 0 ? "#4C8FD6" : "#E8574B";
      util.line(ctx, left + 5, board.y + 2.4, left + width * 0.45, board.y + 2.4, ink, 0.5);
      util.line(ctx, left + 5, board.y + 4.2, left + width * 0.3, board.y + 4.2, ink, 0.5);
      util.line(ctx, left + width * 0.55, board.y + 2.4, left + width - 6, board.y + 4.6, "#2E2A3B", 0.4);
    });
  };

  // A long white desk, and below it the row of black chairs whose backs
  // face the viewer (the students look at the board). The chairs overhang
  // the desk's rectangle by at most 2 units.
  art.kinds.bench = function (ctx, bench) {
    var deskDepth = Math.min(5, bench.h * 0.55);
    var chairSize = 4.6;
    var chairY = bench.y + deskDepth + chairSize / 2 + 0.2;
    for (var x = bench.x + 6; x <= bench.x + bench.w - 5; x += 9.5) {
      util.chair(ctx, x, chairY, chairSize, "#34313E", "down");
    }
    util.shadowBelow(ctx, bench.x + 1, bench.y + deskDepth, bench.w - 2, 0.8);
    util.box(ctx, bench.x, bench.y, bench.w, deskDepth, 1, "#FFFFFF", 1);
    util.line(ctx, bench.x + 1, bench.y + deskDepth - 1.1, bench.x + bench.w - 1, bench.y + deskDepth - 1.1, "#DADDE3", 0.6);
  };
})();
