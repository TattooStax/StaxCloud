// OpenFang App — Alpine.js init, hash router, global store
'use strict';

// Marked.js configuration
if (typeof marked !== 'undefined') {
  marked.setOptions({
    breaks: true,
    gfm: true,
    highlight: function(code, lang) {
      if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
        try { return hljs.highlight(code, { language: lang }).value; } catch(e) {}
      }
      return code;
    }
  });
}

function escapeHtml(text) {
  var div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML.replace(/\n/g, '<br>');
}

function renderMarkdown(text) {
  if (!text) return '';
  if (typeof marked !== 'undefined') {
    // Protect LaTeX blocks from marked.js mangling (underscores, backslashes, etc.)
    var latexBlocks = [];
    var protected_ = text;
    // Protect display math $$...$$ first (greedy across lines)
    protected_ = protected_.replace(/\$\$([\s\S]+?)\$\$/g, function(match) {
      var idx = latexBlocks.length;
      latexBlocks.push(match);
      return '\x00LATEX' + idx + '\x00';
    });
    // Protect inline math $...$ (single line, not empty, not starting/ending with space)
    protected_ = protected_.replace(/\$([^\s$](?:[^$]*[^\s$])?)\$/g, function(match) {
      var idx = latexBlocks.length;
      latexBlocks.push(match);
      return '\x00LATEX' + idx + '\x00';
    });
    // Protect \[...\] display math
    protected_ = protected_.replace(/\\\[([\s\S]+?)\\\]/g, function(match) {
      var idx = latexBlocks.length;
      latexBlocks.push(match);
      return '\x00LATEX' + idx + '\x00';
    });
    // Protect \(...\) inline math
    protected_ = protected_.replace(/\\\(([\s\S]+?)\\\)/g, function(match) {
      var idx = latexBlocks.length;
      latexBlocks.push(match);
      return '\x00LATEX' + idx + '\x00';
    });

    var html = marked.parse(protected_);
    // Restore LaTeX blocks
    for (var i = 0; i < latexBlocks.length; i++) {
      html = html.replace('\x00LATEX' + i + '\x00', latexBlocks[i]);
    }
    // Add copy buttons to code blocks
    html = html.replace(/<pre><code/g, '<pre><button class="copy-btn" onclick="copyCode(this)">Copy</button><code');
    // Open external links in new tab
    html = html.replace(/<a\s+href="(https?:\/\/[^"]*)"(?![^>]*target=)([^>]*)>/gi, '<a href="$1" target="_blank" rel="noopener"$2>');
    return html;
  }
  return escapeHtml(text);
}

