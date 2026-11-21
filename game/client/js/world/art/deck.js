// The art of the Main Deck (M2-1.4, rough pass): the reflecting pool with
// its stone edge, young trees in gravel beds and the leafy hedge.
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

  // The shallow pool: a light stone edge, water with ripples.
  art.kinds.pool = function (ctx, pool) {
    util.box(ctx, pool.x, pool.y, pool.w, pool.h, 3, "#E6E0D2", 1.4);
    var edge = 3;
    var water = { x: pool.x + edge, y: pool.y + edge, w: pool.w - 2 * edge, h: pool.h - 2 * edge };
    util.box(ctx, water.x, water.y, water.w, water.h, 1.5, "#9CD3E6", 0.8);
    ctx.save();
    util.roundedPath(ctx, water.x, water.y, water.w, water.h, 1.5);
    ctx.clip();
    // The tiles on the bottom of the pool, faint through the water.
    ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
    ctx.lineWidth = 0.4;
    for (var x = water.x + 8; x < water.x + water.w; x += 8) {
      util.line(ctx, x, water.y, x, water.y + water.h, ctx.strokeStyle, 0.4);
    }
    for (var y = water.y + 8; y < water.y + water.h; y += 8) {
      util.line(ctx, water.x, y, water.x + water.w, y, ctx.strokeStyle, 0.4);
    }
    // The shade of the edge on the water.
    ctx.fillStyle = "rgba(46, 42, 59, 0.12)";
    ctx.fillRect(water.x, water.y, water.w, 2);
    ctx.restore();
    ctx.lineCap = "round";
    [[0.1, 0.36, 0.38], [0.52, 0.66, 0.86], [0.2, 0.78, 0.36]].forEach(function (wave) {
      var y = pool.y + pool.h * wave[1];
      util.line(ctx, pool.x + pool.w * wave[0], y, pool.x + pool.w * wave[2], y, "#DDF0FA", 1.4);
    });
    ctx.lineCap = "butt";
  };

  // A young tree: a gravel bed with a round crown of leaves.
  art.kinds.tree = function (ctx, bed) {
    util.box(ctx, bed.x, bed.y, bed.w, bed.h, 2, "#D9D2C2", 1);
    ctx.fillStyle = "#B8AE98";
    for (var i = 0; i < 26; i++) {
      var x = bed.x + 2 + util.noise(bed.x + i, bed.y) * (bed.w - 4);
      var y = bed.y + 2 + util.noise(bed.y, bed.x + i * 1.7) * (bed.h - 4);
      ctx.fillRect(x, y, 0.8, 0.8);
    }
    var middleX = bed.x + bed.w / 2;
    var middleY = bed.y + bed.h / 2;
    var radius = bed.w * 0.36;
    util.ellipse(ctx, middleX + 1, middleY + 2.2, radius, radius * 0.8, "rgba(46, 42, 59, 0.16)", 0);
    for (var leaf = 0; leaf < 6; leaf++) {
      var angle = leaf / 6 * Math.PI * 2;
      util.circle(ctx, middleX + Math.cos(angle) * radius * 0.45, middleY + Math.sin(angle) * radius * 0.45, radius * 0.58, "#5FA86B", 1);
    }
    util.circle(ctx, middleX, middleY, radius * 0.62, "#5FA86B", 0);
    util.circle(ctx, middleX - radius * 0.25, middleY - radius * 0.3, radius * 0.32, "#7DBE7A", 0);
    util.circle(ctx, middleX + radius * 0.3, middleY - radius * 0.05, radius * 0.18, "#7DBE7A", 0);
  };

  // The hedge: a green block with a leafy, bumpy edge.
  art.kinds.hedge = function (ctx, hedge) {
    var bump = 3;
    util.shadowBelow(ctx, hedge.x + 2, hedge.y + hedge.h, hedge.w - 4, 1.6);
    ctx.fillStyle = "#5FA86B";
    ctx.strokeStyle = util.OUTLINE;
    ctx.lineWidth = 1.4;
    util.roundedPath(ctx, hedge.x, hedge.y, hedge.w, hedge.h, 7);
    ctx.fill();
    ctx.stroke();
    for (var x = hedge.x + 5; x < hedge.x + hedge.w - 3; x += 6) {
      util.circle(ctx, x, hedge.y + bump, 2.2, "#4E9659", 0);
      util.circle(ctx, x + 3, hedge.y + hedge.h - bump, 2.2, "#4E9659", 0);
      util.circle(ctx, x + 1.5, hedge.y + hedge.h / 2, 1.6, "#7DBE7A", 0);
    }
  };
})();
