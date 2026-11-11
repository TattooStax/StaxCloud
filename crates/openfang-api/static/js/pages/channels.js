// OpenFang Channels Page — OpenClaw-style setup UX with QR code support
'use strict';

function channelsPage() {
  return {
    allChannels: [],
    categoryFilter: 'all',
    searchQuery: '',
    setupModal: null,
    configuring: false,
    testing: {},
    formValues: {},
    showAdvanced: false,
    showBusinessApi: false,
    loading: true,
    loadError: '',
    pollTimer: null,

    // Setup flow step tracking
    setupStep: 1, // 1=Configure, 2=Verify, 3=Ready
    testPassed: false,

    // WhatsApp QR state
    qr: {
      loading: false,
      available: false,
      dataUrl: '',
      sessionId: '',
      message: '',
      help: '',
      connected: false,
      expired: false,
      error: ''
    },
    qrPollTimer: null,

    categories: [
      { key: 'all', label: 'All' },
      { key: 'messaging', label: 'Messaging' },
      { key: 'social', label: 'Social' },
      { key: 'enterprise', label: 'Enterprise' },
      { key: 'developer', label: 'Developer' },
      { key: 'notifications', label: 'Notifications' }
    ],

    get filteredChannels() {
      var self = this;
      return this.allChannels.filter(function(ch) {
        if (self.categoryFilter !== 'all' && ch.category !== self.categoryFilter) return false;
        if (self.searchQuery) {
          var q = self.searchQuery.toLowerCase();
          return ch.name.toLowerCase().indexOf(q) !== -1 ||
                 ch.display_name.toLowerCase().indexOf(q) !== -1 ||
                 ch.description.toLowerCase().indexOf(q) !== -1;
        }
        return true;
      });
    },

    get configuredCount() {
      return this.allChannels.filter(function(ch) { return ch.configured; }).length;
    },

    categoryCount(cat) {
      var all = this.allChannels.filter(function(ch) { return cat === 'all' || ch.category === cat; });
      var configured = all.filter(function(ch) { return ch.configured; });
      return configured.length + '/' + all.length;
    },

    basicFields() {
      if (!this.setupModal || !this.setupModal.fields) return [];
      return this.setupModal.fields.filter(function(f) { return !f.advanced; });
    },

    advancedFields() {
      if (!this.setupModal || !this.setupModal.fields) return [];
      return this.setupModal.fields.filter(function(f) { return f.advanced; });
    },

    hasAdvanced() {
      return this.advancedFields().length > 0;
    },

    isQrChannel() {
      return this.setupModal && this.setupModal.setup_type === 'qr';
    },

    async loadChannels() {
      this.loading = true;
      this.loadError = '';
      try {
        var data = await OpenFangAPI.get('/api/channels');
        this.allChannels = (data.channels || []).map(function(ch) {
          ch.connected = ch.configured && ch.has_token;
          return ch;
        });
      } catch(e) {
        this.loadError = e.message || 'Could not load channels.';
      }
      this.loading = false;
      this.startPolling();
    },

    async loadData() { return this.loadChannels(); },

    startPolling() {
      var self = this;
      if (this.pollTimer) clearInterval(this.pollTimer);
      this.pollTimer = setInterval(function() { self.refreshStatus(); }, 15000);
    },

    async refreshStatus() {
      try {
        var data = await OpenFangAPI.get('/api/channels');
        var byName = {};
        (data.channels || []).forEach(function(ch) { byName[ch.name] = ch; });
        this.allChannels.forEach(function(c) {
          var fresh = byName[c.name];
          if (fresh) {
            c.configured = fresh.configured;
            c.has_token = fresh.has_token;
            c.connected = fresh.configured && fresh.has_token;
            c.fields = fresh.fields;
          }
        });
      } catch(e) { console.warn('Channel refresh failed:', e.message); }
    },

    statusBadge(ch) {
      if (!ch.configured) return { text: 'Not Configured', cls: 'badge-muted' };
      if (!ch.has_token) return { text: 'Missing Token', cls: 'badge-warn' };
      if (ch.connected) return { text: 'Ready', cls: 'badge-success' };
      return { text: 'Configured', cls: 'badge-info' };
    },

    difficultyClass(d) {
      if (d === 'Easy') return 'difficulty-easy';
      if (d === 'Hard') return 'difficulty-hard';
      return 'difficulty-medium';
    },

    openSetup(ch) {
      this.setupModal = ch;
      // Pre-populate form values from saved config (non-secret fields).
      var vals = {};
      if (ch.fields) {
        ch.fields.forEach(function(f) {
          if (f.value !== undefined && f.value !== null && f.type !== 'secret') {
            vals[f.key] = String(f.value);
          }
        });
      }
      this.formValues = vals;
      this.showAdvanced = false;
      this.showBusinessApi = false;
      this.setupStep = ch.configured ? 3 : 1;
      this.testPassed = !!ch.configured;
      this.resetQR();
      // Auto-start QR flow for QR-type channels
      if (ch.setup_type === 'qr') {
        this.startQR();
      }
    },

    // ── QR Code Flow (WhatsApp Web style) ──────────────────────────

    resetQR() {
      this.qr = {
        loading: false, available: false, dataUrl: '', sessionId: '',
        message: '', help: '', connected: false, expired: false, error: ''
      };
      if (this.qrPollTimer) { clearInterval(this.qrPollTimer); this.qrPollTimer = null; }
    },

    async startQR() {
      this.qr.loading = true;
      this.qr.error = '';
      this.qr.connected = false;
      this.qr.expired = false;
      try {
        var result = await OpenFangAPI.post('/api/channels/whatsapp/qr/start', {});
        this.qr.available = result.available || false;
        this.qr.dataUrl = result.qr_data_url || '';
        this.qr.sessionId = result.session_id || '';
        this.qr.message = result.message || '';
        this.qr.help = result.help || '';
        this.qr.connected = result.connected || false;
        if (this.qr.available && this.qr.dataUrl && !this.qr.connected) {
          this.pollQR();
        }
        if (this.qr.connected) {
          OpenFangToast.success('WhatsApp connected!');
          await this.refreshStatus();
        }
      } catch(e) {
        this.qr.error = e.message || 'Could not start QR login';
      }
      this.qr.loading = false;
    },

    pollQR() {
      var self = this;
      if (this.qrPollTimer) clearInterval(this.qrPollTimer);
      this.qrPollTimer = setInterval(async function() {
        try {
          var result = await OpenFangAPI.get('/api/channels/whatsapp/qr/status?session_id=' + encodeURIComponent(self.qr.sessionId));
          if (result.connected) {
            clearInterval(self.qrPollTimer);
            self.qrPollTimer = null;
            self.qr.connected = true;
            self.qr.message = result.message || 'Connected!';
            OpenFangToast.success('WhatsApp linked successfully!');
            await self.refreshStatus();
          } else if (result.expired) {
            clearInterval(self.qrPollTimer);
            self.qrPollTimer = null;
            self.qr.expired = true;
            self.qr.message = 'QR code expired. Click to generate a new one.';
          } else {
            self.qr.message = result.message || 'Waiting for scan...';
          }
        } catch(e) { /* silent retry */ }
      }, 3000);
    },

    // ── Standard Form Flow ─────────────────────────────────────────

    async saveChannel() {
      if (!this.setupModal) return;
      var name = this.setupModal.name;
      this.configuring = true;
      try {
        await OpenFangAPI.post('/api/channels/' + name + '/configure', {
          fields: this.formValues
        });
        this.setupStep = 2;
        // Auto-test after save
        try {
          var testResult = await OpenFangAPI.post('/api/channels/' + name + '/test', {});
          if (testResult.status === 'ok') {
            this.testPassed = true;
            this.setupStep = 3;
            OpenFangToast.success(this.setupModal.display_name + ' activated!');
          } else {
            OpenFangToast.success(this.setupModal.display_name + ' saved. ' + (testResult.message || ''));
          }
        } catch(te) {
          OpenFangToast.success(this.setupModal.display_name + ' saved. Test to verify connection.');
        }
        await this.refreshStatus();
      } catch(e) {
        OpenFangToast.error('Failed: ' + (e.message || 'Unknown error'));
      }
      this.configuring = false;
    },

    async removeChannel() {
      if (!this.setupModal) return;
      var name = this.setupModal.name;
      var displayName = this.setupModal.display_name;
      var self = this;
      OpenFangToast.confirm('Remove Channel', 'Remove ' + displayName + ' configuration? This will deactivate the channel.', async function() {
        try {
          await OpenFangAPI.delete('/api/channels/' + name + '/configure');
          OpenFangToast.success(displayName + ' removed and deactivated.');
          await self.refreshStatus();
          self.setupModal = null;
        } catch(e) {
          OpenFangToast.error('Failed: ' + (e.message || 'Unknown error'));
        }
      });
    },

    async testChannel() {
      if (!this.setupModal) return;
      var name = this.setupModal.name;
      this.testing[name] = true;
      try {
        var result = await OpenFangAPI.post('/api/channels/' + name + '/test', {});
        if (result.status === 'ok') {
          this.testPassed = true;
          this.setupStep = 3;
          OpenFangToast.success(result.message);
        } else {
          OpenFangToast.error(result.message);
        }
      } catch(e) {
        OpenFangToast.error('Test failed: ' + (e.message || 'Unknown error'));
      }
      this.testing[name] = false;
    },

    async copyConfig(ch) {
      var tpl = ch ? ch.config_template : (this.setupModal ? this.setupModal.config_template : '');
      if (!tpl) return;
      try {
        await navigator.clipboard.writeText(tpl);
        OpenFangToast.success('Copied to clipboard');
      } catch(e) {
        OpenFangToast.error('Copy failed');
      }
    },

    destroy() {
      if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
      if (this.qrPollTimer) { clearInterval(this.qrPollTimer); this.qrPollTimer = null; }
    }
  };
}

