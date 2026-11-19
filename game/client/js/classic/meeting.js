// The meeting view draws server-owned state. The browser never counts time or
// decides who may write: it only enables the input for a living participant.

window.Game = window.Game || {};
Game.classicMeeting = Game.classicMeeting || {};

(function () {
  "use strict";

  var state = null;
  var ownName = null;
  var canvas;
  var context;
  var screen;
  var form;
  var input;
  var sendButton;
  var hint;

  function setup() {
    screen = document.getElementById("classic-meeting");
    canvas = document.getElementById("classic-meeting-canvas");
    context = canvas.getContext("2d");
    form = document.getElementById("classic-chat-form");
    input = document.getElementById("classic-chat-input");
    sendButton = document.getElementById("classic-chat-send");
    hint = document.getElementById("classic-chat-hint");
    form.addEventListener("submit", sendMessage);
    window.addEventListener("resize", draw);
    Game.net.on("meeting_state", show);
  }

  function setOwnName(name) {
    ownName = typeof name === "string" ? name : null;
    updateInput();
  }

  function show(message) {
    if (!isMeetingState(message)) return;
    state = message;
    screen.hidden = false;
    updateInput();
    draw();
  }

  function hide() {
    state = null;
    screen.hidden = true;
  }

  function isMeetingState(message) {
    return message && ["discussion", "voting", "result"].includes(message.phase)
      && Number.isInteger(message.seconds_left)
      && Array.isArray(message.living)
      && Array.isArray(message.ghosts)
      && Array.isArray(message.messages);
  }

  function updateInput() {
    if (!input) return;
    var mayWrite = Boolean(state && state.phase === "discussion"
      && state.living.includes(ownName));
    input.disabled = !mayWrite;
    sendButton.disabled = !mayWrite;
    if (mayWrite) hint.textContent = "Living players can chat during the discussion.";
    else if (state && state.phase === "voting") hint.textContent = "Chat is closed while the players vote.";
    else if (state && state.phase === "result") hint.textContent = "The vote is over.";
    else hint.textContent = "Ghosts can read the chat but cannot write.";
  }

  function sendMessage(event) {
    event.preventDefault();
    if (!state || input.disabled || input.value.length === 0) return;
    if (Game.net.send({ type: "chat", text: input.value })) input.value = "";
  }

  function draw() {
    if (!state || !canvas || !context) return;
    var scale = window.devicePixelRatio || 1;
    var width = Math.max(320, canvas.clientWidth);
    var height = Math.max(360, canvas.clientHeight);
    canvas.width = Math.floor(width * scale);
    canvas.height = Math.floor(height * scale);
    context.setTransform(scale, 0, 0, scale, 0, 0);
    context.clearRect(0, 0, width, height);
    context.fillStyle = "#F4EFE3";
    context.fillRect(0, 0, width, height);
    context.fillStyle = "#2E2A3B";
    context.font = "800 28px system-ui, sans-serif";
    context.fillText("Meeting", 24, 42);
    context.font = "700 18px system-ui, sans-serif";
    context.fillText(phaseLabel(state.phase), 24, 76);
    context.fillText("Time left: " + state.seconds_left + " s", width - 170, 76);
    drawPlayers("Living", state.living, 24, 112, "#5FA86B");
    drawPlayers("Ghosts", state.ghosts, Math.max(170, width * 0.52), 112, "#8C8795");
    drawChat(width, height);
  }

  function phaseLabel(phase) {
    if (phase === "discussion") return "Discussion";
    if (phase === "voting") return "Voting";
    return "Meeting ended";
  }

  function drawPlayers(title, players, x, y, color) {
    context.fillStyle = color;
    context.font = "700 16px system-ui, sans-serif";
    context.fillText(title, x, y);
    context.fillStyle = "#2E2A3B";
    context.font = "14px system-ui, sans-serif";
    var shown = players.length ? players.join(", ") : "None";
    wrapText(shown, x, y + 24, 260, 18, 3);
  }

  function drawChat(width, height) {
    var top = 210;
    context.strokeStyle = "#2E2A3B";
    context.lineWidth = 2;
    context.beginPath();
    context.moveTo(20, top - 12);
    context.lineTo(width - 20, top - 12);
    context.stroke();
    context.fillStyle = "#2E2A3B";
    context.font = "700 16px system-ui, sans-serif";
    context.fillText("Discussion chat", 24, top + 12);
    var maxRows = Math.max(1, Math.floor((height - top - 24) / 38));
    var messages = state.messages.slice(-maxRows);
    var y = top + 40;
    context.font = "14px system-ui, sans-serif";
    messages.forEach(function (message) {
      context.fillStyle = "#2E2A3B";
      context.font = "700 14px system-ui, sans-serif";
      context.fillText(message.player_id + ":", 24, y);
      context.font = "14px system-ui, sans-serif";
      wrapText(message.text, 120, y, width - 150, 18, 2);
      y += 38;
    });
  }

  function wrapText(text, x, y, maxWidth, lineHeight, maxLines) {
    var words = String(text).split(/\s+/);
    var line = "";
    var lineNumber = 0;
    words.forEach(function (word) {
      var next = line ? line + " " + word : word;
      if (line && context.measureText(next).width > maxWidth) {
        context.fillText(line, x, y + lineNumber * lineHeight);
        lineNumber += 1;
        line = word;
      } else {
        line = next;
      }
    });
    if (line && lineNumber < maxLines) context.fillText(line, x, y + lineNumber * lineHeight);
  }

  Game.classicMeeting.setup = setup;
  Game.classicMeeting.setOwnName = setOwnName;
  Game.classicMeeting.hide = hide;
})();
