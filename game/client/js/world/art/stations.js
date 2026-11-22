// The objects that stand at the task stations (Felix, 2026-11-21): one
// thing per station, so a player sees what the task is about before opening
// it. Station 6 ("Catch the wave") is not in use and has no object.
//
// draw.js looks them up in Game.world.art.stations by station id. Each
// function draws its object around the station's centre (0, 0), in map
// units. They are drawn every frame on top of the cached map (see
// drawStations in draw.js): draw.js draws the soft shadow below each object,
// its number tag and the glowing outline around it, from the object's own
// shape.
//
// Since M2-1.20 (Felix, 2026-11-22) the objects are drawn like the furniture
// around them: about as large as the furniture next to them (a chair is
// 8-10 units, a character 39 high), with the furniture's outline colour and
// line widths and colours from the room art files, and each one stands
// against a wall or a piece of furniture where there is room for its
// outline. So an object does not always lie in the middle of its station:
// `place` puts it where it belongs, no part of it (with its lines) more than
// 15 units from the station's centre, so that the outline (4.2 wider, and its soft edge)
// still fits into draw.js's square of 2 x 20 units.
//
// Places of the stations come from campus.json; this file only knows how a
// thing looks and where it stands beside its station.

"use strict";

window.Game = window.Game || {};
Game.world = Game.world || {};

