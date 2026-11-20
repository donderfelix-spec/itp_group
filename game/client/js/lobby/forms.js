// The Start, Sign up, Log in and Home screens: their buttons, their forms and
// the error texts at the fields.
//
// The browser checks nothing itself. It sends what the player typed and shows
// the text the server answers with, so the rules exist in one place only.

window.Game = window.Game || {};

(function () {
  // Where on each screen an error can be shown: place -> id of the element.
  // Places: 'name', 'password', 'form' (the whole form) and 'code'.
  const ERROR_ELEMENTS = {
    signup: { name: 'signup-name-error', password: 'signup-password-error', form: 'signup-form-error' },
    login: { name: 'login-form-error', password: 'login-form-error', form: 'login-form-error' },
    home: { code: 'join-code-error' },
  };

  const signupForm = document.getElementById('signup-form');
  const loginForm = document.getElementById('login-form');
  const joinForm = document.getElementById('join-form');

  // Each password field has its own eye button that shows or hides it.
  const PASSWORD_EYES = [
    { field: 'signup-password', button: 'signup-password-eye' },
    { field: 'login-password', button: 'login-password-eye' },
  ];

  // `logOut` is the function of main.js that asks the server to log out.
  function setup(logOut) {
    onClick('start-login', () => openForm('login'));
    onClick('start-signup', () => openForm('signup'));
    onClick('start-guest', () => Game.net.ask({ type: 'guest' }));
    onClick('signup-back', backToStart);
    onClick('login-back', backToStart);
    onClick('home-create', () => Game.net.ask({ type: 'create_lobby' }));
    onClick('home-logout', logOut);

    // A form's "submit" fires for its button and for Enter in a field.
    signupForm.addEventListener('submit', (event) => submitAccountForm(event, signupForm, 'sign_up'));
    loginForm.addEventListener('submit', (event) => submitAccountForm(event, loginForm, 'log_in'));
    joinForm.addEventListener('submit', submitJoinForm);

    PASSWORD_EYES.forEach(setupPasswordEye);
  }

  function onClick(id, action) {
    document.getElementById(id).addEventListener('click', action);
  }

  function openForm(name) {
    stopWaiting();
    hidePasswords();
    clearErrors();
    Game.screens.show(name);
  }

  function backToStart() {
    stopWaiting();
    forgetTypedPasswords();
    Game.screens.show('start');
  }

  function submitAccountForm(event, form, messageType) {
    event.preventDefault(); // Otherwise the browser would reload the page.
    clearErrors();
    const sent = Game.net.ask({
      type: messageType,
      name: form.elements.name.value,
      password: form.elements.password.value,
    });
    // The server needs a moment to hash the password. Until its answer
    // arrives the button is off, so the form cannot be sent twice.
    setSubmitButtonsOff(sent);
  }

  function submitJoinForm(event) {
    event.preventDefault();
    clearErrors();
    Game.net.ask({ type: 'join_lobby', code: joinForm.elements.code.value });
  }

  function setSubmitButtonsOff(isOff) {
    document.getElementById('signup-submit').disabled = isOff;
    document.getElementById('login-submit').disabled = isOff;
  }

  // Called for every answer of the server and when the connection is lost,
  // so a button can never stay off.
  function stopWaiting() {
    setSubmitButtonsOff(false);
  }

  // The password lives only in its field while the player types it. It is
  // never stored or logged, and the field is emptied as soon as possible.
  // A field that is emptied is hidden as well, so no form is ever found
  // again with its password readable.
  function forgetTypedPasswords() {
    signupForm.elements.password.value = '';
    loginForm.elements.password.value = '';
    hidePasswords();
  }

  function setupPasswordEye(eye) {
    const field = document.getElementById(eye.field);
    const button = document.getElementById(eye.button);
    // A click with the mouse would take the keyboard out of the field.
    // Stopping that keeps the caret where the player was typing. Tab still
    // reaches the button, and Enter and Space press it.
    button.addEventListener('mousedown', (event) => event.preventDefault());
    button.addEventListener('click', () => {
      setPasswordShown(eye, field.type === 'password');
    });
  }

  // Shows the password as plain text or hides it again. The button's name
  // says what the next press does, and its icon follows `aria-pressed`.
  function setPasswordShown(eye, isShown) {
    const field = document.getElementById(eye.field);
    const button = document.getElementById(eye.button);
    if ((field.type === 'text') === isShown) return;
    // Some browsers move the caret to the start when the type changes.
    const caretStart = field.selectionStart;
    const caretEnd = field.selectionEnd;
    field.type = isShown ? 'text' : 'password';
    if (document.activeElement === field) field.setSelectionRange(caretStart, caretEnd);
    button.setAttribute('aria-pressed', String(isShown));
    button.setAttribute('aria-label', isShown ? 'Hide password' : 'Show password');
  }

  function hidePasswords() {
    PASSWORD_EYES.forEach((eye) => setPasswordShown(eye, false));
  }

  function clearErrors() {
    document.querySelectorAll('.field-error').forEach((element) => {
      element.textContent = '';
    });
  }

  // Shows `text` at `place` of the visible screen. Returns false when that
  // screen has no such place, so the caller can show the text elsewhere.
  function showError(place, text) {
    const places = ERROR_ELEMENTS[Game.screens.current()] || {};
    if (!places[place]) return false;
    document.getElementById(places[place]).textContent = text;
    return true;
  }

  function showSignedIn(name, isGuest) {
    stopWaiting();
    forgetTypedPasswords();
    signupForm.reset();
    loginForm.reset();
    document.getElementById('home-name').textContent = name;
    document.getElementById('home-guest').hidden = !isGuest;
    showHome();
  }

  function showHome() {
    clearErrors();
    joinForm.reset();
    Game.screens.show('home');
  }

  // Puts a lobby code into the join field (S-109, after a lost connection).
  // Call it after `showHome`, whose reset empties the field.
  function putCodeInJoinField(code) {
    joinForm.elements.code.value = code;
  }

  function showStart() {
    stopWaiting();
    forgetTypedPasswords();
    clearErrors();
    Game.screens.show('start');
  }

  Game.forms = {
    setup: setup,
    stopWaiting: stopWaiting,
    showError: showError,
    showSignedIn: showSignedIn,
    showHome: showHome,
    showStart: showStart,
    putCodeInJoinField: putCodeInJoinField,
  };
})();
