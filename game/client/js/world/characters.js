// The eight characters, drawn with code (no image files, decision S-28).
//
// Every character is drawn in "design units", the units of the sketch
// game/design/characters.svg: the head is a circle around (0, 20), the body a
// rounded box from y = 38 to 80, the shoes end at y = 97. drawCharacter()
// scales and moves this drawing to the place and size that was asked for.
//
// A character has two drawings, see the comment above drawCharacter():
// - the portrait: it stands and looks at the viewer, as in the sketch. Used
//   for the small icons in the lobby panel.
// - the side view: it looks to the right and can walk. Its mirror image
//   looks to the left. Used on the map (world.js). Hair, headwear and the
//   thing in the hand are drawn for this view, so mirroring turns the whole
//   character and nothing stays behind.

"use strict";

window.Game = window.Game || {};
Game.world = Game.world || {};

// The function around everything keeps the helper names of this file out of
// the other files. Only what is put on Game.world is visible outside.
(function () {
  var OUTLINE = "#2E2A3B";
  var SKIN = "#F6E7D0";

  // The drawing of a standing character reaches from y = -12 (hair bun) to
  // y = 100 (shadow). A walking one rises above that on every step, by up
  // to BODY_BOB; its middle is still counted from these two numbers.
  var DESIGN_TOP = -12;
  var DESIGN_HEIGHT = 112;

  // A line thinner than this many screen pixels turns grey and blurry.
  var THINNEST_LINE_IN_PIXELS = 1.2;

  // The same limit in design units. drawCharacter() sets it before drawing,
  // because it depends on how small the character is drawn.
  var thinnestLine = 0;

  // Walking, in design units: how high a foot is lifted, how far it swings
  // forward and back, how far a free hand swings, and how far the body
  // rises on a step.
  var FOOT_LIFT = 5;
  var FOOT_SWING = 7;
  var HAND_SWING = 9;
  var BODY_BOB = 3;
  // Standing in the side view, the far foot is this much in front of the
  // near one, so both shoes are seen.
  var FAR_FOOT_AHEAD = 2.5;

  // Ids, names and lines from DESIGN.md, section 3. `colour` is the body colour.
  var characters = [
    { id: "consultant", name: "The Consultant", line: "Let’s take this offline.", colour: "#26406E" },
    { id: "finance_bro", name: "The Finance Bro", line: "What’s the upside?", colour: "#BFD9F2" },
    { id: "exchange_student", name: "The Exchange Student", line: "Is this graded?", colour: "#F0569B" },
    { id: "surfer", name: "The Surfer", line: "Waves were good, sorry.", colour: "#159A8C" },
    { id: "founder", name: "The Founder", line: "We should pivot.", colour: "#33333D" },
    { id: "overachiever", name: "The Overachiever", line: "I already started.", colour: "#4E9F5B" },
    { id: "latecomer", name: "The Latecomer", line: "Did I miss anything?", colour: "#F08A3C" },
    { id: "library_local", name: "The Library Local", line: "Shhh.", colour: "#7A5CC2" }
  ];

  // ---- Small drawing helpers -------------------------------------------

  // Fills and outlines the path that was just built. Pass null to skip one.
  function paint(ctx, fill, lineColour, lineWidth) {
    if (fill) {
      ctx.fillStyle = fill;
      ctx.fill();
    }
    if (lineColour) {
      ctx.strokeStyle = lineColour;
      ctx.lineWidth = Math.max(lineWidth, thinnestLine);
      ctx.stroke();
    }
  }

  function box(ctx, x, y, width, height, radius, fill, lineWidth) {
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.arcTo(x + width, y, x + width, y + height, radius);
    ctx.arcTo(x + width, y + height, x, y + height, radius);
    ctx.arcTo(x, y + height, x, y, radius);
    ctx.arcTo(x, y, x + width, y, radius);
    ctx.closePath();
    paint(ctx, fill, lineWidth ? OUTLINE : null, lineWidth);
  }

  function circle(ctx, x, y, radius, fill, lineWidth) {
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    paint(ctx, fill, lineWidth ? OUTLINE : null, lineWidth);
  }

  // A free shape, written like the "d" of a path in an SVG file. This way the
  // hair and hats can be taken over from the sketch one to one.
  function shape(ctx, svgPath, fill, lineWidth) {
    var path = pathOf(svgPath);
    if (fill) {
      ctx.fillStyle = fill;
      ctx.fill(path);
    }
    if (lineWidth) {
      strokePath(ctx, path, OUTLINE, lineWidth);
    }
  }

  // Only a line, no filling.
  function stroke(ctx, svgPath, colour, lineWidth) {
    strokePath(ctx, pathOf(svgPath), colour, lineWidth);
  }

  // Reading the text of a path takes time, and every character is drawn
  // again on every frame. So each path is read once and then kept here.
  var keptPaths = new Map(); // text of the path -> Path2D

  function pathOf(svgPath) {
    if (!keptPaths.has(svgPath)) {
      keptPaths.set(svgPath, new Path2D(svgPath));
    }
    return keptPaths.get(svgPath);
  }

  // Is the drawing mirrored right now (a character walking to the left)?
  // In a mirrored drawing the two axes turn the other way round, which makes
  // this number of the transform negative.
  function isMirrored(ctx) {
    var transform = ctx.getTransform();
    return transform.a * transform.d - transform.b * transform.c < 0;
  }

  // Text centred at (x, y). It always reads from left to right, also on a
  // mirrored character: there it is mirrored a second time, around its middle.
  function label(ctx, words, x, y, size, colour) {
    ctx.save();
    ctx.translate(x, y);
    if (isMirrored(ctx)) {
      ctx.scale(-1, 1);
    }
    ctx.fillStyle = colour;
    ctx.font = "bold " + size + "px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    ctx.fillText(words, 0, 0);
    ctx.restore();
  }

  function strokePath(ctx, path, colour, lineWidth) {
    ctx.strokeStyle = colour;
    ctx.lineWidth = Math.max(lineWidth, thinnestLine);
    ctx.stroke(path);
  }

  // ---- The parts every character has -----------------------------------

  // The shadow lies on the ground, also while the character walks.
  function drawShadow(ctx) {
    ctx.save();
    ctx.globalAlpha = 0.14;
    ctx.beginPath();
    ctx.ellipse(0, 98, 24, 5, 0, 0, Math.PI * 2);
    paint(ctx, OUTLINE, null, 0);
    ctx.restore();
  }

  // The portrait: one shoe and one leg. `side` is -1 for the left and 1 for
  // the right one.
  function drawShoe(ctx, side, shoeColour) {
    box(ctx, side < 0 ? -15 : 1, 89, 14, 8, 4, shoeColour || OUTLINE, shoeColour ? 1.5 : 0);
  }

  function drawLeg(ctx, side, colour) {
    box(ctx, side < 0 ? -13 : 2, 74, 11, 18, 4, colour, 2);
  }

  function drawBody(ctx, colour) {
    box(ctx, -19, 38, 38, 42, 11, colour, 2.5);
  }

  // An arm is a bent line from the shoulder to the hand: first drawn thick in
  // the outline colour, then thinner in the body colour, which leaves an
  // outlined sleeve.
  function drawArm(ctx, side, hand, colour) {
    var shoulderX = side * 17;
    var shoulderY = 45;
    var endY = hand[1] - 3;
    // The bend: the middle of the arm, pushed a little away from the body.
    var bendX = (shoulderX + hand[0]) / 2 + side * 6;
    var bendY = (shoulderY + endY) / 2 + 1;
    var arm = new Path2D();
    arm.moveTo(shoulderX, shoulderY);
    arm.quadraticCurveTo(bendX, bendY, hand[0], endY);
    strokePath(ctx, arm, OUTLINE, 10.5);
    // The sleeve must stay thinner than its outline, also at icon size.
    ctx.strokeStyle = colour;
    ctx.lineWidth = 6.5;
    ctx.stroke(arm);
  }

  function drawHand(ctx, hand) {
    circle(ctx, hand[0], hand[1], 5, SKIN, 2);
  }

  function drawBareHead(ctx) {
    circle(ctx, 0, 20, 18, SKIN, 2.5);
  }

  // The face is the same for all characters (S-07).
  function drawFace(ctx) {
    drawBareHead(ctx);
    circle(ctx, -6.5, 22, 2.4, OUTLINE, 0);
    circle(ctx, 6.5, 22, 2.4, OUTLINE, 0);
    stroke(ctx, "M-4 29 Q0 32.5 4 29", OUTLINE, 2);
    ctx.save();
    ctx.globalAlpha = 0.7;
    circle(ctx, -11, 27, 2.6, "#F2A99B", 0);
    circle(ctx, 11, 27, 2.6, "#F2A99B", 0);
    ctx.restore();
  }

  // The same face seen from the side, looking to the right: one eye, the
  // nose, half a smile and the near cheek.
  function drawFaceFromSide(ctx) {
    // The nose is a small circle behind the head: only its tip sticks out.
    circle(ctx, 17.5, 24.5, 3, SKIN, 2);
    drawBareHead(ctx);
    circle(ctx, 9.5, 21.5, 2.4, OUTLINE, 0);
    stroke(ctx, "M10.5 30 Q13.5 32 16 29.5", OUTLINE, 2);
    ctx.save();
    ctx.globalAlpha = 0.7;
    circle(ctx, 5, 27.5, 2.6, "#F2A99B", 0);
    ctx.restore();
  }

  function nothing() {}

  // ---- What makes each character different -----------------------------
  //
  // A look has the colours `body`, `legs` and `shoes`, and two sets of
  // drawing functions.
  //
  // For the portrait:
  //   leftHand, rightHand where the hands are, as [x, y]
  //   behind(ctx)         drawn behind the body (backpack, hood)
  //   clothes(ctx)        drawn on the body (tie, vest, long hair)
  //   object(ctx)         the thing in the hand
  //   head(ctx)           hair, hat, glasses, headphones
  //
  // For the side view, always drawn looking to the right (x grows towards
  // the front of the character):
  //   sideHand            where the one hand that is seen holds the object,
  //                       as [x, y]; null for a free hand, which swings
  //   sideBehind(ctx)     drawn behind the body (backpack on the back)
  //   sideClothes(ctx)    drawn on the body
  //   sideObject(ctx)     the thing in the hand, in front or at the side
  //   sideHead(ctx)       hair, hat, glasses, headphones from the side

  var PLAIN_LOOK = {
    body: "#B9B4A6", legs: "#8F8A7D", leftHand: [-22, 65], rightHand: [22, 65],
    behind: nothing, clothes: nothing, object: nothing, head: nothing,
    sideHand: null, sideBehind: nothing, sideClothes: nothing, sideObject: nothing, sideHead: nothing
  };

  var LOOKS = {
    // Dark blue suit, red tie, briefcase.
    consultant: {
      body: "#26406E", legs: "#1C3156", leftHand: [-22, 65], rightHand: [23, 68],
      behind: nothing,
      clothes: function (ctx) {
        shape(ctx, "M-9 39 L9 39 L0 63 Z", "#FFFFFF", 1.5);
        shape(ctx, "M-2.8 41 L2.8 41 L3.3 52 L2.1 57.5 L0 63 L-2.1 57.5 L-3.3 52 Z", "#E0483E", 1.2);
        stroke(ctx, "M-9 39 L-2.6 56 M9 39 L2.6 56", "#1C3156", 2.5);
      },
      object: function (ctx) {
        box(ctx, 12, 73, 22, 16, 2.5, "#8A5A3B", 2);
        stroke(ctx, "M18 73 v-5 h10 v5", OUTLINE, 2);
        box(ctx, 21, 79, 4, 3, 0, "#FFD23F", 0); // the lock
      },
      head: function (ctx) {
        shape(ctx, "M-18 19 A18 18 0 0 1 18 19 Q10 7 -3 9 Q-12 10 -18 19 Z", "#3B2F2F", 2);
      },
      sideHand: [1, 68],
      sideBehind: nothing,
      sideClothes: function (ctx) {
        // Shirt and tie show at the front of the chest.
        shape(ctx, "M5 39.5 L12 41.5 L14 48 L13.5 62 Z", "#FFFFFF", 1.5);
        shape(ctx, "M10.5 42 L13.6 46 L13.6 62 L11 57 Z", "#E0483E", 1.2);
      },
      sideObject: function (ctx) {
        // The briefcase hangs from the hand, beside the legs.
        stroke(ctx, "M-4 73 v-5 h10 v5", OUTLINE, 2);
        box(ctx, -10, 73, 22, 16, 2.5, "#8A5A3B", 2);
        box(ctx, -1, 79, 4, 3, 0, "#FFD23F", 0);
      },
      sideHead: function (ctx) {
        drawShortHairFromSide(ctx, "#3B2F2F");
      }
    },

    // Light blue shirt, quilted vest, phone with a price chart.
    finance_bro: {
      body: "#BFD9F2", legs: "#D8C3A0", leftHand: [-22, 65], rightHand: [25, 63],
      behind: nothing,
      clothes: function (ctx) {
        shape(ctx, "M-18 48 Q-18 39 -8 39 L-4 39 L-4 79 L-10 79 Q-18 79 -18 70 Z", "#3F4A5E", 1.5);
        shape(ctx, "M18 48 Q18 39 8 39 L4 39 L4 79 L10 79 Q18 79 18 70 Z", "#3F4A5E", 1.5);
        stroke(ctx, "M-17 52 h13 M-17 62 h13 M-17 72 h13 M4 52 h13 M4 62 h13 M4 72 h13", "#2A3345", 1.5);
      },
      object: function (ctx) {
        box(ctx, 19, 42, 13, 22, 2.5, OUTLINE, 0);
        stroke(ctx, "M21.5 58 L24.5 51 L27 54.5 L30 46", "#6BD68A", 1.8);
      },
      head: function (ctx) {
        shape(ctx, "M-18 19 A18 18 0 0 1 18 19 Q14 6 0 7 Q-14 6 -18 19 Z", "#8A6A3B", 2);
      },
      sideHand: [23, 60],
      sideBehind: nothing,
      sideClothes: function (ctx) {
        // The vest is open at the front, where the shirt shows.
        shape(ctx, "M-13.5 49 Q-13.5 39.5 -4 39.5 L7 39.5 L9 79 L-4 79 Q-13.5 79 -13.5 70 Z", "#3F4A5E", 1.5);
        stroke(ctx, "M-12.5 52 h20 M-12.5 62 h21 M-12.5 72 h21", "#2A3345", 1.5);
      },
      sideObject: function (ctx) {
        // The phone is held up in front of the face, a little tilted, so
        // its lit screen is seen.
        ctx.save();
        ctx.translate(26, 50);
        ctx.rotate(0.3);
        box(ctx, -5, -11, 10, 22, 2.5, OUTLINE, 0);
        stroke(ctx, "M-2.5 6 L-0.5 0 L1.5 3 L3 -5", "#6BD68A", 1.8);
        ctx.restore();
      },
      sideHead: function (ctx) {
        drawShortHairFromSide(ctx, "#8A6A3B");
      }
    },

    // Pink, yellow bucket hat, backpack, wheeled suitcase with stickers, lanyard.
    exchange_student: {
      body: "#F0569B", legs: SKIN, leftHand: [-22, 65], rightHand: [32, 50],
      behind: function (ctx) {
        box(ctx, -27, 36, 54, 36, 12, "#3E8FD0", 2.5);
      },
      clothes: function (ctx) {
        box(ctx, -18, 70, 36, 12, 5, "#FFD23F", 2);
        stroke(ctx, "M-12 39 V68 M12 39 V68", "#2A6FA8", 5);
        stroke(ctx, "M-6 40 L0 52 L6 40", OUTLINE, 1.5);
        box(ctx, -4, 52, 8, 10, 1.5, "#FFFFFF", 1.5);
      },
      object: function (ctx) {
        stroke(ctx, "M28 62 V48 H37 V62", OUTLINE, 2);
        box(ctx, 23, 62, 19, 27, 3, "#2BB3A3", 2);
        circle(ctx, 29, 70, 2.5, "#FFD23F", 0);
        box(ctx, 33, 75, 6, 5, 0, "#F2695C", 0);
        circle(ctx, 30, 82, 2, "#FFFFFF", 0);
        circle(ctx, 27, 91, 2.5, OUTLINE, 0);
        circle(ctx, 38, 91, 2.5, OUTLINE, 0);
      },
      head: drawBucketHat,
      sideHand: [25, 52],
      sideBehind: function (ctx) {
        // The backpack sits on the back.
        box(ctx, -31, 39, 24, 34, 9, "#3E8FD0", 2.5);
        box(ctx, -29, 54, 10, 13, 3, "#2A6FA8", 1.5);
      },
      sideClothes: function (ctx) {
        box(ctx, -14, 70, 28, 12, 5, "#FFD23F", 2);
        // The strap of the backpack, then the lanyard with its card.
        stroke(ctx, "M-4 39.5 Q4 50 -11 64", "#2A6FA8", 4.5);
        stroke(ctx, "M7 40 L12.5 52", OUTLINE, 1.5);
        box(ctx, 9.5, 52, 7, 9, 1.5, "#FFFFFF", 1.5);
      },
      sideObject: function (ctx) {
        // The suitcase is pushed along in front.
        stroke(ctx, "M26 62 V51 H35 V62", OUTLINE, 2);
        box(ctx, 21, 62, 19, 27, 3, "#2BB3A3", 2);
        circle(ctx, 27, 70, 2.5, "#FFD23F", 0);
        box(ctx, 31, 75, 6, 5, 0, "#F2695C", 0);
        circle(ctx, 28, 82, 2, "#FFFFFF", 0);
        circle(ctx, 25, 91, 2.5, OUTLINE, 0);
        circle(ctx, 36, 91, 2.5, OUTLINE, 0);
      },
      sideHead: function (ctx) {
        drawShortHairFromSide(ctx, "#8A5A3B");
        // The hat from the side: its brim reaches further to the front.
        shape(ctx, "M-15 12.5 Q-14 -5 1 -5 Q16 -5 17 13.5 Z", "#FFD23F", 2);
        stroke(ctx, "M-21 12 Q2 9 27 15.5", OUTLINE, 5.5);
        ctx.strokeStyle = "#FFD23F";
        ctx.lineWidth = 2.5;
        ctx.stroke(pathOf("M-21 12 Q2 9 27 15.5"));
      }
    },

    // Turquoise, long blond hair, shell necklace, surfboard printed on the shirt.
    surfer: {
      body: "#159A8C", legs: SKIN, leftHand: [-22, 65], rightHand: [22, 65],
      behind: nothing,
      clothes: function (ctx) {
        box(ctx, -18, 68, 36, 14, 5, "#F08A3C", 2);
        stroke(ctx, "M-9 41 Q0 50 9 41", OUTLINE, 1.2);
        circle(ctx, -5, 45, 1.8, "#FFFFFF", 0);
        circle(ctx, 0, 46.5, 1.8, "#FFFFFF", 0);
        circle(ctx, 5, 45, 1.8, "#FFFFFF", 0);
        // The long hair falls over the shoulders, so it is drawn before the face.
        shape(ctx, "M-21 20 Q-22 -1 0 -1 Q22 -1 21 20 L22 40 Q16 45 12 36 L12 20 L-12 20 L-12 36 Q-16 45 -22 40 Z", "#F2D36B", 2);
        drawSurfboardPrint(ctx);
      },
      object: nothing,
      head: function (ctx) {
        shape(ctx, "M-18 19 A18 18 0 0 1 18 19 Q7 9 -5 11 Q-13 12 -18 19 Z", "#F2D36B", 2);
      },
      sideHand: null,
      sideBehind: nothing,
      sideClothes: function (ctx) {
        box(ctx, -14, 68, 28, 14, 5, "#F08A3C", 2);
        // The necklace and the surfboard print are on the front of the
        // shirt; from the side only their near ends are seen.
        circle(ctx, 8.5, 42.5, 1.8, "#FFFFFF", 0);
        circle(ctx, 12, 45, 1.8, "#FFFFFF", 0);
        stroke(ctx, "M5 64 q3 -4 6 0 q1.5 2 3 0", "#FFFFFF", 1.8);
      },
      sideObject: nothing,
      sideHead: function (ctx) {
        // The long hair covers the back of the head and falls down the back.
        shape(ctx, "M13 8 Q11 -1 0 -1 Q-22 -1 -21 20 L-23 47 Q-16 53 -9 47 L-8 17 Q3 15 13 8 Z", "#F2D36B", 2);
        stroke(ctx, "M-15 28 V45", "#D9B84F", 1.5);
      }
    },

    // Black hoodie with the hood up, laptop covered in stickers.
    founder: {
      body: "#33333D", legs: "#4A5568", shoes: "#FFFFFF", leftHand: [-18, 68], rightHand: [18, 68],
      behind: function (ctx) {
        circle(ctx, 0, 20, 22, "#33333D", 2.5);
      },
      clothes: function (ctx) {
        stroke(ctx, "M-5 40 V52 M5 40 V52", "#FFFFFF", 1.8);
      },
      object: function (ctx) {
        box(ctx, -16, 55, 32, 21, 2.5, "#C9CED6", 2);
        circle(ctx, -6, 63, 3.5, "#F2695C", 0);
        box(ctx, 2, 60, 8, 5, 1, "#FFD23F", 0);
        circle(ctx, 6, 70, 2.2, "#5FA86B", 0);
      },
      head: function (ctx) {
        shape(ctx, "M-19 22 A19 19 0 0 1 19 22 Q13 7 0 7 Q-13 7 -19 22 Z", "#33333D", 2);
      },
      sideHand: [14, 73],
      sideBehind: nothing,
      sideClothes: function (ctx) {
        stroke(ctx, "M9 43 V54", "#FFFFFF", 1.8); // the cord of the hood
      },
      sideObject: function (ctx) {
        // The laptop is carried under the arm, its stickers to the outside.
        box(ctx, -11, 55, 30, 20, 2.5, "#C9CED6", 2);
        circle(ctx, -2, 63, 3.5, "#F2695C", 0);
        box(ctx, 6, 59, 8, 5, 1, "#FFD23F", 0);
        circle(ctx, 9, 69, 2.2, "#5FA86B", 0);
      },
      sideHead: function (ctx) {
        // The hood covers the head except for the face, which looks out
        // at the front. A lighter rim shows where it opens.
        shape(ctx, "M11 1 Q-2 -6 -15 3 Q-26 13 -22 31 Q-19 41 -9 42 L3 40.5 Q-6 31 -3 19 Q0 8 11 1 Z", "#33333D", 2);
        stroke(ctx, "M7.5 5 Q-1.5 12 -0.5 24 Q0 31 3 36.5", "#6E6E7A", 1.8);
      }
    },

    // Green cardigan, glasses, hair bun, folder with tabs and "A+".
    overachiever: {
      body: "#4E9F5B", legs: "#5E6472", leftHand: [-22, 65], rightHand: [31, 70],
      behind: drawHairBun,
      clothes: function (ctx) {
        shape(ctx, "M-8 39 L8 39 L0 56 Z", "#FFFFFF", 1.5);
        circle(ctx, 0, 62, 1.6, OUTLINE, 0);
        circle(ctx, 0, 70, 1.6, OUTLINE, 0);
      },
      object: function (ctx) {
        box(ctx, 7, 54, 24, 30, 2.5, "#FFFFFF", 2);
        box(ctx, 31, 58, 5, 6, 0, "#F2695C", 1);
        box(ctx, 31, 66, 5, 6, 0, "#FFD23F", 1);
        box(ctx, 31, 74, 5, 6, 0, "#6FA8F0", 1);
        stroke(ctx, "M11 61 h15 M11 67 h15 M11 73 h10", "#B9B4A6", 1.5);
        label(ctx, "A+", 19, 82, 7, "#5FA86B");
      },
      head: function (ctx) {
        shape(ctx, "M-18 19 A18 18 0 0 1 18 19 Q9 9 0 9 Q-9 9 -18 19 Z", "#5A3E2B", 2);
        drawGlasses(ctx);
      },
      sideHand: [16, 80],
      sideBehind: nothing,
      sideClothes: function (ctx) {
        shape(ctx, "M5 39.5 L12 41.5 L14 48 L12.5 54 Z", "#FFFFFF", 1.5);
      },
      sideObject: function (ctx) {
        // The folder is carried under the arm, its tabs to the front.
        box(ctx, -7, 52, 24, 30, 2.5, "#FFFFFF", 2);
        box(ctx, 17, 56, 5, 6, 0, "#F2695C", 1);
        box(ctx, 17, 64, 5, 6, 0, "#FFD23F", 1);
        box(ctx, 17, 72, 5, 6, 0, "#6FA8F0", 1);
        stroke(ctx, "M-3 59 h15 M-3 65 h15 M-3 71 h10", "#B9B4A6", 1.5);
        label(ctx, "A+", 3, 80, 7, "#5FA86B");
      },
      sideHead: function (ctx) {
        // The bun sits at the back of the head, half under the hair.
        circle(ctx, -15, 3, 8, "#5A3E2B", 2);
        drawShortHairFromSide(ctx, "#5A3E2B");
        drawGlassesFromSide(ctx);
      }
    },

    // Orange jacket, messy hair, coffee cup, drops of sweat.
    latecomer: {
      body: "#F08A3C", legs: "#3F5F8A", leftHand: [-22, 65], rightHand: [25, 67],
      behind: drawSpeedLines,
      clothes: function (ctx) {
        box(ctx, -6, 39, 12, 40, 0, "#FFFFFF", 1.5);
      },
      object: function (ctx) {
        stroke(ctx, "M23 46 q-3 -4 0 -8 M29 47 q3 -4 0 -8", "#B9B4A6", 1.8);
        shape(ctx, "M17 56 L34 56 L32 78 L19 78 Z", "#FFFFFF", 2);
        box(ctx, 16, 52, 19, 5, 2, "#8A5A3B", 1.5);
        box(ctx, 19, 63, 13, 7, 0, "#C9A27A", 0);
      },
      head: function (ctx) {
        shape(ctx, "M-18 19 Q-23 7 -13 4 Q-15 -5 -5 0 Q-2 -9 4 -1 Q11 -8 13 3 Q23 5 18 19 Q10 9 0 11 Q-10 9 -18 19 Z", "#7A4B2A", 2);
        drawSweatDrop(ctx);
      },
      sideHand: [22, 68],
      // The speed lines trail behind, which is where they are in the sketch.
      sideBehind: drawSpeedLines,
      sideClothes: function (ctx) {
        // The open jacket shows the white shirt at the front.
        shape(ctx, "M7 39.5 L12 41.5 L14 48 L14 72 L9.5 79 Z", "#FFFFFF", 1.5);
      },
      sideObject: function (ctx) {
        // The coffee cup is held out in front.
        stroke(ctx, "M24 46 q-3 -4 0 -8 M30 47 q3 -4 0 -8", "#B9B4A6", 1.8);
        shape(ctx, "M18 56 L35 56 L33 78 L20 78 Z", "#FFFFFF", 2);
        box(ctx, 17, 52, 19, 5, 2, "#8A5A3B", 1.5);
        box(ctx, 20, 63, 13, 7, 0, "#C9A27A", 0);
      },
      sideHead: function (ctx) {
        shape(ctx, "M13 8 Q14 -3 6 -1 Q4 -10 -3 -2 Q-9 -10 -12 0 Q-23 -2 -19 9 Q-26 14 -19.5 20 L-17 26 Q-11 25 -9 16 Q3 15 13 8 Z", "#7A4B2A", 2);
        // The drop of sweat flies off behind the head.
        shape(ctx, "M-27 12 q4 6 0 10 q-4 -4 0 -10 Z", "#6FB8E8", 1.2);
      }
    },

    // Purple hoodie, large headphones, stack of books in front of the body.
    library_local: {
      body: "#7A5CC2", legs: "#B9B4A6", leftHand: [-16, 73], rightHand: [16, 73],
      behind: nothing,
      clothes: nothing,
      object: function (ctx) {
        box(ctx, -14, 67, 28, 8, 1.5, "#6FA8F0", 1.8);
        box(ctx, -12, 59, 25, 8, 1.5, "#E0483E", 1.8);
        box(ctx, -13, 51, 23, 8, 1.5, "#FFD23F", 1.8);
      },
      head: function (ctx) {
        shape(ctx, "M-18 24 Q-21 2 0 2 Q21 2 18 24 L15 14 Q0 8 -15 14 Z", "#2B2B33", 2);
        drawHeadphones(ctx);
      },
      sideHand: [20, 77],
      sideBehind: nothing,
      sideClothes: function (ctx) {
        // The hood of the hoodie hangs down the back.
        shape(ctx, "M-7 39.5 Q-22 39 -20 50 Q-14 55 -10 47 Z", "#6548AD", 2);
      },
      sideObject: function (ctx) {
        // The stack of books is carried in front of the chest.
        box(ctx, 7, 67, 28, 8, 1.5, "#6FA8F0", 1.8);
        box(ctx, 9, 59, 25, 8, 1.5, "#E0483E", 1.8);
        box(ctx, 8, 51, 23, 8, 1.5, "#FFD23F", 1.8);
      },
      sideHead: function (ctx) {
        shape(ctx, "M13 9 Q12 1 0 1 Q-20 1 -19.5 20 L-17 28 Q-11 27 -9 17 Q3 16 13 9 Z", "#2B2B33", 2);
        drawHeadphonesFromSide(ctx);
      }
    }
  };

  // ---- Parts of the looks that need more than a line or two ------------

  function drawBucketHat(ctx) {
    shape(ctx, "M-15 13 Q-14 -4 0 -4 Q14 -4 15 13 Z", "#FFD23F", 2);
    // The brim of the hat: a thick dark line with a yellow one on top.
    stroke(ctx, "M-23 14 Q0 8 23 14", OUTLINE, 5.5);
    ctx.strokeStyle = "#FFD23F";
    ctx.lineWidth = 2.5;
    ctx.stroke(pathOf("M-23 14 Q0 8 23 14"));
  }

  function drawHairBun(ctx) {
    circle(ctx, 0, -3, 8, "#5A3E2B", 2);
  }

  // Short hair from the side: it covers the top and the back of the head
  // and leaves the face free at the front.
  function drawShortHairFromSide(ctx, colour) {
    shape(ctx, "M13 8 Q11 0.5 0 1 Q-19.5 1.5 -19 20 L-17 26 Q-11 25 -9 16 Q3 15 13 8 Z", colour, 2);
  }

  function drawGlasses(ctx) {
    ctx.save();
    ctx.globalAlpha = 0.35;
    circle(ctx, -6.5, 22, 6, "#FFFFFF", 0);
    circle(ctx, 6.5, 22, 6, "#FFFFFF", 0);
    ctx.restore();
    circle(ctx, -6.5, 22, 6, null, 2);
    circle(ctx, 6.5, 22, 6, null, 2);
    // The bridge between the lenses, and the arms of the glasses, which run
    // to the edge of the head.
    stroke(ctx, "M-0.5 22 h1 M-12.5 21 L-17.5 19 M12.5 21 L17.5 19", OUTLINE, 2);
  }

  // From the side one lens is seen, and the arm that runs back to the ear.
  function drawGlassesFromSide(ctx) {
    ctx.save();
    ctx.globalAlpha = 0.35;
    circle(ctx, 9.5, 21.5, 6, "#FFFFFF", 0);
    ctx.restore();
    circle(ctx, 9.5, 21.5, 6, null, 2);
    stroke(ctx, "M3.5 21 L-8 19.5", OUTLINE, 2);
  }

  // Speed lines: the Latecomer is always in a hurry.
  function drawSpeedLines(ctx) {
    stroke(ctx, "M-44 50 h10 M-46 60 h14 M-44 70 h10", "#B9B4A6", 2.5);
  }

  function drawSweatDrop(ctx) {
    shape(ctx, "M24 14 q4 6 0 10 q-4 -4 0 -10 Z", "#6FB8E8", 1.2);
  }

  function drawHeadphones(ctx) {
    // The band of the headphones: dark line, coral line on top.
    stroke(ctx, "M-19 17 A19 19 0 0 1 19 17", OUTLINE, 7);
    ctx.strokeStyle = "#F2695C";
    ctx.lineWidth = 3.5;
    ctx.stroke(pathOf("M-19 17 A19 19 0 0 1 19 17"));
    box(ctx, -25, 13, 9, 16, 4, "#F2695C", 2);
    box(ctx, 16, 13, 9, 16, 4, "#F2695C", 2);
  }

  // From the side the band runs straight up over the head, and one ear cup
  // is seen from its round outside.
  function drawHeadphonesFromSide(ctx) {
    stroke(ctx, "M-3 16 Q-5.5 8 -3 0.5", OUTLINE, 7);
    ctx.strokeStyle = "#F2695C";
    ctx.lineWidth = 3.5;
    ctx.stroke(pathOf("M-3 16 Q-5.5 8 -3 0.5"));
    circle(ctx, -3, 22, 9, "#F2695C", 2);
    circle(ctx, -3, 22, 4, "#C9463B", 0);
  }

  // A small yellow surfboard, tilted, with waves below it.
  function drawSurfboardPrint(ctx) {
    var tilt = 28 * Math.PI / 180;
    ctx.beginPath();
    ctx.ellipse(0, 57, 4.5, 9.5, tilt, 0, Math.PI * 2);
    paint(ctx, "#FFD23F", OUTLINE, 1.5);
    stroke(ctx, "M-3.5 50.5 L3.5 63.5", "#F2695C", 1.5);
    stroke(ctx, "M-12 65 q3 -4 6 0 t6 0 t6 0 t6 0", "#FFFFFF", 1.8);
  }

  // ---- Putting a character together ------------------------------------

  function lookOf(characterId) {
    // hasOwnProperty: an id like "toString" must not find something by accident.
    if (typeof characterId === "string" && Object.prototype.hasOwnProperty.call(LOOKS, characterId)) {
      return LOOKS[characterId];
    }
    return PLAIN_LOOK;
  }

  // The portrait: the character stands and looks at the viewer, as in the
  // sketch. The order matters: what is drawn later lies on top.
  function drawPortrait(ctx, look) {
    drawShadow(ctx);
    look.behind(ctx);
    drawShoe(ctx, -1, look.shoes);
    drawShoe(ctx, 1, look.shoes);
    drawLeg(ctx, -1, look.legs);
    drawLeg(ctx, 1, look.legs);
    drawBody(ctx, look.body);
    look.clothes(ctx);
    drawArm(ctx, -1, look.leftHand, look.body);
    drawArm(ctx, 1, look.rightHand, look.body);
    look.object(ctx);
    drawHand(ctx, look.leftHand);
    drawHand(ctx, look.rightHand);
    drawFace(ctx);
    look.head(ctx);
  }

  // ---- The side view and its walking cycle -----------------------------

  // The swing of the walking cycle, from -1 to 1, and 0 when standing.
  // Above 0 the near foot is in the air and in front, below 0 the far one.
  function swingOf(pose) {
    var isWalking = typeof pose.walkPhase === "number" && isFinite(pose.walkPhase);
    if (!isWalking) {
      return 0;
    }
    return Math.sin(pose.walkPhase * 2 * Math.PI) * strideOf(pose);
  }

  // How big the steps are, from 0 (none) to 1 (full). Full if nothing
  // understandable was passed.
  function strideOf(pose) {
    if (typeof pose.stride !== "number" || isNaN(pose.stride)) {
      return 1;
    }
    return Math.max(0, Math.min(1, pose.stride));
  }

  // One leg with its shoe, seen from the side. `ownSwing` is the swing of
  // this foot: above 0 it is in the air and in front, below 0 it stands on
  // the ground behind. `ahead` moves the whole leg to the front. `raised` is
  // how far the body is lifted right now: the leg reaches that much further
  // up, so it never comes off the body.
  function drawLegFromSide(ctx, look, ownSwing, ahead, raised) {
    var footX = ownSwing * FOOT_SWING + ahead;
    var lift = Math.max(0, ownSwing) * FOOT_LIFT;
    // The toe of the shoe points to the front.
    box(ctx, -6.5 + footX, 89 - lift, 16, 8, 4, look.shoes || OUTLINE, look.shoes ? 1.5 : 0);
    // The hip moves less than the foot.
    box(ctx, -5.5 + footX * 0.6, 74 - raised, 11, 18 + raised - lift, 4, look.legs, 2);
  }

  // The one arm that is seen from the side, from the shoulder to the hand
  // at (handX, handY), and the hand. Drawn like the arms of the portrait:
  // a thick dark line with a thinner one in the body colour on top.
  function drawArmFromSide(ctx, handX, handY, colour) {
    var shoulderX = -1;
    var shoulderY = 46;
    var endY = handY - 3;
    ctx.beginPath();
    ctx.moveTo(shoulderX, shoulderY);
    // The elbow: the middle of the arm, pushed a little to the back.
    ctx.quadraticCurveTo((shoulderX + handX) / 2 - 4, (shoulderY + endY) / 2 + 2, handX, endY);
    paint(ctx, null, OUTLINE, 10.5);
    ctx.strokeStyle = colour;
    ctx.lineWidth = 6.5;
    ctx.stroke();
    circle(ctx, handX, handY, 5, SKIN, 2);
  }

  // Everything above the legs. A hand that holds something stays where the
  // object is; a free hand swings against the near leg, as in real walking.
  function drawUpperBodyFromSide(ctx, look, swing) {
    box(ctx, -14, 38, 28, 42, 11, look.body, 2.5);
    look.sideClothes(ctx);
    look.sideObject(ctx);
    if (look.sideHand) {
      drawArmFromSide(ctx, look.sideHand[0], look.sideHand[1], look.body);
    } else {
      drawArmFromSide(ctx, 1 - swing * HAND_SWING, 67 - Math.abs(swing) * 2, look.body);
    }
    drawFaceFromSide(ctx);
    look.sideHead(ctx);
  }

  // The character seen from the side, looking to the right.
  function drawSideView(ctx, look, swing) {
    var raised = Math.abs(swing) * BODY_BOB;
    drawShadow(ctx);
    // The legs stand on the ground while the body above them rises with
    // the step. They are drawn between the things on the back and the
    // body, so each part needs its own shift upwards.
    ctx.save();
    ctx.translate(0, -raised);
    look.sideBehind(ctx);
    ctx.restore();
    drawLegFromSide(ctx, look, -swing, FAR_FOOT_AHEAD, raised);
    drawLegFromSide(ctx, look, swing, 0, raised);
    ctx.save();
    ctx.translate(0, -raised);
    drawUpperBodyFromSide(ctx, look, swing);
    ctx.restore();
  }

  // How many screen pixels one unit of the context is right now.
  function pixelsPerUnit(ctx) {
    var transform = ctx.getTransform();
    return Math.sqrt(transform.a * transform.a + transform.b * transform.b);
  }

  // Draws one character centred at (x, y); `size` is its height.
  // An unknown id draws a plain grey figure.
  //
  // Without `pose` it is the portrait: the character stands and looks at
  // the viewer, as in the sketch (the icons of the lobby).
  //
  // With `pose` it is the side view (the map). `pose` is an object with
  // these fields, each of which may be left out:
  //   mirrored   false or left out: the character looks to the right.
  //              true: the whole drawing is mirrored and looks to the left.
  //   walkPhase  a number that runs from 0 to 1 during one walking cycle
  //              (two steps); 0 and 0.5 are the moments with both feet on
  //              the ground. Leave it out or pass null for a standing
  //              character.
  //   stride     how big the steps are, from 0 (the feet stay down) to 1
  //              (full steps, also when it is left out). world.js lets it
  //              grow and shrink so that starting and stopping look soft.
  // The middle of the standing character stays at (x, y) in both drawings; a
  // walking one rises by at most 3 % of its height on each step.
  function drawCharacter(ctx, characterId, x, y, size, pose) {
    var canDraw = ctx && isFinite(x) && isFinite(y) && isFinite(size) && size > 0;
    if (!canDraw) {
      return;
    }
    var scale = size / DESIGN_HEIGHT;
    var isMirrored = Boolean(pose) && pose.mirrored === true;
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(isMirrored ? -scale : scale, scale);
    // Move the middle of the drawing to (x, y).
    ctx.translate(0, -(DESIGN_TOP + DESIGN_HEIGHT / 2));
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    thinnestLine = THINNEST_LINE_IN_PIXELS / (pixelsPerUnit(ctx) || 1);
    if (pose) {
      drawSideView(ctx, lookOf(characterId), swingOf(pose));
    } else {
      drawPortrait(ctx, lookOf(characterId));
    }
    ctx.restore();
  }

  Game.world.characters = characters;
  Game.world.drawCharacter = drawCharacter;
})();