// ── StaxCloud Connections — the owner page (System > Connections) ────
// Reports the product's own connections from the same records the
// Texts, Email and Team surfaces read: sms/ thread records and
// attention/sms for the text line, mailbox/status for email, teammsg/
// for the team channel, and the store's one gate snapshot for the
// text-reply mode. Daemon channel config (channelsPage above) is not
// a product connection and stays in Advanced. A leg whose record
// cannot be read says "Couldn't check" — this page never states a
// connection state the underlying record does not prove.
function connectionsPage() {
  function parseVal(v) {
    if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { return null; } }
    return v && typeof v === 'object' ? v : null;
  }
  function tsOf(x) {
    if (!x) return 0;
    var t = new Date(x).getTime();
    return isNaN(t) ? 0 : t;
  }
  return {
    loading: true,
    loadError: '',
    checkedAt: '',
    texts: null,
    // The replies row is a getter, not a load-time field: it derives
    // from the store's one gate snapshot at render time — the same
    // derive-at-render pattern as the drawer's staxStatus() — so a
    // gate refresh (drawer open, login, page load) updates this row
    // in place and it can never sit stale beside a fresher drawer.
    get replies() { return this.gateRow(Alpine.store('app').textGate); },
    email: null,
    team: null,
    helpers: null,
    wakes: null,

    gateRow(gate) {
      if (!gate || gate.mode === 'unknown') {
        return { tone: 'warn', status: "Couldn't check", sub: 'The reply setting did not load — try again in a moment' };
      }
      if (gate.mode === 'paused') {
        return { tone: 'quiet', status: 'Paused', sub: 'No replies are being drafted right now' };
      }
      var rsub = 'Replies wait in Needs you until you approve them';
      if (gate.held) rsub += ' · ' + gate.held + (gate.held === 1 ? ' reply' : ' replies') + ' waiting now';
      return { tone: 'ok', status: 'You approve', sub: rsub };
    },

    fmtTs(ts) {
      var t = tsOf(ts);
      if (!t) return '';
      var d = new Date(t);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ' ' +
             d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    },

    fmtClock(ts) {
      var t = tsOf(ts);
      if (!t) return '';
      return new Date(t).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    },

    async loadData() { return this.loadFacts(); },

    async loadFacts() {
      this.loading = true;
      this.loadError = '';
      var store = Alpine.store('app');
      var agentId = (store.agents[0] || {}).id || 'shared';
      var base = '/api/memory/agents/' + agentId + '/kv';
      var self = this;

      async function pairs(prefix) {
        var d = await OpenFangAPI.get(base + '?prefix=' + encodeURIComponent(prefix));
        return ((d && d.kv_pairs) || []).map(function(pr) {
          return { key: pr.key, value: parseVal(pr.value) };
        }).filter(function(pr) { return pr.value; });
      }
      // One record, read by prefix: a record that was never written is
      // an answer ("not set up"), not a failed read.
      async function one(key) {
        var d = await OpenFangAPI.get(base + '?prefix=' + encodeURIComponent(key));
        var hit = ((d && d.kv_pairs) || []).find(function(pr) { return pr.key === key; });
        return hit ? parseVal(hit.value) : null;
      }
      // Each leg reads independently: one leg's failed read marks only
      // that leg "Couldn't check", never the whole page.
      async function leg(fn) {
        try { return { ok: true, v: await fn() }; }
        catch(e) { return { ok: false, v: null }; }
      }

      var results = await Promise.all([
        leg(function() { return pairs('sms/'); }),
        leg(function() { return one('attention/sms'); }),
        leg(function() { return one('mailbox/status'); }),
        leg(function() { return pairs('teammsg/'); }),
        store.refreshTextGate(),
        leg(function() { return pairs('health/'); }),
        leg(function() { return pairs('wake/'); })
      ]);
      var smsR = results[0], attR = results[1], mbR = results[2], teamR = results[3], gate = results[4], hpR = results[5], wkR = results[6];

      // ── Text line: the shop's texting, from its thread records ──
      if (!smsR.ok) {
        this.texts = { tone: 'warn', status: "Couldn't check", sub: 'The text records did not load — try again in a moment' };
      } else if (!smsR.v.length) {
        this.texts = { tone: 'quiet', status: 'No texts yet', sub: 'Customer texts to the shop line land in Texts' };
      } else {
        var lastTs = 0;
        smsR.v.forEach(function(pr) {
          (Array.isArray(pr.value.messages) ? pr.value.messages : []).forEach(function(m) {
            var t = tsOf(m && m.ts); if (t > lastTs) lastTs = t;
          });
        });
        var sub = lastTs ? 'Last text ' + this.fmtTs(lastTs) : 'Texts are flowing to the shop line';
        if (attR.ok && attR.v && Array.isArray(attR.v.threads) && attR.v.threads.length) {
          var n = attR.v.threads.length;
          sub += ' · ' + n + (n === 1 ? ' conversation' : ' conversations') + ' waiting for a reply';
        }
        this.texts = { tone: 'ok', status: 'Connected', sub: sub };
      }

      // ── Text replies: no row is built here — the `replies` getter
      // renders the store snapshot (refreshed by the refreshTextGate
      // call in the Promise.all above) live, exactly as the drawer
      // and the Home pill do. `gate` is still used below for the
      // all-legs-failed error line.

      // ── Email: the mailbox's own status stamp ──
      if (!mbR.ok) {
        this.email = { tone: 'warn', status: "Couldn't check", sub: 'The mailbox check did not load — try again in a moment' };
      } else if (!mbR.v) {
        this.email = { tone: 'quiet', status: 'Not set up', sub: 'No shop mailbox is connected yet — ask Stax to connect one' };
      } else {
        var mb = mbR.v;
        var addr = mb.address || 'Shop email';
        var runT = tsOf(mb.last_run);
        if (!runT) {
          this.email = { tone: 'warn', status: "Couldn't check", sub: addr + ' · no check time on record' };
        } else {
          var esub = addr + ' · last checked ' + this.fmtTs(mb.last_run);
          if (mb.waiting_to_send) esub += ' · ' + mb.waiting_to_send + ' waiting to send';
          var fresh = (Date.now() - runT) <= 20 * 60000;
          this.email = fresh
            ? { tone: 'ok', status: 'Connected', sub: esub }
            : { tone: 'warn', status: 'Needs attention', sub: esub };
        }
      }

      // ── Team: the shop's channel, from its message records ──
      if (!teamR.ok) {
        this.team = { tone: 'warn', status: "Couldn't check", sub: 'The team channel did not load — try again in a moment' };
      } else if (!teamR.v.length) {
        this.team = { tone: 'ok', status: 'Connected', sub: 'The team channel is ready — no messages yet' };
      } else {
        var tTs = 0;
        teamR.v.forEach(function(pr) { var t = tsOf(pr.value.ts); if (t > tTs) tTs = t; });
        this.team = { tone: 'ok', status: 'Connected', sub: tTs ? 'Last message ' + this.fmtTs(tTs) : 'The team channel is in use' };
      }

      // ── Background helpers: each records health/<name> after every run ──
      this.helpers = staxHelperHealth(hpR, Date.now());
      this.wakes = staxWakeSummary(wkR, new Date());

      this.checkedAt = new Date().toISOString();
      if (!smsR.ok && !mbR.ok && !teamR.ok && (!gate || gate.mode === 'unknown')) {
        this.loadError = 'Your connections did not load. Check that StaxCloud is online, then try again.';
      }
      this.loading = false;
    }
  };
}

