// Public lobby members, displayed over the map during a round. A task,
// missing position or lost connection never decides whether someone is dead.
window.Game = window.Game || {};

(function () {
  const MAX_PLAYERS = 8;
  const PORTRAIT_SIZE = 44;
  let container = null;
  let list = null;
  let count = null;
  let ownName = null;
  let members = [];

  function element(tag, className, text) {
    const made = document.createElement(tag);
    made.className = className;
    if (text !== undefined) made.textContent = text;
    return made;
  }

  function setup() {
    container = document.getElementById('player-roster');
    list = document.getElementById('player-roster-list');
    count = document.getElementById('player-roster-count');
    reset();
  }

  function fallbackPortrait() {
    const fallback = element('span', 'player-roster-fallback');
    fallback.append(element('span', 'player-roster-fallback-head'), element('span', 'player-roster-fallback-body'));
    return fallback;
  }

  function portrait(character) {
    const frame = element('span', 'player-roster-portrait');
    frame.setAttribute('aria-hidden', 'true');
    try {
      if (!Game.world || typeof Game.world.drawCharacter !== 'function') throw new Error('no drawing');
      const canvas = document.createElement('canvas');
      const density = window.devicePixelRatio || 1;
      canvas.width = PORTRAIT_SIZE * density;
      canvas.height = PORTRAIT_SIZE * density;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('no canvas');
      ctx.scale(density, density);
      Game.world.drawCharacter(ctx, character, PORTRAIT_SIZE / 2, PORTRAIT_SIZE / 2, 38);
      frame.append(canvas);
    } catch (problem) {
      // A missing character drawing must never hide a player or their status.
      frame.append(fallbackPortrait());
    }
    return frame;
  }

  function row(player) {
    const dead = player.alive === false;
    const item = element('li', 'player-roster-row');
    if (dead) item.classList.add('player-roster-dead');
    const picture = portrait(player.character);
    if (dead) {
      const cross = element('span', 'player-roster-cross', '×');
      cross.setAttribute('aria-hidden', 'true');
      picture.append(cross);
    }
    const detail = element('div', 'player-roster-detail');
    const identity = element('div', 'player-roster-identity');
    const name = element('span', 'player-roster-name', player.name);
    name.title = player.name;
    identity.append(name);
    if (player.name === ownName) identity.append(element('span', 'player-roster-you', 'You'));
    detail.append(identity, element('span', 'player-roster-status', dead ? 'Dead' : 'In game'));
    item.append(picture, detail);
    return item;
  }

  function render() {
    if (!container || !list || !count) return;
    list.replaceChildren(...members.map(row));
    count.textContent = String(members.length);
    container.hidden = members.length === 0;
  }

  function setOwnName(name) {
    ownName = typeof name === 'string' ? name : null;
    render();
  }

  function show(state) {
    if (!state || state.phase !== 'round' || !Array.isArray(state.players)) {
      reset();
      return;
    }
    const names = new Set();
    members = [];
    state.players.forEach((player) => {
      if (!player || typeof player.name !== 'string' || !player.name || names.has(player.name) || members.length >= MAX_PLAYERS) return;
      names.add(player.name);
      // Copy only public presentation fields. No role, task or position data
      // belongs in this card. Only the literal boolean false means "Dead".
      members.push({ name: player.name, character: typeof player.character === 'string' ? player.character : null, alive: player.alive !== false });
    });
    render();
  }

  function reset() {
    members = [];
    if (container) container.hidden = true;
    if (list) list.replaceChildren();
    if (count) count.textContent = '0';
  }

  Game.roster = { setup, setOwnName, show, reset };
})();
