// StaxCloud Contacts (R8) — the studio's people book over kv contact/
// records, in the directory grammar of the product it replaces:
// hairline rows, one search box, cause-specific empty states, and a
// person view that opens on the same card stack.
//
// Wave 2.2 (Contacts parity): one person, one card — records that
// share an identity are merged read-side (nothing is rewritten);
// the person view carries the actions (Message / Call / Edit /
// Archive), counted sections (appointments, projects, messages,
// what they've sent, notes), prep markers for people with design
// work waiting, and a fix-ups alert for records that need attention.
// Sends never leave this surface: Message opens the Texts thread,
// and a first hello is held as a draft for Needs you, on the same
// rails Leads uses.
'use strict';

/*PURE-BEGIN merge*/
// Phone identity: digits only, US country code dropped. Two records
// with the same digits are the same person however they were typed.
function contactDigits(p) {
  var d = String(p || '').replace(/\D/g, '');
  if (d.length === 11 && d.charAt(0) === '1') d = d.slice(1);
  return d;
}

// Read-side dedupe. Records sharing an entity id, a StaxCloud person
// id, an email, or a phone number (transitively) are one person. The
// card the owner sees is the record carrying the most truth — kind
// first, then stage, then an email — with the rest merged behind it:
// every key kept for submission matching, notes unioned, contact
// details unioned, first/last seen widened. No record is written.
function mergePeople(records) {
  var parent = records.map(function(_, i) { return i; });
  function find(i) { while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i]; } return i; }
  function union(a, b) { a = find(a); b = find(b); if (a !== b) parent[b] = a; }
  var claimed = {};
  function claim(tag, i) {
    if (!tag) return;
    if (claimed[tag] === undefined) claimed[tag] = i; else union(claimed[tag], i);
  }
  records.forEach(function(r, i) {
    if (r.entity_id) claim('e:' + r.entity_id, i);
    if (r.staxcloud && r.staxcloud.person_id) claim('p:' + r.staxcloud.person_id, i);
    var em = (r.email || '').trim().toLowerCase();
    if (em) claim('m:' + em, i);
    var dg = contactDigits(r.phone);
    if (dg.length >= 7) claim('t:' + dg, i);
  });
  var groups = {};
  records.forEach(function(r, i) {
    var root = find(i);
    (groups[root] = groups[root] || []).push(r);
  });
  function score(r) {
    var s = 0;
    if (r.kind) s += 8;
    if (r.stage || r.client_state) s += 4;
    if ((r.email || '').trim()) s += 2;
    if ((r.name || '').trim()) s += 1;
    return s;
  }
  function firstSet(rs, field) {
    for (var i = 0; i < rs.length; i++) {
      var v = rs[i][field];
      if (v !== undefined && v !== null && v !== '') return v;
    }
    return '';
  }
  return Object.keys(groups).map(function(root) {
    var rs = groups[root].slice().sort(function(a, b) {
      var d = score(b) - score(a);
      if (d) return d;
      return String(a.key) < String(b.key) ? -1 : 1;
    });
    var w = rs[0];
    var out = {};
    Object.keys(w).forEach(function(k) { out[k] = w[k]; });
    out.raw = w.raw || w;
    out.key = w.key;
    out.keys = rs.map(function(r) { return r.key; });
    out.mergedCount = rs.length;
    out.name = firstSet(rs, 'name');
    out.email = firstSet(rs, 'email');
    out.phone = firstSet(rs, 'phone');
    out.kind = firstSet(rs, 'kind');
    out.stage = firstSet(rs, 'stage');
    out.client_state = firstSet(rs, 'client_state');
    out.artist = firstSet(rs, 'artist');
    out.source_form = firstSet(rs, 'source_form');
    out.entity_id = firstSet(rs, 'entity_id');
    out.piece_idea = firstSet(rs, 'piece_idea');
    if (w.opportunity === undefined) {
      for (var oi = 0; oi < rs.length; oi++) if (rs[oi].opportunity !== undefined) { out.opportunity = rs[oi].opportunity; break; }
    }
    var emails = [], phones = [], artists = [], notes = [];
    rs.forEach(function(r) {
      var em = (r.email || '').trim().toLowerCase();
      if (em && emails.indexOf(em) < 0) emails.push(em);
      var dg = contactDigits(r.phone);
      if (dg.length >= 7 && phones.indexOf(dg) < 0) phones.push(dg);
      var list = Array.isArray(r.artists) ? r.artists.slice() : [];
      if (r.artist && list.indexOf(r.artist) < 0) list.push(r.artist);
      list.forEach(function(a) { if (a && artists.indexOf(a) < 0) artists.push(a); });
      (Array.isArray(r.notes) ? r.notes : []).forEach(function(n) { notes.push(n); });
    });
    notes.sort(function(a, b) { return new Date((a && a.ts) || 0) - new Date((b && b.ts) || 0); });
    out.emails = emails;
    out.phones = phones;
    out.artists = artists;
    out.notes = notes;
    out.first_seen = rs.map(function(r) { return r.first_seen || ''; }).filter(Boolean).sort()[0] || '';
    out.last_seen = rs.map(function(r) { return r.last_seen || ''; }).filter(Boolean).sort().slice(-1)[0] || '';
    out.visits = rs.reduce(function(m, r) { return Math.max(m, r.visits || 0); }, 0);
    out.archived = w.archived === true;
    return out;
  });
}
/*PURE-END merge*/

