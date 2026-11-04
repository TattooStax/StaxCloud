// Leads page — the pipeline surface (Verdict 4 §2).
// Reads contact records from the shared cabinet and groups them by stage.
// Stage and temperature are record fields, set deterministically by the
// import translator or by the sweeps; this page only presents them.
// Temperatures: Ready · Interested · Just looking. Stages: New · Talking ·
// Waiting on an artist · Booked · Resting. (Not a fit is a quiet terminal
// record state and is never shown as a column.)
'use strict';

function leadsPage() {
  var STAGES = ['New', 'Talking', 'Waiting on an artist', 'Booked', 'Resting'];
  var TEMPS = ['Ready', 'Interested', 'Just looking'];

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

  return {
    leads: [],
    loading: true,
    error: '',
    artistFilter: 'all',
    stages: STAGES,
    openStages: { 'New': true, 'Talking': true, 'Waiting on an artist': true, 'Booked': true, 'Resting': false },

    async loadData() {
      this.loading = true;
      this.error = '';
      try {
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        var data = await OpenFangAPI.get('/api/memory/agents/' + agentId + '/kv');
        var pairs = data.kv_pairs || [];
        var out = [];
        for (var i = 0; i < pairs.length; i++) {
          var pr = pairs[i];
          if (!pr.key || pr.key.indexOf('contact/') !== 0) continue;
          var c = pr.value;
          if (typeof c === 'string') { try { c = JSON.parse(c); } catch (e) { continue; } }
          if (!c || typeof c !== 'object') continue;
          if (!this.isLead(c)) continue;
          out.push(this.decorate(c));
        }
        this.leads = out;
      } catch (e) {
        this.error = 'Leads could not load. Check the connection, then refresh.';
      }
      this.loading = false;
    },

    // A contact belongs to the pipeline when it carries a stage, or it
    // arrived through a form, a booking, or an inquiry, or it came in
    // with the StaxCloud import. Plain directory contacts (added by
    // hand, or born from a text thread) stay in Contacts only.
    isLead(c) {
      if (c.stage) return true;
      if (c.staxcloud) return true;
      return ['form', 'booking', 'inquiry'].indexOf(c.source) >= 0;
    },

    stageOf(c) {
      return STAGES.indexOf(c.stage) >= 0 ? c.stage : 'New';
    },

    tempOf(c) {
      return TEMPS.indexOf(c.temperature) >= 0 ? c.temperature : 'Just looking';
    },

    artistsOf: artistsOf,
    artistLabel: artistLabel,

    matchesArtist(c) {
      if (this.artistFilter === 'all') return true;
      return artistsOf(c).indexOf(this.artistFilter) >= 0;
    },

    lastLabel(c) {
      if (!c.last_seen) return 'no contact yet';
      var d = new Date(c.last_seen);
      if (isNaN(d.getTime())) return 'no contact yet';
      var opts = { month: 'short', day: 'numeric' };
      if (d.getFullYear() !== new Date().getFullYear()) opts.year = 'numeric';
      return d.toLocaleDateString('en-US', opts);
    },

    nextAction(stage, temp, c) {
      switch (stage) {
        case 'New': return 'Say hello — the first reply is still owed.';
        case 'Talking':
          if (temp === 'Ready') return 'They asked to book — send the booking link.';
          if (temp === 'Interested') return 'Keep it warm — a reply is due today.';
          return 'Answer their question, share the booking link, then let it rest.';
        case 'Waiting on an artist': {
          var who = artistLabel(c);
          return (who === 'Unassigned' ? 'Waiting on an artist' : 'Waiting on ' + who) + ' — their call.';
        }
        case 'Booked': return 'Work underway — nothing owed right now.';
        case 'Resting': return 'Resting — it re-opens on its own if they write.';
        default: return '';
      }
    },

    decorate(c) {
      var stage = this.stageOf(c);
      var temp = this.tempOf(c);
      var out = {};
      for (var k in c) out[k] = c[k];
      out._key = c.email || c.phone || c.name || '';
      out._stage = stage;
      out._temp = temp;
      out._idea = (typeof c.piece_idea === 'string' && c.piece_idea.trim()) ? c.piece_idea.trim() : '';
      out._artistLabel = artistLabel(c);
      out._lastLabel = this.lastLabel(c);
      out._next = this.nextAction(stage, temp, c);
      out._seen = c.last_seen || '';
      return out;
    },

    byStage(stage) {
      var self = this;
      return this.leads
        .filter(function(l) { return l._stage === stage && self.matchesArtist(l); })
        .sort(function(a, b) { return (b._seen || '').localeCompare(a._seen || ''); });
    },

    stageCount(stage) {
      var self = this;
      return this.leads.filter(function(l) { return l._stage === stage && self.matchesArtist(l); }).length;
    },

    artistCount(a) {
      if (a === 'all') return this.leads.length;
      return this.leads.filter(function(l) { return artistsOf(l).indexOf(a) >= 0; }).length;
    },

    summaryLine() {
      return this.leads.length + (this.leads.length === 1 ? ' lead' : ' leads')
        + ' · ' + this.artistCount('shawn') + ' with Shawn'
        + ' · ' + this.artistCount('leni') + ' with Leni';
    }
  };
}
