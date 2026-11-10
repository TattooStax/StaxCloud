// Browser checks for the shared UI primitives (Strike 9), on an iPad-size
// screen against a local daemon with no API key (STAX_BASE to change).
//   node stax/tests/ui_primitives_browser.js
// The question box: a dangerous question opens on Cancel (Enter alone
// never removes), Tab stays inside, Escape cancels and focus goes back to
// the button that asked; required fields hold the confirm button; one
// question at a time. Undo toasts run once. Pop-up windows get dialog
// roles, take focus and give it back. Forms asks before discarding edits
// and offers Undo for a removed block.
const { chromium } = require('playwright');
const assert = require('assert');
const B = process.env.STAX_BASE || 'http://127.0.0.1:50051';
(async () => {
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 820, height: 1180 }, hasTouch: true })).newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  // Any native dialog is a failure: they can vanish silently in an installed web app.
  page.on('dialog', d => { errors.push('native ' + d.type() + ': ' + d.message()); d.dismiss(); });
  await page.goto(B + '/#forms'); await page.waitForTimeout(2500);
  let n = 0; const ok = (name) => { n++; console.log('ok', name); };
  const focused = () => page.evaluate(() => { const a = document.activeElement; return a ? (a.id || a.className || a.tagName) + '|' + (a.textContent || '').trim() : ''; });

  // A button that asks, so we can see focus come back to it.
  await page.evaluate(() => {
    const b = document.createElement('button'); b.id = 'asker'; b.textContent = 'Ask'; document.body.appendChild(b); b.focus();
    window.__ans = 'pending';
    StaxUI.confirm({ title: 'Delete this thing?', message: 'Gone for good.', confirmLabel: 'Delete', danger: true }).then(v => { window.__ans = v; });
  });
  await page.waitForTimeout(150);
  assert.strictEqual(await page.locator('.confirm-modal[role=alertdialog][aria-modal=true]').count(), 1);
  assert.match(await focused(), /confirm-cancel.*\|Cancel$/, 'danger opens on Cancel');
  assert.strictEqual(await page.locator('.confirm-ok').innerText(), 'Delete');
  await page.keyboard.press('Tab'); assert.match(await focused(), /\|Delete$/);
  await page.keyboard.press('Tab'); assert.match(await focused(), /\|Cancel$/, 'Tab wraps inside');
  await page.keyboard.press('Enter'); await page.waitForTimeout(100);
  assert.strictEqual(await page.evaluate(() => window.__ans), false, 'Enter on Cancel cancels');
  assert.match(await focused(), /^asker/, 'focus returns to the asker');
  ok('danger question: Cancel first, Tab stays inside, focus returns');

  await page.evaluate(() => { window.__ans = 'pending'; StaxUI.confirm({ title: 'Remove?', danger: true, confirmLabel: 'Remove' }).then(v => { window.__ans = v; }); });
  await page.waitForTimeout(100); await page.keyboard.press('Escape'); await page.waitForTimeout(80);
  assert.strictEqual(await page.evaluate(() => window.__ans), false);
  assert.strictEqual(await page.locator('.confirm-overlay').count(), 0);
  ok('Escape cancels');

  await page.evaluate(() => { window.__ans = 'pending'; StaxUI.ask({ title: 'Name it', fields: [{ name: 'label', label: 'Name', required: true }], confirmLabel: 'Save' }).then(v => { window.__ans = v; }); });
  await page.waitForTimeout(100);
  assert.strictEqual(await page.locator('.confirm-ok').isDisabled(), true, 'required field holds Save');
  assert.match(await focused(), /^stax-ask-.*-f0/, 'focus starts in the field');
  await page.keyboard.type('Sleeve plan'); assert.strictEqual(await page.locator('.confirm-ok').isDisabled(), false);
  await page.keyboard.press('Enter'); await page.waitForTimeout(80);
  assert.deepStrictEqual(await page.evaluate(() => window.__ans), { label: 'Sleeve plan' });
  ok('ask with a required field');

  await page.evaluate(() => { window.__q = []; StaxUI.confirm({ title: 'One' }).then(v => window.__q.push('one:' + v)); StaxUI.confirm({ title: 'Two' }).then(v => window.__q.push('two:' + v)); });
  await page.waitForTimeout(100);
  assert.strictEqual(await page.locator('.confirm-overlay').count(), 1, 'one at a time');
  assert.strictEqual(await page.locator('.confirm-title').innerText(), 'One');
  await page.locator('.confirm-ok').click(); await page.waitForTimeout(100);
  assert.strictEqual(await page.locator('.confirm-title').innerText(), 'Two');
  await page.locator('.confirm-cancel').click(); await page.waitForTimeout(80);
  assert.deepStrictEqual(await page.evaluate(() => window.__q), ['one:true', 'two:false']);
  ok('questions queue');

  await page.evaluate(() => { OpenFangToast.confirm('Delete Schedule', 'x', () => { window.__legacy = true; }); });
  await page.waitForTimeout(100);
  assert.strictEqual(await page.locator('.confirm-ok').innerText(), 'Delete');
  assert.match(await focused(), /\|Cancel$/);
  await page.locator('.confirm-ok').click(); await page.waitForTimeout(80);
  assert.strictEqual(await page.evaluate(() => window.__legacy), true);
  ok('older confirm calls name their verb and open on Cancel');

  await page.evaluate(() => { window.__u = 0; StaxUI.undo('Removed block', () => { window.__u++; }); });
  await page.waitForTimeout(100);
  const undoBtn = page.locator('.toast-action', { hasText: 'Undo' });
  await undoBtn.click(); await page.waitForTimeout(400);
  assert.strictEqual(await page.evaluate(() => window.__u), 1);
  assert.strictEqual(await undoBtn.count(), 0);
  ok('Undo runs once and the toast goes');

  // A page-made pop-up window: role, focus in, focus back.
  await page.evaluate(() => {
    const b = document.createElement('button'); b.id = 'opener'; b.textContent = 'Open'; document.body.appendChild(b); b.focus();
    const o = document.createElement('div'); o.className = 'modal-overlay'; o.id = 'testmodal'; o.style.display = 'none';
    o.innerHTML = '<div class="modal"><h3>Edit schedule</h3><input id="m1" aria-label="Name"><button id="m2">Save</button></div>';
    document.body.appendChild(o);
    o.style.display = 'flex';
  });
  await page.waitForTimeout(200);
  assert.strictEqual(await page.getAttribute('#testmodal .modal', 'role'), 'dialog');
  assert.strictEqual(await page.getAttribute('#testmodal .modal', 'aria-label'), 'Edit schedule');
  assert.match(await focused(), /^m1/, 'focus moves into the window');
  await page.keyboard.press('Tab'); await page.keyboard.press('Tab');
  assert.match(await focused(), /^m1/, 'Tab stays in the window');
  await page.evaluate(() => { document.getElementById('testmodal').style.display = 'none'; });
  await page.waitForTimeout(150);
  assert.match(await focused(), /^opener/, 'focus returns to the opener');
  ok('pop-up windows take focus and give it back');

  // Forms: removing a block offers Undo; discarding edits asks first.
  await page.goto(B + '/#forms'); await page.waitForTimeout(2000);
  const comp = await page.evaluateHandle(() => {
    const el = [...document.querySelectorAll('[x-data]')].find(e => { try { return typeof Alpine.$data(e).removeBlock === 'function'; } catch (_) { return false; } });
    return el;
  });
  assert.ok(comp, 'forms component found');
  await page.evaluate(el => { const d = Alpine.$data(el); d.startNew('contact'); }, comp);
  await page.waitForTimeout(300);
  const before = await page.evaluate(el => Alpine.$data(el).draft.fields.length, comp);
  await page.evaluate(el => Alpine.$data(el).removeBlock(0), comp);
  await page.waitForTimeout(150);
  assert.strictEqual(await page.evaluate(el => Alpine.$data(el).draft.fields.length, comp), before - 1);
  await page.locator('.toast-action', { hasText: 'Undo' }).last().click(); await page.waitForTimeout(150);
  assert.strictEqual(await page.evaluate(el => Alpine.$data(el).draft.fields.length, comp), before, 'Undo puts the block back');
  await page.evaluate(el => { window.__d = Alpine.$data(el).discardDraft(); }, comp);
  await page.waitForTimeout(150);
  assert.strictEqual(await page.locator('.confirm-title').innerText(), 'Discard your changes?');
  await page.locator('.confirm-cancel').click(); await page.waitForTimeout(100);
  assert.ok(await page.evaluate(el => !!Alpine.$data(el).draft, comp), 'Cancel keeps the draft');
  ok('Forms: Undo for a removed block, discard asks first');

  assert.deepStrictEqual(errors, [], 'page errors or native dialogs');
  console.log(n + ' passed');
  await browser.close();
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
