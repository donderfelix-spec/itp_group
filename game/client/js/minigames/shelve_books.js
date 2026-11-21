// Minigame of station 4, CTT Student Hall: "Shelve the books" (DESIGN.md, section 8).
//
// Six numbered books lie mixed up on a table. The player clicks them onto
// the shelf, lowest number first. A wrong book hops up and falls back onto
// the table; the books on the shelf stay (S-58). When all six stand on the
// shelf the task is solved.
//
// The server draws the numbers and the order the books lie in
// (server/modes/shelve_books.py):
//   content = { kind: 'shelve_books', books: [412, 108, 977, 230, 655, 301] }

window.Game = window.Game || {};

(function () {
  const BOOK_COUNT = 6;
  const LOWEST_NUMBER = 100;
  const HIGHEST_NUMBER = 999;
  const BROKEN_TEXT = 'This task could not be loaded.';
  // As long as the animation `books-fall-back` in style.css.
  const FALL_BACK_MS = 450;

  function element(tag, className, text) {
    const made = document.createElement(tag);
    made.className = className;
    if (text !== undefined) made.textContent = text;
    return made;
  }

  function isShelfNumber(value) {
    return Number.isInteger(value) && value >= LOWEST_NUMBER && value <= HIGHEST_NUMBER;
  }

  // True if the content is six different shelf numbers.
  function isUsable(content) {
    const books = content ? content.books : null;
    if (!Array.isArray(books) || books.length !== BOOK_COUNT) return false;
    return books.every(isShelfNumber) && new Set(books).size === BOOK_COUNT;
  }

  // The empty shelf: six places in a row, on a board.
  function buildShelf() {
    const shelf = element('div', 'books-shelf');
    const places = [];
    for (let index = 0; index < BOOK_COUNT; index += 1) {
      const place = element('div', 'books-place');
      places.push(place);
      shelf.append(place);
    }
    return { shelf: shelf, places: places };
  }

  // A book lying on the table. It is a button, so it can be clicked. The
  // colour only tells the books apart, it says nothing about the number:
  // it comes from where the book lies.
  function buildLyingBook(number, index) {
    const book = element('button', 'books-book books-lying books-colour-' + index, String(number));
    book.type = 'button';
    return book;
  }

  // The same book standing on the shelf: same colour, same number.
  function buildStandingBook(number, index) {
    return element('div', 'books-book books-standing books-colour-' + index, String(number));
  }

  function start(body, content, done) {
    if (!isUsable(content)) {
      body.append(element('p', 'books-broken', BROKEN_TEXT));
      return undefined;
    }

    const numbers = content.books;
    // The numbers still on the table, lowest first: the first one is next.
    const waiting = numbers.slice().sort((a, b) => a - b);
    const parts = buildShelf();
    const table = element('div', 'books-table');
    const fallTimers = new Map(); // lying book -> the timer that ends its fall
    let shelved = 0;
    let isSolved = false;

    function putOnShelf(book, number, index) {
      waiting.shift();
      parts.places[shelved].append(buildStandingBook(number, index));
      parts.places[shelved].classList.add('books-place-filled');
      shelved += 1;
      // The book leaves the table, but its place stays, so the other
      // books do not jump under the mouse.
      book.disabled = true;
      book.classList.add('books-gone');
      if (waiting.length === 0) {
        isSolved = true;
        done();
      }
    }

    // The wrong book hops towards the shelf and falls back onto the table.
    function letFallBack(book) {
      clearTimeout(fallTimers.get(book));
      book.classList.remove('books-falling');
      void book.offsetWidth; // makes the browser start the animation again
      book.classList.add('books-falling');
      fallTimers.set(book, setTimeout(() => book.classList.remove('books-falling'), FALL_BACK_MS));
    }

    function onBookClick(book, number, index) {
      if (isSolved || book.disabled) return;
      if (number === waiting[0]) putOnShelf(book, number, index);
      else letFallBack(book);
    }

    numbers.forEach((number, index) => {
      const book = buildLyingBook(number, index);
      book.addEventListener('click', () => onBookClick(book, number, index));
      table.append(book);
    });
    body.append(parts.shelf, table);

    // When the window closes: no timer may run on.
    return function stop() {
      isSolved = true;
      fallTimers.forEach((timer) => clearTimeout(timer));
      fallTimers.clear();
    };
  }

  Game.minigames.register('shelve_books', {
    instructions: 'Click the books onto the shelf, lowest number first.',
    start: start,
  });
})();
