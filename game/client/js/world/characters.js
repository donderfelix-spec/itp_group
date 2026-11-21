// Eight campus mascots with distinct silhouettes, shared by the map and lobby.
"use strict";
window.Game = window.Game || {};
Game.world = Game.world || {};

(function () {
  var OUTLINE = "#20212A";
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


  var paths = new Map();

  function shape(ctx, path, fill) {
    if (!paths.has(path)) {
      paths.set(path, new Path2D(path));
    }
    path = paths.get(path);
    ctx.fillStyle = fill;
    ctx.strokeStyle = OUTLINE;
    ctx.lineWidth = 4;
    ctx.fill(path);
    ctx.stroke(path);
  }

  function box(ctx, x, y, width, height, radius, fill) {
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.arcTo(x + width, y, x + width, y + height, radius);
    ctx.arcTo(x + width, y + height, x, y + height, radius);
    ctx.arcTo(x, y + height, x, y, radius);
    ctx.arcTo(x, y, x + width, y, radius);
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.strokeStyle = OUTLINE;
    ctx.lineWidth = 4;
    ctx.fill();
    ctx.stroke();
  }

  // Paths are constructed once, rather than parsed on every animation frame.
  var bodies = {
    consultant: "M-17 51 L17 51 L19 80 L-19 80 Z",
    finance_bro: "M-22 51 L22 51 L16 80 L-16 80 Z",
    exchange_student: "M-15 49 Q-27 62 -21 81 L21 81 Q27 62 15 49 Z",
    surfer: "M-12 48 L12 48 L15 80 L-15 80 Z",
    founder: "M-18 49 Q-29 57 -25 78 Q0 89 25 78 Q29 57 18 49 Z",
    overachiever: "M-12 50 L12 50 L25 81 L-25 81 Z",
    latecomer: "M-18 51 L17 51 L22 78 L-13 83 Z",
    library_local: "M-17 52 L17 52 L20 81 L-20 81 Z"
  };
  // Head dimensions and materials make the characters readable in silhouette.
  var heads = {
    consultant: { x: -23, y: 10, w: 46, h: 34, r: 2, fill: "#D8B98A" },
    finance_bro: { x: -19, y: 0, w: 38, h: 47, r: 5, fill: "#667C98" },
    exchange_student: { x: -25, y: 14, w: 50, h: 31, r: 7, fill: "#F9B7D3" },
    surfer: { x: -16, y: 2, w: 32, h: 45, r: 15, fill: "#F6D874" },
    founder: { x: -28, y: 9, w: 56, h: 37, r: 12, fill: "#33333D" },
    overachiever: { x: -21, y: 6, w: 42, h: 40, r: 3, fill: "#F4EFE3" },
    latecomer: { x: -19, y: 10, w: 38, h: 36, r: 5, fill: "#F4EFE3" },
    library_local: { x: -23, y: 8, w: 46, h: 38, r: 2, fill: "#BDA5E4" }
  };
  var crown = "M-22 6 L-24 -3 L-10 1 L0 -7 L10 1 L24 -3 L22 6 Z";
  var tie = "M-1 53 L7 53 L5 59 L9 70 L3 76 L-2 70 L1 59 Z";
  var hat = "M-23 18 L-17 4 Q0 -5 17 4 L22 18 Z";

  // Cadence, swing and lean are cosmetic; server movement speed stays the same.
  var movement = {
    consultant: { cadence: 190, swing: 0.6, lean: 0.015, eyes: 8 },
    finance_bro: { cadence: 160, swing: 0.75, lean: -0.03, eyes: 6 },
    exchange_student: { cadence: 170, swing: 1.15, lean: 0.04, eyes: 11 },
    surfer: { cadence: 230, swing: 0.8, lean: -0.09, eyes: 5 },
    founder: { cadence: 180, swing: 0.55, lean: 0.06, eyes: 7 },
    overachiever: { cadence: 155, swing: 0.65, lean: 0, eyes: 10 },
    latecomer: { cadence: 115, swing: 1.3, lean: 0.12, eyes: 12 },
    library_local: { cadence: 220, swing: 0.45, lean: -0.02, eyes: 6 }
  };

  function drawAccessory(ctx, id, time, walking, step) {
    var idle = walking ? 0 : Math.sin(time / 650);
    // Accessories react independently of the torso and head.
    ctx.save();
    ctx.translate(0, walking ? -Math.abs(step) * 2 : idle);
    ctx.rotate(walking ? step * 0.025 : idle * 0.012);
    switch (id) {
      case "consultant":
        box(ctx, -11, 3, 22, 7, 2, "#9B653F");
        shape(ctx, tie, "#ED5A56");
        ctx.translate(step * 3, 0);
        box(ctx, 17, 64, 20, 17, 3, "#9B653F");
        break;
      case "finance_bro":
        // A rising chart above the eyes gives the tall calculator its own face.
        ctx.beginPath();
        ctx.moveTo(-10, 13);
        ctx.lineTo(-3, 9);
        ctx.lineTo(3, 12);
        ctx.lineTo(10, 5);
        ctx.strokeStyle = "#76E7AA";
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.translate(0, idle * 4);
        box(ctx, 18, 53, 13, 21, 3, "#344154");
        box(ctx, 21, 57, 7, 10, 1, "#76E7AA");
        break;
      case "exchange_student":
        shape(ctx, hat, "#FFD23F");
        box(ctx, -27, 16, 55, 6, 3, "#FFD23F");
        break;
      case "surfer":
        // A full-height board is recognisable even in a tiny lobby icon.
        ctx.beginPath();
        ctx.ellipse(-25, 54, 9, 32, -0.15, 0, Math.PI * 2);
        ctx.fillStyle = "#FFD23F";
        ctx.fill();
        ctx.strokeStyle = OUTLINE;
        ctx.lineWidth = 3;
        ctx.stroke();
        box(ctx, -28, 38, 6, 30, 2, "#F2695C");
        break;
      case "founder":
        // Two asymmetric aerials distinguish the broad, hooded laptop robot.
        box(ctx, -23, 1, 8, 11, 3, "#F2695C");
        box(ctx, 13, -3, 8, 14, 3, "#FFD23F");
        box(ctx, -15, 60, 34, 19, 3, "#C9CED6");
        box(ctx, -5, 65, 8, 6, 2, "#F2695C");
        // Alternating hands tap at the laptop during an idle pause.
        box(ctx, -14, 75 + idle * 2, 8, 5, 2, "#F4EFE3");
        box(ctx, 8, 75 - idle * 2, 8, 5, 2, "#F4EFE3");
        break;
      case "overachiever":
        shape(ctx, crown, "#FFD23F");
        box(ctx, 15, 56, 19, 26, 2, "#F4EFE3");
        box(ctx, 29, 60, 6, 5, 1, "#FFD23F");
        ctx.beginPath();
        ctx.moveTo(19, 68);
        ctx.lineTo(22, 71);
        ctx.lineTo(28, 64 + idle);
        ctx.strokeStyle = "#4E9F5B";
        ctx.lineWidth = 2;
        ctx.stroke();
        break;
      case "latecomer":
        // The head is a takeaway cup, with a large handle and a coffee lid.
        box(ctx, 19, 18, 12, 19, 5, "#F08A3C");
        box(ctx, -23, 5, 46, 8, 3, "#9B653F");
        ctx.beginPath();
        ctx.moveTo(-8, 0);
        ctx.quadraticCurveTo(-15 + Math.sin(time / 350) * 3, -5, -8, -9);
        ctx.moveTo(7, 0);
        ctx.quadraticCurveTo(Math.sin(time / 400) * 3, -5, 7, -9);
        ctx.strokeStyle = "#9BACA9";
        ctx.lineWidth = 3;
        ctx.stroke();
        box(ctx, 18, 56, 15, 22, 3, "#F4EFE3");
        box(ctx, 16, 53, 19, 6, 2, "#9B653F");
        break;
      case "library_local":
        box(ctx, -26, 2, 49, 8, 2, "#E99078");
        box(ctx, -21, -6, 43, 8, 2, "#FFD23F");
        box(ctx, -16, 56, 33, 9, 2, "#9CD3E6");
        box(ctx, -20, 66, 38, 9, 2, "#F4EFE3");
        box(ctx, -17, 76, 34, 8, 2, "#E99078");
        ctx.beginPath();
        ctx.arc(2, 35, 24, Math.PI, 0);
        ctx.strokeStyle = OUTLINE;
        ctx.lineWidth = 7;
        ctx.stroke();
        box(ctx, -26, 28, 10, 21, 5, "#F2695C");
        box(ctx, 23, 28, 10, 21, 5, "#F2695C");
        break;
    }
    ctx.restore();
  }

  function drawLeg(ctx, x, swing) {
    ctx.save();
    ctx.translate(x, 77);
    ctx.rotate(swing * 0.32);
    box(ctx, -5, 0, 10, 14, 3, "#F4EFE3");
    box(ctx, -8, 11, 18, 7, 3, OUTLINE);
    ctx.restore();
  }

  function drawArm(ctx, x, swing, colour) {
    ctx.save();
    ctx.translate(x, 55);
    ctx.rotate(swing * 0.4);
    box(ctx, -4.5, 0, 9, 22, 4, colour);
    ctx.restore();
  }

  function drawCharacter(ctx, characterId, x, y, size, stride, motion) {
    if (!ctx || !isFinite(x) || !isFinite(y) || !isFinite(size) || size <= 0) {
      return;
    }
    var character = characters.find(function (entry) { return entry.id === characterId; });
    var colour = character ? character.colour : "#9296A0";
    // Lobby previews omit stride and keep their neutral pose.
    var pose = stride && typeof stride === "object" ? stride : null;
    if (pose) {
      motion = { time: motion && motion.time || 0, walking: pose.walkPhase != null && pose.stride > 0, facing: motion && motion.facing || "side" };
      stride = pose.walkPhase === null ? 0 : Math.sin(pose.walkPhase * Math.PI * 2) * pose.stride;
    }
    var profile = movement[characterId] || movement.consultant;
    var time = motion && Number.isFinite(motion.time) ? motion.time : 0;
    var walking = motion ? motion.walking === true : !!stride;
    var facing = motion ? motion.facing : "front";
    var rawStep = Number.isFinite(stride) ? Math.max(-1, Math.min(1, stride)) : 0;
    var step = (pose ? rawStep : (motion ? (walking ? Math.sin(time / profile.cadence) : 0) : rawStep)) * profile.swing;
    var idle = motion && !walking ? Math.sin(time / 900) : 0;
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(pose && pose.mirrored ? -size / 104 : size / 104, size / 104);
    ctx.translate(0, -48);
    ctx.lineJoin = "round";
    ctx.lineCap = "round";

    ctx.beginPath();
    ctx.ellipse(0, 93, 29, 6, 0, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(32,33,42,0.22)";
    ctx.fill();
    ctx.save();
    ctx.translate(0, 77);
    ctx.rotate(walking ? profile.lean + step * 0.018 : idle * 0.018);
    ctx.translate(0, -77);
    // Opposite limbs swing together, pivoting from the hips and shoulders.
    drawLeg(ctx, -10, step);
    drawLeg(ctx, 10, -step);
    drawArm(ctx, -23, -step, colour);
    drawArm(ctx, 23, step, colour);
    shape(ctx, bodies[characterId] || bodies.consultant, colour);
    box(ctx, -5, 43, 10, 11, 2, "#9BACA9");

    ctx.save();
    ctx.translate(0, 47);
    ctx.rotate(step * 0.065 + idle * 0.035);
    ctx.translate(0, -47);
    var head = heads[characterId] || heads.consultant;
    box(ctx, head.x, head.y, head.w, head.h, head.r, head.fill);
    if (facing === "back") {
      // A casing seam and a colour-coded backpack identify the rear view.
      box(ctx, -12, head.y + 12, 24, 5, 2, "#9BACA9");
      box(ctx, -13, 54, 26, 24, 5, colour);
      box(ctx, -8, 62, 16, 9, 2, "#F4EFE3");
    } else {
      var eyeY = head.y + head.h * 0.55;
      var gaze = facing === "side" ? 5 : 0;
      var blink = time > 0 && (time + characters.indexOf(character) * 347) % 3900 < 140;
      var eyeHeight = blink ? 2 : profile.eyes;
      // Looking down at an accessory gives the idle actions an expression.
      var glance = !walking && (characterId === "finance_bro" || characterId === "founder") ? idle * 2 : 0;
      box(ctx, -13 + gaze, eyeY - eyeHeight / 2 + glance, 8, eyeHeight, Math.min(3, eyeHeight / 2), OUTLINE);
      box(ctx, 5 + gaze, eyeY - eyeHeight / 2 + glance, 8, eyeHeight, Math.min(3, eyeHeight / 2), OUTLINE);
      if (!blink) {
        ctx.fillStyle = "#FFFFFF";
        ctx.fillRect(-11 + gaze, eyeY - 2 + glance, 3, 3);
        ctx.fillRect(7 + gaze, eyeY - 2 + glance, 3, 3);
      }
    }
    ctx.restore();
    if (facing !== "back") {
      drawAccessory(ctx, characterId, time, walking, step);
    }
    ctx.restore();
    ctx.restore();
  }

  Game.world.characters = characters;
  Game.world.drawCharacter = drawCharacter;
})();
