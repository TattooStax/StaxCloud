// Walks every artist-facing screen on an iPad and a phone viewport and flags
// script errors, failed requests, junk text ("undefined", "[object Object]"),
// sideways scrolling, unnamed buttons and missing docks. Screenshots land in
// the folder given as the first argument.
//   node stax/tests/surface_audit.js <screenshot-dir> [comma,separated,pages]
// Runs against a daemon on this machine with no API key set (STAX_BASE to
// point elsewhere). "SMALL" lists controls drawn under 40px; ones that extend
// their tap area with ::after are fine.
const { chromium, devices } = require('playwright');
const B = process.env.STAX_BASE || 'http://127.0.0.1:50051', S = process.argv[2] || '.';
const PAGES = (process.argv[3] || 'chat,sms,team,email,leads,contacts,boards,forms,library,websites,approvals,settings,channels,advanced').split(',');
const VIEWS = { ipad: { viewport: { width: 820, height: 1180 }, hasTouch: true, deviceScaleFactor: 1 }, phone: { ...devices['iPhone 13'], deviceScaleFactor: 1 } };
(async () => {
  const browser = await chromium.launch(); const out = [];
  for (const [vn, opts] of Object.entries(VIEWS)) {
    const ctx = await browser.newContext(opts); const page = await ctx.newPage();
    let errs = [], bad = [];
    page.on('pageerror', e => errs.push(e.message.slice(0, 160)));
    page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push(m.text().slice(0, 160)); });
    page.on('response', r => { if (r.status() >= 400) bad.push(r.status() + ' ' + r.url().replace(B, '')); });
    await page.goto(B + '/#chat'); await page.waitForTimeout(2500);
    for (const p of PAGES) {
      errs = []; bad = [];
      await page.evaluate(h => { location.hash = h; }, p); await page.waitForTimeout(1400);
      const info = await page.evaluate(() => {
        const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && r.bottom > 0 && r.top < innerHeight * 6; };
        const main = document.querySelector('.main-content') || document.body;
        const text = main.innerText || '';
        const junk = (text.match(/\bundefined\b|\bNaN\b|\[object Object\]|\bnull\b/g) || []).slice(0, 4);
        const btns = [...document.querySelectorAll('button, a.btn, [role=button]')].filter(vis);
        const small = btns.filter(b => { const r = b.getBoundingClientRect(); return r.height < 40 || r.width < 40; }).map(b => (b.getAttribute('aria-label') || b.innerText || '?').trim().slice(0, 22) + ' ' + Math.round(b.getBoundingClientRect().width) + 'x' + Math.round(b.getBoundingClientRect().height));
        const unnamed = btns.filter(b => !(b.innerText || '').trim() && !b.getAttribute('aria-label') && !b.getAttribute('title')).length;
        const overflow = document.documentElement.scrollWidth - innerWidth;
        const docks = [...document.querySelectorAll('nav.stax-dock')].filter(vis).map(n => n.getAttribute('aria-label'));
        const h2 = [...document.querySelectorAll('.page-header h2, h1')].filter(vis).map(h => h.innerText.trim())[0] || '';
        const nonTile = [...document.querySelectorAll('nav.stax-dock .stax-ic')].filter(vis).filter(i => !i.querySelector('.stax-tile')).length;
        // Things that act on a tap but are not buttons or links: a keyboard
        // (or switch control) cannot reach them.
        const clickOnly = [...document.querySelectorAll('[\\@click], [x-on\\:click]')].filter(vis)
          .filter(el => !el.matches('button, a[href], input, select, textarea, label, summary, [role=button], [role=tab], [role=link], [role=option], [role=menuitem], [role=checkbox], [role=switch], [tabindex]'))
          .filter(el => !el.closest('button, a[href], [role=button]'))
          .filter(el => !/(overlay|backdrop|modal-bg|scrim)/i.test(el.className || ''))
          .map(el => (el.tagName.toLowerCase() + '.' + String(el.className || '').split(' ')[0] + ' "' + (el.innerText || '').trim().slice(0, 18) + '"'));
        // Fields with no name a screen reader can say (placeholder alone does not count).
        const fields = [...document.querySelectorAll('input:not([type=hidden]):not([type=file]), select, textarea')].filter(vis);
        const unlabeled = fields.filter(f => !(f.getAttribute('aria-label') || f.getAttribute('aria-labelledby') || f.closest('label') || (f.id && document.querySelector('label[for="' + CSS.escape(f.id) + '"]')) || f.getAttribute('title')))
          .map(f => (f.getAttribute('placeholder') || f.name || f.type || f.tagName).slice(0, 22));
        return { h2, junk, small: small.slice(0, 6), smallCount: small.length, unnamed, overflow, docks, nonTile, chars: text.trim().length, clickOnly: clickOnly.slice(0, 5), clickOnlyCount: clickOnly.length, unlabeled: unlabeled.slice(0, 5), unlabeledCount: unlabeled.length };
      });
      await page.screenshot({ path: `${S}/${vn}-${p}.png` });
      out.push({ view: vn, page: p, ...info, errs: errs.slice(0, 3), bad: [...new Set(bad)].slice(0, 4) });
    }
    await ctx.close();
  }
  for (const r of out) {
    const flags = [];
    if (r.errs.length) flags.push('ERR ' + JSON.stringify(r.errs));
    if (r.bad.length) flags.push('HTTP ' + JSON.stringify(r.bad));
    if (r.junk.length) flags.push('JUNK ' + JSON.stringify(r.junk));
    if (r.overflow > 2) flags.push('OVERFLOW ' + r.overflow + 'px');
    if (r.unnamed) flags.push('UNNAMED-BTN ' + r.unnamed);
    if (r.docks.length !== 1) flags.push('DOCKS ' + JSON.stringify(r.docks));
    if (r.nonTile) flags.push('NON-TILE-DOCK-ICON ' + r.nonTile);
    if (r.smallCount) flags.push('SMALL ' + r.smallCount + ' ' + JSON.stringify(r.small));
    if (r.chars < 40) flags.push('NEAR-EMPTY ' + r.chars);
    if (r.clickOnlyCount) flags.push('CLICK-ONLY ' + r.clickOnlyCount + ' ' + JSON.stringify(r.clickOnly));
    if (r.unlabeledCount) flags.push('UNLABELED-FIELD ' + r.unlabeledCount + ' ' + JSON.stringify(r.unlabeled));
    console.log(`${r.view.padEnd(5)} ${r.page.padEnd(10)} "${r.h2}" dock=${r.docks.join('|')} ${flags.length ? '\n      ' + flags.join('\n      ') : 'clean'}`);
  }
  await browser.close();
})();