function copyCode(btn) {
  var code = btn.nextElementSibling;
  if (code) {
    navigator.clipboard.writeText(code.textContent).then(function() {
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(function() { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 1500);
    });
  }
}

// Tool category icon SVGs — returns inline SVG for each tool category
function toolIcon(toolName) {
  if (!toolName) return '';
  var n = toolName.toLowerCase();
  var s = 'width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
  // File/directory operations
  if (n.indexOf('file_') === 0 || n.indexOf('directory_') === 0)
    return '<svg ' + s + '><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>';
  // Web/fetch
  if (n.indexOf('web_') === 0 || n.indexOf('link_') === 0)
    return '<svg ' + s + '><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15 15 0 0 1 4 10 15 15 0 0 1-4 10 15 15 0 0 1-4-10 15 15 0 0 1 4-10z"/></svg>';
  // Shell/exec
  if (n.indexOf('shell') === 0 || n.indexOf('exec_') === 0)
    return '<svg ' + s + '><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>';
  // Agent operations
  if (n.indexOf('agent_') === 0)
    return '<svg ' + s + '><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>';
  // Memory/knowledge
  if (n.indexOf('memory_') === 0 || n.indexOf('knowledge_') === 0)
    return '<svg ' + s + '><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>';
  // Cron/schedule
  if (n.indexOf('cron_') === 0 || n.indexOf('schedule_') === 0)
    return '<svg ' + s + '><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
  // Browser/playwright
  if (n.indexOf('browser_') === 0 || n.indexOf('playwright_') === 0)
    return '<svg ' + s + '><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/></svg>';
  // Container/docker
  if (n.indexOf('container_') === 0 || n.indexOf('docker_') === 0)
    return '<svg ' + s + '><path d="M22 12H2"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>';
  // Image/media
  if (n.indexOf('image_') === 0 || n.indexOf('tts_') === 0)
    return '<svg ' + s + '><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>';
  // Hand tools
  if (n.indexOf('hand_') === 0)
    return '<svg ' + s + '><path d="M18 11V6a2 2 0 0 0-2-2 2 2 0 0 0-2 2"/><path d="M14 10V4a2 2 0 0 0-2-2 2 2 0 0 0-2 2v6"/><path d="M10 10.5V6a2 2 0 0 0-2-2 2 2 0 0 0-2 2v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.9-5.7-2.4L3.4 16a2 2 0 0 1 3.2-2.4L8 15"/></svg>';
  // Task/collab
  if (n.indexOf('task_') === 0)
    return '<svg ' + s + '><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>';
  // Default — wrench
  return '<svg ' + s + '><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>';
}

// Alpine.js global store
document.addEventListener('alpine:init', function() {
  // Restore saved API key on load
  var savedKey = localStorage.getItem('openfang-api-key');
  if (savedKey) OpenFangAPI.setAuthToken(savedKey);

  Alpine.store('app', {
    agents: [],
    connected: false,
    booting: true,
    wsConnected: false,
    connectionState: 'connected',
    lastError: '',
    version: '0.1.0',
    agentCount: 0,
    pendingApprovalCount: 0,
    pendingApprovals: [],
    sideOpen: false,
    // System > Advanced side panel (side chats + cards), out of the drawer.
    r4Open: false,
    // The Stax card on Home; the drawer's Stax row opens the same card.
    staxCard: false,
    // Bumped after the drawer switches or starts a Stax conversation, so a
    // mounted Home thread reloads the now-active session.
    homeReload: 0,
    homeEngage: false,
    formsTab: 'forms',
    smsTab: 'inbox',
    setupDone: false,
    setupLoaded: false,
    ownerName: 'Shawn',
    morningBrief: null,
    smsThreadCount: 0,
    showAllHelpers: false,
    crewNames: ['stax', 'forms', 'sms', 'surface-builder', 'deep-work'],
    formsNewCount: 0,
    lastPendingApprovalSignature: '',
    pendingAgent: null,
    focusMode: localStorage.getItem('openfang-focus') === 'true',
    showOnboarding: false,
    showAuthPrompt: false,
    authMode: 'apikey',
    sessionUser: null,

    toggleFocusMode() {
      this.focusMode = !this.focusMode;
      localStorage.setItem('openfang-focus', this.focusMode);
    },

    async refreshAgents() {
      try {
        var agents = await OpenFangAPI.get('/api/agents');
        this.agents = Array.isArray(agents) ? agents : [];
        this.agentCount = this.agents.length;
      } catch(e) { /* silent */ }
    },

    async loadSetup() {
      try {
        var first = (this.agents && this.agents[0]) || null;
        var aid = first ? first.id : 'shared';
        var d = await OpenFangAPI.get('/api/memory/agents/' + aid + '/kv/' + encodeURIComponent('setup/profile'));
        var v = d && d.value;
        if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { v = null; } }
        this.setupDone = !!(v && v.business);
      } catch(e) { this.setupDone = false; }
      this.setupLoaded = true;
    },

    async loadMorningBrief() {
      try {
        var first = (this.agents && this.agents[0]) || null;
        var aid = first ? first.id : 'shared';
        var now = new Date();
        var key = 'brief/' + now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
        var d = await OpenFangAPI.get('/api/memory/agents/' + aid + '/kv/' + encodeURIComponent(key));
        var v = d && d.value;
        if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { v = null; } }
        this.morningBrief = (v && v.text) ? v : null;
      } catch(e) { this.morningBrief = null; }
    },

    isCrew(a) { return !!a && this.crewNames.indexOf(a.name) >= 0; },
    displayName(a) {
      if (!a) return '';
      if (a.name === 'stax') return 'Stax';
      if (a.name === 'surface-builder') return 'Surface Builder';
      if (a.name === 'deep-work') return 'Deep Work';
      if (a.name === 'sms') return 'Texts';
      if (a.name === 'forms') return 'Forms';
      return a.name;
    },
    displayRole(a) {
      if (!a) return '';
      var roles = { stax: 'Your lead', forms: 'Forms & intake', sms: 'Texts', 'surface-builder': 'Boards & SEO', 'deep-work': 'Research & hard problems' };
      return roles[a.name] || a.model_name || '';
    },

    async refreshApprovals() {
      try {
        var data = await OpenFangAPI.get('/api/approvals');
        var approvals = Array.isArray(data) ? data : (data.approvals || []);
        var pending = approvals.filter(function(a) { return a.status === 'pending'; });
        var signature = pending
          .map(function(a) { return a.id; })
          .sort()
          .join(',');
        if (pending.length > 0 && signature !== this.lastPendingApprovalSignature && typeof OpenFangToast !== 'undefined') {
          OpenFangToast.warn('An agent is waiting for approval. Open Approvals to review.');
        }
        this.pendingApprovalCount = pending.length;
        this.pendingApprovals = pending;
        this.loadSetup();
        this.loadMorningBrief();
        this.lastPendingApprovalSignature = signature;
      } catch(e) { /* silent */ }
    },

    // Queue the lead agent so the chat page opens on Stax. Navigation itself
    // happens in the caller (template scope), where navigate() lives.
    staxAgent() {
      var agents = this.agents || [];
      var la = agents.find(function(a) { return a.name === 'stax'; });
      if (la) this.pendingAgent = la;
    },

    // A module's "Agent" button opens that helper as a side chat in the
    // Advanced side panel (its own WebSocket), not the helpers console and
    // not the drawer.
    openSideChat(name) {
      var agents = this.agents || [];
      var a = agents.find(function(x) { return x.name === name; });
      if (!a) return;
      this.r4Open = true;
      window.dispatchEvent(new CustomEvent('side-chat', { detail: { agentId: a.id } }));
    },

    smsAgent() { this.openSideChat('sms'); },

    formsAgent() { this.openSideChat('forms'); },

    async approveApproval(id) {
      try {
        await OpenFangAPI.post('/api/approvals/' + id + '/approve', {});
        OpenFangToast.success('Approved');
        this.refreshApprovals();
      } catch(e) { OpenFangToast.error(e.message); }
    },

    async rejectApproval(id) {
      var self = this;
      OpenFangToast.confirm('Reject Action', 'Are you sure you want to reject this action?', async function() {
        try {
          await OpenFangAPI.post('/api/approvals/' + id + '/reject', {});
          OpenFangToast.success('Rejected');
          self.refreshApprovals();
        } catch(e) { OpenFangToast.error(e.message); }
      });
    },

    async checkStatus() {
      try {
        var s = await OpenFangAPI.get('/api/status');
        this.connected = true;
        this.booting = false;
        this.lastError = '';
        this.version = s.version || '0.1.0';
        this.agentCount = s.agent_count || 0;
      } catch(e) {
        this.connected = false;
        this.lastError = e.message || 'Unknown error';
        console.warn('[OpenFang] Status check failed:', e.message);
      }
    },

    async checkOnboarding() {
      if (localStorage.getItem('openfang-onboarded')) return;
      try {
        var config = await OpenFangAPI.get('/api/config');
        var apiKey = config && config.api_key;
        var noKey = !apiKey || apiKey === 'not set' || apiKey === '';
        if (noKey && this.agentCount === 0) {
          this.showOnboarding = true;
        }
      } catch(e) {
        // If config endpoint fails, still show onboarding if no agents
        if (this.agentCount === 0) this.showOnboarding = true;
      }
    },

    dismissOnboarding() {
      this.showOnboarding = false;
      localStorage.setItem('openfang-onboarded', 'true');
    },

    async checkAuth() {
      try {
        // First check if session-based auth is configured
        var authInfo = await OpenFangAPI.get('/api/auth/check');
        if (authInfo.mode === 'none') {
          // No session auth — fall back to API key detection
          this.authMode = 'apikey';
          this.sessionUser = null;
        } else if (authInfo.mode === 'session') {
          this.authMode = 'session';
          if (authInfo.authenticated) {
            this.sessionUser = authInfo.username;
            this.showAuthPrompt = false;
            return;
          }
          // Session auth enabled but not authenticated — show login prompt
          this.showAuthPrompt = true;
          return;
        }
      } catch(e) { /* ignore — fall through to API key check */ }

      // API key mode detection
      try {
        await OpenFangAPI.get('/api/tools');
        this.showAuthPrompt = false;
      } catch(e) {
        if (e.message && (e.message.indexOf('Not authorized') >= 0 || e.message.indexOf('401') >= 0 || e.message.indexOf('Missing Authorization') >= 0 || e.message.indexOf('Unauthorized') >= 0)) {
          var saved = localStorage.getItem('openfang-api-key');
          if (saved) {
            OpenFangAPI.setAuthToken('');
            localStorage.removeItem('openfang-api-key');
          }
          this.showAuthPrompt = true;
        }
      }
    },

    submitApiKey(key) {
      if (!key || !key.trim()) return;
      OpenFangAPI.setAuthToken(key.trim());
      localStorage.setItem('openfang-api-key', key.trim());
      this.showAuthPrompt = false;
      window.location.hash = 'chat';
      this.refreshAgents();
    },

    async sessionLogin(username, password) {
      try {
        var result = await OpenFangAPI.post('/api/auth/login', { username: username, password: password });
        if (result.status === 'ok') {
          this.sessionUser = result.username;
          this.showAuthPrompt = false;
          // Fresh login always lands on home.
          window.location.hash = 'chat';
          this.refreshAgents();
        } else {
          OpenFangToast.error(result.error || 'Login failed');
        }
      } catch(e) {
        OpenFangToast.error(e.message || 'Login failed');
      }
    },

    async sessionLogout() {
      try {
        await OpenFangAPI.post('/api/auth/logout');
      } catch(e) { /* ignore */ }
      this.sessionUser = null;
      this.showAuthPrompt = true;
    },

    clearApiKey() {
      OpenFangAPI.setAuthToken('');
      localStorage.removeItem('openfang-api-key');
    }
  });
});