(function () {
  var art = Game.world.art;
  if (!art || !art.util) {
    return; // common.js did not load: draw.js draws only the station numbers
  }
  var util = art.util;
  var box = util.box;
  var circle = util.circle;
  var ellipse = util.ellipse;
  var line = util.line;
  var OUTLINE = util.OUTLINE;

  // The furniture's line widths: the outline round a thing, and its details.
  var EDGE = 0.7;
  var DETAIL = 0.4;

  // Colours of the room art files (art/*.js).
  var WHITE = "#FFFFFF";
  var DARK = "#3A3646";
  var STEEL = "#C3CAD3";
  var STEEL_LIGHT = "#E3E7EC";
  var GREY = "#9AA1AC";
  var CHROME = "#D4D9E0";
  var SHELF_WOOD = "#9B6B45";
  var CAFE_WOOD = "#E0B77F";
  var COFFEE = "#6B4A2E";
  var KRAFT = "#C99662";
  var TRAY = "#E9A15A";
  var RED = "#E8574B";
  var BLUE = "#4C8FD6";
  var YELLOW = "#F2C53D";
  var GREEN = "#6DB65B";
  var ORANGE = "#E07B39";
  var PURPLE = "#9B6BC9";
  var CHECKOUT = "#2F2C38";

  // A closed shape through the given points, filled and outlined.
  function polygon(ctx, points, fill, lineWidth) {
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for (var i = 1; i < points.length; i++) {
      ctx.lineTo(points[i][0], points[i][1]);
    }
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
    if (lineWidth) {
      ctx.strokeStyle = OUTLINE;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    }
  }

  var stations = art.stations = art.stations || {};

  // Registers the drawing of station `id`. `drawObject(ctx)` draws a thing
  // `w` wide and `h` high from (0, 0) to (w, h); `left` and `top` put its
  // top left corner, counted from the station's centre. draw.js draws the
  // shadow along the thing's foot and the number tag at its lower right
  // corner; `extra.shadow` and `extra.tag` (from the station's centre) give
  // other places where the foot is narrower or a wall is close.
  function place(id, left, top, w, h, drawObject, extra) {
    var drawing = function (ctx) {
      ctx.save();
      ctx.translate(left, top);
      drawObject(ctx);
      ctx.restore();
    };
    drawing.shadow = (extra && extra.shadow) || { x: left + 1, y: top + h, w: w - 2 };
    drawing.tag = (extra && extra.tag) || { x: left + w, y: top + h - 1 };
    stations[id] = drawing;
  }

  // 1 Sort the slides: a projector screen on a tripod, with a slide on it.
  // It stands on the stage against the front wall, right of the clock.
  function projectorScreen(ctx) {
    line(ctx, 9, 10, 9, 12, DARK, EDGE);
    line(ctx, 9, 12, 5.5, 14, OUTLINE, EDGE);
    line(ctx, 9, 12, 12.5, 14, OUTLINE, EDGE);
    box(ctx, 1, 1, 16, 9, 0.3, WHITE, EDGE);
    box(ctx, 0, 0, 18, 2, 0.8, "#5A5767", EDGE); // the case the screen rolls into
    line(ctx, 3, 4, 8, 4, BLUE, DETAIL);
    line(ctx, 3, 5.8, 7, 5.8, OUTLINE, DETAIL);
    line(ctx, 3, 7.6, 7.5, 7.6, OUTLINE, DETAIL);
    // A little bar chart on the right half of the slide.
    box(ctx, 10.5, 6, 1.5, 2.5, 0, BLUE, 0);
    box(ctx, 12.75, 4, 1.5, 4.5, 0, RED, 0);
    box(ctx, 15, 5, 1.5, 3.5, 0, BLUE, 0);
  }
  place(1, -6, -14.5, 18, 14, projectorScreen, { shadow: { x: -1, y: -1, w: 8 } });

  // 2 Brew the order: an espresso machine on a small steel cabinet, against
  // the café's right wall below the coffee bar. The tag stays 4 units off
  // the wall.
  function espressoMachine(ctx) {
    box(ctx, 0, 7, 13, 7, 0.8, STEEL, EDGE); // the cabinet
    line(ctx, 5.5, 11.5, 7.5, 11.5, "#8E96A3", DETAIL); // its handle
    box(ctx, 0, 7, 13, 2, 0.6, "#24222B", EDGE); // its black top
    box(ctx, 1.5, 0, 10, 8, 1, CHROME, EDGE); // the machine
    box(ctx, 2.5, 1, 8, 2, 0.4, STEEL_LIGHT, DETAIL); // the warming top with cups
    circle(ctx, 4.5, 2, 0.6, WHITE, 0.3);
    circle(ctx, 6.5, 2, 0.6, WHITE, 0.3);
    circle(ctx, 8.5, 2, 0.6, WHITE, 0.3);
    circle(ctx, 6.5, 4.2, 1, "#8B929E", DETAIL); // the group head
    box(ctx, 5.5, 5.6, 2, 1.6, 0.3, WHITE, DETAIL); // a cup under it
    circle(ctx, 10, 4.2, 0.5, "#F2695C", 0); // the light
  }
  place(2, -2.5, -7, 13, 14, espressoMachine, { tag: { x: 9.5, y: 6 } });

  // 3 Build the tray: a tray with two plates on a short steel stand at the
  // end of the canteen's counter.
  function trayStand(ctx) {
    box(ctx, 0, 0, 16, 11, 0.8, STEEL, EDGE); // the stand
    line(ctx, 1.5, 9.25, 14.5, 9.25, GREY, DETAIL);
    box(ctx, 0, 0, 16, 7.5, 0.8, STEEL_LIGHT, EDGE); // its top
    box(ctx, 1.5, 1, 13, 5.5, 0.6, TRAY, DETAIL); // the tray
    circle(ctx, 5, 3.75, 2, WHITE, DETAIL);
    circle(ctx, 5, 3.75, 1.1, ORANGE, 0);
    circle(ctx, 11, 3.75, 2, WHITE, DETAIL);
    circle(ctx, 11, 3.75, 1.1, GREEN, 0);
  }
  place(3, -13.5, -12, 16, 11, trayStand);

  // 4 Shelve the books: a wooden book cart with a row of books, parked in
  // front of the bookshelf. Its shadow lies under the cart, between the wheels.
  function bookCart(ctx) {
    var colours = [RED, BLUE, YELLOW, GREEN, PURPLE, ORANGE];
    var heights = [4.5, 5, 4, 5, 4.5, 4];
    colours.forEach(function (colour, index) {
      box(ctx, 2.5 + index * 2.2, 6 - heights[index], 2, heights[index], 0.3, colour, DETAIL);
    });
    box(ctx, 0, 6, 18, 5.5, 0.8, SHELF_WOOD, EDGE);
    line(ctx, 1, 8.75, 17, 8.75, util.darker(SHELF_WOOD, 0.3), DETAIL); // the lower shelf
    circle(ctx, 3.5, 12.5, 1.4, DARK, 0);
    circle(ctx, 14.5, 12.5, 1.4, DARK, 0);
  }
  place(4, -9, -1, 18, 14, bookCart, { shadow: { x: -8, y: 10.5, w: 16 } });

  // 5 Self-checkout: one more checkout pillar in the row of Pingo Doce, with
  // its screen, card reader, red scanner glass and bagging tray.
  function selfCheckout(ctx) {
    box(ctx, 0, 0, 14, 16, 1.4, CHECKOUT, EDGE);
    box(ctx, 1, 1, 8.5, 5.5, 0.6, "#101D27", DETAIL); // the screen
    box(ctx, 1.6, 1.6, 7.3, 4.3, 0.3, "#B4DFE0", 0);
    for (var row = 0; row < 3; row++) {
      line(ctx, 2.4, 2.6 + row * 1.1, 6.5, 2.6 + row * 1.1, "#427D80", 0.3);
    }
    box(ctx, 10.5, 1.5, 2.5, 4.5, 0.4, "#1A252C", 0.3); // the card reader
    box(ctx, 11, 2, 1.5, 1.2, 0.2, "#69BE9A", 0);
    box(ctx, 1.2, 8, 6.5, 5.5, 0.5, "#182934", DETAIL); // the scanner glass
    line(ctx, 1.8, 10.75, 7.1, 10.75, "#F56F62", 0.5);
    box(ctx, 8.7, 8, 4.3, 6.5, 0.5, "#B9C0C2", 0.3); // the bagging tray
  }
  place(5, -14.5, -9, 14, 16, selfCheckout);

  // 7 De-buzzword the slides: a flip chart on an easel, one word crossed
  // out. It stands against the front wall, left of the lectern.
  function flipChart(ctx) {
    line(ctx, 6.5, 10, 6.5, 15, util.darker(SHELF_WOOD, 0.3), EDGE); // the back leg
    line(ctx, 4, 10, 1.5, 16, SHELF_WOOD, EDGE);
    line(ctx, 9, 10, 11.5, 16, SHELF_WOOD, EDGE);
    box(ctx, 1, 1, 11, 9.5, 0.3, WHITE, EDGE); // the paper
    box(ctx, 0, 0, 13, 1.8, 0.6, "#5A5767", EDGE); // the clip on top
    line(ctx, 3, 4, 8, 4, OUTLINE, DETAIL);
    line(ctx, 3, 6, 9, 6, OUTLINE, DETAIL);
    line(ctx, 3, 8, 7, 8, OUTLINE, DETAIL);
    line(ctx, 2.5, 7, 9.5, 5, RED, 0.6); // the buzzword, crossed out
  }
  place(7, -2, -14.5, 13, 16, flipChart, { shadow: { x: -0.5, y: 1, w: 10 } });

  // 8 Emergency caffeine protocol: a to-go coffee cup on a small round
  // café table, beside the divider.
  function coffeeOnTable(ctx) {
    box(ctx, 3.5, 9.5, 3, 2.5, 0.5, DARK, DETAIL); // the table's foot
    ellipse(ctx, 5, 8.5, 5, 2.5, CAFE_WOOD, EDGE); // the table top
    polygon(ctx, [[2.5, 2], [7.5, 2], [6.9, 8.5], [3.1, 8.5]], WHITE, EDGE); // the cup
    polygon(ctx, [[2.7, 4.2], [7.3, 4.2], [7.1, 6.3], [2.9, 6.3]], KRAFT, 0); // its sleeve
    box(ctx, 1.5, 0.5, 7, 1.8, 0.6, COFFEE, EDGE); // its lid
  }
  place(8, -9, -14, 10, 12, coffeeOnTable, { shadow: { x: -7.5, y: -3, w: 7 }, tag: { x: 0.5, y: -3 } });

  // 9 Save the lunch: a lunch tray on a small steel trolley. The nearest
  // furniture (table 3, the tray return) is too far for it to lean on.
  function lunchTrolley(ctx) {
    circle(ctx, 2.5, 11, 1, DARK, 0);
    circle(ctx, 13.5, 11, 1, DARK, 0);
    box(ctx, 0, 0, 16, 10, 0.8, STEEL, EDGE); // the trolley
    box(ctx, 0, 0, 16, 7.5, 0.8, STEEL_LIGHT, EDGE); // its top
    box(ctx, 1, 0.75, 14, 6, 0.6, GREY, DETAIL); // the tray
    box(ctx, 2, 1.75, 6, 4, 0.4, "#F4EAC5", 0); // rice
    box(ctx, 9, 1.75, 5, 1.7, 0.4, WHITE, 0);
    box(ctx, 9, 4.05, 5, 1.7, 0.4, WHITE, 0);
    circle(ctx, 11.5, 2.6, 0.7, GREEN, 0);
    circle(ctx, 11.5, 4.9, 0.7, ORANGE, 0);
    circle(ctx, 4, 4.25, 0.8, "#7C8F3A", 0); // a mouldy spot
  }
  place(9, -8, -6, 16, 12, lunchTrolley, { shadow: { x: -7, y: 4, w: 14 } });

  // 10 Decode the group chat: an open laptop with chat bubbles on a small
  // white desk, in front of study table 2. Its shadow lies under the desk.
  function laptopOnDesk(ctx) {
    box(ctx, 1, 7, 1.5, 3, 0.3, GREY, DETAIL); // the legs
    box(ctx, 10.5, 7, 1.5, 3, 0.3, GREY, DETAIL);
    box(ctx, 0, 0, 13, 8, 0.8, WHITE, EDGE); // the desk
    line(ctx, 1, 7, 12, 7, "#E1E4E9", DETAIL);
    box(ctx, 2, 0.5, 9, 5, 0.6, DARK, EDGE); // the laptop's screen
    box(ctx, 2.8, 1.2, 7.4, 3.6, 0.3, WHITE, 0);
    box(ctx, 3.3, 1.6, 4, 1.2, 0.5, util.lighter(GREEN, 0.55), 0);
    box(ctx, 5.7, 3.2, 4, 1.2, 0.5, util.lighter(BLUE, 0.6), 0);
    box(ctx, 1.5, 5.5, 10, 1.5, 0.4, "#AEB5BF", DETAIL); // its keyboard
  }
  place(10, -6.5, 2, 13, 10, laptopOnDesk, { shadow: { x: -5.5, y: 9, w: 11 } });

  // 11 Expense the essentials: a red shopping basket with two products,
  // on the floor beside shelf 3.
  function shoppingBasket(ctx) {
    ctx.beginPath(); // the handle
    ctx.moveTo(2, 4);
    ctx.lineTo(3, 0.5);
    ctx.lineTo(9, 0.5);
    ctx.lineTo(10, 4);
    ctx.strokeStyle = OUTLINE;
    ctx.lineWidth = 0.6;
    ctx.stroke();
    box(ctx, 3, 1.5, 2.5, 3.5, 0.3, YELLOW, DETAIL);
    box(ctx, 6.5, 1, 2.5, 4, 0.3, GREEN, DETAIL);
    polygon(ctx, [[0, 4], [12, 4], [11, 10], [1, 10]], RED, EDGE);
    [4, 6, 8].forEach(function (x) {
      line(ctx, x, 5.5, x, 8.5, util.darker(RED, 0.3), DETAIL);
    });
  }
  place(11, -7, -5, 12, 10, shoppingBasket, { tag: { x: 5.5, y: 4.5 } });

  // 12 Seagull quality control: a seagull on a bin, holding a stolen page,
  // beside the bush on the deck.
  function seagullOnBin(ctx) {
    box(ctx, 1.5, 7, 9, 7, 0.6, "#5E6270", EDGE); // the bin
    [4, 6, 8].forEach(function (x) {
      line(ctx, x, 9, x, 12.5, "#4A4560", DETAIL);
    });
    box(ctx, 0.5, 5.5, 11, 2, 0.6, DARK, EDGE); // its lid
    ellipse(ctx, 5, 3.5, 3.8, 2.3, WHITE, EDGE); // the seagull's body
    ellipse(ctx, 4.2, 3.7, 2.2, 1.2, "#C9CED6", 0); // its wing
    circle(ctx, 8.5, 1.8, 1.8, WHITE, EDGE); // its head
    circle(ctx, 9, 1.5, 0.35, OUTLINE, 0);
    polygon(ctx, [[10.2, 1.6], [11.8, 2.1], [10.2, 2.6]], "#F08A3C", 0); // its beak
    box(ctx, 9.5, 2.8, 2.5, 3, 0.2, WHITE, DETAIL); // the page
    line(ctx, 10, 3.8, 11.5, 3.8, GREY, 0.3);
    line(ctx, 10, 4.8, 11.5, 4.8, GREY, 0.3);
  }
  place(12, -6, -8, 12, 14, seagullOnBin, { shadow: { x: -4.5, y: 6, w: 9 } });
})();
