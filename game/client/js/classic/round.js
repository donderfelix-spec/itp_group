// Displays private role cards and shared Classic progress and round results.
window.Game = window.Game || {};
Game.classicRound = Game.classicRound || {};

(function () {
  "use strict";
  var roleScreen, roleName, roleInstructions, rolePartners, ownNameLabel;
  var endScreen, winner, reason, roles, stats, newRound, hostHint;
  var progressPanel, progressLabel, progressTrack, progressFill;
  var ownName = null;
  var ownIsFreeRider = false;
  var roundIsActive = false;
  var isHost = false;
  var roleTimer = null;

  function setup() {
    roleScreen = document.getElementById("classic-role-card");
    roleName = document.getElementById("classic-role-name");
    roleInstructions = document.getElementById("classic-role-instructions");
    rolePartners = document.getElementById("classic-role-partners");
    endScreen = document.getElementById("classic-end-screen");
    winner = document.getElementById("classic-winner");
    reason = document.getElementById("classic-end-reason");
    roles = document.getElementById("classic-role-list");
    stats = document.getElementById("classic-stat-list");
    newRound = document.getElementById("classic-new-round");
    hostHint = document.getElementById("classic-host-hint");
    progressPanel = document.getElementById("classic-progress");
    progressLabel = document.getElementById("classic-progress-label");
    progressTrack = progressPanel.querySelector('[role="progressbar"]');
    progressFill = document.getElementById("classic-progress-fill");
    ownNameLabel = document.getElementById("classic-own-name");
    document.getElementById("classic-back-lobby").addEventListener("click", hideResult);
    newRound.addEventListener("click", startNewRound);
    Game.net.on("classic_role", showRole);
    Game.net.on("classic_progress", showProgress);
    Game.net.on("classic_result", showResult);
  }

  function setLobby(message) {
    if (!message || !Array.isArray(message.players)) return;
    var classicRoundActive = message.mode === "classic" && message.phase === "round";
    if ((classicRoundActive && !roundIsActive)
      || (message.phase === "round" && message.mode !== "classic")) {
      setOwnFreeRider(false);
    }
    roundIsActive = classicRoundActive;
    isHost = message.host === ownName;
    if (message.mode === "classic" && message.phase === "round") progressPanel.hidden = false;
    else if (message.phase !== "round") progressPanel.hidden = true;
    if (!endScreen.hidden) updateHostAction();
  }

  function setOwnName(name) {
    ownName = typeof name === "string" ? name : null;
    updateOwnName();
  }

  function setOwnFreeRider(value) {
    ownIsFreeRider = value === true;
    if (Game.lobby && typeof Game.lobby.setOwnFreeRider === "function") {
      Game.lobby.setOwnFreeRider(ownIsFreeRider);
    }
    if (Game.world && typeof Game.world.setOwnFreeRider === "function") {
      Game.world.setOwnFreeRider(ownIsFreeRider);
    }
    if (Game.classicMeeting && typeof Game.classicMeeting.setOwnFreeRider === "function") {
      Game.classicMeeting.setOwnFreeRider(ownIsFreeRider);
    }
    updateOwnName();
  }

  function updateOwnName() {
    if (!ownNameLabel) return;
    ownNameLabel.textContent = ownName || "";
    ownNameLabel.classList.toggle("free-rider-name", ownIsFreeRider);
  }

  function resetRoleMarker() {
    roundIsActive = false;
    setOwnFreeRider(false);
  }

  function showRole(message) {
    if (!message || !["HP", "FR"].includes(message.role)) return;
    if (roleTimer !== null) window.clearTimeout(roleTimer);
    endScreen.hidden = true;
    roleName.textContent = message.role === "HP" ? "High Performer" : "Free Rider";
    roleInstructions.textContent = message.role === "HP"
      ? "Complete your 4 tasks."
      : "Make High Performers fail without getting caught.";
    var partners = Array.isArray(message.other_free_riders) ? message.other_free_riders : [];
    rolePartners.textContent = message.role === "FR"
      ? "Other Free Riders: " + (partners.length ? partners.join(", ") : "None")
      : "";
    roleScreen.hidden = false;
    roleTimer = window.setTimeout(function () { roleScreen.hidden = true; roleTimer = null; }, 3000);
  }

  function showProgress(message) {
    if (!message || typeof message.progress !== "number" || !Number.isFinite(message.progress)) return;
    var percent = Math.max(0, Math.min(100, Math.round(message.progress * 100)));
    progressPanel.hidden = false;
    progressLabel.textContent = percent + "% complete";
    progressTrack.setAttribute("aria-valuenow", String(percent));
    progressFill.style.width = percent + "%";
  }

  function showResult(message) {
    if (!message || !["HP", "FR"].includes(message.winner) || !message.roles || !message.stats) return;
    if (roleTimer !== null) window.clearTimeout(roleTimer);
    roleScreen.hidden = true;
    progressPanel.hidden = true;
    winner.textContent = message.winner === "HP" ? "High Performers win" : "Free Riders win";
    var reasons = {
      bar_full: "The progress bar is full.",
      all_free_riders_eliminated: "All Free Riders were ejected.",
      free_riders_reached_parity: "Free Riders reached parity.",
    };
    reason.textContent = reasons[message.reason] || "The round has ended.";
    roles.replaceChildren();
    Object.keys(message.roles).forEach(function (playerId) {
      var item = document.createElement("li");
      item.textContent = playerId + " — " + (message.roles[playerId] === "FR" ? "Free Rider" : "High Performer");
      roles.append(item);
    });
    stats.replaceChildren();
    addStat("Failures", message.stats.failures);
    addStat("Tasks completed", message.stats.completed_tasks);
    addStat("Meetings", message.stats.meetings);
    endScreen.hidden = false;
    updateHostAction();
  }

  function addStat(label, value) {
    var item = document.createElement("li");
    item.textContent = label + ": " + (Number.isInteger(value) && value >= 0 ? value : 0);
    stats.append(item);
  }

  function updateHostAction() {
    newRound.disabled = !isHost;
    hostHint.textContent = isHost ? "Start another round with the same lobby." : "The host can start the next round.";
  }

  function startNewRound() {
    if (!isHost || !Game.net.send({ type: "start_game" })) return;
    hideResult();
  }

  function hideResult() { endScreen.hidden = true; }

  function hide() {
    if (roleTimer !== null) window.clearTimeout(roleTimer);
    roleTimer = null;
    roleScreen.hidden = true;
    endScreen.hidden = true;
    progressPanel.hidden = true;
  }

  Game.classicRound.setup = setup;
  Game.classicRound.setOwnName = setOwnName;
  Game.classicRound.setOwnFreeRider = setOwnFreeRider;
  Game.classicRound.resetRoleMarker = resetRoleMarker;
  Game.classicRound.setLobby = setLobby;
  Game.classicRound.hide = hide;
})();
