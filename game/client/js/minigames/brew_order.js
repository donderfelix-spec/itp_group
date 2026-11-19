// Minigame of station 2, Mon Café: "Brew the order" (DESIGN.md, section 8).
//
// The server draws the drink and where the six buttons sit on the machine
// (server/modes/brew_order.py). The content looks like this:
//
//   { kind: 'brew_order', drink: 'Galão',
//     recipe: ['Glass', 'Espresso', 'Milk'],
//     buttons: ['Milk', 'Cup', 'Foam', 'Glass', 'Hot water', 'Espresso'] }
//
// The player presses the buttons in the order of the recipe. A right button
// ticks the step on the order slip and shows in the cup or glass under the
// machine. A wrong button flashes red and changes nothing else (S-58).

(function () {
  const BUTTON_NAMES = ['Cup', 'Glass', 'Espresso', 'Hot water', 'Milk', 'Foam'];
  const LOAD_ERROR_TEXT = 'This task could not be loaded.';
  const SLIP_HEADING = 'Order';
  const TICK = '✓';
  const FLASH_MS = 400;
  // How many layers fit into the vessel before they reach over its rim. The
  // numbers come from the heights in the `brew-` block of style.css: the cup
  // is 70px high with layers of 16px, the glass 82px with layers of 22px.
  const MAX_LAYERS_IN_CUP = 4;
  const MAX_LAYERS_IN_GLASS = 3;
  const MAX_LAYERS = { Cup: MAX_LAYERS_IN_CUP, Glass: MAX_LAYERS_IN_GLASS };

  // What a right button puts under the machine: Cup and Glass put the
  // vessel there, every other button pours one layer into it.
  const VESSEL_CLASS = { Cup: 'brew-vessel-cup', Glass: 'brew-vessel-glass' };
  const LAYER_CLASS = {
    Espresso: 'brew-layer-espresso',
    'Hot water': 'brew-layer-water',
    Milk: 'brew-layer-milk',
    Foam: 'brew-layer-foam',
  };

  function element(tag, className, text) {
    const made = document.createElement(tag);
    made.className = className;
    if (text !== undefined) made.textContent = text;
    return made;
  }

  function isButtonName(value) {
    return BUTTON_NAMES.includes(value);
  }

  // True if every entry of `list` is one of the six button names. A loop
  // over the indexes and not `every`: `every` skips the holes of a list like
  // ['Cup', , 'Milk'], and a hole is broken content too.
  function hasOnlyButtonNames(list) {
    for (let i = 0; i < list.length; i += 1) {
      if (!isButtonName(list[i])) return false;
    }
    return true;
  }

  // True if `buttons` is the six names, each exactly once, in any order.
  function isAllSixButtons(buttons) {
    if (!Array.isArray(buttons) || buttons.length !== BUTTON_NAMES.length) return false;
    // Six entries, all of them names, all different: each name exactly once.
    return hasOnlyButtonNames(buttons) && new Set(buttons).size === BUTTON_NAMES.length;
  }

  function isVesselName(value) {
    return Object.prototype.hasOwnProperty.call(VESSEL_CLASS, value);
  }

  // True if every step after the first pours a layer (no second cup or
  // glass) and no step is the same as the one before it. The second rule is
  // what the double-click rule in press() relies on.
  function hasPlayableLayers(recipe) {
    for (let i = 1; i < recipe.length; i += 1) {
      if (isVesselName(recipe[i]) || recipe[i] === recipe[i - 1]) return false;
    }
    return true;
  }

  // True if the recipe can be drawn and played: the cup or glass comes
  // first and only once (the layers are poured into it), the layers fit
  // into it, and no button comes twice in a row.
  function isDrawableRecipe(recipe) {
    if (!Array.isArray(recipe) || !hasOnlyButtonNames(recipe)) return false;
    if (!isVesselName(recipe[0])) return false; // also says no to an empty recipe
    const layerCount = recipe.length - 1;
    return layerCount <= MAX_LAYERS[recipe[0]] && hasPlayableLayers(recipe);
  }

  // The content comes over the network, so nothing about it is taken for granted.
  function isUsable(content) {
    if (!content || typeof content !== 'object') return false;
    const hasDrink = typeof content.drink === 'string' && content.drink !== '';
    return hasDrink && isDrawableRecipe(content.recipe) && isAllSixButtons(content.buttons);
  }

  // The order slip: the drink and one line for every step of the recipe.
  function buildSlip(drink, recipe) {
    const slip = element('div', 'brew-slip');
    const list = element('ol', 'brew-steps');
    const stepItems = recipe.map(function (name) {
      const item = element('li', 'brew-step');
      item.append(element('span', 'brew-step-tick'), element('span', 'brew-step-name', name));
      return item;
    });
    list.append(...stepItems);
    slip.append(element('p', 'brew-slip-heading', SLIP_HEADING), element('p', 'brew-drink', drink), list);
    return { slip: slip, stepItems: stepItems };
  }

  // The coffee machine: the six buttons on top, the spout below them, and
  // the place under the spout where the cup or glass will stand.
  function buildMachine(buttonNames, onPress) {
    const machine = element('div', 'brew-machine');
    const panel = element('div', 'brew-panel');
    const buttons = buttonNames.map(function (name) {
      const button = element('button', 'button brew-button', name);
      button.type = 'button';
      button.addEventListener('click', () => onPress(name, button));
      return button;
    });
    panel.append(...buttons);

    const vessel = element('div', 'brew-vessel');
    vessel.hidden = true; // appears with "Cup" or "Glass"
    const bay = element('div', 'brew-bay');
    bay.append(element('div', 'brew-spout'), vessel);
    machine.append(panel, bay, element('div', 'brew-tray'));
    return { machine: machine, buttons: buttons, vessel: vessel };
  }

  function tickStep(stepItem) {
    stepItem.classList.add('brew-step-done');
    stepItem.querySelector('.brew-step-tick').textContent = TICK;
  }

  // Shows a right step under the machine: the vessel, or one more layer in it.
  function showInVessel(vessel, name) {
    if (VESSEL_CLASS[name]) {
      vessel.classList.add(VESSEL_CLASS[name]);
      vessel.hidden = false;
    } else {
      vessel.append(element('div', 'brew-layer ' + LAYER_CLASS[name]));
    }
  }

  function start(body, content, done) {
    if (!isUsable(content)) {
      body.append(element('p', 'brew-error', LOAD_ERROR_TEXT));
      return undefined;
    }
    // Copies, so nothing that happens to `content` later changes the task.
    const recipe = content.recipe.slice();
    let stepsDone = 0;
    let isSolved = false;
    // The button of the step that was accepted last, until another button is pressed.
    let justAccepted = null;
    let flashTimer = null;
    let flashingButton = null;

    const slipParts = buildSlip(content.drink, recipe);
    const machineParts = buildMachine(content.buttons.slice(), press);
    const layout = element('div', 'brew-layout');
    layout.append(slipParts.slip, machineParts.machine);
    body.append(layout);

    function press(name, button) {
      if (isSolved) return;
      // A fast double click on a right button: the second click is not a
      // mistake, so it is ignored. No recipe has the same button twice in a
      // row (isDrawableRecipe checks it), so no right press is lost by this.
      if (name === justAccepted) return;
      if (name === recipe[stepsDone]) {
        acceptStep(name);
      } else {
        justAccepted = null;
        flashWrong(button);
      }
    }

    function acceptStep(name) {
      stopFlash();
      tickStep(slipParts.stepItems[stepsDone]);
      showInVessel(machineParts.vessel, name);
      stepsDone += 1;
      justAccepted = name;
      if (stepsDone === recipe.length) finish();
    }

    // Solved: no button does anything any more, and done() is called once.
    function finish() {
      isSolved = true;
      machineParts.buttons.forEach(function (button) {
        button.disabled = true;
      });
      done();
    }

    // The wrong button turns coral for a moment. The steps so far stay.
    function flashWrong(button) {
      stopFlash();
      flashingButton = button;
      button.classList.add('brew-button-wrong');
      flashTimer = setTimeout(stopFlash, FLASH_MS);
    }

    function stopFlash() {
      clearTimeout(flashTimer);
      flashTimer = null;
      if (flashingButton) flashingButton.classList.remove('brew-button-wrong');
      flashingButton = null;
    }

    // The frame calls this when the window closes: no timer is left behind.
    return stopFlash;
  }

  Game.minigames.register('brew_order', {
    instructions: 'Press the buttons in the order of the recipe.',
    start: start,
  });
})();
