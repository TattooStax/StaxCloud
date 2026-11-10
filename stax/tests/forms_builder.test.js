// Offline checks for the Forms builder's pure helpers.
//   node stax/tests/forms_builder.test.js
const fs = require('fs'), path = require('path'), assert = require('assert'), vm = require('vm');
const src = fs.readFileSync(path.join(__dirname, '../../crates/openfang-api/static/js/pages/forms.js'), 'utf8');
function block(name) {
  const a = src.indexOf('/*PURE-BEGIN ' + name + '*/'), b = src.indexOf('/*PURE-END ' + name + '*/');
  assert(a >= 0 && b > a, 'missing PURE block ' + name);
  return src.slice(a, b);
}
const ctx = {}; vm.createContext(ctx);
vm.runInContext(block('pvforms') + block('fbbuilder'), ctx);
const run = (code) => vm.runInContext(code, ctx);
let n = 0; const t = (name, fn) => { fn(); n++; console.log('ok  ' + name); };

t('every palette block has a real kind and a unique name', () => {
  const names = new Set();
  run('FB_PALETTE').forEach(g => g.items.forEach(it => {
    assert(!names.has(it.name), it.name); names.add(it.name);
    const kind = ctx.pvKind({ stype: it.stype, type: it.type });
    assert(kind && kind !== 'widget', it.name + ' -> ' + kind);
    assert.strictEqual(ctx.fbPaletteEntry(it.stype, it.type), it);
  }));
});

t('keys never collide, even as a prefix of another', () => {
  const fields = [{ key: 'client_details' }, { key: 'name' }];
  assert.strictEqual(ctx.fbUniqueKey('Name', fields), 'name2');
  assert.strictEqual(ctx.fbUniqueKey('Client', fields), 'client2', '"client" would own "client_details" sub-answers');
  assert.strictEqual(ctx.fbUniqueKey('Signature', fields), 'signature');
  assert.strictEqual(ctx.fbUniqueKey('!!!', fields), 'field');
});

t('templates build valid, publishable forms', () => {
  ['consent', 'booking', 'contact'].forEach(name => {
    const d = ctx.fbTemplate(name);
    assert(d.fields.length >= 4, name);
    assert.strictEqual(ctx.fbProblems(d), '', name);
    assert.strictEqual(new Set(d.fields.map(f => f.key)).size, d.fields.length);
  });
  assert.strictEqual(ctx.fbProblems(ctx.fbTemplate('blank')), 'Add at least one block.');
});

t('a required health list can be answered with "none"', () => {
  const d = ctx.fbTemplate('consent');
  const med = d.fields.find(f => f.stype === 'consent-medical-disclosure');
  assert(ctx.pvSec1(med).includes('None of the above'));
  const data = {}; data[med.key + '_conditions'] = ['None of the above'];
  assert.strictEqual(ctx.pvMissing(med, data), '');
});

t('settings rows read and write the block', () => {
  const f = ctx.fbNewBlock(ctx.fbPaletteEntry('field-dropdown'), []);
  const rows = ctx.fbSettings(f);
  rows.find(r => r.label === 'Question').set('Favorite style?');
  rows.find(r => r.label === 'Options').set('Realism\n\n  Fine line \n');
  rows.find(r => r.label === 'Required').set(true);
  assert.strictEqual(f.label, 'Favorite style?');
  assert.deepStrictEqual(Array.from(f.config.options), ['Realism', 'Fine line']);
  assert.strictEqual(f.required, true);
  assert.deepStrictEqual(Array.from(ctx.pvOptions(f), o => o.label), ['Realism', 'Fine line']);
});

t('typed terms become safe paragraphs and round-trip', () => {
  const html = ctx.fbTextToHtml('I agree.\nFully.\n\nNo <refunds>.');
  assert.strictEqual(html, '<p>I agree.<br>Fully.</p><p>No &lt;refunds>.</p>');
  assert.strictEqual(ctx.fbHtmlToText(html), 'I agree.\nFully.\n\nNo <refunds>.');
  assert.strictEqual(ctx.fbTextToHtml('<p>kept</p>'), '<p>kept</p>');
});

t('problems are named in plain words', () => {
  const d = ctx.fbTemplate('contact');
  d.title = ' '; assert.strictEqual(ctx.fbProblems(d), 'Give the form a name.');
  d.title = 'Contact'; d.fields.push({ key: 'pick', label: 'Pick', type: 'select', stype: 'field-dropdown', config: { options: [] } });
  assert(/needs at least one option/.test(ctx.fbProblems(d)));
});

t('sub-answers get their block\'s label', () => {
  const d = ctx.fbTemplate('consent');
  const map = ctx.pvAnswerLabels(d);
  const info = d.fields.find(f => f.stype === 'consent-client-info');
  assert.strictEqual(map[info.key + '_email'], 'Your details — Email');
  const sig = d.fields.find(f => f.stype === 'consent-signature');
  assert.strictEqual(map[sig.key + '_typed'], 'Signature (typed name)');
});

t('slugs are unique and url-safe', () => {
  assert.strictEqual(ctx.fbUniqueSlug('Tattoo Consent!', {}), 'tattoo-consent');
  assert.strictEqual(ctx.fbUniqueSlug('Tattoo Consent', { 'tattoo-consent': 1 }), 'tattoo-consent-2');
});

console.log(n + ' passed');
