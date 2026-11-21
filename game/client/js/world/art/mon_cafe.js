// The art of Mon Café (M2-1.4, rough pass): the black counter on stainless
// steel, the chrome espresso machine with cups on top, the white columns and
// the light wooden tables with grey-green chairs.
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

  // A black counter top on a front of brushed stainless steel.
  art.kinds["mon-cafe:counter"] = function (ctx, counter) {
    var topDepth = counter.h * 0.62;
    util.shadowBelow(ctx, counter.x + 1, counter.y + counter.h, counter.w - 2, 1.4);
    util.box(ctx, counter.x, counter.y, counter.w, counter.h, 1, "#BCC3CC", 1);
    for (var x = counter.x + 3; x < counter.x + counter.w - 1; x += 3) {
      util.line(ctx, x, counter.y + topDepth + 0.6, x, counter.y + counter.h - 0.8, "#D5DAE1", 0.5);
    }
    util.box(ctx, counter.x, counter.y, counter.w, topDepth, 1, "#24222B", 1);
    util.line(ctx, counter.x + 2, counter.y + 1.4, counter.x + counter.w * 0.4, counter.y + 1.4, "#4A4656", 0.6);
    // A few white cups waiting on the counter.
    [0.62, 0.7, 0.78].forEach(function (share) {
      util.circle(ctx, counter.x + counter.w * share, counter.y + topDepth / 2, 1.4, "#FFFFFF", 0.4);
    });
  };

  // The chrome espresso machine: two group heads, a drip tray, white cups
  // warming on top.
  art.kinds.machine = function (ctx, machine) {
    util.shadowBelow(ctx, machine.x + 1, machine.y + machine.h, machine.w - 2, 1.4);
    util.box(ctx, machine.x, machine.y, machine.w, machine.h, 2, "#D4D9E0", 1);
    util.box(ctx, machine.x + 1.5, machine.y + 1.2, machine.w - 3, machine.h * 0.36, 1, "#EEF1F4", 0.5);
    for (var x = machine.x + 4; x < machine.x + machine.w - 2; x += 4) {
      util.circle(ctx, x, machine.y + 1.2 + machine.h * 0.18, 1.2, "#FFFFFF", 0.4);
    }
    util.box(ctx, machine.x + 3, machine.y + machine.h * 0.62, machine.w - 6, machine.h * 0.26, 0.6, "#3A3646", 0);
    util.circle(ctx, machine.x + machine.w * 0.32, machine.y + machine.h * 0.55, 2, "#7A808C", 0.6);
    util.circle(ctx, machine.x + machine.w * 0.68, machine.y + machine.h * 0.55, 2, "#7A808C", 0.6);
    util.circle(ctx, machine.x + machine.w - 3, machine.y + machine.h * 0.55, 0.8, "#F2695C", 0);
  };

  // A round white column with a soft shade on its lower side.
  art.kinds.column = function (ctx, column) {
    var x = column.x + column.w / 2;
    var y = column.y + column.h / 2;
    var radius = Math.min(column.w, column.h) / 2;
    util.ellipse(ctx, x, y + radius * 0.35, radius, radius * 0.9, "rgba(46, 42, 59, 0.12)", 0);
    util.circle(ctx, x, y, radius, "#FFFFFF", 1.6);
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, radius - 0.8, 0, Math.PI * 2);
    ctx.clip();
    util.circle(ctx, x + radius * 0.35, y + radius * 0.35, radius * 0.85, "#E6E8EC", 0);
    ctx.restore();
  };

  // A light wooden table with three grey-green chairs around it; the chairs
  // overhang the table's square by at most 2 units.
  art.kinds["round-table"] = function (ctx, table) {
    var x = table.x + table.w / 2;
    var y = table.y + table.h / 2;
    var half = Math.min(table.w, table.h) / 2;
    var chairRadius = half * 0.36;
    var chairDistance = half + 1.8 - chairRadius;
    for (var i = 0; i < 3; i++) {
      var angle = -Math.PI / 2 + i / 3 * Math.PI * 2 + Math.PI / 3;
      var chairX = x + Math.cos(angle) * chairDistance;
      var chairY = y + Math.sin(angle) * chairDistance;
      util.circle(ctx, chairX, chairY, chairRadius, "#9DB5A6", 0.6);
      // The backrest: a darker rim on the side away from the table.
      ctx.beginPath();
      ctx.arc(chairX, chairY, chairRadius - 0.6, angle - 1.1, angle + 1.1);
      ctx.strokeStyle = "#6F8A7A";
      ctx.lineWidth = 1.1;
      ctx.stroke();
    }
    util.ellipse(ctx, x, y + 1.2, half * 0.72, half * 0.62, "rgba(46, 42, 59, 0.12)", 0);
    util.circle(ctx, x, y, half * 0.72, "#E0B77F", 1);
    util.circle(ctx, x - half * 0.2, y - half * 0.2, half * 0.25, "rgba(255, 255, 255, 0.35)", 0);
  };
})();
