// The minigame of the Lecture Hall, station 1: "Sort the slides"
// (DESIGN.md, section 8, row 1).
//
// At the top is the presentation: five numbered, empty places. Below lies
// the pile: the five slides, shuffled by the server
// (server/modes/sort_slides.py). The player drags each slide onto its place.
//
//   right place            the slide snaps in and stays there
//   wrong or filled place  the slide shakes and jumps back to the pile (S-58:
//                          only this slide, everything placed stays)
//   anywhere else          the slide goes back to the pile without a shake
//
// The content from the server looks like this:
//   { kind: 'sort_slides',
//     order:  ['Title', 'Agenda', 'Analysis', 'Results', 'Q&A'],   the right order
//     slides: ['Results', 'Title', 'Q&A', 'Agenda', 'Analysis'] }  the pile

window.Game = window.Game || {};

(function () {
  const INSTRUCTIONS = 'Drag the slides into the right order.';
  const LOAD_ERROR_TEXT = 'This task could not be loaded.';
  const SLIDE_COUNT = 5;
  // How long a slide shakes on a wrong place before it jumps back. The
  // animation `slides-shake` in style.css takes the same time.
  const SHAKE_MS = 350;
  // How many lines or bars the little sketches have.
  const AGENDA_LINES = 3;
  const ANALYSIS_BARS = 4;

  function element(tag, className, text) {
    const made = document.createElement(tag);
    made.className = className;
    if (text !== undefined) made.textContent = text;
    return made;
  }

  // ---- Checking the content ----

  function isListOfNames(list) {
    if (!Array.isArray(list) || list.length !== SLIDE_COUNT) return false;
    const areNames = list.every((name) => typeof name === 'string' && name !== '');
    const areAllDifferent = new Set(list).size === list.length;
    return areNames && areAllDifferent;
  }

  // True if `content` has the right order and a pile with the same slides.
  function isUsable(content) {
    if (!content || !isListOfNames(content.order) || !isListOfNames(content.slides)) return false;
    return content.slides.every((name) => content.order.includes(name));
  }

  // ---- Drawing one slide ----

  function sketchParts(className, count) {
    const parts = [];
    for (let i = 0; i < count; i += 1) parts.push(element('span', className));
    return parts;
  }

  // A tiny picture that fits the slide, made of plain elements (S-28: no
  // image files). A slide with a name not listed here gets no picture.
  const SKETCHES = {
    'Title': () => [element('span', 'slides-line-thick'), element('span', 'slides-line-thin')],
    'Agenda': () => sketchParts('slides-bullet', AGENDA_LINES),
    'Analysis': () => sketchParts('slides-bar', ANALYSIS_BARS),
    'Results': () => [element('span', 'slides-pie')],
    'Q&A': () => [element('span', 'slides-question', '?')],
  };

  // The class of the sketch says how its parts are laid out, see style.css.
  const SKETCH_CLASSES = {
    'Title': 'slides-sketch-title',
    'Agenda': 'slides-sketch-agenda',
    'Analysis': 'slides-sketch-analysis',
    'Results': 'slides-sketch-results',
    'Q&A': 'slides-sketch-question',
  };

  function buildSketch(name) {
    const hasSketch = Object.prototype.hasOwnProperty.call(SKETCHES, name);
    const sketch = element('div', 'slides-sketch');
    if (!hasSketch) return sketch;
    sketch.classList.add(SKETCH_CLASSES[name]);
    sketch.append(...SKETCHES[name]());
    return sketch;
  }

  function buildSlide(name) {
    const slide = element('div', 'slides-slide');
    slide.append(element('span', 'slides-name', name), buildSketch(name));
    return slide;
  }

  // ---- Geometry ----

  function centreOf(box) {
    return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
  }

  function contains(box, point) {
    return point.x >= box.left && point.x <= box.right && point.y >= box.top && point.y <= box.bottom;
  }

  function clamp(value, lowest, highest) {
    return Math.min(Math.max(value, lowest), highest);
  }

  // ---- The minigame ----

  function showLoadError(body) {
    body.append(element('p', 'slides-error', LOAD_ERROR_TEXT));
  }

  function start(body, content, done) {
    if (!isUsable(content)) {
      showLoadError(body);
      return undefined;
    }

    const board = element('div', 'slides-board');
    const placeRow = element('div', 'slides-row');
    const pileRow = element('div', 'slides-row slides-pile');
    board.append(placeRow, pileRow);

    const places = []; // { box: the element, name: the slide that belongs here, filled }
    let placedCount = 0;
    let isOver = false; // solved or closed: nothing can be dragged any more
    let drag = null; // the slide in the player's hand, see beginDrag
    const shakeTimers = new Set();

    content.order.forEach(function (name, index) {
      const box = element('div', 'slides-place');
      box.append(element('span', 'slides-number', String(index + 1)));
      placeRow.append(box);
      places.push({ box: box, name: name, filled: false });
    });

    content.slides.forEach(function (name) {
      // The spot keeps the slide's room in the pile, so the pile does not
      // move together when a slide leaves it.
      const spot = element('div', 'slides-spot');
      const slide = buildSlide(name);
      spot.append(slide);
      pileRow.append(spot);
      listenForDragging(slide, name);
    });

    body.append(board);

    function listenForDragging(slide, name) {
      slide.addEventListener('pointerdown', (event) => beginDrag(event, slide, name));
      slide.addEventListener('pointermove', (event) => moveDrag(event, slide));
      slide.addEventListener('pointerup', (event) => endDrag(event, slide));
      // The browser took the pointer away (for example the window lost the
      // mouse): the slide goes back to the pile.
      slide.addEventListener('pointercancel', () => cancelDrag(slide));
      slide.addEventListener('lostpointercapture', () => cancelDrag(slide));
    }

    function canBeDragged(slide) {
      const isLocked = slide.classList.contains('slides-locked');
      const isShaking = slide.classList.contains('slides-shaking');
      return !isOver && !drag && !isLocked && !isShaking;
    }

    function beginDrag(event, slide, name) {
      const isMainButton = event.button === 0;
      if (!isMainButton || !canBeDragged(slide)) return;
      event.preventDefault(); // no text selection while dragging
      const home = slide.getBoundingClientRect();
      const limits = board.getBoundingClientRect();
      drag = {
        slide: slide,
        name: name,
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        // How far the slide may move from its spot. It stays inside the
        // board, so it can never leave the window or make it scroll.
        minX: limits.left - home.left,
        maxX: limits.right - home.right,
        minY: limits.top - home.top,
        maxY: limits.bottom - home.bottom,
      };
      // With the capture, this slide gets every move and the release of the
      // pointer, also outside the window and outside the browser.
      slide.setPointerCapture(event.pointerId);
      slide.classList.add('slides-dragging');
    }

    function isDragOf(event, slide) {
      return Boolean(drag) && drag.slide === slide && drag.pointerId === event.pointerId;
    }

    function moveDrag(event, slide) {
      if (!isDragOf(event, slide)) return;
      const x = clamp(event.clientX - drag.startX, drag.minX, drag.maxX);
      const y = clamp(event.clientY - drag.startY, drag.minY, drag.maxY);
      // `translate` and not `transform`: the shake uses `transform`.
      slide.style.translate = x + 'px ' + y + 'px';
    }

    // The place the middle of the slide lies on, or null.
    function placeUnder(slide) {
      const middle = centreOf(slide.getBoundingClientRect());
      return places.find((place) => contains(place.box.getBoundingClientRect(), middle)) || null;
    }

    function endDrag(event, slide) {
      if (!isDragOf(event, slide)) return;
      const name = drag.name;
      const place = placeUnder(slide);
      letGo();
      if (!place) {
        backToPile(slide);
      } else if (place.name === name && !place.filled) {
        lockIn(slide, place);
      } else {
        shakeThenBackToPile(slide);
      }
    }

    function cancelDrag(slide) {
      if (!drag || drag.slide !== slide) return;
      letGo();
      backToPile(slide);
    }

    // Takes the slide out of the player's hand. Where it goes is decided after.
    function letGo() {
      const slide = drag.slide;
      const pointerId = drag.pointerId;
      drag = null; // first, so `lostpointercapture` below finds no drag
      slide.classList.remove('slides-dragging');
      if (slide.hasPointerCapture(pointerId)) slide.releasePointerCapture(pointerId);
    }

    function backToPile(slide) {
      slide.style.translate = '';
    }

    function shakeThenBackToPile(slide) {
      slide.classList.add('slides-shaking');
      const timer = setTimeout(function () {
        shakeTimers.delete(timer);
        slide.classList.remove('slides-shaking');
        backToPile(slide);
      }, SHAKE_MS);
      shakeTimers.add(timer);
    }

    function lockIn(slide, place) {
      place.filled = true;
      place.box.classList.add('slides-filled');
      slide.style.translate = '';
      slide.classList.add('slides-locked');
      place.box.append(slide);
      placedCount += 1;
      if (placedCount === places.length) solve();
    }

    function solve() {
      isOver = true; // before done(): it is called exactly once
      done();
    }

    // The window closes: stop the drag and the timers.
    function stop() {
      isOver = true;
      if (drag) cancelDrag(drag.slide);
      shakeTimers.forEach((timer) => clearTimeout(timer));
      shakeTimers.clear();
    }

    return stop;
  }

  Game.minigames.register('sort_slides', { instructions: INSTRUCTIONS, start: start });
})();
