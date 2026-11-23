// The task navigator: an arrow beside the own character and the card at the
// top left with the own room and next task (Lennart's request, Felix's card).
// It only reads the public map, the own position and the own target;
// changing the target never moves anybody. The live arrow points directly
// at the station, even through a wall. The route search of `create` is not
// used by the page; tests check the map with it (tests/test_task_navigation.js).
//
// In Classic a High Performer has one active task at a time (S-197), shown
// like the next task of a Duel. `setTargets` (the nearest of several open
// tasks, S-145) is no longer used by the page; main.js empties it.
//
// main.js sets the target (`setTarget`, `setTargets`, `reset`), world.js calls `draw`
// once per frame. The card is the element #task-card of index.html, so it
// stays out of the canvas and under the ?debug panel.
"use strict";
window.Game = window.Game || {};

(function () {
  const STEP = 4;
  const HALF = 5;
  const YELLOW = '#FFD23F';
  const DARK = '#2E2A3B';
  const STEPS = [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]];

  // Small priority queue: the shortest unfinished distance comes out first.
  class Queue {
    constructor() { this.items = []; }
    push(distance, point) {
      const item = { distance: distance, point: point };
      let at = this.items.length;
      this.items.push(item);
      while (at > 0) {
        const parent = Math.floor((at - 1) / 2);
        if (this.items[parent].distance <= distance) break;
        this.items[at] = this.items[parent];
        at = parent;
      }
      this.items[at] = item;
    }
    pop() {
      const first = this.items[0];
      const last = this.items.pop();
      if (this.items.length) {
        let at = 0;
        while (at * 2 + 1 < this.items.length) {
          let child = at * 2 + 1;
          if (child + 1 < this.items.length && this.items[child + 1].distance < this.items[child].distance) child += 1;
          if (this.items[child].distance >= last.distance) break;
          this.items[at] = this.items[child];
          at = child;
        }
        this.items[at] = last;
      }
      return first;
    }
  }

  function create(campus) {
    const columns = Math.floor(campus.width / STEP) + 1;
    const rows = Math.floor(campus.height / STEP) + 1;
    const free = new Int8Array(columns * rows); // 0 unknown, 1 free, -1 blocked
    const fields = new Map(); // one field per station, built only when first needed
    const stations = new Map(campus.stations.map((station) => [station.id, station]));
    const rooms = new Map(campus.rooms.map((room) => [room.id, room]));

    function isFree(x, y) {
      if (!Number.isFinite(x) || !Number.isFinite(y) || x < HALF || y < HALF || x > campus.width - HALF || y > campus.height - HALF) return false;
      return !campus.solids.some((solid) => x + HALF > solid.x && x - HALF < solid.x + solid.w
        && y + HALF > solid.y && y - HALF < solid.y + solid.h);
    }

    function cellFree(column, row) {
      if (column < 0 || row < 0 || column >= columns || row >= rows) return false;
      const index = row * columns + column;
      if (free[index] === 0) free[index] = isFree(column * STEP, row * STEP) ? 1 : -1;
      return free[index] === 1;
    }

    // Intersect the segment with expanded solid interiors. Touching an edge
    // is allowed, just as in movement.py; slipping diagonally through is not.
    function segmentIsFree(a, b) {
      if (!isFree(a.x, a.y) || !isFree(b.x, b.y)) return false;
      return !campus.solids.some((solid) => {
        let low = 0;
        let high = 1;
        const bounds = [[a.x, b.x - a.x, solid.x - HALF, solid.x + solid.w + HALF],
          [a.y, b.y - a.y, solid.y - HALF, solid.y + solid.h + HALF]];
        for (const [start, change, minimum, maximum] of bounds) {
          if (change === 0) {
            if (start <= minimum || start >= maximum) return false;
          } else {
            const enter = (minimum - start) / change;
            const exit = (maximum - start) / change;
            low = Math.max(low, Math.min(enter, exit));
            high = Math.min(high, Math.max(enter, exit));
            if (low >= high - 1e-10) return false;
          }
        }
        return low < high - 1e-10;
      });
    }

    function inDestinationRoom(x, y, station) {
      const room = rooms.get(station.room);
      return !room || (x >= room.x && x <= room.x + room.w && y >= room.y && y <= room.y + room.h);
    }

    function fieldFor(station) {
      if (fields.has(station.id)) return fields.get(station.id);
      const distances = new Float64Array(columns * rows).fill(Infinity);
      const next = new Int32Array(columns * rows).fill(-1);
      const waiting = new Queue();
      const reach = Math.ceil(campus.use_range / STEP);
      const middleX = Math.round(station.x / STEP);
      const middleY = Math.round(station.y / STEP);
      for (let row = middleY - reach; row <= middleY + reach; row += 1) {
        for (let column = middleX - reach; column <= middleX + reach; column += 1) {
          const x = column * STEP;
          const y = row * STEP;
          if (Math.hypot(x - station.x, y - station.y) > campus.use_range || !inDestinationRoom(x, y, station) || !cellFree(column, row)) continue;
          const point = row * columns + column;
          distances[point] = 0;
          waiting.push(0, point);
        }
      }
      while (waiting.items.length) {
        const current = waiting.pop();
        if (current.distance !== distances[current.point]) continue;
        const column = current.point % columns;
        const row = Math.floor(current.point / columns);
        for (const [dx, dy] of STEPS) {
          if (!cellFree(column + dx, row + dy)) continue;
          if (dx && dy && (!cellFree(column + dx, row) || !cellFree(column, row + dy))) continue;
          const point = (row + dy) * columns + column + dx;
          const length = current.distance + STEP * (dx && dy ? Math.SQRT2 : 1);
          if (length < distances[point]) {
            distances[point] = length;
            next[point] = current.point;
            waiting.push(length, point);
          }
        }
      }
      const field = { distances: distances, next: next };
      fields.set(station.id, field);
      return field;
    }

    function positionOf(point) {
      return { x: (point % columns) * STEP, y: Math.floor(point / columns) * STEP };
    }

    function startPoint(position, field) {
      const middleX = Math.round(position.x / STEP);
      const middleY = Math.round(position.y / STEP);
      let best = null;
      let closest = Infinity;
      // The nearest cell may lie across a furniture edge. Only a cell with
      // a clear connection from the actual position is a valid first step.
      for (let row = middleY - 2; row <= middleY + 2; row += 1) {
        for (let column = middleX - 2; column <= middleX + 2; column += 1) {
          if (!cellFree(column, row)) continue;
          const point = row * columns + column;
          if (!Number.isFinite(field.distances[point])) continue;
          const candidate = positionOf(point);
          const distance = Math.hypot(candidate.x - position.x, candidate.y - position.y);
          if (distance >= closest || !segmentIsFree(position, candidate)) continue;
          best = point;
          closest = distance;
        }
      }
      return best;
    }

    function route(position, stationId) {
      const station = stations.get(stationId);
      if (!station || !position || !isFree(position.x, position.y)) return null;
      const room = rooms.get(station.room);
      const base = { station: station.id, room: room ? room.name : 'Main Deck', title: station.name };
      if (Math.hypot(position.x - station.x, position.y - station.y) <= campus.use_range) {
        return Object.assign(base, { path: [position], distance: 0, arrived: true });
      }
      const field = fieldFor(station);
      let point = startPoint(position, field);
      if (point === null) return null; // never suggest a straight line through a wall
      const path = [position];
      const distance = Math.hypot(position.x - positionOf(point).x, position.y - positionOf(point).y) + field.distances[point];
      while (point !== -1) {
        path.push(positionOf(point));
        point = field.next[point];
      }
      let waypoint = path[1];
      for (let index = 2; index < Math.min(path.length, 10); index += 1) {
        if (!segmentIsFree(position, path[index])) break;
        waypoint = path[index];
      }
      return Object.assign(base, { path: path, waypoint: waypoint, distance: distance, arrived: false });
    }

    return { route: route, isFree: isFree, segmentIsFree: segmentIsFree };
  }

  // ---- The arrow: a plain triangle (Felix, 2026-11-21) -------------------

  // An isosceles triangle pointing right, 11 map units long and 9 wide,
  // around (0, 0), with its tip the corner farthest from (0, 0). A
  // character is 39 units high.
  const TRIANGLE_POINTS = [[6.5, 0], [-4.5, -4.5], [-4.5, 4.5]];
  const TRIANGLE_OUTLINE = 1.6; // the game's dark outline, readable on every floor
  // Where the arrow stands: this far from the middle of the character's
  // body, which is 14.5 units above its position (feet 5 below it, 39 high).
  const ARROW_DISTANCE = 24;
  const BODY_MIDDLE_ABOVE_POSITION = 14.5;
  // Close to the station its pulsing object is enough: the arrow fades out
  // between these distances (in map units) and is gone on arrival.
  const FADE_FROM = 60;
  const FADE_TO = 40;

  // The triangle at (x, y) turned by `angle`: sun yellow with a dark outline.
  function arrow(ctx, x, y, angle, alpha) {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.translate(x, y);
    ctx.rotate(angle);
    ctx.beginPath();
    TRIANGLE_POINTS.forEach(([pointX, pointY], index) => (index === 0 ? ctx.moveTo(pointX, pointY) : ctx.lineTo(pointX, pointY)));
    ctx.closePath();
    ctx.fillStyle = YELLOW;
    ctx.fill();
    ctx.lineJoin = 'round';
    ctx.lineWidth = TRIANGLE_OUTLINE;
    ctx.strokeStyle = DARK;
    ctx.stroke();
    ctx.restore();
  }

  // 1 far away, 0 near the station, in between it fades.
  function arrowAlpha(distance) {
    return Math.max(0, Math.min(1, (distance - FADE_TO) / (FADE_FROM - FADE_TO)));
  }

  // The live compass uses only the player's own position and destination.
  // It deliberately does not follow doors or route waypoints.
  function directGuidance(campus, position, stationId) {
    if (!campus || !position || !Number.isFinite(position.x) || !Number.isFinite(position.y)) return null;
    const station = campus.stations.find((entry) => entry.id === stationId);
    if (!station) return null;
    const room = campus.rooms.find((entry) => entry.id === station.room);
    return {
      station: station.id,
      room: room ? room.name : 'Main Deck',
      title: station.name,
      target: { x: station.x, y: station.y },
      angle: Math.atan2(station.y - position.y, station.x - position.x),
      arrived: Math.hypot(station.x - position.x, station.y - position.y) <= campus.use_range
    };
  }

  // The station of `stationIds` nearest to `position` in a straight line,
  // or null when there is none. On a tie the first in the list wins. Ids
  // that are not on the map are skipped. No hysteresis: the arrow simply
  // turns to whichever station is nearer now.
  function nearestStation(campus, position, stationIds) {
    if (!campus || !isPosition(position) || !Array.isArray(stationIds)) return null;
    let nearest = null;
    let shortest = Infinity;
    for (const stationId of stationIds) {
      const station = campus.stations.find((entry) => entry.id === stationId);
      if (!station) continue;
      const distance = Math.hypot(station.x - position.x, station.y - position.y);
      if (distance < shortest) { // strictly smaller, so a tie keeps the first
        nearest = station.id;
        shortest = distance;
      }
    }
    return nearest;
  }

  // Called in map coordinates, before the characters are drawn. The arrow
  // stands beside the character's body and points straight at the station
  // (also through a wall). No arrow on arrival or exactly on the station.
  function drawArrow(ctx, guidance, position) {
    if (!guidance || guidance.arrived) return;
    const dx = guidance.target.x - position.x;
    const dy = guidance.target.y - position.y;
    const alpha = arrowAlpha(Math.hypot(dx, dy));
    if ((dx === 0 && dy === 0) || alpha === 0) return;
    const angle = Math.atan2(dy, dx);
    const middleY = position.y - BODY_MIDDLE_ABOVE_POSITION;
    arrow(ctx, position.x + Math.cos(angle) * ARROW_DISTANCE, middleY + Math.sin(angle) * ARROW_DISTANCE, angle, alpha);
  }

  // ---- The card at the top left -----------------------------------------
  //
  // Its head says which room the own character stands in, in every mode and
  // also in the lobby. Below it, while this player has one next task (Duel,
  // Solo, Classic; main.js decides), "NEXT TASK" and the task. It is the only room
  // display of the page.

  let target = null; // the station id of the own next task, or null
  let targets = []; // Classic: the station ids of the own open tasks
  let shownCard = ''; // what the card shows now, so it is only changed on a change
  let shownPlace = null; // the room the card shows now, or null while it is hidden

  // The three lines of the task part for `guidance`, or null for none.
  function cardLines(guidance) {
    if (!guidance) return null;
    return [guidance.arrived ? 'E USE · YOUR TASK' : 'NEXT TASK', guidance.room, guidance.title];
  }

  // The name of the room at `position`, "Main Deck" outside the rooms.
  // roomAt comes from world/draw.js; without it every place is the deck.
  function placeName(campus, position) {
    const roomAt = Game.world && Game.world.roomAt;
    const room = typeof roomAt === 'function' ? roomAt(campus, position.x, position.y) : null;
    return room && typeof room.name === 'string' ? room.name : 'Main Deck';
  }

  function setText(id, text) {
    const element = document.getElementById(id);
    if (element) element.textContent = text;
  }

  // Shows the card with the room `place` (or hides it for null) and the
  // task part for `guidance` (or none for null). Without the card in the
  // page (a test, an old page) nothing happens.
  function showCard(place, guidance) {
    const card = document.getElementById('task-card');
    if (!card) return;
    const lines = place === null ? null : cardLines(guidance);
    const key = JSON.stringify([place, lines]);
    if (key === shownCard) return;
    shownCard = key;
    shownPlace = place;
    card.hidden = place === null;
    card.classList.toggle('task-card-arrived', Boolean(lines && guidance.arrived));
    setText('task-card-here', place === null ? '' : place);
    const task = document.getElementById('task-card-task');
    if (task) task.hidden = lines === null;
    ['task-card-kicker', 'task-card-room', 'task-card-title'].forEach((id, index) => {
      setText(id, lines ? lines[index] : '');
    });
  }

  // The station of the own next task, or null for none. From main.js.
  function setTarget(stationId) {
    target = Number.isInteger(stationId) ? stationId : null;
    if (target === null) showCard(shownPlace, null); // at once, not only at the next frame
  }

  // Classic: the own open tasks. The arrow points at the nearest one; the
  // card gets no task part. An empty list (all done, a Free Rider) means no arrow.
  function setTargets(stationIds) {
    targets = Array.isArray(stationIds) ? stationIds.filter((id) => Number.isInteger(id)) : [];
  }

  // The player left the lobby: no target and no card until the next frame of a world.
  function reset() {
    target = null;
    targets = [];
    showCard(null, null);
  }

  // Once per frame from world.js, in map units and before the characters.
  // `drawn` is where the own character is drawn (the card names its room and
  // the arrow starts there), `server` the newest position from the server:
  // like "E Use", the card says "E USE" only when the server counts the
  // player in range. While a minigame is open (`paused`) nothing is shown.
  function draw(ctx, campus, drawn, server, paused) {
    const canShow = Boolean(campus) && isPosition(drawn) && !paused;
    const guidance = canShow && target !== null ? directGuidance(campus, server, target) : null;
    showCard(canShow ? placeName(campus, drawn) : null, guidance);
    if (guidance) {
      drawArrow(ctx, guidance, drawn);
    } else if (canShow && targets.length) {
      // Classic: the arrow only, towards the nearest open task, chosen anew every frame.
      const nearest = nearestStation(campus, server, targets);
      drawArrow(ctx, directGuidance(campus, server, nearest), drawn);
    }
  }

  function isPosition(position) {
    return Boolean(position) && Number.isFinite(position.x) && Number.isFinite(position.y);
  }

  Game.taskNavigation = {
    create: create,
    directGuidance: directGuidance,
    nearestStation: nearestStation,
    drawArrow: drawArrow,
    cardLines: cardLines,
    placeName: placeName,
    setTarget: setTarget,
    setTargets: setTargets,
    reset: reset,
    draw: draw,
  };
})();
