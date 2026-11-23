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
  var skipOptions;
  var skipStatus;
  var skipButton;
  var voteListSignature = "";
  // True from a vote or Skip click until the next meeting_state arrives.
  // A second click before then is ignored, so a double click cannot take
  // back the vote (or the Skip) it just cast.
  var waitingForMeeting = false;
  var resultCloseTimer = null;
  var resultShown = false;
  // The window stays this long after any result, then the round goes on.
  var RESULT_MILLISECONDS = 1800;

  function setup() {
    screen = document.getElementById("classic-meeting");
    canvas = document.getElementById("classic-meeting-canvas");
    context = canvas.getContext("2d");
    form = document.getElementById("classic-chat-form");
    input = document.getElementById("classic-chat-input");
    sendButton = document.getElementById("classic-chat-send");
    // The meeting covers the panel with "Leave lobby"; this button does the
    // same, so a player can leave during a meeting too (final audit, S-201).
    var leave = document.getElementById("classic-meeting-leave");
    if (leave) leave.addEventListener("click", function () { document.getElementById("lobby-leave").click(); });
    hint = document.getElementById("classic-chat-hint");
    voteOptions = document.getElementById("classic-vote-options");
    votePlayers = document.getElementById("classic-vote-players");
    voteResult = document.getElementById("classic-vote-result");
    skipOptions = document.getElementById("classic-skip-options");
    skipStatus = document.getElementById("classic-skip-status");
    skipButton = document.getElementById("classic-skip-discussion");
    form.addEventListener("submit", sendMessage);
    skipButton.addEventListener("click", skipDiscussion);
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
    waitingForMeeting = false;
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
    updateSkip();
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
    waitingForMeeting = false;
    voteListSignature = "";
    screen.hidden = true;
  }

  function isMeetingState(message) {
    return message && ["discussion", "voting", "result"].includes(message.phase)
      && Number.isInteger(message.seconds_left)
      && Array.isArray(message.living)
      && Array.isArray(message.ghosts)
      && Array.isArray(message.messages)
      && Array.isArray(message.voted)
      && (message.skip_voted === undefined || Array.isArray(message.skip_voted));
  }

  function updateSkip() {
    var skippable = votingIsOpen();
    skipOptions.hidden = !skippable;
    if (!skippable) return;
    var skipVotes = skipVotesOf(state);
    var agreed = skipVotes.length;
    var total = state.living.length;
    var ownAgreed = skipVotes.includes(ownName);
    skipStatus.textContent = agreed + " / " + Math.ceil(total * 0.75) + " Skip votes to end voting early.";
    skipButton.disabled = !state.living.includes(ownName);
    skipButton.textContent = ownAgreed ? "Undo Skip" : "Skip";
    skipButton.setAttribute("aria-pressed", String(ownAgreed));
  }

  function skipVotesOf(message) {
    return message && Array.isArray(message.skip_voted) ? message.skip_voted : [];
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

  function votingIsOpen() {
    return Boolean(state && (
      state.phase === "voting" || (state.phase === "discussion" && state.reason === "report")
    ));
  }

  function updateVoting() {
    var voting = votingIsOpen();
    voteOptions.hidden = !voting;
    if (!voting) return;
    var signature = state.living.join("\u0000");
    if (signature !== voteListSignature) {
      voteListSignature = signature;
      votePlayers.replaceChildren();
      state.living.forEach(function (playerId) {
        votePlayers.append(makeVoteButton(playerId));
      });
    }
    var voteTargets = voteTargetsOf(state);
    var selectedTarget = voteTargets[ownName];
    Array.from(votePlayers.children).forEach(function (button) {
      button.disabled = !state.living.includes(ownName);
      var selected = button.dataset.targetId === selectedTarget;
      button.classList.toggle("classic-vote-player-selected", selected);
      button.setAttribute("aria-pressed", selected ? "true" : "false");
      updateVoteCount(button, voteTargets);
    });
  }

  // One button per living player: a letter, the name and the number of
  // votes. Every button has the same size in a fixed grid (style.css), so
  // nothing in the window moves when votes come, change or are taken back.
  function makeVoteButton(playerId) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "classic-vote-player";
    button.dataset.targetId = playerId;
    var avatar = document.createElement("span");
    avatar.className = "classic-vote-avatar";
    avatar.textContent = playerId.charAt(0).toUpperCase();
    // A long name ends in "…"; the whole name is in the button's title.
    var name = document.createElement("span");
    name.className = "classic-vote-name";
    name.textContent = playerId;
    var count = document.createElement("span");
    count.className = "classic-vote-count";
    // The button's label already says who voted, so a screen reader skips the number.
    count.setAttribute("aria-hidden", "true");
    button.append(avatar, name, count);
    button.addEventListener("click", function () { castVote(playerId); });
    return button;
  }

  function voteTargetsOf(message) {
    return message && message.vote_targets && typeof message.vote_targets === "object"
      ? message.vote_targets : {};
  }

  // The names of the players who voted for this target, in alphabetical
  // order, so the label does not change when the server lists them differently.
  function votersFor(targetId, voteTargets) {
    return Object.keys(voteTargets).filter(function (voterId) {
      return voteTargets[voterId] === targetId;
    }).sort();
  }

  // Votes are public (S-160): the count field shows how many, the title and
  // the label for screen readers say who, e.g. "Bo — votes: Ana, Cy".
  function updateVoteCount(button, voteTargets) {
    var count = button.children[2];
    if (!count) return;
    var targetId = button.dataset.targetId;
    var voters = votersFor(targetId, voteTargets);
    count.textContent = String(voters.length);
    count.classList.toggle("classic-vote-count-zero", voters.length === 0);
    var label = targetId + " — " + (voters.length ? "votes: " + voters.join(", ") : "no votes");
    button.title = label;
    button.setAttribute("aria-label", label);
  }

  function skipDiscussion() {
    if (waitingForMeeting || !votingIsOpen() || !state.living.includes(ownName)) return;
    waitingForMeeting = Game.net.send({ type: "skip_discussion" });
  }

  function castVote(targetId) {
    if (waitingForMeeting || !votingIsOpen() || !state.living.includes(ownName)) return;
    waitingForMeeting = Game.net.send({ type: "vote", target_id: targetId });
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
    var winners = { HP: "High Performers win.", FR: "Free Riders win." };
    if (winners[state.winner]) voteResult.textContent += " " + winners[state.winner];
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

  // Where the parts of the canvas go. The canvas is the part of the window
  // that shrinks (style.css), so a short canvas gets a compact layout that
  // leaves room for the chat. All numbers are CSS pixels from the top.
  var ROOMY_LAYOUT = {
    titleFont: "800 28px", titleY: 42, phaseFont: "700 18px", phaseY: 76,
    reasonFont: "700 15px", reasonY: 101, playersY: 132, playerRows: 3,
    chatTop: 230, chatHeading: true,
  };
  var COMPACT_LAYOUT = {
    titleFont: "800 20px", titleY: 28, phaseFont: "700 15px", phaseY: 50,
    reasonFont: "700 13px", reasonY: 68, playersY: 90, playerRows: 1,
    chatTop: 134, chatHeading: false,
  };
  // Below this height the roomy layout would leave room for fewer than two
  // chat messages.
  var COMPACT_BELOW = 340;

  function draw() {
    if (!state || !canvas || !context) return;
    // Drawn at the size the canvas has on screen, so it stays sharp.
    var scale = window.devicePixelRatio || 1;
    var width = Math.max(1, canvas.clientWidth);
    var height = Math.max(1, canvas.clientHeight);
    canvas.width = Math.floor(width * scale);
    canvas.height = Math.floor(height * scale);
    context.setTransform(scale, 0, 0, scale, 0, 0);
    context.clearRect(0, 0, width, height);
    context.fillStyle = "#F4EFE3";
    context.fillRect(0, 0, width, height);
    var layout = height < COMPACT_BELOW ? COMPACT_LAYOUT : ROOMY_LAYOUT;
    context.fillStyle = "#2E2A3B";
    context.font = layout.titleFont + " system-ui, sans-serif";
    context.fillText("Meeting", 24, layout.titleY);
    context.font = layout.phaseFont + " system-ui, sans-serif";
    context.fillText(phaseLabel(state.phase), 24, layout.phaseY);
    var timeLeft = "Time left: " + state.seconds_left + " s";
    context.fillText(timeLeft, width - 24 - context.measureText(timeLeft).width, layout.phaseY);
    var trigger = state.trigger_player_id ? " by " + state.trigger_player_id : "";
    var reasonLabel = state.reason === "report" ? "Report" : state.reason === "emergency" ? "Emergency" : "Meeting";
    context.font = layout.reasonFont + " system-ui, sans-serif";
    context.fillText(reasonLabel + trigger, 24, layout.reasonY);
    var listWidth = Math.max(100, Math.min(260, width * 0.52 - 40));
    drawPlayers("Living", state.living, 24, layout.playersY, "#5FA86B", listWidth, layout.playerRows);
    drawPlayers("Dead players", state.ghosts, Math.max(170, width * 0.52), layout.playersY, "#8C8795",
      listWidth, layout.playerRows);
    drawChat(width, height, layout);
  }

  function phaseLabel(phase) {
    if (phase === "discussion") return "Discussion";
    if (phase === "voting") return "Voting";
    return "Meeting ended";
  }

  function drawPlayers(title, players, x, y, color, maxWidth, maxRows) {
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
      if (cursorX > x && cursorX + width > x + maxWidth) {
        cursorX = x;
        row += 1;
      }
      if (row >= maxRows) return;
      context.fillStyle = ownIsFreeRider && playerId === ownName ? "#C43E3E" : "#2E2A3B";
      context.fillText(label, cursorX, y + 24 + row * 18);
      cursorX += width;
    });
  }

  function drawChat(width, height, layout) {
    var top = layout.chatTop;
    context.strokeStyle = "#2E2A3B";
    context.lineWidth = 2;
    context.beginPath();
    context.moveTo(20, top - 12);
    context.lineTo(width - 20, top - 12);
    context.stroke();
    context.fillStyle = "#2E2A3B";
    var firstMessageY = top + 12;
    if (layout.chatHeading) {
      context.font = "700 16px system-ui, sans-serif";
      context.fillText("Discussion chat", 24, top + 12);
      firstMessageY = top + 40;
    }
    // A message takes up to two lines; only messages that fit are drawn,
    // the newest ones.
    var maxRows = Math.max(1, Math.floor((height - firstMessageY + 14) / 38));
    var messages = state.messages.slice(-maxRows);
    var y = firstMessageY;
    var textX = Math.min(120, Math.floor(width * 0.3));
    messages.forEach(function (message) {
      context.fillStyle = "#2E2A3B";
      context.font = "700 14px system-ui, sans-serif";
      context.fillText(message.player_id + ":", 24, y);
      context.font = "14px system-ui, sans-serif";
      wrapText(message.text, textX, y, width - textX - 24, 18, 2);
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
