// Six campus emergencies. The content is drawn by the server; these small
// puzzles only handle presentation and mouse/keyboard interaction (S-19).
window.Game = window.Game || {};

(function () {
  const BROKEN = 'This task could not be loaded.';
  const INSTRUCTIONS = {
    cleanup: 'Cross out the nonsense buzzwords. Keep the useful content.',
    food: 'Remove the discoloured pieces from the tray.',
    recipe: 'Follow the recipe. The group deadline runs on caffeine.',
    order: "Put the words in order to decode your teammate's excuse.",
    budget: 'Scan emergency supplies until the total matches the budget.',
    seagull: 'Catch the seagull to recover every stolen project page.',
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
      return ['slides', 'food'].includes(content.theme) && Array.isArray(content.items)
        && content.items.length >= 2 && content.items.length <= 16
        && content.items.every((item) => item && ['number', 'string'].includes(typeof item.id)
          && typeof item.label === 'string' && item.label.length > 0 && typeof item.remove === 'boolean')
        && distinct(content.items.map((item) => item.id))
        && content.items.some((item) => item.remove) && content.items.some((item) => !item.remove)
        && (content.theme !== 'food' || foodItemsAreUsable(content.items));
    }
    if (content.puzzle === 'recipe') {
      return typeof content.drink === 'string' && texts(content.controls, 2) && distinct(content.controls)
        && texts(content.recipe, 2) && content.recipe.every((step) => content.controls.includes(step));
    }
    if (content.puzzle === 'order') {
      return texts(content.words, 3) && texts(content.order, 3) && distinct(content.words)
        && content.words.length === content.order.length && distinct(content.order)
        && content.order.every((word) => content.words.includes(word)) && typeof content.hint === 'string';
    }
    if (content.puzzle === 'budget') {
      return cents(content.target) && Array.isArray(content.products) && content.products.length >= 3
        && content.products.length <= 12 && content.products.every((product) => product
          && typeof product.name === 'string' && product.name.length > 0 && cents(product.price))
        && distinct(content.products.map((product) => product.name));
    }
    return content.puzzle === 'seagull' && Number.isInteger(content.pages) && content.pages >= 4 && content.pages <= 6;
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
    const instruction = content.theme === 'food' ? INSTRUCTIONS.food : INSTRUCTIONS[content.puzzle];
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
    if (content.puzzle === 'cleanup') cleanup(content, helpers);
    if (content.puzzle === 'recipe') recipe(content, helpers);
    if (content.puzzle === 'order') order(content, helpers);
    if (content.puzzle === 'budget') budget(content, helpers);
    if (content.puzzle === 'seagull') seagull(content, helpers);

    return function stop() {
      finished = true;
      timers.forEach((timer) => clearTimeout(timer));
      timers.clear();
      game.querySelectorAll('button').forEach((control) => { control.disabled = true; });
    };
  }

  function cleanup(content, ui) {
    if (content.theme === 'food') {
      lunchTray(content, ui);
      return;
    }
    ui.game.append(element('p', 'campus-story', 'The Consultant has added 400% more synergy. Make the slide say something.'));
    const pile = element('div', 'campus-pile campus-slide');
    const scene = element('section', 'campus-presentation-scene');
    scene.append(sceneLabel('GROUP PROJECT_final_FINAL.pptx', 'Slide 07 · the consultant has been here'), pile);
    ui.game.append(scene);
    const total = content.items.filter((item) => item.remove).length;
    let removed = 0;
    content.items.forEach((item) => {
      const piece = button('', (clicked) => {
        if (!item.remove) {
          ui.wrong(clicked, 'That actually means something. Keep it!');
          return;
        }
        removed += 1;
        clicked.disabled = true;
        clicked.classList.add('campus-removed');
        clicked.querySelector('.campus-piece-state').textContent = '✓ Crossed out';
        ui.progress(removed + '/' + total + ' buzzwords removed.');
        if (removed === total) ui.complete();
      }, 'campus-buzzword');
      const drawing = element('span', 'campus-slide-mark', 'Aa');
      drawing.setAttribute('aria-hidden', 'true');
      piece.append(drawing, element('span', 'campus-piece-label', item.label),
        element('span', 'campus-piece-state', item.remove ? 'Buzzword' : 'Useful content'));
      pile.append(piece);
    });
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
    ui.game.append(element('p', 'campus-story', 'The Latecomer ordered a “' + content.drink + '”. This is now your responsibility.'));
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

  function order(content, ui) {
    ui.game.append(element('p', 'campus-story', 'One unread message. Zero accountability.'));
    const hint = element('blockquote', 'campus-chat-hint', content.hint);
    const sentence = element('div', 'campus-sentence');
    sentence.setAttribute('aria-label', 'Decoded message');
    const pile = element('div', 'campus-pile');
    const phone = element('section', 'campus-chat-phone');
    phone.append(sceneLabel('Group project (8)', '7 typing… · 0 working'), element('p', 'campus-chat-time', 'Today, 23:58'), hint,
      element('p', 'campus-chat-caption', 'Rebuild the suspiciously familiar excuse:'), sentence, pile);
    ui.game.append(phone);
    let next = 0;
    content.words.forEach((word) => pile.append(button(word, (clicked) => {
      if (word !== content.order[next]) {
        ui.wrong(clicked, 'That word goes later. The excuse must sound convincing.');
        return;
      }
      sentence.append(element('span', 'campus-word-done', word));
      clicked.disabled = true;
      next += 1;
      ui.progress(next + '/' + content.order.length + ' words decoded.');
      if (next === content.order.length) ui.complete();
    }, 'campus-word')));
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

  function seagull(content, ui) {
    ui.game.append(element('p', 'campus-story', 'A seagull has peer-reviewed your draft. It is eating the evidence.'));
    const arena = element('div', 'campus-seagull-arena');
    const sun = element('span', 'campus-beach-sun', '');
    sun.setAttribute('aria-hidden', 'true');
    const shoreline = element('span', 'campus-beach-shore', '');
    shoreline.setAttribute('aria-hidden', 'true');
    const poster = element('span', 'campus-beach-poster', 'NOVA · MAIN DECK');
    poster.setAttribute('aria-hidden', 'true');
    arena.append(sun, shoreline, poster);
    const pages = element('div', 'campus-rescued-pages');
    pages.setAttribute('aria-label', 'Recovered project pages');
    ui.game.append(arena, pages);
    let rescued = 0;
    // Fixed places remain large and in bounds at every window size. They
    // change after a click, never while someone is trying to click the bird.
    const places = [[12, 8], [60, 46], [14, 55], [58, 5], [35, 30], [5, 30]];
    const bird = button('', () => {
      rescued += 1;
      const page = element('span', 'campus-page', String(rescued));
      page.setAttribute('aria-label', 'Recovered page ' + rescued);
      pages.append(page);
      ui.progress(rescued + '/' + content.pages + ' pages recovered. Academic integrity restored.');
      if (rescued === content.pages) ui.complete();
      else placeBird();
    }, 'campus-seagull');
    const shape = picture('campus-bird-art');
    shape.append(svgPart('path', { d: 'M15 57 Q30 41 48 45 L44 33 Q46 20 60 20 Q77 20 78 39 Q94 44 99 57 Q74 76 45 69 L23 76 L29 62Z', fill: '#FFFDF5', stroke: '#2E2A3B', 'stroke-width': 3 }),
      svgPart('path', { d: 'M43 46 Q64 36 75 51 Q61 66 43 57Z', fill: '#C7D5D4', stroke: '#2E2A3B', 'stroke-width': 2 }),
      svgPart('path', { d: 'M76 34 L99 40 L77 46Z', fill: '#FFD23F', stroke: '#2E2A3B', 'stroke-width': 2 }),
      svgPart('circle', { cx: 66, cy: 31, r: 3.5, fill: '#2E2A3B' }), line(53, 69, 48, 80, '#D49340', 3), line(67, 70, 72, 80, '#D49340', 3),
      svgPart('path', { d: 'M86 42 L110 45 L106 68 L85 65Z', fill: 'white', stroke: '#2E2A3B', 'stroke-width': 2 }),
      line(91, 51, 104, 53, '#A4B8B2', 2), line(90, 57, 101, 59, '#A4B8B2', 2));
    bird.append(shape, element('span', 'campus-seagull-caption', 'Rescue page 1'));
    arena.append(bird);
    function placeBird() {
      const place = places[rescued % places.length];
      bird.style.left = 'min(' + place[0] + '%, calc(100% - 110px))';
      bird.style.top = place[1] + '%';
      bird.querySelector('.campus-seagull-caption').textContent = 'Rescue page ' + (rescued + 1);
      bird.setAttribute('aria-label', 'Rescue page ' + (rescued + 1) + ' from the seagull');
    }
    placeBird();
  }

  Game.minigames.register('campus_task', { instructions: 'A group project emergency. Read the brief below.', start });
})();
