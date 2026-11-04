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
    // A link shown as its own address is marked so it can end in an ellipsis
    // instead of breaking mid-word; the app download becomes a button.
    html = html.replace(/<a href="([^"]*\/download\/staxcloud\.apk)"([^>]*)>[^<]*<\/a>/gi, '<a href="$1"$2 class="link-app">Get the StaxCloud app</a>');
    html = html.replace(/<a href="(https?:\/\/[^"]*)"([^>]*)>(https?:\/\/[^<]*)<\/a>/gi, '<a href="$1"$2 class="link-url">$3</a>');
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
    // A request drafted by an Ask Stax row, placed in the Home composer.
    askDraft: '',
    formsTab: 'forms',
    // A board to open on arrival at Boards.
    boardPick: '',
    smsTab: 'inbox',
    canvasTab: 'canvas',
    canvasPanel: '',
    canvasTopNonce: 0,
    canvasGo(tab) {
      if (this.canvasTab === tab) { this.canvasTopNonce++; return; }
      this.canvasTab = tab;
    },
    canvasPanelToggle(panel) {
      if (this.canvasTab !== 'canvas') this.canvasTab = 'canvas';
      this.canvasPanel = (this.canvasPanel === panel) ? '' : panel;
    },
    // Canvas working state (open design, drafts, per-tab scroll),
    // bound by the canvas page so it survives leaving the module.
    canvasCv: null,
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

    // Record text for display: a missing value renders as nothing, never as
    // its template token ("Draft reply to Marta (<slug>)" -> "Draft reply to Marta").
    plain(t) {
      return String(t || '').replace(/\s*\(\s*(?:<[a-z_-]+>|\{\{?\s*[a-z_-]+\s*\}?\})\s*\)/gi, '')
        .replace(/<[a-z_-]+>|\{\{\s*[a-z_-]+\s*\}\}/gi, '').replace(/\s+([,.;:!?])/g, '$1').replace(/\s{2,}/g, ' ').trim();
    },
    // Card copy with its links live: one line each, ellipsis end, full href.
    plainLinked(t) {
      return escapeHtml(this.plain(t)).replace(/https?:\/\/[^\s<"']*[^\s<"'.,;:!?)\]]/g, '<a class="link-url" href="$&" target="_blank" rel="noopener">$&</a>');
    },

    // A plain short date for list rows ("Nov 2"); nothing when unknown.
    shortDate(ts) {
      var d = ts ? new Date(ts) : null;
      return d && !isNaN(d) ? d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '';
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
        if (pending.length > 0 && signature !== this.lastPendingApprovalSignature && location.hash !== '#approvals' && typeof OpenFangToast !== 'undefined') {
          OpenFangToast.warn('Something is waiting for you in Work.');
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
          // The thread read before sign-in was refused: read the record again
          this.homeReload++;
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
    surfaceOf: { chat: 'home', sms: 'texts', team: 'texts', email: 'texts', approvals: 'work', contacts: 'leads', boards: 'boards', forms: 'studio', library: 'studio', canvas: 'studio', channels: 'system', settings: 'system', advanced: 'advanced' },
    surfaceHome: { home: 'chat', work: 'approvals', boards: 'boards', leads: 'contacts', system: 'settings', advanced: 'advanced' },
    // Pages demoted to System > Advanced. Their page keys are unchanged;
    // only their URL hash carries an advanced/ prefix, so a stale bare
    // bookmark (#agents, #scheduler, ...) lands on home instead.
    // The stock Settings console (configuration) and the integrations
    // catalog (integrations) live here too; 'advanced' itself is the index.
    advancedPages: ['overview', 'agents', 'setup', 'comms', 'logs', 'runtime', 'wizard', 'configuration', 'integrations', 'workflows', 'scheduler', 'hands', 'skills', 'sessions', 'analytics'],
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

      // The browser's own bars (status bar, toolbar) follow the app's theme:
      // the dark background in dark, StaxCloud teal in light.
      var tint = function() {
        var m = document.querySelector('meta[name="theme-color"]');
        if (m) m.setAttribute('content', self.theme === 'dark' ? '#0c0c0e' : '#146e68');
      };
      tint();
      this.$watch('theme', tint);

      // Listen for OS theme changes (only matters when mode is 'system')
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
        if (self.themeMode === 'system') {
          self.theme = e.matches ? 'dark' : 'light';
        }
      });

      // Hash routing
      var validPages = ['overview','chat','agents','sessions','approvals','comms','workflows','scheduler','channels','skills','hands','analytics','logs','runtime','settings','wizard','advanced'];
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
          self.surface = self.surfaceOf[hash] || null;
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

    // The surface the shell chrome (dock highlight) follows.
    surf() {
      return this.surface || this.surfaceOf[this.page] || (this.advancedPages.indexOf(this.page) >= 0 ? 'advanced' : 'home');
    },

    navigate(p) {
      this.page = p;
      window.location.hash = (this.advancedPages.indexOf(p) >= 0 ? 'advanced/' : '') + p;
      this.mobileMenuOpen = false;
      Alpine.store('app').sideOpen = false;
      Alpine.store('app').r4Open = false;
      Alpine.store('app').staxCard = false;
      this.surface = this.surfaceOf[p] || (this.advancedPages.indexOf(p) >= 0 ? 'advanced' : this.surface);
      // The agents template stays mounted when moving between the list and
      // the chat page, so it cannot rely on init alone to open the chat.
      if (p === 'chat') window.dispatchEvent(new CustomEvent('open-chat'));
    },

    goSurface(s) {
      this.navigate(this.surfaceHome[s]);
      this.surface = s;
    },

    // The System corner (Settings, Connections, Advanced and every console
    // under Advanced) carries its own module dock instead of the main one.
    inSystemCorner() {
      var s = this.surf();
      return s === 'system' || s === 'advanced';
    },

    // Agent-first settings: a setting with no owner control is changed by
    // asking Stax. Opens the Stax conversation with the request drafted.
    askStax(text) {
      var store = Alpine.store('app');
      store.staxAgent();
      store.askDraft = text || '';
      store.homeEngage = true;
      this.goSurface('home');
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
    // Channels / Studio / System open collapsed every time the drawer opens.
    // Expanding one lasts only for that visit; nothing is persisted.
    open: { channels: false, studio: false, system: false },
    chats: [],
    loaded: false,
    showAll: false,
    chatLimit: 5,
    busy: false,
    scrolled: false,
    more: false,      // drawer content continues below the fold
    _dragOpened: false,

    initDrawer() {
      var self = this;
      // The Step 2 build remembered expanded sections; drop that key so no
      // stale value lingers on owners' phones.
      try { localStorage.removeItem('stax-drawer-open'); } catch(e) { /* ignore */ }
      this.$watch('$store.app.sideOpen', function(isOpen) {
        if (isOpen) self.placeHeld();
        self.handOffFocus(isOpen);
        if (!isOpen) return;
        if (!self._dragOpened) self.collapseAll();
        self._dragOpened = false;
        self.loadChats();
        self.cue();
      });
      // Sections opening, chats loading, Show all: any change in the one
      // scroll's content re-checks the bottom cue.
      if (window.ResizeObserver) {
        var ro = new ResizeObserver(function() { self.cue(); });
        Array.prototype.forEach.call(this.$el.querySelector('.sd-body').children, function(c) { ro.observe(c); });
      }
      this.initGestures();
    },

    // The menu button held above the open card sits exactly where the page's
    // own menu button is, so a second tap in the same spot closes the card.
    // When that spot would land on the card's wordmark (a mid-width desktop
    // window), it takes the header's leading slot instead (the CSS default).
    placeHeld() {
      var held = document.querySelector('.sd-toggle');
      if (!held) return;
      held.style.left = '';
      held.style.top = '';
      var page = Array.prototype.find.call(document.querySelectorAll('.stax-menu-btn'), function(b) {
        return b !== held && b.offsetParent !== null;
      });
      var brand = this.$el.querySelector('.sd-brand');
      if (!page || !brand) return;
      var r = page.getBoundingClientRect();
      var brandRight = brand.getBoundingClientRect().right - this.$el.getBoundingClientRect().left;
      var far = r.left > 12 && r.left >= brandRight + 8;
      if (r.left <= 12 || far) {
        held.style.left = Math.round(r.left) + 'px';
        held.style.top = Math.round(r.top) + 'px';
      }
      // The header keeps its leading slot free only when the button sits there.
      this.$el.classList.toggle('sd-held-far', far);
    },

    // Keyboard users toggle with the same button: opening from a page's menu
    // button moves focus to the one held above the card; closing from it
    // hands focus back to the page's visible menu button.
    handOffFocus(isOpen) {
      var active = document.activeElement;
      var held = document.querySelector('.sd-toggle');
      if (!held || !active) return;
      if (isOpen && active.classList && active.classList.contains('stax-menu-btn') && active !== held) {
        requestAnimationFrame(function() { held.focus({ preventScroll: true }); });
      } else if (!isOpen && active === held) {
        var page = Array.prototype.find.call(document.querySelectorAll('.stax-menu-btn'), function(b) {
          return b !== held && b.offsetParent !== null;
        });
        if (page) page.focus({ preventScroll: true }); else held.blur();
      }
    },

    // ── Gestures (Round 3) ────────────────────────────────────────────────
    // Pointer Events drive the card; only transform (card) and opacity
    // (dimmed page, held menu button) change while a finger is down.
    //  - Closed: a drag that starts within EDGE px of the left screen edge
    //    and moves mostly sideways pulls the card out under the finger.
    //  - Open: a sideways drag on the card or the dimmed page pushes it back.
    //  - Release: a flick decides; otherwise past THRESHOLD of the card's
    //    width finishes the move, short of it snaps back.
    // Vertical drags are let go at the first decisive move, so scrolling is
    // never taken over; drags starting outside the edge zone on the page are
    // never claimed. With reduced motion asked for, none of this runs: the
    // menu button, the dimmed page and Esc still toggle.
    initGestures() {
      var self = this;
      var aside = this.$el;
      var store = Alpine.store('app');
      var scrim = document.querySelector('.sd-scrim');
      var held = document.querySelector('.sd-toggle');
      if (!aside || !scrim || !window.PointerEvent) return;
      var reduce = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
      var EDGE = 24, SLOP = 10, THRESHOLD = 0.4, FLICK = 0.3; // FLICK in px/ms
      var g = null;   // the gesture in progress
      var raf = 0;

      function clamp(v) { return v < 0 ? 0 : (v > 1 ? 1 : v); }
      function layers() { return held ? [aside, scrim, held] : [aside, scrim]; }
      function paint() {
        raf = 0;
        if (!g || !g.engaged) return;
        aside.style.transform = 'translate3d(' + ((g.p - 1) * g.w).toFixed(1) + 'px,0,0)';
        scrim.style.opacity = g.p.toFixed(3);
        if (held) held.style.opacity = g.p.toFixed(3);
      }
      function clear() {
        if (raf) { cancelAnimationFrame(raf); raf = 0; }
        layers().forEach(function(el) {
          el.classList.remove('is-dragging');
          el.style.transform = '';
          el.style.opacity = '';
        });
        document.body.classList.remove('sd-dragging');
      }
      function isTextField(t) {
        return !!(t && t.closest && t.closest('input, textarea, select, [contenteditable=""], [contenteditable="true"]'));
      }
      function blocked() {
        return store.staxCard || store.r4Open || store.showAuthPrompt;
      }
      // Speed over the last ~100ms of movement, in px/ms. A finger that
      // rested before lifting has no speed left.
      function velocity(samples, upAt) {
        var last = samples[samples.length - 1];
        if (upAt - last[0] > 120) return 0;
        var first = last;
        for (var i = samples.length - 2; i >= 0; i--) {
          if (last[0] - samples[i][0] > 100) break;
          first = samples[i];
        }
        var dt = last[0] - first[0];
        return dt > 0 ? (last[1] - first[1]) / dt : 0;
      }
      // A drag that ends over a row must not also press it.
      function swallowNextClick() {
        var kill = function(ev) { ev.stopPropagation(); ev.preventDefault(); done(); };
        var done = function() { window.removeEventListener('click', kill, true); };
        window.addEventListener('click', kill, true);
        setTimeout(done, 400);
      }
      function settle(open) {
        clear();
        if (open && !store.sideOpen) self._dragOpened = true;
        store.sideOpen = open;
      }

      window.addEventListener('pointerdown', function(e) {
        if (g || reduce.matches || !e.isPrimary) return;
        if (e.pointerType === 'mouse' && e.button !== 0) return;
        var mode;
        if (!store.sideOpen) {
          if (e.clientX > EDGE || blocked() || isTextField(e.target)) return;
          mode = 'open';
        } else {
          if (!(aside.contains(e.target) || e.target === scrim)) return;
          if (isTextField(e.target)) return;
          mode = 'close';
        }
        g = { mode: mode, id: e.pointerId, x0: e.clientX, y0: e.clientY, engaged: false,
              p: mode === 'open' ? 0 : 1, w: aside.getBoundingClientRect().width || 1,
              samples: [[e.timeStamp, e.clientX]] };
      }, { passive: true });

      window.addEventListener('pointermove', function(e) {
        if (!g || e.pointerId !== g.id) return;
        var dx = e.clientX - g.x0, dy = e.clientY - g.y0;
        if (!g.engaged) {
          if (Math.abs(dx) < SLOP && Math.abs(dy) < SLOP) return;
          var sideways = Math.abs(dx) > Math.abs(dy) * 1.2;
          var inward = g.mode === 'open' ? dx > 0 : dx < 0;
          if (!sideways || !inward) { g = null; return; }   // a scroll, or the wrong way: let it be
          g.engaged = true;
          if (g.mode === 'open') { self.collapseAll(); self.placeHeld(); }  // the card arrives as it always opens
          layers().forEach(function(el) { el.classList.add('is-dragging'); });
          document.body.classList.add('sd-dragging');
        }
        g.p = clamp(g.mode === 'open' ? dx / g.w : 1 + dx / g.w);
        g.samples.push([e.timeStamp, e.clientX]);
        if (g.samples.length > 12) g.samples.shift();
        if (!raf) raf = requestAnimationFrame(paint);
      }, { passive: true });

      function release(e, cancelled) {
        if (!g || e.pointerId !== g.id) return;
        var was = g; g = null;
        if (!was.engaged) return;
        if (cancelled) { settle(was.mode === 'close'); return; }
        var v = velocity(was.samples, e.timeStamp);
        var open;
        if (v > FLICK) open = true;
        else if (v < -FLICK) open = false;
        else open = was.mode === 'open' ? was.p >= THRESHOLD : (1 - was.p) < THRESHOLD;
        settle(open);
        swallowNextClick();
      }
      window.addEventListener('pointerup', function(e) { release(e, false); }, { passive: true });
      window.addEventListener('pointercancel', function(e) { release(e, true); }, { passive: true });

      // Once a sideways drag is claimed, keep the browser from starting its
      // own pan for that touch (which would cancel the pointer stream).
      // Nothing is prevented before the claim, so vertical scrolling and
      // every other touch run natively.
      document.addEventListener('touchmove', function(e) {
        if (g && g.engaged && e.cancelable) e.preventDefault();
      }, { passive: false });

      // Anything else that opens or closes the card mid-drag wins.
      this.$watch('$store.app.sideOpen', function() {
        if (g && g.engaged) { g = null; clear(); }
      });
    },

    // Bottom fade while the one scroll continues past the fold.
    cue() {
      var self = this;
      requestAnimationFrame(function() {
        var b = document.querySelector('.stax-side .sd-body');
        self.more = !!b && b.scrollHeight - b.scrollTop - b.clientHeight > 4;
      });
    },

    collapseAll() {
      this.open.channels = false;
      this.open.studio = false;
      this.open.system = false;
      var body = this.$el.querySelector('.sd-body');
      if (body) body.scrollTop = 0;
      this.scrolled = false;
    },

    toggle(k) {
      this.open[k] = !this.open[k];
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
// Glance law (Round B): badges come from one closed set, anything else is
// dropped; a stat value is a number or a short state, anything else is text.
var BOARD_BADGES = { waiting: 'Waiting', doing: 'Doing', done: 'Done', 'needs you': 'Needs you' };
function boardStatOk(v) {
  var s = String(v == null ? '' : v).trim();
  if (/^[-+$€£]?\d[\d,.:]*\s?[%a-z]{0,3}$/i.test(s)) return true;
  return !!s && s.length <= 24 && s.split(/\s+/).length <= 3 && !/[.!?;:]|\b(see|below|above|queue|list|tab|page)\b/i.test(s);
}
function boardAgo(ts) {
  var t = ts ? Date.parse(ts) : NaN;
  if (isNaN(t)) return '';
  var m = Math.max(0, Math.round((Date.now() - t) / 60000));
  return 'updated ' + (m < 1 ? 'just now' : m < 60 ? m + 'm ago' : m < 1440 ? Math.round(m / 60) + 'h ago' : Math.round(m / 1440) + 'd ago');
}
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
              var blocks = Array.isArray(v.blocks) ? v.blocks : [], head = '';
              blocks.some(function(b) {
                return b && b.type === 'stats' && (b.items || []).some(function(it) {
                  if (!it || !it.label || !boardStatOk(it.value)) return false;
                  var val = String(it.value).trim();
                  head = /^\d/.test(val) ? val + ' ' + it.label.charAt(0).toLowerCase() + it.label.slice(1) : it.label + ': ' + val;
                  return true;
                });
              });
              var fresh = boardAgo(v.updated || v.updated_at);
              list.push({ slug: pr.key.slice(8), title: v.title || pr.key.slice(8), blocks: blocks, fresh: fresh, line: [head, fresh].filter(Boolean).join(' · ') });
            }
          }
        });
        list.sort(function(a, b) { return a.title.localeCompare(b.title); });
        this.surfaces = list;
        // Boards' block set is closed: a block type this shell does
        // not render is skipped silently on screen and logged here.
        var knownBlocks = { heading: 1, text: 1, stats: 1, list: 1, kvlist: 1 };
        list.forEach(function(sf) {
          (sf.blocks || []).forEach(function(b) {
            if (b && b.type && !knownBlocks[b.type]) console.warn('[boards] skipped a block this version does not render:', b.type);
          });
        });
        var store = Alpine.store('app');
        if (store.boardPick) {
          var pick = store.boardPick;
          store.boardPick = '';
          if (list.some(function(s) { return s.slug === pick; })) this.current = pick;
        }
        var cur = this.current;
        if (cur && !list.some(function(s) { return s.slug === cur; })) this.current = null;
      } catch(e) {
        this.loadError = e.message || 'Could not load boards.';
      }
      this.loading = false;
    },

    get currentSurface() {
      var c = this.current;
      return this.surfaces.find(function(s) { return s.slug === c; }) || null;
    },

    badge(b) { return BOARD_BADGES[String(b || '').trim().toLowerCase()] || ''; },
    stats(b, ok) { return (b.items || []).filter(function(it) { return it && boardStatOk(it.value) === ok; }); },

    // A kvlist row is a record's own title/name/status. Records without one
    // are counted on one line, never printed; a family's index is not a row.
    kvView(b) {
      var p = b.prefix, noun = String(b.title || 'records').toLowerCase(), rows = [], bare = 0;
      this.kvAll.forEach(function(pr) {
        var k = pr.key || '', v = pr.value;
        if (!p || k.indexOf(p) !== 0 || k.indexOf('surface/') === 0 || /^(index|meta)$/.test(k.slice(p.length))) return;
        if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { v = null; } }
        var o = v && typeof v === 'object' ? v : {}, name = o.title || o.name;
        if (typeof (name || o.status) !== 'string') bare++;
        else rows.push({ key: k, title: name || o.status, sub: name && typeof o.status === 'string' ? o.status.replace(/_/g, ' ') : '' });
      });
      return { rows: rows, count: bare ? bare + ' ' + (rows.length ? 'more ' : '') + noun + ' stored' : '', empty: 'No ' + noun + ' yet — new ' + noun + ' land here.' };
    },
  };
}


