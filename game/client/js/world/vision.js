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

  // How dark the fog is: 0.60 since S-193 (Felix: "a touch lighter"; was
  // 0.74). The soft edge fades into this same value, so there is no seam.
  var FOG = "rgba(34, 36, 54, 0.6)";
  var CLEAR = "rgba(34, 36, 54, 0)";
  var FOG_COLOUR = "rgb(34, 36, 54)";
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

  // Soft wall shadows (S-214). The fog is drawn from several points of
  // sight instead of one: the centre and a ring of SAMPLE_RING points
  // SAMPLE_RADIUS map units around it. Where a wall cuts the view, part of
  // the points see a spot and part do not, so the shadow fades in over a
  // band instead of starting with a hard grey edge. The band is centred on
  // the true edge (the server's rule, S-185). A player always keeps 5 units
  // from every wall (his 10 x 10 square), so a point 4 units away can never
  // lie in or behind a wall.
  var SAMPLE_RADIUS = 4;
  var SAMPLE_RING = 8;
  // The fog is drawn small, one pixel per map unit, then scaled up smoothly.
  // Smoothing straight onto the big canvas is slow without a GPU (measured
  // in headless Chromium at device scale 2: 13 ms for that step alone), so
  // it is smoothed onto a canvas SMOOTH_SCALE times as large, whose pixels
  // are only about 1.5 screen pixels wide, and that one is copied without
  // smoothing. The whole soft fog then takes about 7 ms per frame at device
  // scale 2 (the hard fog 5.4 ms) and 5.3 ms at scale 1 (1.7 ms).
  var SMOOTH_SCALE = 3;
  var fogCanvas = null;
  var layerCanvas = null;
  var smoothCanvas = null;

  function sightPoints(origin) {
    var points = [origin];
    for (var i = 0; i < SAMPLE_RING; i++) {
      var angle = i * 2 * Math.PI / SAMPLE_RING;
      points.push({
        x: origin.x + SAMPLE_RADIUS * Math.cos(angle),
        y: origin.y + SAMPLE_RADIUS * Math.sin(angle),
      });
    }
    return points;
  }

  // A canvas of at least `w` x `h` pixels, made once and reused. Null where
  // there is no document (Node).
  function sizedCanvas(canvas, w, h) {
    if (!canvas) {
      if (typeof document === "undefined" || !document.createElement) return null;
      canvas = document.createElement("canvas");
      if (!canvas.getContext || !canvas.getContext("2d")) return null;
    }
    if (canvas.width !== w) canvas.width = w;
    if (canvas.height !== h) canvas.height = h;
    return canvas;
  }

  // Like darken, with soft wall shadows: the darken of every sight point is
  // averaged exactly, so colour, the full fog and the soft range edge stay
  // as they are. Returns false (and draws nothing) where no extra canvas
  // can be made; the caller then uses darken itself.
  function darkenSoftly(ctx, view, campus, origin) {
    // One spare unit on every side, so the smooth scaling has no seam at
    // the edge of the screen.
    var area = { x: Math.floor(view.x) - 1, y: Math.floor(view.y) - 1 };
    area.w = Math.ceil(view.x + view.w) + 1 - area.x;
    area.h = Math.ceil(view.y + view.h) + 1 - area.y;
    fogCanvas = sizedCanvas(fogCanvas, area.w, area.h);
    layerCanvas = fogCanvas && sizedCanvas(layerCanvas, area.w, area.h);
    smoothCanvas = layerCanvas && sizedCanvas(smoothCanvas, area.w * SMOOTH_SCALE, area.h * SMOOTH_SCALE);
    if (!smoothCanvas) return false;
    var fog = fogCanvas.getContext("2d");
    var layer = layerCanvas.getContext("2d");
    var range = rangeOf(campus);
    var points = sightPoints(origin);
    fog.setTransform(1, 0, 0, 1, 0, 0);
    fog.globalCompositeOperation = "source-over";
    fog.clearRect(0, 0, area.w, area.h);
    // 'lighter' adds up, so with an alpha of 1/n each the sum is the average.
    fog.globalCompositeOperation = "lighter";
    fog.globalAlpha = 1 / points.length;
    points.forEach(function (point) {
      layer.setTransform(1, 0, 0, 1, 0, 0);
      layer.clearRect(0, 0, area.w, area.h);
      layer.setTransform(1, 0, 0, 1, -area.x, -area.y);
      // The fade stays centred on the player, so the range edge is unchanged.
      darken(layer, area, boundary(campus, point), origin, range);
      fog.drawImage(layerCanvas, 0, 0);
    });
    // Rounding in the sum can shift the colour a little: paint it back to
    // the fog's own colour, keeping the averaged darkness.
    fog.globalAlpha = 1;
    fog.globalCompositeOperation = "source-in";
    fog.fillStyle = FOG_COLOUR;
    fog.fillRect(0, 0, area.w, area.h);
    fog.globalCompositeOperation = "source-over";
    var smooth = smoothCanvas.getContext("2d");
    smooth.clearRect(0, 0, smoothCanvas.width, smoothCanvas.height);
    smooth.imageSmoothingEnabled = true;
    smooth.drawImage(fogCanvas, 0, 0, smoothCanvas.width, smoothCanvas.height);
    ctx.save();
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(smoothCanvas, area.x, area.y, area.w, area.h);
    ctx.restore();
    return true;
  }

  function clip(ctx, points) {
    ctx.beginPath();
    trace(ctx, points);
    ctx.clip();
  }

  Game.world.vision = { rangeOf: rangeOf, boundary: boundary, darken: darken, darkenSoftly: darkenSoftly, clip: clip,
    sightPoints: sightPoints, SAMPLE_RADIUS: SAMPLE_RADIUS, FADE_FROM: FADE_FROM };
})();