// Main app component
function app() {
  return {
    page: 'chat',
    surface: null,
    surfaceOf: { chat: 'home', sms: 'channels', approvals: 'work', contacts: 'leads', sessions: 'work', analytics: 'work', boards: 'boards', forms: 'studio', workflows: 'studio', scheduler: 'studio', hands: 'studio', skills: 'studio', channels: 'system', settings: 'system', overview: 'advanced', agents: 'advanced', setup: 'advanced', comms: 'advanced', logs: 'advanced', runtime: 'advanced', wizard: 'advanced' },
    surfaceHome: { home: 'chat', channels: 'chat', work: 'approvals', boards: 'boards', leads: 'contacts', studio: 'workflows', system: 'channels', advanced: 'agents' },
    // Pages demoted to System > Advanced. Their page keys are unchanged;
    // only their URL hash carries an advanced/ prefix, so a stale #agents or
    // #overview bookmark lands on home instead of the old consoles.
    advancedPages: ['overview', 'agents', 'setup', 'comms', 'logs', 'runtime', 'wizard'],
    themeMode: localStorage.getItem('openfang-theme-mode') || 'system',
    theme: (() => {
      var mode = localStorage.getItem('openfang-theme-mode') || 'system';
      if (mode === 'system') return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      return mode;
    })(),
    sidebarCollapsed: localStorage.getItem('openfang-sidebar') === 'collapsed',
    mobileMenuOpen: false,
    connected: false,
    wsConnected: false,
    version: '0.1.0',
    agentCount: 0,

    get agents() { return Alpine.store('app').agents; },

    init() {
      var self = this;

      // Listen for OS theme changes (only matters when mode is 'system')
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
        if (self.themeMode === 'system') {
          self.theme = e.matches ? 'dark' : 'light';
        }
      });

      // Hash routing
      var validPages = ['overview','chat','agents','sessions','approvals','comms','workflows','scheduler','channels','skills','hands','analytics','logs','runtime','settings','wizard'];
      var pageRedirects = {
        'templates': 'agents',
        'triggers': 'workflows',
        'cron': 'scheduler',
        'schedules': 'scheduler',
        'memory': 'sessions',
        'audit': 'logs',
        'security': 'settings',
        'peers': 'settings',
        'migration': 'settings',
        'usage': 'analytics',
        'approval': 'approvals'
      };
      function handleHash() {
        var hash = window.location.hash.replace('#', '') || 'chat';
        if (pageRedirects[hash]) {
          hash = pageRedirects[hash];
        }
        // advanced/<key> opens a demoted page; a bare demoted key is a
        // stale landing and goes home.
        if (hash.indexOf('advanced/') === 0) {
          var key = hash.slice(9);
          if (self.advancedPages.indexOf(key) >= 0) { self.page = key; self.surface = 'advanced'; }
          return;
        }
        if (self.advancedPages.indexOf(hash) >= 0) hash = 'chat';
        if (('#' + hash) !== window.location.hash) {
          history.replaceState(null, '', '#' + hash);
        }
        if (validPages.indexOf(hash) >= 0) {
          self.page = hash;
          if (hash === 'chat' && self.surface !== 'channels') self.surface = 'home';
        }
      }
      window.addEventListener('hashchange', handleHash);
      handleHash();

      // Keyboard shortcuts
      document.addEventListener('keydown', function(e) {
        // Ctrl+K — focus agent switch / go to agents
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
          e.preventDefault();
          self.navigate('agents');
        }
        // Ctrl+N — new agent
        if ((e.ctrlKey || e.metaKey) && e.key === 'n' && !e.shiftKey) {
          e.preventDefault();
          self.navigate('agents');
        }
        // Ctrl+Shift+F — toggle focus mode
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'F') {
          e.preventDefault();
          Alpine.store('app').toggleFocusMode();
        }
        // Escape — close mobile menu
        if (e.key === 'Escape') {
          self.mobileMenuOpen = false;
        }
      });

      // Connection state listener
      OpenFangAPI.onConnectionChange(function(state) {
        Alpine.store('app').connectionState = state;
      });

      // Initial data load
      this.pollStatus();
      Alpine.store('app').refreshApprovals();
      Alpine.store('app').checkOnboarding();
      Alpine.store('app').checkAuth();
      setInterval(function() {
        self.pollStatus();
        Alpine.store('app').refreshApprovals();
      }, 5000);
    },

    // The surface the shell chrome (dock highlight, pill row) follows. It is
    // the surface the user actually entered by, because two dock tabs (Stax
    // and Channels) land on the same chat page and the page alone cannot
    // say which one is active.
    surf() {
      return this.surface || this.surfaceOf[this.page] || 'home';
    },

    navigate(p) {
      this.page = p;
      window.location.hash = (this.advancedPages.indexOf(p) >= 0 ? 'advanced/' : '') + p;
      this.mobileMenuOpen = false;
      Alpine.store('app').sideOpen = false;
      Alpine.store('app').r4Open = false;
      Alpine.store('app').staxCard = false;
      this.surface = this.surfaceOf[p] || this.surface;
      // The agents template stays mounted when moving between the list and
      // the chat page, so it cannot rely on init alone to open the chat.
      if (p === 'chat') window.dispatchEvent(new CustomEvent('open-chat'));
    },

    goSurface(s) {
      this.navigate(this.surfaceHome[s]);
      this.surface = s;
    },

    setTheme(mode) {
      this.themeMode = mode;
      localStorage.setItem('openfang-theme-mode', mode);
      if (mode === 'system') {
        this.theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      } else {
        this.theme = mode;
      }
    },

    toggleTheme() {
      var modes = ['light', 'system', 'dark'];
      var next = modes[(modes.indexOf(this.themeMode) + 1) % modes.length];
      this.setTheme(next);
    },

    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed;
      localStorage.setItem('openfang-sidebar', this.sidebarCollapsed ? 'collapsed' : 'expanded');
    },

    async pollStatus() {
      var store = Alpine.store('app');
      await store.checkStatus();
      await store.refreshAgents();
      this.connected = store.connected;
      this.version = store.version;
      this.agentCount = store.agentCount;
      this.wsConnected = OpenFangAPI.isWsConnected();
    }
  };
}


