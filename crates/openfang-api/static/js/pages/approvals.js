// StaxCloud Work — Needs you (decisions), Current work, Finished.
// One count source: the header badge reads the shell store's
// pendingApprovalCount, the same number Home and the floating pill
// show. This page's own fetch feeds the lists only.
'use strict';

function approvalsPage() {
  return {
    approvals: [],
    jobs: [],
    heldBack: [],
    unownedAsks: [],
    loading: true,
    loadError: '',
    refreshTimer: null,
    expandedId: '',
    showCurrent: false,
    showFinished: false,

    init() {
      var self = this;
      this.loadData();
      this.refreshTimer = setInterval(function() {
        self.loadData();
      }, 5000);
      // The module dock jumps between this page's three sections:
      // open the section if it is an accordion, then scroll to it.
      this._onWorkSection = function(e) {
        var s = (e && e.detail) || 'needsyou';
        if (s === 'current') self.showCurrent = true;
        if (s === 'finished') self.showFinished = true;
        var tick = self.$nextTick || function(cb) { setTimeout(cb, 0); };
        tick(function() {
          var el = document.getElementById('work-' + s);
          if (el) el.scrollIntoView({ block: 'start' });
        });
      };
      window.addEventListener('stax-work-section', this._onWorkSection);
    },

    destroy() {
      if (this.refreshTimer) {
        clearInterval(this.refreshTimer);
        this.refreshTimer = null;
      }
      if (this._onWorkSection) window.removeEventListener('stax-work-section', this._onWorkSection);
    },

    // A held item keeps one identity across re-carries: the daemon
    // mints a new approval id each carry, so records are matched by
    // what they ask, not by id (the shell's toast de-dupe keys the
    // same way).
    fingerprint(a) {
      return [a.agent_id || a.agent_name || '', a.tool_name || a.action || '',
        a.description || '', a.action_summary || ''].join('|');
    },

    dedupe(list) {
      var seen = {}, out = [];
      var sorted = list.slice().sort(function(x, y) {
        return new Date(y.created_at || 0) - new Date(x.created_at || 0);
      });
      sorted.forEach(function(a) {
        var k = this.fingerprint(a);
        if (!seen[k]) { seen[k] = true; out.push(a); }
      }, this);
      return out;
    },

    get pendingList() {
      return this.dedupe(this.approvals.filter(function(a) { return a.status === 'pending'; }));
    },

    get decidedList() {
      // An item still live in Needs you is not also Finished: its
      // expired earlier carries are the same item, superseded.
      var live = {};
      this.pendingList.forEach(function(a) { live[this.fingerprint(a)] = true; }, this);
      var rest = this.approvals.filter(function(a) {
        return a.status !== 'pending' && !live[this.fingerprint(a)];
      }, this);
      return this.dedupe(rest);
    },

    // What would actually happen, in plain lines: the summary when it
    // adds anything, plus the call's own fields (a text's body, a
    // design's id) so no decision is blind.
    previewLines(a) {
      var lines = [];
      var desc = a.description || '';
      if (a.action_summary && a.action_summary !== desc) lines.push(a.action_summary);
      var args = a.args || a.tool_args || null;
      if (args && typeof args === 'object') {
        Object.keys(args).forEach(function(k) {
          var v = args[k];
          if (v === null || v === undefined || v === '') return;
          var s = (typeof v === 'object') ? JSON.stringify(v) : String(v);
          if (s.length > 300) s = s.slice(0, 300) + '…';
          lines.push(k + ': ' + s);
        });
      }
      var fmt = Alpine.store('app').fmtPhones;
      return lines.map(function(l) { return fmt(l); });
    },

    // ---- Design approvals: show the work (Wave 1.1) ----------------
    // A design approval's lineage names its draft record; the draft
    // names the request; the request's design records carry the
    // picture (preview_b64 — the same records Canvas reads). Loaded
    // once per held item, keyed by the item's fingerprint so a
    // re-carry under a fresh approval id reuses the read.
    designInfo: {},

    setDesignInfo(key, info) {
      var next = Object.assign({}, this.designInfo);
      next[key] = info;
      this.designInfo = next;
    },

    kvAgentId() {
      var agents = (Alpine.store('app') && Alpine.store('app').agents) || [];
      var designer = agents.filter(function(x) { return x.name === 'designer'; })[0];
      if (designer) return designer.id;
      return (agents[0] || {}).id || 'shared';
    },

    kvParse(v) {
      if (typeof v === 'string') { try { return JSON.parse(v); } catch (e) { return null; } }
      return (v && typeof v === 'object') ? v : null;
    },

    async kvGet(key) {
      var rec = await OpenFangAPI.get('/api/memory/agents/' + this.kvAgentId() + '/kv/' + encodeURIComponent(key));
      return this.kvParse(rec && rec.value);
    },

    async kvList(prefix, strip) {
      var url = '/api/memory/agents/' + this.kvAgentId() + '/kv?prefix=' + encodeURIComponent(prefix);
      if (strip) url += '&strip=' + encodeURIComponent(strip);
      var data = await OpenFangAPI.get(url);
      var out = {};
      (data.kv_pairs || []).forEach(function(pr) { out[pr.key] = pr.value; });
      return out;
    },

    _designLoading: {},

    async loadDesign(a) {
      var dk = a.lineage && a.lineage.draft_key;
      if (!dk) return;
      var key = this.fingerprint(a);
      var cur = this.designInfo[key];
      if (cur && cur.state !== 'error') return;
      if (this._designLoading[key]) return;
      this._designLoading[key] = true;
      // State stays unset until the draft proves to be a design
      // draft: a text reply's card must never flash a picture state.
      var info = { state: 'na', requestId: '', latestId: '', versions: 0, title: '', artistName: '', customer: '' };
      try {
        var draft = await this.kvGet(dk);
        if (!draft || draft.kind !== 'design_approval' || !draft.request_id) {
          this.setDesignInfo(key, info);
          delete this._designLoading[key];
          return;
        }
        info.state = 'loading';
        this.setDesignInfo(key, Object.assign({}, info));
        info.requestId = draft.request_id;
        info.customer = draft.customer_id || '';
        if (draft.artist_id) {
          var art = await this.kvGet('artist/' + draft.artist_id);
          if (art && art.display_name) info.artistName = art.display_name;
        }
        var designs = await this.kvList('design/', 'preview_b64,bundle_b64');
        var vers = [];
        Object.keys(designs).forEach(function(k) {
          var d = this.kvParse(designs[k]);
          if (d && d.request_id === info.requestId) vers.push(d);
        }, this);
        vers.sort(function(x, y) { return (parseInt(x.version, 10) || 0) - (parseInt(y.version, 10) || 0); });
        if (!vers.length) { info.state = 'none'; this.setDesignInfo(key, info); delete this._designLoading[key]; return; }
        var latest = vers[vers.length - 1];
        info.versions = vers.length;
        info.latestId = latest.id || '';
        info.title = latest.title || '';
        var full = info.latestId ? await this.kvGet('design/' + info.latestId) : null;
        if (full) {
          if (full.title) info.title = full.title;
          if (full.preview_b64) {
            info.state = 'ready';
            info.img = 'data:' + (full.preview_mime || 'image/jpeg') + ';base64,' + full.preview_b64;
          }
        }
        // No picture on the newest version (or the record itself did
        // not come back): the honest end state is the plain line,
        // never a stuck 'loading'.
        if (info.state !== 'ready') info.state = 'none';
        this.setDesignInfo(key, info);
      } catch (e) {
        info.state = 'error';
        this.setDesignInfo(key, info);
      }
      delete this._designLoading[key];
    },

    designOf(a) {
      return this.designInfo[this.fingerprint(a)] || null;
    },

    toggleExpand(a) {
      this.expandedId = this.expandedId === a.id ? '' : a.id;
      if (this.expandedId === a.id) this.loadDesign(a);
    },

    openInCanvas(a) {
      var info = this.designOf(a);
      if (!info || !info.latestId) return;
      var store = Alpine.store('app');
      if (!store.canvasCv) {
        store.canvasCv = { openId: '', sel: {}, note: {}, brief: '', artist: '', fileId: '', client: '', bg: 'white', setArtist: '', scroll: {}, layerSel: {}, msgDraft: '' };
      }
      store.canvasCv.openId = info.latestId;
      if (info.requestId) store.canvasCv.sel[info.requestId] = info.latestId;
      // Page navigation lives in the shell component's template scope,
      // not on the store; page components route by setting the hash
      // (the same pattern chat.js / wizard.js use).
      // Canvas is an Advanced page now; the deep link keeps working.
      window.location.hash = 'advanced/canvas';
    },

    // Who is asking, in the artist's words (One Face) — the store
    // resolver, shared with the Home strips.
    bylineName(a) {
      return Alpine.store('app').crewLabel(a);
    },

    // The card's title: the item's own words, phones formatted,
    // and — once the design read lands — the artist's real name
    // where the held text carries the artist's slug ("Design for
    // shawn:" becomes "Design for Shawn Lowe:").
    cardTitle(a) {
      var t = a.description || '';
      var info = this.designOf(a);
      if (info && info.artistName) {
        t = t.replace(/^Design for [a-z][a-z0-9_-]*:/i, 'Design for ' + info.artistName + ':');
      }
      return Alpine.store('app').fmtPhones(t);
    },

    // Held-back items (Work build §4): when the queue is full the
    // carriers refuse visibly instead of dropping work — each keeps
    // its refused drafts in a shared record the page reads. They are
    // NOT decisions waiting on the owner, so they never join the
    // badge or the pending count; they get their own plain line.
    get heldBackCount() {
      return this.heldBack.length;
    },

    get heldBackSeats() {
      var by = {};
      this.heldBack.forEach(function(e) { by[e.seat] = (by[e.seat] || 0) + 1; });
      return Object.keys(by).sort().map(function(s) { return s + ' ' + by[s]; }).join(' · ');
    },

    async loadData() {
      this.loading = true;
      this.loadError = '';
      try {
        var data = await OpenFangAPI.get('/api/approvals');
        this.approvals = data.approvals || [];
        // Design reads for the decision cards (titles carry the
        // artist's name; the expanded card carries the picture).
        // Guarded inside loadDesign — a 5s refresh does not refetch.
        this.pendingList.forEach(function(a) {
          if (a.lineage && a.lineage.draft_key) this.loadDesign(a);
        }, this);
      } catch(e) {
        this.loadError = e.message || 'Could not load approvals.';
      }
      try {
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        var kv = await OpenFangAPI.get('/api/memory/agents/' + agentId + '/kv?prefix=' + encodeURIComponent('attention/held-back'));
        var held = [];
        (kv.kv_pairs || []).forEach(function(pr) {
          var v = pr.value;
          if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { v = null; } }
          if (!v || typeof v !== 'object' || !v.entries) return;
          Object.keys(v.entries).forEach(function(k) {
            var e = v.entries[k] || {};
            held.push({ key: k, seat: e.seat || 'Texts', at: e.at || '' });
          });
        });
        this.heldBack = held;
      } catch(e) { this.heldBack = []; }
      // Unowned asks (Q2-A honesty build): asks no seat can do,
      // logged by Stax as standing records. Like held-back items
      // they are NOT decisions, so they never join the badge or
      // the pending count; unlike held-back items they leave only
      // when a resolution is written into the record itself — an
      // open record is listed on every load until then.
      try {
        var askMap = await this.kvList('ask/unowned');
        var asks = [];
        Object.keys(askMap).forEach(function(k) {
          var v = this.kvParse(askMap[k]);
          if (!v || typeof v !== 'object') return;
          if (v.status && v.status !== 'open') return;
          asks.push({ key: k, request: v.request || '',
            reason: v.reason || '', seatTried: v.seat_tried || '',
            ts: v.ts || '' });
        }, this);
        asks.sort(function(x, y) {
          return new Date(x.ts || 0) - new Date(y.ts || 0);
        });
        this.unownedAsks = asks;
      } catch(e) { this.unownedAsks = []; }
      try {
        var jd = await OpenFangAPI.get('/api/cron/jobs');
        this.jobs = jd.jobs || jd || [];
      } catch(e) { this.jobs = []; }
      this.loading = false;
    },

    async approve(id) {
      try {
        await OpenFangAPI.post('/api/approvals/' + id + '/approve', {});
        OpenFangToast.success('Approved');
        await this.loadData();
      } catch(e) {
        OpenFangToast.error(e.message);
      }
    },

    async reject(a) {
      var self = this;
      var words = Alpine.store('app').rejectWords(a, this.cardTitle(a));
      OpenFangToast.confirm(words.title, words.message, async function() {
        try {
          await OpenFangAPI.post('/api/approvals/' + a.id + '/reject', {});
          OpenFangToast.success('Rejected');
          await self.loadData();
        } catch(e) {
          OpenFangToast.error(e.message);
        }
      });
    },

    jobName(j) {
      return j.name || j.label || ({ texts: 'Texts check', designer: 'Design check', brief: 'Morning brief', forms: 'Forms check' })[j.hand_id] || j.hand_id || 'Scheduled check';
    },

    jobWhen(j) {
      var t = j.next_run_at || j.next_run || null;
      if (!t) return j.enabled === false ? 'Paused' : 'On its schedule';
      var d = new Date(t);
      if (isNaN(d)) return j.enabled === false ? 'Paused' : 'On its schedule';
      return (j.enabled === false ? 'Paused · next ' : 'Next ') + d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
    },

    timeAgo(dateStr) {
      if (!dateStr) return '';
      var d = new Date(dateStr);
      var secs = Math.floor((Date.now() - d.getTime()) / 1000);
      if (secs < 60) return secs + 's ago';
      if (secs < 3600) return Math.floor(secs / 60) + 'm ago';
      if (secs < 86400) return Math.floor(secs / 3600) + 'h ago';
      return Math.floor(secs / 86400) + 'd ago';
    }
  };
}
