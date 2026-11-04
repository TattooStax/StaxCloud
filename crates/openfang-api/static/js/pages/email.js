// StaxCloud Email — the shop mailbox (support@staxcloud.ai) under
// Channels, carried by Cloudflare in both directions. Inbound mail is
// pulled from the mail relay into kv records (mail/<uuid>) by the
// mailsync sidecar. Sending follows the house approval law, exactly
// like Texts: the composer holds the message as a draft record
// (draft/<uuid>, kind email_send); it waits in Needs you, and only an
// approved draft ever reaches the outbox (emailout/<uuid>) that the
// sender works from.
'use strict';

function emailPage() {
  return {
    mails: [],
    outbox: [],
    status: null,
    loading: true,
    loadError: '',
    selectedKey: '',
    composing: false,
    to: '',
    subject: '',
    body: '',
    inReplyTo: '',
    references: '',
    holding: false,

    async loadData() {
      this.loading = true;
      this.loadError = '';
      try {
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        var data = await OpenFangAPI.get('/api/memory/agents/' + agentId + '/kv');
        var mails = [], outbox = [], status = null;
        (data.kv_pairs || []).forEach(function(pr) {
          if (!pr.key) return;
          var v = pr.value;
          if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { v = null; } }
          if (!v) return;
          if (pr.key.indexOf('mail/') === 0) {
            mails.push({ key: pr.key, from: v.from || '', from_name: v.from_name || '',
                         to: v.to || '', subject: v.subject || '(no subject)',
                         snippet: v.snippet || '', text: v.text || '', ts: v.ts || '',
                         message_id: v.message_id || '', unread: !!v.unread });
          } else if (pr.key.indexOf('emailout/') === 0) {
            outbox.push({ key: pr.key, to: v.to || '', subject: v.subject || '',
                          status: v.status || 'queued', ts: v.ts || '' });
          } else if (pr.key === 'mailbox/status') {
            status = v;
          }
        });
        mails.sort(function(a, b) { return new Date(b.ts || 0) - new Date(a.ts || 0); });
        outbox.sort(function(a, b) { return new Date(b.ts || 0) - new Date(a.ts || 0); });
        this.mails = mails;
        this.outbox = outbox;
        this.status = status;
      } catch(e) {
        this.loadError = e.message || 'Could not load mail.';
      }
      this.loading = false;
    },

    get selected() {
      var k = this.selectedKey;
      return this.mails.find(function(m) { return m.key === k; }) || null;
    },

    get unreadCount() { return this.mails.filter(function(m) { return m.unread; }).length; },

    fmtTs(ts) {
      if (!ts) return '';
      var d = new Date(ts);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ' ' +
             d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    },

    startCompose() {
      this.composing = true;
      this.selectedKey = '';
      this.to = ''; this.subject = ''; this.body = '';
      this.inReplyTo = ''; this.references = '';
    },

    startReply() {
      var m = this.selected;
      if (!m) return;
      this.composing = true;
      this.selectedKey = '';
      this.to = m.from || '';
      this.subject = /^re:/i.test(m.subject || '') ? m.subject : 'Re: ' + (m.subject || '');
      this.body = '';
      this.inReplyTo = m.message_id || '';
      var refs = (m.references || '').trim();
      this.references = (refs ? refs + ' ' : '') + (m.message_id ? '<' + m.message_id + '>' : '');
    },

    cancelCompose() { this.composing = false; },

    async holdSend() {
      var to = (this.to || '').trim();
      var body = (this.body || '').trim();
      if (!to || !body || this.holding) return;
      this.holding = true;
      try {
        var uuid = (crypto.randomUUID ? crypto.randomUUID() : 'em-' + Date.now());
        var rec = {
          kind: 'email_send',
          to: to,
          to_name: to,
          subject: (this.subject || '').trim() || '(no subject)',
          body: body,
          text: body,
          form: 'email',
          status: 'held',
          ts: new Date().toISOString(),
          in_reply_to: this.inReplyTo || '',
          references: this.references || ''
        };
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        await OpenFangAPI.put('/api/memory/agents/' + agentId + '/kv/' +
          encodeURIComponent('draft/' + uuid), { value: rec });
        this.composing = false;
        this.to = ''; this.subject = ''; this.body = '';
        OpenFangToast.success('Held — it is waiting in Needs you');
      } catch(e) {
        OpenFangToast.error(e.message || 'Could not hold the email. Try again.');
      }
      this.holding = false;
    }
  };
}
