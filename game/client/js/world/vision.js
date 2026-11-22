// The fog uses the same range and opaque wall rectangles as the server.
"use strict";

(function () {
  function rayEnd(origin, dx, dy, range, walls) {
    var distance = range;
    // An almost parallel ray avoids dividing by zero on an axis.
    var xDirection = dx || Number.EPSILON;
    var yDirection = dy || Number.EPSILON;
    for (var i = 0; i < walls.length; i++) {
      var wall = walls[i];
      var left = (wall.x - origin.x) / xDirection;
      var right = (wall.x + wall.w - origin.x) / xDirection;
      var top = (wall.y - origin.y) / yDirection;
      var bottom = (wall.y + wall.h - origin.y) / yDirection;
      var entry = Math.max(0, Math.min(left, right), Math.min(top, bottom));
      var exit = Math.min(Math.max(left, right), Math.max(top, bottom));
      if (entry <= exit && exit > 0) distance = Math.min(distance, entry);
    }
    return { x: origin.x + dx * distance, y: origin.y + dy * distance };
  }

  function boundary(campus, origin) {
    var range = campus.classic_vision_range || 150;
    var walls = campus.solids.filter(function (wall) {
      return wall.kind === "wall"
        && wall.x <= origin.x + range && wall.x + wall.w >= origin.x - range
        && wall.y <= origin.y + range && wall.y + wall.h >= origin.y - range;
    });
    var angles = [];
    for (var i = 0; i < 96; i++) angles.push(i * Math.PI / 48 - Math.PI);
    walls.forEach(function (wall) {
      [wall.x, wall.x + wall.w].forEach(function (x) {
        [wall.y, wall.y + wall.h].forEach(function (y) {
          var angle = Math.atan2(y - origin.y, x - origin.x);
          angles.push(angle - 0.0001, angle, angle + 0.0001);
        });
      });
    });
    angles.sort(function (a, b) { return a - b; });
    return angles.map(function (angle) {
      return rayEnd(origin, Math.cos(angle), Math.sin(angle), range, walls);
    });
  }

  function trace(ctx, points) {
    ctx.moveTo(points[0].x, points[0].y);
    for (var i = 1; i < points.length; i++) ctx.lineTo(points[i].x, points[i].y);
    ctx.closePath();
  }

  function darken(ctx, view, points) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(view.x, view.y, view.w, view.h);
    trace(ctx, points);
    ctx.fillStyle = "rgba(34, 36, 54, 0.74)";
    ctx.fill("evenodd");
    ctx.restore();
  }

  function clip(ctx, points) {
    ctx.beginPath();
    trace(ctx, points);
    ctx.clip();
  }

  Game.world.vision = { boundary: boundary, darken: darken, clip: clip };
})();
