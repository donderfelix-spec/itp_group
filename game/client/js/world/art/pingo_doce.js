// The art of Pingo Doce (M2-1.4): shelves full of products, the
// self-checkout with its baskets, turnstile gates, refrigerated shelves, the
// round fruit stand with separate produce baskets and the bakery counter.
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
  var OUTLINE = util.OUTLINE;

  // ---- Shelves ---------------------------------------------------------

  // A free-standing shelf seen from above: products on both of its long
  // sides, a spine in the middle, and its front end facing the aisle.
  art.kinds.shelf = function (ctx, shelf) {
    util.shadowBelow(ctx, shelf.x + 1, shelf.y + shelf.h, shelf.w - 2, 1.4);
    util.box(ctx, shelf.x, shelf.y, shelf.w, shelf.h, 1.2, "#ECE9E2", 1);
    var middle = shelf.x + shelf.w / 2;
    // Leave the last 8 units free for the sign at the front end.
    var top = shelf.y + 1.6;
    var bottom = shelf.y + shelf.h - 8;
    var side = (shelf.w - 4.4) / 2;
    productRows(ctx, shelf.x + 1.4, top, side, bottom - top, shelf.id, 0);
    productRows(ctx, middle + 0.8, top, side, bottom - top, shelf.id, 2);
    util.line(ctx, middle, shelf.y + 1, middle, shelf.y + shelf.h - 1, "#B9B4AA", 0.8);
    // The front end seen from the south: a darker band.
    util.box(ctx, shelf.x + 0.5, shelf.y + shelf.h - 2.2, shelf.w - 1, 1.7, 0.6, "#CFCAC0", 0);
  };

  // Fewer, larger products make each aisle readable at the normal camera zoom.
  function productRows(ctx, x, y, width, height, shelfId, offset) {
    var rowHeight = 8;
    for (var row = 0; (row + 1) * rowHeight <= height; row++) {
      var top = y + row * rowHeight;
      if (shelfId === "pingo-doce-shelf-1") {
        candy(ctx, x, top, width, rowHeight - 0.8, row + offset);
      } else if (shelfId === "pingo-doce-shelf-2") {
        drink(ctx, x, top, width, rowHeight - 0.8, row + offset);
      } else if (shelfId === "pingo-doce-shelf-3") {
        pizza(ctx, x, top, width, rowHeight - 0.8, row + offset);
      } else {
        pantry(ctx, x, top, width, rowHeight - 0.8, row + offset);
      }
      util.line(ctx, x, top + rowHeight - 0.2, x + width, top + rowHeight - 0.2, "#AAA69E", 0.4);
    }
  }

  // Generic drinks with plain labels: no brand names and no brand colours,
  // because only the campus's own shops are named on the map (DESIGN.md).
  function drink(ctx, x, y, w, h, variant) {
    var colours = ["#A42F2C", "#B8732E", "#E8762F", "#B89A22"];
    var labels = ["COLA", "ICE TEA", "ORANGE", "LEMON"];
    var i = variant % 6;
    if (i >= 4) {
      // A slim energy can and a sparkling-water can, without copied logos.
      var can = i === 4 ? "#6A4A9C" : "#D6E9EF";
      util.box(ctx, x + w * 0.25, y + 0.5, w * 0.5, h - 0.9, 0.7, can, 0.4);
      util.ellipse(ctx, x + w / 2, y + 0.7, w * 0.24, 0.45, "#B9C0C5", 0.2);
      util.line(ctx, x + w * 0.44, y + 0.7, x + w * 0.55, y + 0.7, "#5A6268", 0.3);
      util.text(ctx, i === 4 ? "ENERGY" : "WATER", x + w / 2, y + h * 0.57, 1, i === 4 ? "#FFE08A" : "#488AAB", w * 0.46);
      util.line(ctx, x + w * 0.31, y + 1.6, x + w * 0.31, y + h - 1.2, "rgba(255,255,255,0.45)", 0.3);
      return;
    }
    var left = x + w * 0.22;
    var width = w * 0.56;
    util.box(ctx, left + width * 0.24, y + 0.1, width * 0.52, h * 0.23, 0.3, colours[i], 0.3);
    util.box(ctx, left, y + h * 0.2, width, h * 0.76, 0.9, i < 2 ? "#563529" : colours[i], 0.35);
    util.box(ctx, left, y + h * 0.43, width, h * 0.32, 0.2, colours[i], 0);
    util.text(ctx, labels[i], x + w / 2, y + h * 0.6, 1.1, "#FFFFFF", width - 0.3);
    util.line(ctx, left + 0.6, y + h * 0.28, left + 0.6, y + h * 0.85, "rgba(255,255,255,0.5)", 0.4);
  }

  function candy(ctx, x, y, w, h, variant) {
    if (variant % 4 === 0) {
      // A foil wrapper peeled back from a segmented chocolate bar.
      util.box(ctx, x + 0.5, y + 0.4, w - 1, h - 0.8, 0.4, "#8F4B86", 0.4);
      util.box(ctx, x + 1, y + 0.8, w - 2, h * 0.57, 0.2, "#6D3D27", 0.3);
      for (var col = 0; col < 2; col++) {
        for (var row = 0; row < 2; row++) {
          util.box(ctx, x + 1.4 + col * (w - 2.8) / 2, y + 1.2 + row * 1.5,
            (w - 3.4) / 2, 1.1, 0.15, "#A26B43", 0);
        }
      }
      util.line(ctx, x + 0.8, y + h * 0.67, x + w - 0.8, y + h * 0.67, "#ECE5DC", 0.7);
    } else if (variant % 4 === 1) {
      // Two cookies with chocolate chips in a folded paper sleeve.
      util.box(ctx, x + 0.5, y + 0.4, w - 1, h - 0.8, 0.5, "#F1D0A2", 0.3);
      [0.35, 0.65].forEach(function (share, index) {
        var cx = x + w * share;
        var cy = y + h * (index ? 0.64 : 0.37);
        util.circle(ctx, cx, cy, 1.6, "#D6A263", 0.3);
        [[-0.5, -0.3], [0.6, -0.1], [0.1, 0.7]].forEach(function (chip) {
          util.circle(ctx, cx + chip[0], cy + chip[1], 0.25, "#65402D", 0);
        });
      });
    } else if (variant % 4 === 2) {
      // Lollipops on white sticks, with a small coloured spiral.
      [0.3, 0.7].forEach(function (share, index) {
        var cx = x + w * share;
        var cy = y + h * (index ? 0.47 : 0.3);
        util.line(ctx, cx, cy, cx, y + h - 0.4, "#D9D4CB", 0.6);
        util.circle(ctx, cx, cy, 1.6, index ? "#E9A8CC" : "#E88758", 0.3);
        ctx.beginPath();
        ctx.arc(cx, cy, 0.85, 0.4, Math.PI * 1.8);
        ctx.strokeStyle = "#FFF5DC";
        ctx.lineWidth = 0.45;
        ctx.stroke();
      });
    } else {
      // Wrapped sweets: a centre and folded ends, distinct from bottles.
      ["#9B72C1", "#DB7184", "#69AAB0"].forEach(function (colour, index) {
        var cy = y + 1.5 + index * 2;
        util.box(ctx, x + 2, cy - 0.65, w - 4, 1.3, 0.5, colour, 0.25);
        util.line(ctx, x + 1, cy - 0.6, x + 2, cy, colour, 0.7);
        util.line(ctx, x + w - 2, cy, x + w - 1, cy + 0.6, colour, 0.7);
      });
    }
  }

  function pantry(ctx, x, y, w, h, variant) {
    var look = variant % 4;
    if (look === 0) {
      // Pasta strands through the window of a blue packet.
      util.box(ctx, x + 0.5, y + 0.4, w - 1, h - 0.8, 0.4, "#386693", 0.3);
      util.box(ctx, x + 1.2, y + 1.3, w - 2.4, h - 2.2, 0.2, "#EDD19A", 0);
      for (var strand = 0; strand < 5; strand++) {
        var sx = x + 1.7 + strand * (w - 3.4) / 4;
        util.line(ctx, sx, y + 1.7, sx, y + h - 1.3, "#BD8C3E", 0.3);
      }
    } else if (look === 1) {
      util.box(ctx, x + 0.7, y + 0.5, w - 1.4, h - 1, 0.7, "#F2E9CE", 0.4);
      util.box(ctx, x + 1, y + 0.7, w - 2, 1.2, 0.2, "#7F9A59", 0);
      for (var grain = 0; grain < 9; grain++) {
        util.ellipse(ctx, x + 1.8 + grain % 3 * 1.5, y + 2.6 + Math.floor(grain / 3), 0.45, 0.2, "#C8B999", 0);
      }
      util.text(ctx, "RICE", x + w / 2, y + h - 0.8, 1, "#6C784C", w - 2);
    } else if (look === 2) {
      [0.3, 0.7].forEach(function (share, index) {
        var cx = x + w * share;
        util.box(ctx, cx - 1.25, y + 1.2, 2.5, h - 2.1, 0.4, index ? "#77A760" : "#C65A43", 0.3);
        util.ellipse(ctx, cx, y + 1.3, 1.25, 0.5, "#D1D3CE", 0.25);
        util.line(ctx, cx - 0.4, y + 1.3, cx + 0.4, y + 1.3, "#7B827F", 0.3);
        util.circle(ctx, cx, y + h * 0.6, 0.7, index ? "#DDE3A0" : "#F1CF89", 0);
      });
    } else {
      util.ellipse(ctx, x + w / 2, y + h / 2, w * 0.36, h * 0.42, "#C48A4C", 0.4);
      [0.3, 0.5, 0.7].forEach(function (share) {
        util.line(ctx, x + w * 0.3, y + h * share + 0.5, x + w * 0.65, y + h * share - 0.5, "#F1D4A4", 0.7);
      });
    }
  }

  function pizza(ctx, x, y, w, h, variant) {
    util.box(ctx, x + 0.3, y + 0.3, w - 0.6, h - 0.6, 0.4,
      variant % 2 ? "#DCE9F5" : "#F4E7D0", 0.4);
    ctx.fillStyle = variant % 2 ? "#397E59" : "#B74438";
    ctx.fillRect(x + 0.6, y + 0.6, w - 1.2, 1);
    var radius = Math.min(w, h) * 0.32;
    var cx = x + w / 2;
    var cy = y + h * 0.59;
    util.circle(ctx, cx, cy, radius, "#D69B50", 0.3);
    util.circle(ctx, cx, cy, radius * 0.8, "#F6D376", 0);
    [[-0.4, -0.3], [0.4, -0.2], [0, 0.45]].forEach(function (spot, index) {
      var tx = cx + radius * spot[0];
      var ty = cy + radius * spot[1];
      if (variant % 3 === 0) {
        util.circle(ctx, tx, ty, radius * 0.2, "#BA4A3D", 0);
      } else if (variant % 3 === 1) {
        util.ellipse(ctx, tx, ty, radius * 0.25, radius * 0.14, "#EDE0C2", 0.2);
        util.line(ctx, tx, ty, tx, ty + radius * 0.22, "#B29E7D", 0.35);
      } else {
        util.ellipse(ctx, tx, ty, radius * 0.13, radius * 0.25, index % 2 ? "#49824D" : "#BE5A3F", 0);
      }
    });
    util.line(ctx, cx, cy, cx + radius * 0.8, cy + radius * 0.4, "#E8B85E", 0.25);
  }

  // ---- Refrigerated shelves --------------------------------------------

  // A long fridge against a wall: a dark frame, cold glass, shelves of
  // bottles, salads and packed meals, and a light strip on the side that
  // faces the room.
  art.kinds.fridge = function (ctx, fridge, room) {
    var upright = fridge.h >= fridge.w;
    util.box(ctx, fridge.x, fridge.y, fridge.w, fridge.h, 1, "#565E6E", 1);
    var inner = { x: fridge.x + 1.2, y: fridge.y + 1.2, w: fridge.w - 2.4, h: fridge.h - 2.4 };
    ctx.fillStyle = "#DDF0F7";
    ctx.fillRect(inner.x, inner.y, inner.w, inner.h);
    var long = upright ? inner.h : inner.w;
    var compartment = 8;
    for (var along = 0; along + compartment <= long + 0.01; along += compartment) {
      if (upright) {
        coldGoods(ctx, inner.x, inner.y + along, inner.w, compartment);
      } else {
        coldGoods(ctx, inner.x + along, inner.y, compartment, inner.h);
      }
    }
    glassShine(ctx, inner);
    lightStrip(ctx, fridge, inner, upright, room);
  };

  // What one compartment of a fridge holds.
  function coldGoods(ctx, x, y, w, h) {
    var look = Math.floor(util.noise(x * 1.3, y) * 5);
    var middleX = x + w / 2;
    var middleY = y + h / 2;
    if (look === 0) {
      drink(ctx, x, y, w, h, Math.floor(y / 8) % 4);
    } else if (look === 1) {
      pizza(ctx, x, y, w, h, Math.floor(y / 8) % 2);
    } else if (look === 2) {
      // Milk carton with its folded blue top and a white front.
      util.box(ctx, x + w * 0.2, y + 0.8, w * 0.6, h - 1.6, 0.3, "#FFFFFF", 0.4);
      util.box(ctx, x + w * 0.2, y + 0.8, w * 0.6, 1.4, 0.2, "#76B9DB", 0);
      util.text(ctx, "MILK", middleX, middleY + 0.8, 1.2, "#39799A", w * 0.5);
    } else if (look === 3) {
      util.box(ctx, x + 0.5, y + 0.6, w - 1, h - 1.2, 1, "#EAF6E0", 0.35);
      util.circle(ctx, middleX - 0.6, middleY, Math.min(w, h) * 0.2, "#79B84E", 0);
      util.circle(ctx, middleX + 0.7, middleY + 0.3, Math.min(w, h) * 0.16, "#A3D26B", 0);
      util.circle(ctx, middleX + 0.3, middleY - 0.6, 0.5, "#D96347", 0);
    } else {
      // Sandwich halves in a clear triangular-pack style tray.
      util.box(ctx, x + 0.5, y + 0.6, w - 1, h - 1.2, 0.6, "#EEF3ED", 0.35);
      [0.3, 0.65].forEach(function (share) {
        var left = x + w * share;
        ctx.beginPath();
        ctx.moveTo(left, y + 1.5);
        ctx.lineTo(left + w * 0.26, y + h - 1.5);
        ctx.lineTo(left, y + h - 1.5);
        ctx.closePath();
        ctx.fillStyle = "#E4B879";
        ctx.fill();
        util.line(ctx, left + 0.4, y + h - 2.1, left + w * 0.19, y + h - 2.1, "#69A150", 0.55);
      });
    }
    // The edge of the shelf below the goods.
    ctx.fillStyle = "rgba(91, 100, 117, 0.35)";
    if (w < h) {
      ctx.fillRect(x, y + h - 0.4, w, 0.4);
    } else {
      ctx.fillRect(x, y + h - 0.4, w, 0.4);
    }
  }

  // White streaks on the glass.
  function glassShine(ctx, inner) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(inner.x, inner.y, inner.w, inner.h);
    ctx.clip();
    ctx.strokeStyle = "rgba(255, 255, 255, 0.7)";
    ctx.lineWidth = 0.5;
    var step = 14;
    var start = inner.y - inner.w;
    for (var y = start; y < inner.y + inner.h; y += step) {
      ctx.beginPath();
      ctx.moveTo(inner.x, y + inner.w);
      ctx.lineTo(inner.x + inner.w, y);
      ctx.stroke();
    }
    ctx.restore();
  }

  // The cold blue light along the open side of the fridge, with door
  // handles. The open side is the one further from the room's nearest wall.
  function lightStrip(ctx, fridge, inner, upright, room) {
    ctx.fillStyle = "#8FD8F2";
    if (upright) {
      var nearLeftWall = !room || fridge.x - room.x < room.x + room.w - (fridge.x + fridge.w);
      var stripX = nearLeftWall ? fridge.x + fridge.w - 1.1 : fridge.x + 0.3;
      ctx.fillRect(stripX, fridge.y + 1.5, 0.8, fridge.h - 3);
      for (var y = fridge.y + 9; y < fridge.y + fridge.h - 4; y += 18) {
        util.line(ctx, stripX + 0.4, y, stripX + 0.4, y + 4, OUTLINE, 0.6);
      }
    } else {
      ctx.fillRect(fridge.x + 1.5, fridge.y + fridge.h - 1.1, fridge.w - 3, 0.8);
    }
  }

  // ---- The self-checkout -----------------------------------------------

  // A row of black self-checkout pillars with screens, and a stack of
  // shopping baskets at the left end.
  art.kinds.checkout = function (ctx, checkout) {
    var basketWidth = Math.min(11, checkout.w * 0.22);
    baskets(ctx, checkout.x, checkout.y, basketWidth, checkout.h);
    var left = checkout.x + basketWidth + 1;
    var pillars = 3;
    var pillarWidth = (checkout.x + checkout.w - left) / pillars;
    for (var i = 0; i < pillars; i++) {
      pillar(ctx, left + i * pillarWidth + 0.5, checkout.y, pillarWidth - 1, checkout.h);
    }
  };

  function pillar(ctx, x, y, w, h) {
    util.shadowBelow(ctx, x + 0.5, y + h, w - 1, 1.2);
    util.box(ctx, x, y, w, h, 1.4, "#2F2C38", 1);
    // Raised register display with item lines, total, and a separate card reader.
    util.box(ctx, x + 1, y + 1, w * 0.59, h * 0.36, 0.6, "#101D27", 0.4);
    util.box(ctx, x + 1.6, y + 1.6, w * 0.59 - 1.2, h * 0.36 - 1.2, 0.3, "#B4DFE0", 0);
    for (var row = 0; row < 3; row++) {
      util.line(ctx, x + 2.2, y + 2.3 + row, x + w * 0.5, y + 2.3 + row, "#427D80", 0.3);
    }
    util.box(ctx, x + w * 0.73, y + 1.6, w * 0.2, h * 0.31, 0.4, "#1A252C", 0.3);
    util.box(ctx, x + w * 0.76, y + 2, w * 0.14, 1.5, 0.2, "#69BE9A", 0);
    for (var key = 0; key < 6; key++) {
      util.circle(ctx, x + w * (0.77 + key % 2 * 0.1), y + 4 + Math.floor(key / 2) * 0.65, 0.18, "#CAD1D4", 0);
    }
    // Red scan line in a dark glass window, receipt emerging beside it.
    util.box(ctx, x + 1.2, y + h * 0.48, w * 0.45, h * 0.35, 0.5, "#182934", 0.4);
    util.line(ctx, x + 1.6, y + h * 0.65, x + w * 0.5, y + h * 0.65, "#F56F62", 0.6);
    util.box(ctx, x + w * 0.17, y + h * 0.82, w * 0.23, h * 0.13, 0.1, "#FFF9E9", 0.2);
    // Steel bagging tray and a paper shopping bag with handles.
    util.box(ctx, x + w * 0.61, y + h * 0.48, w * 0.32, h * 0.45, 0.5, "#B9C0C2", 0.3);
    util.box(ctx, x + w * 0.66, y + h * 0.62, w * 0.22, h * 0.25, 0.3, "#C9A16C", 0.3);
    util.box(ctx, x + w * 0.71, y + h * 0.55, w * 0.12, h * 0.14, 0.5, null, 0.4, "#8C693F");
  }

  // A stack of grey baskets seen from above: three rims, a mesh, handles.
  function baskets(ctx, x, y, w, h) {
    util.shadowBelow(ctx, x + 0.5, y + h, w - 1, 1.2);
    for (var i = 2; i >= 0; i--) {
      util.box(ctx, x + i * 0.4, y + i * 0.6, w - i * 0.8, h - i * 0.9, 1.2, i === 0 ? "#9AA0AB" : "#7F8592", 0.7);
    }
    var inner = { x: x + 1.6, y: y + 1.8, w: w - 3.2, h: h - 3.6 };
    util.box(ctx, inner.x, inner.y, inner.w, inner.h, 0.6, "#6E7480", 0);
    for (var meshX = inner.x + 1.2; meshX < inner.x + inner.w; meshX += 1.2) {
      util.line(ctx, meshX, inner.y, meshX, inner.y + inner.h, "#8C929D", 0.3);
    }
    util.line(ctx, x + w * 0.3, y + 0.8, x + w * 0.3, y + h - 0.8, "#3E4350", 0.6);
    util.line(ctx, x + w * 0.7, y + 0.8, x + w * 0.7, y + h - 0.8, "#3E4350", 0.6);
  }

  // ---- Turnstile gates -------------------------------------------------

  // A silver gate post with a green arrow light and its two glass wings,
  // folded open along the passage (at most 2 units past the post).
  art.kinds.turnstile = function (ctx, post) {
    var wingTop = post.y + post.h * 0.3;
    var wingHeight = post.h * 0.45;
    ctx.fillStyle = "rgba(156, 211, 230, 0.65)";
    ctx.strokeStyle = "#4F8AA6";
    ctx.lineWidth = 0.4;
    [post.x - 2, post.x + post.w].forEach(function (wingX) {
      ctx.beginPath();
      ctx.rect(wingX, wingTop, 2, wingHeight);
      ctx.fill();
      ctx.stroke();
    });
    util.shadowBelow(ctx, post.x, post.y + post.h, post.w, 1.2);
    util.box(ctx, post.x, post.y, post.w, post.h, 1, "#CBD1DA", 0.8);
    util.box(ctx, post.x + 0.7, post.y + 0.7, post.w - 1.4, post.h * 0.4, 0.5, "#EEF1F5", 0);
    // Point towards the north exit, not merely a round status lamp.
    var cx = post.x + post.w / 2;
    var cy = post.y + post.h * 0.7;
    util.line(ctx, cx, cy + 1.3, cx, cy - 1.3, "#238B51", 0.7);
    util.line(ctx, cx - 0.8, cy - 0.4, cx, cy - 1.3, "#238B51", 0.7);
    util.line(ctx, cx + 0.8, cy - 0.4, cx, cy - 1.3, "#238B51", 0.7);
  };

  // ---- The fruit stand -------------------------------------------------

  // Produce in separate baskets, leaving every item visible without a tree.
  art.kinds["fruit-stand"] = function (ctx, stand) {
    var x = stand.x + stand.w / 2;
    var y = stand.y + stand.h / 2;
    var radius = Math.min(stand.w, stand.h) / 2;
    util.ellipse(ctx, x, y + radius * 0.25, radius, radius * 0.92, "rgba(46, 42, 59, 0.12)", 0);
    tiledBase(ctx, x, y, radius);
    for (var i = 0; i < 6; i++) {
      var angle = i / 6 * Math.PI * 2;
      basket(ctx, x + Math.cos(angle) * radius * 0.63,
        y + Math.sin(angle) * radius * 0.63, radius * 0.29, i % 3);
    }
    util.box(ctx, x - 5, y - 3, 10, 6, 0.5, "#315F3E", 0.4);
    util.text(ctx, "FRESH", x, y - 1.2, 1.8, "#FFF6D8", 9);
    util.text(ctx, "FRUITS", x, y + 1.2, 1.8, "#FFF6D8", 9);
  };

  function tiledBase(ctx, x, y, radius) {
    util.circle(ctx, x, y, radius, "#FFFFFF", 1);
    var pieces = 16;
    for (var i = 0; i < pieces; i += 2) {
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.arc(x, y, radius - 0.5, i / pieces * Math.PI * 2, (i + 1) / pieces * Math.PI * 2);
      ctx.closePath();
      ctx.fillStyle = "#3E9B5B";
      ctx.fill();
    }
    util.circle(ctx, x, y, radius * 0.82, "#E8F3E4", 0.6);
  }

  function basket(ctx, x, y, radius, kind) {
    util.circle(ctx, x, y, radius, "#C9935A", 0.7);
    util.circle(ctx, x, y, radius * 0.8, "#A8743F", 0);
    if (kind === 1) {
      // Curving banana bunch, with dark tips and a shared brown stem.
      for (var banana = 0; banana < 3; banana++) {
        var bx = x - radius * 0.55 + banana * radius * 0.35;
        ctx.beginPath();
        ctx.moveTo(bx, y - radius * 0.5);
        ctx.quadraticCurveTo(bx - radius * 0.35, y + radius * 0.55, bx + radius * 0.5, y + radius * 0.5);
        ctx.quadraticCurveTo(bx, y + radius * 0.12, bx, y - radius * 0.5);
        ctx.fillStyle = "#F2CE4C";
        ctx.fill();
        ctx.strokeStyle = "#B59438";
        ctx.lineWidth = 0.3;
        ctx.stroke();
        util.circle(ctx, bx, y - radius * 0.5, 0.35, "#745838", 0);
      }
    } else {
      [[-0.32, -0.28], [0.35, -0.2], [0, 0.38]].forEach(function (spot) {
        var fx = x + spot[0] * radius;
        var fy = y + spot[1] * radius;
        var size = radius * 0.33;
        if (kind === 0) {
          // Two lobes, a stalk and a leaf distinguish apples from balls.
          util.ellipse(ctx, fx - size * 0.25, fy, size * 0.7, size, "#D65742", 0.25);
          util.ellipse(ctx, fx + size * 0.25, fy, size * 0.7, size, "#E36A4A", 0);
          util.line(ctx, fx, fy - size * 0.7, fx + 0.2, fy - size * 1.2, "#63492F", 0.4);
          util.ellipse(ctx, fx + 0.7, fy - size * 0.8, 0.7, 0.3, "#568346", 0);
        } else {
          util.ellipse(ctx, fx, fy, size, size * 0.82, "#967142", 0.3);
          util.ellipse(ctx, fx, fy, size * 0.82, size * 0.65, "#A3C85C", 0);
          util.ellipse(ctx, fx, fy, size * 0.28, size * 0.22, "#F4EAC5", 0);
          for (var seed = 0; seed < 8; seed++) {
            var angle = seed / 8 * Math.PI * 2;
            util.circle(ctx, fx + Math.cos(angle) * size * 0.52, fy + Math.sin(angle) * size * 0.4, 0.15, "#534832", 0);
          }
        }
      });
    }
  }

  // ---- The bakery and hot-food counter ---------------------------------

  // Against the wall: a front clad in yellow patterned tiles, a steel top
  // with a glass case of pastries and bread, and trays of hot food.
  art.kinds["hot-counter"] = function (ctx, counter) {
    util.box(ctx, counter.x, counter.y, counter.w, counter.h, 1, "#C9CED6", 1);
    yellowTiles(ctx, counter.x + 0.5, counter.y + 0.5, counter.w - 1, 3.4);
    var caseLeft = counter.x + 12;
    var caseWidth = counter.w * 0.45;
    pastryCase(ctx, caseLeft, counter.y + 4.6, caseWidth, counter.h - 6);
    hotTrays(ctx, caseLeft + caseWidth + 2, counter.y + 4.6, counter.x + counter.w - caseLeft - caseWidth - 4, counter.h - 6);
  };

  function yellowTiles(ctx, x, y, w, h) {
    ctx.fillStyle = "#F4C542";
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = "#FFF4CC";
    for (var tileX = x + h / 2; tileX < x + w; tileX += h) {
      ctx.beginPath();
      ctx.moveTo(tileX, y + 0.5);
      ctx.lineTo(tileX + h / 2 - 0.5, y + h / 2);
      ctx.lineTo(tileX, y + h - 0.5);
      ctx.lineTo(tileX - h / 2 + 0.5, y + h / 2);
      ctx.closePath();
      ctx.fill();
    }
    util.line(ctx, x, y + h, x + w, y + h, OUTLINE, 0.5);
  }

  function pastryCase(ctx, x, y, w, h) {
    util.box(ctx, x, y, w, h, 0.6, "#E9F4F8", 0.5);
    var spacing = 4.2;
    for (var itemX = x + 2.6; itemX < x + w - 2.4; itemX += spacing) {
      var look = Math.floor(util.noise(itemX, y) * 3);
      if (look === 0) {
        croissant(ctx, itemX, y + h / 2);
      } else if (look === 1) {
        util.ellipse(ctx, itemX, y + h / 2, 1.7, 1.1, "#B9773D", 0.4); // a bread roll
        util.line(ctx, itemX - 0.8, y + h / 2 - 0.3, itemX + 0.8, y + h / 2 + 0.3, "#E6B47A", 0.35);
      } else {
        util.circle(ctx, itemX, y + h / 2, 1.4, "#F6D36B", 0.4); // a custard tart
        util.circle(ctx, itemX, y + h / 2, 0.6, "#C47A2C", 0);
      }
    }
    ctx.fillStyle = "rgba(255, 255, 255, 0.6)";
    ctx.fillRect(x + 0.6, y + 0.5, w - 1.2, 0.5);
  }

  function croissant(ctx, x, y) {
    ctx.beginPath();
    ctx.arc(x, y + 0.9, 1.7, Math.PI * 1.1, Math.PI * 1.9);
    ctx.strokeStyle = "#D08A3C";
    ctx.lineWidth = 1.3;
    ctx.stroke();
  }

  function hotTrays(ctx, x, y, w, h) {
    var trays = 3;
    var trayWidth = w / trays;
    var foods = ["#E07B39", "#C9493B", "#D9B25A"];
    for (var i = 0; i < trays; i++) {
      util.box(ctx, x + i * trayWidth + 0.3, y, trayWidth - 0.6, h, 0.5, "#9EA5B0", 0.4);
      util.box(ctx, x + i * trayWidth + 1, y + 0.7, trayWidth - 2, h - 1.4, 0.8, foods[i % foods.length], 0);
    }
  }

  // ---- Sign totems -----------------------------------------------------

  // An upright digital sign on a small dark foot, seen from the front: a
  // bright screen with a white line drawing. Its `icon` says which drawing:
  // "basket" (on bright green) or "cup" (on light blue).
  art.kinds.totem = function (ctx, totem) {
    var cup = totem.icon === "cup";
    util.shadowBelow(ctx, totem.x, totem.y + totem.h, totem.w, 1.2);
    util.box(ctx, totem.x + 0.6, totem.y + totem.h - 1.8, totem.w - 1.2, 1.8, 0.5, "#2F2C38", 0.6);
    util.box(ctx, totem.x, totem.y, totem.w, totem.h - 1.4, 0.8, OUTLINE, 0);
    var screen = { x: totem.x + 0.6, y: totem.y + 0.6, w: totem.w - 1.2, h: totem.h - 2.6 };
    util.box(ctx, screen.x, screen.y, screen.w, screen.h, 0.5, cup ? "#7CC7EC" : "#58C23A", 0);
    ctx.strokeStyle = "#FFFFFF";
    ctx.lineWidth = 0.4;
    ctx.lineJoin = "round";
    var middleX = screen.x + screen.w / 2;
    var middleY = screen.y + screen.h / 2;
    var size = Math.min(screen.w, screen.h) * 0.36;
    ctx.beginPath();
    if (cup) {
      // A cup with a handle and a curl of steam.
      ctx.rect(middleX - size, middleY - size * 0.2, size * 1.6, size * 1.2);
      ctx.moveTo(middleX + size * 0.6, middleY + size * 0.1);
      ctx.arc(middleX + size * 0.8, middleY + size * 0.4, size * 0.3, -Math.PI / 2, Math.PI / 2);
      ctx.moveTo(middleX - size * 0.2, middleY - size * 0.5);
      ctx.quadraticCurveTo(middleX + size * 0.2, middleY - size * 0.9, middleX - size * 0.1, middleY - size * 1.3);
    } else {
      // A shopping basket: the basket, a handle and two lines of mesh.
      ctx.moveTo(middleX - size, middleY - size * 0.1);
      ctx.lineTo(middleX + size, middleY - size * 0.1);
      ctx.lineTo(middleX + size * 0.7, middleY + size);
      ctx.lineTo(middleX - size * 0.7, middleY + size);
      ctx.closePath();
      ctx.moveTo(middleX - size * 0.6, middleY - size * 0.1);
      ctx.arc(middleX, middleY - size * 0.1, size * 0.6, Math.PI, 0);
      ctx.moveTo(middleX - size * 0.2, middleY - size * 0.1);
      ctx.lineTo(middleX - size * 0.15, middleY + size);
      ctx.moveTo(middleX + size * 0.2, middleY - size * 0.1);
      ctx.lineTo(middleX + size * 0.15, middleY + size);
    }
    ctx.stroke();
  };

  // ---- Decor -----------------------------------------------------------

  // A small coffee machine standing on a counter, with two white cups.
  art.decor["coffee-machine"] = function (ctx, item) {
    util.box(ctx, item.x, item.y, item.w, item.h, 1, "#3A3646", 0.7);
    util.box(ctx, item.x + 1, item.y + 1, item.w - 2, item.h * 0.35, 0.5, "#C9CED6", 0);
    util.circle(ctx, item.x + item.w * 0.3, item.y + item.h * 0.7, Math.min(item.w, item.h) * 0.14, "#FFFFFF", 0.4);
    util.circle(ctx, item.x + item.w * 0.7, item.y + item.h * 0.7, Math.min(item.w, item.h) * 0.14, "#FFFFFF", 0.4);
  };
})();
