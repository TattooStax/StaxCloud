// Leads page — the pipeline surface (Verdict 4 §2).
// Reads contact records from the shared cabinet. A person's kind
// (Client · Lead · Contact-only) is separate from their stage: Leads
// lists the people whose kind is Lead, grouped by stage, plus clients
// with open work cross-listed under Opportunities (their kind does not
// change). Stage and temperature are record fields, set deterministically
// by the import translator or by the sweeps; this page presents them —
// and what a record does not carry, the page says so: a lead with no
// readable stage sits under "No stage yet", and a missing temperature
// shows no chip at all instead of an invented one.
// Every card opens the person in Contacts, and each card carries the
// one next step its stage names, performable from the card itself: a
// first hello, a follow-up, or the booking link is held as a draft in
// Needs you (the Texts pattern — nothing sends from here), and a reply
// owed on a live conversation opens that Texts thread.
// Temperatures: Ready · Interested · Just looking. Lead stages: New ·
// Talking · Waiting on an artist · Booked · Gone quiet · Not a fit.
'use strict';

function leadsPage() {
  var STAGES = ['New', 'Talking', 'Waiting on an artist', 'Booked', 'Gone quiet', 'Not a fit'];
  var TEMPS = ['Ready', 'Interested', 'Just looking'];
  var NO_STAGE = 'No stage yet';
  var BOOKING_LINK = 'https://squareup.com/appointments/book/L7VAHB1TPFGN2/start';

  function artistsOf(c) {
    var set = [];
    if (Array.isArray(c.artists)) {
      c.artists.forEach(function(a) {
        if ((a === 'shawn' || a === 'leni') && set.indexOf(a) < 0) set.push(a);
      });
    }
    if ((c.artist === 'shawn' || c.artist === 'leni') && set.indexOf(c.artist) < 0) set.push(c.artist);
    return set;
  }

  function artistLabel(c) {
    var set = artistsOf(c);
    if (set.length === 2) return 'Shawn + Leni';
    if (set[0] === 'shawn') return 'Shawn';
    if (set[0] === 'leni') return 'Leni';
    return 'Unassigned';
  }

  function digits(s) { return (s || '').replace(/\D/g, ''); }

  function firstName(name) {
    var n = (name || '').trim();
    if (!n || n === '(no name)') return 'there';
    return n.split(/\s+/)[0];
  }

  return {
    leads: [],
    threadKeys: {},
    loading: true,
    error: '',
    // The artist scope lives in the store: the module dock (outside
    // this page's scope) reads and writes the same value.
    get artistFilter() { return Alpine.store('app').leadsArtist; },
    set artistFilter(v) { Alpine.store('app').leadsArtist = v; },
    shownCounts: {},
    stages: ['Opportunities', NO_STAGE].concat(STAGES),
    openStages: { 'Opportunities': true, 'No stage yet': true, 'New': true, 'Talking': true, 'Waiting on an artist': true, 'Booked': true, 'Gone quiet': false, 'Not a fit': false },

    // Arriving by the module dock re-scopes the board; the per-stage
    // "show more" counts reset, as the old in-page control did.
    init() {
      var self = this;
      this._onDockArtist = function() { self.shownCounts = {}; };
      window.addEventListener('stax-leads-artist', this._onDockArtist);
    },

    destroy() {
      if (this._onDockArtist) window.removeEventListener('stax-leads-artist', this._onDockArtist);
    },

    async loadData() {
      this.loading = true;
      this.error = '';
      try {
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        var data = await OpenFangAPI.get('/api/memory/agents/' + agentId + '/kv');
        var pairs = data.kv_pairs || [];
        var out = [];
        var threads = {};
        var i, pr;
        for (i = 0; i < pairs.length; i++) {
          pr = pairs[i];
          if (pr.key && pr.key.indexOf('sms/') === 0) threads[pr.key] = true;
        }
        this.threadKeys = threads;
        for (i = 0; i < pairs.length; i++) {
          pr = pairs[i];
          if (!pr.key || pr.key.indexOf('contact/') !== 0) continue;
          var c = pr.value;
          if (typeof c === 'string') { try { c = JSON.parse(c); } catch (e) { continue; } }
          if (!c || typeof c !== 'object') continue;
          if (!this.isLead(c)) continue;
          c._kvkey = pr.key;
          out.push(this.decorate(c));
        }
        this.leads = out;
        // The module dock's counts are this page's own, mirrored to
        // the store on every load.
        Alpine.store('app').leadsArtistCounts = { all: this.artistCount('all'), shawn: this.artistCount('shawn'), leni: this.artistCount('leni') };
      } catch (e) {
        this.error = 'Leads could not load. Check the connection, then refresh.';
      }
      this.loading = false;
    },

    // A contact belongs to the pipeline when its kind is Lead, or when
    // it carries open work (an opportunity — clients cross-list here
    // without becoming leads). Records with no kind yet (born in Fang,
    // not imported) keep the older rule: a stage, or an arrival through
    // a form, a booking, or an inquiry. The arrival is read from the
    // same fields Contacts writes (source, or source_form where the
    // manual add stamps its provenance), so a lead added by hand in
    // Contacts — which writes its kind — is seen here like any other.
    // Plain directory contacts stay in Contacts only.
    isLead(c) {
      if (c.kind) return c.kind === 'Lead' || c.opportunity === true;
      if (c.stage) return true;
      var src = c.source || c.source_form || '';
      return ['form', 'booking', 'inquiry'].indexOf(src) >= 0;
    },

    // A stage the record does not carry — or carries in words the
    // pipeline does not know — reads as no stage (null here, the
    // "No stage yet" section on the surface), never as 'New'.
    stageOf(c) {
      return STAGES.indexOf(c.stage) >= 0 ? c.stage : null;
    },

    // Same honesty for temperature: unknown or missing reads as no
    // temperature, and the card shows no chip — never 'Just looking'.
    tempOf(c) {
      return TEMPS.indexOf(c.temperature) >= 0 ? c.temperature : null;
    },

    artistsOf: artistsOf,
    artistLabel: artistLabel,

    matchesArtist(c) {
      if (this.artistFilter === 'all') return true;
      return artistsOf(c).indexOf(this.artistFilter) >= 0;
    },

    lastLabel(c) {
      if (!c.last_seen) return '';
      var d = new Date(c.last_seen);
      if (isNaN(d.getTime())) return '';
      var opts = { month: 'short', day: 'numeric' };
      if (d.getFullYear() !== new Date().getFullYear()) opts.year = 'numeric';
      return d.toLocaleDateString('en-US', opts);
    },

    nextAction(stage, temp, c) {
      var reachable = !!(digits(c.phone) || (c.email || '').trim());
      switch (stage) {
        case 'New':
          return reachable
            ? 'Say hello — the first reply is still owed.'
            : 'No phone or email on the record — open it to see what we have.';
        case 'Talking':
          if (temp === 'Ready') return 'They asked to book — send the booking link.';
          if (temp === 'Interested') return 'Keep it warm — a reply is due today.';
          if (temp === 'Just looking') return 'Answer their question, share the booking link, then let it rest.';
          return 'A reply is due — pick the conversation back up.';
        case 'Waiting on an artist': {
          var who = artistLabel(c);
          return who === 'Unassigned'
            ? 'Waiting on an artist — no one has picked it up yet.'
            : 'Waiting on ' + who + ' — their call; the record has the details.';
        }
        case 'Booked': return 'Booked — their appointment is ahead of them; nothing owed right now.';
        case 'Gone quiet': return 'Went quiet — it re-opens on its own if they write.';
        case 'Not a fit': return 'Not a fit — kept on the record, nothing owed.';
        case 'Opportunities': return 'Work is open on a new piece.';
        case NO_STAGE: return 'No stage on their record yet — open it to see where they stand.';
        default: return '';
      }
    },

    // The one primary action a card offers, named by its stage. Draft
    // actions (hello / follow-up / booking link) hold a message in
    // Needs you; 'reply' opens the live Texts thread when one exists
    // and falls back to a held follow-up when it does not; 'open' is
    // the person's record, for stages where the next move is a look,
    // not a message, and for people no channel can reach.
    actionFor(stage, temp, c) {
      var phone = digits(c.phone);
      var email = (c.email || '').trim();
      var reachable = !!(phone || email);
      var hasThread = !!(phone && this.threadKeys['sms/' + phone]);
      switch (stage) {
        case 'New':
          return reachable ? { id: 'hello', label: 'Say hello' } : { id: 'open', label: 'Open their record' };
        case 'Talking':
          if (temp === 'Ready' || temp === 'Just looking') {
            return reachable ? { id: 'book', label: 'Send the booking link' } : { id: 'open', label: 'Open their record' };
          }
          if (hasThread) return { id: 'reply', label: 'Reply' };
          return reachable ? { id: 'followup', label: 'Reply' } : { id: 'open', label: 'Open their record' };
        default:
          return { id: 'open', label: 'Open their record' };
      }
    },

    decorate(c) {
      var stage = (c.opportunity === true && c.kind === 'Client')
        ? 'Opportunities' : this.stageOf(c);
      var temp = this.tempOf(c);
      var out = {};
      for (var k in c) out[k] = c[k];
      out._key = c._kvkey || c.email || c.phone || c.name || '';
      out._stage = stage === null ? NO_STAGE : stage;
      out._temp = temp;
      out._idea = (typeof c.piece_idea === 'string' && c.piece_idea.trim()) ? c.piece_idea.trim() : '';
      out._artistLabel = artistLabel(c);
      out._lastLabel = this.lastLabel(c);
      out._next = this.nextAction(out._stage, temp, c);
      out._action = this.actionFor(out._stage, temp, c);
      out._seen = c.last_seen || '';
      out._holding = false;
      out._held = false;
      return out;
    },

    openPerson(l) {
      if (!l || !l._kvkey) return;
      Alpine.store('app').contactOpenKey = l._kvkey;
      window.location.hash = 'contacts';
    },

    openThread(l) {
      var phone = digits(l.phone);
      if (!phone) return;
      Alpine.store('app').smsOpenKey = 'sms/' + phone;
      window.location.hash = 'sms';
    },

    draftBody(which, l) {
      var hi = 'Hi ' + firstName(l.name) + ' — ';
      if (which === 'book') return hi + 'you can book here when you are ready: ' + BOOKING_LINK;
      if (which === 'followup') return hi + 'following up from Fargo Tattoo. Anything I can answer about your piece?';
      return hi + 'thanks for getting in touch with Fargo Tattoo. What are you thinking of getting done?';
    },

    // Hold the card's message as a draft in Needs you — the Texts
    // pattern, record shape and all: an sms_reply to their number, or
    // an email_send when the record has no phone. Approval stays the
    // owner's, in Needs you; nothing sends from this surface.
    async holdDraft(l, which) {
      var phone = digits(l.phone);
      var email = (l.email || '').trim();
      var body = this.draftBody(which, l);
      var uuid = (crypto.randomUUID ? crypto.randomUUID() : 'lead-' + Date.now());
      var rec;
      if (phone) {
        rec = {
          kind: 'sms_reply',
          to: phone,
          to_name: l.name || '',
          body: body,
          thread: 'sms/' + phone,
          status: 'held',
          ts: new Date().toISOString()
        };
      } else if (email) {
        rec = {
          kind: 'email_send',
          to: email,
          to_name: email,
          subject: which === 'book' ? 'Booking your tattoo' : 'Fargo Tattoo',
          body: body,
          text: body,
          form: 'email',
          status: 'held',
          ts: new Date().toISOString(),
          in_reply_to: '',
          references: ''
        };
      } else {
        return false;
      }
      var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
      await OpenFangAPI.put('/api/memory/agents/' + agentId + '/kv/' + encodeURIComponent('draft/' + uuid), { value: rec });
      return true;
    },

    async runAction(l) {
      var a = l && l._action;
      if (!a || l._holding || l._held) return;
      if (a.id === 'open') { this.openPerson(l); return; }
      if (a.id === 'reply') { this.openThread(l); return; }
      l._holding = true;
      try {
        var held = await this.holdDraft(l, a.id);
        if (held) {
          l._held = true;
          OpenFangToast.success('Held — it is waiting in Needs you');
        } else {
          OpenFangToast.error('No way to reach them — open their record to check.');
        }
      } catch (e) {
        OpenFangToast.error(e.message || 'Could not hold the message. Try again.');
      }
      l._holding = false;
    },

    // Density: a section shows the first PAGE cards; the rest wait behind
    // the section's "Show more". Keyed by stage name only — whatever
    // categories the records carry, the cap behaves the same.
    shownCount(stage) {
      return this.shownCounts[stage] || 10;
    },

    moreCount(stage) {
      return Math.max(0, this.stageCount(stage) - this.shownCount(stage));
    },

    showMore(stage) {
      this.shownCounts[stage] = this.shownCount(stage) + 10;
    },

    byStage(stage) {
      var self = this;
      return this.leads
        .filter(function(l) { return l._stage === stage && self.matchesArtist(l); })
        .sort(function(a, b) { return (b._seen || '').localeCompare(a._seen || ''); })
        .slice(0, this.shownCount(stage));
    },

    stageCount(stage) {
      var self = this;
      return this.leads.filter(function(l) { return l._stage === stage && self.matchesArtist(l); }).length;
    },

    artistCount(a) {
      if (a === 'all') return this.leads.length;
      return this.leads.filter(function(l) { return artistsOf(l).indexOf(a) >= 0; }).length;
    },

    // Every count on this line describes the same set — the people in
    // the pipeline — so the arithmetic reads as written: total people,
    // split by kind, then the same people counted per artist (a person
    // with both artists counts under each, as the filter does).
    summaryLine() {
      var clients = this.leads.filter(function(l) { return l.kind === 'Client'; }).length;
      var n = this.leads.length - clients;
      var s = this.leads.length + (this.leads.length === 1 ? ' person: ' : ' people: ')
        + n + (n === 1 ? ' lead' : ' leads');
      if (clients) s += ' + ' + clients + (clients === 1 ? ' client with work open' : ' clients with work open');
      return s
        + ' · ' + this.artistCount('shawn') + ' with Shawn'
        + ' · ' + this.artistCount('leni') + ' with Leni';
    }
  };
}