// Today's scheduled wakes, from each helper's wake/<name> receipt: how many
// reached a model, how many were skipped because there was nothing new, and
// what the woken ones cost. Receipts from an earlier day count as zero.
var STAX_WAKE_NAMES = { sms: 'Texts', forms: 'Forms', style: 'Style', memory: 'Memory', designer: 'Designs', stax: 'Stax' };
function staxWakeSummary(r, now) {
  if (!r || !r.ok) return null;
  var y = now.getFullYear(), m = ('0' + (now.getMonth() + 1)).slice(-2), d = ('0' + now.getDate()).slice(-2);
  var today = y + '-' + m + '-' + d;
  var woke = 0, skipped = 0, early = 0, cost = 0, parts = [];
  (r.v || []).forEach(function(pr) {
    var v = pr.value || {};
    if (v.day !== today) return;
    var w = Math.round(+v.woke || 0), s = Math.round(+v.skipped || 0), e = Math.round(+v.stopped_early || 0);
    woke += w; skipped += s; early += e; cost += +v.cost_usd || 0;
    var name = STAX_WAKE_NAMES[pr.key.slice(5)] || pr.key.slice(5);
    parts.push(name + ' ' + w + ' woke, ' + s + ' skipped' + (e ? ', ' + e + ' stopped early' : ''));
  });
  if (!parts.length) return { tone: 'quiet', status: 'No wakes yet today', sub: 'Scheduled checks show here once they run' };
  var money = cost < 0.01 ? 'under a cent' : '$' + cost.toFixed(2);
  // A helper that keeps hitting its limits is doing less than it was woken
  // for: worth the owner's eye.
  return { tone: early ? 'warn' : 'ok', status: woke + ' woke · ' + skipped + ' skipped' + (early ? ' · ' + early + ' stopped early' : ''), sub: parts.join(' · ') + ' — ' + money + ' today', woke: woke, skipped: skipped, early: early, cost: cost };
}

