// StaxCloud Home — the conversation with Stax is the landing.
// Presentation only: the thread and composer run on chatPage (same WS +
// HTTP fallback, same session handling); the brief card reads the same
// brief/<date> kv record through the store's loadMorningBrief(); the
// Needs-you line is the store's real approvals count; first-run setup is
// the existing setupPage flow, presented as turns in the thread.
'use strict';

var STAX_LEAD_ID = '8cad1d3b-58f9-5563-ba0f-966d734c8a1f';

function findStaxAgent() {
  var agents = (Alpine.store('app') && Alpine.store('app').agents) || [];
  for (var i = 0; i < agents.length; i++) {
    if (agents[i] && (agents[i].name === 'stax' || agents[i].id === STAX_LEAD_ID)) return agents[i];
  }
  return null;
}

// Keep the home thread on Stax. chatPage restores whichever agent was last
// open anywhere; home is always the lead's conversation.
function homePinStax(chat) {
  function pick() {
    var s = findStaxAgent();
    if (s && (!chat.currentAgent || chat.currentAgent.id !== s.id)) {
      chat.selectAgent(s);
    }
  }
  pick();
  chat.$watch('$store.app.agents', pick);
  // An Ask Stax row drafted a request: put it in the composer, ready to send.
  function takeDraft() {
    var store = Alpine.store('app');
    var d = store.askDraft;
    if (!d) return;
    store.askDraft = '';
    setTimeout(function() {
      chat.inputText = d;
      chat.$nextTick(function() {
        var el = document.getElementById('msg-input');
        if (!el) return;
        el.focus();
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 150) + 'px';
      });
    }, 250);
  }
  takeDraft();
  chat.$watch('$store.app.askDraft', takeDraft);
  // The drawer switched or started a Stax conversation: reload the thread
  // onto the now-active session (same calls as the chat's session switch).
  chat.$watch('$store.app.homeReload', function() {
    var s = findStaxAgent();
    if (!s) return;
    if (!chat.currentAgent || chat.currentAgent.id !== s.id) { chat.selectAgent(s); return; }
    chat.messages = [];
    chat._wsAgent = null;
    chat.connectWs(s.id);
    chat.loadSession(s.id);
    chat.loadSessions(s.id);
  });
}

// "Start a fresh conversation" on the Stax card: the same sessions API the
// chat's own session switcher uses, without the name prompt.
async function homeFreshConversation(chat) {
  if (!chat || !chat.currentAgent) return;
  var id = chat.currentAgent.id;
  try {
    await OpenFangAPI.post('/api/agents/' + id + '/sessions', {});
    chat.messages = [];
    chat._wsAgent = null;
    chat.connectWs(id);
    await chat.loadSessions(id);
  } catch(e) {
    if (typeof OpenFangToast !== 'undefined') OpenFangToast.error('Could not start a fresh conversation. Try again in a moment.');
  }
}

// Status in plain words, from real state: the daemon connection and the
// texts helper. Its replies are held drafts that wait for the owner's
// approval (see the sms hand), so "you approve" is the true mode.
// Shared by the Home pill and the drawer's Stax row (one source, one wording).
function staxStatus() {
  var s = Alpine.store('app');
  if (!s.connected && !s.booting) return { tone: 'warn', words: 'Reconnecting' };
  if (s.booting) return { tone: 'quiet', words: 'Waking up' };
  var agents = s.agents || [];
  var sms = agents.find(function(a) { return a.name === 'sms'; });
  if (sms) {
    var on = (sms.state || '').toLowerCase() === 'running';
    return { tone: on ? 'ok' : 'quiet', words: on ? 'Text replies: You approve' : 'Text replies: Paused' };
  }
  var ready = !!findStaxAgent();
  return { tone: ready ? 'ok' : 'quiet', words: ready ? 'Stax is on' : 'Stax is getting ready' };
}

function homePage() {
  return {
    homeEngaged: false,   // the owner started talking or started setup this visit
    homeSetup: false,     // the setup conversation is running in the thread
    homeSetupAt: 0,       // thread position where the setup conversation began

    init() {
      // The stock first-use tips message is a developer cheat sheet; home
      // never shows it. (The flag only suppresses that one system message.)
      try { localStorage.setItem('of-chat-tips-seen', 'true'); } catch(e) {}
      var store = Alpine.store('app');
      store.loadSetup();
      store.loadMorningBrief();
      // A conversation opened from the drawer lands in the thread view.
      var self = this;
      var engage = function() { if (store.homeEngage) { self.homeEngaged = true; store.homeEngage = false; } };
      engage();
      this.$watch('$store.app.homeEngage', engage);
    },

    get staxReady() { return !!findStaxAgent(); },

    // The Stax card is open. Held in the store so the drawer's Stax row
    // opens this same card.
    get homeCard() { return Alpine.store('app').staxCard; },
    set homeCard(v) { Alpine.store('app').staxCard = !!v; },

    // First open (Figma screen 1) until a setup/profile record exists.
    get homeFirstOpen() {
      var s = Alpine.store('app');
      return s.setupLoaded && !s.setupDone;
    },

    // The status pill. One source for every place status appears: the
    // drawer's Stax row renders this same staxStatus() expression.
    get homeStatus() { return staxStatus(); },

    get homeNeedsWords() {
      var n = Alpine.store('app').pendingApprovalCount || 0;
      if (n === 0) return 'Nothing needs you right now';
      return n === 1 ? '1 thing needs you' : n + ' things need you';
    },

    get homeToday() {
      return new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
    },

    // Called from the chat scope so the setup turns sit at the point in the
    // thread where they started; later messages flow below them.
    homeStartSetup(count) {
      this.homeSetupAt = count || 0;
      this.homeEngaged = true;
      this.homeSetup = true;
    },

    // System lines in the thread speak plainly: failures say what to do,
    // never echo the raw error string.
    homeSystemText(text) {
      var t = String(text || '');
      if (/^error\b|failed|not connected|exception|panic/i.test(t)) {
        return 'That didn\u2019t go through. Give it a moment and send it again.';
      }
      return t;
    },

    homeIsFailure(text) {
      return /^error\b|failed|not connected|exception|panic/i.test(String(text || ''));
    }
  };
}
