// Minigame 5, "Self-checkout" at Pingo Doce (DESIGN.md, section 8; S-60).
//
// The checkout shows a target amount. Six products lie on the belt. A click
// scans a product into the bagging area, a click there puts it back. The
// task is solved when the total is exactly the target. A product that would
// take the total above the target is not accepted (S-58: nothing that is
// already scanned is reset).
//
// The server draws the content (server/modes/self_checkout.py):
//   { kind: 'self_checkout',
//     products: [{ name: 'Water', cents: 150 }, ... six of them],
//     target_cents: 750 }
//
// Money is counted in whole cents here and only turned into "€7.50" for
// showing it. With euros as decimal numbers 0.1 + 0.2 would be
// 0.30000000000000004, and the total would never be "exactly" the target.

(function () {
  const INSTRUCTIONS = 'Scan products until the total is exactly the target amount.';
  const NOT_LOADED_TEXT = 'This task could not be loaded.';
  const TOO_MUCH_TEXT = 'Unexpected item in the bagging area';
  const TARGET_LABEL = 'Target';
  const TOTAL_LABEL = 'Total';
  const BELT_LABEL = 'Belt';
  const BAG_LABEL = 'Bagging area';
  const PRODUCT_COUNT = 6;
  const MESSAGE_VISIBLE_MS = 1800;

  // Product name -> the CSS class that draws it. A Map, so a name like
  // "constructor" finds nothing. An unknown name is drawn as a plain box.
  const PICTURES = new Map([
    ['Water', 'checkout-picture-water'],
    ['Bread', 'checkout-picture-bread'],
    ['Cheese', 'checkout-picture-cheese'],
    ['Apples', 'checkout-picture-apples'],
    ['Coffee', 'checkout-picture-coffee'],
    ['Chocolate', 'checkout-picture-chocolate'],
  ]);
  const PLAIN_PICTURE = 'checkout-picture-box';

  function element(tag, className, text) {
    const made = document.createElement(tag);
    made.className = className;
    if (text !== undefined) made.textContent = text;
    return made;
  }

  // 750 -> "€7.50". Euros and cents are split as whole numbers, so no
  // rounding can happen.
  function formatMoney(cents) {
    const euros = Math.floor(cents / 100);
    const rest = String(cents % 100).padStart(2, '0');
    return '€' + euros + '.' + rest;
  }

  function isAmount(value) {
    return Number.isSafeInteger(value) && value > 0;
  }

  function isProduct(product) {
    return Boolean(product) && typeof product === 'object'
      && typeof product.name === 'string' && isAmount(product.cents);
  }

  // The content comes over the network: check it before building anything.
  function isUsable(content) {
    return Boolean(content) && typeof content === 'object'
      && Array.isArray(content.products)
      && content.products.length === PRODUCT_COUNT
      && content.products.every(isProduct)
      && isAmount(content.target_cents);
  }

  // One line of the display: "Target" on the left, "€7.50" on the right.
  function buildDisplayLine(label, cents) {
    const line = element('p', 'checkout-line');
    const amount = element('span', 'checkout-amount', formatMoney(cents));
    line.append(element('span', 'checkout-label', label), amount);
    return { line: line, amount: amount };
  }

  // A product is a button with a small drawing, its name and its price.
  function buildProductButton(product) {
    const button = element('button', 'checkout-product');
    button.type = 'button';
    const picture = element('span', 'checkout-picture ' + (PICTURES.get(product.name) || PLAIN_PICTURE));
    picture.setAttribute('aria-hidden', 'true');
    button.append(
      picture,
      element('span', 'checkout-name', product.name),
      element('span', 'checkout-price', formatMoney(product.cents))
    );
    return button;
  }

  // A row of six fixed places. Above it a line with its name, where the
  // bagging area also shows its message.
  function buildRow(label, rowClass) {
    const area = element('div', 'checkout-area');
    const heading = element('div', 'checkout-area-heading');
    heading.append(element('p', 'checkout-area-label', label));
    const row = element('div', 'checkout-row ' + rowClass);
    const slots = [];
    for (let place = 0; place < PRODUCT_COUNT; place += 1) {
      const slot = element('div', 'checkout-slot');
      slots.push(slot);
      row.append(slot);
    }
    area.append(heading, row);
    return { area: area, heading: heading, slots: slots };
  }

  function start(body, content, done) {
    if (!isUsable(content)) {
      body.append(element('p', 'checkout-broken', NOT_LOADED_TEXT));
      return undefined;
    }

    const targetCents = content.target_cents;
    let totalCents = 0;
    let isSolved = false;
    let messageTimer = null;

    const target = buildDisplayLine(TARGET_LABEL, targetCents);
    const total = buildDisplayLine(TOTAL_LABEL, totalCents);
    const display = element('div', 'checkout-display');
    display.append(target.line, total.line);

    const belt = buildRow(BELT_LABEL, 'checkout-belt');
    const bag = buildRow(BAG_LABEL, 'checkout-bag');

    // The message stands next to the name of the bagging area. Its line is
    // always there, so the layout does not jump when the text comes.
    const message = element('p', 'checkout-message');
    message.setAttribute('role', 'alert');
    bag.heading.append(message);

    function showTooMuch() {
      message.textContent = TOO_MUCH_TEXT;
      clearTimeout(messageTimer);
      messageTimer = setTimeout(hideMessage, MESSAGE_VISIBLE_MS);
    }

    function hideMessage() {
      clearTimeout(messageTimer);
      messageTimer = null;
      message.textContent = '';
    }

    function showTotal() {
      total.amount.textContent = formatMoney(totalCents);
    }

    function finish() {
      isSolved = true;
      display.classList.add('checkout-display-solved');
      done();
    }

    // Every product keeps its place: place 3 on the belt goes to place 3 of
    // the bagging area and back. So a double click never hits another
    // product that slid under the mouse.
    function addProduct(product, place) {
      const button = buildProductButton(product);
      let isScanned = false;

      function scan() {
        if (totalCents + product.cents > targetCents) {
          showTooMuch();
          return;
        }
        isScanned = true;
        totalCents += product.cents;
        bag.slots[place].append(button);
      }

      function putBack() {
        isScanned = false;
        totalCents -= product.cents;
        belt.slots[place].append(button);
      }

      button.addEventListener('click', function () {
        if (isSolved) return;
        hideMessage();
        if (isScanned) putBack();
        else scan();
        showTotal();
        if (totalCents === targetCents) finish();
      });
      belt.slots[place].append(button);
    }

    content.products.forEach(addProduct);
    body.append(display, belt.area, bag.area);

    // The frame calls this when the window closes: no timer is left behind.
    return function stop() {
      clearTimeout(messageTimer);
      messageTimer = null;
    };
  }

  Game.minigames.register('self_checkout', { instructions: INSTRUCTIONS, start: start });
})();
