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
  var FOG_ALPHA = 0.6; // the alpha of FOG
  var OPAQUE = "rgba(34, 36, 54, 1)";
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

  // Soft wall shadows (S-214). Besides the player's centre, a ring of
  // SAMPLE_RING points SAMPLE_RADIUS map units around it is asked what it
  // sees. Where a wall cuts the view, the share of these points that see a
  // spot falls off towards the sight line, so the floor darkens softly
  // before it. Everything beyond the line, that is everything the server
  // keeps from the player (S-185), still gets the full fog, so no floor
  // looks visible where no player would be drawn. A player always keeps 5
  // units from every wall (his 10 x 10 square), so a point 4 units away
  // can never lie in or behind a wall.
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

  // Like darken, with soft wall shadows. Works in "shade" (0 clear, 1 the
  // full fog) on small canvases, then draws it in the fog colour at the
  // fog's alpha. Returns false (and draws nothing) where no extra canvas can
  // be made; the caller then uses darken itself.
  function darkenSoftly(ctx, view, campus, origin) {
    // One spare unit on every side, so the smooth scaling has no seam at
    // the edge of the screen.
    // The size depends only on the size of the view, not on where it lies,
    // so the canvases are not made anew in nearly every frame while walking.
    var area = { x: Math.floor(view.x) - 1, y: Math.floor(view.y) - 1 };
    area.w = Math.ceil(view.w) + 3;
    area.h = Math.ceil(view.h) + 3;
    fogCanvas = sizedCanvas(fogCanvas, area.w, area.h);
    layerCanvas = fogCanvas && sizedCanvas(layerCanvas, area.w, area.h);
    smoothCanvas = layerCanvas && sizedCanvas(smoothCanvas, area.w * SMOOTH_SCALE, area.h * SMOOTH_SCALE);
    if (!smoothCanvas) return false;
    var fog = fogCanvas.getContext("2d");
    var seen = layerCanvas.getContext("2d");
    var range = rangeOf(campus);
    var points = sightPoints(origin);
    var sights = points.map(function (point) { return boundary(campus, point); });
    var whole = { x: 0, y: 0, w: area.w, h: area.h };

    // 1. The share of sight points that see each spot: 'lighter' adds up,
    //    so with an alpha of 1/n per view the sum is the share. One step of
    //    255 more per view, so that 8-bit rounding never leaves a spot that
    //    all points see a touch short of fully seen (the sum stops at 1).
    begin(seen, area, "copy", 1);
    seen.clearRect(area.x, area.y, area.w, area.h);
    begin(seen, area, "lighter", 1 / points.length + 1 / 255);
    sights.forEach(function (sight) { fillPath(seen, sight, OPAQUE); });

    // 2. Shade = twice the share not seeing, at most 1. At the sight line
    //    about half the points see (the centre and half the ring), so the
    //    shade reaches 1 there and the soft band lies before the line.
    begin(fog, whole, "copy", 1);
    fog.clearRect(0, 0, area.w, area.h);
    fillPath(fog, null, OPAQUE, whole);
    fog.globalCompositeOperation = "destination-out";
    fog.drawImage(layerCanvas, 0, 0);
    copyInto(seen, fogCanvas, area);
    fog.globalCompositeOperation = "lighter";
    fog.drawImage(layerCanvas, 0, 0);

    // 3. All that the centre does not see (behind walls, beyond the
    //    range): the full shade, as in darken.
    begin(fog, area, "source-over", 1);
    fillPath(fog, sights[0], OPAQUE, area, "evenodd");

    // 4. The soft range edge of S-188, centred on the player, laid over it.
    var fade = fog.createRadialGradient(origin.x, origin.y, range * FADE_FROM, origin.x, origin.y, range);
    fade.addColorStop(0, CLEAR);
    fade.addColorStop(1, OPAQUE);
    fillPath(fog, null, fade, area);

    // 5. In the fog's colour, scaled up smoothly, at the fog's alpha.
    begin(fog, whole, "source-in", 1);
    fillPath(fog, null, FOG_COLOUR, whole);
    fog.globalCompositeOperation = "source-over";
    var smooth = smoothCanvas.getContext("2d");
    smooth.globalCompositeOperation = "copy";
    smooth.imageSmoothingEnabled = true;
    smooth.drawImage(fogCanvas, 0, 0, smoothCanvas.width, smoothCanvas.height);
    smooth.globalCompositeOperation = "source-over";
    ctx.save();
    ctx.imageSmoothingEnabled = false;
    ctx.globalAlpha = FOG_ALPHA;
    ctx.drawImage(smoothCanvas, area.x, area.y, area.w, area.h);
    ctx.restore();
    return true;
  }

  // Sets a small canvas to draw in map units over `area`, with `operation` and `alpha`.
  function begin(c, area, operation, alpha) {
    c.setTransform(1, 0, 0, 1, -area.x, -area.y);
    c.globalCompositeOperation = operation;
    c.globalAlpha = alpha;
  }

  // Fills `points` (a view), or the whole `rect` without it with
  // "evenodd", or only `rect` when points is null.
  function fillPath(c, points, style, rect, rule) {
    c.beginPath();
    if (rect) c.rect(rect.x, rect.y, rect.w, rect.h);
    if (points) trace(c, points);
    c.fillStyle = style;
    c.fill(rule || "nonzero");
  }

  // Copies the canvas `from` onto the context `c`, replacing what it held.
  function copyInto(c, from, area) {
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.globalCompositeOperation = "copy";
    c.globalAlpha = 1;
    c.drawImage(from, 0, 0);
    begin(c, area, "source-over", 1);
  }

  function clip(ctx, points) {
    ctx.beginPath();
    trace(ctx, points);
    ctx.clip();
  }

  Game.world.vision = { rangeOf: rangeOf, boundary: boundary, darken: darken, darkenSoftly: darkenSoftly, clip: clip,
    sightPoints: sightPoints, SAMPLE_RADIUS: SAMPLE_RADIUS, FADE_FROM: FADE_FROM };
})();
