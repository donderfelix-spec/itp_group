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

  function setup() {
    onClick('start-login', () => openForm('login'));
    onClick('start-signup', () => openForm('signup'));
    onClick('start-guest', () => Game.net.ask({ type: 'guest' }));
    onClick('signup-back', backToStart);
    onClick('login-back', backToStart);
    onClick('home-create', () => Game.net.ask({ type: 'create_lobby' }));
    onClick('home-logout', () => Game.net.ask({ type: 'log_out' }));

    // A form's "submit" fires for its button and for Enter in a field.
    signupForm.addEventListener('submit', (event) => submitAccountForm(event, signupForm, 'sign_up'));
    loginForm.addEventListener('submit', (event) => submitAccountForm(event, loginForm, 'log_in'));
    joinForm.addEventListener('submit', submitJoinForm);
  }

  function onClick(id, action) {
    document.getElementById(id).addEventListener('click', action);
  }

  function openForm(name) {
    stopWaiting();
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
  function forgetTypedPasswords() {
    signupForm.elements.password.value = '';
    loginForm.elements.password.value = '';
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
  };
})();
