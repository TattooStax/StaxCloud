// StaxCloud Team — the shop's team channel, under Channels.
// One shared channel for the people on the team (Stax, Shawn Lowe,
// Leni Bee). Messages are append-only kv records (teammsg/<ts>-<uuid>)
// in the shared store: the page writes them through the same API the
// Texts page uses, and Stax answers in-channel from its own rounds by
// storing its replies the same way. Authorship is always the real
// author — the page posts as the signed-in owner; Stax's posts are
// Stax's own.
'use strict';

function teamPage() {
  return {
    messages: [],
    loading: true,
    loadError: '',
    draft: '',
    posting: false,

    people: [
      { name: 'Stax', role: 'Your lead' },
      { name: 'Shawn Lowe', role: 'Owner' },
      { name: 'Leni Bee', role: 'Artist' }
    ],

    async loadData() {
      this.loading = true;
      this.loadError = '';
      try {
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        var data = await OpenFangAPI.get('/api/memory/agents/' + agentId + '/kv');
        var msgs = [];
        (data.kv_pairs || []).forEach(function(pr) {
          if (!pr.key || pr.key.indexOf('teammsg/') !== 0) return;
          var v = pr.value;
          if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { v = null; } }
          if (!v || !v.body) return;
          msgs.push({ key: pr.key, author: v.author || '', body: v.body, ts: v.ts || '' });
        });
        msgs.sort(function(a, b) { return new Date(a.ts || 0) - new Date(b.ts || 0); });
        this.messages = msgs.slice(-200);
      } catch(e) {
        this.loadError = e.message || 'Could not load the team channel.';
      }
      this.loading = false;
      this.scrollToNewest();
    },

    // The message list is its own scroll region now; land on the
    // newest message whenever the channel (re)loads or a post lands.
    scrollToNewest() {
      var self = this;
      this.$nextTick(function() {
        var el = self.$refs.teamScroll;
        if (el) el.scrollTop = el.scrollHeight;
      });
    },

    initials(name) {
      if (name === 'Stax') return '';
      return (name || '?').split(/\s+/).map(function(w) { return w.charAt(0); }).join('').slice(0, 2).toUpperCase();
    },

    isStax(m) { return m.author === 'Stax'; },
    isOwn(m) { return m.author === 'Shawn Lowe'; },

    fmtTs(ts) {
      if (!ts) return '';
      var d = new Date(ts);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ' ' +
             d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    },

    async post() {
      var body = (this.draft || '').trim();
      if (!body || this.posting) return;
      this.posting = true;
      try {
        var now = new Date();
        var uuid = (crypto.randomUUID ? crypto.randomUUID() : 'tm-' + Date.now());
        var stamp = now.toISOString().replace(/[-:]/g, '').replace(/\..*/, 'Z');
        var rec = { author: 'Shawn Lowe', body: body, ts: now.toISOString() };
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        await OpenFangAPI.put('/api/memory/agents/' + agentId + '/kv/' +
          encodeURIComponent('teammsg/' + stamp + '-' + uuid.slice(0, 8)), { value: rec });
        this.messages.push({ key: 'teammsg/' + stamp, author: rec.author, body: rec.body, ts: rec.ts });
        this.draft = '';
        this.scrollToNewest();
      } catch(e) {
        OpenFangToast.error(e.message || 'Could not post. Try again.');
      }
      this.posting = false;
    }
  };
}
