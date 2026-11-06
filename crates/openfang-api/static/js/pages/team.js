// StaxCloud Team — the shop's team conversations, under Channels.
// The surface is a conversation list — Everyone, one conversation
// per teammate, and named group conversations — and you post into
// the conversation you opened; a message is a kv record
// (teammsg/<ts>-<uuid>) carrying the conversation id in its `conv`
// field (absent means Everyone, which is how the records written
// before conversations read). Named groups carry a record of their
// own (teamconv/<id>: name + members); 1:1 ids are derived from the
// member pair, never stored. The people list is a kv record too
// (people/roster), seeded with the shop's trio the first time the
// page finds it missing. Conversations here are organization, not
// confidentiality: everyone on the shared login sees every
// conversation, and the surface says so. Authorship is always the
// real author — the page posts as the signed-in owner; Stax's posts
// are Stax's own, and Stax is a member of Everyone only.
'use strict';

function teamPage() {
  return staxWithConversationView({
    people: [],
    groups: [],
    byConv: {},
    view: 'list',
    currentConv: '',
    loading: true,
    loadError: '',
    showCreate: false,
    creating: false,
    newName: '',
    newMembers: [],
    seen: {},

    // The one authenticated identity the app has: the owner session.
    viewer: 'Shawn Lowe',

    agentId() {
      return (Alpine.store('app').agents[0] || {}).id || 'shared';
    },

    async loadData() {
      this.loading = true;
      this.loadError = '';
      try {
        var data = await OpenFangAPI.get('/api/memory/agents/' + this.agentId() + '/kv');
        var roster = null, groups = [], msgs = [];
        (data.kv_pairs || []).forEach(function(pr) {
          if (!pr.key) return;
          var v = pr.value;
          if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { v = null; } }
          if (!v) return;
          if (pr.key === 'people/roster' && Array.isArray(v.people)) {
            roster = v.people;
          } else if (pr.key.indexOf('teamconv/') === 0) {
            if (v.name) groups.push({ id: v.id || pr.key.slice(9), name: v.name, members: Array.isArray(v.members) ? v.members : [], ts: v.ts || '' });
          } else if (pr.key.indexOf('teammsg/') === 0) {
            if (v.body) msgs.push({ key: pr.key, author: v.author || '', body: v.body, ts: v.ts || '', conv: convOf(v) });
          }
        });
        if (!roster || !roster.length) {
          roster = [
            { name: 'Stax', role: 'Your lead' },
            { name: 'Shawn Lowe', role: 'Owner' },
            { name: 'Leni Bee', role: 'Artist' }
          ];
          try {
            await OpenFangAPI.put('/api/memory/agents/' + this.agentId() + '/kv/' +
              encodeURIComponent('people/roster'), { value: { people: roster } });
          } catch(e) { /* the page still works from the seed in memory */ }
        }
        this.people = roster.filter(function(p) { return p && p.name; });
        this.groups = groups;
        msgs.sort(function(a, b) { return new Date(a.ts || 0) - new Date(b.ts || 0); });
        var known = convAllPairIds(this.people);
        known[CONV_EVERYONE] = true;
        groups.forEach(function(g) { known[g.id] = true; });
        this.byConv = groupByConv(msgs, known);
        this.seen = this.loadSeen();
      } catch(e) {
        this.loadError = e.message || 'Could not load the team channel.';
      }
      this.loading = false;
      if (this.view === 'conv') this.convScrollToNewest();
    },

    loadSeen() {
      try { return JSON.parse(localStorage.getItem('stax.team.seen.v1') || '{}') || {}; }
      catch(e) { return {}; }
    },

    markSeen(id) {
      var ms = this.byConv[id] || [];
      this.seen[id] = ms.length ? ms[ms.length - 1].ts : new Date().toISOString();
      try { localStorage.setItem('stax.team.seen.v1', JSON.stringify(this.seen)); } catch(e) {}
    },

    convList() {
      var self = this;
      var mk = function(id, kind, title, members) {
        var ms = self.byConv[id] || [];
        var last = ms.length ? ms[ms.length - 1] : null;
        return {
          id: id, kind: kind, title: title, members: members || [],
          lastTs: last ? last.ts : '',
          snippet: last ? last.body : 'No messages yet',
          hasNew: !!(last && last.author !== self.viewer && (self.seen[id] || '') < last.ts)
        };
      };
      var out = [mk(CONV_EVERYONE, 'all', 'Everyone', this.people.map(function(p) { return p.name; }))];
      var pairs = convPairIdsFor(this.people, this.viewer);
      this.people.forEach(function(p) {
        if (pairs[p.name]) out.push(mk(pairs[p.name], 'dm', p.name, [self.viewer, p.name]));
      });
      this.groups
        .filter(function(g) { return g.members.indexOf(self.viewer) >= 0; })
        .forEach(function(g) { out.push(mk(g.id, 'group', g.name, g.members)); });
      return out;
    },

    currentEntry() {
      var id = this.currentConv;
      var list = this.convList();
      for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
      return { id: id, title: 'Everyone', members: [] };
    },

    currentTitle() { return this.currentEntry().title; },

    currentMembersLine() { return this.currentEntry().members.join(', '); },

    currentMessages() { return this.byConv[this.currentConv] || []; },

    openConv(id) {
      this.currentConv = id;
      this.view = 'conv';
      this.markSeen(id);
      this.convScrollToNewest();
    },

    backToList() { this.view = 'list'; },

    // The conversation view's send handler (see conversation.js):
    // Team is internal, so a post writes the team record directly
    // and appears at once.
    async onDraft(body) {
      var now = new Date();
      var uuid = (crypto.randomUUID ? crypto.randomUUID() : 'tm-' + Date.now());
      var stamp = now.toISOString().replace(/[-:]/g, '').replace(/\..*/, 'Z');
      var conv = this.currentConv || CONV_EVERYONE;
      var rec = { author: this.viewer, body: body, ts: now.toISOString(), conv: conv };
      var key = 'teammsg/' + stamp + '-' + uuid.slice(0, 8);
      await OpenFangAPI.put('/api/memory/agents/' + this.agentId() + '/kv/' +
        encodeURIComponent(key), { value: rec });
      var arr = this.byConv[conv] || (this.byConv[conv] = []);
      arr.push({ key: key, author: rec.author, body: rec.body, ts: rec.ts, conv: conv });
      this.markSeen(conv);
    },

    async createGroup() {
      var name = (this.newName || '').trim();
      if (!name || this.creating) return;
      this.creating = true;
      try {
        var members = [this.viewer];
        this.newMembers.forEach(function(n) { if (members.indexOf(n) < 0) members.push(n); });
        var now = new Date();
        var uuid = (crypto.randomUUID ? crypto.randomUUID() : 'grp-' + Date.now());
        var stamp = now.toISOString().replace(/[-:]/g, '').replace(/\..*/, 'Z');
        var id = 'grp:' + stamp + '-' + uuid.slice(0, 8);
        var rec = { id: id, name: name, members: members, ts: now.toISOString() };
        await OpenFangAPI.put('/api/memory/agents/' + this.agentId() + '/kv/' +
          encodeURIComponent('teamconv/' + id), { value: rec });
        this.groups.push({ id: id, name: name, members: members, ts: rec.ts });
        this.newName = '';
        this.newMembers = [];
        this.showCreate = false;
        this.openConv(id);
      } catch(e) {
        OpenFangToast.error(e.message || 'Could not start the conversation. Try again.');
      }
      this.creating = false;
    },

    initials(name) {
      if (name === 'Stax') return '';
      return (name || '?').split(/\s+/).map(function(w) { return w.charAt(0); }).join('').slice(0, 2).toUpperCase();
    },

    isOwn(m) { return m.author === this.viewer; },

    fmtTs(ts) {
      if (!ts) return '';
      var d = new Date(ts);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ' ' +
             d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    }
  });
}
