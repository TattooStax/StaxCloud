// StaxCloud Canvas — the artist's design bench, its own app surface.
//
// One page, five tabs (Canvas · Layers · Display · Export · Settings)
// over the designer sidecar's records: designreq/ requests, design/
// built versions, draft/design- approval holds, designjob/ the work
// queue, artist/ the bench settings. The page queues job records
// exactly as the designer playbook prescribes and reads everything
// back from the same store the agent works — no surface-only state,
// and no design is customer-visible before the artist approves it.
// Layer state (order, visibility) is read back from the doc.op job
// receipts on the job records; export state from the export jobs'
// receipts and the design record's own exports.
'use strict';

function canvasPage() {
  return {
    kvAll: [],
    approvals: [],
    loading: true,
    loadError: '',
    // Working state that must survive tab switches, leaving the
    // module, and coming back (open design, version picks, drafts,
    // per-tab scroll). init() binds this to the store's canvasCv
    // object so the same object lives across page mounts.
    cv: { openId: '', sel: {}, note: {}, brief: '', artist: '', fileId: '', bg: 'white', setArtist: '', scroll: {} },
    decided: {},
    artistDraft: null,
    busy: false,
    err: '',
    fileName: '',
    _cvTimer: null,

    init() {
      var store = Alpine.store('app');
      if (store.canvasCv) {
        for (var k in store.canvasCv) this.cv[k] = store.canvasCv[k];
      }
      store.canvasCv = this.cv;
      var self = this;
      this.$watch('$store.app.canvasTab', function() {
        self.$nextTick(function() { self.cvRestoreScroll(); });
      });
    },

    cvTab() { return Alpine.store('app').canvasTab || 'canvas'; },

    cvNoteScroll() {
      var b = this.$refs.body;
      if (b) this.cv.scroll[this.cvTab()] = b.scrollTop;
    },
    cvRestoreScroll() {
      var b = this.$refs.body;
      if (b) b.scrollTop = this.cv.scroll[this.cvTab()] || 0;
    },

    async loadData(quiet) {
      if (!quiet) { this.loading = true; this.loadError = ''; }
      var self = this;
      try {
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        var data = await OpenFangAPI.get('/api/memory/agents/' + agentId + '/kv');
        this.kvAll = data.kv_pairs || [];
        try {
          var apData = await OpenFangAPI.get('/api/approvals');
          this.approvals = Array.isArray(apData) ? apData : (apData.approvals || []);
        } catch(e) { if (!quiet) this.approvals = []; }
        var artists = this.cvArtists();
        if (!this.cv.artist && artists.length) this.cv.artist = artists[0].id;
        if (!this.cv.setArtist && artists.length) this.cv.setArtist = artists[0].id;
        var cards = this.cvCards();
        var openJob = this.cvRecs('designjob/', true).some(function(j) {
          return j.v.args && j.v.args.request_id === self.cv.openId &&
            (j.v.status === 'queued' || j.v.status === 'running');
        });
        if (cards.length && !openJob && !cards.some(function(c) { return c.id === self.cv.openId; })) {
          this.cv.openId = cards[0].id;
        }
        this.cvSyncArtistDraft();
      } catch(e) {
        if (!quiet) this.loadError = e.message || 'Could not load Canvas.';
      }
      this.loading = false;
      this.cvArmPoll();
      if (!quiet) this.$nextTick(function() { self.cvRestoreScroll(); });
    },

    // ── Records (the same store the designer hand works) ────────────
    cvParse(v) {
      if (typeof v === 'string') { try { return JSON.parse(v); } catch(e) { return null; } }
      return v && typeof v === 'object' ? v : null;
    },
    cvRecs(prefix, skipIndex) {
      var out = [], self = this;
      this.kvAll.forEach(function(pr) {
        var k = pr.key || '';
        if (k.indexOf(prefix) !== 0) return;
        if (skipIndex && /^(index|meta)$/.test(k.slice(prefix.length))) return;
        var v = self.cvParse(pr.value);
        if (v && typeof v === 'object' && !v.deleted) out.push({ key: k, id: k.slice(prefix.length), v: v });
      });
      return out;
    },
    cvDesignerId() {
      var agents = (Alpine.store('app').agents || []);
      var d = agents.find(function(a) { return a.name === 'designer'; });
      return d ? d.id : ((agents[0] || {}).id || 'shared');
    },
    async cvKvPut(key, value) {
      await OpenFangAPI.put('/api/memory/agents/' + this.cvDesignerId() + '/kv/' + encodeURIComponent(key), { value: value });
    },
    async cvQueue(jobId, op, args) {
      await this.cvKvPut('designjob/' + jobId, { job_id: jobId, op: op, args: args, status: 'queued', ts: new Date().toISOString() });
      var idx = { jobs: [] };
      var recs = this.cvRecs('designjob/', false);
      for (var i = 0; i < recs.length; i++) {
        if (recs[i].id === 'index' && Array.isArray(recs[i].v.jobs)) idx = recs[i].v;
      }
      if (idx.jobs.indexOf(jobId) === -1) idx.jobs.push(jobId);
      await this.cvKvPut('designjob/index', idx);
    },
    cvArtists() {
      return this.cvRecs('artist/', true).map(function(r) {
        return { id: r.id, name: r.v.display_name || r.id };
      }).sort(function(a, b) { return a.name.localeCompare(b.name); });
    },
    cvArtistRec(id) {
      var recs = this.cvRecs('artist/', true);
      for (var i = 0; i < recs.length; i++) if (recs[i].id === id) return recs[i].v;
      return null;
    },
    cvArtistName(id) {
      var a = this.cvArtists().find(function(x) { return x.id === id; });
      return a ? a.name : id;
    },
    cvFirstName(id) { return this.cvArtistName(id).split(' ')[0]; },
    cvPlainErr(e) {
      var raw = String(e || '').replace(/^[A-Za-z]*Error:\s*/, '');
      // Technical failures (imports, file paths, module names) are
      // machinery, not owner language: show the plain version and
      // keep the detail on the job record where it belongs.
      if (/(\/[\w.-]+)+\//.test(raw) || /import|module|traceback/i.test(raw)) {
        return 'This design did not finish — the design tools hit a snag. You can try again.';
      }
      return raw;
    },
    cvCards() {
      var self = this;
      var designs = this.cvRecs('design/', true);
      var drafts = {};
      this.cvRecs('draft/', false).forEach(function(r) {
        if (r.id.indexOf('design-') === 0) drafts[r.id.slice(7)] = r.v;
      });
      var jobs = this.cvRecs('designjob/', true);
      var cards = this.cvRecs('designreq/', true).map(function(r) {
        var req = r.v, id = r.id;
        var mine = designs.filter(function(d) { return d.v.request_id === id; })
          .sort(function(a, b) { return (a.v.version || 0) - (b.v.version || 0); });
        var myJobs = jobs.filter(function(j) { return j.v.args && j.v.args.request_id === id; })
          .sort(function(a, b) { return String(a.v.ts || '').localeCompare(String(b.v.ts || '')); });
        var sel = mine.find(function(d) { return d.id === self.cv.sel[id]; }) || mine[mine.length - 1] || null;
        return { id: id,
                 brief: (req.intake || {}).prompt_text || 'Design',
                 artistId: req.artist_id || '',
                 status: req.status || '',
                 versions: mine, sel: sel,
                 draft: drafts[id] || null,
                 lastJob: myJobs[myJobs.length - 1] || null,
                 lastTs: myJobs.length ? (myJobs[myJobs.length - 1].v.ts || '') : '' };
      });
      cards.sort(function(a, b) { return String(b.lastTs).localeCompare(String(a.lastTs)); });
      return cards;
    },
    cvOpenCard() {
      var id = this.cv.openId;
      return this.cvCards().find(function(c) { return c.id === id; }) || null;
    },
    cvOpen(card) {
      this.cv.openId = card.id;
      this.cv.scroll.canvas = 0;
      var b = this.$refs.body;
      if (b && this.cvTab() === 'canvas') b.scrollTop = 0;
    },
    cvSelVersion(card, v) { this.cv.sel[card.id] = v.id; },
    cvState(card) {
      var j = card.lastJob;
      if (j && (j.v.status === 'queued' || j.v.status === 'running')) return { word: 'Designing…' };
      if (j && j.v.status === 'error' && !card.versions.length) return { word: 'Needs another try', error: this.cvPlainErr(j.v.error) };
      switch (card.status) {
        case 'artist_approved': return { word: 'Approved' };
        case 'artist_rejected': return { word: 'Not approved' };
        case 'awaiting_artist': return { word: 'Waiting for ' + this.cvFirstName(card.artistId) };
        case 'planned': return card.versions.length ? { word: 'Ready' } : { word: 'Designing…' };
        default: return { word: 'Getting ready' };
      }
    },
    cvClosed(card) {
      return ['artist_approved', 'artist_rejected', 'sent_to_customer', 'customer_approved', 'stencil_ready'].indexOf(card.status) !== -1;
    },
    cvApprovalFor(card) {
      if (!card.draft || !card.draft.approval_id) return null;
      return (this.approvals || []).find(function(a) { return a.id === card.draft.approval_id && a.status === 'pending'; }) || null;
    },
    cvHeadLine() {
      var cards = this.cvCards();
      if (!cards.length) return this.cvAnyJobBusy() ? 'Designing your first design…' : 'Your design bench';
      var waiting = cards.filter(function(c) { return c.status === 'awaiting_artist'; }).length;
      var parts = [cards.length + (cards.length === 1 ? ' design' : ' designs')];
      if (waiting) parts.push(waiting + ' waiting for your eye');
      return parts.join(' · ');
    },
    cvLayerLine(card) {
      if (!card.sel) return '';
      return (card.sel.v.layers || []).map(function(l) {
        return l.role === 'line' ? 'Line' : l.role === 'shading' ? 'Shading' : (l.name || l.role || '');
      }).join(' · ');
    },

    // ── Design jobs: generate, submit, approve, redesign ────────────
    async cvPickFile(ev) {
      var f = ev.target.files && ev.target.files[0];
      ev.target.value = '';
      if (!f) return;
      this.err = '';
      try {
        var res = await OpenFangAPI.upload(this.cvDesignerId(), f);
        this.cv.fileId = res.file_id;
        this.fileName = f.name;
      } catch(e) { this.err = 'That photo did not upload. Try again.'; }
    },
    async cvGenerate() {
      if (this.busy) return;
      this.err = '';
      if (!this.cv.fileId) { this.err = 'Add the reference photo first.'; return; }
      if (!this.cv.brief.trim()) { this.err = 'Say what we are designing.'; return; }
      this.busy = true;
      try {
        var reqId = 'req-' + Math.random().toString(36).slice(2, 10);
        await this.cvQueue('job-' + reqId + '-gen', 'gen.design', {
          request_id: reqId, brief: this.cv.brief.trim(),
          artist_id: this.cv.artist, reference_ref: this.cv.fileId });
        this.cv.brief = '';
        this.cv.fileId = '';
        this.fileName = '';
        this.cv.openId = reqId;
        await this.loadData(true);
      } catch(e) { this.err = 'The design did not start. Try again in a moment.'; }
      this.busy = false;
    },
    async cvSubmit(card) {
      try {
        await this.cvQueue('job-' + card.id + '-submit-' + Date.now(), 'request.submit', { request_id: card.id });
        await this.loadData(true);
      } catch(e) { OpenFangToast.error('That did not send. Try again in a moment.'); }
    },
    async cvApprove(card) {
      var ap = this.cvApprovalFor(card);
      if (!ap) return;
      try {
        await OpenFangAPI.post('/api/approvals/' + ap.id + '/approve', {});
        this.decided[card.id] = true;
        await this.loadData(true);
      } catch(e) { OpenFangToast.error('That approval did not save. Try again.'); }
    },
    cvReject(card) {
      var ap = this.cvApprovalFor(card);
      if (!ap) return;
      var self = this;
      OpenFangToast.confirm('Not approve this design?', 'It stays out of the customer view.', async function() {
        try {
          await OpenFangAPI.post('/api/approvals/' + ap.id + '/reject', {});
          self.decided[card.id] = true;
          await self.loadData(true);
        } catch(e) { OpenFangToast.error('That did not save. Try again.'); }
      });
    },
    async cvRedesign(card) {
      try {
        await this.cvQueue('job-' + card.id + '-rd-' + Date.now(), 'gen.redesign', {
          request_id: card.id, note: (this.cv.note[card.id] || '').trim() });
        this.cv.note[card.id] = '';
        await this.loadData(true);
      } catch(e) { OpenFangToast.error('That version did not start. Try again.'); }
    },

    // ── Per-design jobs (layers, exports): receipts on job records ──
    cvDesignJobs(designId) {
      return this.cvRecs('designjob/', true)
        .filter(function(j) { return j.v.args && j.v.args.design_id === designId; })
        .sort(function(a, b) { return String(a.v.ts || '').localeCompare(String(b.v.ts || '')); });
    },
    cvLastJob(designId, op, extra) {
      var js = this.cvDesignJobs(designId).filter(function(j) {
        if (j.v.op !== op) return false;
        return !extra || extra(j.v);
      });
      return js.length ? js[js.length - 1] : null;
    },
    cvAnyJobBusy() {
      return this.cvRecs('designjob/', true)
        .some(function(j) { return j.v.status === 'queued' || j.v.status === 'running'; });
    },

    // ── Layers ───────────────────────────────────────────────────────
    // The stack of the version on the canvas. Order and visibility
    // are derived from the design's doc.op job receipts (newest
    // wins) — the same records the agent reads — over the design
    // record's own layer list.
    cvLayers(card) {
      if (!card || !card.sel) return [];
      var layers = (card.sel.v.layers || []).map(function(l) {
        return { id: l.id, name: l.name || '', role: l.role || '', visible: true, busy: false };
      });
      var byId = {};
      layers.forEach(function(l) { byId[l.id] = l; });
      var order = null;
      this.cvDesignJobs(card.sel.id).forEach(function(j) {
        var a = j.v.args || {};
        if (j.v.op !== 'doc.op') return;
        if (j.v.status === 'queued' || j.v.status === 'running') {
          if (a.layer_id && byId[a.layer_id]) byId[a.layer_id].busy = true;
          return;
        }
        if (j.v.status !== 'done') return;
        if (a.op === 'set_visible' && a.layer_id && byId[a.layer_id]) {
          byId[a.layer_id].visible = !!(a.args && a.args.visible);
        }
        if (a.op === 'reorder' && j.v.result && Array.isArray(j.v.result.layers)) {
          order = j.v.result.layers;
        }
      });
      if (order) {
        layers.sort(function(x, y) {
          var ix = order.indexOf(x.id), iy = order.indexOf(y.id);
          return (ix === -1 ? 999 : ix) - (iy === -1 ? 999 : iy);
        });
      }
      return layers;
    },
    cvLayerName(layer) {
      if (layer.role === 'line') return 'Line';
      if (layer.role === 'shading') return 'Shading';
      var n = layer.name || layer.role || 'Layer';
      return n.charAt(0).toUpperCase() + n.slice(1);
    },
    cvLayerErr(card) {
      if (!card || !card.sel) return '';
      var j = this.cvLastJob(card.sel.id, 'doc.op');
      return j && j.v.status === 'error' ? 'The last layer change did not save — try again.' : '';
    },
    async cvToggleLayer(card, layer) {
      if (!card.sel || layer.busy) return;
      try {
        await this.cvQueue('job-' + card.sel.id + '-vis-' + Date.now(), 'doc.op', {
          design_id: card.sel.id, op: 'set_visible', layer_id: layer.id,
          base_revision: card.sel.v.revision, args: { visible: !layer.visible } });
        await this.loadData(true);
      } catch(e) { OpenFangToast.error('That did not save. Try again.'); }
    },
    async cvMoveLayer(card, layer, dir) {
      if (!card.sel || layer.busy) return;
      var layers = this.cvLayers(card);
      var i = -1;
      layers.forEach(function(l, ix) { if (l.id === layer.id) i = ix; });
      var target = i + dir;
      if (i === -1 || target < 0 || target >= layers.length) return;
      try {
        await this.cvQueue('job-' + card.sel.id + '-ord-' + Date.now(), 'doc.op', {
          design_id: card.sel.id, op: 'reorder', layer_id: layer.id,
          base_revision: card.sel.v.revision, args: { new_index: target } });
        await this.loadData(true);
      } catch(e) { OpenFangToast.error('That did not save. Try again.'); }
    },

    // ── Display + sharing ────────────────────────────────────────────
    cvStageStyle() {
      switch (this.cv.bg) {
        case 'clear': return 'background-color:#fff;background-image:conic-gradient(#ddd6c9 25%, #fff 0 50%, #ddd6c9 0 75%, #fff 0);background-size:18px 18px';
        case 'skin1': return 'background:#f3ddcb';
        case 'skin2': return 'background:#c68e5e';
        case 'skin3': return 'background:#7a4b2a';
        default: return 'background:#fff';
      }
    },
    cvShareStale(card) {
      if (!card || !card.sel) return false;
      var designId = card.sel.id;
      var layerChange = this.cvLastJob(designId, 'doc.op');
      var shareMade = this.cvLastJob(designId, 'doc.export', function(v) {
        return v.args && Array.isArray(v.args.kinds) && v.args.kinds.indexOf('share') !== -1;
      });
      if (!layerChange || layerChange.v.status !== 'done') return false;
      if (!shareMade) return true;
      return String(layerChange.v.ts || '') > String(shareMade.v.ts || '');
    },
    async cvExportKind(card, kind) {
      if (!card.sel) return;
      try {
        await this.cvQueue('job-' + card.sel.id + '-exp-' + kind + '-' + Date.now(), 'doc.export', {
          design_id: card.sel.id, kinds: [kind] });
        await this.loadData(true);
      } catch(e) { OpenFangToast.error('That did not start. Try again.'); }
    },
    cvExportState(card, kind) {
      if (!card || !card.sel) return '';
      var j = this.cvLastJob(card.sel.id, 'doc.export', function(v) {
        return v.args && Array.isArray(v.args.kinds) && v.args.kinds.indexOf(kind) !== -1;
      });
      if (j && (j.v.status === 'queued' || j.v.status === 'running')) return 'Making it…';
      if (j && j.v.status === 'error') return 'Did not finish — try again.';
      if (j && j.v.status === 'done' && Date.now() - Date.parse(j.v.ts || 0) < 600000) return 'Saved just now';
      return card.sel.v.exports && card.sel.v.exports[kind] ? 'Saved with the design' : '';
    },
    cvShareDesign(card) {
      var v = card && card.sel && card.sel.v;
      if (!v || !v.preview_b64) return;
      var mime = v.preview_mime || 'image/jpeg';
      try {
        if (navigator.share) {
          var bin = atob(v.preview_b64);
          var arr = new Uint8Array(bin.length);
          for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
          var file = new File([arr], (v.title || 'design') + '.jpg', { type: mime });
          if (navigator.canShare && navigator.canShare({ files: [file] })) {
            navigator.share({ files: [file] }).catch(function() {});
            return;
          }
          navigator.share({ title: v.title || 'Design' }).catch(function() {});
          return;
        }
      } catch(e) { /* fall through to the download below */ }
      var a = document.createElement('a');
      a.href = 'data:' + mime + ';base64,' + v.preview_b64;
      a.download = (v.title || 'design') + '.jpg';
      document.body.appendChild(a);
      a.click();
      a.remove();
    },

    // ── Export tab ───────────────────────────────────────────────────
    async cvExportPsd(card) {
      if (!card.sel) return;
      try {
        await this.cvQueue('job-' + card.sel.id + '-psd-' + Date.now(), 'export.psd', {
          design_id: card.sel.id });
        await this.loadData(true);
      } catch(e) { OpenFangToast.error('That did not start. Try again.'); }
    },
    cvPsdState(card) {
      if (!card || !card.sel) return '';
      var j = this.cvLastJob(card.sel.id, 'export.psd');
      if (j && (j.v.status === 'queued' || j.v.status === 'running')) return 'Making it…';
      if (j && j.v.status === 'error') return 'Did not finish — try again.';
      if (j && j.v.status === 'done' && j.v.result) {
        var n = (j.v.result.layers || []).length;
        var kb = Math.max(1, Math.round((j.v.result.size_bytes || 0) / 1024));
        return 'Saved · ' + n + (n === 1 ? ' layer' : ' layers') + ' · ' + kb + ' KB';
      }
      return card.sel.v.exports && card.sel.v.exports.psd ? 'Saved with the design' : '';
    },
    async cvExportBrush(card, layer) {
      if (!card.sel || !layer) return;
      try {
        await this.cvQueue('job-' + card.sel.id + '-brush-' + Date.now(), 'export.brush', {
          design_id: card.sel.id, layer_id: layer.id });
        await this.loadData(true);
      } catch(e) { OpenFangToast.error('That did not start. Try again.'); }
    },
    cvBrushJob(card, layer) {
      if (!card || !card.sel || !layer) return null;
      return this.cvLastJob(card.sel.id, 'export.brush', function(v) {
        return v.args && v.args.layer_id === layer.id;
      });
    },
    cvBrushState(card, layer) {
      var j = this.cvBrushJob(card, layer);
      if (!j) return '';
      if (j.v.status === 'queued' || j.v.status === 'running') return 'Making the stamp file…';
      if (j.v.status === 'error') return 'Did not finish — try again.';
      if (j.v.status === 'done') {
        // The job record carries the core's full proof-state string;
        // on screen it reads in plain words, the claim unchanged:
        // the file is saved, importing it is not proven yet.
        var st = j.v.result && j.v.result.record && j.v.result.record.spec_status;
        return 'Stamp file saved' + (st ? ' — importing into Procreate isn’t proven yet' : '');
      }
      return '';
    },
    cvLineLayer(card) {
      var layers = this.cvLayers(card);
      for (var i = 0; i < layers.length; i++) if (layers[i].role === 'line') return layers[i];
      return layers.length ? layers[0] : null;
    },
    cvSizeLine(card) {
      if (!card || !card.sel || !card.sel.v.size_bytes) return '';
      return Math.max(1, Math.round(card.sel.v.size_bytes / 1024)) + ' KB';
    },

    // ── Settings tab: the artist record itself ───────────────────────
    cvSyncArtistDraft() {
      var rec = this.cvArtistRec(this.cv.setArtist);
      if (!rec) { this.artistDraft = null; return; }
      this.artistDraft = {
        allow: !!rec.allow_customer_designs,
        versions: rec.versions_per_request || 1,
        presets: (rec.style_presets || []).slice(),
        note: rec.style_note || '',
        styles: (rec.styles || []).join(', '),
        specialties: (rec.specialties || []).join(', ')
      };
    },
    cvSetArtist(id) {
      this.cv.setArtist = id;
      this.cvSyncArtistDraft();
    },
    cvPresetOn(id) { return !!this.artistDraft && this.artistDraft.presets.indexOf(id) !== -1; },
    cvTogglePreset(id) {
      if (!this.artistDraft) return;
      var i = this.artistDraft.presets.indexOf(id);
      if (i === -1) this.artistDraft.presets.push(id);
      else this.artistDraft.presets.splice(i, 1);
    },
    cvStepVersions(d) {
      if (!this.artistDraft) return;
      var n = (this.artistDraft.versions || 1) + d;
      this.artistDraft.versions = Math.min(5, Math.max(1, n));
    },
    async cvSaveArtist() {
      var rec = this.cvArtistRec(this.cv.setArtist);
      if (!rec || !this.artistDraft) return;
      var v = JSON.parse(JSON.stringify(rec));
      v.allow_customer_designs = !!this.artistDraft.allow;
      v.versions_per_request = this.artistDraft.versions;
      v.style_presets = this.artistDraft.presets.slice();
      v.style_note = this.artistDraft.note;
      try {
        await this.cvKvPut('artist/' + this.cv.setArtist, v);
        await this.loadData(true);
        OpenFangToast.success('Saved');
      } catch(e) { OpenFangToast.error('That did not save. Try again.'); }
    },

    // ── Poll while work is in flight (the surface's refresh rule) ────
    cvPending() {
      if (this.cvAnyJobBusy()) return true;
      var self = this, any = false;
      Object.keys(this.decided).forEach(function(id) {
        var c = self.cvCards().find(function(x) { return x.id === id; });
        if (c && c.status === 'awaiting_artist') any = true;
        else delete self.decided[id];
      });
      return any;
    },
    cvArmPoll() {
      if (this._cvTimer) { clearTimeout(this._cvTimer); this._cvTimer = null; }
      if (this.cvPending()) {
        var self = this;
        this._cvTimer = setTimeout(function() { self.loadData(true); }, 5000);
      }
    }
  };
}
