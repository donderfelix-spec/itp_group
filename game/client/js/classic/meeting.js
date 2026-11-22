// The meeting view draws server-owned state. The browser never counts time or
// decides who may write: it only enables the input for a living participant.

window.Game = window.Game || {};
Game.classicMeeting = Game.classicMeeting || {};

(function () {
  "use strict";

  var state = null;
  var ownName = null;
  var ownIsFreeRider = false;
  var canvas;
  var context;
  var screen;
  var form;
  var input;
  var sendButton;
  var hint;
  var voteOptions;
  var votePlayers;
  var voteResult;
  var voteListSignature = "";
  var pendingVoteTarget = null;
  var resultCloseTimer = null;
  var resultShown = false;
  // The window stays this long after any result, then the round goes on.
  var RESULT_MILLISECONDS = 1800;
  // The vote for nobody: the same value as SKIP_VOTE in server/protocol.py.
  var SKIP_VOTE = "";

  function setup() {
    screen = document.getElementById("classic-meeting");
    canvas = document.getElementById("classic-meeting-canvas");
    context = canvas.getContext("2d");
    form = document.getElementById("classic-chat-form");
    input = document.getElementById("classic-chat-input");
    sendButton = document.getElementById("classic-chat-send");
    hint = document.getElementById("classic-chat-hint");
    voteOptions = document.getElementById("classic-vote-options");
    votePlayers = document.getElementById("classic-vote-players");
    voteResult = document.getElementById("classic-vote-result");
    form.addEventListener("submit", sendMessage);
    window.addEventListener("resize", draw);
    Game.net.on("meeting_state", show);
  }

  function setOwnName(name) {
    ownName = typeof name === "string" ? name : null;
    updateInput();
    draw();
  }

  function setOwnFreeRider(value) {
    ownIsFreeRider = value === true;
    draw();
  }

  function show(message) {
    if (!isMeetingState(message)) return;
    // A result is shown once: a later copy of the same result (the server
    // may send the snapshot again) must not open the closed window again.
    if (message.phase === "result") {
      if (resultShown) return;
      resultShown = true;
    } else {
      resultShown = false;
    }
    cancelResultClose();
    state = message;
    // A reported sheet stays visible, but can no longer start a meeting.
    if (
      message.reason === "report" &&
      typeof message.reported_sheet_id === "string" &&
      Game.world && typeof Game.world.markBloodSheetReported === "function"
    ) {
      Game.world.markBloodSheetReported(message.reported_sheet_id);
    }
    screen.hidden = false;
    holdTheCharacter(message.phase !== "result");
    updateInput();
    updateVoting();
    updateVoteResult();
    if (message.phase === "result") {
      resultCloseTimer = window.setTimeout(hide, RESULT_MILLISECONDS);
    }
    draw();
  }

  // During discussion and vote the own character stands still, like while a
  // minigame is open (Game.world.setInputPaused, S-121). It walks again once
  // the result is shown or the meeting is gone, unless a minigame is open.
  function holdTheCharacter(hold) {
    if (!Game.world || typeof Game.world.setInputPaused !== "function") return;
    if (!hold && Game.minigames && typeof Game.minigames.isOpen === "function" && Game.minigames.isOpen()) return;
    Game.world.setInputPaused(hold);
  }

  function hide() {
    cancelResultClose();
    if (state !== null) holdTheCharacter(false);
    state = null;
    pendingVoteTarget = null;
    voteListSignature = "";
    screen.hidden = true;
  }

  function isMeetingState(message) {
    return message && ["discussion", "voting", "result"].includes(message.phase)
      && Number.isInteger(message.seconds_left)
      && Array.isArray(message.living)
      && Array.isArray(message.ghosts)
      && Array.isArray(message.messages)
      && Array.isArray(message.voted);
  }

  function updateInput() {
    if (!input) return;
    var mayWrite = Boolean(state && state.phase === "discussion"
      && state.living.includes(ownName));
    input.disabled = !mayWrite;
    sendButton.disabled = !mayWrite;
    if (mayWrite) hint.textContent = "Living players can chat during the discussion.";
    else if (state && state.phase === "voting") hint.textContent = "Chat is closed. Choose one living player to eject, or Skip.";
    else if (state && state.phase === "result") hint.textContent = "The vote is over.";
    else hint.textContent = "Ghosts can read the chat but cannot write.";
  }

  function updateVoting() {
    var voting = Boolean(state && state.phase === "voting");
    voteOptions.hidden = !voting;
    if (!voting) {
      if (state && state.phase === "result") pendingVoteTarget = null;
      return;
    }
    var signature = state.living.join("\u0000");
    if (signature !== voteListSignature) {
      voteListSignature = signature;
      votePlayers.replaceChildren();
      state.living.forEach(function (playerId) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "classic-vote-player";
        button.dataset.targetId = playerId;
        var avatar = document.createElement("span");
        avatar.className = "classic-vote-avatar";
        avatar.textContent = playerId.charAt(0).toUpperCase();
        var name = document.createElement("span");
        name.textContent = playerId;
        button.append(avatar, name);
        button.addEventListener("click", function () { castVote(playerId); });
        votePlayers.append(button);
      });
      votePlayers.append(skipButton());
    }
    var hasVoted = state.voted.includes(ownName) || pendingVoteTarget !== null;
    Array.from(votePlayers.children).forEach(function (button) {
      button.disabled = !state.living.includes(ownName) || hasVoted;
    });
    if (state.voted.includes(ownName)) pendingVoteTarget = null;
  }

  // "Skip" is a vote like the others: secret and final (DESIGN.md 5.6).
  function skipButton() {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "classic-vote-player classic-vote-skip";
    button.dataset.targetId = SKIP_VOTE;
    button.textContent = "Skip";
    button.addEventListener("click", function () { castVote(SKIP_VOTE); });
    return button;
  }

  function castVote(targetId) {
    if (!state || state.phase !== "voting" || !state.living.includes(ownName)
      || state.voted.includes(ownName) || pendingVoteTarget !== null) return;
    if (Game.net.send({ type: "vote", target_id: targetId })) {
      pendingVoteTarget = targetId;
      updateVoting();
    }
  }

  function updateVoteResult() {
    var result = state && state.phase === "result";
    voteResult.hidden = !result;
    if (!result) return;
    if (!state.ejected_id || state.tie) {
      voteResult.textContent = "No one was ejected.";
    } else if (state.revealed_role === "FR") {
      voteResult.textContent = state.ejected_id + " was a Free Rider.";
    } else {
      voteResult.textContent = state.ejected_id + " was not a Free Rider.";
    }
    if (state.winner) voteResult.textContent += " " + state.winner + " wins.";
  }

  function cancelResultClose() {
    if (resultCloseTimer !== null) {
      window.clearTimeout(resultCloseTimer);
      resultCloseTimer = null;
    }
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
    var trigger = state.trigger_player_id ? " by " + state.trigger_player_id : "";
    var reasonLabel = state.reason === "report" ? "Report" : state.reason === "emergency" ? "Emergency" : "Meeting";
    context.font = "700 15px system-ui, sans-serif";
    context.fillText(reasonLabel + trigger, 24, 101);
    drawPlayers("Living", state.living, 24, 132, "#5FA86B");
    drawPlayers("Dead players", state.ghosts, Math.max(170, width * 0.52), 132, "#8C8795");
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
    context.font = "14px system-ui, sans-serif";
    if (!players.length) {
      context.fillStyle = "#2E2A3B";
      context.fillText("None", x, y + 24);
      return;
    }
    var cursorX = x;
    var row = 0;
    players.forEach(function (playerId, index) {
      var label = playerId + (index === players.length - 1 ? "" : ", ");
      var width = context.measureText(label).width;
      if (cursorX > x && cursorX + width > x + 260) {
        cursorX = x;
        row += 1;
      }
      if (row >= 3) return;
      context.fillStyle = ownIsFreeRider && playerId === ownName ? "#C43E3E" : "#2E2A3B";
      context.fillText(label, cursorX, y + 24 + row * 18);
      cursorX += width;
    });
  }

  function drawChat(width, height) {
    var top = 230;
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
  Game.classicMeeting.setOwnFreeRider = setOwnFreeRider;
  Game.classicMeeting.hide = hide;
})();
