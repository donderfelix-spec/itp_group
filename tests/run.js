/* Runs the flow tests without a browser: node tests/run.js
   Loads the prototype scripts in the order index.html lists them, then tests/flows.js. */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.join(__dirname, '..', 'prototype');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const scripts = [...html.matchAll(/<script src="([^"]+)"/g)].map(m => m[1]);
if (!scripts.length) throw new Error('No scripts found in prototype/index.html');

const parts = [fs.readFileSync(path.join(__dirname, 'stub.js'), 'utf8')];
for (const s of scripts) {
  const file = path.join(root, s);
  if (!fs.existsSync(file)) throw new Error('index.html loads a script that does not exist: ' + s);
  parts.push(fs.readFileSync(file, 'utf8'));
}
parts.push(fs.readFileSync(path.join(__dirname, 'flows.js'), 'utf8'));

try {
  console.log(vm.runInNewContext(parts.join('\n'), {}, { filename: 'prototype-bundle.js' }));
} catch (e) {
  console.error(e.message);
  process.exit(1);
}
