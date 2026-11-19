// The minigame of the Canteen, station 3: "Build the tray" (DESIGN.md, section 8).
//
// Six dishes stand at the counter and the order slip names four of them. The
// player clicks these four onto the tray, in any order. A dish that is not on
// the slip hops towards the tray, shakes and is back at the counter: only the
// wrong piece is reset (S-58), the tray keeps what it had.
//
// The server draws the content (server/modes/build_tray.py):
//   { kind: 'build_tray', dishes: [six names, in counter order], order: [four of them] }
//
// The dishes are drawn with CSS only (the "tray-" block in css/style.css).

window.Game = window.Game || {};

(function () {
  const INSTRUCTIONS = 'Put the four dishes from the order slip on the tray.';
  const BROKEN_TEXT = 'This task could not be loaded.';
  const SLIP_LABEL = 'Order slip';
  const COUNTER_LABEL = 'Counter';
  const TRAY_LABEL = 'Tray';
  const TICK = '✓';

  const DISHES_AT_COUNTER = 6;
  const DISHES_ON_SLIP = 4;
  // As long as the animation "tray-wrong" in style.css.
  const WRONG_VISIBLE_MS = 600;

  // Name of a dish -> the CSS class of its drawing. A Map and not a plain
  // object, so a name like "constructor" finds nothing. A name that is not
  // in here is drawn as an empty plate.
  const DRAWINGS = new Map([
    ['Soup', 'tray-food-soup'],
    ['Bacalhau', 'tray-food-bacalhau'],
    ['Rice', 'tray-food-rice'],
    ['Salad', 'tray-food-salad'],
    ['Pastel de nata', 'tray-food-nata'],
    ['Fruit', 'tray-food-fruit'],
  ]);

  function element(tag, className, text) {
    const made = document.createElement(tag);
    made.className = className;
    if (text !== undefined) made.textContent = text;
    return made;
  }

  // True for a list of exactly `length` different, non-empty texts.
  function isListOfNames(list, length) {
    if (!Array.isArray(list) || list.length !== length) return false;
    const areTexts = list.every((name) => typeof name === 'string' && name.length > 0);
    return areTexts && new Set(list).size === length;
  }

  // The content comes over the network, so it is checked before it is used.
  function isUsable(content) {
    if (!content || typeof content !== 'object') return false;
    if (!isListOfNames(content.dishes, DISHES_AT_COUNTER)) return false;
    if (!isListOfNames(content.order, DISHES_ON_SLIP)) return false;
    return content.order.every((name) => content.dishes.includes(name));
  }

  // A labelled area: the small heading and, below it, the box for the pieces.
  function buildArea(areaClass, label, boxClass) {
    const area = element('div', 'tray-area ' + areaClass);
    const box = element('div', boxClass);
    area.append(element('span', 'tray-label', label), box);
    return { area: area, box: box };
  }

  // One dish: its drawing and, always, its name.
  function buildDish(name) {
    const dish = element('button', 'tray-dish');
    dish.type = 'button';
    const drawing = element('span', 'tray-food ' + (DRAWINGS.get(name) || ''));
    drawing.setAttribute('aria-hidden', 'true');
    dish.append(drawing, element('span', 'tray-name', name));
    return dish;
  }

  // One line of the order slip: a box for the tick, then the name.
  function buildSlipLine(name) {
    const line = element('li', 'tray-slip-line');
    const box = element('span', 'tray-slip-box');
    line.append(box, element('span', 'tray-slip-name', name));
    return { line: line, box: box };
  }

  function start(body, content, done) {
    if (!isUsable(content)) {
      body.append(element('p', 'tray-broken', BROKEN_TEXT));
      return undefined;
    }

    const onTray = new Set(); // names of the dishes that are on the tray
    const slipLines = new Map(); // name -> its line on the order slip
    const wrongTimers = new Map(); // dish that is hopping back -> its timer
    let isSolved = false;

    const slip = buildArea('tray-area-slip', SLIP_LABEL, 'tray-slip');
    const counter = buildArea('tray-area-counter', COUNTER_LABEL, 'tray-counter');
    const tray = buildArea('tray-area-tray', TRAY_LABEL, 'tray-tray');

    const slipList = element('ul', 'tray-slip-list');
    content.order.forEach(function (name) {
      const made = buildSlipLine(name);
      slipLines.set(name, made);
      slipList.append(made.line);
    });
    slip.box.append(slipList);

    // Every dish stands in a fixed place of the counter. The place stays
    // when the dish moves to the tray, so the other dishes do not jump.
    content.dishes.forEach(function (name) {
      const place = element('div', 'tray-place');
      const dish = buildDish(name);
      dish.addEventListener('click', () => onDishClick(name, dish));
      place.append(dish);
      counter.box.append(place);
    });

    const slots = [];
    for (let number = 0; number < DISHES_ON_SLIP; number += 1) {
      const slot = element('div', 'tray-slot');
      slots.push(slot);
      tray.box.append(slot);
    }

    const game = element('div', 'tray-game');
    game.append(slip.area, counter.area, tray.area);
    body.append(game);

    function onDishClick(name, dish) {
      // A dish on the tray stays there: a second click must not count again.
      if (isSolved || onTray.has(name)) return;
      if (content.order.includes(name)) {
        putOnTray(name, dish);
      } else {
        sendBack(dish);
      }
    }

    function putOnTray(name, dish) {
      slots[onTray.size].append(dish);
      onTray.add(name);
      dish.disabled = true;
      dish.classList.add('tray-dish-placed');
      const slipLine = slipLines.get(name);
      slipLine.line.classList.add('tray-slip-line-done');
      slipLine.box.textContent = TICK;
      if (onTray.size === DISHES_ON_SLIP) {
        isSolved = true;
        done();
      }
    }

    // The wrong dish hops towards the tray, shakes and is back at the
    // counter. It never leaves its place, so nothing else can change.
    function sendBack(dish) {
      if (wrongTimers.has(dish)) return; // it is still on its way back
      dish.classList.add('tray-dish-wrong');
      const timer = setTimeout(function () {
        wrongTimers.delete(dish);
        dish.classList.remove('tray-dish-wrong');
      }, WRONG_VISIBLE_MS);
      wrongTimers.set(dish, timer);
    }

    // The frame calls this when the window closes: no timer is left behind.
    return function stop() {
      isSolved = true;
      wrongTimers.forEach((timer) => clearTimeout(timer));
      wrongTimers.clear();
    };
  }

  Game.minigames.register('build_tray', { instructions: INSTRUCTIONS, start: start });
})();
