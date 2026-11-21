// The art of Pingo Doce (M2-1.4): shelves full of products, the
// self-checkout with its baskets, turnstile gates, refrigerated shelves, the
// round fruit stand with the olive tree and the bakery counter.
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

  // The colours of the packs, bottles and boxes on the shelves.
  var PRODUCT_COLOURS = ["#E8574B", "#F2C53D", "#4C8FD6", "#F08A3C", "#6DB65B", "#FFFFFF", "#9B6BC9", "#C98B5A"];
  // Bottle caps: no white, a white ring reads as a letter O from afar.
  var CAP_COLOURS = ["#E8574B", "#F2C53D", "#4C8FD6", "#F08A3C", "#6DB65B", "#9B6BC9"];

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
    productRows(ctx, shelf.x + 1.4, top, side, bottom - top);
    productRows(ctx, middle + 0.8, top, side, bottom - top);
    util.line(ctx, middle, shelf.y + 1, middle, shelf.y + shelf.h - 1, "#B9B4AA", 0.8);
    // The front end seen from the south: a darker band.
    util.box(ctx, shelf.x + 0.5, shelf.y + shelf.h - 2.2, shelf.w - 1, 1.7, 0.6, "#CFCAC0", 0);
  };

  // Rows of products in one strip: packs, pairs of bottles or jars.
  function productRows(ctx, x, y, width, height) {
    var rowHeight = 3.3;
    for (var rowY = y; rowY + rowHeight <= y + height + 0.01; rowY += rowHeight) {
      var colour = util.pick(PRODUCT_COLOURS, x, rowY);
      var look = util.noise(rowY, x);
      if (look < 0.45) {
        util.box(ctx, x, rowY + 0.3, width, rowHeight - 0.6, 0.5, colour, 0.35);
        ctx.fillStyle = "rgba(255, 255, 255, 0.55)";
        ctx.fillRect(x + 0.6, rowY + 0.8, width * 0.35, 0.6);
      } else if (look < 0.8) {
        // Three bottles side by side, seen from above: a cap and a shine.
        colour = util.pick(CAP_COLOURS, x, rowY);
        var radius = Math.min(width / 6, rowHeight / 2) - 0.1;
        for (var bottle = 0; bottle < 3; bottle++) {
          var bottleX = x + width * (bottle * 2 + 1) / 6;
          util.circle(ctx, bottleX, rowY + rowHeight / 2, radius, colour, 0.3);
          util.circle(ctx, bottleX - radius * 0.3, rowY + rowHeight / 2 - radius * 0.3, radius * 0.3, "rgba(255, 255, 255, 0.75)", 0);
        }
      } else {
        util.box(ctx, x + 0.3, rowY + 0.4, width - 0.6, rowHeight - 0.8, 1, "#F6EEDC", 0.35);
        ctx.fillStyle = colour;
        ctx.fillRect(x + 0.6, rowY + rowHeight / 2 - 0.5, width - 1.2, 1);
      }
    }
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
    var compartment = 5.2;
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
    var look = util.noise(x * 1.3, y);
    var middleX = x + w / 2;
    var middleY = y + h / 2;
    if (look < 0.4) {
      // Bottles: coloured caps seen from above.
      var colour = util.pick(CAP_COLOURS, x, y);
      var capRadius = Math.min(w, h) * 0.17;
      [-0.25, 0.25].forEach(function (offset) {
        util.circle(ctx, middleX + w * offset, middleY, capRadius, colour, 0.3);
        util.circle(ctx, middleX + w * offset - capRadius * 0.3, middleY - capRadius * 0.3, capRadius * 0.35, "rgba(255, 255, 255, 0.75)", 0);
      });
    } else if (look < 0.7) {
      // A salad bowl: green leaves under a clear lid.
      util.box(ctx, x + 0.5, y + 0.6, w - 1, h - 1.2, 1, "#EAF6E0", 0.35);
      util.circle(ctx, middleX - 0.6, middleY, Math.min(w, h) * 0.2, "#79B84E", 0);
      util.circle(ctx, middleX + 0.7, middleY + 0.3, Math.min(w, h) * 0.16, "#A3D26B", 0);
    } else {
      // A packed meal: a white tray with a coloured label.
      util.box(ctx, x + 0.5, y + 0.6, w - 1, h - 1.2, 0.6, "#FFFFFF", 0.35);
      ctx.fillStyle = util.pick(["#F08A3C", "#E8574B", "#C98B5A"], y, x);
      ctx.fillRect(x + 1, middleY - 0.5, w - 2, 1);
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
    // The screen, glowing, and the scanner below it.
    util.box(ctx, x + 1.5, y + 1.4, w - 3, h * 0.42, 0.6, "#8FD3F0", 0.4, "#141218");
    ctx.fillStyle = "rgba(255, 255, 255, 0.6)";
    ctx.fillRect(x + 2.2, y + 2.1, (w - 3) * 0.45, 0.6);
    util.box(ctx, x + 2, y + h * 0.62, w - 4, h * 0.22, 0.5, "#5A5767", 0);
    util.circle(ctx, x + w - 2, y + h * 0.73, 0.6, "#5FD38A", 0);
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
    util.circle(ctx, post.x + post.w / 2, post.y + post.h * 0.72, Math.min(post.w, post.h) * 0.2, "#4CD07D", 0.3);
  };

  // ---- The fruit stand -------------------------------------------------

  // Round: a base of green-and-white tiles, wicker baskets full of red and
  // green apples and oranges, and a small olive tree in the middle.
  art.kinds["fruit-stand"] = function (ctx, stand) {
    var x = stand.x + stand.w / 2;
    var y = stand.y + stand.h / 2;
    var radius = Math.min(stand.w, stand.h) / 2;
    util.ellipse(ctx, x, y + radius * 0.25, radius, radius * 0.92, "rgba(46, 42, 59, 0.12)", 0);
    tiledBase(ctx, x, y, radius);
    var fruits = ["#E5483C", "#8CC63F", "#F39A2B"];
    var basketCount = 6;
    for (var i = 0; i < basketCount; i++) {
      // No basket straight below the middle: there the tree's pot shows.
      var angle = i / basketCount * Math.PI * 2;
      var basketX = x + Math.cos(angle) * radius * 0.68;
      var basketY = y + Math.sin(angle) * radius * 0.68;
      basket(ctx, basketX, basketY, radius * 0.24, fruits[i % fruits.length]);
    }
    oliveTree(ctx, x, y, radius);
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

  function basket(ctx, x, y, radius, fruitColour) {
    util.circle(ctx, x, y, radius, "#C9935A", 0.7);
    util.circle(ctx, x, y, radius * 0.72, "#A8743F", 0);
    var fruitRadius = radius * 0.3;
    var spots = [[0, 0], [-0.42, -0.3], [0.42, -0.3], [-0.38, 0.38], [0.38, 0.38]];
    spots.forEach(function (spot) {
      var fruitX = x + spot[0] * radius;
      var fruitY = y + spot[1] * radius;
      util.circle(ctx, fruitX, fruitY, fruitRadius, fruitColour, 0.3);
      util.circle(ctx, fruitX - fruitRadius * 0.35, fruitY - fruitRadius * 0.35, fruitRadius * 0.3, "rgba(255, 255, 255, 0.7)", 0);
    });
  }

  // The small olive tree in the middle of the stand, seen from the south:
  // a pot, a trunk with branches going up, and above them a grey-green crown
  // of leaves with one dark outline round it. `standRadius` is the stand's.
  function oliveTree(ctx, x, y, standRadius) {
    var crownX = x;
    var crownY = y - standRadius * 0.2;
    var crown = standRadius * 0.42;
    var potY = y + standRadius * 0.5;
    // Pot and trunk first: the crown covers the top of the trunk.
    util.ellipse(ctx, x, potY, standRadius * 0.17, standRadius * 0.12, "#B8643A", 0.6);
    util.line(ctx, x, potY, x, crownY + crown * 0.3, "#6B4A2E", 1.3);
    util.line(ctx, x, crownY + crown * 0.6, x - crown * 0.55, crownY + crown * 0.2, "#6B4A2E", 0.8);
    util.line(ctx, x, crownY + crown * 0.75, x + crown * 0.6, crownY + crown * 0.35, "#6B4A2E", 0.8);
    // The crown: grey-green olive leaves with volume, and a branch showing
    // through a gap in them.
    util.foliage(ctx, crownX, crownY, crown, util.OLIVE_LEAVES, 7);
    util.line(ctx, crownX - crown * 0.1, crownY + crown * 0.25, crownX - crown * 0.5, crownY - crown * 0.1, "#6B4A2E", 0.6);
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
