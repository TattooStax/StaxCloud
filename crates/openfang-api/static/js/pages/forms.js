// StaxCloud Forms — Studio module: definitions + submissions in the shared kv
// store (form/<slug>, formsub/<slug>/<uuid>), rendered from real records.
'use strict';

function formsPage() {
  return {
    defs: [],
    subs: [],
    loading: true,
    loadError: '',
    previewSlug: '',
    previewData: {},
    submitting: false,
    submitted: false,
    contactNames: {},
    labelMap: {},

    async loadData() {
      this.loading = true;
      this.loadError = '';
      try {
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        var data = await OpenFangAPI.get('/api/memory/agents/' + agentId + '/kv');
        var pairs = data.kv_pairs || [];
        var defs = [];
        var subs = [];
        var contactNames = {};
        var labelMap = {};
        pairs.forEach(function(pr) {
          if (!pr.key) return;
          var v = pr.value;
          if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { v = null; } }
          if (!v) return;
          if (pr.key.indexOf('contact/') === 0) {
            if (v.name) contactNames[pr.key] = v.name;
          } else if (pr.key.indexOf('formsub/') === 0) {
            subs.push({ key: pr.key, form: v.form || '', uuid: v.uuid || '', ts: v.ts || '', source: v.source || '', test: !!v.test, processed: !!v.processed, contact: v.contact || '', data: v.data || {} });
          } else if (pr.key.indexOf('form/') === 0) {
            (Array.isArray(v.fields) ? v.fields : []).forEach(function(f) {
              if (f && f.key && f.label && !labelMap[f.key]) labelMap[f.key] = f.label;
            });
            if (!v.deleted) defs.push({ slug: pr.key.slice(5), title: v.title || pr.key.slice(5), fields: Array.isArray(v.fields) ? v.fields : [], public_url: v.public_url || '' });
          }
        });
        defs.sort(function(a, b) { return a.title.localeCompare(b.title); });
        subs.sort(function(a, b) { return new Date(b.ts || 0) - new Date(a.ts || 0); });
        this.defs = defs;
        this.subs = subs;
        this.contactNames = contactNames;
        this.labelMap = labelMap;
        Alpine.store('app').formsNewCount = subs.filter(function(s) { return !s.processed; }).length;
        if (!this.previewSlug && defs.length) this.previewSlug = defs[0].slug;
      } catch(e) {
        this.loadError = e.message || 'Could not load forms.';
      }
      this.loading = false;
    },

    get tab() { return Alpine.store('app').formsTab; },

    defOf(slug) {
      return this.defs.find(function(d) { return d.slug === slug; }) || null;
    },

    subsOf(slug) {
      return this.subs.filter(function(s) { return s.form === slug; });
    },

    get previewDef() { return this.defOf(this.previewSlug); },

    fieldLabel(slug, key) {
      var d = this.defOf(slug);
      if (d) {
        var f = d.fields.find(function(x) { return x.key === key; });
        if (f && f.label) return f.label;
      }
      return this.labelMap[key] || staxHumanKey(key);
    },

    // Answers render through the one shared helper (app.js) — the
    // same rows Contacts shows on the person.
    answerRows(s) {
      var d = this.defOf(s.form);
      return staxAnswerRows(s.data, d ? d.fields : [], this.labelMap);
    },

    // The card footer names the person, never their record key;
    // when the pointer does not resolve, the footer stays off.
    contactName(s) {
      if (s.contact && this.contactNames[s.contact]) return this.contactNames[s.contact];
      var e = ((s.data || {}).email || '').toLowerCase();
      if (e && this.contactNames['contact/' + e]) return this.contactNames['contact/' + e];
      return '';
    },

    fmtTs(ts) {
      if (!ts) return '';
      var d = new Date(ts);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    },

    async submitPreview() {
      var def = this.previewDef;
      if (!def || this.submitting) return;
      // Required-field check, plain and local
      for (var i = 0; i < def.fields.length; i++) {
        var f = def.fields[i];
        if (f.required && !(this.previewData[f.key] || '').toString().trim()) {
          OpenFangToast.error('Please fill in: ' + (f.label || f.key));
          return;
        }
      }
      this.submitting = true;
      try {
        var uuid = (crypto.randomUUID ? crypto.randomUUID() : 'test-' + Date.now());
        var rec = {
          form: def.slug,
          uuid: uuid,
          ts: new Date().toISOString(),
          source: 'preview',
          test: true,
          data: Object.assign({}, this.previewData)
        };
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        await OpenFangAPI.put('/api/memory/agents/' + agentId + '/kv/' + encodeURIComponent('formsub/' + def.slug + '/' + uuid), { value: rec });
        this.submitted = true;
        this.previewData = {};
        OpenFangToast.success('Test submission saved — see Submissions');
        await this.loadData();
      } catch(e) {
        OpenFangToast.error(e.message);
      }
      this.submitting = false;
    }
  };
}