// ── Library v1: the shop's records shelf ──────────────────────────────────
// One plain list, newest first, projected from the same kv snapshot Boards
// reads: saved designs (design/<id>: title + updated) and the saved surface
// records (surface/<slug>, live ones only). Families without records behind
// them get no section; a missing date renders as nothing.
function libraryPage() {
  return {
    items: [],
    loading: true,
    loadError: '',

    async loadData() {
      this.loading = true;
      this.loadError = '';
      try {
        var agentId = (Alpine.store('app').agents[0] || {}).id || 'shared';
        var data = await OpenFangAPI.get('/api/memory/agents/' + agentId + '/kv');
        var items = [];
        (data.kv_pairs || []).forEach(function(pr) {
          var k = pr.key || '';
          var v = pr.value;
          if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { v = null; } }
          if (!v || typeof v !== 'object' || v.deleted) return;
          if (k.indexOf('design/') === 0 && k !== 'design/index') {
            items.push({ key: k, title: v.title || k.slice(7), kind: 'Design', when: v.updated || '' });
          } else if (k.indexOf('surface/') === 0) {
            items.push({ key: k, title: v.title || k.slice(8), kind: 'Saved board', when: v.updated || v.updated_at || '' });
          }
        });
        items.sort(function(a, b) { return (b.when ? Date.parse(b.when) : 0) - (a.when ? Date.parse(a.when) : 0); });
        this.items = items;
      } catch(e) {
        this.loadError = 'The shelf did not load. Try again in a moment.';
      }
      this.loading = false;
    },

    fmtDate(ts) {
      var d = ts ? new Date(ts) : null;
      return d && !isNaN(d) ? d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '';
    }
  };
}