// What the background helpers' last runs say, in one row. A helper is
// "quiet" when it has not run for three of its intervals. Helper names are
// the box's script names; the owner sees plain ones.
var STAX_HELPER_NAMES = { 'pull-sync': 'Form sync', 'designer': 'Design bench', 'bridge': 'Text line link', 'mail': 'Mail sync', 'mailsync': 'Mail sync', 'mailsend': 'Mail sending' };
function staxHelperHealth(r, now) {
  if (!r || !r.ok) return { tone: 'warn', status: "Couldn't check", sub: 'The helpers\' records did not load — try again in a moment', rows: [] };
  var rows = (r.v || []).map(function(pr) {
    var v = pr.value || {}, name = pr.key.slice(7);
    var at = v.at ? Date.parse(v.at) : NaN, every = Math.max(1, +v.every_minutes || 5);
    var quiet = isNaN(at) || (now - at) > every * 3 * 60000;
    return { name: STAX_HELPER_NAMES[name] || name, ok: !!v.ok && !quiet, failed: v.ok === false, quiet: quiet, at: at };
  });
  if (!rows.length) return { tone: 'quiet', status: 'Not reporting', sub: 'The background helpers have not reported in yet', rows: [] };
  var bad = rows.filter(function(x) { return !x.ok; });
  if (!bad.length) return { tone: 'ok', status: 'Running', sub: rows.length + (rows.length === 1 ? ' helper' : ' helpers') + ' working normally', rows: rows };
  var words = bad.map(function(x) { return x.name + (x.failed && !x.quiet ? ' had a problem on its last run' : ' has gone quiet'); });
  return { tone: 'warn', status: 'Needs a look', sub: words.join('; ') + ' — ask Stax to check it', rows: rows };
}