// ── R4: Side panel — side chats (own WebSocket, never touches the main-chat
// singleton) + side cards (projections of real records) ─────────────────────
function sidePanel() {
  return {
    tab: 'chats',
    view: 'list',
    sessions: [],
    loadingList: false,
    chatAgent: null,
    chatSessions: [],
    messages: [],
    input: '',
    sending: false,
    wsState: 'off',
    _ws: null,
    _msgSeq: 0,
    jobs: [],

    initPanel() {
      var self = this;
      this.$watch('$store.app.r4Open', function(open) {
        if (open) { self.onOpen(); } else { self.disconnectWs(); }
      });
      // Module "Agent" buttons open their helper here as a side chat.
      window.addEventListener('side-chat', function(e) {
        if (!e.detail || !e.detail.agentId) return;
        self.tab = 'chats';
        self.openChat(e.detail.agentId);
      });
    },

    onOpen() { this.loadSessions(); this.loadJobs(); },

    async loadSessions() {
      this.loadingList = true;
      try {
        var data = await OpenFangAPI.get('/api/sessions');
        var agents = Alpine.store('app').agents || [];
        var map = {};
        agents.forEach(function(a) { map[a.id] = a.name; });
        var list = data.sessions || [];
        list.forEach(function(s) { s.agent_name = map[s.agent_id] || 'Helper'; });
        list.sort(function(a, b) { return new Date(b.created_at || 0) - new Date(a.created_at || 0); });
        this.sessions = list;
      } catch(e) { this.sessions = []; }
      this.loadingList = false;
    },

    async loadJobs() {
      try {
        var data = await OpenFangAPI.get('/api/cron/jobs');
        var jobs = (data.jobs || []).filter(function(j) { return j.enabled && j.next_run; });
        jobs.sort(function(a, b) { return new Date(a.next_run) - new Date(b.next_run); });
        this.jobs = jobs.slice(0, 3);
      } catch(e) { this.jobs = []; }
    },

    agentById(id) {
      return (Alpine.store('app').agents || []).find(function(a) { return a.id === id; });
    },

    async openChat(agentId, sessionId) {
      var agent = this.agentById(agentId);
      if (!agent) return;
      this.chatAgent = agent;
      this.view = 'chat';
      this.messages = [];
      if (sessionId) {
        try { await OpenFangAPI.post('/api/agents/' + agentId + '/sessions/' + sessionId + '/switch', {}); } catch(e) {}
      }
      await this.loadChatSessions();
      await this.loadHistory();
      this.connectWs();
    },

    async loadChatSessions() {
      try {
        var data = await OpenFangAPI.get('/api/agents/' + this.chatAgent.id + '/sessions');
        this.chatSessions = data.sessions || [];
      } catch(e) { this.chatSessions = []; }
    },

    async loadHistory() {
      var self = this;
      try {
        var data = await OpenFangAPI.get('/api/agents/' + this.chatAgent.id + '/session');
        var msgs = (data.messages || []).filter(function(m) { return m && m.role !== 'System' && m.role !== 'system'; });
        this.messages = msgs.map(function(m) {
          return { id: ++self._msgSeq, role: (m.role === 'User' ? 'user' : 'agent'), text: (typeof m.content === 'string' ? m.content : ''), meta: '', tools: [] };
        });
      } catch(e) { this.messages = []; }
      this.scrollDown();
    },

    async newSession() {
      if (!this.chatAgent) return;
      try {
        await OpenFangAPI.post('/api/agents/' + this.chatAgent.id + '/sessions', {});
        await this.loadChatSessions();
        var act = this.chatSessions.find(function(s) { return s.active; });
        if (act) { await this.openChat(this.chatAgent.id, act.session_id); }
      } catch(e) { OpenFangToast.error('Could not start a new session'); }
    },

    connectWs() {
      this.disconnectWs();
      if (!this.chatAgent) return;
      var self = this;
      var proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
      var token = OpenFangAPI.getToken ? OpenFangAPI.getToken() : '';
      var url = proto + location.host + '/api/agents/' + this.chatAgent.id + '/ws' + (token ? '?token=' + encodeURIComponent(token) : '');
      var ws;
      try { ws = new WebSocket(url); } catch(e) { this.wsState = 'http'; return; }
      this._ws = ws;
      this.wsState = 'connecting';
      ws.onopen = function() { if (self._ws === ws) self.wsState = 'live'; };
      ws.onmessage = function(ev) {
        if (self._ws !== ws) return;
        var data;
        try { data = JSON.parse(ev.data); } catch(e) { return; }
        self.onFrame(data);
      };
      ws.onclose = function() { if (self._ws === ws && self.wsState === 'live') self.wsState = 'http'; };
      ws.onerror = function() { if (self._ws === ws) self.wsState = 'http'; };
    },

    disconnectWs() {
      if (this._ws) { try { this._ws.close(1000); } catch(e) {} this._ws = null; }
      this.wsState = 'off';
    },

    onFrame(data) {
      var last = this.messages.length ? this.messages[this.messages.length - 1] : null;
      if (data.type === 'typing') {
        if (data.state === 'start') {
          if (!last || !last.streaming) {
            this.messages.push({ id: ++this._msgSeq, role: 'agent', text: 'Thinking...', meta: '', tools: [], streaming: true, thinking: true });
            this.scrollDown();
          }
        } else if (data.state === 'tool' && last && last.thinking) {
          last.text = 'Using a tool...';
          this.messages.splice(this.messages.length - 1, 1, last);
        }
      } else if (data.type === 'text_delta') {
        if (last && last.streaming) {
          if (last.thinking) { last.text = ''; last.thinking = false; }
          last.text += (data.content || '');
          this.messages.splice(this.messages.length - 1, 1, last);
          this.scrollDown();
        }
      } else if (data.type === 'response') {
        var streamed = '';
        this.messages.forEach(function(m) { if (m.streaming && !m.thinking && m.role === 'agent') streamed += (m.text || ''); });
        this.messages = this.messages.filter(function(m) { return !m.streaming; });
        var finalText = (data.content && data.content.trim()) ? data.content : streamed;
        if (finalText) this.messages.push({ id: ++this._msgSeq, role: 'agent', text: finalText, meta: '', tools: [] });
        this.sending = false;
        this.scrollDown();
      } else if (data.type === 'message') {
        if (data.content) {
          this.messages.push({ id: ++this._msgSeq, role: 'user', text: data.content, meta: 'scheduled', tools: [] });
          this.scrollDown();
        }
      }
    },

    async sendSide() {
      var text = (this.input || '').trim();
      if (!text || !this.chatAgent || this.sending) return;
      this.input = '';
      this.messages.push({ id: ++this._msgSeq, role: 'user', text: text, meta: '', tools: [] });
      this.scrollDown();
      this.sending = true;
      if (this._ws && this._ws.readyState === WebSocket.OPEN) {
        this._ws.send(JSON.stringify({ type: 'message', content: text }));
        this.messages.push({ id: ++this._msgSeq, role: 'agent', text: 'Thinking...', meta: '', tools: [], streaming: true, thinking: true });
        this.scrollDown();
        return;
      }
      try {
        var res = await OpenFangAPI.post('/api/agents/' + this.chatAgent.id + '/message', { message: text });
        this.messages.push({ id: ++this._msgSeq, role: 'agent', text: res.response || '', meta: '', tools: [] });
      } catch(e) {
        this.messages.push({ id: ++this._msgSeq, role: 'system', text: 'Error: ' + e.message, meta: '', tools: [] });
      }
      this.sending = false;
      this.scrollDown();
    },

    openInChannels() {
      if (!this.chatAgent) return;
      Alpine.store('app').pendingAgent = this.chatAgent;
      Alpine.store('app').r4Open = false;
      // Stax's conversation is home; other helpers open in the Advanced
      // helpers view.
      navigate(this.chatAgent.name === 'stax' ? 'chat' : 'agents');
    },

    scrollDown() {
      var self = this;
      this.$nextTick(function() {
        var el = self.$refs.sideScroll;
        if (el) el.scrollTop = el.scrollHeight;
      });
    },

    fmtWhen(ts) {
      if (!ts) return '';
      var d = new Date(ts);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    }
  };
}


