// StaxCloud Websites — Studio module: the shop's websites, from the
// site/<slug> records the publisher (sitepub.py) owns. The record's
// status is the ONLY status source (draft | published) — this page
// keeps no side state about a site. Publishing is a job: the page
// writes a sitejob/ record (publish | unpublish | preview) and the
// worker does the rest; the page then reads the outcome back from
// the job record and from the site record itself. The tier caps are
// the publisher's code constants — mirrored here ONLY to phrase the
// "N of M published" line; the publish-time check itself lives in
// the worker, never here.
// W-4 (Consult 16): the record also carries the custom-domain
// state (domain_state) and the rate-limit tri-state fact
// (ratelimits), both shown VERBATIM — the page derives only
// the empty-record defaults, the same ones the worker uses
// (unattached / none).
'use strict';

var SITE_TIER_CAPS = { tier1: 2, tier2: 5, pro: 7 };
var SITE_TIER_WORDS = { tier1: 'tier 1', tier2: 'tier 2', pro: 'the Pro plan' };

function websitesPage() {
  return {
    sites: [],
    plan: null,
    jobs: [],
    loading: true,
    loadError: '',
    busySlug: '',
    previewSlug: '',
    previewHtml: '',
    previewBusy: false,
    previewNote: '',

    agentId() {
      return (Alpine.store('app').agents[0] || {}).id || 'shared';
    },

    async kvAll() {
      var data = await OpenFangAPI.get('/api/memory/agents/' + this.agentId() + '/kv');
      return (data && data.kv_pairs) || [];
    },

    parse(v) {
      if (typeof v === 'string') { try { return JSON.parse(v); } catch (e) { return null; } }
      return (v && typeof v === 'object') ? v : null;
    },

    async loadData() {
      this.loading = true;
      this.loadError = '';
      try {
        var pairs = await this.kvAll();
        var sites = [], jobs = [], plan = null, refusals = {};
        var self = this;
        pairs.forEach(function(pr) {
          if (!pr.key) return;
          var v = self.parse(pr.value);
          if (!v) return;
          if (pr.key.indexOf('site/') === 0) {
            sites.push({
              key: pr.key,
              slug: v.slug || pr.key.slice(5),
              title: v.title || v.slug || pr.key.slice(5),
              status: v.status === 'published' ? 'published' : 'draft',
              url: v.url || '',
              domain: v.domain || '',
              domainState: v.domain_state || 'unattached',
              ratelimits: (typeof v.ratelimits === 'string' && v.ratelimits) ? v.ratelimits : 'none',
              fileCount: Array.isArray(v.files) ? v.files.length : 0,
              updated: v.updated || v.created || ''
            });
          } else if (pr.key === 'plan/current') {
            plan = v;
          } else if (pr.key.indexOf('sitejob/') === 0) {
            jobs.push({
              key: pr.key,
              job_id: v.job_id || pr.key.slice(8),
              op: v.op || '',
              site: v.site || '',
              status: v.status || '',
              error: v.error || '',
              refusal: (v.refusal && typeof v.refusal === 'object') ? v.refusal : null,
              finished: v.finished || '',
              started: v.started || ''
            });
          } else if (pr.key.indexOf('draft/site-publish-') === 0 &&
                     v.kind === 'site_publish_refusal') {
            // The standing refusal reason for a site, written by the
            // publisher when a publish was refused. Read-only here.
            refusals[v.site || pr.key.slice(18)] = v.text || '';
          }
        });
        sites.sort(function(a, b) { return a.title.localeCompare(b.title); });
        jobs.sort(function(a, b) {
          return new Date(b.finished || b.started || 0) - new Date(a.finished || a.started || 0);
        });
        sites.forEach(function(s) { s.refusalText = refusals[s.slug] || ''; });
        this.sites = sites;
        this.jobs = jobs;
        this.plan = plan;
        if (this.previewSlug && !sites.some(function(s) { return s.slug === self.previewSlug; })) {
          this.previewSlug = '';
          this.previewHtml = '';
        }
        if (!this.previewSlug && sites.length) this.previewSlug = sites[0].slug;
      } catch (e) {
        this.loadError = e.message || 'Could not load your websites.';
      }
      this.loading = false;
    },

    get tab() { return Alpine.store('app').websitesTab; },

    get publishedCount() {
      return this.sites.filter(function(s) { return s.status === 'published'; }).length;
    },

    get tier() { return (this.plan && this.plan.tier) || ''; },

    get cap() {
      var c = SITE_TIER_CAPS[this.tier];
      return (typeof c === 'number') ? c : 0;
    },

    get tierWord() { return SITE_TIER_WORDS[this.tier] || 'your plan'; },

    // "1 of 2 published on tier 1" — read from plan/current + the
    // site records, the same inputs the publisher counts.
    get countLine() {
      if (!this.plan) return 'Publishing plan is not set yet — ask Stax.';
      return this.publishedCount + ' of ' + this.cap + ' published on ' + this.tierWord;
    },

    siteOf(slug) {
      return this.sites.find(function(s) { return s.slug === slug; }) || null;
    },

    // The newest job for a site, any op — how the surface learns
    // what the worker last did with it.
    lastJob(slug) {
      return this.jobs.find(function(j) { return j.site === slug; }) || null;
    },

    pendingJob(slug) {
      return this.jobs.find(function(j) {
        return j.site === slug && (j.status === 'queued' || j.status === 'running');
      }) || null;
    },

    // The refusal to show for a site: the newest refused job's plain
    // message wins; the standing refusal record is the fallback.
    refusalFor(s) {
      var j = this.jobs.find(function(x) {
        return x.site === s.slug && x.refusal && x.refusal.message;
      });
      if (j) return j.refusal.message;
      return s.refusalText || '';
    },

    stateWord(s) {
      if (this.pendingJob(s.slug)) return 'Working…';
      return s.status === 'published' ? 'Live' : 'Draft';
    },

    async queueJob(op, s) {
      var id = 'job-' + op + '-' + s.slug + '-' + Date.now().toString(36) +
               Math.floor(Math.random() * 1296).toString(36);
      var rec = {
        job_id: id,
        op: op,
        site: s.slug,
        status: 'queued',
        queued: new Date().toISOString(),
        queued_by: 'websites surface'
      };
      await OpenFangAPI.put('/api/memory/agents/' + this.agentId() + '/kv/' +
        encodeURIComponent('sitejob/' + id), { value: rec });
      return id;
    },

    async publishSite(s) {
      if (this.busySlug) return;
      this.busySlug = s.slug;
      try {
        await this.queueJob('publish', s);
        OpenFangToast.success(s.status === 'published'
          ? 'Republishing “' + s.title + '” — refreshing now'
          : 'Publishing “' + s.title + '” — it goes live in a moment');
        await this.loadData();
      } catch (e) {
        OpenFangToast.error(e.message || 'Could not start publishing. Try again.');
      }
      this.busySlug = '';
    },

    unpublishSite(s) {
      if (this.busySlug) return;
      var self = this;
      OpenFangToast.confirm('Take “' + s.title + '” offline?',
        'The site comes down and frees its publishing slot. The draft stays here, so you can publish it again any time.',
        async function() {
          self.busySlug = s.slug;
          try {
            await self.queueJob('unpublish', s);
            OpenFangToast.success('Taking “' + s.title + '” offline');
            await self.loadData();
          } catch (e) {
            OpenFangToast.error(e.message || 'Could not take the site offline. Try again.');
          }
          self.busySlug = '';
        });
    },

    async showPreview(s) {
      Alpine.store('app').websitesTab = 'preview';
      this.previewSlug = s.slug;
      await this.loadPreview();
    },

    // Preview = a preview job through the same queue the publisher
    // drains; the rendered page comes back on the job record. The
    // page polls the job briefly, then reads whatever state it is
    // in — a preview that has not landed says so, it never spins
    // forever.
    async loadPreview() {
      var s = this.siteOf(this.previewSlug);
      if (!s || this.previewBusy) return;
      this.previewBusy = true;
      this.previewHtml = '';
      this.previewNote = '';
      try {
        var id = await this.queueJob('preview', s);
        var html = '';
        for (var i = 0; i < 10 && !html; i++) {
          await new Promise(function(r) { setTimeout(r, 3000); });
          var pairs = await this.kvAll();
          for (var k = 0; k < pairs.length; k++) {
            if (pairs[k].key !== 'sitejob/' + id) continue;
            var v = this.parse(pairs[k].value);
            if (v && v.status === 'done' && v.result && v.result.preview_html) {
              html = v.result.preview_html;
            } else if (v && v.status === 'error') {
              this.previewNote = 'The preview could not be made: ' + (v.error || 'something went wrong.');
            }
          }
        }
        if (html) {
          this.previewHtml = html;
        } else if (!this.previewNote) {
          this.previewNote = 'The preview is still being made — tap Preview again in a few seconds.';
        }
        // Keep the list state honest alongside the preview read.
        await this.loadData();
        Alpine.store('app').websitesTab = 'preview';
      } catch (e) {
        this.previewNote = e.message || 'Could not load the preview.';
      }
      this.previewBusy = false;
    }
  };
}
