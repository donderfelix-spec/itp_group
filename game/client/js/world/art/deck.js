// The art of the Main Deck and the corridor (M2-1.4): the study tables on
// their terrace, leafy bushes, the hedge, benches, lamp posts, a bike rack,
// drains, the glass front, the beach with towels, parasols and surfboards
// and a surfboard rack; in the corridor a terrazzo floor with its name
// "Academic Hall", the taupe slat wall, ceiling lights, sofas, wire-grid
// dividers, a black column and stairs.
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

  // The study area uses the deck-pool map entry so its footprint stays
  // stable. The tables and chairs stand on a low wooden terrace as large as
  // the solid (M2-1.20, M2-1.21): the whole block that stops a player is
  // seen, also between the chairs.
  art.kinds.pool = function (ctx, area) {
    studyTerrace(ctx, area);
    var tableWidth = (area.w - 8) / 2;
    var tableDepth = area.h - 24;
    var top = area.y + 12;

    for (var table = 0; table < 2; table++) {
      var left = area.x + 2 + table * (tableWidth + 4);
      // Seats tuck under the two long sides, with the backrests facing out.
      for (var seat = 0; seat < 4; seat++) {
        var x = left + tableWidth * (seat + 0.5) / 4;
        util.chair(ctx, x, area.y + 7, 11, "#25262A", "up");
        util.chair(ctx, x, area.y + area.h - 7, 11, "#25262A", "down");
      }

      util.shadowBelow(ctx, left, top + tableDepth, tableWidth, 1.5);
      util.box(ctx, left, top, tableWidth, tableDepth, 2, TABLE_TOP, 1.1);
      util.line(ctx, left + 2, top + tableDepth - 2, left + tableWidth - 2,
        top + tableDepth - 2, "#F4F6F8", 0.7);

      // A laptop, an open notebook and a small plant on each table.
      var centre = left + tableWidth / 2;
      util.box(ctx, centre - 18, top + 7, 10, 6, 1, "#676B74", 0.6);
      util.box(ctx, centre - 18, top + 6, 10, 3, 0.7, "#B7D6E4", 0.6);
      util.box(ctx, centre + 9, top + tableDepth - 11, 11, 7, 0.8, "#FFF1D1", 0.6);
      util.line(ctx, centre + 14.5, top + tableDepth - 10, centre + 14.5,
        top + tableDepth - 5, "#BAA881", 0.6);
      util.circle(ctx, centre, top + tableDepth / 2, 3.2, "#BF8262", 0.6);
      util.ellipse(ctx, centre - 0.5, top + tableDepth / 2 - 0.8, 2.4, 1.8, "#6E9C61", 0.5);
    }
  };

  // The top of a study table: a pale grey-white laminate. Pure white would
  // differ from the light paving by only about 50 (red + green + blue), so
  // the drawing check (6 of 16 pixels differing by more than 60) would count
  // the tables as not drawn; this grey differs by about 75.
  var TABLE_TOP = "#CFD6DE";

  // A low terrace of pale wooden boards, its outline just inside the solid,
  // with a lighter back edge and a darker front edge, like the plinth of
  // the NOVA sign: a raised platform, not a mark on the paving.
  function studyTerrace(ctx, area) {
    var lineWidth = 0.9;
    var inset = lineWidth / 2;
    util.box(ctx, area.x + inset, area.y + inset, area.w - lineWidth, area.h - lineWidth,
      2, "#D2B48C", lineWidth);
    // The joints between the boards run along the terrace.
    util.strokeAll(ctx, "#B8976C", 0.4, function () {
      for (var y = area.y + 4; y < area.y + area.h - 2; y += 4) {
        ctx.moveTo(area.x + 1.5, y);
        ctx.lineTo(area.x + area.w - 1.5, y);
      }
    });
    util.line(ctx, area.x + 2, area.y + 1.6, area.x + area.w - 2, area.y + 1.6, "#E6D2B0", 0.8);
    ctx.fillStyle = "rgba(46, 42, 59, 0.14)";
    ctx.fillRect(area.x + 1, area.y + area.h - 3, area.w - 2, 2.1);
  }

  // A deck bush is trimmed square (M2-1.20): its crown fills its solid to
  // the corners, so that what is drawn is what blocks. Its ground shadow is
  // the band along the bottom of the solid, below the crown.
  art.kinds.tree = function (ctx, bush) {
    var x = bush.x + bush.w / 2;
    var y = bush.y + bush.h / 2;
    var radius = Math.min(bush.w, bush.h) / 2;
    util.box(ctx, x - radius * 0.98, y + radius * 0.55, radius * 1.96, radius * 0.43,
      radius * 0.12, "rgba(46, 42, 59, 0.22)", 0);
    leafyCrown(ctx, x, y, radius, bush.x + bush.y, true);
  };

  // How far a square crown reaches at `angle`, for a radius of 1: the edge
  // of a square with rounded corners (a "superellipse"), with small lobes
  // that stay inside it (at most 0.99 of the way: 13.86 of a bush's 14).
  function squareReach(angle, phase) {
    var roundness = 7; // 2 is a circle; the larger, the closer to a square
    var edge = Math.pow(Math.pow(Math.abs(Math.cos(angle)), roundness)
      + Math.pow(Math.abs(Math.sin(angle)), roundness), -1 / roundness);
    return edge * (0.965 + 0.025 * Math.cos(angle * 9 + phase));
  }

  // The outline of the low foliage, for a radius of 1. Round: lobed and a
  // little flattened. Square: the trimmed square, lifted a little so that
  // the ground shadow shows below it (top at -0.97, bottom at 0.85).
  function crownPath(ctx, phase, square) {
    ctx.beginPath();
    for (var edge = 0; edge < 48; edge++) {
      var angle = edge / 48 * Math.PI * 2;
      var px;
      var py;
      if (square) {
        var squareEdge = squareReach(angle, phase);
        px = Math.cos(angle) * squareEdge;
        py = Math.sin(angle) * squareEdge * 0.92 - 0.06;
      } else {
        var reach = 0.82 + 0.06 * Math.cos(angle * 7 + phase) + 0.035 * Math.sin(angle * 11);
        var depth = Math.sin(angle);
        px = Math.cos(angle) * reach * (1 + Math.max(0, depth) * 0.13);
        py = depth * reach * 0.82 - 0.025;
      }
      if (edge === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
  }

  var shadowLeaves = ["#29401D", "#3B5325", "#4F682A", "#657C33"];
  var sunlitLeaves = ["#4E6828", "#66832E", "#7C983B", "#99AE49", "#B6C75B"];

  function bushLeaf(ctx, x, y, angle, length, colour) {
    var dx = Math.cos(angle) * length;
    var dy = Math.sin(angle) * length;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.quadraticCurveTo(x + dx * 0.32 - dy * 0.46, y + dy * 0.32 + dx * 0.46, x + dx, y + dy);
    ctx.quadraticCurveTo(x + dx * 0.58 + dy * 0.32, y + dy * 0.58 - dx * 0.32, x, y);
    ctx.fillStyle = colour;
    ctx.fill();
  }

  // Shoots and small leaves on low foliage, after Hanna's reference photo.
  // `square` trims the crown to the square around it and keeps every leaf
  // inside it (the deck bushes); without it the crown is round (the hedge).
  function leafyCrown(ctx, x, y, radius, seed, square) {
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(radius, radius);

    // Low, compact foliage under the individual leaves and shoots.
    var phase = util.noise(seed, 4) * Math.PI * 2;
    crownPath(ctx, phase, square);
    ctx.fillStyle = "#2D421F";
    ctx.fill();
    // A square crown spreads its leaves further, into its corners; the
    // clip cuts off whatever would reach past the trimmed edge.
    var spread = 1;
    if (square) {
      ctx.clip();
      spread = 1.25;
    }

    // Fan thin shoots out of the base. Alternating leaves follow each stem.
    for (var shoot = 0; shoot < 12; shoot++) {
      var angle = -Math.PI + (shoot + 0.15 + util.noise(seed, shoot) * 0.7) / 12 * Math.PI;
      var reach = (0.75 + util.noise(shoot, seed) * 0.19) * spread;
      var tipX = Math.cos(angle) * reach;
      var tipY = Math.sin(angle) * reach * 0.83 - 0.04;
      var baseX = tipX * 0.2;
      var baseY = 0.58 + util.noise(seed + 12, shoot) * 0.13;
      var bend = (util.noise(seed + 20, shoot) - 0.5) * 0.64;
      var stemX = tipX - baseX;
      var stemY = tipY - baseY;
      ctx.beginPath();
      ctx.moveTo(baseX, baseY);
      ctx.quadraticCurveTo(baseX + stemX / 2 + bend / 2, baseY + stemY / 2, tipX, tipY);
      ctx.strokeStyle = shoot % 3 === 0 ? "#6B6043" : "#4D592E";
      ctx.lineWidth = 0.03;
      ctx.lineCap = "round";
      ctx.stroke();

      for (var leaf = 0; leaf < 6; leaf++) {
        var t = 0.28 + leaf * 0.132;
        var side = (leaf + shoot) % 2 ? -1 : 1;
        var leafX = baseX + stemX * t + bend * t * (1 - t);
        var leafY = baseY + stemY * t;
        var direction = Math.atan2(stemY, stemX + bend * (1 - 2 * t)) + side * 0.73;
        var size = 0.15 + util.noise(seed + shoot, leaf) * 0.12 - 0.09 * t;
        var palette = t > 0.67 ? sunlitLeaves : shadowLeaves;
        bushLeaf(ctx, leafX, leafY, direction, size, util.pick(palette, seed + leaf * 0.9, shoot + 21));
      }
    }

    // Smaller foreground leaves overlap into pockets of light and shade.
    for (var leaf = 0; leaf < 52; leaf++) {
      var angle = util.noise(seed + leaf, 31) * Math.PI * 2;
      var reach = Math.sqrt(util.noise(leaf * 1.9, seed)) * 0.75 * spread;
      var leafX = Math.cos(angle) * reach;
      var leafY = Math.sin(angle) * reach * 0.79 + 0.09;
      var size = 0.14 + util.noise(seed, leaf + 18) * 0.15;
      var palette = leafY < 0.1 || leaf % 5 === 0 ? sunlitLeaves : shadowLeaves;
      bushLeaf(ctx, leafX, leafY, angle - 0.6, size, util.pick(palette, leaf + 22, seed));
    }
    ctx.restore();
  }

  // Overlapping bush crowns form the hedge along its existing footprint.
  art.kinds.hedge = function (ctx, bed) {
    var radius = bed.h * 0.45;
    util.ellipse(ctx, bed.x + bed.w / 2, bed.y + bed.h * 0.8,
      bed.w * 0.43, bed.h * 0.085, "rgba(46, 42, 59, 0.18)", 0);
    [0.18, 0.4, 0.62, 0.82].forEach(function (share, index) {
      var x = bed.x + bed.w * share;
      var y = bed.y + bed.h * (index % 2 ? 0.46 : 0.54);
      leafyCrown(ctx, x, y, radius * (index % 2 ? 1 : 0.94), bed.x + index * 7);
    });
  };

  // The hiding spot in the hedge (M3-1.5): a hollow in the foliage, dark
  // inside, with leaves hanging over its rim. The hedge is walkable (S-98).
  // Registered as "spot" for the deck, the place without a room.
  var HOLLOW_LEAVES = 16;

  art.hiding.spot = function (ctx, spot) {
    var x = spot.x;
    var y = spot.y;
    var r = spot.r;
    var hollow = ctx.createRadialGradient(x, y + r * 0.15, 0, x, y, r);
    hollow.addColorStop(0, "rgba(20, 29, 13, 0.95)");
    hollow.addColorStop(0.55, "rgba(29, 44, 20, 0.78)");
    hollow.addColorStop(1, "rgba(41, 64, 29, 0)");
    util.ellipse(ctx, x, y, r, r * 0.9, hollow, 0);
    for (var i = 0; i < HOLLOW_LEAVES; i++) {
      var angle = (i + util.noise(x, i) * 0.6) / HOLLOW_LEAVES * Math.PI * 2;
      var reach = r * (0.72 + util.noise(i, y) * 0.18);
      var leafX = x + Math.cos(angle) * reach;
      var leafY = y + Math.sin(angle) * reach * 0.9;
      var length = r * (0.2 + util.noise(y, i) * 0.12);
      var palette = Math.sin(angle) < 0 ? sunlitLeaves : shadowLeaves;
      bushLeaf(ctx, leafX, leafY, angle + Math.PI + (util.noise(i, x) - 0.5) * 0.8, length, util.pick(palette, i, x));
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

  // The size of the room names and of "Main Deck" (drawRoomNames in draw.js).
  var NAME_SIZE = 13;

  // Lettering: on the floor, a name in the game's ink, like the room names
  // (the corridor's "Academic Hall": Felix, 2026-11-22, wanted it in black
  // on the floor); on a wall, raised white letters with a little shadow.
  art.decor.lettering = function (ctx, item) {
    if (!item.text) {
      return;
    }
    if (item.layer === "floor") {
      util.text(ctx, item.text, item.x + item.w / 2, item.y + item.h / 2, NAME_SIZE, util.OUTLINE, item.w);
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
    logoPlinth(ctx, logo);
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

  // The flat stone plinth the letters stand on, as large as the logo's
  // solid (M2-1.20): the whole block that stops a player is seen. Its
  // outline lies just inside the solid.
  function logoPlinth(ctx, logo) {
    var lineWidth = 0.8;
    var inset = lineWidth / 2;
    util.box(ctx, logo.x + inset, logo.y + inset, logo.w - lineWidth, logo.h - lineWidth, 2, "#D6CEBD", lineWidth);
    // A lighter top edge and a darker front edge: a low block, not a mark on the floor.
    util.line(ctx, logo.x + 2, logo.y + 1.6, logo.x + logo.w - 2, logo.y + 1.6, "#F4F0E7", 0.8);
    ctx.fillStyle = "rgba(46, 42, 59, 0.14)";
    ctx.fillRect(logo.x + 1, logo.y + logo.h - 3, logo.w - 2, 2.2);
  }

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
