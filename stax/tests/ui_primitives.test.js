// Static checks for the shared UI primitives (Strike 9).
//   node stax/tests/ui_primitives.test.js
// 1. No page uses the browser's own confirm()/prompt()/alert(): they can be
//    dismissed silently in an installed web app. StaxUI.ask/confirm instead.
// 2. Every older OpenFangToast.confirm(title, …) title names its action, so
//    no destructive button just says "Confirm".
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const STATIC = path.join(__dirname, '../../crates/openfang-api/static');
const files = [];
(function walk(d) {
  for (const f of fs.readdirSync(d)) {
    const p = path.join(d, f);
    if (fs.statSync(p).isDirectory()) { if (f !== 'vendor') walk(p); }
    else if (/\.(js|html)$/.test(f)) files.push(p);
  }
})(STATIC);
let n = 0;
function test(name, fn) { fn(); n++; console.log('ok', name); }

test('no native confirm/prompt/alert', () => {
  const hits = [];
  for (const f of files) {
    const src = fs.readFileSync(f, 'utf8');
    src.split('\n').forEach((line, i) => {
      const code = line.replace(/\/\/.*$/, '').replace(/^\s*\*.*$/, '');
      if (/(^|[^.\w$-])(window\.)?(confirm|prompt|alert)\(/.test(code) && !/function (confirm|prompt|alert)\(/.test(code))
        hits.push(path.relative(STATIC, f) + ':' + (i + 1) + ' ' + line.trim().slice(0, 80));
    });
  }
  assert.deepStrictEqual(hits, [], 'native dialogs:\n' + hits.join('\n'));
});

// Load api.js with just enough of a browser to read verbOf.
const api = fs.readFileSync(path.join(STATIC, 'js/api.js'), 'utf8').split('// ── Friendly Error Messages')[0];
const ctx = { document: { getElementById: () => null, addEventListener() {}, body: null, querySelector: () => null },
  window: {}, console, setTimeout, requestAnimationFrame: () => 0, Promise, MutationObserver: function() { this.observe = () => {}; } };
vm.createContext(ctx);
vm.runInContext(api + '\n;this.__T = OpenFangToast;', ctx);
const verbOf = ctx.__T.verbOf;

test('verbOf names the action', () => {
  const cases = {
    'Delete Schedule': 'Delete', 'Delete all': 'Delete', 'Remove Channel': 'Remove',
    'Clear History': 'Clear', 'Deactivate Hand': 'Deactivate', 'Uninstall Agent': 'Uninstall',
    'Reject this item?': 'Reject', 'Take “My site” offline?': 'Take offline',
    'Delete Session': 'Delete', 'Uninstall Skill': 'Uninstall',
  };
  for (const [t, v] of Object.entries(cases)) assert.strictEqual(verbOf(t), v, t);
});

test('every literal confirm title gets a verb', () => {
  const bad = [];
  for (const f of files) {
    const src = fs.readFileSync(f, 'utf8');
    for (const m of src.matchAll(/OpenFangToast\.confirm\(\s*(?:[^'"()]*\|\|\s*)?'([^']*)'\s*[,)]/g)) {
      if (verbOf(m[1]) === 'Confirm') bad.push(path.relative(STATIC, f) + ': ' + m[1]);
    }
  }
  assert.deepStrictEqual(bad, []);
});

console.log(n + ' passed');
