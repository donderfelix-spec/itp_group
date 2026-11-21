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
// - the turned view: it is still seen mostly from the front, but turned a
//   little to the right, and it can walk. Its mirror image is turned to the
//   left. Used on the map (world.js). Face, hair, headwear and the thing in
//   the hand are drawn turned too, so the character reads as one turned
//   figure and mirroring turns all of it: the face moves towards the side
//   it is turned to, and hair and headwear are drawn as seen from there.
//   The head itself is not moved, so a hat on it is not either; only the
//   top of its crown leans towards the face. What sits on the front of the
//   upper body (tie, straps, necklace) stays in the middle of the body, so
//   it is still in the middle in the mirror image.

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

  // The highest the body may rise on a step, in design units. The name above
  // a character on the map keeps room for exactly this rise
  // (HEAD_ROOM_BELOW_NAME in world.js), so the body never rises higher.
  var BODY_BOB = 3;

  // How a character runs on the map, in design units (a character is 112
  // design units high, which is 39 map units on the map). How many map
  // units one cycle of two steps covers is set in world.js
  // (WALK_CYCLE_LENGTH): it belongs to these numbers, because together
  // they decide how much a foot slides on the ground.
  //
  // How far a foot goes in front of and behind its place when standing.
  var FOOT_TRAVEL = 9;
  // The part of a step a foot is on the ground. The rest of the step both
  // feet are in the air: that moment in the air is what makes it a run.
  var GROUND_FRACTION = 0.5;
  // How high the back foot is kicked up after it pushed off, and when: at
  // this part of its time in the air (35 %), while it is still behind.
  var KICK = 9;
  var KICK_HIGHEST_AT = 0.35;
  // How far the body rises in the air between two steps: as high as the
  // name above it leaves room for (BODY_BOB).
  var HOP = BODY_BOB;
  // How far the runner leans forward (radians), turning around the point
  // between the feet (GROUND_Y), so the feet stay in place.
  var LEAN = 0.11;
  var GROUND_Y = 96;
  // The arms of a runner are bent: the free hands are held this much higher
  // and this much closer to the body ...
  var HAND_RAISE = 9;
  var HAND_INWARD = 3;
  // ... and pump this far forward and back, higher in front than behind.
  var HAND_PUMP = 6;
  var HAND_PUMP_RISE = 3;
  // A hand that holds something alone pumps only this part as far, so its
  // object does not fly about.
  var HELD_SHARE = 1 / 3;

  // In the turned view the face (eyes, mouth, cheeks, glasses) sits this
  // far towards the side it is turned to, and the shoes point a little
  // that way.
  var TURN = 5;
  var SHOE_TURN = 2;
  // The body, a rounded box. In the turned view it is a little narrower on
  // the side the character is turned to: it reaches from x = -18 to 17, so
  // its middle is half a unit left of the middle of the portrait's body.
  var BODY = { x: -19, y: 38, width: 38, height: 42, radius: 11 };
  var TURNED_BODY = { x: -18, y: 38, width: 35, height: 42, radius: 11 };
  var TURNED_BODY_MIDDLE = TURNED_BODY.x + TURNED_BODY.width / 2;

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

  // Text centred at (x, y). The only text is the "A+" on the folder. It is
  // never drawn mirrored: a character turned to the left holds its folder
  // in a hand that is mirrored back, see drawArmsWithObjectKeptInHand().
  function label(ctx, words, x, y, size, colour) {
    ctx.save();
    ctx.translate(x, y);
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

  // Pass null as `fill` and 0 as `lineWidth` to only build the path.
  function drawBodyBox(ctx, body, fill, lineWidth) {
    box(ctx, body.x, body.y, body.width, body.height, body.radius, fill, lineWidth);
  }

  function drawBody(ctx, colour) {
    drawBodyBox(ctx, BODY, colour, 2.5);
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
    stroke(ctx, "M-4 29 Q0 31.5 4 29", OUTLINE, 2);
    ctx.save();
    ctx.globalAlpha = 0.5;
    circle(ctx, -11, 27, 2.6, "#F2A99B", 0);
    circle(ctx, 11, 27, 2.6, "#F2A99B", 0);
    ctx.restore();
  }

  // The same face in the turned view: eyes, mouth and cheeks sit further to
  // the right. The eye and the cheek on that side are almost at the edge of
  // the head, so they are seen narrower.
  function drawTurnedFace(ctx) {
    drawBareHead(ctx);
    circle(ctx, -6.5 + TURN, 22, 2.4, OUTLINE, 0);
    ctx.beginPath();
    ctx.ellipse(6.2 + TURN, 22, 1.8, 2.4, 0, 0, Math.PI * 2);
    paint(ctx, OUTLINE, null, 0);
    stroke(ctx, "M1.5 29 Q5 31.5 8.5 29", OUTLINE, 2);
    ctx.save();
    ctx.globalAlpha = 0.5;
    circle(ctx, -11 + TURN, 27, 2.6, "#F2A99B", 0);
    ctx.beginPath();
    ctx.ellipse(13.5, 27, 1.7, 2.6, 0, 0, Math.PI * 2);
    paint(ctx, "#F2A99B", null, 0);
    ctx.restore();
  }

  function nothing() {}

  // Draws what sits on the front of the upper body in the turned view: the
  // same drawing as in the portrait, moved to the middle of the turned body.
  function drawOnTurnedBody(ctx, drawFront) {
    ctx.save();
    ctx.translate(TURNED_BODY_MIDDLE, 0);
    drawFront(ctx);
    ctx.restore();
  }

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
  // For the turned view, always drawn turned to the right. The right half
  // of the drawing is the side the character walks to; on the left more of
  // its back is seen (the back of the hair, a bun, a backpack).
  //   turnedLeftHand, turnedRightHand  where the hands are, as [x, y]
  //   handsSwing          true if the hands are free and swing while walking
  //   holdsInRightHand    true if the object is held in the right hand alone.
  //                       It then stays in that hand, on the right of the
  //                       screen, when the character is turned to the left.
  //   turnedBehind(ctx)   drawn behind the body
  //   turnedClothes(ctx)  drawn on the body
  //   turnedObject(ctx)   the thing in the hand
  //   turnedHead(ctx)     hair, hat, glasses, headphones, turned like the face

  var PLAIN_LOOK = {
    body: "#B9B4A6", legs: "#8F8A7D", leftHand: [-22, 65], rightHand: [22, 65],
    behind: nothing, clothes: nothing, object: nothing, head: nothing,
    turnedLeftHand: [-21, 65], turnedRightHand: [21, 65], handsSwing: true,
    turnedBehind: nothing, turnedClothes: nothing, turnedObject: nothing, turnedHead: nothing
  };

  var LOOKS = {
    // Dark blue suit, red tie, briefcase.
    consultant: {
      body: "#26406E", legs: "#1C3156", leftHand: [-22, 65], rightHand: [23, 68],
      behind: nothing,
      clothes: drawShirtAndTie,
      object: drawBriefcase,
      head: function (ctx) {
        shape(ctx, "M-18 19 A18 18 0 0 1 18 19 Q10 7 -3 9 Q-12 10 -18 19 Z", "#3B2F2F", 2);
      },
      turnedLeftHand: [-21, 65], turnedRightHand: [23, 68], holdsInRightHand: true,
      turnedBehind: nothing,
      turnedClothes: function (ctx) {
        drawOnTurnedBody(ctx, drawShirtAndTie);
      },
      turnedObject: drawBriefcase,
      turnedHead: function (ctx) {
        // The parting moves with the face; behind it the hair reaches down
        // to the ear.
        shape(ctx, "M-17 26 A18 18 0 0 1 17 14 Q13 6 3 8 Q-6 9 -9.5 17 Q-11 24 -17 26 Z", "#3B2F2F", 2);
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
      object: drawPhone,
      head: function (ctx) {
        shape(ctx, "M-18 19 A18 18 0 0 1 18 19 Q14 6 0 7 Q-14 6 -18 19 Z", "#8A6A3B", 2);
      },
      turnedLeftHand: [-21, 65], turnedRightHand: [25, 63], holdsInRightHand: true,
      turnedBehind: nothing,
      turnedClothes: function (ctx) {
        // The turned body is narrower than the portrait's, so the vest is
        // too: two halves of the same width with the opening (x -4.5 to 3.5)
        // in the middle of the body.
        shape(ctx, "M-17 48 Q-17 39 -7.5 39 L-4.5 39 L-4.5 79 L-9.5 79 Q-17 79 -17 70 Z", "#3F4A5E", 1.5);
        shape(ctx, "M16 48 Q16 39 6.5 39 L3.5 39 L3.5 79 L8.5 79 Q16 79 16 70 Z", "#3F4A5E", 1.5);
        stroke(ctx, "M-16 52 h11.5 M-16 62 h11.5 M-16 72 h11.5 M3.5 52 h11.5 M3.5 62 h11.5 M3.5 72 h11.5", "#2A3345", 1.5);
      },
      turnedObject: drawPhone,
      turnedHead: function (ctx) {
        shape(ctx, "M-17 26 A18 18 0 0 1 17 14 Q15 5 5 6.5 Q-7 6 -10 17 Q-11.5 24 -17 26 Z", "#8A6A3B", 2);
      }
    },

    // Pink, yellow bucket hat, backpack, lanyard. Both hands are free.
    exchange_student: {
      body: "#F0569B", legs: SKIN, leftHand: [-22, 65], rightHand: [22, 65],
      behind: function (ctx) {
        box(ctx, -27, 36, 54, 36, 12, "#3E8FD0", 2.5);
      },
      clothes: function (ctx) {
        drawStrapsAndLanyard(ctx, BODY);
      },
      object: nothing,
      head: drawBucketHat,
      turnedLeftHand: [-21, 65], turnedRightHand: [21, 65], handsSwing: true,
      turnedBehind: function (ctx) {
        // The backpack on the back shows on the left, behind the shoulder.
        box(ctx, -31, 36, 44, 36, 12, "#3E8FD0", 2.5);
      },
      turnedClothes: function (ctx) {
        drawStrapsAndLanyard(ctx, TURNED_BODY);
      },
      turnedObject: nothing,
      turnedHead: function (ctx) {
        // Under the hat the hair shows at the back of the head.
        shape(ctx, "M-17.6 16 Q-18.6 22 -16.6 27 Q-12 24 -11 15 Z", "#8A5A3B", 2);
        drawTurnedBucketHat(ctx);
      }
    },

    // Turquoise, long blond hair, shell necklace, surfboard printed on the shirt.
    surfer: {
      body: "#159A8C", legs: SKIN, leftHand: [-22, 65], rightHand: [22, 65],
      behind: nothing,
      clothes: function (ctx) {
        box(ctx, -18, 68, 36, 14, 5, "#F08A3C", 2);
        drawShellNecklace(ctx);
        // The long hair falls over the shoulders, so it is drawn before the
        // face and the arms. The front hair is drawn on the face, see head.
        shape(ctx, "M-21 20 Q-22 -1 0 -1 Q22 -1 21 20 L22 40 Q16 45 12.5 37 Q14 31 15.5 25 L-15.5 25 Q-14 31 -12.5 37 Q-16 45 -22 40 Z", "#F2D36B", 2);
        drawSurfboardPrint(ctx);
      },
      object: nothing,
      head: drawSurferFrontHair,
      turnedLeftHand: [-21, 65], turnedRightHand: [20, 65], handsSwing: true,
      turnedBehind: nothing,
      turnedClothes: function (ctx) {
        box(ctx, -17, 68, 33, 14, 5, "#F08A3C", 2);
        // The long hair falls down the back, which shows on the left. On
        // the other side only a short strand is seen. Drawn before the face.
        shape(ctx, "M-22 20 Q-23 -1 0 -1 Q20 -1 20.5 17 L20 25 Q17.8 27.5 16.3 23 L-7 20 L-7 38 Q-13 48 -25 43 Z", "#F2D36B", 2);
        // The hair covers the left shoulder, so the necklace is drawn after
        // it: the necklace lies on top and is seen whole.
        drawOnTurnedBody(ctx, drawShellNecklace);
        drawOnTurnedBody(ctx, drawSurfboardPrint);
      },
      turnedObject: nothing,
      turnedHead: drawTurnedSurferFrontHair
    },

    // Black hoodie with the hood up, laptop covered in stickers.
    founder: {
      body: "#33333D", legs: "#4A5568", shoes: "#FFFFFF", leftHand: [-18, 68], rightHand: [18, 68],
      behind: function (ctx) {
        circle(ctx, 0, 20, 22, "#33333D", 2.5);
      },
      clothes: drawHoodieStrings,
      object: function (ctx) {
        box(ctx, -16, 55, 32, 21, 2.5, "#C9CED6", 2);
        circle(ctx, -6, 63, 3.5, "#F2695C", 0);
        box(ctx, 2, 60, 8, 5, 1, "#FFD23F", 0);
        circle(ctx, 6, 70, 2.2, "#5FA86B", 0);
      },
      head: function (ctx) {
        shape(ctx, "M-19 22 A19 19 0 0 1 19 22 Q13 7 0 7 Q-13 7 -19 22 Z", "#33333D", 2);
      },
      turnedLeftHand: [-14, 68], turnedRightHand: [21, 68],
      turnedBehind: function (ctx) {
        // More of the hood is seen at the back of the head.
        circle(ctx, -2, 20, 22, "#33333D", 2.5);
      },
      turnedClothes: function (ctx) {
        drawOnTurnedBody(ctx, drawHoodieStrings);
      },
      turnedObject: function (ctx) {
        box(ctx, -12, 55, 31, 21, 2.5, "#C9CED6", 2);
        circle(ctx, -2, 63, 3.5, "#F2695C", 0);
        box(ctx, 6, 60, 8, 5, 1, "#FFD23F", 0);
        circle(ctx, 10, 70, 2.2, "#5FA86B", 0);
      },
      turnedHead: function (ctx) {
        // The opening of the hood is turned with the face.
        shape(ctx, "M-19.5 25 A19.5 19.5 0 0 1 18.5 16 Q17 7 6 6.5 Q-7 6.5 -10 19 Q-12 26 -19.5 25 Z", "#33333D", 2);
      }
    },

    // Green cardigan, glasses, hair bun, folder with "A+".
    overachiever: {
      body: "#4E9F5B", legs: "#5E6472", leftHand: [-22, 65], rightHand: [31, 70],
      behind: drawHairBun,
      clothes: drawCollarAndButtons,
      object: drawFolder,
      head: function (ctx) {
        shape(ctx, "M-18 19 A18 18 0 0 1 18 19 Q9 9 0 9 Q-9 9 -18 19 Z", "#5A3E2B", 2);
        drawGlasses(ctx);
      },
      turnedLeftHand: [-21, 65], turnedRightHand: [31, 70], holdsInRightHand: true,
      turnedBehind: function (ctx) {
        // The bun is at the back of the head, so it moves against the face.
        circle(ctx, -8, -2, 8, "#5A3E2B", 2);
      },
      turnedClothes: function (ctx) {
        drawOnTurnedBody(ctx, drawCollarAndButtons);
      },
      turnedObject: drawFolder,
      turnedHead: function (ctx) {
        shape(ctx, "M-17 26 A18 18 0 0 1 17 14 Q12 8 5 8.5 Q-6 9 -9.5 18 Q-11 24 -17 26 Z", "#5A3E2B", 2);
        drawTurnedGlasses(ctx);
      }
    },

    // Orange jacket, messy hair, coffee cup.
    latecomer: {
      body: "#F08A3C", legs: "#3F5F8A", leftHand: [-22, 65], rightHand: [25, 67],
      behind: nothing,
      clothes: drawShirtStripe,
      object: drawCoffeeCup,
      head: function (ctx) {
        shape(ctx, "M-18 19 Q-23 7 -13 4 Q-15 -5 -5 0 Q-2 -9 4 -1 Q11 -8 13 3 Q23 5 18 19 Q10 9 0 11 Q-10 9 -18 19 Z", "#7A4B2A", 2);
      },
      turnedLeftHand: [-21, 65], turnedRightHand: [25, 67], holdsInRightHand: true,
      turnedBehind: nothing,
      turnedClothes: function (ctx) {
        drawOnTurnedBody(ctx, drawShirtStripe);
      },
      turnedObject: drawCoffeeCup,
      turnedHead: function (ctx) {
        shape(ctx, "M-17 26 Q-24 18 -19 10 Q-25 2 -13 3 Q-15 -6 -4 -1 Q-1 -10 6 -2 Q13 -8 14.5 3 Q23 6 17 15 Q12 8 4 10 Q-6 11 -9.5 18 Q-11 24 -17 26 Z", "#7A4B2A", 2);
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
      turnedLeftHand: [-12, 73], turnedRightHand: [21, 73],
      turnedBehind: drawTurnedHeadphonesBehind,
      turnedClothes: nothing,
      turnedObject: function (ctx) {
        box(ctx, -10, 67, 28, 8, 1.5, "#6FA8F0", 1.8);
        box(ctx, -8, 59, 25, 8, 1.5, "#E0483E", 1.8);
        box(ctx, -9, 51, 23, 8, 1.5, "#FFD23F", 1.8);
      },
      turnedHead: function (ctx) {
        shape(ctx, "M-18 28 Q-22 2 0 2 Q20 2 18.5 19 L17 13 Q9 7.5 2 9.5 Q-7 11 -10 20 Q-12 27 -18 28 Z", "#2B2B33", 2);
        drawTurnedHeadphones(ctx);
      }
    }
  };

  // ---- Parts of the looks that need more than a line or two ------------

  // What sits on the front of the upper body. Each is drawn for the middle
  // of the portrait's body (x = 0); drawOnTurnedBody() moves it for the
  // turned view.

  // The Consultant's white shirt, red tie and the lapels of the jacket.
  function drawShirtAndTie(ctx) {
    shape(ctx, "M-9 39 L9 39 L0 63 Z", "#FFFFFF", 1.5);
    shape(ctx, "M-2.8 41 L2.8 41 L3.3 52 L2.1 57.5 L0 63 L-2.1 57.5 L-3.3 52 Z", "#E0483E", 1.2);
    stroke(ctx, "M-9 39 L-2.6 56 M9 39 L2.6 56", "#1C3156", 2.5);
  }

  // The Exchange Student's backpack straps and the lanyard with its card,
  // centred on `body`. The straps come over the shoulders from the
  // backpack and curve back to it at the sides, and the cord goes round
  // the neck. So they are drawn only inside `body` (the clip), and the
  // body's outline is drawn again on top: their ends disappear behind it.
  function drawStrapsAndLanyard(ctx, body) {
    var middle = body.x + body.width / 2;
    ctx.save();
    drawBodyBox(ctx, body, null, 0);
    ctx.clip();
    ctx.translate(middle, 0);
    stroke(ctx, "M-12 30 V54 Q-12 64 -24 68 M12 30 V54 Q12 64 24 68", "#2A6FA8", 5);
    stroke(ctx, "M-7 36 L0 52 L7 36", OUTLINE, 1.5);
    box(ctx, -4, 52, 8, 10, 1.5, "#FFFFFF", 1.5);
    ctx.restore();
    drawBodyBox(ctx, body, null, 2.5);
  }

  // The Surfer's shell necklace.
  function drawShellNecklace(ctx) {
    stroke(ctx, "M-9 41 Q0 50 9 41", OUTLINE, 1.2);
    circle(ctx, -5, 45, 1.8, "#FFFFFF", 0);
    circle(ctx, 0, 46.5, 1.8, "#FFFFFF", 0);
    circle(ctx, 5, 45, 1.8, "#FFFFFF", 0);
  }

  // The two strings of the Founder's hoodie.
  function drawHoodieStrings(ctx) {
    stroke(ctx, "M-5 40 V52 M5 40 V52", "#FFFFFF", 1.8);
  }

  // The Overachiever's white collar and two buttons of the cardigan.
  function drawCollarAndButtons(ctx) {
    shape(ctx, "M-8 39 L8 39 L0 56 Z", "#FFFFFF", 1.5);
    circle(ctx, 0, 62, 1.6, OUTLINE, 0);
    circle(ctx, 0, 70, 1.6, OUTLINE, 0);
  }

  // The white shirt that shows under the Latecomer's open jacket.
  function drawShirtStripe(ctx) {
    box(ctx, -6, 39, 12, 40, 0, "#FFFFFF", 1.5);
  }

  // What is held in a hand.

  // The Consultant's briefcase. It is held in the same place in the portrait and
  // in the turned view.
  function drawBriefcase(ctx) {
    box(ctx, 12, 73, 22, 16, 2.5, "#8A5A3B", 2);
    stroke(ctx, "M18 73 v-5 h10 v5", OUTLINE, 2);
    box(ctx, 21, 79, 4, 3, 0, "#FFD23F", 0); // the lock
  }

  // The Finance Bro's phone with a price chart. It is held in the same place in the portrait and
  // in the turned view.
  function drawPhone(ctx) {
    box(ctx, 19, 42, 13, 22, 2.5, OUTLINE, 0);
    stroke(ctx, "M21.5 58 L24.5 51 L27 54.5 L30 46", "#6BD68A", 1.8);
  }

  // The Overachiever's folder with "A+". It is held in the same place in the portrait and
  // in the turned view.
  function drawFolder(ctx) {
    box(ctx, 7, 54, 24, 30, 2.5, "#FFFFFF", 2);
    stroke(ctx, "M11 61 h15 M11 67 h15 M11 73 h10", "#B9B4A6", 1.5);
    label(ctx, "A+", 19, 82, 7, "#5FA86B");
  }

  // The Latecomer's coffee cup. It is held in the same place in the portrait and
  // in the turned view.
  function drawCoffeeCup(ctx) {
    shape(ctx, "M17 56 L34 56 L32 78 L19 78 Z", "#FFFFFF", 2);
    box(ctx, 16, 52, 19, 5, 2, "#8A5A3B", 1.5);
    box(ctx, 19, 63, 13, 7, 0, "#C9A27A", 0);
  }

  // The Exchange Student's bucket hat. It sits on the head: where the brim
  // crosses them (y = 12), the sides of the rounded crown (x = -17 and 17)
  // lie on the outline of the head. The middle of that 2.5 wide line is at
  // about x = -16.1 and 16.1 there, so x = -17 and 17 are inside it, and
  // the outline runs on into the crown as one line. The brim reaches
  // equally far out on both sides and stays above the eyes (y = 22).
  function drawBucketHat(ctx) {
    shape(ctx, "M-17 12 C-17 -1 -12.5 -5 0 -5 C12.5 -5 17 -1 17 12 Q0 7 -17 12 Z", "#FFD23F", 2);
    drawBucketHatBrim(ctx);
  }

  // The head is not moved in the turned view, so neither is the hat; only
  // the top of its crown leans a little towards the face.
  function drawTurnedBucketHat(ctx) {
    shape(ctx, "M-17 12 C-17 -1 -11 -5 1.5 -5 C13.5 -5 17 -1 17 12 Q0 7 -17 12 Z", "#FFD23F", 2);
    drawBucketHatBrim(ctx);
  }

  // The brim of the hat: a thick dark line with a yellow one on top.
  function drawBucketHatBrim(ctx) {
    stroke(ctx, "M-27 14.5 Q0 6.5 27 14.5", OUTLINE, 5.5);
    ctx.strokeStyle = "#FFD23F";
    ctx.lineWidth = 2.5;
    ctx.stroke(pathOf("M-27 14.5 Q0 6.5 27 14.5"));
  }

  function drawHairBun(ctx) {
    circle(ctx, 0, -3, 8, "#5A3E2B", 2);
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

  // The glasses sit on the turned eyes. The lens at the edge of the head is
  // seen narrower, and of its arm only the start is seen.
  function drawTurnedGlasses(ctx) {
    ctx.save();
    ctx.globalAlpha = 0.35;
    circle(ctx, -6.5 + TURN, 22, 6, "#FFFFFF", 0);
    traceNarrowLens(ctx);
    paint(ctx, "#FFFFFF", null, 0);
    ctx.restore();
    circle(ctx, -6.5 + TURN, 22, 6, null, 2);
    traceNarrowLens(ctx);
    paint(ctx, null, OUTLINE, 2);
    stroke(ctx, "M4.5 22 h1.7 M-7.5 21 L-17 20 M16.4 21 L17.8 20.5", OUTLINE, 2);
  }

  function traceNarrowLens(ctx) {
    ctx.beginPath();
    ctx.ellipse(11.3, 22, 5, 6, 0, 0, Math.PI * 2);
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

  // The headphones turned with the head. The ear at the back of the head
  // is seen, so its cup sits there, on the side of the head at ear height.
  // The far ear and its cup are hidden behind the head. The band runs from
  // the near cup over the top of the head (NEAR_BAND) and then down behind
  // the head to the far ear.
  var NEAR_BAND = "M-15 13 Q-16 -2.5 0 -2.5";
  var WHOLE_BAND = NEAR_BAND + " Q15 -2.5 13 13";

  // A band: a dark line with a coral one on top.
  function drawHeadphoneBand(ctx, svgPath) {
    stroke(ctx, svgPath, OUTLINE, 7);
    ctx.strokeStyle = "#F2695C";
    ctx.lineWidth = 3.5;
    ctx.stroke(pathOf(svgPath));
  }

  // Drawn behind the body and the head: the head hides the part of the
  // band that goes down behind it.
  function drawTurnedHeadphonesBehind(ctx) {
    drawHeadphoneBand(ctx, WHOLE_BAND);
  }

  // Drawn on the head: the near part of the band lies over the band drawn
  // behind. It runs a little past the top of the head, along the first
  // bit of the far half (these short curves lie exactly on it: its first
  // 7 % and 15 %), and ends flat ("butt"). Its coral line runs further
  // than its dark line, so the coral covers the dark end and the band
  // shows no seam where the two parts meet.
  function drawTurnedHeadphones(ctx) {
    ctx.save();
    ctx.lineCap = "butt";
    stroke(ctx, NEAR_BAND + " Q1.05 -2.5 2.02 -2.42", OUTLINE, 7);
    stroke(ctx, NEAR_BAND + " Q2.25 -2.5 4.12 -2.15", "#F2695C", 3.5);
    ctx.restore();
    box(ctx, -20.5, 12.5, 11, 17, 5, "#F2695C", 2);
  }

  // The Surfer's front hair: the fringe and the strands beside the face as
  // one piece, drawn over the edge of the face so that no outline of the
  // head cuts them apart. Its outer edge and the inner edge of the strands
  // lie exactly on those of the long hair (see clothes), and it ends below
  // where the long hair is, so the two read as one head of hair.
  function drawSurferFrontHair(ctx) {
    var outerEdge = "M-21.85 37 L-21 20 Q-22 -1 0 -1 Q22 -1 21 20 L21.85 37";
    var faceEdge = "M12.5 37 Q14 31 15.5 25 L15.5 21 Q7 9 -5 11 Q-13 12 -15.5 21 L-15.5 25 Q-14 31 -12.5 37";
    // The filled piece: the outer edge, along the bottom to the strand on
    // the right, the face edge, and back along the bottom on the left.
    shape(ctx, outerEdge + " L" + faceEdge.slice(1) + " Z", "#F2D36B", 0);
    stroke(ctx, outerEdge + " " + faceEdge, OUTLINE, 2);
  }

  // The same in the turned view. On the side the character is turned to a
  // short strand comes out of the fringe; on the back the hair reaches down
  // to the ear (-17, 26), and below it the long hair goes on. The path is
  // left open: the fill closes it along y = 26 over the long hair, the
  // outline leaves that edge out.
  function drawTurnedSurferFrontHair(ctx) {
    shape(ctx, "M-22.8 26 L-22 20 Q-23 -1 0 -1 Q20 -1 20.5 17 L20 25 Q17.8 27.5 16.3 23 L15.8 17 Q11 7 1 10 Q-7 12 -9.5 19 Q-11.5 25 -17 26", "#F2D36B", 2);
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

  // ---- The turned view and its running cycle ---------------------------
  //
  // One cycle is two steps. At walkPhase 0 the left foot lands in front, at
  // 0.5 the right one. Each foot stays on the ground for GROUND_FRACTION of
  // a step; for the rest of the step both feet are in the air.

  // Where the character is in its cycle, from 0 to 1. Any number is taken:
  // 1.25 is the same moment as 0.25.
  function phaseOf(pose) {
    if (strideOf(pose) === 0) {
      return 0;
    }
    var phase = pose.walkPhase % 1;
    return phase < 0 ? phase + 1 : phase;
  }

  // Where one foot is in its own cycle. `legPhase` runs from 0 to 1; at 0
  // the foot lands in front. It stays on the ground for `groundShare` of
  // the cycle and moves backwards at a steady speed, as the ground moves
  // under the runner. Then it pushes off: it kicks up behind and swings
  // forward to land again. Returns `place`, from 1 (in front) to -1
  // (behind), and `lift`, from 0 (on the ground) to 1 (kicked up highest).
  function runningFoot(legPhase, groundShare) {
    if (legPhase < groundShare) {
      return { place: 1 - 2 * legPhase / groundShare, lift: 0 };
    }
    var inTheAir = (legPhase - groundShare) / (1 - groundShare); // 0 to 1
    // Slow at both ends (3t² - 2t³): the foot stays behind while it kicks
    // up, and comes down gently in front.
    var forward = inTheAir * inTheAir * (3 - 2 * inTheAir);
    return { place: -1 + 2 * forward, lift: kickHeight(inTheAir) };
  }

  // The kick: the foot goes up quickly after it pushed off, is highest at
  // KICK_HIGHEST_AT (35 %) of its time in the air, and then comes down
  // until it lands.
  function kickHeight(inTheAir) {
    if (inTheAir < KICK_HIGHEST_AT) {
      return Math.sin(Math.PI / 2 * inTheAir / KICK_HIGHEST_AT);
    }
    return Math.cos(Math.PI / 2 * (inTheAir - KICK_HIGHEST_AT) / (1 - KICK_HIGHEST_AT));
  }

  // Everything that moves at one moment of the run, in design units and
  // radians. Everything is multiplied by `stride`, so a character that
  // starts or stops changes smoothly between standing and running, and a
  // standing one (stride 0) gets all zeros: it stands exactly as in the
  // portrait's turned view.
  //   leftFootX, rightFootX  how far a foot is in front of its standing place
  //   leftLift, rightLift    how high a foot is off the ground
  //   raised                 how far the body is lifted
  //   lean                   how far the body leans forward
  //   armSwing               from -1 to 1 (times stride): above 0 the hand
  //                          on the front side of the body is in front and
  //                          the one on the back side behind
  //   handRaise, handInward  how much higher and closer to the body the free
  //                          hands are held (the bent arms of a runner)
  function runningMoment(phase, stride) {
    var groundShare = GROUND_FRACTION / 2; // of the whole cycle
    var left = runningFoot(phase, groundShare);
    var right = runningFoot((phase + 0.5) % 1, groundShare);
    var travel = FOOT_TRAVEL * stride;
    // The body is lowest in the middle of a foot's time on the ground
    // (phase groundShare / 2) and highest in the middle of the time in the
    // air, a quarter of a cycle later. Two hops per cycle.
    var hop = HOP * stride;
    return {
      leftFootX: left.place * travel,
      leftLift: left.lift * KICK * stride,
      rightFootX: right.place * travel,
      rightLift: right.lift * KICK * stride,
      raised: hop * (1 - Math.cos(4 * Math.PI * (phase - groundShare / 2))) / 2,
      lean: stride * LEAN,
      // The arms pump against the legs: the right hand is furthest in front
      // when the left foot lands (phase 0).
      armSwing: Math.cos(2 * Math.PI * phase) * stride,
      handRaise: HAND_RAISE * stride,
      handInward: HAND_INWARD * stride
    };
  }

  // How big the steps are, from 0 (none, also when standing) to 1 (full).
  // Full if the character walks and nothing understandable was passed.
  function strideOf(pose) {
    var isWalking = typeof pose.walkPhase === "number" && isFinite(pose.walkPhase);
    if (!isWalking) {
      return 0;
    }
    if (typeof pose.stride !== "number" || isNaN(pose.stride)) {
      return 1;
    }
    return Math.max(0, Math.min(1, pose.stride));
  }

  // A leg is a rounded box that hangs from a hip point. The hip point
  // belongs to the body: it is in the middle of the top of the standing
  // leg (x = -7.5 or 7.5, y = 74), under the body, and rises with it. The
  // leg turns around it towards the ankle, which is where the shoe is, and
  // becomes as long as the way from hip to ankle. So the leg looks fixed to
  // the body: its top stays under the body in every frame and never slides
  // sideways under it, and no gap opens between leg and body. A standing
  // leg hangs straight down: the box from (-13, 74) or (2, 74), 11 wide and
  // 18 high.
  var LEG_WIDTH = 11;
  // The middles of the two standing legs: 7.5 to the left and to the right,
  // so the legs are 4 units apart.
  var HIP_X = 7.5;
  var HIP_Y = 74;
  var LEG_BOTTOM_Y = 92; // on the shoe, which reaches from y = 89 to 97

  // One leg with its shoe. `side` is -1 for the left and 1 for the right
  // one. `footX` is how far the foot is in front of its standing place
  // (behind if below 0) and `lift` how high it is off the ground, both in
  // design units. `raised` is how far the body is lifted right now: the hip
  // goes up with it.
  function drawTurnedLeg(ctx, look, side, footX, lift, raised) {
    // The shoes point a little to the side the character is turned to.
    var shoeX = (side < 0 ? -15 : 1) + SHOE_TURN + footX;
    box(ctx, shoeX, 89 - lift, 14, 8, 4, look.shoes || OUTLINE, look.shoes ? 1.5 : 0);
    var hipX = side * HIP_X;
    var hipY = HIP_Y - raised;
    var toAnkleX = footX;
    var toAnkleY = LEG_BOTTOM_Y - lift - hipY;
    var length = Math.sqrt(toAnkleX * toAnkleX + toAnkleY * toAnkleY);
    ctx.save();
    ctx.translate(hipX, hipY);
    // Turn the box, which points straight down, so that it points to the
    // ankle: rotate(angle) turns "down" (0, 1) into (-sin, cos).
    ctx.rotate(Math.atan2(-toAnkleX, toAnkleY));
    box(ctx, -LEG_WIDTH / 2, 0, LEG_WIDTH, length, 4, look.legs, 2);
    ctx.restore();
  }

  // Where the arms start in the turned view. The body is a little narrower
  // on the side the character is turned to, so the shoulder there is closer
  // to the middle than the one at the back.
  var FRONT_SHOULDER = 15;
  var BACK_SHOULDER = 16;

  // One arm from the shoulder at `shoulderX` to (handX, handY - 3), like
  // drawArm() of the portrait. `side` is -1 if the arm is on the left of
  // the body and 1 if it is on the right: the elbow points that way.
  function drawTurnedArm(ctx, shoulderX, side, handX, handY, colour) {
    var shoulderY = 45;
    var endY = handY - 3;
    ctx.beginPath();
    ctx.moveTo(shoulderX, shoulderY);
    ctx.quadraticCurveTo((shoulderX + handX) / 2 + side * 6, (shoulderY + endY) / 2 + 1, handX, endY);
    paint(ctx, null, OUTLINE, 10.5);
    ctx.strokeStyle = colour;
    ctx.lineWidth = 6.5;
    ctx.stroke();
  }

  // How far a free hand is moved from where it hangs, as [dx, dy]. `side`
  // is -1 for the hand at the back of the body and 1 for the one in front.
  // A runner holds it higher and closer to the body, which bends the arm,
  // and pumps it forward (and up) and back (and down).
  function freeHandMove(side, moment) {
    var forward = side * moment.armSwing; // from -1 (back) to 1 (forward)
    return [
      -side * moment.handInward + forward * HAND_PUMP,
      -moment.handRaise - forward * HAND_PUMP_RISE
    ];
  }

  // The same for a hand that holds something alone: it stays where it is
  // and only makes a part of the pumping, so its object does not fly about.
  function heldHandMove(side, moment) {
    var forward = side * moment.armSwing;
    return [
      forward * HAND_PUMP * HELD_SHARE,
      -forward * HAND_PUMP_RISE * HELD_SHARE
    ];
  }

  // Arms, object and hands of the character as it is drawn turned to the
  // right. The hand at the back is the left one. Free hands pump against
  // the legs; a hand that holds something alone moves only a little, and its
  // object goes with it. What is held with both hands does not swing; it
  // only rises and sinks with the body.
  function drawTurnedArmsObjectAndHands(ctx, look, moment) {
    var backIsFree = look.handsSwing || look.holdsInRightHand;
    var backMove = backIsFree ? freeHandMove(-1, moment) : [0, 0];
    var frontMove = [0, 0];
    if (look.handsSwing) {
      frontMove = freeHandMove(1, moment);
    } else if (look.holdsInRightHand) {
      frontMove = heldHandMove(1, moment);
    }
    var left = [look.turnedLeftHand[0] + backMove[0], look.turnedLeftHand[1] + backMove[1]];
    var right = [look.turnedRightHand[0] + frontMove[0], look.turnedRightHand[1] + frontMove[1]];
    drawTurnedArm(ctx, -BACK_SHOULDER, -1, left[0], left[1], look.body);
    drawTurnedArm(ctx, FRONT_SHOULDER, 1, right[0], right[1], look.body);
    // An object held in one hand moves with that hand. An object held with
    // both hands (or no object) stays where it is on the body.
    ctx.save();
    if (look.holdsInRightHand) {
      ctx.translate(frontMove[0], frontMove[1]);
    }
    look.turnedObject(ctx);
    ctx.restore();
    circle(ctx, left[0], left[1], 5, SKIN, 2);
    circle(ctx, right[0], right[1], 5, SKIN, 2);
  }

  // The same for a character that is turned to the left and holds its
  // object in the right hand. The whole drawing is mirrored at this point.
  // A plain mirror image would put the object into the other hand, so the
  // hand with the object is mirrored back: it is drawn exactly as in the
  // view to the right, on the right of the screen. Only its shoulder moves,
  // because that side of the body is now the back. The free hand goes to
  // the other side, which is the side the character is turned to.
  //
  // So the free hand now moves like the hand in front, and the holding hand
  // like the one at the back. Mirrored back, "forward" is -x for it.
  function drawArmsWithObjectKeptInHand(ctx, look, moment) {
    var freeMove = freeHandMove(1, moment);
    var heldMove = heldHandMove(-1, moment);
    var free = [-look.turnedLeftHand[0] + freeMove[0], look.turnedLeftHand[1] + freeMove[1]];
    var holding = [look.turnedRightHand[0] - heldMove[0], look.turnedRightHand[1] + heldMove[1]];
    drawTurnedArm(ctx, FRONT_SHOULDER, 1, free[0], free[1], look.body);
    circle(ctx, free[0], free[1], 5, SKIN, 2);
    ctx.save();
    ctx.scale(-1, 1); // mirrored back: from here x grows to the right of the screen
    drawTurnedArm(ctx, BACK_SHOULDER, 1, holding[0], holding[1], look.body);
    ctx.save();
    ctx.translate(-heldMove[0], heldMove[1]);
    look.turnedObject(ctx);
    ctx.restore();
    circle(ctx, holding[0], holding[1], 5, SKIN, 2);
    ctx.restore();
  }

  // The turned character. `moment` comes from runningMoment(). `isMirrored`
  // says that the drawing is mirrored right now, so the character is turned
  // to the left.
  function drawTurnedView(ctx, look, moment, isMirrored) {
    var raised = moment.raised;
    // The shadow stays flat on the ground while the body rises above it,
    // so a step reads as a small hop.
    drawShadow(ctx);
    // A running character leans into its direction.
    ctx.translate(0, GROUND_Y);
    ctx.rotate(moment.lean);
    ctx.translate(0, -GROUND_Y);
    // The legs stand on the ground while the body above them rises. They
    // are drawn between the things behind the body and the body itself, so
    // each part needs its own shift upwards.
    ctx.save();
    ctx.translate(0, -raised);
    look.turnedBehind(ctx);
    ctx.restore();
    drawTurnedLeg(ctx, look, -1, moment.leftFootX, moment.leftLift, raised);
    drawTurnedLeg(ctx, look, 1, moment.rightFootX, moment.rightLift, raised);
    ctx.translate(0, -raised);
    drawBodyBox(ctx, TURNED_BODY, look.body, 2.5);
    look.turnedClothes(ctx);
    if (isMirrored && look.holdsInRightHand) {
      drawArmsWithObjectKeptInHand(ctx, look, moment);
    } else {
      drawTurnedArmsObjectAndHands(ctx, look, moment);
    }
    drawTurnedFace(ctx);
    look.turnedHead(ctx);
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
  // With `pose` it is the turned view (the map). `pose` is an object with
  // these fields, each of which may be left out:
  //   mirrored   false or left out: the character is turned to the right.
  //              true: the drawing is mirrored and turned to the left. Only
  //              what is held in one hand stays in that hand.
  //   walkPhase  a number that runs from 0 to 1 during one cycle of the
  //              run (two steps). At 0 the left foot lands in front, at 0.5
  //              the right one (see runningMoment()). world.js lets it run
  //              on the way walked. Leave it out or pass null for a
  //              standing character.
  //   stride     how big the steps are, from 0 (the feet stay down) to 1
  //              (full steps, also when it is left out). world.js lets it
  //              grow and shrink so that starting and stopping look soft.
  // The middle of the standing character stays at (x, y) in both drawings; a
  // running one rises by at most BODY_BOB (3 % of its height) on each step
  // and leans a little into its direction.
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
      var moment = runningMoment(phaseOf(pose), strideOf(pose));
      drawTurnedView(ctx, lookOf(characterId), moment, isMirrored);
    } else {
      drawPortrait(ctx, lookOf(characterId));
    }
    ctx.restore();
  }

  Game.world.characters = characters;
  Game.world.drawCharacter = drawCharacter;
})();
