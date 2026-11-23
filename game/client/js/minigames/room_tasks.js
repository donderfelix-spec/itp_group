// The three campus tasks of stations 8, 9 and 11 (recipe, lunch tray,
// budget). The content is drawn by the server; these small puzzles only
// handle presentation and mouse/keyboard interaction (S-19). Stations 7, 10
// and 12 are in campus_challenges.js (S-189, S-208).
window.Game = window.Game || {};

(function () {
  const BROKEN = 'This task could not be loaded.';
  const INSTRUCTIONS = {
    food: 'Remove the discoloured pieces from the tray.',
    recipe: 'Follow the recipe. The group deadline runs on caffeine.',
    budget: 'Scan emergency supplies until the total matches the budget.',
  };

  function element(tag, className, text) {
    const made = document.createElement(tag);
    made.className = className;
    if (text !== undefined) made.textContent = text;
    return made;
  }

  function button(text, click, className = '') {
    const made = element('button', 'campus-piece ' + className, text);
    made.type = 'button';
    made.addEventListener('click', () => { if (!made.disabled) click(made); });
    return made;
  }

  // Small original drawings, built as DOM nodes rather than HTML strings.
  // All artwork is decorative: the adjacent label carries the same meaning.
  function svgPart(tag, attributes, ...children) {
    const made = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attributes).forEach(([name, value]) => made.setAttribute(name, String(value)));
    made.append(...children);
    return made;
  }

  function picture(className) {
    return svgPart('svg', { viewBox: '0 0 120 90', class: className, 'aria-hidden': 'true', focusable: 'false' });
  }

  function line(x1, y1, x2, y2, stroke = '#2E2A3B', width = 3) {
    return svgPart('line', { x1, y1, x2, y2, stroke, 'stroke-width': width, 'stroke-linecap': 'round' });
  }

  // One grain or piece, directly overhead. These drawings contain no
  // plate: all of them live together in the shared lunch tray below.
  function trayFoodDrawing(kind, index, mouldy) {
    const drawing = picture('campus-tray-food-art');
    // Bad pieces have the same shapes and details, only a different colour.
    // No marks or labels give away which piece the player should remove.
    if (kind === 'rice') {
      drawing.setAttribute('viewBox', '20 25 80 42');
      drawing.append(svgPart('ellipse', { cx: 60, cy: 46, rx: 30, ry: 10, transform: 'rotate(-12 60 46)', fill: mouldy ? '#92A477' : '#FFF1C9', stroke: mouldy ? '#62784E' : '#B7A57E', 'stroke-width': 2 }),
        svgPart('path', { d: 'M40 48 Q57 39 79 41', fill: 'none', stroke: mouldy ? '#B2BE91' : '#FFFBEB', 'stroke-width': 3, 'stroke-linecap': 'round' }));
    } else if (kind === 'vegetable' && index % 2 === 0) {
      drawing.append(svgPart('ellipse', { cx: 60, cy: 46, rx: 27, ry: 23, fill: mouldy ? '#8C9276' : '#E68C3D', stroke: mouldy ? '#5A6550' : '#784A2E', 'stroke-width': 2.5 }),
        svgPart('ellipse', { cx: 59, cy: 44, rx: 19, ry: 16, fill: mouldy ? '#A6AE8B' : '#F5AB50', stroke: mouldy ? '#778366' : '#D37D35', 'stroke-width': 2 }),
        svgPart('path', { d: 'M59 32 L62 40 L70 43 L63 47 L60 56 L55 47 L47 44 L55 40Z', fill: mouldy ? '#BCC3A1' : '#F7CC7A' }));
    } else if (kind === 'vegetable') {
      drawing.append(svgPart('path', { d: 'M54 42 L69 42 L73 69 L54 69Z', fill: mouldy ? '#A69E87' : '#A3B46D', stroke: mouldy ? '#6D6255' : '#506444', 'stroke-width': 2.5 }),
        svgPart('path', { d: 'M61 45 V61 M61 55 L49 45 M62 52 L75 44', fill: 'none', stroke: mouldy ? '#877960' : '#71894F', 'stroke-width': 2 }));
      [[43, 37, 15], [60, 29, 17], [78, 37, 15], [61, 43, 17]].forEach(([x, y, r]) => {
        drawing.append(svgPart('circle', { cx: x, cy: y, r, fill: mouldy ? '#A68C75' : '#6C9255', stroke: mouldy ? '#6A5A48' : '#415B39', 'stroke-width': 2 }));
      });
      [[39, 33], [56, 24], [75, 31], [63, 39]].forEach(([x, y]) => drawing.append(svgPart('circle', { cx: x, cy: y, r: 4, fill: mouldy ? '#BCAB8A' : '#91AC6A' })));
    } else {
      drawing.append(svgPart('path', { d: 'M25 44 Q23 25 47 22 L73 26 Q99 31 96 51 Q96 70 72 69 L47 65 Q28 65 25 44Z', fill: mouldy ? '#8D9C78' : '#CC945E', stroke: mouldy ? '#52674C' : '#765239', 'stroke-width': 2.5 }),
        svgPart('path', { d: 'M31 42 Q34 29 49 29 L73 32 Q88 36 87 49 Q86 60 70 61 L48 57 Q34 57 31 42Z', fill: mouldy ? '#ACB992' : '#E3B57B' }),
        svgPart('path', { d: 'M42 38 L74 43 M40 47 L72 52', fill: 'none', stroke: mouldy ? '#7B8A68' : '#B07D4F', 'stroke-width': 2.5, 'stroke-linecap': 'round' }),
        svgPart('path', { d: 'M40 33 Q57 29 72 35', fill: 'none', stroke: mouldy ? '#C8D0AD' : '#F3CFA0', 'stroke-width': 3, 'stroke-linecap': 'round' }));
    }
    return drawing;
  }

  function foodKind(item) {
    return typeof item.id === 'string' ? item.id.split('-')[0] : null;
  }

  function foodItemsAreUsable(items) {
    if (items.length !== 16) return false;
    const counts = { rice: 10, vegetable: 3, chicken: 3 };
    const badCounts = { rice: 3, vegetable: 1, chicken: 1 };
    const labels = { rice: 'Rice grain', vegetable: 'Vegetable piece', chicken: 'Chicken piece' };
    if (!items.every((item) => typeof item.id === 'string' && /^(rice|vegetable|chicken)-[0-9]$/.test(item.id)
      && Number(item.id.split('-')[1]) < counts[foodKind(item)] && item.label === labels[foodKind(item)])) return false;
    return Object.keys(counts).every((kind) => {
      const pieces = items.filter((item) => foodKind(item) === kind);
      return pieces.length === counts[kind] && pieces.filter((item) => item.remove).length === badCounts[kind];
    });
  }

  function productDrawing(name) {
    const drawing = picture('campus-product-art');
    const label = name.toLowerCase();
    if (label.includes('banana')) {
      drawing.append(svgPart('path', { d: 'M31 28 Q42 77 91 50 Q73 94 38 71 Q24 58 26 32Z', fill: '#FFD23F', stroke: '#2E2A3B', 'stroke-width': 3 }), line(26, 29, 33, 25));
    } else if (label.includes('paper')) {
      drawing.append(svgPart('path', { d: 'M30 17 L79 17 L93 31 L93 74 L30 74Z', fill: '#FFFDF5', stroke: '#2E2A3B', 'stroke-width': 3 }),
        svgPart('path', { d: 'M79 17 V32 H93', fill: '#CFE0D7', stroke: '#2E2A3B', 'stroke-width': 2 }));
      [43, 53, 63].forEach((y) => drawing.append(line(42, y, 79, y, '#8FA6A3', 2)));
    } else if (label.includes('coffee')) {
      drawing.append(svgPart('rect', { x: 34, y: 19, width: 51, height: 57, rx: 8, fill: '#A97453', stroke: '#2E2A3B', 'stroke-width': 3 }),
        svgPart('rect', { x: 29, y: 16, width: 60, height: 12, rx: 3, fill: '#2E2A3B' }),
        svgPart('ellipse', { cx: 60, cy: 48, rx: 14, ry: 17, fill: '#FFD23F' }), line(65, 36, 55, 60, '#76513F', 3));
    } else {
      const noodles = label.includes('noodle');
      drawing.append(svgPart('path', { d: 'M29 19 L91 19 L86 75 L34 75Z', fill: noodles ? '#F2695C' : '#B3C5A1', stroke: '#2E2A3B', 'stroke-width': 3 }),
        line(31, 24, 88, 24, '#2E2A3B', 2), line(35, 69, 85, 69, '#2E2A3B', 2),
        svgPart('ellipse', { cx: 60, cy: 47, rx: 20, ry: 15, fill: '#FFF3CA', stroke: '#2E2A3B', 'stroke-width': 2 }));
      drawing.append(noodles ? svgPart('path', { d: 'M46 44 Q51 37 54 46 T63 46 T74 45 M46 51 Q54 43 60 52 T75 51', fill: 'none', stroke: '#C99B47', 'stroke-width': 2.5 })
        : svgPart('circle', { cx: 60, cy: 47, r: 10, fill: '#A57852', stroke: '#79513E', 'stroke-width': 2 }));
    }
    return drawing;
  }

  function sceneLabel(text, detail) {
    const label = element('div', 'campus-scene-label');
    label.append(element('strong', '', text), element('span', '', detail));
    return label;
  }

  function texts(values, minimum = 1) {
    return Array.isArray(values) && values.length >= minimum && values.length <= 24
      && values.every((value) => typeof value === 'string' && value.length > 0 && value.length < 160);
  }

  function distinct(values) { return new Set(values).size === values.length; }
  function cents(value) { return Number.isInteger(value) && value > 0 && value < 100000; }
  function money(value) { return '€' + (value / 100).toFixed(2); }

  // A bad network payload leaves an explanatory, closable window.
  function isUsable(content) {
    if (!content || typeof content !== 'object') return false;
    if (content.puzzle === 'cleanup') {
      return content.theme === 'food' && Array.isArray(content.items)
        && content.items.length >= 2 && content.items.length <= 16
        && content.items.every((item) => item && ['number', 'string'].includes(typeof item.id)
          && typeof item.label === 'string' && item.label.length > 0 && typeof item.remove === 'boolean')
        && distinct(content.items.map((item) => item.id))
        && content.items.some((item) => item.remove) && content.items.some((item) => !item.remove)
        && foodItemsAreUsable(content.items);
    }
    if (content.puzzle === 'recipe') {
      return typeof content.drink === 'string' && texts(content.controls, 2) && distinct(content.controls)
        && texts(content.recipe, 2) && content.recipe.every((step) => content.controls.includes(step));
    }
    if (content.puzzle === 'budget') {
      return cents(content.target) && Array.isArray(content.products) && content.products.length >= 3
        && content.products.length <= 12 && content.products.every((product) => product
          && typeof product.name === 'string' && product.name.length > 0 && cents(product.price))
        && distinct(content.products.map((product) => product.name));
    }
    return false;
  }

  function start(body, content, done) {
    if (!isUsable(content)) {
      body.append(element('p', 'campus-feedback', BROKEN));
      return;
    }
    const started = performance.now();
    const timers = new Set();
    let finished = false;
    const game = element('div', 'campus-game campus-game-' + content.puzzle);
    const instruction = content.puzzle === 'cleanup' ? INSTRUCTIONS.food : INSTRUCTIONS[content.puzzle];
    const feedback = element('p', 'campus-feedback', 'Your teammates are counting on you. Probably.');
    feedback.setAttribute('role', 'status');
    game.append(element('p', 'campus-instruction', instruction));
    body.append(game, feedback);

    function later(action, delay) {
      const timer = setTimeout(() => { timers.delete(timer); action(); }, delay);
      timers.add(timer);
      return timer;
    }

    function wrong(piece, message) {
      if (finished) return;
      feedback.textContent = message;
      piece.classList.add('campus-wrong');
      later(() => piece.classList.remove('campus-wrong'), 450);
    }

    function progress(message) { if (!finished) feedback.textContent = message; }

    function complete() {
      if (finished) return;
      finished = true;
      game.querySelectorAll('button').forEach((control) => { control.disabled = true; });
      feedback.textContent = 'Crisis averted. Sending your work…';
      feedback.classList.add('campus-feedback-success');
      // The server's minimum is one second. A fast, valid player should not
      // lose a solved puzzle; closing meanwhile cancels this callback too.
      later(done, Math.max(0, 1100 - (performance.now() - started)));
    }

    const helpers = { game, wrong, progress, complete };
    if (content.puzzle === 'cleanup') lunchTray(content, helpers);
    if (content.puzzle === 'recipe') recipe(content, helpers);
    if (content.puzzle === 'budget') budget(content, helpers);

    return function stop() {
      finished = true;
      timers.forEach((timer) => clearTimeout(timer));
      timers.clear();
      game.querySelectorAll('button').forEach((control) => { control.disabled = true; });
    };
  }

  function lunchTray(content, ui) {
    ui.game.classList.add('campus-game-lunch');
    ui.game.append(element('p', 'campus-story', 'Rice. Veg. Chicken. One suspicious group contribution.'));
    const scene = element('section', 'campus-lunch-scene');
    scene.setAttribute('aria-label', 'Lunch inspection');
    const header = element('div', 'campus-tray-header');
    const total = content.items.filter((item) => item.remove).length;
    const count = element('span', 'campus-lunch-count', '0 / ' + total + ' discarded');
    header.append(element('strong', '', 'NOVA CANTEEN'), count);
    const tray = element('div', 'campus-meal-tray');
    tray.setAttribute('aria-label', 'One lunch tray with rice, vegetables and chicken');
    const groups = {};
    ['rice', 'vegetable', 'chicken'].forEach((kind) => {
      const compartment = element('div', 'campus-tray-compartment campus-tray-compartment-' + kind);
      groups[kind] = compartment;
      tray.append(compartment);
    });
    scene.append(header, tray);
    ui.game.append(scene);
    const places = {
      rice: [[16.67, 12.5, -10], [50, 12.5, 12], [83.33, 12.5, -8],
        [16.67, 37.5, 16], [50, 37.5, -14], [83.33, 37.5, 8],
        [16.67, 62.5, -12], [50, 62.5, 10], [83.33, 62.5, -7], [50, 87.5, 14]],
      vegetable: [[16.67, 50, -8], [50, 50, 12], [83.33, 50, -10]],
      chicken: [[16.67, 50, -13], [50, 50, 8], [83.33, 50, -8]],
    };
    let removed = 0;
    // Display order is spatial and stable even though the server shuffles
    // the payload. Native buttons keep every individual piece keyboard usable.
    [...content.items].sort((a, b) => a.id.localeCompare(b.id)).forEach((item) => {
      const kind = foodKind(item);
      const index = Number(item.id.split('-')[1]);
      const piece = button('', (clicked) => {
        if (!item.remove) {
          ui.wrong(clicked, 'Leave that piece on the tray.');
          return;
        }
        removed += 1;
        clicked.disabled = true;
        clicked.hidden = true;
        count.textContent = removed + ' / ' + total + ' discarded';
        ui.progress(removed + '/' + total + ' pieces removed.');
        if (removed === total) ui.complete();
      });
      piece.className = 'campus-tray-piece campus-tray-piece-' + kind;
      piece.setAttribute('data-food-id', item.id);
      const description = item.label + ' ' + (index + 1);
      piece.setAttribute('aria-label', description);
      const [x, y, angle] = places[kind][index];
      piece.style.left = x + '%';
      piece.style.top = y + '%';
      piece.style.setProperty('--food-angle', angle + 'deg');
      piece.append(trayFoodDrawing(kind, index, item.remove));
      groups[kind].append(piece);
    });
  }

  function recipe(content, ui) {
    ui.game.append(element('p', 'campus-story', 'The Latecomer ordered “' + content.drink + '”. This is now your responsibility.'));
    const slip = element('ol', 'campus-recipe');
    content.recipe.forEach((step) => slip.append(element('li', '', step)));
    const cup = element('div', 'campus-coffee-cup');
    const fill = element('span', 'campus-coffee-fill');
    cup.append(fill, element('span', 'campus-coffee-label', 'DEADLINE FUEL'));
    const controls = element('div', 'campus-pile campus-coffee-controls');
    const recipeCard = element('div', 'campus-recipe-card');
    recipeCard.append(sceneLabel('MON CAFÉ', 'Order #404 · sleep not found'), element('p', 'campus-order-name', content.drink), slip);
    const machine = element('section', 'campus-coffee-machine');
    machine.append(sceneLabel('DEADLINE-O-MATIC', 'The last working machine on campus'), cup, controls);
    const layout = element('div', 'campus-coffee-layout');
    layout.append(recipeCard, machine);
    ui.game.append(layout);
    let next = 0;
    content.controls.forEach((control) => controls.append(button(control, (clicked) => {
      if (control !== content.recipe[next]) {
        ui.wrong(clicked, 'That is not the next step. The caffeine committee objects.');
        return;
      }
      slip.children[next].classList.add('campus-step-done');
      next += 1;
      fill.style.height = (next / content.recipe.length * 100) + '%';
      ui.progress(next + '/' + content.recipe.length + ' steps. The deadline is looking less blurry.');
      if (next === content.recipe.length) ui.complete();
    })));
  }

  function budget(content, ui) {
    ui.game.append(element('p', 'campus-story', 'The Founder calls these “essential project expenses”. The budget is less optimistic.'));
    const display = element('div', 'campus-budget-display');
    const target = element('div', '', 'Budget');
    target.append(element('strong', '', money(content.target)));
    const totalBox = element('div', '', 'Scanned');
    const totalText = element('strong', '', money(0));
    totalBox.append(totalText);
    display.append(target, totalBox);
    const belt = element('div', 'campus-pile campus-belt');
    const checkout = element('section', 'campus-checkout');
    const receipt = element('div', 'campus-receipt');
    receipt.append(sceneLabel('PINGO DOCE', 'Group project survival fund'), display,
      element('p', 'campus-receipt-footer', 'NO REFUNDS ON LOST SLEEP'));
    checkout.append(receipt, element('p', 'campus-small', 'Click a scanned item again to put it back.'), belt);
    ui.game.append(checkout);
    const scanned = new Set();
    let total = 0;
    content.products.forEach((product, index) => {
      const piece = button('', (clicked) => {
        if (scanned.has(index)) {
          scanned.delete(index);
          total -= product.price;
        } else {
          if (total + product.price > content.target) {
            ui.wrong(clicked, 'Over budget. “Put it on the company card” is not a strategy.');
            return;
          }
          scanned.add(index);
          total += product.price;
        }
        clicked.classList.toggle('campus-scanned', scanned.has(index));
        clicked.setAttribute('aria-pressed', String(scanned.has(index)));
        clicked.querySelector('.campus-piece-state').textContent = scanned.has(index) ? '✓ Scanned · click to return' : 'Scan item';
        totalText.textContent = money(total);
        ui.progress(money(content.target - total) + ' left in the budget.');
        if (total === content.target) ui.complete();
      });
      piece.setAttribute('aria-pressed', 'false');
      piece.append(productDrawing(product.name), element('span', 'campus-piece-label', product.name),
        element('strong', 'campus-price', money(product.price)), element('span', 'campus-piece-state', 'Scan item'));
      belt.append(piece);
    });
  }

  // No shared header line: stations 8, 9 and 11 each show their own
  // instruction in the body, like the campus challenges (M2-4.22).
  Game.minigames.register('campus_task', { instructions: '', start });
})();
