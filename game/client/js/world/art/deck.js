// The art of the Main Deck and the corridor (M2-1.4): the reflecting pool
// with its stone edge, a step and reflections, young trees with gravel beds,
// the hedge, benches, lamp posts, a bike rack, drains, the glass front, the
// beach with towels, parasols and surfboards and a surfboard rack; in the
// corridor a terrazzo floor, the taupe slat wall with "ACADEMIC HALL",
// ceiling lights, sofas, wire-grid dividers, a black column and stairs.
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

  // The shallow pool: a light stone edge, a step down into the water, the
  // tiles of the bottom, reflections of the sky and the trees, and ripples.
  art.kinds.pool = function (ctx, pool) {
    util.box(ctx, pool.x, pool.y, pool.w, pool.h, 3, "#E6E0D2", 1.4);
    // The joints of the stone edge.
    util.strokeAll(ctx, "#CFC7B6", 0.4, function () {
      for (var joint = pool.x + 12; joint < pool.x + pool.w - 4; joint += 12) {
        ctx.moveTo(joint, pool.y + 0.6);
        ctx.lineTo(joint, pool.y + 3);
        ctx.moveTo(joint, pool.y + pool.h - 3);
        ctx.lineTo(joint, pool.y + pool.h - 0.6);
      }
    });
    var edge = 3;
    var water = { x: pool.x + edge, y: pool.y + edge, w: pool.w - 2 * edge, h: pool.h - 2 * edge };
    util.box(ctx, water.x, water.y, water.w, water.h, 1.5, "#9CD3E6", 0.8);
    ctx.save();
    util.roundedPath(ctx, water.x, water.y, water.w, water.h, 1.5);
    ctx.clip();
    // The step: a lighter band just inside the edge, where the water is shallow.
    ctx.strokeStyle = "rgba(255, 255, 255, 0.45)";
    ctx.lineWidth = 3;
    ctx.strokeRect(water.x + 1.5, water.y + 1.5, water.w - 3, water.h - 3);
    ctx.strokeStyle = "rgba(46, 42, 59, 0.12)";
    ctx.lineWidth = 0.5;
    ctx.strokeRect(water.x + 3, water.y + 3, water.w - 6, water.h - 6);
    // The tiles on the bottom of the pool, faint through the water.
    util.strokeAll(ctx, "rgba(255, 255, 255, 0.22)", 0.4, function () {
      for (var x = water.x + 8; x < water.x + water.w; x += 8) {
        ctx.moveTo(x, water.y);
        ctx.lineTo(x, water.y + water.h);
      }
      for (var y = water.y + 8; y < water.y + water.h; y += 8) {
        ctx.moveTo(water.x, y);
        ctx.lineTo(water.x + water.w, y);
      }
    });
    // Reflections: a pale patch of sky and the dark green of a tree.
    util.ellipse(ctx, water.x + water.w * 0.7, water.y + water.h * 0.35, water.w * 0.14, water.h * 0.16, "rgba(255, 255, 255, 0.35)", 0);
    util.ellipse(ctx, water.x + water.w * 0.12, water.y + water.h * 0.7, water.w * 0.07, water.h * 0.2, "rgba(78, 150, 89, 0.25)", 0);
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

  // A young tree: a gravel bed, and above it a round crown of leaves with
  // volume, its shadow falling on the paving.
  art.kinds.tree = function (ctx, bed) {
    util.box(ctx, bed.x, bed.y, bed.w, bed.h, 2, "#D9D2C2", 1);
    ctx.fillStyle = "#B8AE98";
    for (var i = 0; i < 26; i++) {
      var x = bed.x + 2 + util.noise(bed.x + i, bed.y) * (bed.w - 4);
      var y = bed.y + 2 + util.noise(bed.y, bed.x + i * 1.7) * (bed.h - 4);
      ctx.fillRect(x, y, 0.8, 0.8);
    }
    util.circle(ctx, bed.x + bed.w / 2, bed.y + bed.h / 2 + 2, 2, "#7A5434", 0.6); // the trunk
    // The crown reaches at most about 1 unit past its bed (the drawings of a tile reach 4).
    util.foliage(ctx, bed.x + bed.w / 2, bed.y + bed.h / 2 - 2, bed.w * 0.4, util.LEAVES, 7);
  };

  // The hedge, drawn as a planted green bed of campus landscaping: lawn in a
  // low stone border, three rounded shrubs with volume and a few flowers.
  art.kinds.hedge = function (ctx, bed) {
    util.shadowBelow(ctx, bed.x + 2, bed.y + bed.h, bed.w - 4, 1.6);
    util.box(ctx, bed.x, bed.y, bed.w, bed.h, 4, "#D9D2C2", 1.2);
    util.box(ctx, bed.x + 2.2, bed.y + 2.2, bed.w - 4.4, bed.h - 4.4, 3, "#8CC56F", 0.6);
    // Short strokes of grass.
    util.strokeAll(ctx, "#76B05C", 0.4, function () {
      for (var i = 0; i < 24; i++) {
        var x = bed.x + 4 + util.noise(i, bed.x) * (bed.w - 8);
        var y = bed.y + 4 + util.noise(bed.y, i) * (bed.h - 8);
        ctx.moveTo(x, y);
        ctx.lineTo(x + 0.5, y - 1.2);
      }
    });
    var flowers = ["#F2695C", "#F2C53D", "#FFFFFF", "#E8A0B4"];
    for (var f = 0; f < 10; f++) {
      var fx = bed.x + 5 + util.noise(f * 3.1, bed.y) * (bed.w - 10);
      var fy = bed.y + bed.h * 0.65 + util.noise(bed.x, f * 1.7) * (bed.h * 0.2);
      util.circle(ctx, fx, fy, 0.9, flowers[f % flowers.length], 0.3);
    }
    var radius = bed.h * 0.3;
    [0.2, 0.5, 0.8].forEach(function (share, index) {
      util.foliage(ctx, bed.x + bed.w * share, bed.y + bed.h * (index === 1 ? 0.42 : 0.5), radius * (index === 1 ? 1.15 : 1), util.LEAVES, 6);
    });
  };

  // ---- The glass front and the beach -----------------------------------

  // The glass front to the beach: panes in light frames with posts, and
  // glints on the glass.
  art.kinds.glass = function (ctx, glass) {
    util.box(ctx, glass.x, glass.y, glass.w, glass.h, 1.5, "#E4E8EE", 1.4);
    var panes = Math.max(1, Math.round(glass.w / 30));
    var pane = glass.w / panes;
    for (var i = 0; i < panes; i++) {
      var left = glass.x + i * pane;
      util.box(ctx, left + 1.4, glass.y + 1.6, pane - 2.8, glass.h - 3.2, 0.3, "#8FD0EC", 0);
      util.line(ctx, left + pane * 0.3, glass.y + glass.h - 2, left + pane * 0.42, glass.y + 2, "rgba(255, 255, 255, 0.9)", 0.8);
      util.line(ctx, left + pane * 0.48, glass.y + glass.h - 2, left + pane * 0.54, glass.y + 4, "rgba(255, 255, 255, 0.7)", 0.6);
      if (i > 0) {
        util.box(ctx, left - 1, glass.y, 2, glass.h, 0.4, "#9AA1AC", 0.5);
      }
    }
  };

  // A beach towel with stripes.
  art.decor.towel = function (ctx, item) {
    var colour = item.colour || "#F2695C";
    util.box(ctx, item.x, item.y, item.w, item.h, 0.6, colour, 0.6);
    ctx.fillStyle = "#FFFFFF";
    for (var x = item.x + 2; x < item.x + item.w - 1; x += 4) {
      ctx.fillRect(x, item.y + 0.6, 1.4, item.h - 1.2);
    }
  };

  // A parasol seen from above: coloured and white segments around a tip.
  art.decor.parasol = function (ctx, item) {
    var x = item.x + item.w / 2;
    var y = item.y + item.h / 2;
    var radius = Math.min(item.w, item.h) / 2;
    util.ellipse(ctx, x + 2, y + 2.5, radius, radius * 0.7, "rgba(46, 42, 59, 0.15)", 0);
    var pieces = 8;
    for (var i = 0; i < pieces; i++) {
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.arc(x, y, radius, i / pieces * Math.PI * 2, (i + 1) / pieces * Math.PI * 2);
      ctx.closePath();
      ctx.fillStyle = i % 2 === 0 ? (item.colour || "#F2C53D") : "#FFFFFF";
      ctx.fill();
    }
    util.circle(ctx, x, y, radius, null, 0.8);
    util.circle(ctx, x, y, 0.9, "#9B6B45", 0);
  };

  // A surfboard lying on the sand.
  art.decor.surfboard = function (ctx, item) {
    surfboard(ctx, item.x + item.w / 2, item.y + item.h / 2, item.w / 2, item.h / 2, item.colour || "#4FC1C1", false);
  };

  function surfboard(ctx, x, y, halfLength, halfWidth, colour, upright) {
    ctx.beginPath();
    if (upright) {
      ctx.ellipse(x, y, halfWidth, halfLength, 0, 0, Math.PI * 2);
    } else {
      ctx.ellipse(x, y, halfLength, halfWidth, 0, 0, Math.PI * 2);
    }
    ctx.fillStyle = colour;
    ctx.fill();
    ctx.strokeStyle = util.OUTLINE;
    ctx.lineWidth = 0.6;
    ctx.stroke();
    if (upright) {
      util.line(ctx, x, y - halfLength * 0.8, x, y + halfLength * 0.8, "#FFFFFF", 0.4);
    } else {
      util.line(ctx, x - halfLength * 0.8, y, x + halfLength * 0.8, y, "#FFFFFF", 0.4);
    }
  }

  // A low wooden rack near "Catch the wave" with surfboards lying on it,
  // each longer than a person is tall.
  art.kinds["surfboard-rack"] = function (ctx, rack) {
    util.shadowBelow(ctx, rack.x + 1, rack.y + rack.h, rack.w - 2, 1.4);
    util.box(ctx, rack.x, rack.y, rack.w, rack.h, 1, "#C99662", 0.9);
    util.strokeAll(ctx, "#9B6B45", 0.5, function () {
      ctx.moveTo(rack.x + rack.w * 0.2, rack.y + 1);
      ctx.lineTo(rack.x + rack.w * 0.2, rack.y + rack.h - 1);
      ctx.moveTo(rack.x + rack.w * 0.8, rack.y + 1);
      ctx.lineTo(rack.x + rack.w * 0.8, rack.y + rack.h - 1);
    });
    var colours = ["#F2695C", "#4FC1C1"];
    var lane = rack.h / colours.length;
    colours.forEach(function (colour, index) {
      surfboard(ctx, rack.x + rack.w / 2, rack.y + lane * (index + 0.5), rack.w / 2 - 1.2, lane / 2 - 1, colour, false);
    });
  };

  // ---- Fittings of the deck --------------------------------------------

  // A wooden bench for two: slats on a dark frame.
  art.kinds["deck-bench"] = function (ctx, bench) {
    util.shadowBelow(ctx, bench.x + 1, bench.y + bench.h, bench.w - 2, 1.4);
    util.box(ctx, bench.x, bench.y, bench.w, bench.h, 1, "#C99662", 0.9);
    util.strokeAll(ctx, "#9B6B45", 0.4, function () {
      for (var y = bench.y + bench.h / 3; y < bench.y + bench.h - 0.5; y += bench.h / 3) {
        ctx.moveTo(bench.x + 0.8, y);
        ctx.lineTo(bench.x + bench.w - 0.8, y);
      }
    });
    ctx.fillStyle = "#3A3646";
    ctx.fillRect(bench.x + 2, bench.y + bench.h - 0.9, 1.6, 0.9);
    ctx.fillRect(bench.x + bench.w - 3.6, bench.y + bench.h - 0.9, 1.6, 0.9);
  };

  // A lamp post: a dark foot, and its round lamp with a soft light around.
  art.kinds["lamp-post"] = function (ctx, lamp) {
    var x = lamp.x + lamp.w / 2;
    var y = lamp.y + lamp.h / 2;
    var glow = ctx.createRadialGradient(x, y, 0, x, y, 9);
    glow.addColorStop(0, "rgba(255, 244, 200, 0.35)");
    glow.addColorStop(1, "rgba(255, 244, 200, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(x - 9, y - 9, 18, 18);
    util.circle(ctx, x + 0.6, y + 1.2, lamp.w * 0.5, "rgba(46, 42, 59, 0.18)", 0);
    util.circle(ctx, x, y, lamp.w * 0.5, "#3A3646", 0.6);
    util.circle(ctx, x, y, lamp.w * 0.25, "#FFF1B8", 0);
  };

  // A bike rack against a wall: a steel rail, and bikes parked in it, seen
  // from above (two wheels, the frame, the handlebar).
  art.kinds["bike-rack"] = function (ctx, rack) {
    util.box(ctx, rack.x, rack.y, 2, rack.h, 0.6, "#9AA1AC", 0.6);
    var colours = ["#E8574B", "#4C8FD6", "#5FA86B"];
    var lane = rack.h / colours.length;
    colours.forEach(function (colour, index) {
      var y = rack.y + lane * (index + 0.5);
      var wheel = Math.min(lane * 0.42, rack.w * 0.22);
      util.ellipse(ctx, rack.x + 2.5 + wheel, y, wheel, wheel * 0.35, "#3A3646", 0.5);
      util.ellipse(ctx, rack.x + rack.w - 0.5 - wheel, y, wheel, wheel * 0.35, "#3A3646", 0.5);
      util.line(ctx, rack.x + 2.5 + wheel, y, rack.x + rack.w - 0.5 - wheel, y, colour, 1.4);
      util.line(ctx, rack.x + rack.w - 0.5 - wheel, y - wheel * 0.9, rack.x + rack.w - 0.5 - wheel, y + wheel * 0.9, util.OUTLINE, 0.8);
    });
  };

  // A gravel bed around a tree's bed, with small plants.
  art.decor["gravel-ring"] = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 3, "#E0D9C9", 0.5, "#CFC7B6");
    var plants = ["#5FA86B", "#7DBE7A", "#E8A0B4"];
    for (var i = 0; i < 12; i++) {
      var angle = i / 12 * Math.PI * 2;
      var x = item.x + item.w / 2 + Math.cos(angle) * item.w * 0.44;
      var y = item.y + item.h / 2 + Math.sin(angle) * item.h * 0.44;
      util.circle(ctx, x, y, 1.1, util.pick(plants, i, item.x), 0.3);
    }
  };

  // A drain: a thin dark grate in the paving.
  art.decor.drain = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 0.4, "#B9B2A3", 0.4);
    util.strokeAll(ctx, "#8E887B", 0.3, function () {
      for (var x = item.x + 1.5; x < item.x + item.w; x += 1.5) {
        ctx.moveTo(x, item.y + 0.3);
        ctx.lineTo(x, item.y + item.h - 0.3);
      }
    });
  };

  // ---- The corridor ----------------------------------------------------

  // The polished terrazzo floor: beige with fine dark speckles (the
  // "speckled" floor pattern in this colour), and a brass edge to the deck.
  art.decor.terrazzo = function (ctx, item) {
    ctx.beginPath();
    ctx.rect(item.x, item.y, item.w, item.h);
    ctx.clip();
    var colour = item.colour || "#E6D9C3";
    ctx.fillStyle = colour;
    ctx.fillRect(item.x, item.y, item.w, item.h);
    art.floors.speckled(ctx, item, { floor: colour });
    ctx.fillStyle = "#C9A96A";
    ctx.fillRect(item.x, item.y + item.h - 0.8, item.w, 0.8);
  };

  // The corridor side of the buildings: a taupe wall of narrow horizontal slats.
  art.faces["taupe-slats"] = function (ctx, band) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(band.x, band.y, band.w, band.h);
    ctx.clip();
    ctx.fillStyle = "#A8998A";
    ctx.fillRect(band.x, band.y, band.w, band.h);
    util.strokeAll(ctx, "#8C7E70", 0.35, function () {
      for (var y = band.y + 1.3; y < band.y + band.h; y += 1.3) {
        ctx.moveTo(band.x, y);
        ctx.lineTo(band.x + band.w, y);
      }
    });
    ctx.fillStyle = "rgba(46, 42, 59, 0.18)";
    ctx.fillRect(band.x, band.y, band.w, 1);
    ctx.restore();
    util.shadowBelow(ctx, band.x, band.y + band.h, band.w, 1.6);
    util.line(ctx, band.x, band.y + band.h, band.x + band.w, band.y + band.h, util.OUTLINE, 0.8);
  };

  // Raised white letters on the slat wall, with a little shadow.
  art.decor.lettering = function (ctx, item) {
    if (!item.text) {
      return;
    }
    var size = item.h * 0.62;
    var x = item.x + item.w / 2;
    var y = item.y + item.h / 2 + 0.2;
    util.text(ctx, item.text, x + 0.3, y + 0.4, size, "rgba(46, 42, 59, 0.35)", item.w);
    util.text(ctx, item.text, x, y, size, "#FFFFFF", item.w);
  };

  // A dark grey sofa against the wall: a back, two arms and two cushions.
  art.kinds.sofa = function (ctx, sofa) {
    util.shadowBelow(ctx, sofa.x + 1, sofa.y + sofa.h, sofa.w - 2, 1.4);
    util.box(ctx, sofa.x, sofa.y, sofa.w, sofa.h, 1.6, "#5A5767", 1);
    util.box(ctx, sofa.x + 0.8, sofa.y + 0.6, sofa.w - 1.6, sofa.h * 0.32, 1, "#4A4756", 0); // the back
    var arm = 3;
    var cushion = (sofa.w - 2 * arm - 1) / 2;
    for (var i = 0; i < 2; i++) {
      util.box(ctx, sofa.x + arm + 0.5 + i * (cushion + 0.5), sofa.y + sofa.h * 0.36, cushion, sofa.h * 0.56, 1, "#6E6B7B", 0.5);
    }
  };

  // A room divider of white wire-grid cubes with orange-brown chipboard
  // panels, and a plant on top.
  art.kinds["cube-divider"] = function (ctx, divider) {
    util.shadowBelow(ctx, divider.x, divider.y + divider.h, divider.w, 1.2);
    var cube = divider.h;
    var cubes = Math.max(1, Math.round(divider.w / cube));
    var size = divider.w / cubes;
    for (var i = 0; i < cubes; i++) {
      var x = divider.x + i * size;
      if (i % 2 === 1) {
        util.box(ctx, x + 0.4, divider.y + 0.4, size - 0.8, cube - 0.8, 0.3, "#C99A62", 0); // chipboard
        ctx.fillStyle = "#B5844E";
        ctx.fillRect(x + 1.5, divider.y + 2, 1.2, 0.6);
        ctx.fillRect(x + size - 3, divider.y + cube - 2.6, 1.4, 0.6);
      }
    }
    util.strokeAll(ctx, "#FFFFFF", 0.7, function () {
      ctx.rect(divider.x + 0.3, divider.y + 0.3, divider.w - 0.6, cube - 0.6);
      for (var line = 1; line < cubes; line++) {
        ctx.moveTo(divider.x + line * size, divider.y);
        ctx.lineTo(divider.x + line * size, divider.y + cube);
      }
    });
    util.strokeAll(ctx, util.OUTLINE, 0.35, function () {
      ctx.rect(divider.x, divider.y, divider.w, cube);
    });
    var plantX = divider.x + size / 2;
    util.foliage(ctx, plantX, divider.y + cube / 2 - 0.5, cube * 0.42, util.LEAVES, 5);
  };

  // A black square column.
  art.kinds["black-column"] = function (ctx, column) {
    util.shadowBelow(ctx, column.x, column.y + column.h, column.w, 2);
    util.box(ctx, column.x, column.y, column.w, column.h, 0.6, "#2F2C38", 0.8);
    ctx.fillStyle = "#4A4560";
    ctx.fillRect(column.x + 1, column.y + 1, column.w * 0.35, column.h - 2);
  };

  // A white staircase going up: steps with dark edges, a handrail.
  art.kinds.staircase = function (ctx, stairs) {
    util.box(ctx, stairs.x, stairs.y, stairs.w, stairs.h, 0.6, "#F4F3EE", 1);
    var steps = 9;
    var depth = stairs.h / steps;
    for (var i = 0; i < steps; i++) {
      var y = stairs.y + i * depth;
      // Further up the stairs (towards the top) the steps get lighter.
      ctx.fillStyle = "rgba(46, 42, 59, " + (0.02 + 0.012 * i) + ")";
      ctx.fillRect(stairs.x + 0.5, y, stairs.w - 1, depth);
      util.line(ctx, stairs.x + 0.5, y + depth, stairs.x + stairs.w - 0.5, y + depth, "#B9BCC4", 0.5);
    }
    util.line(ctx, stairs.x + stairs.w - 1.6, stairs.y + 1, stairs.x + stairs.w - 1.6, stairs.y + stairs.h - 1, util.OUTLINE, 0.7);
  };

  // ---- The NOVA sign ---------------------------------------------------

  var NAVY = "#1E2A4A";

  // The word NOVA set into the paving: N, V and A as heavy capitals; the O
  // as in the school's sign, a thick ring (its stroke about as thick as its
  // hole is wide) raised above a short bar of the same thickness, ring and
  // bar together as tall as the capitals.
  art.kinds.logo = function (ctx, logo) {
    var size = logo.h * 1.25;
    var font = function () { return "900 " + size + "px system-ui, sans-serif"; };
    ctx.font = font();
    var measure = function (letter) {
      var width = typeof ctx.measureText === "function" ? ctx.measureText(letter).width : NaN;
      return typeof width === "number" && isFinite(width) ? width : size * 0.7;
    };
    var capital = size * 0.72; // the height of a capital letter
    var gap = size * 0.06;
    var widths = { N: measure("N"), V: measure("V"), A: measure("A") };
    var ringWidth = capital * 6 / 9; // the ring is 6 of 9 parts of the height
    var total = widths.N + ringWidth + widths.V + widths.A + 3 * gap;
    if (total > logo.w) {
      var shrink = logo.w / total;
      size *= shrink;
      capital *= shrink;
      gap *= shrink;
      ringWidth *= shrink;
      widths = { N: widths.N * shrink, V: widths.V * shrink, A: widths.A * shrink };
      total = logo.w;
      ctx.font = font();
    }
    var baseline = logo.y + (logo.h + capital) / 2;
    var x = logo.x + (logo.w - total) / 2;
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
    var letter = function (text) {
      ctx.fillStyle = "rgba(255, 255, 255, 0.8)";
      ctx.fillText(text, x - 0.5, baseline - 0.6);
      ctx.fillStyle = NAVY;
      ctx.fillText(text, x, baseline);
      x += widths[text] + gap;
    };
    letter("N");
    ringAndBar(ctx, x, baseline - capital, ringWidth, capital);
    x += ringWidth + gap;
    letter("V");
    letter("A");
  };

  // The O: nine parts of the height are the ring (6: a hole of 2 and a
  // stroke of 2 on each side), a gap (1) and the bar (2).
  function ringAndBar(ctx, left, top, width, height) {
    var part = height / 9;
    var middleX = left + width / 2;
    var ringY = top + 3 * part;
    ctx.beginPath();
    ctx.arc(middleX, ringY, 3 * part, 0, Math.PI * 2);
    ctx.moveTo(middleX + part, ringY);
    ctx.arc(middleX, ringY, part, 0, Math.PI * 2, true);
    ctx.fillStyle = NAVY;
    ctx.fill("evenodd");
    ctx.fillRect(left, top + 7 * part, width, 2 * part);
  }

  // ---- The doors from the corridor to the deck ------------------------

  // A wide opening in the wall between the corridor and the deck (the
  // entry's rectangle is the opening in the wall line): a threshold between
  // metal sills, dark posts at both ends, and glass leaves standing open
  // flat on the wall's face on the deck side. "deck-door-one-leaf" has only
  // the leaf on its left: its right end meets the deck's outer wall.
  function deckDoor(ctx, item, leaves) {
    var faceHeight = 8;
    var leafWidth = 12;
    ctx.fillStyle = "#E6E0D4";
    ctx.fillRect(item.x, item.y, item.w, item.h);
    ctx.fillStyle = "#C3C7CF";
    ctx.fillRect(item.x, item.y, item.w, 0.8);
    ctx.fillRect(item.x, item.y + item.h - 0.8, item.w, 0.8);
    var faceTop = item.y + item.h;
    var places = leaves === 2 ? [item.x - 1.5 - leafWidth, item.x + item.w + 1.5] : [item.x - 1.5 - leafWidth];
    places.forEach(function (leafX, index) {
      util.box(ctx, leafX, faceTop + 0.4, leafWidth, faceHeight - 0.9, 0.4, "rgba(170, 216, 234, 0.7)", 0.5);
      ctx.strokeStyle = "#E4E8EE";
      ctx.lineWidth = 0.6;
      ctx.strokeRect(leafX + 0.6, faceTop + 1, leafWidth - 1.2, faceHeight - 2.1);
      util.line(ctx, leafX + 2, faceTop + faceHeight - 1.4, leafX + 4.5, faceTop + 1.8, "rgba(255, 255, 255, 0.9)", 0.5);
      var handleX = index === 0 ? leafX + leafWidth - 1.6 : leafX + 1.6;
      util.line(ctx, handleX, faceTop + faceHeight * 0.35, handleX, faceTop + faceHeight * 0.7, util.OUTLINE, 0.6);
    });
    var posts = leaves === 2 ? [item.x - 1.5, item.x + item.w - 1.5] : [item.x - 1.5];
    posts.forEach(function (postX) {
      util.box(ctx, postX, item.y - 1, 3, item.h + faceHeight + 1, 0.6, "#4A4560", 0.6);
    });
  }

  art.decor["deck-door"] = function (ctx, item) {
    deckDoor(ctx, item, 2);
  };

  art.decor["deck-door-one-leaf"] = function (ctx, item) {
    deckDoor(ctx, item, 1);
  };

  // The leaves stand 13.5 units beside the opening and the posts reach 8
  // below it, past DRAWING_OVERHANG of draw.js.
  art.decor["deck-door"].reach = 14;
  art.decor["deck-door-one-leaf"].reach = 14;
})();