// ── Step 2: the drawer (side card) ─────────────────────────────────────────
// Presentation over existing machinery only. Chats are the lead agent's own
// session records (GET /api/agents/{id}/sessions), titled by their label;
// opening one is the existing session switch, New chat is the existing
// session create. Both then hand off to Home, which reloads the now-active
// session. Status comes from staxStatus() (home.js), the pill's own source.
function staxDrawer() {
  return {
    open: { channels: true, studio: true, system: true },
    chats: [],
    loaded: false,
    showAll: false,
    chatLimit: 5,
    busy: false,
    scrolled: false,

    initDrawer() {
      var self = this;
      try {
        var saved = JSON.parse(localStorage.getItem('stax-drawer-open') || 'null');
        if (saved && typeof saved === 'object') {
          ['channels', 'studio', 'system'].forEach(function(k) { if (typeof saved[k] === 'boolean') self.open[k] = saved[k]; });
        }
      } catch(e) { /* ignore */ }
      this.$watch('$store.app.sideOpen', function(isOpen) { if (isOpen) self.loadChats(); });
    },

    toggle(k) {
      this.open[k] = !this.open[k];
      try { localStorage.setItem('stax-drawer-open', JSON.stringify(this.open)); } catch(e) { /* ignore */ }
    },

    staxId() {
      var s = typeof findStaxAgent === 'function' ? findStaxAgent() : null;
      return s ? s.id : null;
    },

    async loadChats() {
      var id = this.staxId();
      if (!id) { this.chats = []; this.loaded = true; return; }
      try {
        var data = await OpenFangAPI.get('/api/agents/' + id + '/sessions');
        var list = (data && data.sessions) || [];
        // A blank session nobody named or used is not a conversation yet;
        // the active one always shows (it is what Home is on).
        list = list.filter(function(s) { return s && (s.active || s.label || (s.message_count || 0) > 0); });
        list.sort(function(a, b) { return new Date(b.created_at || 0) - new Date(a.created_at || 0); });
        this.chats = list;
      } catch(e) { this.chats = []; }
      this.loaded = true;
    },

    get visibleChats() {
      return this.showAll ? this.chats : this.chats.slice(0, this.chatLimit);
    },

    // The session record's own title. Unnamed sessions have none, so they
    // read as what they are, never as an id or a timestamp.
    chatTitle(s) {
      var label = s && typeof s.label === 'string' ? s.label.trim() : '';
      if (label) return label;
      return s && s.active ? 'Current conversation' : 'Earlier conversation';
    },

    openStaxCard() {
      // Same card Home's avatar opens: go home, then raise it.
      this.goSurface('home');
      Alpine.store('app').staxCard = true;
    },

    async openConversation(s, goHome) {
      var id = this.staxId();
      if (!id || !s || this.busy) return;
      this.busy = true;
      try {
        if (!s.active) await OpenFangAPI.post('/api/agents/' + id + '/sessions/' + s.session_id + '/switch', {});
        goHome();
        Alpine.store('app').homeEngage = true;
        Alpine.store('app').homeReload++;
      } catch(e) {
        OpenFangToast.error('That conversation did not open. Try again in a moment.');
      }
      this.busy = false;
    },

    async newChat(goHome) {
      var id = this.staxId();
      if (!id || this.busy) return;
      this.busy = true;
      try {
        await OpenFangAPI.post('/api/agents/' + id + '/sessions', {});
        goHome();
        Alpine.store('app').homeEngage = true;
        Alpine.store('app').homeReload++;
      } catch(e) {
        OpenFangToast.error('A new chat did not start. Try again in a moment.');
      }
      this.busy = false;
    }
  };
}


