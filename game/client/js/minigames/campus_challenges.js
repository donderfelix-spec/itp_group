// Three distinct campus challenges (stations 7, 10, 12). The old campus_task
// puzzles they replaced are removed from room_tasks.js (S-208).
window.Game = window.Game || {};

(function () {
  'use strict';

  function node(tag, className, text) {
    const result = document.createElement(tag);
    result.className = className;
    if (text !== undefined) result.textContent = text;
    return result;
  }

  function control(text, action, className = '') {
    const result = node('button', 'challenge-button ' + className, text);
    result.type = 'button';
    result.addEventListener('click', () => { if (!result.disabled) action(); });
    return result;
  }

  function strings(values, length) {
    return Array.isArray(values) && values.length === length
      && new Set(values).size === length
      && values.every((value) => typeof value === 'string' && value.length > 0 && value.length < 100);
  }

  function usable(content) {
    if (!content || typeof content !== 'object') return false;
    if (content.puzzle === 'chart') {
      return Array.isArray(content.rows) && content.rows.length === 3
        && content.rows.every((row) => row && typeof row.label === 'string'
          && Number.isInteger(row.count) && row.count >= 2 && row.count <= 8 && row.sample === 10)
        && strings(content.rows.map((row) => row.label), 3)
        && strings(content.initial_labels, 3)
        && content.initial_labels.every((label) => content.rows.some((row) => row.label === label))
        && Array.isArray(content.initial_values) && content.initial_values.length === 3
        && content.initial_values.every((value) => Number.isInteger(value) && value >= 0 && value <= 100 && value % 10 === 0);
    }
    if (content.puzzle === 'chat_logic') {
      return strings(content.people, 4) && strings(content.jobs, 4)
        && Array.isArray(content.slots) && content.slots.join(',') === '9,10,11,12'
        && Array.isArray(content.clues) && content.clues.length === 5
        && content.clues.every((clue) => clue && typeof clue.from === 'string' && typeof clue.text === 'string')
        && Array.isArray(content.schedule) && content.schedule.length === 4
        && content.schedule.every((entry) => entry && content.people.includes(entry.person)
          && content.jobs.includes(entry.job) && content.slots.includes(entry.slot))
        && new Set(content.schedule.map((entry) => entry.person)).size === 4
        && new Set(content.schedule.map((entry) => entry.job)).size === 4
        && new Set(content.schedule.map((entry) => entry.slot)).size === 4;
    }
    return content.puzzle === 'seagull_defence' && content.goal === 6
      && Array.isArray(content.waves) && content.waves.length === 12
      && content.waves.filter((wave) => wave && wave.cargo === 'page').length === 8
      && content.waves.every((wave) => wave && Number.isInteger(wave.lane) && wave.lane >= 0 && wave.lane <= 2
        && ['page', 'coffee'].includes(wave.cargo) && Number.isInteger(wave.duration)
        && wave.duration >= 1200 && wave.duration <= 2200);
  }

  function start(body, content, done) {
    if (!usable(content)) {
      body.append(node('p', 'campus-feedback', 'This task could not be loaded.'));
      return;
    }
    const game = node('div', 'campus-challenge challenge-game-' + content.puzzle);
    const feedback = node('p', 'challenge-feedback', '');
    feedback.setAttribute('role', 'status');
    body.append(game, feedback);
    const timers = new Set();
    const disposers = [];
    const started = performance.now();
    let stopped = false;
    let completed = false;

    function later(action, delay) {
      const id = setTimeout(() => {
        timers.delete(id);
        if (!stopped && !completed) action();
      }, delay);
      timers.add(id);
      return id;
    }

    function clearTimers() {
      timers.forEach((id) => clearTimeout(id));
      timers.clear();
    }

    function complete() {
      if (stopped || completed) return;
      completed = true;
      clearTimers();
      game.querySelectorAll('button, select').forEach((item) => { item.disabled = true; });
      feedback.textContent = 'Crisis averted. Sending your work…';
      feedback.classList.add('challenge-success');
      const id = setTimeout(() => {
        timers.delete(id);
        if (!stopped) done();
      }, Math.max(0, 1100 - (performance.now() - started)));
      timers.add(id);
    }

    const ui = { game, feedback, later, clearTimers, complete, disposers,
      active: () => !stopped && !completed };
    if (content.puzzle === 'chart') chart(content, ui);
    if (content.puzzle === 'chat_logic') chat(content, ui);
    if (content.puzzle === 'seagull_defence') defence(content, ui);
    return function stop() {
      stopped = true;
      clearTimers();
      disposers.forEach((dispose) => dispose());
      game.querySelectorAll('button, select').forEach((item) => { item.disabled = true; });
    };
  }

  function selector(labelText, values, onChange) {
    const label = node('label', 'challenge-select-label', labelText);
    const select = node('select', 'challenge-select');
    select.setAttribute('aria-label', labelText);
    values.forEach((value) => {
      const option = node('option', '', String(value));
      option.value = String(value);
      select.append(option);
    });
    select.addEventListener('change', () => onChange(select.value));
    label.append(select);
    return { label, select };
  }

  function chart(content, ui) {
    ui.game.append(node('p', 'challenge-brief', 'The Consultant has inflated the chart. Rebuild it from the survey notes: fix all labels, percentages and the baseline.'));
    const evidence = node('section', 'challenge-evidence');
    evidence.setAttribute('aria-label', 'Survey notes');
    evidence.append(node('h3', '', 'Actual field research'));
    content.rows.forEach((row) => evidence.append(node('p', '', row.label + ' — ' + row.count + ' of ' + row.sample + ' students')));
    ui.game.append(evidence);
    const chartBox = node('section', 'challenge-chart');
    chartBox.setAttribute('aria-label', 'Chart editor');
    const labels = content.initial_labels.slice();
    const values = content.initial_values.slice();
    let baseline = 40;
    const bars = [];
    content.rows.forEach((_row, index) => {
      const column = node('div', 'challenge-column');
      const track = node('div', 'challenge-bar-track');
      const bar = node('div', 'challenge-bar');
      const number = node('strong', 'challenge-bar-value');
      track.append(bar, number);
      const choice = selector('Bar ' + (index + 1) + ' label', content.rows.map((row) => row.label), (value) => {
        labels[index] = value;
      });
      choice.select.value = labels[index];
      const adjustment = node('div', 'challenge-stepper');
      adjustment.append(control('−10', () => { values[index] = Math.max(0, values[index] - 10); redraw(); }),
        control('+10', () => { values[index] = Math.min(100, values[index] + 10); redraw(); }));
      column.append(track, choice.label, adjustment);
      chartBox.append(column);
      bars.push({ bar, number });
    });
    const axis = selector('Vertical axis starts at', [40, 20, 0], (value) => { baseline = Number(value); redraw(); });
    ui.game.append(chartBox, axis.label);
    const publish = control('Publish honest chart', () => {
      const invalid = labels.some((label, index) => content.rows.find((row) => row.label === label).count * 10 !== values[index]);
      if (baseline !== 0 || invalid || new Set(labels).size !== 3) {
        ui.feedback.textContent = 'The evidence does not match yet. Check the scale and each bar against its survey row.';
        return;
      }
      ui.complete();
    }, 'challenge-primary');
    ui.game.append(publish);
    function redraw() {
      bars.forEach(({ bar, number }, index) => {
        bar.style.height = Math.max(0, (values[index] - baseline) / (100 - baseline) * 100) + '%';
        number.textContent = values[index] + '%';
        bar.setAttribute('aria-label', 'Bar ' + (index + 1) + ': ' + values[index] + ' percent');
      });
      chartBox.setAttribute('data-baseline', baseline);
    }
    redraw();
  }

  function chat(content, ui) {
    ui.game.append(node('p', 'challenge-brief', 'Four teammates. Four presentation slots. Nobody sent a schedule. Use the messages to match each person to one time and one deliverable.'));
    const thread = node('section', 'challenge-thread');
    thread.setAttribute('aria-label', 'Group chat clues');
    content.clues.forEach((clue) => {
      const bubble = node('article', 'challenge-message');
      bubble.append(node('strong', '', clue.from), node('p', '', clue.text));
      thread.append(bubble);
    });
    ui.game.append(thread);
    const board = node('section', 'challenge-schedule');
    const chosen = new Map();
    content.people.forEach((person) => {
      const assignment = { slot: '', job: '' };
      chosen.set(person, assignment);
      const row = node('div', 'challenge-schedule-row');
      const time = selector(person + ' time', ['Choose time', ...content.slots.map((slot) => slot + ':00')], (value) => {
        assignment.slot = value;
      });
      const job = selector(person + ' deliverable', ['Choose work', ...content.jobs], (value) => { assignment.job = value; });
      row.append(node('strong', '', person), time.label, job.label);
      board.append(row);
    });
    const confirm = control('Pin the schedule', () => {
      const picked = [...chosen.values()];
      if (picked.some((entry) => !entry.slot || !entry.job || entry.slot === 'Choose time' || entry.job === 'Choose work')) {
        ui.feedback.textContent = 'Give every teammate a time and a deliverable first.';
        return;
      }
      if (new Set(picked.map((entry) => entry.slot)).size !== 4 || new Set(picked.map((entry) => entry.job)).size !== 4) {
        ui.feedback.textContent = 'One person per slot. Each deliverable belongs to exactly one teammate.';
        return;
      }
      if (!content.schedule.every((entry) => {
        const choice = chosen.get(entry.person);
        return choice.slot === entry.slot + ':00' && choice.job === entry.job;
      })) {
        ui.feedback.textContent = 'Someone disagrees. Read every message again: “immediately” means the very next slot.';
        return;
      }
      ui.complete();
    }, 'challenge-primary');
    ui.game.append(board, confirm);
  }

  function defence(content, ui) {
    ui.game.append(node('p', 'challenge-brief', 'The gulls are dropping your draft and stolen coffee. Catch 6 pages in the yellow rescue zone. Let coffee fall. Three mistakes end the attempt, then you can try again. Use lane buttons or keys 1, 2, 3.'));
    const status = node('p', 'challenge-score');
    const arena = node('div', 'challenge-flight');
    arena.setAttribute('aria-label', 'Three rescue lanes');
    const controls = node('div', 'challenge-lanes');
    const lanes = [];
    const names = ['Left', 'Middle', 'Right'];
    const gull = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    gull.setAttribute('viewBox', '0 0 100 50');
    gull.setAttribute('class', 'challenge-gull');
    gull.setAttribute('aria-hidden', 'true');
    const wings = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    wings.setAttribute('d', 'M5 28 Q23 5 48 28 Q74 4 95 28 L70 22 L50 38 L29 23Z');
    wings.setAttribute('fill', '#FFFDF5');
    wings.setAttribute('stroke', '#2E2A3B');
    wings.setAttribute('stroke-width', '3');
    gull.append(wings);
    arena.append(gull);
    let running = false;
    let waveIndex = 0;
    let saved = 0;
    let mistakes = 0;
    let caught = false;
    let current = null;
    let launch = 0;
    let flight = null;

    names.forEach((name, index) => {
      const lane = node('div', 'challenge-flight-lane');
      lane.append(node('span', 'challenge-rescue-zone', 'RESCUE'));
      arena.append(lane);
      lanes.push(lane);
      const catchButton = control((index + 1) + ' · ' + name, () => catchLane(index));
      catchButton.disabled = true;
      controls.append(catchButton);
    });
    const startButton = control('Protect the draft', begin, 'challenge-primary');
    ui.game.append(status, arena, controls, startButton);
    updateStatus();

    function begin() {
      if (!ui.active() || running) return;
      ui.clearTimers();
      waveIndex = 0;
      saved = 0;
      mistakes = 0;
      running = true;
      startButton.hidden = true;
      controls.querySelectorAll('button').forEach((item) => { item.disabled = false; });
      ui.feedback.textContent = 'Wait for the page to enter the yellow zone. Coffee is a decoy.';
      nextWave();
    }

    function updateStatus() {
      status.textContent = saved + ' / ' + content.goal + ' pages · ' + mistakes + ' / 3 mistakes · wave ' + Math.min(waveIndex + 1, content.waves.length) + ' / ' + content.waves.length;
    }

    function failRound() {
      running = false;
      ui.clearTimers();
      if (flight) flight.remove();
      controls.querySelectorAll('button').forEach((item) => { item.disabled = true; });
      startButton.hidden = false;
      startButton.textContent = 'Try another rescue';
      ui.feedback.textContent = 'The gulls won this round. Try again: wait for the yellow zone and ignore coffee.';
    }

    function nextWave() {
      if (!running || !ui.active()) return;
      if (waveIndex === content.waves.length) {
        if (saved >= content.goal) { running = false; ui.complete(); } else failRound();
        return;
      }
      current = content.waves[waveIndex];
      caught = false;
      launch = performance.now();
      flight = node('div', 'challenge-cargo challenge-cargo-' + current.cargo, current.cargo === 'page' ? '▤' : '☕');
      flight.setAttribute('aria-label', (current.cargo === 'page' ? 'Project page' : 'Coffee decoy') + ', ' + names[current.lane] + ' lane');
      flight.style.animationDuration = current.duration + 'ms';
      lanes[current.lane].append(flight);
      updateStatus();
      ui.later(() => {
        if (!caught && current.cargo === 'page') mistakes += 1;
        flight.remove();
        current = null;
        if (mistakes >= 3) { updateStatus(); failRound(); return; }
        waveIndex += 1;
        ui.later(nextWave, 250);
      }, current.duration);
    }

    function catchLane(lane) {
      if (!running || !current || caught || !ui.active()) return;
      const elapsed = performance.now() - launch;
      if (elapsed > current.duration) return;
      if (lane !== current.lane || current.cargo !== 'page' || elapsed < current.duration * 0.5) {
        mistakes += 1;
        ui.feedback.textContent = current.cargo === 'coffee' ? 'That is coffee. Save the work, not the caffeine.' : 'Too early or wrong lane. Catch the page in the yellow zone.';
        updateStatus();
        if (mistakes >= 3) failRound();
        return;
      }
      caught = true;
      saved += 1;
      flight.classList.add('challenge-caught');
      ui.feedback.textContent = 'Page saved. Watch the next lane.';
      updateStatus();
    }

    function onKey(event) {
      if (!running || event.repeat || event.altKey || event.ctrlKey || event.metaKey
        || !['Digit1', 'Digit2', 'Digit3'].includes(event.code)) return;
      const tag = event.target && event.target.tagName;
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || event.target && event.target.isContentEditable) return;
      event.preventDefault();
      catchLane(Number(event.code.slice(-1)) - 1);
    }
    document.addEventListener('keydown', onKey);
    ui.disposers.push(() => document.removeEventListener('keydown', onKey));
  }

  Game.minigames.register('campus_challenge', {
    instructions: '', start,
  });
})();
