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

  // The hedge: a row of leafy clumps with volume, inside its rectangle.
  art.kinds.hedge = function (ctx, hedge) {
    util.box(ctx, hedge.x + 1, hedge.y + hedge.h * 0.35, hedge.w - 2, hedge.h * 0.6, 4, "#3F7F4E", 1.2);
    var radius = hedge.h * 0.42;
    var count = Math.max(2, Math.round((hedge.w - radius) / (radius * 1.3)));
    var step = (hedge.w - 2 * radius) / (count - 1);
    for (var i = 0; i < count; i++) {
      var x = hedge.x + radius + i * step;
      var y = hedge.y + hedge.h / 2 + (i % 2 === 0 ? -1 : 1);
      util.foliage(ctx, x, y, radius, util.LEAVES, 5);
    }
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

  // A rack of surfboards standing upright, near "Catch the wave".
  art.kinds["surfboard-rack"] = function (ctx, rack) {
    util.shadowBelow(ctx, rack.x, rack.y + rack.h, rack.w, 1);
    util.box(ctx, rack.x, rack.y + rack.h - 3, rack.w, 3, 0.6, "#9B6B45", 0.7);
    var colours = ["#F2695C", "#4FC1C1", "#F2C53D", "#FFFFFF"];
    var boards = colours.length;
    var spacing = rack.w / boards;
    colours.forEach(function (colour, index) {
      surfboard(ctx, rack.x + spacing * (index + 0.5), rack.y + rack.h / 2 - 1, rack.h / 2 - 1, spacing * 0.36, colour, true);
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

  // A bike rack against a wall, with two bikes.
  art.kinds["bike-rack"] = function (ctx, rack) {
    util.box(ctx, rack.x, rack.y, rack.w, rack.h, 0.6, "#C3C7CF", 0.6);
    var colours = ["#E8574B", "#4C8FD6"];
    colours.forEach(function (colour, index) {
      var y = rack.y + rack.h * (index + 1) / 3;
      util.circle(ctx, rack.x + 2, y, 1.6, null, 0.5);
      util.circle(ctx, rack.x + rack.w - 1.4, y, 1.6, null, 0.5);
      util.line(ctx, rack.x + 2, y, rack.x + rack.w - 1.4, y, colour, 0.9);
      util.line(ctx, rack.x + rack.w - 2.4, y - 1.6, rack.x + rack.w - 0.8, y - 1.6, util.OUTLINE, 0.6);
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

  // The word NOVA in heavy geometric capitals, set into the paving: dark
  // letters with a light edge where the paving meets them, and below them a
  // smaller line with the school's name.
  art.kinds.logo = function (ctx, logo) {
    var wordHeight = logo.h * 0.72;
    var x = logo.x + logo.w / 2;
    var wordY = logo.y + wordHeight / 2;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    var size = wordHeight * 1.32;
    ctx.font = "900 " + size + "px system-ui, sans-serif";
    if (typeof ctx.measureText === "function") {
      var width = ctx.measureText("NOVA").width;
      if (typeof width === "number" && width > logo.w) {
        size = size * logo.w / width;
        ctx.font = "900 " + size + "px system-ui, sans-serif";
      }
    }
    ctx.fillStyle = "rgba(255, 255, 255, 0.8)";
    ctx.fillText("NOVA", x - 0.5, wordY - 0.6);
    ctx.fillStyle = util.OUTLINE;
    ctx.fillText("NOVA", x, wordY);
    util.text(ctx, "School of Business & Economics", x, logo.y + logo.h * 0.88, logo.h * 0.16, util.OUTLINE, logo.w * 0.95);
  };
})();
