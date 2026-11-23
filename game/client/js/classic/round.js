// Displays private role cards and shared Classic progress and round results.
window.Game = window.Game || {};
Game.classicRound = Game.classicRound || {};

(function () {
  "use strict";
  var roleScreen, roleName, roleInstructions, rolePartners, ownNameLabel;
  var endScreen, winner, reason, roles, stats, newRound, hostHint;
  var progressPanel, progressLabel, progressTrack, progressFill;
  var hiddenHint; // the text "Hidden" while the own Free Rider hides (M3-1.4)
  var ownName = null;
  var ownIsFreeRider = false;
  var ownIsGhost = false;
  var ownToldHidden = false; // the server said the own Free Rider hides (M3-1.6)
  var roundIsActive = false;
  var isHost = false;
  var roleTimer = null;
  // "You failed." over the map for the victim of a fail (S-228).
  var youFailed = null;
  var youFailedTimer = null;
  var YOU_FAILED_MILLISECONDS = 4000;

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
    youFailed = document.getElementById("classic-you-failed");
    if (youFailed) youFailed.hidden = true;
    hiddenHint = makeHiddenHint();
    progressPanel.appendChild(hiddenHint);
    // "Back to the lobby" only closes the end screen: the player stays in the
    // lobby, as with the Duel ranking's "Back to lobby" (S-101).
    document.getElementById("classic-back-lobby").addEventListener("click", hideResult);
    newRound.addEventListener("click", startNewRound);
    Game.net.on("classic_role", showRole);
    Game.net.on("classic_progress", showProgress);
    Game.net.on("classic_result", showResult);
    Game.net.on("classic_roster", rememberOwnGhost);
    Game.net.on("classic_hiding", rememberOwnHiding);
    // Every member learns who failed from `classic_fail` (S-159); the victim
    // reads his own name in it, so no new message is needed (S-228).
    Game.net.on("classic_fail", showYouFailedIfOwn);
    Game.net.on("meeting_state", function () { showYouFailed(false); });
  }

  function setLobby(message) {
    if (!message || !Array.isArray(message.players)) return;
    var classicRoundActive = message.mode === "classic" && message.phase === "round";
    if ((classicRoundActive && !roundIsActive)
      || (message.phase === "round" && message.mode !== "classic")) {
      setOwnFreeRider(false);
    }
    roundIsActive = classicRoundActive;
    allowHiding(roundIsActive);
    isHost = message.host === ownName;
    if (message.mode === "classic" && message.phase === "round") progressPanel.hidden = false;
    else if (message.phase !== "round") progressPanel.hidden = true;
    // The end screen stays in the lobby, so the players can read the result
    // (S-101). A countdown or a round takes it away: a Duel would otherwise
    // run underneath it and could not be played.
    if (message.phase === "countdown" || message.phase === "round") hideResult();
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
    if (!ownIsFreeRider) showHiddenHint(false);
    updateOwnName();
  }

  // ---- Hiding (M3-1.4) ----------------------------------------------------

  function makeHiddenHint() {
    var hint = document.createElement("p");
    hint.id = "classic-hidden-hint";
    hint.className = "rule";
    hint.textContent = "Hidden";
    hint.hidden = true;
    return hint;
  }

  // Hiding is possible only in a Classic round (S-131): only then does the
  // world get the check below.
  function allowHiding(allowed) {
    if (!allowed) {
      ownIsGhost = false;
      ownToldHidden = false;
      showHiddenHint(false);
    }
    if (Game.world && typeof Game.world.setOwnHidingCheck === "function") {
      Game.world.setOwnHidingCheck(allowed ? ownHidesAt : null);
    }
  }

  function showHiddenHint(hidden) {
    if (hiddenHint && hiddenHint.hidden === hidden) hiddenHint.hidden = !hidden;
  }

  // A ghost does not hide: the roster says whether the own player is one.
  function rememberOwnGhost(message) {
    if (!message || !Array.isArray(message.players)) return;
    var own = message.players.find(function (entry) { return entry && entry.name === ownName; });
    ownIsGhost = Boolean(own) && own.ghost === true;
  }

  // The server tells only the own Free Rider whether he hides (M3-1.6,
  // S-191): after E at a hiding object, after a step, E again or a meeting.
  function rememberOwnHiding(message) {
    if (!message) return;
    ownToldHidden = roundIsActive && message.hidden === true;
  }

  // The world asks this for every frame that draws the own character. The
  // text "Hidden" follows the answer, so it always agrees with the half
  // transparent character. Since M3-1.6 the answer comes from the server,
  // not from the position (the arguments are kept for the world's call).
  function ownHidesAt() {
    var hidden = window.ClassicHudActions.ownIsHidden({
      classicRound: roundIsActive,
      freeRider: ownIsFreeRider,
      ghost: ownIsGhost,
      toldHidden: ownToldHidden,
    });
    showHiddenHint(hidden);
    return hidden;
  }

  function updateOwnName() {
    if (!ownNameLabel) return;
    ownNameLabel.textContent = ownName || "";
    ownNameLabel.classList.toggle("free-rider-name", ownIsFreeRider);
  }

  function showYouFailedIfOwn(message) {
    if (roundIsActive && message && ownName !== null && message.target_id === ownName) showYouFailed(true);
  }

  // Shown for a few seconds, or until a meeting opens or the round ends.
  function showYouFailed(shown) {
    if (!youFailed) return;
    if (youFailedTimer !== null) window.clearTimeout(youFailedTimer);
    youFailedTimer = null;
    youFailed.hidden = !shown;
    if (shown) {
      youFailedTimer = window.setTimeout(function () { showYouFailed(false); }, YOU_FAILED_MILLISECONDS);
    }
  }

  function resetRoleMarker() {
    showYouFailed(false);
    roundIsActive = false;
    allowHiding(false);
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
    // The Players list marks the Free Riders, only on a Free Rider's page (S-227).
    if (Game.lobby && typeof Game.lobby.setFreeRiderPartners === "function") {
      Game.lobby.setFreeRiderPartners(message.role === "FR" ? partners : []);
    }
    // Only with two Free Riders: with one there is nobody to name (no "None").
    rolePartners.textContent = message.role === "FR" && partners.length
      ? "Other Free Riders: " + partners.join(", ")
      : "";
    rolePartners.hidden = rolePartners.textContent === "";
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
      // Also when a Free Rider left the round instead of being voted out.
      all_free_riders_eliminated: "No Free Rider is left.",
      free_riders_reached_parity: "There are as many Free Riders as High Performers.",
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

  // Only the host sees "New Round" (Felix, 2026-11-22). For everybody else it
  // is hidden and takes no room, so "Back to the lobby" stands alone.
  // setLobby calls this again when the host changes while the screen is open.
  function updateHostAction() {
    newRound.hidden = !isHost;
    newRound.disabled = !isHost;
    hostHint.textContent = isHost ? "Start another round with the same lobby." : "The host can start the next round.";
  }

  function startNewRound() {
    if (!isHost || !Game.net.send({ type: "start_game" })) return;
    hideResult();
  }

  function hideResult() {
    // The focus goes back to the page, so the walking keys work at once.
    var focused = document.activeElement;
    if (focused && endScreen.contains(focused)) focused.blur();
    endScreen.hidden = true;
  }

  function hide() {
    if (roleTimer !== null) window.clearTimeout(roleTimer);
    roleTimer = null;
    roleScreen.hidden = true;
    endScreen.hidden = true;
    progressPanel.hidden = true;
    showHiddenHint(false);
  }

  Game.classicRound.setup = setup;
  Game.classicRound.setOwnName = setOwnName;
  Game.classicRound.setOwnFreeRider = setOwnFreeRider;
  Game.classicRound.resetRoleMarker = resetRoleMarker;
  Game.classicRound.setLobby = setLobby;
  Game.classicRound.hide = hide;
})();
