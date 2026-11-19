"use strict";

(function (root) {
  function reportVisible(isLiving, distance, range) {
    return isLiving === true && Number.isFinite(distance) && distance <= (range || 2);
  }

  function emergencyUnlocked(status, receivedAt, now) {
    if (!status || !Number.isFinite(status.emergency_ready_at) || !Number.isFinite(status.server_time)) return false;
    var elapsed = Math.max(0, now - receivedAt) / 1000;
    return status.server_time + elapsed >= status.emergency_ready_at;
  }

  root.ClassicHudActions = { reportVisible: reportVisible, emergencyUnlocked: emergencyUnlocked };
  if (typeof module !== "undefined" && module.exports) module.exports = root.ClassicHudActions;
})(typeof window !== "undefined" ? window : globalThis);
