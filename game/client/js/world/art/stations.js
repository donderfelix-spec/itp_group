// The objects that stand at the task stations (Felix, 2026-11-21): one
// thing per station, so a player sees what the task is about before opening
// it. Station 6 ("Catch the wave") is not in use and has no object.
//
// draw.js looks them up in Game.world.art.stations by station id. Each
// function draws its object around (0, 0), in map units, about 24 units
// wide: smaller than a character (39 units high), so a player standing at
// the station never hides it completely. They are drawn every frame on top
// of the cached map (see drawStations in draw.js) and have no shadow of
// their own: draw.js draws one below each object and the glowing outline
// around it, from the object's own shape.
//
// Places come from campus.json; these files only know how a thing looks.

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

  var WHITE = "#FFFFFF";
  var CREAM = "#F4EFE3";
  var SUN = "#FFD23F";
  var CORAL = "#E8735A";
  var GREEN = "#5FA86B";
  var BLUE = "#5E8BC7";
  var WOOD = "#9B6B43";
  var STEEL = "#BFC6CF";
  var DARK_STEEL = "#3A3D45";

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
    ctx.strokeStyle = OUTLINE;
    ctx.lineWidth = lineWidth;
    ctx.stroke();
  }

  var stations = art.stations = art.stations || {};

  // 1 Sort the slides: a projector screen on a stand, with a slide on it.
  stations[1] = function (ctx) {
    line(ctx, 0, 3, 0, 10, OUTLINE, 1.8);
    line(ctx, -6, 10.5, 6, 10.5, OUTLINE, 1.8);
    box(ctx, -12, -12, 24, 15, 1, WHITE, 1.4);
    line(ctx, -12, -12, 12, -12, OUTLINE, 2.4); // the roller at the top
    line(ctx, -9, -8, -3, -8, "#7A8CA8", 1.4);
    line(ctx, -9, -4.5, 1, -4.5, "#7A8CA8", 1.4);
    line(ctx, -9, -1, -1, -1, "#7A8CA8", 1.4);
    box(ctx, 3, -9, 6, 7, 0.5, "#9FC5E8", 0.7);
  };

  // 2 Brew the order: an espresso machine with a cup under the spout.
  stations[2] = function (ctx) {
    box(ctx, -11, -12, 22, 21, 3, "#6B6F7A", 1.4);
    box(ctx, -8, -9, 16, 5, 1, DARK_STEEL, 0.7);
    circle(ctx, -4.5, -6.5, 1.1, CORAL, 0);
    circle(ctx, 0, -6.5, 1.1, SUN, 0);
    circle(ctx, 4.5, -6.5, 1.1, GREEN, 0);
    box(ctx, -2.5, -3, 5, 3, 0.5, DARK_STEEL, 0.7); // the spout
    box(ctx, -4, 2, 8, 5.5, 1.8, WHITE, 0.9);
    line(ctx, -9, 9, 9, 9, OUTLINE, 1.2); // the drip tray
  };

  // 3 Build the tray: a tray with two plates.
  stations[3] = function (ctx) {
    box(ctx, -12, -8, 24, 16, 3, "#C9A27A", 1.4);
    circle(ctx, -5.5, 0, 4.5, WHITE, 0.9);
    circle(ctx, -5.5, 0, 2.5, "#E8B04A", 0);
    circle(ctx, 5.5, 0, 4.5, WHITE, 0.9);
    circle(ctx, 5.5, 0, 2.5, GREEN, 0);
  };

  // 4 Shelve the books: a book cart with a row of books.
  stations[4] = function (ctx) {
    var colours = [CORAL, BLUE, SUN, GREEN, "#B07CC6", CORAL, BLUE];
    colours.forEach(function (colour, index) {
      var height = index % 2 ? 8 : 9.5;
      box(ctx, -10.5 + index * 3, -4 - height, 2.8, height, 0.4, colour, 0.7);
    });
    box(ctx, -12, -4, 24, 11, 1, WOOD, 1.4);
    line(ctx, -12, 1.5, 12, 1.5, OUTLINE, 0.8);
    circle(ctx, -8, 9, 1.9, OUTLINE, 0);
    circle(ctx, 8, 9, 1.9, OUTLINE, 0);
  };

  // 5 Self-checkout: a terminal with a screen and a red scanner glass.
  stations[5] = function (ctx) {
    box(ctx, -8, -2, 16, 12, 1, STEEL, 1.4);
    box(ctx, -6.5, -13, 13, 10, 1.5, "#2E3B4E", 1.4);
    box(ctx, -4.5, -11, 9, 6, 0.5, "#7FD1C1", 0);
    box(ctx, -5.5, 0.5, 11, 2.5, 0.5, CORAL, 0.7);
    line(ctx, -4, 6, 4, 6, OUTLINE, 0.8);
  };

  // 7 De-buzzword the slides: a flip chart on an easel, one word crossed out.
  stations[7] = function (ctx) {
    line(ctx, -7, 11, -3.5, -1, WOOD, 1.8);
    line(ctx, 7, 11, 3.5, -1, WOOD, 1.8);
    box(ctx, -9, -13, 18, 14, 0.5, WHITE, 1.4);
    line(ctx, -9, -13, 9, -13, OUTLINE, 2.2);
    line(ctx, -6, -9, 4, -9, OUTLINE, 1.1);
    line(ctx, -6, -5, 2, -5, OUTLINE, 1.1);
    line(ctx, -7, -2.5, 6, -11, CORAL, 1.8);
  };

  // 8 Emergency caffeine protocol: a giant to-go coffee cup with steam.
  stations[8] = function (ctx) {
    polygon(ctx, [[-7, -7], [7, -7], [5, 10], [-5, 10]], WHITE, 1.4);
    box(ctx, -6.2, -1, 12.4, 5, 0.5, "#C9A27A", 0.7); // the sleeve
    box(ctx, -8, -10.5, 16, 3.5, 1, "#6B4A35", 1.2); // the lid
    line(ctx, -2.5, -12.5, -1.5, -15.5, "#A0A0A0", 1.1);
    line(ctx, 2.5, -12.5, 3.5, -15.5, "#A0A0A0", 1.1);
  };

  // 9 Save the lunch: a lunch tray seen from above.
  stations[9] = function (ctx) {
    box(ctx, -12, -9, 24, 18, 3, "#DCE6E1", 1.4);
    box(ctx, -10, -7, 10, 14, 2, WHITE, 0.7);
    box(ctx, 1.5, -7, 8.5, 6.5, 2, WHITE, 0.7);
    box(ctx, 1.5, 0.5, 8.5, 6.5, 2, WHITE, 0.7);
    for (var grain = 0; grain < 6; grain++) {
      ellipse(ctx, -7.5 + (grain % 2) * 4.5, -4 + Math.floor(grain / 2) * 4, 1.3, 0.8, CREAM, 0.4);
    }
    circle(ctx, 5.7, -3.7, 2, GREEN, 0.5);
    circle(ctx, 5.7, 3.7, 2, "#D99A5B", 0.5);
    circle(ctx, -3, 3.5, 1.1, "#7C8F3A", 0); // a mouldy spot
  };

  // 10 Decode the group chat: an open laptop with chat bubbles.
  stations[10] = function (ctx) {
    box(ctx, -11, -12, 22, 15, 1.5, DARK_STEEL, 1.4);
    box(ctx, -9, -10, 18, 11, 0.5, WHITE, 0);
    box(ctx, -8, -9, 9, 3.5, 1.5, "#CDE7C8", 0);
    box(ctx, -1, -4.5, 9, 3.5, 1.5, "#D6E4F5", 0);
    box(ctx, -13, 3, 26, 6, 1.5, STEEL, 1.4); // the keyboard
    line(ctx, -4, 6, 4, 6, OUTLINE, 0.8);
  };

  // 11 Expense the essentials: a red shopping basket with two products.
  stations[11] = function (ctx) {
    line(ctx, -6.5, -3, -4.5, -11, OUTLINE, 1.5);
    line(ctx, 6.5, -3, 4.5, -11, OUTLINE, 1.5);
    line(ctx, -4.5, -11, 4.5, -11, OUTLINE, 1.5);
    box(ctx, -6.5, -8, 4.5, 5, 0.5, SUN, 0.7);
    box(ctx, 1, -9, 3.5, 6, 0.5, GREEN, 0.7);
    polygon(ctx, [[-11, -3], [11, -3], [9, 9], [-9, 9]], CORAL, 1.4);
    [-5, 0, 5].forEach(function (x) { line(ctx, x, -1, x * 0.85, 7, "#B85A45", 0.9); });
  };

  // 12 Seagull quality control: a seagull on a bin, holding a stolen page.
  stations[12] = function (ctx) {
    box(ctx, -7, -2, 14, 12, 1, "#6E8A7A", 1.4);
    box(ctx, -8, -4.5, 16, 3.5, 1, "#55705F", 1.1); // the lid
    ellipse(ctx, 0, -9.5, 6.5, 4.5, WHITE, 1.1); // the body
    circle(ctx, 5.5, -13, 3, WHITE, 1.1); // the head
    circle(ctx, 6.6, -13.6, 0.6, OUTLINE, 0);
    line(ctx, 8.2, -12.5, 11, -12, "#F2A93B", 1.6); // the beak
    box(ctx, -11, -13, 6, 7, 0.4, WHITE, 0.9); // the page
    line(ctx, -10, -10.5, -6.5, -10.5, "#99AAAA", 0.7);
    line(ctx, -10, -8.5, -7, -8.5, "#99AAAA", 0.7);
  };
})();
