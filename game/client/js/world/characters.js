// The eight characters, drawn with code (no image files, decision S-28).
//
// Every character is drawn in "design units", the units of the sketch
// game/design/characters.svg: the head is a circle around (0, 20), the body a
// rounded box from y = 38 to 80, the shoes end at y = 97. drawCharacter()
// scales and moves this drawing to the place and size that was asked for.
//
// A character can be drawn from three sides (front, side, back) and in a
// walking cycle, see the comment above drawCharacter().
//
// Used on the map (world.js) and for the small icons in the lobby panel.

"use strict";

window.Game = window.Game || {};
Game.world = Game.world || {};

// The function around everything keeps the helper names of this file out of
// the other files. Only what is put on Game.world is visible outside.
(function () {
  var OUTLINE = "#2E2A3B";
  var SKIN = "#F6E7D0";

  // The drawing reaches from y = -12 (hair bun) to y = 100 (shadow).
  var DESIGN_TOP = -12;
  var DESIGN_HEIGHT = 112;

  // A line thinner than this many screen pixels turns grey and blurry.
  var THINNEST_LINE_IN_PIXELS = 1.2;

  // The same limit in design units. drawCharacter() sets it before drawing,
  // because it depends on how small the character is drawn.
  var thinnestLine = 0;

  // Walking, in design units: how high a foot is lifted, how far it swings
  // forward and back in the side view, and how far the body rises on a step.
  var FOOT_LIFT = 5;
  var FOOT_SWING = 3;
  var BODY_BOB = 3;
  // In the side view the eyes and the mouth sit this far towards the side
  // the character walks to, and the shoes point a little that way.
  var FACE_TURN = 5.5;
  var SHOE_TURN = 2;

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

  // One shoe. `side` is -1 for the left and 1 for the right one, `foot` says
  // how far the foot is moved sideways (x) and lifted off the ground (lift).
  function drawShoe(ctx, side, foot, shoeColour) {
    var x = (side < 0 ? -15 : 1) + foot.x;
    box(ctx, x, 89 - foot.lift, 14, 8, 4, shoeColour || OUTLINE, shoeColour ? 1.5 : 0);
  }

  // One leg, from the hip down into the shoe. `raised` is how far the body
  // is lifted right now: the leg reaches that much further up, so it never
  // comes off the body.
  function drawLeg(ctx, side, foot, colour, raised) {
    var x = (side < 0 ? -13 : 2) + foot.x * 0.6;
    box(ctx, x, 74 - raised, 11, 18 + raised - foot.lift, 4, colour, 2);
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

  // The head without a face: all that is seen of it from behind is skin.
  function drawBareHead(ctx) {
    circle(ctx, 0, 20, 18, SKIN, 2.5);
  }

  // The face is the same for all characters (S-07). `turn` moves the eyes
  // and the mouth to the right: 0 looks at the viewer, FACE_TURN looks to
  // the side.
  function drawFace(ctx, turn) {
    drawBareHead(ctx);
    circle(ctx, -6.5 + turn, 22, 2.4, OUTLINE, 0);
    circle(ctx, 6.5 + turn, 22, 2.4, OUTLINE, 0);
    ctx.save();
    ctx.translate(turn, 0);
    stroke(ctx, "M-4 29 Q0 32.5 4 29", OUTLINE, 2);
    ctx.restore();
    ctx.save();
    ctx.globalAlpha = 0.7;
    if (turn === 0) {
      circle(ctx, -11, 27, 2.6, "#F2A99B", 0);
      circle(ctx, 11, 27, 2.6, "#F2A99B", 0);
    } else {
      // Turned to the side, only the near cheek is seen.
      circle(ctx, 13, 28, 2.6, "#F2A99B", 0);
    }
    ctx.restore();
  }

  // Short hair seen from behind: it covers the head down to the neck.
  function drawShortHairFromBehind(ctx, colour) {
    shape(ctx, "M-18 20 A18 18 0 0 1 18 20 Q17 31 9 33 Q0 30 -9 33 Q-17 31 -18 20 Z", colour, 2);
  }

  function nothing() {}

  // ---- What makes each character different -----------------------------
  //
  // A look has:
  //   body, legs, shoes   colours
  //   leftHand, rightHand where the hands are, as [x, y]
  //   behind(ctx)         drawn behind the body (backpack, hood)
  //   clothes(ctx)        drawn on the body (tie, vest, long hair)
  //   object(ctx)         the thing in the hand
  //   head(ctx, turn)     hair, hat, glasses, headphones; `turn` is how far
  //                       the face is turned to the side (see drawFace)
  //
  // And for the view from behind (a character walking up, away from us):
  //   backClothes(ctx)    drawn on the back (backpack, back of the vest)
  //   backHead(ctx)       hair and headwear from behind, drawn over the head
  //   objectInFront       true if the object is carried in front of the
  //                       body: from behind the body hides it

  var PLAIN_LOOK = {
    body: "#B9B4A6", legs: "#8F8A7D", leftHand: [-22, 65], rightHand: [22, 65],
    behind: nothing, clothes: nothing, object: nothing, head: nothing,
    backClothes: nothing, backHead: nothing
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
        box(ctx, 21, 79, 4, 3, 0, "#FFD23F", 0);
      },
      head: function (ctx) {
        shape(ctx, "M-18 19 A18 18 0 0 1 18 19 Q10 7 -3 9 Q-12 10 -18 19 Z", "#3B2F2F", 2);
      },
      backClothes: function (ctx) {
        // The white shirt collar and the slit at the back of the jacket.
        stroke(ctx, "M-7 40.5 Q0 44 7 40.5", "#FFFFFF", 2.5);
        stroke(ctx, "M0 64 V78", "#1C3156", 2.5);
      },
      backHead: function (ctx) {
        drawShortHairFromBehind(ctx, "#3B2F2F");
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
      backClothes: function (ctx) {
        // The back of the vest is one piece.
        box(ctx, -18, 39, 36, 40, 10, "#3F4A5E", 1.5);
        stroke(ctx, "M-17 52 h34 M-17 62 h34 M-17 72 h34", "#2A3345", 1.5);
      },
      backHead: function (ctx) {
        drawShortHairFromBehind(ctx, "#8A6A3B");
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
      backClothes: function (ctx) {
        box(ctx, -18, 70, 36, 12, 5, "#FFD23F", 2);
        // The backpack, now in front of the body, with its pocket.
        box(ctx, -22, 37, 44, 37, 12, "#3E8FD0", 2.5);
        box(ctx, -11, 53, 22, 15, 4, "#2A6FA8", 1.5);
      },
      backHead: function (ctx) {
        drawShortHairFromBehind(ctx, "#8A5A3B");
        drawBucketHat(ctx);
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
      backClothes: function (ctx) {
        box(ctx, -18, 68, 36, 14, 5, "#F08A3C", 2);
      },
      backHead: function (ctx) {
        // The long hair covers the head and falls down the back.
        shape(ctx, "M-21 20 Q-22 -1 0 -1 Q22 -1 21 20 L22 42 Q11 49 0 45 Q-11 49 -22 42 Z", "#F2D36B", 2);
        stroke(ctx, "M-8 30 V42 M8 30 V42", "#D9B84F", 1.5);
      }
    },

    // Black hoodie with the hood up, laptop covered in stickers.
    founder: {
      body: "#33333D", legs: "#4A5568", shoes: "#FFFFFF", leftHand: [-18, 68], rightHand: [18, 68],
      objectInFront: true,
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
      backClothes: nothing,
      backHead: function (ctx) {
        // The hood hides the whole head; a seam runs down its middle.
        circle(ctx, 0, 20, 22, "#33333D", 2.5);
        stroke(ctx, "M0 0 V38", "#55555F", 1.8);
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
      head: function (ctx, turn) {
        shape(ctx, "M-18 19 A18 18 0 0 1 18 19 Q9 9 0 9 Q-9 9 -18 19 Z", "#5A3E2B", 2);
        drawGlasses(ctx, turn);
      },
      backClothes: nothing,
      backHead: function (ctx) {
        drawShortHairFromBehind(ctx, "#5A3E2B");
        // From behind the bun is in front of the head.
        drawHairBun(ctx);
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
      backClothes: drawSpeedLines,
      backHead: function (ctx) {
        shape(ctx, "M-18 19 Q-23 7 -13 4 Q-15 -5 -5 0 Q-2 -9 4 -1 Q11 -8 13 3 Q23 5 18 19 Q18 31 9 33 Q0 30 -9 33 Q-18 31 -18 19 Z", "#7A4B2A", 2);
        drawSweatDrop(ctx);
      }
    },

    // Purple hoodie, large headphones, stack of books in front of the body.
    library_local: {
      body: "#7A5CC2", legs: "#B9B4A6", leftHand: [-16, 73], rightHand: [16, 73],
      objectInFront: true,
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
      backClothes: function (ctx) {
        // The hood of the hoodie hangs down the back.
        shape(ctx, "M-12 40 Q0 56 12 40 Z", "#6548AD", 2);
      },
      backHead: function (ctx) {
        shape(ctx, "M-18 24 Q-21 2 0 2 Q21 2 18 24 Q16 33 8 34 Q0 31 -8 34 Q-16 33 -18 24 Z", "#2B2B33", 2);
        drawHeadphones(ctx);
      }
    }
  };

  // ---- Parts that are drawn from the front and from behind ---------------

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

  // The glasses sit on the eyes, so they turn with the face (see drawFace).
  function drawGlasses(ctx, turn) {
    ctx.save();
    ctx.translate(turn, 0);
    ctx.save();
    ctx.globalAlpha = 0.35;
    circle(ctx, -6.5, 22, 6, "#FFFFFF", 0);
    circle(ctx, 6.5, 22, 6, "#FFFFFF", 0);
    ctx.restore();
    circle(ctx, -6.5, 22, 6, null, 2);
    circle(ctx, 6.5, 22, 6, null, 2);
    ctx.restore();
    // The bridge between the lenses, and the arms of the glasses, which run
    // to the edge of the head. Turned to the side, only the arm at the back
    // of the head is seen.
    if (turn === 0) {
      stroke(ctx, "M-0.5 22 h1 M-12.5 21 L-17.5 19 M12.5 21 L17.5 19", OUTLINE, 2);
    } else {
      stroke(ctx, "M" + (turn - 0.5) + " 22 h1 M" + (turn - 12.5) + " 21 L-17.5 19", OUTLINE, 2);
    }
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

  // ---- The pose: which way a character looks and how it steps ----------

  var STANDING_FOOT = { x: 0, lift: 0 };

  // Makes a complete pose out of what the caller passed. Everything that is
  // missing or not understood becomes the standing character seen from the
  // front, which is the drawing of the sketch.
  function completePose(pose) {
    var given = pose || {};
    var isKnownDirection = given.direction === "side" || given.direction === "back";
    var isWalking = typeof given.walkPhase === "number" && isFinite(given.walkPhase);
    return {
      direction: isKnownDirection ? given.direction : "front",
      mirrored: given.mirrored === true,
      // -1 to 1: the swing of the walking cycle, 0 when standing. Above 0
      // the left foot is in the air, below 0 the right one.
      swing: isWalking ? Math.sin(given.walkPhase * 2 * Math.PI) : 0
    };
  }

  // Where one foot is. The foot that is in the air is also the one in
  // front; the other one stands on the ground behind it. Only the side view
  // shows forward and back, so only there the feet move sideways.
  function footOf(pose, side) {
    var ownSwing = side < 0 ? pose.swing : -pose.swing;
    if (ownSwing === 0) {
      return STANDING_FOOT;
    }
    var isSideView = pose.direction === "side";
    return {
      x: isSideView ? ownSwing * FOOT_SWING : 0,
      lift: Math.max(0, ownSwing) * FOOT_LIFT
    };
  }

  // Shoes and legs stand on the ground; `raised` is how far the body above
  // them is lifted by the step.
  function drawShoesAndLegs(ctx, look, pose, raised) {
    ctx.save();
    if (pose.direction === "side") {
      ctx.translate(SHOE_TURN, 0); // the shoes point where the character walks
    }
    drawShoe(ctx, -1, footOf(pose, -1), look.shoes);
    drawShoe(ctx, 1, footOf(pose, 1), look.shoes);
    ctx.restore();
    drawLeg(ctx, -1, footOf(pose, -1), look.legs, raised);
    drawLeg(ctx, 1, footOf(pose, 1), look.legs, raised);
  }

  function drawArmsObjectAndHands(ctx, look) {
    drawArm(ctx, -1, look.leftHand, look.body);
    drawArm(ctx, 1, look.rightHand, look.body);
    look.object(ctx);
    drawHand(ctx, look.leftHand);
    drawHand(ctx, look.rightHand);
  }

  // Everything above the legs, seen from the front or from the side.
  // The order matters: what is drawn later lies on top.
  function drawUpperBodyFromFront(ctx, look, turn) {
    drawBody(ctx, look.body);
    look.clothes(ctx);
    drawArmsObjectAndHands(ctx, look);
    drawFace(ctx, turn);
    look.head(ctx, turn);
  }

  // Everything above the legs, seen from behind: no face, and an object
  // that is carried in front of the body disappears behind it.
  function drawUpperBodyFromBehind(ctx, look) {
    if (look.objectInFront) {
      drawArmsObjectAndHands(ctx, look);
    }
    drawBody(ctx, look.body);
    look.backClothes(ctx);
    if (!look.objectInFront) {
      drawArmsObjectAndHands(ctx, look);
    }
    drawBareHead(ctx);
    look.backHead(ctx);
  }

  function drawFigure(ctx, look, pose) {
    var raised = Math.abs(pose.swing) * BODY_BOB;
    var isFromBehind = pose.direction === "back";
    drawShadow(ctx);
    // Legs and shoes are drawn between the things behind the body and the
    // body itself, so each part needs its own shift upwards.
    if (!isFromBehind) {
      ctx.save();
      ctx.translate(0, -raised);
      look.behind(ctx);
      ctx.restore();
    }
    drawShoesAndLegs(ctx, look, pose, raised);
    ctx.save();
    ctx.translate(0, -raised);
    if (isFromBehind) {
      drawUpperBodyFromBehind(ctx, look);
    } else {
      drawUpperBodyFromFront(ctx, look, pose.direction === "side" ? FACE_TURN : 0);
    }
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
  // `pose` may be left out: then the character stands and looks at the
  // viewer, as in the sketch. Otherwise it is an object with these fields,
  // each of which may be left out too:
  //   direction  "front" (walking down, towards the viewer; the face is
  //              seen), "side" (walking to the right; the face is turned
  //              that way) or "back" (walking up; the back of the head)
  //   mirrored   true mirrors the drawing: "side" then walks to the left
  //   walkPhase  a number that runs from 0 to 1 during one walking cycle
  //              (two steps); 0 and 0.5 are the moments with both feet on
  //              the ground. Leave it out or pass null for a standing
  //              character.
  // The middle of the standing character stays at (x, y) in every pose; a
  // walking one rises by at most 3 % of its height on each step.
  function drawCharacter(ctx, characterId, x, y, size, pose) {
    var canDraw = ctx && isFinite(x) && isFinite(y) && isFinite(size) && size > 0;
    if (!canDraw) {
      return;
    }
    var scale = size / DESIGN_HEIGHT;
    ctx.save();
    ctx.translate(x, y);
    var wholePose = completePose(pose);
    ctx.scale(wholePose.mirrored ? -scale : scale, scale);
    // Move the middle of the drawing to (x, y).
    ctx.translate(0, -(DESIGN_TOP + DESIGN_HEIGHT / 2));
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    thinnestLine = THINNEST_LINE_IN_PIXELS / (pixelsPerUnit(ctx) || 1);
    drawFigure(ctx, lookOf(characterId), wholePose);
    ctx.restore();
  }

  Game.world.characters = characters;
  Game.world.drawCharacter = drawCharacter;
})();
