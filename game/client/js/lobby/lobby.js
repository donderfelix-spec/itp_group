// The panel next to the map: lobby code, player list, mode, character
// selection and the start button.
//
// It draws what the last `lobby_state` message of the server says and nothing
// else. Clicking a character, a mode or "Start game" only asks the server; the
// panel changes when the server answers.

window.Game = window.Game || {};

(function () {
  const ICON_PIXELS = 48; // width and height of an icon canvas on the page
  const CHARACTER_PIXELS = 44; // height of the character drawn inside it
  const DOT_RADIUS = 15; // the plain dot drawn when there is no character drawing
  const DOT_COLOUR = '#8A8494';

  // The modes the host sees, from DESIGN.md, section 4. `minPlayers` is only
  // for the hint under the start button: the server checks it again (S-53).
  const MODES = [
    { id: 'duel', name: 'Duel', minPlayers: 2, isBuilt: true },
    { id: 'solo', name: 'Solo', minPlayers: 1, isBuilt: true },
    { id: 'classic', name: 'Classic', minPlayers: 4, isBuilt: true },
  ];

  const codeElement = document.getElementById('lobby-code');
  const playerList = document.getElementById('lobby-players');
  const characterGrid = document.getElementById('lobby-characters');
  const modeGrid = document.getElementById('lobby-modes');
  const startButton = document.getElementById('lobby-start');
  const characterButtons = {}; // character id -> its button
  const modeButtons = {}; // mode id -> its button
  let ownName = null;
  let ownIsFreeRider = false;
  let latestState = null;
  // In a Duel or Solo round: how many stations each player has done, from
  // `duel_progress` (see showProgress). null outside such a round.
  let progress = null;

  function setup() {
    allCharacters().forEach(addCharacterButton);
    MODES.forEach(addModeButton);
    startButton.addEventListener('click', () => {
      // `ask` ignores further clicks until the server has answered (S-89).
      Game.net.ask({ type: 'start_game' });
    });
    document.getElementById('lobby-leave').addEventListener('click', leaveLobby);
  }

  function setOwnName(name) {
    ownName = name;
  }

  function setOwnFreeRider(value) {
    ownIsFreeRider = value === true;
    if (latestState) showPlayers(latestState);
  }

  // The one list of characters in the browser is in world/characters.js,
  // which the page loads before this file. It must match protocol.CHARACTERS
  // on the server; tests/test_character_list.py checks that. If the list is
  // missing, the lobby shows no characters instead of crashing.
  function allCharacters() {
    const fromWorld = Game.world && Game.world.characters;
    return Array.isArray(fromWorld) ? fromWorld : [];
  }

  function findCharacter(characterId) {
    return allCharacters().find((character) => character.id === characterId);
  }

  // ---- Icons ----

  function makeIcon(characterId) {
    const canvas = document.createElement('canvas');
    canvas.className = 'icon';
    // More pixels than the size on the page, so the icon is sharp on
    // high-resolution screens.
    const sharpness = window.devicePixelRatio || 1;
    canvas.width = ICON_PIXELS * sharpness;
    canvas.height = ICON_PIXELS * sharpness;
    const ctx = canvas.getContext('2d');
    ctx.scale(sharpness, sharpness);
    drawIcon(ctx, characterId);
    return canvas;
  }

  function drawIcon(ctx, characterId) {
    const middle = ICON_PIXELS / 2;
    if (Game.world && typeof Game.world.drawCharacter === 'function') {
      try {
        Game.world.drawCharacter(ctx, characterId, middle, middle, CHARACTER_PIXELS);
        return;
      } catch (problem) {
        // The drawing code failed. The panel must still work, so the dot
        // below is drawn instead.
        ctx.clearRect(0, 0, ICON_PIXELS, ICON_PIXELS);
      }
    }
    drawDot(ctx, characterId, middle);
  }

  function drawDot(ctx, characterId, middle) {
    const character = findCharacter(characterId);
    ctx.beginPath();
    ctx.arc(middle, middle, DOT_RADIUS, 0, Math.PI * 2);
    ctx.fillStyle = (character && character.colour) || DOT_COLOUR;
    ctx.fill();
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = '#2E2A3B';
    ctx.stroke();
  }

  // ---- Character selection ----

  // The eight buttons are built once and only updated afterwards, so the
  // keyboard focus stays where it is when the lobby changes.
  function addCharacterButton(character) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'character';
    button.appendChild(makeIcon(character.id));
    button.appendChild(makeCharacterText(character));
    button.addEventListener('click', () => {
      Game.net.ask({ type: 'choose_character', character: character.id });
    });
    characterButtons[character.id] = button;
    characterGrid.appendChild(button);
  }

  // The lobby line is seen only on the player's own card. On the others it is
  // hidden but keeps its room, so no card changes its size when the choice
  // changes (see style.css); there it is a tooltip.
  function makeCharacterText(character) {
    const text = makeText('span', 'character-text', '');
    text.appendChild(makeText('span', 'character-name', character.name));
    if (character.line) {
      const line = '“' + character.line + '”';
      text.appendChild(makeText('span', 'character-line', line));
      text.title = line;
    }
    return text;
  }

  function showCharacters(players, isOpen) {
    const own = players.find((player) => player.name === ownName);
    const takenByOthers = players
      .filter((player) => player.name !== ownName)
      .map((player) => player.character);

    Object.keys(characterButtons).forEach((characterId) => {
      const button = characterButtons[characterId];
      const isOwn = Boolean(own) && own.character === characterId;
      const isTaken = takenByOthers.includes(characterId);
      button.classList.toggle('character-own', isOwn);
      button.setAttribute('aria-pressed', String(isOwn));
      // The server rejects a taken character anyway (S-81), and every
      // character during the countdown (S-102); switching the button off
      // only saves the player the error.
      button.disabled = isTaken || !isOpen;
    });
  }

  // ---- Mode ----

  // Built once, like the character buttons.
  function addModeButton(mode) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'mode';
    button.appendChild(makeText('span', 'mode-name', mode.name));
    button.addEventListener('click', () => {
      Game.net.ask({ type: 'choose_mode', mode: mode.id });
    });
    modeButtons[mode.id] = button;
    modeGrid.appendChild(button);
  }

  function findMode(modeId) {
    return MODES.find((mode) => mode.id === modeId);
  }

  // A mode the page does not know is shown by its id, so the player still
  // sees what the server says.
  function modeName(modeId) {
    const mode = findMode(modeId);
    return mode ? mode.name : modeId;
  }

  // The host gets the buttons, everybody else only the text.
  function showMode(modeId, isHost, isOpen) {
    modeGrid.hidden = !isHost;
    const modeText = document.getElementById('lobby-mode-text');
    modeText.hidden = isHost;
    modeText.textContent = modeName(modeId);

    MODES.forEach((mode) => {
      const button = modeButtons[mode.id];
      const isChosen = mode.id === modeId;
      button.classList.toggle('mode-own', isChosen);
      button.setAttribute('aria-pressed', String(isChosen));
      // The server refuses these anyway (S-91); switching the button off
      // only saves the host the error.
      button.disabled = !mode.isBuilt || !isOpen;
    });
  }

  // ---- Start button ----

  // Switched off while too few players are there, and during the countdown:
  // the host has pressed it already (S-102).
  function showStartButton(state, isOpen) {
    const missing = playersMissing(state.mode, state.players.length);
    startButton.disabled = missing > 0 || !isOpen;
    const hint = document.getElementById('lobby-start-hint');
    hint.textContent = missing > 0 ? startHint(state.mode, missing) : '';
    hint.hidden = missing === 0;
  }

  // How many players are missing for a round of this mode. 0 for a mode the
  // page does not know: then the server alone decides.
  function playersMissing(modeId, playerCount) {
    const mode = findMode(modeId);
    if (!mode) return 0;
    return Math.max(0, mode.minPlayers - playerCount);
  }

  // For example "Duel needs 1 more player" or "Classic needs 2 more players".
  function startHint(modeId, missing) {
    const players = missing === 1 ? 'player' : 'players';
    return modeName(modeId) + ' needs ' + missing + ' more ' + players;
  }

  // ---- Player list ----

  // In a Duel or Solo round each row also shows the player's progress, "2/3"
  // and a bar (Felix, 2026-11-21); the list is then one column wide. In the
  // lobby and in Classic it is the list of main.
  function showPlayers(state) {
    playerList.replaceChildren();
    const shown = isRaceRound(state) ? progress : null;
    playerList.classList.toggle('players-progress', shown !== null);
    state.players.forEach((player) => {
      const row = makePlayerRow(player, state.host);
      if (shown && shown.done.has(player.name)) addProgress(row, shown.done.get(player.name), shown.total);
      playerList.appendChild(row);
    });
  }

  function isRaceRound(state) {
    return state.phase === 'round' && (state.mode === 'duel' || state.mode === 'solo');
  }

  // "2/3" at the right of the row and a bar under the name.
  function addProgress(row, done, total) {
    row.appendChild(makeText('span', 'player-done', done + '/' + total));
    const bar = makeText('span', 'player-bar', '');
    bar.setAttribute('aria-hidden', 'true'); // "2/3" already says it
    const fill = makeText('span', 'player-bar-fill', '');
    fill.style.width = Math.round(100 * done / total) + '%';
    bar.appendChild(fill);
    row.appendChild(bar);
  }

  // From main.js: what duel.js read from `duel_progress`, as
  // {players: [{name, done}], total}, or null. Anything unreadable shows no
  // progress; a count above the total is shown as the total.
  function showProgress(given) {
    progress = readProgress(given);
    if (latestState) showPlayers(latestState);
  }

  function readProgress(given) {
    const isReadable = Boolean(given) && Array.isArray(given.players)
      && Number.isInteger(given.total) && given.total > 0;
    if (!isReadable) return null;
    const done = new Map();
    given.players.forEach((player) => {
      const isPlayer = Boolean(player) && typeof player.name === 'string' && Number.isInteger(player.done) && player.done >= 0;
      if (isPlayer) done.set(player.name, Math.min(player.done, given.total));
    });
    return { done: done, total: given.total };
  }

  function makePlayerRow(player, hostName) {
    const row = document.createElement('li');
    row.className = player.name === ownName ? 'player player-own' : 'player';
    row.appendChild(makeIcon(player.character));
    // textContent, never innerHTML: a name is text from another player.
    const name = makeText('span', 'player-name', player.name);
    if (player.name === ownName && ownIsFreeRider) name.classList.add('free-rider-name');
    name.title = player.name; // A long name is cut off in the narrow list.
    row.appendChild(name);
    if (player.name === hostName) row.appendChild(makeText('span', 'marker marker-host', 'Host'));
    if (player.name === ownName) row.appendChild(makeText('span', 'marker', 'You'));
    return row;
  }

  function makeText(tag, className, text) {
    const element = document.createElement(tag);
    element.className = className;
    element.textContent = text;
    return element;
  }

  // ---- The whole panel ----

  function show(state) {
    latestState = state;
    if (!isRaceRound(state)) progress = null; // a round that ended leaves no progress behind
    codeElement.textContent = state.code;
    showPlayers(state);
    const isHost = state.host === ownName;
    const isRunning = state.phase === 'round';
    // Open: neither the countdown nor a round is running. Only then the
    // characters, the mode and the start button can be used.
    const isOpen = state.phase === 'lobby';
    showCharacters(state.players, isOpen);
    showMode(state.mode, isHost, isOpen);
    showStartButton(state, isOpen);
    // During a round "Round running" stands where the character selection
    // and the start button (or "Waiting for the host") were.
    document.getElementById('lobby-character-area').hidden = isRunning;
    document.getElementById('lobby-round').hidden = !isRunning;
    document.getElementById('lobby-host-area').hidden = !isHost || isRunning;
    document.getElementById('lobby-waiting').hidden = isHost || isRunning;
  }

  function setPlayers(players) {
    if (!latestState || !Array.isArray(players)) return;
    latestState.players = players;
    showPlayers(latestState);
    showCharacters(players);
  }

  function leaveLobby() {
    Game.net.ask({ type: 'leave_lobby' });
  }

  Game.lobby = {
    setup: setup,
    setOwnName: setOwnName,
    setOwnFreeRider: setOwnFreeRider,
    setPlayers: setPlayers,
    showProgress: showProgress,
    leaveLobby: leaveLobby,
    show: show
  };
})();
