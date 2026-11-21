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

  root.ClassicFailButton = { remainingSeconds: remainingSeconds, fillFraction: fillFraction };
  if (typeof module !== "undefined" && module.exports) module.exports = root.ClassicFailButton;
})(typeof window !== "undefined" ? window : globalThis);
