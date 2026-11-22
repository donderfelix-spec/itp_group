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

  // Does the own character hide right now? Only a living Free Rider in a
  // Classic round whom the server told he hides: he pressed E at a hiding
  // object (M3-1.6, S-191; message `classic_hiding`). Standing in a spot
  // alone no longer hides. It decides only what the own browser draws; the
  // server decides what the others get.
  function ownIsHidden(state) {
    return Boolean(state)
      && state.classicRound === true
      && state.freeRider === true
      && state.ghost !== true
      && state.toldHidden === true;
  }

  // The hiding spot whose centre is nearest to (x, y) and at most `reach`
  // away (the reach included), or null. On a tie the first spot of the map
  // wins. The same rule as spot_in_reach() in server/classic/hiding.py.
  function spotInReach(x, y, spots, reach) {
    if (!Array.isArray(spots) || !Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(reach)) return null;
    var nearest = null;
    var nearestDistance = Infinity;
    spots.forEach(function (spot) {
      if (!spot) return;
      var distance = Math.hypot(x - spot.x, y - spot.y);
      if (distance <= reach && distance < nearestDistance) {
        nearest = spot;
        nearestDistance = distance;
      }
    });
    return nearest;
  }

  // What E does when several things are in reach (M3-1.6): the nearest one.
  // `candidates` are {kind, distance}; on a tie the one listed first wins.
  // Returns the kind, or null when the list is empty.
  function nearestTarget(candidates) {
    var best = null;
    (Array.isArray(candidates) ? candidates : []).forEach(function (candidate) {
      if (!candidate || !Number.isFinite(candidate.distance)) return;
      if (best === null || candidate.distance < best.distance) best = candidate;
    });
    return best ? best.kind : null;
  }

  root.ClassicHudActions = {
    reportVisible: reportVisible,
    emergencyUnlocked: emergencyUnlocked,
    inHidingSpot: inHidingSpot,
    ownIsHidden: ownIsHidden,
    spotInReach: spotInReach,
    nearestTarget: nearestTarget,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = root.ClassicHudActions;
})(typeof window !== "undefined" ? window : globalThis);
