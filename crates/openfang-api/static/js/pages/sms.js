// StaxCloud Texts — Channels module over kv thread records (sms/<digits>)
// mirrored from the studio's modem line. Replies are held as draft records
// (draft/<uuid>, kind sms_reply) and only reach the outbox after the owner
// approves them in Needs you; the modem bridge sends from there.
'use strict';

function smsPage() {
  return {
    threads: [],
    outbox: [],
    loading: true,
    loadError: '',
    selectedKey: '',
    replyText: '',
    holding: false,

    async loadData() {
      this.loading = true;
      this.loadError = '';
      try {
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        var data = await OpenFangAPI.get('/api/memory/agents/' + agentId + '/kv');
        var pairs = data.kv_pairs || [];
        var threads = [];
        var outbox = [];
        pairs.forEach(function(pr) {
          if (!pr.key) return;
          var v = pr.value;
          if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { v = null; } }
          if (!v) return;
          if (pr.key.indexOf('sms/') === 0) {
            var msgs = Array.isArray(v.messages) ? v.messages.slice() : [];
            msgs.sort(function(a, b) { return new Date(a.ts || 0) - new Date(b.ts || 0); });
            threads.push({ key: pr.key, number: v.number || pr.key.slice(4), name: v.name || '', test: !!v.test, messages: msgs });
          } else if (pr.key.indexOf('smsout/') === 0) {
            outbox.push({ key: pr.key, to: v.to || '', body: v.body || '', ts: v.ts || '', status: v.status || 'queued' });
          }
        });
        threads.sort(function(a, b) {
          var la = a.messages.length ? a.messages[a.messages.length - 1].ts : '';
          var lb = b.messages.length ? b.messages[b.messages.length - 1].ts : '';
          return new Date(lb || 0) - new Date(la || 0);
        });
        this.threads = threads;
        this.outbox = outbox;
        Alpine.store('app').smsThreadCount = threads.length;
        var wantThread = '';
        try { wantThread = Alpine.store('app').smsOpenKey || ''; } catch(e) { wantThread = ''; }
        if (wantThread) {
          try { Alpine.store('app').smsOpenKey = ''; } catch(e) {}
          if (threads.some(function(t) { return t.key === wantThread; })) this.selectedKey = wantThread;
        }
      } catch(e) {
        this.loadError = e.message || 'Could not load texts.';
      }
      this.loading = false;
      if (this.selectedKey) this.scrollThread();
    },

    get tab() { return Alpine.store('app').smsTab; },

    openThread(th) {
      this.selectedKey = th.key;
      this.scrollThread();
    },

    // The thread's message region scrolls on its own now; land on
    // the newest message when a thread opens.
    scrollThread() {
      var self = this;
      this.$nextTick(function() {
        var el = self.$refs.threadScroll;
        if (el) el.scrollTop = el.scrollHeight;
      });
    },

    get selected() {
      var k = this.selectedKey;
      return this.threads.find(function(t) { return t.key === k; }) || null;
    },

    lastMsg(t) { return t.messages.length ? t.messages[t.messages.length - 1] : null; },

    // Row preview: the last message's words, or a truthful label when
    // it carried only media (an MMS picture has no body text).
    snippet(t) {
      var m = this.lastMsg(t);
      if (!m) return '';
      if ((m.body || '').trim()) return m.body;
      if (m.media && m.media.length) {
        var img = m.media.some(function(x) { return (x.mime || '').indexOf('image/') === 0; });
        return img ? 'Photo' : 'Attachment';
      }
      return '';
    },

    fmtTs(ts) {
      if (!ts) return '';
      var d = new Date(ts);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    },

    prettyNumber(n) {
      var d = (n || '').replace(/\D/g, '');
      if (d.length === 11 && d.charAt(0) === '1') d = d.slice(1);
      if (d.length === 10) return '(' + d.slice(0, 3) + ') ' + d.slice(3, 6) + '-' + d.slice(6);
      return n;
    },

    async holdReply() {
      var t = this.selected;
      var body = (this.replyText || '').trim();
      if (!t || !body || this.holding) return;
      this.holding = true;
      try {
        var uuid = (crypto.randomUUID ? crypto.randomUUID() : 'sms-' + Date.now());
        var rec = {
          kind: 'sms_reply',
          to: t.number,
          to_name: t.name || '',
          body: body,
          thread: t.key,
          status: 'held',
          ts: new Date().toISOString()
        };
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        await OpenFangAPI.put('/api/memory/agents/' + agentId + '/kv/' + encodeURIComponent('draft/' + uuid), { value: rec });
        this.replyText = '';
        OpenFangToast.success('Reply held — it is waiting in Needs you');
      } catch(e) {
        OpenFangToast.error(e.message);
      }
      this.holding = false;
    }
  };
}
