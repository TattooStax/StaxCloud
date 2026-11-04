// Canvas: the design bench as its own app (the module-tabs law:
// every module carries its own bottom tabs). Composition per the
// owner's 2026-11-04 re-think, grounded in the creative-tool
// research: the bench is the front screen and it STAYS — Gallery
// is a page-changing destination (Procreate's Gallery, Figma's
// file browser); Layers, Stamps and Stencil are panels that open
// over the bench and tuck away (Procreate's panel-over-canvas,
// Canva's bottom-sheet pickers); undo/redo live in the bench
// chrome (Procreate's slider-bar arrows, Canva's top bar);
// Settings sits behind the header gear (Procreate's Actions).
// The in-Canvas composer is the same composer as Home's — same
// attach menu (Camera · Photos · Videos · Files), same send path
// (the per-agent message route) — pointed at the designer, and
// every send carries where the artist is (surface, tab, design,
// version, layers) so "make the leaves bigger" resolves against
// what's open. All state is the shared record families the
// designer hand works (design/, designreq/, designjob/, artist/,
// designlib/, designkit/, designsend/) — the surface never keeps
// anything the agent cannot reach; jobs queue exactly the records
// the hand queues. Working state (open design, drafts, tab,
// panel, per-tab scroll) persists in the store across surfaces.
// Layer state is read from the design's own job receipts (doc.op
// results), the same read the agent has.
function canvasPage() {
  return {
    cvKv: null,
    cvBusy: false,
    cvErr: '',
    cvStampName: '',
    cvKitName: '',
    cvThread: [],
    cvThreadBusy: false,
    cvAtts: [],
    _cvPoll: null,

    init() {
      var store = (window.Alpine && Alpine.store) ? Alpine.store('app') : this.$store.app;
      if (!store.canvasCv) {
        store.canvasCv = { openId: '', sel: {}, note: {}, brief: '', artist: '', fileId: '', client: '', bg: 'white', setArtist: '', scroll: {}, layerSel: {}, msgDraft: '' };
      }
      var self = this;
      this.$watch('$store.app.canvasTab', function(v) {
        self.$nextTick(function() {
          var sc = self.$refs.cvBody;
          var saved = (self.cv.scroll || {})[v];
          if (sc && saved != null) sc.scrollTop = saved;
        });
        if (v === 'gallery') self.loadData();
        if (v === 'canvas') self.cvArmPoll();
        self.cvNoteContext();
      });
      this.$watch('$store.app.canvasPanel', function() { self.cvNoteContext(); });
      this.$watch('$store.app.canvasTopNonce', function() {
        var sc = self.$refs.cvBody;
        if (sc) sc.scrollTo({ top: 0, behavior: 'smooth' });
      });
    },

    get cv() { return this.$store.app.canvasCv; },
    get cvTab() { return this.$store.app.canvasTab; },
    get cvPanel() { return this.$store.app.canvasPanel; },

    cvTabGo(tab) {
      var sc = this.$refs.cvBody;
      if (sc) { if (!this.cv.scroll) this.cv.scroll = {}; this.cv.scroll[this.cvTab] = sc.scrollTop; }
      this.$store.app.canvasGo(tab);
    },

    cvPanelGo(panel) { this.$store.app.canvasPanelToggle(panel); },

    // --- record reads (the same kv reads the Boards block made) --
    cvParse(v) { if (typeof v === 'string') { try { return JSON.parse(v); } catch (e) { return null; } } return v; },
    cvRecs(prefix) {
      var out = [], kv = this.cvKv || {};
      for (var k in kv) if (k.indexOf(prefix) === 0) { var r = this.cvParse(kv[k]); if (r) out.push(r); }
      return out;
    },
    get cvLoaded() { return !!this.cvKv; },
    get cvDesigns() {
      return this.cvRecs('design/').slice().sort(function(a, b) { return String(b.updated || '').localeCompare(String(a.updated || '')); });
    },
    get cvRequests() { var o = {}; this.cvRecs('designreq/').forEach(function(r) { o[r.id] = r; }); return o; },
    get cvJobs() {
      return this.cvRecs('designjob/').slice().sort(function(a, b) { return String(b.ts || '').localeCompare(String(a.ts || '')); });
    },
    cvDesignerId() {
      var jobs = (this.$store.app.jobs || []).filter(function(j) { return j.hand_id === 'designer'; });
      return jobs.length ? jobs[0].agent_id : '';
    },
    async cvKvPut(key, value) {
      var r = await fetch('/api/memory/kv/' + encodeURIComponent(key), {
        method: 'PUT', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: value })
      });
      if (!r.ok) throw new Error('save failed (' + r.status + ')');
    },
    async cvQueue(op, args) {
      var id = 'job-' + Math.random().toString(36).slice(2, 10);
      var rec = { job_id: id, op: op, args: args, status: 'queued', ts: new Date().toISOString() };
      await this.cvKvPut('designjob/' + id, rec);
      var idx = [];
      try { idx = this.cvParse((this.cvKv || {})['designjob/index']) || []; } catch (e) { idx = []; }
      if (!Array.isArray(idx)) idx = [];
      idx.push(id);
      await this.cvKvPut('designjob/index', idx);
      if (!this.cvKv) this.cvKv = {};
      this.cvKv['designjob/' + id] = rec;
      this.cvKv['designjob/index'] = idx;
      this.cvArmPoll();
      return id;
    },

    // --- artists --------------------------------------------------
    get cvArtists() {
      var idx = this.cvParse((this.cvKv || {})['artist/index']) || {};
      var self = this, out = [];
      (idx.artists || []).forEach(function(id) {
        var a = self.cvParse((self.cvKv || {})['artist/' + id]);
        if (a) out.push(a);
      });
      return out;
    },
    cvArtistOf(d) {
      if (!d) return null;
      var found = null;
      this.cvArtists.forEach(function(a) { if (a.id === d.artist_id) found = a; });
      return found;
    },
    cvCards() {
      var reqs = this.cvRequests, out = {};
      this.cvDesigns.forEach(function(d) {
        var rid = d.request_id;
        if (!out[rid]) out[rid] = { req: reqs[rid] || null, versions: [] };
        out[rid].versions.push(d);
      });
      Object.keys(out).forEach(function(rid) {
        out[rid].versions.sort(function(a, b) { return (a.version || 0) - (b.version || 0); });
      });
      return out;
    },
    get cvCardList() {
      var cards = this.cvCards();
      return Object.keys(cards).map(function(k) { return cards[k]; }).sort(function(a, b) {
        var la = a.versions[a.versions.length - 1], lb = b.versions[b.versions.length - 1];
        return String((lb && lb.updated) || '').localeCompare(String((la && la.updated) || ''));
      });
    },
    cvState(req) {
      if (!req) return 'On the bench';
      return {
        received: 'Just in', routed: 'With the artist', offered: 'Waiting on the customer',
        awaiting_choice: 'Waiting on the customer', planned: 'Making versions',
        in_production: 'Making versions', artist_review: 'Needs your eye',
        awaiting_artist: 'Needs your eye', artist_approved: 'Approved',
        artist_rejected: 'Not going ahead', sent_to_customer: 'Sent to the customer',
        revision_requested: 'Customer asked for changes', customer_approved: 'Customer approved it',
        stencil_ready: 'Stencil ready', completed: 'Done', closed: 'Done'
      }[req.status] || 'On the bench';
    },
    cvClosed(req) { return !!req && ['artist_approved', 'sent_to_customer', 'customer_approved', 'stencil_ready', 'completed'].indexOf(req.status) >= 0; },
    cvApprovalFor(req) {
      if (!req) return null;
      var all = this.$store.app.pendingApprovals || [];
      for (var i = 0; i < all.length; i++) if ((all[i].description || '').indexOf(req.id) >= 0) return all[i];
      return null;
    },

    // --- the bench ------------------------------------------------
    get cvOpen() {
      var id = this.cv.openId;
      if (!id) return null;
      var found = null;
      this.cvDesigns.forEach(function(d) { if (d.id === id) found = d; });
      return found;
    },
    get cvOpenReq() { var d = this.cvOpen; return d ? (this.cvRequests[d.request_id] || null) : null; },
    get cvVersions() {
      var d = this.cvOpen;
      if (!d) return [];
      return this.cvDesigns.filter(function(x) { return x.request_id === d.request_id; })
        .sort(function(a, b) { return (a.version || 0) - (b.version || 0); });
    },
    cvOpenDesign(id) {
      this.cv.openId = id;
      var d = this.cvOpen;
      if (d) this.cv.sel[d.request_id] = id;
      if (this.cvTab !== 'canvas') this.cvTabGo('canvas');
      this.cvLoadThread();
      this.cvNoteContext();
    },
    cvHeadLine() {
      if (this.cvTab === 'gallery') return 'Every design on the bench';
      if (this.cvTab === 'settings') return 'How your bench is set up';
      var cards = this.cvCardList.length;
      var need = 0, reqs = this.cvRequests;
      Object.keys(reqs).forEach(function(k) { if (reqs[k].status === 'awaiting_artist' || reqs[k].status === 'artist_review') need++; });
      if (!cards) return 'Your bench is clear';
      return cards + (cards === 1 ? ' design' : ' designs') + (need ? ' · ' + need + ' need' + (need === 1 ? 's' : '') + ' your eye' : '');
    },
    cvGenState(reqId) {
      var job = this.cvJobs.filter(function(j) {
        return (j.op === 'gen.design' || j.op === 'gen.redesign') && j.args && j.args.request_id === reqId;
      })[0];
      if (!job) return null;
      if (job.status === 'queued') return { phase: 'working', text: 'Making the versions…' };
      if (job.status === 'error') return { phase: 'error', text: 'The last try didn\'t finish — ' + cvPlainErr(job.error) + ' You can try again.' };
      if (job.status === 'done') {
        var when = job.result && job.result.finished_ts ? Date.parse(job.result.finished_ts) : NaN;
        if (!isNaN(when) && Date.now() - when < 60000) return { phase: 'done', text: 'Fresh versions are on the canvas.' };
      }
      return null;
    },
    cvJobError(op, key, value) {
      var job = this.cvJobs.filter(function(j) {
        return j.op === op && j.args && String(j.args[key]) === String(value);
      })[0];
      if (job && job.status === 'error') return 'That didn\'t finish — ' + cvPlainErr(job.error) + ' You can try again.';
      return '';
    },
    cvExportState(kind, d) {
      if (!d) return null;
      var job = this.cvJobs.filter(function(j) {
        return j.op === 'doc.export' && j.args && j.args.design_id === d.id && j.args.kind === kind;
      })[0];
      if (job) {
        if (job.status === 'queued') return 'Saving…';
        if (job.status === 'error') return 'That save didn\'t finish — ' + cvPlainErr(job.error);
        if (job.status === 'done') {
          var when = job.result && job.result.finished_ts ? Date.parse(job.result.finished_ts) : NaN;
          return (!isNaN(when) && Date.now() - when < 600000) ? 'Saved just now' : 'Saved with the design';
        }
      }
      return (d.exports && d.exports[kind]) ? 'Saved with the design' : null;
    },

    // --- layers: read from the design's own receipts ---------------
    get cvLayers() {
      var d = this.cvOpen;
      if (!d) return [];
      var order = (d.layers || []).map(function(l) { return l.id; });
      var meta = {};
      (d.layers || []).forEach(function(l) { meta[l.id] = l; });
      var visible = {}, seenOrder = null;
      this.cvJobs.filter(function(j) { return j.op === 'doc.op' && j.args && j.args.design_id === d.id && j.status === 'done' && j.result; })
        .slice().sort(function(a, b) { return String(a.ts || '').localeCompare(String(b.ts || '')); })
        .forEach(function(j) {
          var sub = j.args.op, a = j.args.args || {};
          if (sub === 'set_visible' && j.args.layer_id) visible[j.args.layer_id] = !!a.visible;
          if ((sub === 'reorder' || sub === 'merge') && j.result.layers) seenOrder = j.result.layers.slice();
          if (sub === 'merge') visible = {};
          if (sub === 'remove' && j.args.layer_id) { var ix = order.indexOf(j.args.layer_id); if (ix >= 0) order.splice(ix, 1); }
        });
      if (seenOrder) order = seenOrder.filter(function(id) { return meta[id]; });
      return order.map(function(id, i) {
        return { id: id, name: (meta[id] && meta[id].name) || id, role: (meta[id] && meta[id].role) || '',
                 visible: visible[id] !== false, top: i === order.length - 1, bottom: i === 0 };
      }).reverse();
    },
    cvLayerJob(op, args, layerId) {
      var d = this.cvOpen;
      if (!d || this.cvBusy) return;
      var self = this;
      this.cvBusy = true; this.cvErr = '';
      var jobArgs = { design_id: d.id, op: op, base_revision: d.revision || 0, args: args || {} };
      if (layerId) jobArgs.layer_id = layerId;
      this.cvQueue('doc.op', jobArgs).then(function() { self.cvArmPoll(true); })
        .catch(function(e) { self.cvErr = 'That didn\'t go through — ' + cvPlainErr(e && e.message); })
        .finally(function() { self.cvBusy = false; });
    },
    cvToggleLayer(l) { this.cvLayerJob('set_visible', { visible: !l.visible }, l.id); },
    cvMoveLayer(l, dir) {
      var list = this.cvLayers; // top-first
      var i = -1;
      list.forEach(function(x, ix) { if (x.id === l.id) i = ix; });
      var j = i + dir;
      if (i < 0 || j < 0 || j >= list.length) return;
      var newIndex = (list.length - 1) - j; // doc indexes run bottom-first
      this.cvLayerJob('reorder', { new_index: newIndex }, l.id);
    },
    // Combine: the pinch rule — the picked layers merge along with
    // everything between them (Procreate's own rule), into the
    // bottom picked layer.
    cvLayerSel(id) { return !!((this.cv.layerSel || {})[id]); },
    cvToggleSel(id) {
      if (!this.cv.layerSel) this.cv.layerSel = {};
      this.cv.layerSel[id] = !this.cv.layerSel[id];
    },
    get cvSelLayers() {
      var sel = this.cv.layerSel || {};
      return this.cvLayers.filter(function(l) { return sel[l.id]; });
    },
    get cvSpanCount() {
      var list = this.cvLayers, sel = this.cvSelLayers;
      if (sel.length < 2) return sel.length;
      var idx = sel.map(function(l) { return list.indexOf(l); });
      return Math.max.apply(null, idx) - Math.min.apply(null, idx) + 1;
    },
    cvCombine() {
      var sel = this.cvSelLayers;
      if (sel.length < 2 || this.cvBusy) return;
      this.cvLayerJob('merge', { layer_ids: sel.map(function(l) { return l.id; }) });
      this.cv.layerSel = {};
    },
    cvUndoRedo(which) {
      var d = this.cvOpen;
      if (!d || this.cvBusy) return;
      var self = this;
      this.cvBusy = true; this.cvErr = '';
      this.cvQueue(which === 'undo' ? 'doc.undo' : 'doc.redo', { design_id: d.id })
        .then(function() { self.cvArmPoll(true); })
        .catch(function(e) { self.cvErr = 'That didn\'t go through — ' + cvPlainErr(e && e.message); })
        .finally(function() { self.cvBusy = false; });
    },

    // --- stencil panel: formats, look, sharing ---------------------
    cvStageStyle(d) {
      var bg = this.cv.bg || 'white';
      if (bg === 'white') return '';
      var tones = { skin1: '#f3ddcb', skin2: '#c68e5e', skin3: '#7a4b2a' };
      if (tones[bg]) return 'background:' + tones[bg] + ';mix-blend-mode:multiply;border-radius:12px';
      return 'background:repeating-conic-gradient(#e8e8e8 0% 25%, #fbfbfb 0% 50%) 0 0/22px 22px;border-radius:12px';
    },
    cvStageLine() {
      return { white: 'Shown on white', clear: 'Shown see-through, the way it sits on skin', skin1: 'Shown on a light skin tone', skin2: 'Shown on a medium skin tone', skin3: 'Shown on a deep skin tone' }[this.cv.bg || 'white'];
    },
    cvStencilJob(kind) {
      var d = this.cvOpen;
      if (!d) return;
      var self = this;
      this.cvBusy = true; this.cvErr = '';
      this.cvQueue('doc.export', { design_id: d.id, kind: kind })
        .then(function() { self.cvArmPoll(true); })
        .catch(function(e) { self.cvErr = 'That didn\'t go through — ' + cvPlainErr(e && e.message); })
        .finally(function() { self.cvBusy = false; });
    },
    cvStencilState() {
      var d = this.cvOpen;
      var st = this.cvExportState('stencil', d);
      if (!st) return null;
      var job = this.cvJobs.filter(function(j) { return j.op === 'doc.export' && j.args && j.args.design_id === d.id && j.args.kind === 'stencil' && j.status === 'done'; })[0];
      var sr = job && job.result && job.result.stencil_record;
      if (sr && sr.review_state) st += ' · ' + String(sr.review_state).replace(/_/g, ' ');
      return st;
    },
    get cvPsdJob() {
      var d = this.cvOpen;
      if (!d) return null;
      return this.cvJobs.filter(function(j) { return j.op === 'export.psd' && j.args && j.args.design_id === d.id; })[0] || null;
    },
    cvPsdState() {
      var j = this.cvPsdJob;
      if (!j) { var d = this.cvOpen; return (d && d.exports && d.exports.psd) ? 'Saved with the design' : null; }
      if (j.status === 'queued') return 'Saving…';
      if (j.status === 'error') return 'That save didn\'t finish — ' + cvPlainErr(j.error);
      if (j.status === 'done') {
        var r = j.result || {}, when = r.finished_ts ? Date.parse(r.finished_ts) : NaN;
        var base = (!isNaN(when) && Date.now() - when < 600000) ? 'Saved just now' : 'Saved with the design';
        return base + (r.layers ? ' · ' + r.layers.length + ' layers, ' + (r.width || '?') + ' × ' + (r.height || '?') : '');
      }
      return null;
    },
    cvExportPsd() {
      var d = this.cvOpen;
      if (!d) return;
      var self = this;
      this.cvBusy = true; this.cvErr = '';
      this.cvQueue('export.psd', { design_id: d.id })
        .then(function() { self.cvArmPoll(true); })
        .catch(function(e) { self.cvErr = 'That didn\'t go through — ' + cvPlainErr(e && e.message); })
        .finally(function() { self.cvBusy = false; });
    },
    get cvBrushJob() {
      var d = this.cvOpen;
      if (!d) return null;
      return this.cvJobs.filter(function(j) { return j.op === 'export.brush' && j.args && j.args.design_id === d.id; })[0] || null;
    },
    cvBrushState() {
      var j = this.cvBrushJob;
      if (!j) return null;
      if (j.status === 'queued') return 'Saving…';
      if (j.status === 'error') return 'That save didn\'t finish — ' + cvPlainErr(j.error);
      if (j.status === 'done') return 'Brush file saved — importing into Procreate isn\'t proven yet';
      return null;
    },
    cvExportBrush() {
      var d = this.cvOpen;
      if (!d) return;
      var line = (d.layers || []).filter(function(l) { return l.role === 'line'; })[0];
      var self = this;
      this.cvBusy = true; this.cvErr = '';
      this.cvQueue('export.brush', { design_id: d.id, layer_id: line ? line.id : undefined })
        .then(function() { self.cvArmPoll(true); })
        .catch(function(e) { self.cvErr = 'That didn\'t go through — ' + cvPlainErr(e && e.message); })
        .finally(function() { self.cvBusy = false; });
    },
    cvShareStale(kind) {
      var d = this.cvOpen;
      if (!d || !d.exports || !d.exports[kind]) return false;
      return this.cvJobs.some(function(j) {
        return j.op === 'doc.op' && j.args && j.args.design_id === d.id && j.status === 'done' &&
          j.result && j.result.finished_ts && (!d.updated || String(j.result.finished_ts) > String(d.updated));
      });
    },
    async cvShareDesign() {
      var d = this.cvOpen;
      if (!d || !d.preview_b64) return;
      try {
        var bin = atob(d.preview_b64), bytes = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        var file = new File([new Blob([bytes], { type: d.preview_mime || 'image/jpeg' })], 'design.jpg', { type: d.preview_mime || 'image/jpeg' });
        if (navigator.canShare && navigator.canShare({ files: [file] })) { await navigator.share({ files: [file] }); return; }
        throw new Error('no-native-share');
      } catch (e) {
        var a = document.createElement('a');
        a.href = 'data:' + (d.preview_mime || 'image/jpeg') + ';base64,' + d.preview_b64;
        a.download = 'design.jpg';
        document.body.appendChild(a); a.click(); a.remove();
      }
    },

    // --- stamps panel: the artists' stamp + brush library ----------
    get cvElements() {
      var kv = this.cvKv || {}, out = [];
      for (var k in kv) if (k.indexOf('designlib/') === 0 && k !== 'designlib/index') { var r = this.cvParse(kv[k]); if (r) out.push(r); }
      return out;
    },
    get cvKits() {
      var kv = this.cvKv || {}, out = [];
      for (var k in kv) if (k.indexOf('designkit/') === 0 && k !== 'designkit/index') { var r = this.cvParse(kv[k]); if (r) out.push(r); }
      return out;
    },
    cvElementsOf(artistId) { return this.cvElements.filter(function(e) { return e.artist_id === artistId; }); },
    cvKitsOf(artistId) { return this.cvKits.filter(function(k) { return k.artist_id === artistId; }); },
    cvKitJob(kit) {
      return this.cvJobs.filter(function(j) { return j.op === 'export.brushset' && j.args && j.args.kit_id === kit.kit_id; })[0] || null;
    },
    cvKitState(kit) {
      var j = this.cvKitJob(kit);
      if (!j) return '';
      if (j.status === 'queued') return 'Saving…';
      if (j.status === 'error') return 'That save didn\'t finish — ' + cvPlainErr(j.error);
      if (j.status === 'done') return 'Kit file saved — importing into Procreate isn\'t proven yet';
      return '';
    },
    cvSaveLineAsStamp() {
      var d = this.cvOpen;
      if (!d || this.cvBusy) return;
      var line = (d.layers || []).filter(function(l) { return l.role === 'line'; })[0] || (d.layers || [])[0];
      if (!line) return;
      var self = this;
      this.cvBusy = true; this.cvErr = '';
      this.cvQueue('library.save_element', { design_id: d.id, layer_id: line.id, artist_id: d.artist_id, name: this.cvStampName || undefined })
        .then(function() { self.cvStampName = ''; self.cvArmPoll(true); })
        .catch(function(e) { self.cvErr = 'That didn\'t go through — ' + cvPlainErr(e && e.message); })
        .finally(function() { self.cvBusy = false; });
    },
    cvCreateKit(artistId) {
      var name = (this.cvKitName || '').trim();
      if (!name || this.cvBusy) return;
      var self = this;
      this.cvBusy = true; this.cvErr = '';
      this.cvQueue('library.create_kit', { artist_id: artistId, name: name })
        .then(function() { self.cvKitName = ''; self.cvArmPoll(true); })
        .catch(function(e) { self.cvErr = 'That didn\'t go through — ' + cvPlainErr(e && e.message); })
        .finally(function() { self.cvBusy = false; });
    },
    cvAddToKit(kit, el) {
      if (this.cvBusy) return;
      var self = this;
      this.cvBusy = true; this.cvErr = '';
      this.cvQueue('library.add_to_kit', { artist_id: kit.artist_id, kit_id: kit.kit_id, element_id: el.element_id })
        .then(function() { self.cvArmPoll(true); })
        .catch(function(e) { self.cvErr = 'That didn\'t go through — ' + cvPlainErr(e && e.message); })
        .finally(function() { self.cvBusy = false; });
    },
    cvExportKit(kit) {
      if (this.cvBusy) return;
      var self = this;
      this.cvBusy = true; this.cvErr = '';
      this.cvQueue('export.brushset', { artist_id: kit.artist_id, kit_id: kit.kit_id })
        .then(function() { self.cvArmPoll(true); })
        .catch(function(e) { self.cvErr = 'That didn\'t go through — ' + cvPlainErr(e && e.message); })
        .finally(function() { self.cvBusy = false; });
    },

    // --- request actions (the approval flow, untouched) -------------
    cvPending(req) { return !!req && (req.status === 'awaiting_artist' || req.status === 'artist_review'); },
    cvSubmit(req) {
      if (!req || this.cvBusy) return;
      var self = this;
      this.cvBusy = true; this.cvErr = '';
      this.cvQueue('request.submit', { request_id: req.id })
        .then(function() { self.cvArmPoll(true); })
        .catch(function(e) { self.cvErr = 'That didn\'t go through — ' + cvPlainErr(e && e.message); })
        .finally(function() { self.cvBusy = false; });
    },
    async cvApprove(req) {
      var hold = this.cvApprovalFor(req);
      if (!hold) return;
      try { await this.$store.app.approveApproval(hold); } catch (e) { /* the notice stays the source */ }
      this.loadData();
    },
    async cvReject(req) {
      var hold = this.cvApprovalFor(req);
      if (!hold) return;
      try { await this.$store.app.rejectApproval(hold); } catch (e) { /* the notice stays the source */ }
      this.loadData();
    },
    cvRedesign(card) {
      var req = card.req;
      var note = (this.cv.note[req.id] || '').trim();
      if (!req || !note || this.cvBusy) return;
      var self = this;
      this.cvBusy = true; this.cvErr = '';
      this.cvQueue('gen.redesign', { request_id: req.id, note: note })
        .then(function() { self.cv.note[req.id] = ''; self.cvArmPoll(true); })
        .catch(function(e) { self.cvErr = 'That didn\'t go through — ' + cvPlainErr(e && e.message); })
        .finally(function() { self.cvBusy = false; });
    },
    cvPickFile(ev) {
      var f = ev.target.files && ev.target.files[0];
      ev.target.value = '';
      if (!f) return;
      var self = this;
      this.cvErr = '';
      OpenFangAPI.upload(this.cvDesignerId(), f).then(function(res) {
        self.cv.fileId = res.file_id;
      }).catch(function() { self.cvErr = 'That picture didn\'t attach — try again.'; });
    },
    cvGenerate() {
      var brief = (this.cv.brief || '').trim();
      if (!brief || this.cvBusy) return;
      var artist = this.cv.artist || (this.cvArtists[0] && this.cvArtists[0].id) || '';
      if (!artist) { this.cvErr = 'Pick who the design is for first.'; return; }
      var self = this;
      this.cvBusy = true; this.cvErr = '';
      var rid = 'req-' + Math.random().toString(36).slice(2, 10);
      // The client mock-up seam: a design can be FOR someone — the
      // request carries the client and where the ask came from, the
      // design is made under the artist's own style, and on approval
      // it can go back into that client's thread as a picture.
      var args = { request_id: rid, brief: brief, artist_id: artist, reference_ref: this.cv.fileId || undefined };
      var client = (this.cv.client || '').trim();
      if (client) { args.client = client; args.channel = 'canvas'; }
      this.cvQueue('gen.design', args)
        .then(function() {
          self.cv.brief = ''; self.cv.fileId = ''; self.cv.client = '';
          if (self.cvTab !== 'canvas') self.cvTabGo('canvas');
          self.cvArmPoll(true);
        })
        .catch(function(e) { self.cvErr = 'That didn\'t go through — ' + cvPlainErr(e && e.message); })
        .finally(function() { self.cvBusy = false; });
    },

    // Requests with no designs yet — a first generation still
    // working, or one that didn't finish (its error must show
    // somewhere, not vanish with the missing card).
    get cvOrphanReqs() {
      var have = {};
      this.cvDesigns.forEach(function(d) { have[d.request_id] = true; });
      var reqs = this.cvRequests, out = [];
      Object.keys(reqs).forEach(function(k) { if (!have[k]) out.push(reqs[k]); });
      return out.sort(function(a, b) { return String(b.updated || '').localeCompare(String(a.updated || '')); });
    },
    get cvAnyGenWorking() {
      return this.cvJobs.some(function(j) { return (j.op === 'gen.design' || j.op === 'gen.redesign') && j.status === 'queued'; });
    },
    async cvSaveArtistFor(rec, patch) {
      if (!rec || this.cvBusy) return;
      var next = Object.assign({}, rec, patch);
      var self = this;
      this.cvBusy = true; this.cvErr = '';
      try {
        await this.cvKvPut('artist/' + rec.id, next);
        await this.loadData();
        OpenFangToast.success('Saved');
      } catch (e) { this.cvErr = 'That didn\'t save — ' + cvPlainErr(e && e.message); }
      this.cvBusy = false;
    },

    // --- settings: the artist's own bench setup ---------------------
    cvSyncArtistDraft() {
      var list = this.cvArtists;
      if (!list.length) return;
      if (!this.cv.setArtist || !list.some(function(a) { return a.id === this.cv.setArtist; })) this.cv.setArtist = list[0].id;
    },
    get cvSetArtistRec() {
      var id = this.cv.setArtist, found = null;
      this.cvArtists.forEach(function(a) { if (a.id === id) found = a; });
      return found;
    },
    async cvSaveArtist(patch) {
      var rec = this.cvSetArtistRec;
      if (!rec || this.cvBusy) return;
      var next = Object.assign({}, rec, patch);
      var self = this;
      this.cvBusy = true; this.cvErr = '';
      try {
        await this.cvKvPut('artist/' + rec.id, next);
        await this.loadData(); // read the record back before claiming it saved
        OpenFangToast.success('Saved');
      } catch (e) { this.cvErr = 'That didn\'t save — ' + cvPlainErr(e && e.message); }
      this.cvBusy = false;
    },
    cvSetVersions(delta) {
      var rec = this.cvSetArtistRec;
      if (!rec) return;
      var v = Math.max(1, Math.min(5, (rec.versions_per_request || 1) + delta));
      if (v !== rec.versions_per_request) this.cvSaveArtist({ versions_per_request: v });
    },
    cvTogglePreset() {
      var rec = this.cvSetArtistRec;
      if (!rec) return;
      var has = (rec.style_presets || []).indexOf('tattoo-smooth-grey') >= 0;
      this.cvSaveArtist({ style_presets: has ? [] : ['tattoo-smooth-grey'] });
    },

    // --- the composer: same component as Home, pointed at the -----
    // --- designer, carrying where the artist is -------------------
    cvContextLine() {
      var parts = ['In Canvas'];
      parts.push(this.cvTab === 'gallery' ? 'looking at the gallery' : (this.cvTab === 'settings' ? 'in the bench settings' : 'at the bench'));
      if (this.cvPanel) parts.push('with the ' + this.cvPanel + ' panel open');
      var d = this.cvOpen;
      if (d) {
        var req = this.cvOpenReq;
        parts.push('the open design is "' + (((req || {}).intake || {}).prompt_text || d.title || 'the design') + '"');
        parts.push('(request id ' + d.request_id + ', version ' + (d.version || 1) + ' of ' + Math.max(this.cvVersions.length, 1) + ', its state is ' + this.cvState(req).toLowerCase() + ')');
        var showing = this.cvLayers.filter(function(l) { return l.visible; }).map(function(l) { return l.name; });
        if (showing.length) parts.push('layers showing: ' + showing.join(', '));
        var sel = this.cvSelLayers;
        if (sel.length) parts.push('layers picked: ' + sel.map(function(l) { return l.name; }).join(', '));
      }
      return parts.join('; ');
    },
    cvNoteContext() {
      // The standing location record: the agent can read where the
      // artist is even between messages (canvas/context in the same
      // record family the hand works).
      var line = this.cvContextLine();
      if (this._cvCtxLast === line) return;
      this._cvCtxLast = line;
      this.cvKvPut('canvas/context', { where: line, ts: new Date().toISOString() }).catch(function() { /* the message carries it too */ });
    },
    cvStripContext(text) {
      return String(text || '').replace(/^\[Where I am: [^\]]*\]\s*/, '');
    },
    async cvLoadThread() {
      var id = this.cvDesignerId();
      if (!id) { this.cvThread = []; return; }
      var self = this;
      try {
        var data = await OpenFangAPI.get('/api/agents/' + id + '/session');
        var rows = (data.messages || []).filter(function(m) { return m && m.role !== 'System' && m.role !== 'system'; })
          .map(function(m) {
            return { role: m.role === 'User' ? 'user' : 'agent',
                     text: self.cvStripContext(typeof m.content === 'string' ? m.content : '') };
          }).filter(function(r) { return r.text.trim(); });
        this.cvThread = rows.slice(-8);
      } catch (e) { /* the thread just stays as it was */ }
    },
    cvAddFiles(files) {
      var allowed = ['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'text/plain', 'application/pdf',
                     'text/markdown', 'application/json', 'text/csv'];
      var allowedExts = ['.txt', '.pdf', '.md', '.json', '.csv'];
      for (var i = 0; i < files.length; i++) {
        var file = files[i];
        if (file.size > 10 * 1024 * 1024) { OpenFangToast.warn('File "' + file.name + '" exceeds 10MB limit'); continue; }
        var typeOk = allowed.indexOf(file.type) !== -1;
        if (!typeOk) {
          var ext = file.name.lastIndexOf('.') !== -1 ? file.name.substring(file.name.lastIndexOf('.')).toLowerCase() : '';
          typeOk = allowedExts.indexOf(ext) !== -1 || file.type.indexOf('image/') === 0 || file.type.indexOf('video/') === 0;
        }
        if (!typeOk) { OpenFangToast.warn('File type not supported: ' + file.name); continue; }
        this.cvAtts.push({ file: file, preview: file.type.indexOf('image/') === 0 ? URL.createObjectURL(file) : null, uploading: false });
      }
    },
    cvRemoveAtt(i) {
      var att = this.cvAtts[i];
      if (att && att.preview) URL.revokeObjectURL(att.preview);
      this.cvAtts.splice(i, 1);
    },
    async cvSendMsg() {
      var id = this.cvDesignerId();
      var text = (this.cv.msgDraft || '').trim();
      if (!id || (!text && !this.cvAtts.length) || this.cvThreadBusy) return;
      var self = this;
      this.cvThreadBusy = true;
      var uploaded = [], refs = [];
      for (var i = 0; i < this.cvAtts.length; i++) {
        var att = this.cvAtts[i];
        att.uploading = true;
        try {
          var res = await OpenFangAPI.upload(id, att.file);
          refs.push('[File: ' + att.file.name + ']');
          uploaded.push({ file_id: res.file_id, filename: res.filename, content_type: res.content_type });
        } catch (e) { refs.push('[File: ' + att.file.name + ' (upload failed)]'); }
        att.uploading = false;
      }
      this.cvAtts.forEach(function(a) { if (a.preview) URL.revokeObjectURL(a.preview); });
      this.cvAtts = [];
      var finalText = '[Where I am: ' + this.cvContextLine() + ']\n' + text + (refs.length ? (text ? '\n' : '') + refs.join('\n') : '');
      this.cv.msgDraft = '';
      this.cvThread.push({ role: 'user', text: text || refs.join(' ') });
      try {
        var body = { message: finalText };
        if (uploaded.length) body.attachments = uploaded;
        await OpenFangAPI.post('/api/agents/' + id + '/message', body);
      } catch (e) { OpenFangToast.error('That message didn\'t go through — try again.'); }
      this.cvThreadBusy = false;
      await this.cvLoadThread();
      this.loadData(); // the agent's work lands in the same records
    },

    // --- polling + loading ------------------------------------------
    cvArmPoll(fast) {
      if (this._cvPoll) return;
      var self = this, ticks = 0;
      this._cvPoll = setInterval(function() {
        ticks++;
        var pending = self.cvJobs.some(function(j) { return j.status === 'queued'; });
        self.loadData();
        if ((!pending && ticks > 1) || ticks > 24) { clearInterval(self._cvPoll); self._cvPoll = null; }
      }, fast ? 3000 : 5000);
    },

    async loadData() {
      var self = this;
      if (this.$store.app.page !== 'canvas') return;
      try {
        var all = await OpenFangAPI.get('/api/memory/kv');
        var map = {};
        (all.pairs || []).forEach(function(p) { map[p.key] = p.value; });
        this.cvKv = map;
        this.cvSyncArtistDraft();
        var cards = this.cvCards();
        Object.keys(cards).forEach(function(rid) {
          var c = cards[rid];
          if (!self.cv.sel[rid] || !c.versions.some(function(v) { return v.id === self.cv.sel[rid]; })) {
            self.cv.sel[rid] = c.versions[c.versions.length - 1].id;
          }
        });
        if (!this.cv.openId || !this.cvOpen) {
          var list = this.cvCardList;
          if (list.length) {
            var top = list[0], topSel = this.cv.sel[top.req ? top.req.id : ''] || top.versions[top.versions.length - 1].id;
            this.cv.openId = topSel;
            this.cvLoadThread();
          }
        } else if (this.cvOpen) {
          this.cv.sel[this.cvOpen.request_id] = this.cv.openId;
        }
        if (this.cvJobs.some(function(j) { return j.status === 'queued'; })) this.cvArmPoll();
      } catch (e) { /* the last good read stays on screen */ }
    }
  };
}

// Plain words for a job error: keep the core's own honest refusals
// (they're already plain sentences), drop anything mechanism-shaped.
function cvPlainErr(msg) {
  var s = String(msg || '').trim();
  if (!s) return 'Something went wrong.';
  if (/traceback|errno|exception|stack|panic|\.py\b|line \d+/i.test(s)) return 'Something went wrong on our side.';
  return s.replace(/\.$/, '') + '.';
}
