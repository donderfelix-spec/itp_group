/* Minimal stand-ins for the browser so the prototype scripts can run without one. Used by tests/run.js. */
var __els = { app: { innerHTML: '' }, toast: { textContent: '', hidden: true } };
var localStorage = { getItem: function () { return null; }, setItem: function () {} };
var document = { getElementById: function (id) { return __els[id]; }, addEventListener: function () {} };
var window = { scrollTo: function () {} };
var setTimeout = function () { return 0; }, clearTimeout = function () {};