// ── R6: Boards — generic renderer for kv-stored surface definitions ────────
function boardsPage() {
  return {
    surfaces: [],
    kvAll: [],
    current: null,
    loading: true,
    loadError: '',

    async loadData() {
      this.loading = true;
      this.loadError = '';
      try {
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        var data = await OpenFangAPI.get('/api/memory/agents/' + agentId + '/kv');
        var pairs = data.kv_pairs || [];
        this.kvAll = pairs;
        var list = [];
        pairs.forEach(function(pr) {
          if (pr.key && pr.key.indexOf('surface/') === 0) {
            var v = pr.value;
            if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { v = null; } }
            if (v && !v.deleted) {
              list.push({ slug: pr.key.slice(8), title: v.title || pr.key.slice(8), blocks: Array.isArray(v.blocks) ? v.blocks : [] });
            }
          }
        });
        list.sort(function(a, b) { return a.title.localeCompare(b.title); });
        this.surfaces = list;
        if (this.current && !list.some(function(s) { return s.slug === this.current; })) this.current = null;
      } catch(e) {
        this.loadError = e.message || 'Could not load boards.';
      }
      this.loading = false;
    },

    get currentSurface() {
      var c = this.current;
      return this.surfaces.find(function(s) { return s.slug === c; }) || null;
    },

    kvRows(prefix) {
      if (!prefix) return [];
      return this.kvAll.filter(function(pr) {
        return pr.key && pr.key.indexOf(prefix) === 0 && pr.key.indexOf('surface/') !== 0;
      }).map(function(pr) {
        var v = pr.value;
        var sub = '';
        if (v && typeof v === 'object') {
          sub = v.title || v.status || v.name || '';
          if (!sub) { try { sub = JSON.stringify(v).slice(0, 90); } catch(e) {} }
        } else { sub = String(v).slice(0, 90); }
        return { key: pr.key.slice(prefix.length) || pr.key, sub: sub };
      });
    },

    async deleteSurface(slug) {
      var self = this;
      OpenFangToast.confirm('Delete board', 'Remove this board from Studio? The record is deleted for good.', async function() {
        try {
          var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
          await OpenFangAPI.del('/api/memory/agents/' + agentId + '/kv/' + encodeURIComponent('surface/' + slug));
          OpenFangToast.success('Board deleted');
          self.current = null;
          await self.loadData();
        } catch(e) { OpenFangToast.error(e.message); }
      });
    }
  };
}
