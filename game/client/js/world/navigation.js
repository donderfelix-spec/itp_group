// The task navigator only reads the public map and the player's own target.
// The live arrow points directly at the assigned station, even when a wall
// is in between. The route helpers below remain available for map checks.
// Changing the target never changes a player's position.
"use strict";
window.Game = window.Game || {};
Game.world = Game.world || {};

(function () {
  const STEP = 4;
  const HALF = 5;
  const YELLOW = '#FFD23F';
  const DARK = '#2E2A3B';
  const CREAM = '#F4EFE3';
  const GREEN = '#5FA86B';
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

  function arrow(ctx, x, y, angle, size, colour) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(angle);
    ctx.beginPath();
    ctx.moveTo(size, 0);
    ctx.lineTo(-size * 0.7, -size * 0.65);
    ctx.lineTo(-size * 0.35, 0);
    ctx.lineTo(-size * 0.7, size * 0.65);
    ctx.closePath();
    ctx.fillStyle = colour;
    ctx.strokeStyle = DARK;
    ctx.lineWidth = size / 6;
    ctx.fill();
    ctx.stroke();
    ctx.restore();
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

  // Called in map coordinates, before the characters are drawn. The small
  // arrow stays next to the character and always points at the station.
  function drawArrow(ctx, guidance, position) {
    if (!guidance) return;
    const dx = guidance.target.x - position.x;
    const dy = guidance.target.y - position.y;
    if (dx === 0 && dy === 0) return; // no direction exactly at the centre
    const angle = Math.atan2(dy, dx);
    arrow(ctx, position.x + Math.cos(angle) * 21, position.y + Math.sin(angle) * 21, angle, 5.8, YELLOW);
  }

  function shorten(ctx, text, width) {
    if (ctx.measureText(text).width <= width) return text;
    while (text.length && ctx.measureText(text + '…').width > width) text = text.slice(0, -1);
    return text + '…';
  }

  // Called last in screen pixels: it stays in the corner as the camera moves.
  function drawOverlay(ctx, guidance, title, canvas) {
    if (!guidance) return;
    const density = window.devicePixelRatio || 1;
    const width = Math.min(314, canvas.width / density - 24);
    if (width < 150) return;
    ctx.save();
    ctx.setTransform(density, 0, 0, density, 0, 0);
    ctx.fillStyle = DARK;
    ctx.fillRect(15, 15, width, 74);
    ctx.fillStyle = CREAM;
    ctx.fillRect(12, 12, width, 74);
    ctx.strokeStyle = DARK;
    ctx.lineWidth = 2;
    ctx.strokeRect(12, 12, width, 74);
    ctx.fillStyle = guidance.arrived ? GREEN : YELLOW;
    ctx.fillRect(12, 12, 6, 74);
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = DARK;
    ctx.font = 'bold 11px system-ui, sans-serif';
    ctx.fillText(guidance.arrived ? 'E Use · YOUR TASK' : 'YOUR NEXT TASK', 28, 30);
    ctx.font = 'bold 17px system-ui, sans-serif';
    ctx.fillText(shorten(ctx, guidance.room, width - 34), 28, 51);
    ctx.font = '12px system-ui, sans-serif';
    ctx.fillText(shorten(ctx, title || guidance.title, width - 34), 28, 72);
    ctx.restore();
  }

  Game.world.navigation = { create: create, directGuidance: directGuidance, drawArrow: drawArrow, drawOverlay: drawOverlay };
})();