function contactsPage() {
  return {
    contacts: [],
    subs: [],
    defs: {},
    labelMap: {},
    loading: true,
    loadError: '',
    query: '',
    artistFilter: 'all',
    // The book view lives in the store: the module dock (outside this
    // page's scope) reads and writes the same value.
    get view() { return Alpine.store('app').contactsView; },
    set view(v) { Alpine.store('app').contactsView = v; },
    visibleCount: 60,
    selectedKey: '',
    // Records layout: on a wide screen the list stays beside the open record.
    wide: window.matchMedia('(min-width: 900px)').matches,
    noteText: '',
    savingNote: false,
    showNew: false,
    newName: '',
    newEmail: '',
    newPhone: '',
    newKind: 'Lead',
    newStage: 'New',
    newArtist: '',
    savingNew: false,
    editing: false,
    editForm: {},
    savingEdit: false,
    helloHeld: false,

    // Arriving by the module dock resets the list the way the old
    // in-page view control did, and leaves any open record.
    init() {
      var self = this;
      this._onDockView = function() {
        self.visibleCount = 60;
        self.selectedKey = '';
        self.editing = false;
      };
      window.addEventListener('stax-contacts-view', this._onDockView);
      this._mq = window.matchMedia('(min-width: 900px)');
      this._onMq = function(e) { self.wide = e.matches; };
      this._mq.addEventListener('change', this._onMq);
    },

    destroy() {
      if (this._onDockView) window.removeEventListener('stax-contacts-view', this._onDockView);
      if (this._mq && this._onMq) this._mq.removeEventListener('change', this._onMq);
    },

    async loadData() {
      this.loading = true;
      this.loadError = '';
      try {
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        var data = await OpenFangAPI.get('/api/memory/agents/' + agentId + '/kv');
        var pairs = data.kv_pairs || [];
        var views = [];
        var subs = [];
        var defs = {};
        var labelMap = {};
        var projects = [];
        var threads = {};
        var reqs = [];
        pairs.forEach(function(pr) {
          if (!pr.key) return;
          var v = pr.value;
          if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { v = null; } }
          if (!v) return;
          if (pr.key.indexOf('contact/') === 0) {
            views.push({
              key: pr.key,
              name: v.name || '',
              email: v.email || '',
              phone: v.phone || '',
              kind: v.kind || '',
              stage: v.stage || '',
              client_state: v.client_state || '',
              entity_id: v.entity_id || '',
              staxcloud: v.staxcloud || null,
              opportunity: v.opportunity,
              artist: v.artist || '',
              artists: Array.isArray(v.artists) ? v.artists : [],
              source_form: v.source_form || v.source || '',
              piece_idea: v.piece_idea || '',
              first_seen: v.first_seen || v.date || '',
              last_seen: v.last_seen || '',
              visits: v.visits || 0,
              notes: Array.isArray(v.notes) ? v.notes : [],
              archived: v.archived === true,
              raw: v
            });
          } else if (pr.key.indexOf('formsub/') === 0) {
            subs.push({ key: pr.key, form: v.form || pr.key.split('/')[1] || '', ts: v.ts || '', data: v.data || {}, processed: !!v.processed, contact: v.contact || '' });
          } else if (pr.key.indexOf('form/') === 0) {
            var slug = v.slug || pr.key.slice(5);
            defs[slug] = { title: v.title || slug, fields: Array.isArray(v.fields) ? v.fields : [] };
            (Array.isArray(v.fields) ? v.fields : []).forEach(function(f) {
              if (f && f.key && f.label && !labelMap[f.key]) labelMap[f.key] = f.label;
            });
          } else if (pr.key.indexOf('project/') === 0) {
            var rest = pr.key.slice(8);
            var cut = rest.lastIndexOf('/');
            projects.push({
              key: pr.key,
              contactKey: v.contact || (cut > 0 ? rest.slice(0, cut) : ''),
              title: v.title || 'Tattoo',
              status: v.status || '',
              artist: v.artist || ''
            });
          } else if (pr.key.indexOf('sms/') === 0) {
            var dg = contactDigits(pr.key.slice(4));
            if (dg) threads[dg] = { key: pr.key, count: Array.isArray(v.messages) ? v.messages.length : 0 };
          } else if (pr.key.indexOf('designreq/') === 0 && pr.key !== 'designreq/index') {
            reqs.push({ key: pr.key, status: v.status || '', customer: (v.intake && v.intake.customer_id) || '' });
          }
        });
        subs.sort(function(a, b) { return new Date(b.ts || 0) - new Date(a.ts || 0); });
        // One person, one card: duplicates merge read-side, then the
        // card is decorated with what the rest of the store says
        // about them — open design work (prep), their text thread,
        // their projects, and anything about the record that needs
        // fixing before it misleads someone.
        var people = mergePeople(views);
        var openStates = { received: 1, routed: 1, planned: 1, awaiting_artist: 1 };
        people.forEach(function(p) {
          p._projects = projects.filter(function(pr) { return p.keys.indexOf(pr.contactKey) >= 0; });
          p._thread = null;
          p.phones.forEach(function(d) { if (!p._thread && threads[d]) p._thread = threads[d]; });
          p._prep = reqs.some(function(r) {
            if (!openStates[r.status]) return false;
            var cd = contactDigits(r.customer);
            if (cd && p.phones.indexOf(cd) >= 0) return true;
            return p.phones.some(function(d) { return r.key.indexOf('req-sms-' + d + '-') >= 0; });
          });
          p._issues = [];
          if (!(p.name || '').trim()) p._issues.push('No name on the record');
          if ((p.email || '').trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(p.email.trim())) p._issues.push('Email looks wrong');
          if ((p.phone || '').trim()) {
            var pd = contactDigits(p.phone);
            if (pd.length < 7 || pd.length > 15) p._issues.push('Phone looks wrong');
          }
        });
        people.sort(function(a, b) { return (a.name || '').localeCompare(b.name || ''); });
        this.contacts = people;
        // The module dock's counts are this page's own, mirrored to
        // the store on every load (mutations all end in a reload).
        Alpine.store('app').contactsCounts = { all: this.allCount, today: this.todayCount, prep: this.prepCount, archived: this.archivedCount };
        this.subs = subs;
        this.defs = defs;
        this.labelMap = labelMap;
        // A deep link from another surface (Leads opens the person
        // here) names any of the person's records; consume it once,
        // on arrival, and open the merged card.
        var want = '';
        try { want = Alpine.store('app').contactOpenKey || ''; } catch(e) { want = ''; }
        if (want) {
          try { Alpine.store('app').contactOpenKey = ''; } catch(e) {}
          var target = people.find(function(p) { return p.keys.indexOf(want) >= 0; });
          if (target) {
            this.artistFilter = 'all';
            this.query = '';
            this.view = target.archived ? 'archived' : 'all';
            this.selectedKey = target.key;
          }
        }
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

    // A person's kind, with their stage (leads) or state (clients)
    // after it: "Client · Lapsed client", "Lead · Talking". Records
    // born in Fang carry no kind yet and show nothing.
    kindLabel(c) {
      if (!c || !c.kind) return '';
      var s = c.kind === 'Lead' ? c.stage : (c.kind === 'Client' ? c.client_state : '');
      return (s && s !== c.kind) ? c.kind + ' · ' + s : c.kind;
    },

    // Counts read the book the owner is looking at: the everyday
    // book (archived people rest under Archived), one person once.
    artistCount(a) {
      var archivedView = this.view === 'archived';
      var base = this.contacts.filter(function(c) { return archivedView ? c.archived : !c.archived; });
      if (a === 'all') return base.length;
      return base.filter(function(c) {
        var set = Array.isArray(c.artists) ? c.artists.slice() : [];
        if (c.artist && set.indexOf(c.artist) < 0) set.push(c.artist);
        return set.indexOf(a) >= 0;
      }).length;
    },

    get allCount() { return this.contacts.filter(function(c) { return !c.archived; }).length; },
    get prepCount() { return this.contacts.filter(function(c) { return !c.archived && c._prep; }).length; },
    get archivedCount() { return this.contacts.filter(function(c) { return c.archived; }).length; },

    // Today: people who came in today — first seen, seen again, or sent
    // a form since local midnight.
    isToday(c) {
      var start = new Date(); start.setHours(0, 0, 0, 0);
      function today(ts) { var t = ts ? Date.parse(ts) : NaN; return !isNaN(t) && t >= start.getTime(); }
      if (today(c.last_seen) || today(c.first_seen)) return true;
      return this.subsOf(c).some(function(s) { return today(s.ts); });
    },
    get todayCount() {
      var self = this;
      return this.contacts.filter(function(c) { return !c.archived && self.isToday(c); }).length;
    },

    get flagged() {
      return this.contacts.filter(function(c) { return !c.archived && c._issues && c._issues.length; });
    },

    get filtered() {
      var self = this;
      var view = this.view;
      var list = this.contacts.filter(function(c) {
        if (view === 'archived' ? !c.archived : c.archived) return false;
        if (view === 'prep' && !c._prep) return false;
        if (view === 'today' && !self.isToday(c)) return false;
        return self.matchesArtist(c);
      });
      var q = (this.query || '').trim().toLowerCase();
      if (!q) return list;
      var qd = q.replace(/\D/g, '');
      return list.filter(function(c) {
        if ((c.name || '').toLowerCase().indexOf(q) >= 0) return true;
        if (c.emails.some(function(e) { return e.indexOf(q) >= 0; })) return true;
        if ((c.phone || '').toLowerCase().indexOf(q) >= 0) return true;
        return qd.length >= 3 && c.phones.some(function(d) { return d.indexOf(qd) >= 0; });
      });
    },

    get selected() {
      var k = this.selectedKey;
      return this.contacts.find(function(c) { return c.key === k; }) || null;
    },

    // Density: the directory renders in pages behind "Show more" instead
    // of every row at once.
    get visible() {
      return this.filtered.slice(0, this.visibleCount);
    },

    selectPerson(c) {
      this.selectedKey = c.key;
      this.editing = false;
      this.helloHeld = false;
    },

    openPersonKey(key) {
      var p = this.contacts.find(function(c) { return c.keys.indexOf(key) >= 0; });
      if (p) this.selectPerson(p);
    },

    fixPerson(c) {
      this.selectPerson(c);
      this.startEdit();
    },

    // Returning from the detail restores focus to the row that opened
    // it (V4 acceptance J.8). The row stays in the DOM under x-show, so
    // this is a focus call, not a re-render; scroll is the browser's,
    // nothing moves it.
    closeDetail() {
      var key = this.selectedKey;
      this.selectedKey = '';
      this.editing = false;
      var tick = this.$nextTick || function(cb) { setTimeout(cb, 0); };
      tick(function() {
        var el = document.querySelector('[data-ckey="' + key + '"]');
        if (el) el.focus();
      });
    },

    // The detail view shows where a person came in; records carry form
    // slugs, which are not owner language. Prettify for display only —
    // the record itself is untouched.
    viaLabel(sf) {
      if (!sf) return '';
      if (sf === 'manual') return 'Added by hand';
      var s = String(sf).replace(/-\d+$/, '').replace(/-/g, ' ');
      return s.charAt(0).toUpperCase() + s.slice(1);
    },

    digits(s) { return contactDigits(s); },

    subsOf(c) {
      return this.subs.filter(function(s) {
        // Submissions name their contact directly — and after the
        // merge, any of the person's records can be the one named.
        if (s.contact && c.keys.indexOf(s.contact) >= 0) return true;
        var d = s.data || {};
        var e = (d.email || '').toLowerCase();
        if (e && c.emails.indexOf(e) >= 0) return true;
        var p = contactDigits(d.phone);
        return !!p && c.phones.indexOf(p) >= 0;
      });
    },

    // Answers render through the one shared helper (app.js): labels
    // from the form def, every value as plain language.
    answerRows(s) {
      var def = this.defs[s.form] || {};
      return staxAnswerRows(s.data, def.fields, this.labelMap);
    },

    formTitle(slug) {
      var d = this.defs[slug];
      if (d && d.title) return d.title;
      return (slug || '').replace(/-/g, ' ');
    },

    artistName(c) {
      var names = { shawn: 'Shawn', leni: 'Leni' };
      var list = (c.artists && c.artists.length ? c.artists : (c.artist ? [c.artist] : []))
        .map(function(a) { return names[a] || a; });
      return list.length ? list.join(' · ') : 'Unassigned';
    },

    activeProjects(c) {
      return (c._projects || []).filter(function(p) { return p.status === 'active' || p.status === 'in_progress'; });
    },

    projectLine(c) {
      var act = this.activeProjects(c);
      if (!act.length) return '';
      return act[0].title + (act.length > 1 ? ' +' + (act.length - 1) + ' more' : '');
    },

    // No appointment data lives in this store — the daemon has no
    // calendar or Square read — so the section says only what the
    // person's record carries and points at the schedule's home.
    // It never invents a day or a time.
    apptText(c) {
      if (c.stage === 'Booked') return 'Booked — their appointment is ahead of them. Square holds the day and time.';
      if (c.kind === 'Client') return 'No appointment ahead on their record. Square holds the shop\u2019s schedule.';
      return 'Nothing booked yet. Square holds the shop\u2019s schedule.';
    },

    issuesText(c) { return (c._issues || []).join(' · '); },

    openThread(c) {
      if (!c._thread) return;
      Alpine.store('app').smsOpenKey = c._thread.key;
      window.location.hash = 'sms';
    },

    // First contact with someone who has never texted: hold the
    // intro as a draft on the Texts rails — it waits in Needs you
    // and sends only on the owner's approval, exactly like a reply.
    async sayHello(c) {
      var phone = c.phones.length ? c.phones[0] : contactDigits(c.phone);
      if (!phone || this.helloHeld) return;
      var first = (c.name || '').trim().split(/\s+/)[0];
      var body = 'Hi ' + (first || 'there') + ' — thanks for getting in touch with Fargo Tattoo. What are you thinking of getting done?';
      var uuid = (crypto.randomUUID ? crypto.randomUUID() : 'hello-' + Date.now());
      var rec = {
        kind: 'sms_reply',
        to: phone,
        to_name: c.name || '',
        body: body,
        thread: 'sms/' + phone,
        status: 'held',
        ts: new Date().toISOString()
      };
      try {
        await this.putRecord('draft/' + uuid, rec);
        this.helloHeld = true;
        OpenFangToast.success('Held in Needs you — nothing sends until you approve it');
      } catch(e) {
        OpenFangToast.error(e.message);
      }
    },

    callHref(c) {
      var d = contactDigits(c.phone);
      return 'tel:' + (d.length === 10 ? '+1' + d : (c.phone || ''));
    },

    fmtPhone(p) {
      var d = contactDigits(p);
      if (d.length === 10) return '(' + d.slice(0, 3) + ') ' + d.slice(3, 6) + '-' + d.slice(6);
      return p || '';
    },

    startEdit() {
      var c = this.selected;
      if (!c) return;
      this.editForm = {
        name: c.name || '',
        email: c.email || '',
        phone: c.phone || '',
        kind: c.kind || '',
        stage: c.stage || '',
        artist: c.artist || (c.artists && c.artists[0]) || ''
      };
      this.editing = true;
    },

    // Edits write through the surface's own record path, onto the
    // card's record — the same kv PUT notes and new contacts use.
    async saveEdit() {
      var c = this.selected;
      if (!c || this.savingEdit) return;
      var f = this.editForm;
      if (!(f.name || '').trim()) { OpenFangToast.error('A name is required.'); return; }
      this.savingEdit = true;
      try {
        var rec = Object.assign({}, c.raw);
        rec.name = f.name.trim();
        rec.email = (f.email || '').trim();
        rec.phone = (f.phone || '').trim();
        rec.kind = f.kind || '';
        if (f.kind === 'Lead') { if (f.stage) rec.stage = f.stage; else delete rec.stage; }
        else delete rec.stage;
        rec.artist = f.artist || '';
        rec.artists = f.artist ? [f.artist] : (Array.isArray(rec.artists) ? rec.artists : []);
        await this.putRecord(c.key, rec);
        this.editing = false;
        OpenFangToast.success('Saved');
        await this.loadData();
        this.openPersonKey(c.key);
      } catch(e) {
        OpenFangToast.error(e.message);
      }
      this.savingEdit = false;
    },

    // Archive is a flag on the record and nothing more: the person
    // rests under Archived, one tap brings them back, and their
    // kind and stage — what Leads reads — never change.
    async toggleArchive(c) {
      if (!c) return;
      try {
        var rec = Object.assign({}, c.raw);
        rec.archived = !c.archived;
        await this.putRecord(c.key, rec);
        OpenFangToast.success(c.archived ? 'Back in the book' : 'Archived — find them under Archived any time');
        await this.loadData();
        this.openPersonKey(c.key);
      } catch(e) {
        OpenFangToast.error(e.message);
      }
    },

    exportCsv() {
      function cell(v) { return '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"'; }
      var self = this;
      var lines = [['Name', 'Email', 'Phone', 'Kind', 'Stage', 'Artist', 'First seen', 'Last seen', 'Visits', 'Forms sent'].join(',')];
      this.contacts.filter(function(c) { return !c.archived; }).forEach(function(c) {
        lines.push([
          cell(c.name), cell(c.email), cell(c.phone), cell(c.kind),
          cell(c.kind === 'Lead' ? (c.stage || '') : (c.client_state || '')),
          cell(self.artistName(c)), cell((c.first_seen || '').slice(0, 10)), cell((c.last_seen || '').slice(0, 10)),
          cell(c.visits || 0), cell(self.subsOf(c).length)
        ].join(','));
      });
      var blob = new Blob([lines.join('\n')], { type: 'text/csv' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'contacts.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(function() { URL.revokeObjectURL(a.href); }, 4000);
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
        this.openPersonKey(c.key);
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
        // Kind, stage and artist are written in the same fields the
        // pipeline reads — a lead added by hand is a lead everywhere,
        // Leads included, from the moment it is saved.
        var rec = {
          name: name, email: email, phone: phone,
          source_form: 'manual', first_seen: new Date().toISOString(),
          last_seen: '', visits: 1, notes: [],
          kind: this.newKind || 'Lead'
        };
        if (rec.kind === 'Lead') rec.stage = this.newStage || 'New';
        if (this.newArtist === 'shawn' || this.newArtist === 'leni') {
          rec.artist = this.newArtist;
          rec.artists = [this.newArtist];
        }
        await this.putRecord('contact/' + idKey, rec);
        this.showNew = false;
        this.newName = ''; this.newEmail = ''; this.newPhone = '';
        this.newKind = 'Lead'; this.newStage = 'New'; this.newArtist = '';
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
