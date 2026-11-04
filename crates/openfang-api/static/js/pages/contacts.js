// StaxCloud Contacts — Work surface over the kv contact index (contact/<id>)
// maintained by the Forms hand, plus the submission records those people sent.
'use strict';

function contactsPage() {
  return {
    contacts: [],
    subs: [],
    loading: true,
    loadError: '',
    query: '',
    artistFilter: 'all',
    selectedKey: '',
    noteText: '',
    savingNote: false,
    showNew: false,
    newName: '',
    newEmail: '',
    newPhone: '',
    savingNew: false,

    async loadData() {
      this.loading = true;
      this.loadError = '';
      try {
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        var data = await OpenFangAPI.get('/api/memory/agents/' + agentId + '/kv');
        var pairs = data.kv_pairs || [];
        var contacts = [];
        var subs = [];
        pairs.forEach(function(pr) {
          if (!pr.key) return;
          var v = pr.value;
          if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { v = null; } }
          if (!v) return;
          if (pr.key.indexOf('contact/') === 0) {
            contacts.push({
              key: pr.key,
              name: v.name || '(no name)',
              email: v.email || '',
              phone: v.phone || '',
              entity_id: v.entity_id || '',
              artist: v.artist || '',
              artists: Array.isArray(v.artists) ? v.artists : [],
              source_form: v.source_form || v.source || '',
              first_seen: v.first_seen || v.date || '',
              last_seen: v.last_seen || '',
              visits: v.visits || 0,
              notes: Array.isArray(v.notes) ? v.notes : [],
              raw: v
            });
          } else if (pr.key.indexOf('formsub/') === 0) {
            subs.push({ key: pr.key, form: v.form || '', ts: v.ts || '', data: v.data || {}, processed: !!v.processed });
          }
        });
        contacts.sort(function(a, b) { return a.name.localeCompare(b.name); });
        subs.sort(function(a, b) { return new Date(b.ts || 0) - new Date(a.ts || 0); });
        this.contacts = contacts;
        this.subs = subs;
      } catch(e) {
        this.loadError = e.message || 'Could not load contacts.';
      }
      this.loading = false;
    },

    matchesArtist(c) {
      if (this.artistFilter === 'all') return true;
      var set = Array.isArray(c.artists) ? c.artists.slice() : [];
      if (c.artist && set.indexOf(c.artist) < 0) set.push(c.artist);
      return set.indexOf(this.artistFilter) >= 0;
    },

    artistCount(a) {
      if (a === 'all') return this.contacts.length;
      return this.contacts.filter(function(c) {
        var set = Array.isArray(c.artists) ? c.artists.slice() : [];
        if (c.artist && set.indexOf(c.artist) < 0) set.push(c.artist);
        return set.indexOf(a) >= 0;
      }).length;
    },

    get filtered() {
      var self = this;
      var list = this.contacts.filter(function(c) { return self.matchesArtist(c); });
      var q = (this.query || '').trim().toLowerCase();
      if (!q) return list;
      return list.filter(function(c) {
        return c.name.toLowerCase().indexOf(q) >= 0 || c.email.toLowerCase().indexOf(q) >= 0 || c.phone.indexOf(q) >= 0;
      });
    },

    get selected() {
      var k = this.selectedKey;
      return this.contacts.find(function(c) { return c.key === k; }) || null;
    },

    digits(s) { return (s || '').replace(/\D/g, ''); },

    subsOf(c) {
      var self = this;
      var email = (c.email || '').toLowerCase();
      var phone = this.digits(c.phone);
      return this.subs.filter(function(s) {
        var e = (s.data.email || '').toLowerCase();
        var p = self.digits(s.data.phone);
        return (email && e === email) || (phone && p && p === phone);
      });
    },

    initials(name) {
      return (name || '?').split(/\s+/).map(function(w) { return w.charAt(0); }).join('').slice(0, 2).toUpperCase();
    },

    fmtDate(ts) {
      if (!ts) return '';
      var d = new Date(ts);
      if (isNaN(d.getTime())) return String(ts).slice(0, 10);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    },

    async putRecord(key, value) {
      var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
      await OpenFangAPI.put('/api/memory/agents/' + agentId + '/kv/' + encodeURIComponent(key), { value: value });
    },

    async addNote() {
      var c = this.selected;
      var text = (this.noteText || '').trim();
      if (!c || !text || this.savingNote) return;
      this.savingNote = true;
      try {
        var rec = Object.assign({}, c.raw);
        rec.notes = (Array.isArray(rec.notes) ? rec.notes : []).concat([{ ts: new Date().toISOString(), text: text }]);
        await this.putRecord(c.key, rec);
        this.noteText = '';
        OpenFangToast.success('Note saved');
        await this.loadData();
      } catch(e) {
        OpenFangToast.error(e.message);
      }
      this.savingNote = false;
    },

    async saveNewContact() {
      var name = (this.newName || '').trim();
      var email = (this.newEmail || '').trim();
      var phone = (this.newPhone || '').trim();
      if (!name || (!email && !phone) || this.savingNew) {
        if (!this.savingNew) OpenFangToast.error('A name and an email or phone are needed.');
        return;
      }
      this.savingNew = true;
      try {
        var idKey = email ? email.toLowerCase() : this.digits(phone);
        var rec = {
          name: name, email: email, phone: phone,
          source_form: 'manual', first_seen: new Date().toISOString(),
          last_seen: '', visits: 1, notes: []
        };
        await this.putRecord('contact/' + idKey, rec);
        this.showNew = false;
        this.newName = ''; this.newEmail = ''; this.newPhone = '';
        OpenFangToast.success('Contact saved');
        await this.loadData();
        this.selectedKey = 'contact/' + idKey;
      } catch(e) {
        OpenFangToast.error(e.message);
      }
      this.savingNew = false;
    }
  };
}
