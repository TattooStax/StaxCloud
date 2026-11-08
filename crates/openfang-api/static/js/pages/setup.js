// StaxCloud first-run setup — a short conversation, not a settings maze.
// Three plain questions; on finish it writes setup/profile, switches on the
// playbooks that match the stated needs, and posts a "Your crew" board.
// The full helper roster stays available — this only fits the starting crew.
'use strict';

function setupPage() {
  return {
    step: 0,
    business: '',
    needs: [],
    brief: 'morning',
    saving: false,
    done: false,
    profile: null,

    bizOptions: [
      { id: 'tattoo', label: 'Tattoo studio' },
      { id: 'salon', label: 'Salon or barber' },
      { id: 'service', label: 'Another service business' }
    ],
    needOptions: [
      { id: 'forms', label: 'Forms & new-client intake', hand: 'forms', crew: 'Forms' },
      { id: 'texts', label: 'Text messages', hand: 'sms', crew: 'Texts' },
      { id: 'boards', label: 'SEO & getting found', hand: 'surface-builder', crew: 'Surface Builder' },
      { id: 'messages', label: 'Client messages & follow-ups', hand: null, crew: '' },
      { id: 'content', label: 'Social posts & content', hand: null, crew: '' }
    ],

    async loadData() {
      try {
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        var data = await OpenFangAPI.get('/api/memory/agents/' + agentId + '/kv/' + encodeURIComponent('setup/profile'));
        var v = data.value;
        if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { v = null; } }
        if (v && v.business) { this.profile = v; this.done = true; }
      } catch(e) { /* no profile yet — the conversation starts */ }
    },

    toggleNeed(id) {
      var i = this.needs.indexOf(id);
      if (i >= 0) this.needs.splice(i, 1); else this.needs.push(id);
    },

    async finish() {
      if (this.saving) return;
      this.saving = true;
      var self = this;
      try {
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        var profile = {
          business: this.business,
          needs: this.needs.slice(),
          brief: this.brief,
          ts: new Date().toISOString()
        };
        await OpenFangAPI.put('/api/memory/agents/' + agentId + '/kv/' + encodeURIComponent('setup/profile'), { value: profile });

        // Switch on the playbooks that match the stated needs.
        var crewNames = ['Stax (your lead)'];
        for (var i = 0; i < this.needOptions.length; i++) {
          var n = this.needOptions[i];
          if (this.needs.indexOf(n.id) < 0 || !n.hand) continue;
          crewNames.push(n.crew);
          try { await OpenFangAPI.post('/api/hands/' + n.hand + '/activate', {}); } catch(e) { /* already active is fine */ }
        }

        // A board that says what got set up — projected from the real profile.
        var needsLabels = this.needOptions.filter(function(n) { return self.needs.indexOf(n.id) >= 0; }).map(function(n) { return { title: n.label }; });
        var board = {
          title: 'Your crew',
          blocks: [
            { type: 'heading', text: 'Your crew' },
            { type: 'text', text: 'Fitted to what you said you need. The full helper roster is still under Channels — this is just who starts on your team.' },
            { type: 'stats', items: [
              { label: 'Business', value: (this.bizOptions.find(function(b) { return b.id === self.business; }) || {}).label || self.business },
              { label: 'Brief', value: self.brief === 'morning' ? 'Each morning' : (self.brief === 'live' ? 'As things happen' : 'Morning + as it happens') },
              { label: 'On your crew', value: String(crewNames.length) }
            ]},
            { type: 'list', title: 'You asked for help with', items: needsLabels }
          ]
        };
        await OpenFangAPI.put('/api/memory/agents/' + agentId + '/kv/' + encodeURIComponent('surface/crew'), { value: board });

        this.profile = profile;
        this.done = true;
        OpenFangToast.success('Your crew is set');
      } catch(e) {
        OpenFangToast.error(e.message);
      }
      this.saving = false;
    },

    bizLabel(id) {
      var b = this.bizOptions.find(function(x) { return x.id === id; });
      return b ? b.label : id;
    }
  };
}
