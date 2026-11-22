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

  // The one range of the fog and of the server (positions_in_sight).
  function rangeOf(campus) {
    return campus.classic_vision_range || 120;
  }

  function boundary(campus, origin) {
    var range = rangeOf(campus);
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

  var FOG = "rgba(34, 36, 54, 0.74)";
  var CLEAR = "rgba(34, 36, 54, 0)";
  // The view fades into the fog over its outer part: clear up to this share
  // of the range, then darker until it reaches the full fog at the range.
  var FADE_FROM = 0.6;

  // Darkens the map outside the view. With `origin` and `range` the floor
  // inside the view also fades softly into the fog towards the range, so
  // there is no hard edge where the range ends. Only the map is darkened:
  // players, F-sheets and the station glow are drawn afterwards, on top,
  // so everybody the server sends stays fully visible.
  function darken(ctx, view, points, origin, range) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(view.x, view.y, view.w, view.h);
    trace(ctx, points);
    ctx.fillStyle = FOG;
    ctx.fill("evenodd");
    if (origin && range > 0) {
      var inner = range * FADE_FROM;
      var fade = ctx.createRadialGradient(origin.x, origin.y, inner, origin.x, origin.y, range);
      // Two stops only: Chrome draws a two-stop gradient about 2.5 times
      // faster without a GPU than one with a stop in between.
      fade.addColorStop(0, CLEAR);
      fade.addColorStop(1, FOG);
      // Only the view itself is filled; that is cheaper than a clip.
      ctx.beginPath();
      trace(ctx, points);
      ctx.fillStyle = fade;
      ctx.fill();
    }
    ctx.restore();
  }

  function clip(ctx, points) {
    ctx.beginPath();
    trace(ctx, points);
    ctx.clip();
  }

  Game.world.vision = { rangeOf: rangeOf, boundary: boundary, darken: darken, clip: clip, FADE_FROM: FADE_FROM };
})();
