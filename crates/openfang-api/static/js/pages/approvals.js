// StaxCloud Work — Needs you (decisions), Current work, Finished.
// One count source: the header badge reads the shell store's
// pendingApprovalCount, the same number Home and the floating pill
// show. This page's own fetch feeds the lists only.
'use strict';

function approvalsPage() {
  return {
    approvals: [],
    jobs: [],
    loading: true,
    loadError: '',
    refreshTimer: null,
    expandedId: '',
    showCurrent: false,
    showFinished: false,

    init() {
      var self = this;
      this.loadData();
      this.refreshTimer = setInterval(function() {
        self.loadData();
      }, 5000);
    },

    destroy() {
      if (this.refreshTimer) {
        clearInterval(this.refreshTimer);
        this.refreshTimer = null;
      }
    },

    // A held item keeps one identity across re-carries: the daemon
    // mints a new approval id each carry, so records are matched by
    // what they ask, not by id (the shell's toast de-dupe keys the
    // same way).
    fingerprint(a) {
      return [a.agent_id || a.agent_name || '', a.tool_name || a.action || '',
        a.description || '', a.action_summary || ''].join('|');
    },

    dedupe(list) {
      var seen = {}, out = [];
      var sorted = list.slice().sort(function(x, y) {
        return new Date(y.created_at || 0) - new Date(x.created_at || 0);
      });
      sorted.forEach(function(a) {
        var k = this.fingerprint(a);
        if (!seen[k]) { seen[k] = true; out.push(a); }
      }, this);
      return out;
    },

    get pendingList() {
      return this.dedupe(this.approvals.filter(function(a) { return a.status === 'pending'; }));
    },

    get decidedList() {
      // An item still live in Needs you is not also Finished: its
      // expired earlier carries are the same item, superseded.
      var live = {};
      this.pendingList.forEach(function(a) { live[this.fingerprint(a)] = true; }, this);
      var rest = this.approvals.filter(function(a) {
        return a.status !== 'pending' && !live[this.fingerprint(a)];
      }, this);
      return this.dedupe(rest);
    },

    // What would actually happen, in plain lines: the summary when it
    // adds anything, plus the call's own fields (a text's body, a
    // design's id) so no decision is blind.
    previewLines(a) {
      var lines = [];
      var desc = a.description || '';
      if (a.action_summary && a.action_summary !== desc) lines.push(a.action_summary);
      var args = a.args || a.tool_args || null;
      if (args && typeof args === 'object') {
        Object.keys(args).forEach(function(k) {
          var v = args[k];
          if (v === null || v === undefined || v === '') return;
          var s = (typeof v === 'object') ? JSON.stringify(v) : String(v);
          if (s.length > 300) s = s.slice(0, 300) + '…';
          lines.push(k + ': ' + s);
        });
      }
      return lines;
    },

    async loadData() {
      this.loading = true;
      this.loadError = '';
      try {
        var data = await OpenFangAPI.get('/api/approvals');
        this.approvals = data.approvals || [];
      } catch(e) {
        this.loadError = e.message || 'Could not load approvals.';
      }
      try {
        var jd = await OpenFangAPI.get('/api/cron/jobs');
        this.jobs = jd.jobs || jd || [];
      } catch(e) { this.jobs = []; }
      this.loading = false;
    },

    async approve(id) {
      try {
        await OpenFangAPI.post('/api/approvals/' + id + '/approve', {});
        OpenFangToast.success('Approved');
        await this.loadData();
      } catch(e) {
        OpenFangToast.error(e.message);
      }
    },

    async reject(id) {
      var self = this;
      OpenFangToast.confirm('Reject Action', 'Are you sure you want to reject this action?', async function() {
        try {
          await OpenFangAPI.post('/api/approvals/' + id + '/reject', {});
          OpenFangToast.success('Rejected');
          await self.loadData();
        } catch(e) {
          OpenFangToast.error(e.message);
        }
      });
    },

    jobName(j) {
      return j.name || j.label || ({ texts: 'Texts check', designer: 'Design check', brief: 'Morning brief', forms: 'Forms check' })[j.hand_id] || j.hand_id || 'Scheduled check';
    },

    jobWhen(j) {
      var t = j.next_run_at || j.next_run || null;
      if (!t) return j.enabled === false ? 'Paused' : 'On its schedule';
      var d = new Date(t);
      if (isNaN(d)) return j.enabled === false ? 'Paused' : 'On its schedule';
      return (j.enabled === false ? 'Paused · next ' : 'Next ') + d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
    },

    timeAgo(dateStr) {
      if (!dateStr) return '';
      var d = new Date(dateStr);
      var secs = Math.floor((Date.now() - d.getTime()) / 1000);
      if (secs < 60) return secs + 's ago';
      if (secs < 3600) return Math.floor(secs / 60) + 'm ago';
      if (secs < 86400) return Math.floor(secs / 3600) + 'h ago';
      return Math.floor(secs / 86400) + 'd ago';
    }
  };
}
