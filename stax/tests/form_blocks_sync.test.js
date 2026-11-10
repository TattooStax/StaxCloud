// The agent drafts forms from the SAME blocks the Forms builder offers.
// The builder's palette (FB_PALETTE + fbNewBlock in forms.js) is the one
// source; crates/openfang-runtime/src/form_blocks.json is generated from it
// and read by the form_draft tool. This test fails if they drift.
//   node stax/tests/form_blocks_sync.test.js          # check
//   node stax/tests/form_blocks_sync.test.js --write  # regenerate the JSON
const fs = require('fs'), path = require('path'), assert = require('assert'), vm = require('vm');
const root = path.join(__dirname, '../..');
const src = fs.readFileSync(path.join(root, 'crates/openfang-api/static/js/pages/forms.js'), 'utf8');
function block(name) {
  const a = src.indexOf('/*PURE-BEGIN ' + name + '*/'), b = src.indexOf('/*PURE-END ' + name + '*/');
  assert(a >= 0 && b > a, 'missing PURE block ' + name);
  return src.slice(a, b);
}
const ctx = {}; vm.createContext(ctx);
vm.runInContext(block('pvforms') + block('fbbuilder'), ctx);
const palette = vm.runInContext('FB_PALETTE', ctx);
const blocks = [];
palette.forEach(g => g.items.forEach(it => {
  const f = ctx.fbNewBlock(it, []);
  delete f.key;
  blocks.push({ group: g.group, name: it.name, block: JSON.parse(JSON.stringify(f)) });
}));
const json = JSON.stringify({ generated_from: 'crates/openfang-api/static/js/pages/forms.js FB_PALETTE + fbNewBlock', blocks }, null, 2) + '\n';
const out = path.join(root, 'crates/openfang-runtime/src/form_blocks.json');
if (process.argv.includes('--write')) {
  fs.writeFileSync(out, json);
  console.log('wrote', path.relative(root, out), blocks.length, 'blocks');
} else {
  assert.strictEqual(fs.readFileSync(out, 'utf8'), json, 'form_blocks.json is out of date — run with --write');
  console.log('ok  form_blocks.json matches the builder palette (' + blocks.length + ' blocks)');
}
