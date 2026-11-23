// Station 6: catch three waves when the crest passes under the board.
window.Game = window.Game || {};

(function () {
  'use strict';

  const GOAL = 3;
  const PAUSE_MS = 320;
  const BOARD_POSITION = 61;
  const CATCH_MARGIN = 8;
  const WAVE_START = -12;
  const WAVE_END = 112;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function start(body, content, done) {
    const duration = content && content.wave_duration_ms;
    if (!Number.isInteger(duration) || duration < 1800 || duration > 2400) {
      body.append(element('p', 'surf-feedback', 'This task could not be loaded.'));
      return;
    }

    const game = element('div', 'surf-game');
    const scene = element('div', 'surf-scene');
    scene.setAttribute('aria-hidden', 'true');
    scene.style.setProperty('--board-position', BOARD_POSITION + '%');
    scene.style.setProperty('--catch-width', CATCH_MARGIN * 2 + '%');
    const wave = element('div', 'surf-wave');
    const target = element('div', 'surf-target');
    const board = element('div', 'surf-board');
    // Only drawing (style.css): the board's shadow, the foam of a catch, and
    // one mark per wave to catch, filled as they are caught.
    const shadow = element('div', 'surf-shadow');
    const splash = element('div', 'surf-splash');
    const marks = element('div', 'surf-marks');
    const markers = [];
    for (let index = 0; index < GOAL; index += 1) {
      const mark = element('span', 'surf-mark');
      marks.append(mark);
      markers.push(mark);
    }
    scene.append(target, wave, shadow, board, splash, marks);
    // A catch or a miss plays a short animation; its class goes when it ends.
    scene.addEventListener('animationend', (event) => {
      if (event.animationName === 'surf-bob') scene.classList.toggle('surf-caught', false);
      if (event.animationName === 'surf-wobble') scene.classList.toggle('surf-missed', false);
    });

    const controls = element('div', 'surf-controls');
    const catchButton = element('button', 'button button-main surf-catch', 'Catch wave');
    catchButton.type = 'button';
    const score = element('p', 'surf-score', '0 / 3 waves caught');
    controls.append(catchButton, score);

    const feedback = element('p', 'surf-feedback');
    feedback.setAttribute('role', 'status');
    game.append(scene, controls, feedback);
    body.append(game);
    catchButton.focus({ preventScroll: true });

    const started = performance.now();
    const cycle = duration + PAUSE_MS;
    let caught = 0;
    let attemptedWave = -1;
    let stopped = false;
    let frame;

    function currentWave(now) {
      const elapsed = Math.max(0, now - started);
      const waveNumber = Math.floor(elapsed / cycle);
      const age = elapsed % cycle;
      const position = WAVE_START + (WAVE_END - WAVE_START) * age / duration;
      return { waveNumber, position, passing: age < duration };
    }

    function draw(now) {
      const current = currentWave(now);
      wave.hidden = !current.passing;
      wave.style.left = current.position + '%';
      scene.classList.toggle('surf-in-range',
        current.passing && current.waveNumber !== attemptedWave
        && Math.abs(current.position - BOARD_POSITION) <= CATCH_MARGIN);
      frame = requestAnimationFrame(draw);
    }

    function stop() {
      stopped = true;
      cancelAnimationFrame(frame);
      document.removeEventListener('keydown', onKey);
    }

    function tryCatch() {
      if (stopped) return;
      const current = currentWave(performance.now());
      if (!current.passing || current.waveNumber === attemptedWave) return;
      attemptedWave = current.waveNumber;
      const distance = current.position - BOARD_POSITION;
      if (Math.abs(distance) > CATCH_MARGIN) {
        feedback.textContent = distance < 0 ? 'Too early. Try the next wave.' : 'Too late. Try the next wave.';
        scene.classList.toggle('surf-missed', true);
        return;
      }

      caught += 1;
      markers[caught - 1].classList.toggle('surf-mark-done', true);
      scene.classList.toggle('surf-caught', true);
      score.textContent = caught + ' / ' + GOAL + ' waves caught';
      if (caught < GOAL) {
        feedback.textContent = 'Caught! ' + score.textContent + '.';
        return;
      }

      catchButton.disabled = true;
      feedback.textContent = 'All three waves caught!';
      stop();
      done();
    }

    scene.addEventListener('click', tryCatch);
    catchButton.addEventListener('click', tryCatch);
    // Holding Enter should not submit an attempt on every passing wave.
    catchButton.addEventListener('keydown', (event) => {
      if (event.repeat && event.key === 'Enter') event.preventDefault();
    });
    // A click on the water moves the focus from the button to the window, so
    // Space and Enter catch wherever the focus is in the window (S-221). On a
    // button they do what the button does: the browser clicks it.
    function onKey(event) {
      if (event.repeat || event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key !== ' ' && event.key !== 'Enter') return;
      if (event.target && event.target.tagName === 'BUTTON') return;
      event.preventDefault();
      tryCatch();
    }
    document.addEventListener('keydown', onKey);
    draw(started);
    return stop;
  }

  Game.minigames.register('catch_the_wave', {
    instructions: 'Tap the water or press Catch wave as the crest passes under the board. Catch three waves.',
    start: start,
  });
})();
