"use strict";

(function (root) {
  function remainingSeconds(status, receivedAt, now) {
    if (!status || !Number.isFinite(status.cooldown_until) || !Number.isFinite(status.server_time)) return 0;
    return Math.max(0, status.cooldown_until - status.server_time - Math.max(0, now - receivedAt) / 1000);
  }

  function fillFraction(status, receivedAt, now, cooldownSeconds) {
    var duration = cooldownSeconds || 15;
    if (!status || !Number.isFinite(status.cooldown_until)) return 1;
    return Math.min(1, Math.max(0, 1 - remainingSeconds(status, receivedAt, now) / duration));
  }

  // The Free Rider's button (S-195): the key first, like "E Emergency", and
  // never any seconds or distance. While it charges, its fill shows how far.
  var TEXT = "F Let fail";

  // What a screen reader hears: the state the button shows only by colour.
  function spokenLabel(secondsLeft, inRange) {
    if (secondsLeft > 0) {
      return "Let fail, ready in " + secondsLeft + (secondsLeft === 1 ? " second" : " seconds");
    }
    return inRange === false ? "Let fail, nobody in range" : "Let fail";
  }

  root.ClassicFailButton = {
    TEXT: TEXT,
    remainingSeconds: remainingSeconds,
    fillFraction: fillFraction,
    spokenLabel: spokenLabel,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = root.ClassicFailButton;
})(typeof window !== "undefined" ? window : globalThis);
