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

  // Is (x, y) inside one of the hiding spots, the edge included? The same
  // rule as hiding_spot() in server/world/visibility.py.
  function inHidingSpot(x, y, spots) {
    if (!Array.isArray(spots)) return false;
    return spots.some(function (spot) {
      return Boolean(spot) && Math.hypot(x - spot.x, y - spot.y) <= spot.r;
    });
  }

  // Does the own character hide right now (M3-1.4)? Only a living Free
  // Rider in a Classic round, standing in a hiding spot. It decides only
  // what the own browser draws; the server decides what the others get.
  function ownIsHidden(state) {
    return Boolean(state)
      && state.classicRound === true
      && state.freeRider === true
      && state.ghost !== true
      && Number.isFinite(state.x)
      && Number.isFinite(state.y)
      && inHidingSpot(state.x, state.y, state.spots);
  }

  root.ClassicHudActions = {
    reportVisible: reportVisible,
    emergencyUnlocked: emergencyUnlocked,
    inHidingSpot: inHidingSpot,
    ownIsHidden: ownIsHidden,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = root.ClassicHudActions;
})(typeof window !== "undefined" ? window : globalThis);
