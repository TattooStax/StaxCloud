// OpenFang Chat Page — Agent chat with markdown + streaming
'use strict';

// A tool call the model wrote out as text was never run: not a message.
function isToolCallText(t) {
  t = String(t || '').trim().replace(/^```(?:json)?\s*|\s*```$/g, '');
  if (!/^[[{]/.test(t)) return false;
  try { var o = JSON.parse(t); } catch(e) { return false; }
  if (Array.isArray(o)) o = o[0];
  return !!(o && typeof o.name === 'string' && (o.parameters || o.arguments || o.input));
}

// Turns of the stored record: an owner turn with no worded reply before the
// next is `unfinished`; kernel prompts, the tick's exchange, text tool calls
// and the silent marker are `machine` rows, left out without losing a turn.
function markTurns(rows) {
  var turn = null, tick = false;
  function close() { if (turn && !turn.answered) turn.unfinished = true; }
  rows.forEach(function(r) {
    var t = (r.text || '').trim();
    if (r.role === 'user') {
      if (/^\[AUTONOMOUS TICK\]/.test(t)) { close(); turn = null; tick = true; r.machine = true; }
      else if (/^\[System:/.test(t)) r.machine = true;
      else { close(); turn = r; tick = false; }
      return;
    }
    var silent = t === '[no reply needed]';
    if (tick || silent || isToolCallText(t)) r.machine = true;
    if (!turn) return;
    if (silent || (!r.machine && (t || r.tools.some(function(x) { return x._imageUrls; })))) turn.answered = true;
  });
  close();
}
function chatPage() {
  var msgId = 0;
  return {
    currentAgent: null,
    messages: [],
    inputText: '',
    sending: false,
    messageQueue: [],    // Queue for messages sent while streaming
    thinkingMode: 'off', // 'off' | 'on' | 'stream'
    _wsAgent: null,
    showSlashMenu: false,
    slashFilter: '',
    slashIdx: 0,
    attachments: [],
    _shown: {},          // photos shown with a stored turn this visit (turn-scoped)
    dragOver: false,
    _typingTimeout: null,
    // Multi-session state
    sessions: [],
    sessionsOpen: false,
    searchOpen: false,
    searchQuery: '',
    // Voice recording state
    recording: false,
    _mediaRecorder: null,
    _audioChunks: [],
    recordingTime: 0,
    _recordingTimer: null,
    // Model autocomplete state
    showModelPicker: false,
    modelPickerList: [],
    modelPickerFilter: '',
    modelPickerIdx: 0,
    // Model switcher dropdown
    showModelSwitcher: false,
    modelSwitcherFilter: '',
    modelSwitcherProviderFilter: '',
    modelSwitcherIdx: 0,
    modelSwitching: false,
    _modelCache: null,
    _modelCacheTime: 0,
    slashCommands: [], // Loaded dynamically with i18n in init()
    _slashCommandsLoaded: false,
    tokenCount: 0,

    // ── Tip Bar ──
    tipIndex: 0,
    tips: [],
    _tipsInitialized: false,
    tipTimer: null,
    get currentTip() {
      if (localStorage.getItem('of-tips-off') === 'true') return '';
      if (!this._tipsInitialized) {
        var t = typeof window.t === 'function' ? window.t : function(s) { return s; };
        this.tips = [
          t('tips.commands'),
          t('tips.think'),
          t('tips.focus'),
          'Drag files to attach',
          '/model to switch models',
          '/context to check usage',
          '/verbose off to hide tool details'
        ];
        this._tipsInitialized = true;
      }
      return this.tips[this.tipIndex % this.tips.length] || '';
    },
    dismissTips: function() { localStorage.setItem('of-tips-off', 'true'); },
    startTipCycle: function() {
      var self = this;
      if (this.tipTimer) clearInterval(this.tipTimer);
      this.tipTimer = setInterval(function() {
        self.tipIndex = (self.tipIndex + 1) % self.tips.length;
      }, 30000);
    },

    get modelDisplayName() {
      if (!this.currentAgent) return '';
      var name = this.currentAgent.model_name || '';
      var short = name.replace(/-\d{8}$/, '');
      return short.length > 24 ? short.substring(0, 22) + '\u2026' : short;
    },

    get switcherProviders() {
      var seen = {};
      (this._modelCache || []).forEach(function(m) { seen[m.provider] = true; });
      return Object.keys(seen).sort();
    },

    get filteredSwitcherModels() {
      var models = this._modelCache || [];
      var provFilter = this.modelSwitcherProviderFilter;
      var textFilter = this.modelSwitcherFilter ? this.modelSwitcherFilter.toLowerCase() : '';
      if (!provFilter && !textFilter) return models;
      return models.filter(function(m) {
        if (provFilter && m.provider !== provFilter) return false;
        if (textFilter) {
          return m.id.toLowerCase().indexOf(textFilter) !== -1 ||
                 (m.display_name || '').toLowerCase().indexOf(textFilter) !== -1 ||
                 m.provider.toLowerCase().indexOf(textFilter) !== -1;
        }
        return true;
      });
    },

    get groupedSwitcherModels() {
      var filtered = this.filteredSwitcherModels;
      var groups = {}, order = [];
      filtered.forEach(function(m) {
        if (!groups[m.provider]) { groups[m.provider] = []; order.push(m.provider); }
        groups[m.provider].push(m);
      });
      return order.map(function(p) {
        return { provider: p.charAt(0).toUpperCase() + p.slice(1), models: groups[p] };
      });
    },

    init() {
      var self = this;

      // Initialize slash commands with i18n
      this.initSlashCommands();

      // Start tip cycle
      this.startTipCycle();

      // Fetch dynamic commands from server
      this.fetchCommands();

      // Observe DOM for new messages and render LaTeX
      this._latexObserver = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
          mutation.addedNodes.forEach(function(node) {
            if (node.nodeType === Node.ELEMENT_NODE) {
              var bubbles = node.querySelector ? node.querySelectorAll('.message-bubble') : [];
              if (node.classList && node.classList.contains('message-bubble')) {
                bubbles = [node];
              }
              bubbles.forEach(function(bubble) {
                if (bubble.textContent && hasLatexDelimiters(bubble.textContent)) {
                  renderLatex(bubble);
                }
              });
            }
          });
        });
      });
      this._latexObserver.observe(document.getElementById('messages') || document.body, {
        childList: true,
        subtree: true
      });

      // Ctrl+/ keyboard shortcut
      document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === '/') {
          e.preventDefault();
          var input = document.getElementById('msg-input');
          if (input) { input.focus(); self.inputText = '/'; }
        }
        // Ctrl+M for model switcher
        if ((e.ctrlKey || e.metaKey) && e.key === 'm' && self.currentAgent) {
          e.preventDefault();
          self.toggleModelSwitcher();
        }
        // Ctrl+F for chat search
        if ((e.ctrlKey || e.metaKey) && e.key === 'f' && self.currentAgent) {
          e.preventDefault();
          self.toggleSearch();
        }
      });

      // Load session + session list when agent changes
      this.$watch('currentAgent', function(agent) {
        if (agent) {
          self.loadSession(agent.id);
          self.loadSessions(agent.id);
        }
      });

      // Check for pending agent from Agents page (set before chat mounted)
      var store = Alpine.store('app');
      if (store.pendingAgent) {
        self.selectAgent(store.pendingAgent);
        store.pendingAgent = null;
      } else {
        // Restore previously active agent after page refresh (#1179).
        // The agent list may not be loaded yet, so resolve once it appears.
        self._restoreActiveAgent();
      }

      // Watch for future pending agent selections (e.g., user clicks agent while on chat)
      this.$watch('$store.app.pendingAgent', function(agent) {
        if (agent) {
          self.selectAgent(agent);
          Alpine.store('app').pendingAgent = null;
        }
      });

      // Re-attempt restore once the agent list arrives from the server
      this.$watch('$store.app.agents', function(agents) {
        if (!self.currentAgent && agents && agents.length) {
          self._restoreActiveAgent();
        }
      });

      // Watch for slash commands + model autocomplete
      this.$watch('inputText', function(val) {
        var modelMatch = val.match(/^\/model\s+(.*)$/i);
        if (modelMatch) {
          self.showSlashMenu = false;
          self.modelPickerFilter = modelMatch[1].toLowerCase();
          if (!self.modelPickerList.length) {
            OpenFangAPI.get('/api/models').then(function(data) {
              self.modelPickerList = (data.models || []).filter(function(m) { return m.available; });
              self.showModelPicker = true;
              self.modelPickerIdx = 0;
            }).catch(function() {});
          } else {
            self.showModelPicker = true;
          }
        } else if (val.startsWith('/')) {
          self.showModelPicker = false;
          self.slashFilter = val.slice(1).toLowerCase();
          self.showSlashMenu = true;
          self.slashIdx = 0;
        } else {
          self.showSlashMenu = false;
          self.showModelPicker = false;
        }
      });
    },

    get filteredModelPicker() {
      if (!this.modelPickerFilter) return this.modelPickerList.slice(0, 15);
      var f = this.modelPickerFilter;
      return this.modelPickerList.filter(function(m) {
        return m.id.toLowerCase().indexOf(f) !== -1 || (m.display_name || '').toLowerCase().indexOf(f) !== -1 || m.provider.toLowerCase().indexOf(f) !== -1;
      }).slice(0, 15);
    },

    pickModel(modelId) {
      this.showModelPicker = false;
      this.inputText = '/model ' + modelId;
      this.sendMessage();
    },

    toggleModelSwitcher() {
      if (this.showModelSwitcher) { this.showModelSwitcher = false; return; }
      var self = this;
      var now = Date.now();
      if (this._modelCache && (now - this._modelCacheTime) < 300000) {
        this.modelSwitcherFilter = '';
        this.modelSwitcherProviderFilter = '';
        this.modelSwitcherIdx = 0;
        this.showModelSwitcher = true;
        this.$nextTick(function() {
          var el = document.getElementById('model-switcher-search');
          if (el) el.focus();
        });
        return;
      }
      OpenFangAPI.get('/api/models').then(function(data) {
        var models = (data.models || []).filter(function(m) { return m.available; });
        self._modelCache = models;
        self._modelCacheTime = Date.now();
        self.modelPickerList = models;
        self.modelSwitcherFilter = '';
        self.modelSwitcherProviderFilter = '';
        self.modelSwitcherIdx = 0;
        self.showModelSwitcher = true;
        self.$nextTick(function() {
          var el = document.getElementById('model-switcher-search');
          if (el) el.focus();
        });
      }).catch(function(e) {
        OpenFangToast.error('Failed to load models: ' + e.message);
      });
    },

    switchModel(model) {
      if (!this.currentAgent) return;
      if (model.id === this.currentAgent.model_name) { this.showModelSwitcher = false; return; }
      var self = this;
      this.modelSwitching = true;
      var t = typeof window.t === 'function' ? window.t : function(s) { return s; };
      OpenFangAPI.put('/api/agents/' + this.currentAgent.id + '/model', { model: model.id }).then(function(resp) {
        // Use server-resolved model/provider to stay in sync (fixes #387/#466)
        self.currentAgent.model_name = (resp && resp.model) || model.id;
        self.currentAgent.model_provider = (resp && resp.provider) || model.provider;
        OpenFangToast.success(t('chat.model_switched') + ' ' + (model.display_name || model.id));
        self.showModelSwitcher = false;
        self.modelSwitching = false;
      }).catch(function(e) {
        OpenFangToast.error(t('chat.model_switch_failed') + ': ' + e.message);
        self.modelSwitching = false;
      });
    },

    // Initialize slash commands with i18n translations
    initSlashCommands: function() {
      if (this._slashCommandsLoaded) return;
      var t = typeof window.t === 'function' ? window.t : function(s) { return s; };
      this.slashCommands = [
        { cmd: '/help', desc: t('chat.slash.help') },
        { cmd: '/agents', desc: t('chat.slash.agents') },
        { cmd: '/new', desc: t('chat.slash.new') },
        { cmd: '/compact', desc: t('chat.slash.compact') },
        { cmd: '/model', desc: t('chat.slash.model') },
        { cmd: '/stop', desc: t('chat.slash.stop') },
        { cmd: '/usage', desc: t('chat.slash.usage') },
        { cmd: '/think', desc: t('chat.slash.think') },
        { cmd: '/context', desc: t('chat.slash.context') },
        { cmd: '/verbose', desc: t('chat.slash.verbose') },
        { cmd: '/queue', desc: t('chat.slash.queue') },
        { cmd: '/status', desc: t('chat.slash.status') },
        { cmd: '/clear', desc: t('chat.slash.clear') },
        { cmd: '/exit', desc: t('chat.slash.exit') },
        { cmd: '/budget', desc: t('chat.slash.budget') },
        { cmd: '/peers', desc: t('chat.slash.peers') },
        { cmd: '/a2a', desc: t('chat.slash.a2a') }
      ];
      this._slashCommandsLoaded = true;
    },

    // Fetch slash commands from the unified registry (/api/commands?surface=web).
    // Replaces the hardcoded initSlashCommands() list once loaded — ensures
    // the help panel and autocomplete stay in sync with the backend registry.
    fetchCommands: function() {
      var self = this;
      OpenFangAPI.get('/api/commands?surface=web').then(function(data) {
        var cmds = (data && data.commands) || [];
        if (!cmds.length) return;
        self.slashCommands = cmds.map(function(c) {
          // Prefer unified-registry shape { name, aliases, description, category, requires_agent }.
          // Fall back to legacy { cmd, desc } shape so older shims keep working.
          if (c.name) {
            return {
              cmd: '/' + c.name,
              desc: c.description || '',
              category: c.category || 'general',
              aliases: c.aliases || [],
              requires_agent: !!c.requires_agent,
              source: 'registry'
            };
          }
          return {
            cmd: c.cmd,
            desc: c.desc || '',
            category: c.category || 'general',
            aliases: c.aliases || [],
            requires_agent: !!c.requires_agent,
            source: c.source || 'server'
          };
        });
        self._slashCommandsLoaded = true;
      }).catch(function() { /* silent — keep hardcoded fallback list */ });
    },

    get filteredSlashCommands() {
      if (!this.slashFilter) return this.slashCommands;
      var f = this.slashFilter;
      return this.slashCommands.filter(function(c) {
        return c.cmd.toLowerCase().indexOf(f) !== -1 || c.desc.toLowerCase().indexOf(f) !== -1;
      });
    },

    // Render `/help` output grouped by category, mirroring the
    // backend's render_help(Surfaces::WEB). Falls back to a flat list if
    // categories are not populated (pre-fetch hardcoded list).
    renderHelpText: function() {
      var order = ['general', 'session', 'model', 'control', 'memory', 'info', 'automation', 'monitoring'];
      var labels = {
        general: 'General', session: 'Session', model: 'Model', control: 'Control',
        memory: 'Memory', info: 'Info', automation: 'Automation', monitoring: 'Monitoring'
      };
      var anyCategorised = this.slashCommands.some(function(c) { return c.category; });
      if (!anyCategorised) {
        return this.slashCommands.map(function(c) {
          return '`' + c.cmd + '` \u2014 ' + c.desc;
        }).join('\n');
      }
      var groups = {};
      this.slashCommands.forEach(function(c) {
        var cat = c.category || 'general';
        if (!groups[cat]) groups[cat] = [];
        groups[cat].push(c);
      });
      var lines = ['**Available commands:**'];
      order.forEach(function(cat) {
        var list = groups[cat];
        if (!list || !list.length) return;
        lines.push('');
        lines.push('**' + (labels[cat] || cat) + '**');
        list.forEach(function(c) {
          var aliasText = '';
          if (c.aliases && c.aliases.length) {
            aliasText = ' (aliases: ' + c.aliases.map(function(a) { return '/' + a; }).join(', ') + ')';
          }
          lines.push('- `' + c.cmd + '`' + aliasText + ' \u2014 ' + c.desc);
        });
      });
      return lines.join('\n');
    },

    // A turn quiet for 120s is settled against the record
    _resetTypingTimeout: function() {
      var self = this;
      if (self._typingTimeout) clearTimeout(self._typingTimeout);
      self._typingTimeout = setTimeout(function() { self._settle('fail'); }, 120000);
    },

    _clearTypingTimeout: function() {
      if (this._typingTimeout) {
        clearTimeout(this._typingTimeout);
        this._typingTimeout = null;
      }
    },

    executeSlashCommand(cmd, cmdArgs) {
      this.showSlashMenu = false;
      this.inputText = '';
      var self = this;
      cmdArgs = cmdArgs || '';
      switch (cmd) {
        case '/help':
          self.messages.push({ id: ++msgId, role: 'system', text: self.renderHelpText(), meta: '', tools: [] });
          self.scrollToBottom();
          break;
        case '/agents':
          location.hash = 'agents';
          break;
        case '/new':
          if (self.currentAgent) {
            OpenFangAPI.post('/api/agents/' + self.currentAgent.id + '/session/reset', {}).then(function() {
              self.messages = [];
              OpenFangToast.success('Session reset');
            }).catch(function(e) { OpenFangToast.error('Reset failed: ' + e.message); });
          }
          break;
        case '/compact':
          if (self.currentAgent) {
            self.messages.push({ id: ++msgId, role: 'system', text: 'Compacting session...', meta: '', tools: [] });
            OpenFangAPI.post('/api/agents/' + self.currentAgent.id + '/session/compact', {}).then(function(res) {
              self.messages.push({ id: ++msgId, role: 'system', text: res.message || 'Compaction complete', meta: '', tools: [] });
              self.scrollToBottom();
            }).catch(function(e) { OpenFangToast.error('Compaction failed: ' + e.message); });
          }
          break;
        case '/stop':
          if (self.currentAgent) {
            OpenFangAPI.post('/api/agents/' + self.currentAgent.id + '/stop', {}).then(function(res) {
              self.messages.push({ id: ++msgId, role: 'system', text: res.message || 'Run cancelled', meta: '', tools: [] });
              self.sending = false;
              self.scrollToBottom();
            }).catch(function(e) { OpenFangToast.error('Stop failed: ' + e.message); });
          }
          break;
        case '/usage':
          if (self.currentAgent) {
            var approxTokens = self.messages.reduce(function(sum, m) { return sum + Math.round((m.text || '').length / 4); }, 0);
            self.messages.push({ id: ++msgId, role: 'system', text: '**Session Usage**\n- Messages: ' + self.messages.length + '\n- Approx tokens: ~' + approxTokens, meta: '', tools: [] });
            self.scrollToBottom();
          }
          break;
        case '/think':
          if (cmdArgs === 'on') {
            self.thinkingMode = 'on';
          } else if (cmdArgs === 'off') {
            self.thinkingMode = 'off';
          } else if (cmdArgs === 'stream') {
            self.thinkingMode = 'stream';
          } else {
            // Cycle: off -> on -> stream -> off
            if (self.thinkingMode === 'off') self.thinkingMode = 'on';
            else if (self.thinkingMode === 'on') self.thinkingMode = 'stream';
            else self.thinkingMode = 'off';
          }
          var modeLabel = self.thinkingMode === 'stream' ? 'enabled (streaming reasoning)' : (self.thinkingMode === 'on' ? 'enabled' : 'disabled');
          self.messages.push({ id: ++msgId, role: 'system', text: 'Extended thinking **' + modeLabel + '**. ' +
            (self.thinkingMode === 'stream' ? 'Reasoning tokens will appear in a collapsible panel.' :
             self.thinkingMode === 'on' ? 'The agent will show its reasoning when supported by the model.' :
             'Normal response mode.'), meta: '', tools: [] });
          self.scrollToBottom();
          break;
        case '/context':
          // Send via WS command
          if (self.currentAgent && OpenFangAPI.isWsConnected()) {
            OpenFangAPI.wsSend({ type: 'command', command: 'context', args: '' });
          } else {
            self.messages.push({ id: ++msgId, role: 'system', text: 'Not connected (' + (OpenFangAPI.getConnectionState ? OpenFangAPI.getConnectionState() : 'unknown') + '). Pick an agent or check that your session is still valid.', meta: '', tools: [] });
            self.scrollToBottom();
          }
          break;
        case '/verbose':
          if (self.currentAgent && OpenFangAPI.isWsConnected()) {
            OpenFangAPI.wsSend({ type: 'command', command: 'verbose', args: cmdArgs });
          } else {
            self.messages.push({ id: ++msgId, role: 'system', text: 'Not connected (' + (OpenFangAPI.getConnectionState ? OpenFangAPI.getConnectionState() : 'unknown') + '). Pick an agent or check that your session is still valid.', meta: '', tools: [] });
            self.scrollToBottom();
          }
          break;
        case '/queue':
          if (self.currentAgent && OpenFangAPI.isWsConnected()) {
            OpenFangAPI.wsSend({ type: 'command', command: 'queue', args: '' });
          } else {
            self.messages.push({ id: ++msgId, role: 'system', text: 'Not connected (' + (OpenFangAPI.getConnectionState ? OpenFangAPI.getConnectionState() : 'unknown') + ').', meta: '', tools: [] });
            self.scrollToBottom();
          }
          break;
        case '/status':
          OpenFangAPI.get('/api/status').then(function(s) {
            self.messages.push({ id: ++msgId, role: 'system', text: '**System Status**\n- Agents: ' + (s.agent_count || 0) + '\n- Uptime: ' + (s.uptime_seconds || 0) + 's\n- Version: ' + (s.version || '?'), meta: '', tools: [] });
            self.scrollToBottom();
          }).catch(function() {});
          break;
        case '/model':
          if (self.currentAgent) {
            if (cmdArgs) {
              OpenFangAPI.put('/api/agents/' + self.currentAgent.id + '/model', { model: cmdArgs }).then(function(resp) {
                // Use server-resolved model/provider (fixes #387/#466)
                var resolvedModel = (resp && resp.model) || cmdArgs;
                var resolvedProvider = (resp && resp.provider) || '';
                self.currentAgent.model_name = resolvedModel;
                if (resolvedProvider) { self.currentAgent.model_provider = resolvedProvider; }
                self.messages.push({ id: ++msgId, role: 'system', text: 'Model switched to: `' + resolvedModel + '`' + (resolvedProvider ? ' (provider: `' + resolvedProvider + '`)' : ''), meta: '', tools: [] });
                self.scrollToBottom();
              }).catch(function(e) { OpenFangToast.error('Model switch failed: ' + e.message); });
            } else {
              self.messages.push({ id: ++msgId, role: 'system', text: '**Current Model**\n- Provider: `' + (self.currentAgent.model_provider || '?') + '`\n- Model: `' + (self.currentAgent.model_name || '?') + '`', meta: '', tools: [] });
              self.scrollToBottom();
            }
          } else {
            self.messages.push({ id: ++msgId, role: 'system', text: 'No agent selected.', meta: '', tools: [] });
            self.scrollToBottom();
          }
          break;
        case '/clear':
          self.messages = [];
          break;
        case '/exit':
          OpenFangAPI.wsDisconnect();
          self._wsAgent = null;
          self.currentAgent = null;
          self.messages = [];
          try { localStorage.removeItem('of-active-agent'); } catch(e) { /* ignore */ }
          window.dispatchEvent(new Event('close-chat'));
          break;
        case '/budget':
          OpenFangAPI.get('/api/budget').then(function(b) {
            var fmt = function(v) { return v > 0 ? '$' + v.toFixed(2) : 'unlimited'; };
            self.messages.push({ id: ++msgId, role: 'system', text: '**Budget Status**\n' +
              '- Hourly: $' + (b.hourly_spend||0).toFixed(4) + ' / ' + fmt(b.hourly_limit) + '\n' +
              '- Daily: $' + (b.daily_spend||0).toFixed(4) + ' / ' + fmt(b.daily_limit) + '\n' +
              '- Monthly: $' + (b.monthly_spend||0).toFixed(4) + ' / ' + fmt(b.monthly_limit), meta: '', tools: [] });
            self.scrollToBottom();
          }).catch(function() {});
          break;
        case '/peers':
          OpenFangAPI.get('/api/network/status').then(function(ns) {
            self.messages.push({ id: ++msgId, role: 'system', text: '**OFP Network**\n' +
              '- Status: ' + (ns.enabled ? 'Enabled' : 'Disabled') + '\n' +
              '- Connected peers: ' + (ns.connected_peers||0) + ' / ' + (ns.total_peers||0), meta: '', tools: [] });
            self.scrollToBottom();
          }).catch(function() {});
          break;
        case '/a2a':
          OpenFangAPI.get('/api/a2a/agents').then(function(res) {
            var agents = res.agents || [];
            if (!agents.length) {
              self.messages.push({ id: ++msgId, role: 'system', text: 'No external A2A agents discovered.', meta: '', tools: [] });
            } else {
              var lines = agents.map(function(a) { return '- **' + a.name + '** — ' + a.url; });
              self.messages.push({ id: ++msgId, role: 'system', text: '**A2A Agents (' + agents.length + ')**\n' + lines.join('\n'), meta: '', tools: [] });
            }
            self.scrollToBottom();
          }).catch(function() {});
          break;
      }
    },

    // Restore the previously-active agent (set in selectAgent) after a page
    // refresh, so the WebSocket re-attaches to the same session and any
    // in-flight tool output streams back into the chat (#1179).
    _restoreActiveAgent: function() {
      var storedId = null;
      try { storedId = localStorage.getItem('of-active-agent'); } catch(e) { /* ignore */ }
      if (!storedId) {
        // One Face default: land on Stax, the lead.
        var all = (Alpine.store('app') && Alpine.store('app').agents) || [];
        for (var j = 0; j < all.length; j++) {
          if (all[j] && all[j].name === 'stax') { this.selectAgent(all[j]); return; }
        }
        return;
      }
      var agents = (Alpine.store('app') && Alpine.store('app').agents) || [];
      var match = null;
      for (var i = 0; i < agents.length; i++) {
        if (agents[i] && agents[i].id === storedId) { match = agents[i]; break; }
      }
      if (match) {
        this.selectAgent(match);
      }
    },

    selectAgent(agent) {
      this.currentAgent = agent;
      this.messages = [];
      try { localStorage.setItem('of-active-agent', agent.id); } catch(e) { /* ignore */ }
      this.connectWs(agent.id);
      var t = typeof window.t === 'function' ? window.t : function(s) { return s; };
      // Show welcome tips on first use
      if (!localStorage.getItem('of-chat-tips-seen')) {
        this.messages.push({
          id: ++msgId,
          role: 'system',
          text: t('chat.welcome_message'),
          meta: '',
          tools: []
        });
        localStorage.setItem('of-chat-tips-seen', 'true');
      }
      // Focus input after agent selection, except on touch screens, where it
      // would throw the keyboard over the page on arrival.
      var self = this;
      this.$nextTick(function() {
        var el = document.getElementById('msg-input');
        if (el && !(window.matchMedia && window.matchMedia('(pointer: coarse)').matches)) el.focus();
      });
    },

    // The thread is the stored session, whole and in order; `after` (rows
    // still in flight) goes below it. Returns the rows, or null if unread.
    async loadSession(agentId, after) {
      var self = this;
      try {
        var data = await OpenFangAPI.get('/api/agents/' + agentId + '/session');
        if (self.currentAgent && self.currentAgent.id !== agentId) return null;
        // #935: never render system-role rows, even if the backend sends one
        var rows = (data.messages || []).filter(function(m) {
          return m && m.role !== 'System' && m.role !== 'system';
        }).map(function(m) {
          var text = self.sanitizeToolText(typeof m.content === 'string' ? m.content : JSON.stringify(m.content));
          var tools = (m.tools || []).map(function(t, idx) {
            var tool = { id: (t.name || 'tool') + '-hist-' + idx, name: t.name || 'unknown', running: false,
              expanded: true, input: t.input || '', result: t.result || '', is_error: !!t.is_error };
            try { var r = JSON.parse(tool.result); if (r.image_urls && r.image_urls.length && !tool.is_error) tool._imageUrls = r.image_urls; } catch(e) { /* not JSON */ }
            return tool;
          });
          var images = (m.images || []).map(function(img) {
            return { file_id: img.file_id, filename: img.filename || 'image' };
          });
          return { id: ++msgId, role: m.role === 'User' ? 'user' : 'agent', text: text, meta: '', tools: tools, images: images };
        });
        // This visit's photos go back on their own turns, latest send on the latest row
        var left = {};
        for (var k in self._shown) left[k] = self._shown[k].slice();
        rows.slice().reverse().forEach(function(r) {
          var s = r.role === 'user' && !r.images.length && left[r.text] && left[r.text].pop();
          if (s) { r.images = s.images; r.unseen = s.unseen; }
        });
        markTurns(rows);
        self._storedCount = data.raw_message_count != null ? data.raw_message_count : (data.message_count || 0);
        if (rows.length || after) self.messages = rows.concat(after || []);
        self.$nextTick(function() { self.scrollToBottom(); });
        return rows;
      } catch(e) { return null; }
    },

    // Rebuild from the record; a turn in flight settles only if it is stored.
    rehydrate() {
      if (!this.currentAgent) return;
      if (this.sending) this._settle('check');
      else this.loadSession(this.currentAgent.id);
    },

    // A turn ended ('end' | 'fail') or may have ('check'): the placeholders
    // give way to the record; a send it doesn't hold is shown as not saved.
    async _settle(how) {
      var turn = this._turn, agent = this.currentAgent;
      if (this._settling || !agent || (!turn && this.sending)) return;
      this._settling = true;
      this._clearTypingTimeout();
      // A cancelled run can still be finishing its save.
      if (how === 'fail') await new Promise(function(r) { setTimeout(r, 600); });
      if (this._turn !== turn) { this._settling = false; return; }
      var before = this._storedCount, live = this.messages;
      // Below the record: queued sends, and on a repeat end signal the note
      var below = live.filter(function(m) { return m.interrupted && !turn; }).concat(this.messageQueue.map(function(q) {
        return { id: ++msgId, role: 'user', text: q.text, meta: '', tools: [], images: q.images || [], pending: true };
      }));
      var rows = await this.loadSession(agent.id, below);
      var users = (rows || []).filter(function(r) { return r.role === 'user' && !r.machine; });
      var last = users[users.length - 1];
      function holds(text) { return !!(last && last.text.indexOf(text.trim()) === 0); }
      var kept = !!(turn && this._storedCount !== before && holds(turn.text));
      if (how === 'check' && !(kept && !last.unfinished)) {
        if (rows) { this.messages = live; this._storedCount = before; }
        this._settling = false;
        return;
      }
      this._turn = null;
      if (rows) this.messages = this.messages.filter(function(m) { return !(m.interrupted && holds(m.turnText)); });
      if (kept && turn.images.length) {
        var shown = { images: turn.images, unseen: !!turn.unseen }, row = this.messages.find(function(m) { return m.id === last.id; });
        (this._shown[last.text] = this._shown[last.text] || []).push(shown);
        Object.assign(row, shown);
      }
      if (turn && !kept) {
        var words = turn.text.replace(/\n?\[File: [^\]\n]*\]/g, '').trim(), back = rows && words && !this.inputText;
        if (!rows) this.messages = live.filter(function(m) { return !m.thinking && !m.streaming; });
        this.messages.push({ id: ++msgId, role: 'system', interrupted: true, turnText: turn.text, meta: '', tools: [], text: rows
          ? (this._stopped ? 'Stopped before I finished' : 'That one didn\u2019t go through') + ', so it isn\u2019t saved.' + (back ? ' Your words are back in the box.' : '') + (turn.images.length ? ' Add the photo again when you send it.' : '')
          : 'I couldn\u2019t check whether that one was saved. I\u2019ll look again when the connection is back.' });
        if (back) {
          this.inputText = words;
          this.$nextTick(function() { var ta = document.getElementById('msg-input'); if (ta) { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 150) + 'px'; } });
        }
      }
      this.sending = this._stopped = false;
      this.tokenCount = 0;
      this._settling = false;
      this.scrollToBottom();
      var self = this;
      setTimeout(function() { self._processQueue(); }, 300);
    },

    // Multi-session: load session list for current agent
    async loadSessions(agentId) {
      try {
        var data = await OpenFangAPI.get('/api/agents/' + agentId + '/sessions');
        this.sessions = data.sessions || [];
      } catch(e) { this.sessions = []; }
    },

    // Multi-session: create a new session
    async createSession() {
      if (!this.currentAgent) return;
      var t = typeof window.t === 'function' ? window.t : function(s) { return s; };
      var label = prompt(t('chat.session_name_prompt'));
      if (label === null) return; // cancelled
      try {
        await OpenFangAPI.post('/api/agents/' + this.currentAgent.id + '/sessions', {
          label: label.trim() || undefined
        });
        await this.loadSessions(this.currentAgent.id);
        await this.loadSession(this.currentAgent.id);
        this.messages = [];
        this.scrollToBottom();
        if (typeof OpenFangToast !== 'undefined') OpenFangToast.success(t('chat.session_created'));
      } catch(e) {
        if (typeof OpenFangToast !== 'undefined') OpenFangToast.error(t('chat.session_create_failed'));
      }
    },

    // Multi-session: switch to an existing session
    async switchSession(sessionId) {
      if (!this.currentAgent) return;
      try {
        await OpenFangAPI.post('/api/agents/' + this.currentAgent.id + '/sessions/' + sessionId + '/switch', {});
        this.messages = [];
        await this.loadSession(this.currentAgent.id);
        await this.loadSessions(this.currentAgent.id);
        // Reconnect WebSocket for new session
        this._wsAgent = null;
        this.connectWs(this.currentAgent.id);
      } catch(e) {
        if (typeof OpenFangToast !== 'undefined') OpenFangToast.error('Failed to switch session');
      }
    },

    connectWs(agentId) {
      if (this._wsAgent === agentId) return;
      this._wsAgent = agentId;
      var self = this;

      OpenFangAPI.wsConnect(agentId, {
        onOpen: function() {
          Alpine.store('app').wsConnected = true;
          // (Re)connected, e.g. after sign-in or a dropped line: read the record
          self.rehydrate();
        },
        onMessage: function(data) { self.handleWsMessage(data); },
        onClose: function() {
          Alpine.store('app').wsConnected = false;
          self._wsAgent = null;
        },
        onError: function() {
          Alpine.store('app').wsConnected = false;
          self._wsAgent = null;
        }
      });
    },

    handleWsMessage(data) {
      switch (data.type) {
        case 'connected': break;

        // Incoming message from server (e.g., cron trigger) — display as user message
        case 'message':
          if (data.content) {
            var meta = data.source === 'cron' ? '[Scheduled: ' + (data.job_name || data.job_id || '') + ']' : '';
            this.messages.push({ id: ++msgId, role: 'user', text: data.content, meta: meta, tools: [], images: [], ts: Date.now() });
            this.scrollToBottom();
          }
          break;

        // Legacy thinking event (backward compat)
        case 'thinking':
          if (!this.messages.length || !this.messages[this.messages.length - 1].thinking) {
            var thinkLabel = data.level ? 'Thinking (' + data.level + ')...' : 'Processing...';
            this.messages.push({ id: ++msgId, role: 'agent', text: thinkLabel, meta: '', thinking: true, streaming: true, tools: [] });
            this.scrollToBottom();
            this._resetTypingTimeout();
          } else if (data.level) {
            var thinkIdx = this.messages.length - 1;
            var lastThink = thinkIdx >= 0 ? this.messages[thinkIdx] : null;
            if (lastThink && lastThink.thinking) {
              lastThink.text = 'Thinking (' + data.level + ')...';
              this.messages.splice(thinkIdx, 1, lastThink);
            }
          }
          break;

        // New typing lifecycle
        case 'typing':
          if (data.state === 'start') {
            if (!this.messages.length || !this.messages[this.messages.length - 1].thinking) {
              this.messages.push({ id: ++msgId, role: 'agent', text: 'Processing...', meta: '', thinking: true, streaming: true, tools: [] });
              this.scrollToBottom();
            }
            this._resetTypingTimeout();
          } else if (data.state === 'tool') {
            var toolTypIdx = this.messages.length - 1;
            var typingMsg = toolTypIdx >= 0 ? this.messages[toolTypIdx] : null;
            if (typingMsg && (typingMsg.thinking || typingMsg.streaming)) {
              typingMsg.text = 'Using ' + (data.tool || 'tool') + '...';
              this.messages.splice(toolTypIdx, 1, typingMsg);
            }
            this._resetTypingTimeout();
          } else if (data.state === 'stop') {
            this._clearTypingTimeout();
          }
          break;

        case 'phase':
          // Show tool/phase progress so the user sees the agent is working
          var phaseIdx = this.messages.length - 1;
          var phaseMsg = phaseIdx >= 0 ? this.messages[phaseIdx] : null;
          if (phaseMsg && (phaseMsg.thinking || phaseMsg.streaming)) {
            // Skip phases that have no user-meaningful display text — "streaming"
            // and "done" are lifecycle signals, not status to show in the chat bubble.
            if (data.phase === 'streaming' || data.phase === 'done') {
              break;
            }
            // Context warning: show prominently as a separate system message
            if (data.phase === 'context_warning') {
              var cwDetail = data.detail || 'Context limit reached.';
              this.messages.push({ id: ++msgId, role: 'system', text: cwDetail, meta: '', tools: [] });
            } else if (data.phase === 'thinking' && this.thinkingMode === 'stream') {
              // Stream reasoning tokens to a collapsible panel
              if (!phaseMsg._reasoning) phaseMsg._reasoning = '';
              phaseMsg._reasoning += (data.detail || '') + '\n';
              phaseMsg.text = '<details><summary>Reasoning...</summary>\n\n' + phaseMsg._reasoning + '</details>';
              this.messages.splice(phaseIdx, 1, phaseMsg);
            } else if (phaseMsg.thinking) {
              // Only update text on messages still in thinking state (not yet
              // receiving streamed content) to avoid overwriting accumulated text.
              var phaseDetail;
              if (data.phase === 'tool_use') {
                phaseDetail = 'Using ' + (data.detail || 'tool') + '...';
              } else if (data.phase === 'thinking') {
                phaseDetail = 'Thinking...';
              } else {
                phaseDetail = data.detail || 'Working...';
              }
              phaseMsg.text = phaseDetail;
              this.messages.splice(phaseIdx, 1, phaseMsg);
            }
          }
          this.scrollToBottom();
          break;

        case 'text_delta':
          var lastIdx = this.messages.length - 1;
          var last = lastIdx >= 0 ? this.messages[lastIdx] : null;
          if (last && last.streaming) {
            if (last.thinking) { last.text = ''; last.thinking = false; }
            // If we already detected a text-based tool call, skip further text
            if (last._toolTextDetected) break;
            last.text += data.content;
            // Detect function-call patterns streamed as text and convert to tool cards
            var fcIdx = last.text.search(/\w+<\/function[=,>]/);
            if (fcIdx === -1) fcIdx = last.text.search(/<function=\w+>/);
            if (fcIdx !== -1) {
              var fcPart = last.text.substring(fcIdx);
              var toolMatch = fcPart.match(/^(\w+)<\/function/) || fcPart.match(/^<function=(\w+)>/);
              last.text = last.text.substring(0, fcIdx).trim();
              last._toolTextDetected = true;
              if (toolMatch) {
                if (!last.tools) last.tools = [];
                var inputMatch = fcPart.match(/[=,>]\s*(\{[\s\S]*)/);
                last.tools.push({
                  id: toolMatch[1] + '-txt-' + Date.now(),
                  name: toolMatch[1],
                  running: true,
                  expanded: true,
                  input: inputMatch ? inputMatch[1].replace(/<\/function>?\s*$/, '').trim() : '',
                  result: '',
                  is_error: false
                });
              }
            }
            this.tokenCount = Math.round(last.text.length / 4);
            // Force Alpine reactivity: splice-in-place so x-for re-renders
            // this item. Direct property mutation on array elements may not
            // trigger DOM updates from async WebSocket callbacks.
            this.messages.splice(lastIdx, 1, last);
          } else {
            this.messages.push({ id: ++msgId, role: 'agent', text: data.content, meta: '', streaming: true, tools: [] });
          }
          this.scrollToBottom();
          break;

        case 'tool_start':
          var tsIdx = this.messages.length - 1;
          var lastMsg = tsIdx >= 0 ? this.messages[tsIdx] : null;
          if (lastMsg && lastMsg.streaming) {
            if (!lastMsg.tools) lastMsg.tools = [];
            lastMsg.tools.push({ id: data.tool + '-' + Date.now(), name: data.tool, running: true, expanded: true, input: '', result: '', is_error: false });
            this.messages.splice(tsIdx, 1, lastMsg);
          }
          this.scrollToBottom();
          break;

        case 'tool_end':
          // Tool call parsed by LLM — update tool card with input params
          var teIdx = this.messages.length - 1;
          var lastMsg2 = teIdx >= 0 ? this.messages[teIdx] : null;
          if (lastMsg2 && lastMsg2.tools) {
            for (var ti = lastMsg2.tools.length - 1; ti >= 0; ti--) {
              if (lastMsg2.tools[ti].name === data.tool && lastMsg2.tools[ti].running) {
                lastMsg2.tools[ti].input = data.input || '';
                break;
              }
            }
            this.messages.splice(teIdx, 1, lastMsg2);
          }
          break;

        case 'tool_result':
          // Tool execution completed — update tool card with result
          var trIdx = this.messages.length - 1;
          var lastMsg3 = trIdx >= 0 ? this.messages[trIdx] : null;
          if (lastMsg3 && lastMsg3.tools) {
            for (var ri = lastMsg3.tools.length - 1; ri >= 0; ri--) {
              if (lastMsg3.tools[ri].name === data.tool && lastMsg3.tools[ri].running) {
                lastMsg3.tools[ri].running = false;
                lastMsg3.tools[ri].result = data.result || '';
                lastMsg3.tools[ri].is_error = !!data.is_error;
                // Extract audio file path from text_to_speech results
                if (data.tool === 'text_to_speech' && !data.is_error) {
                  try {
                    var ttsResult = JSON.parse(data.result);
                    if (ttsResult.saved_to) {
                      lastMsg3.tools[ri]._audioFile = ttsResult.saved_to;
                      lastMsg3.tools[ri]._audioDuration = ttsResult.duration_estimate_ms;
                    }
                  } catch(e) { /* not JSON */ }
                }
                break;
              }
            }
            this.messages.splice(trIdx, 1, lastMsg3);
          }
          this.scrollToBottom();
          break;

        case 'response':
          this._settle('end');
          break;

        case 'silent_complete':
          // Agent intentionally chose not to reply (NO_REPLY)
          this._settle('end');
          break;

        case 'error':
          this._settle('fail');
          break;

        case 'agents_updated':
          if (data.agents) {
            Alpine.store('app').agents = data.agents;
            Alpine.store('app').agentCount = data.agents.length;
          }
          break;

        case 'command_result':
          // The model could not open this turn's photo: say so under the turn
          if (this._turn && /^\*\*Vision not supported/.test(data.message || '')) { this._turn.unseen = true; break; }
          this.messages.push({ id: ++msgId, role: 'system', text: data.message || 'Command executed.', meta: '', tools: [] });
          this.scrollToBottom();
          break;

        case 'canvas':
          // Agent presented an interactive canvas — render it in an iframe sandbox
          var canvasHtml = '<div class="canvas-panel" style="border:1px solid var(--border);border-radius:8px;margin:8px 0;overflow:hidden;">';
          canvasHtml += '<div style="padding:6px 12px;background:var(--surface);border-bottom:1px solid var(--border);font-size:0.85em;display:flex;justify-content:space-between;align-items:center;">';
          canvasHtml += '<span>' + (data.title || 'Canvas') + '</span>';
          canvasHtml += '<span style="opacity:0.5;font-size:0.8em;">' + (data.canvas_id || '').substring(0, 8) + '</span></div>';
          canvasHtml += '<iframe sandbox="allow-scripts" srcdoc="' + (data.html || '').replace(/"/g, '&quot;') + '" ';
          canvasHtml += 'style="width:100%;min-height:300px;border:none;background:#fff;" loading="lazy"></iframe></div>';
          this.messages.push({ id: ++msgId, role: 'agent', text: canvasHtml, meta: 'canvas', isHtml: true, tools: [] });
          this.scrollToBottom();
          break;

        case 'pong': break;
      }
    },

    // Format timestamp for display
    formatTime: function(ts) {
      if (!ts) return '';
      var d = new Date(ts);
      var h = d.getHours();
      var m = d.getMinutes();
      var ampm = h >= 12 ? 'PM' : 'AM';
      h = h % 12 || 12;
      return h + ':' + (m < 10 ? '0' : '') + m + ' ' + ampm;
    },

    // Copy message text to clipboard
    copyMessage: function(msg) {
      var text = msg.text || '';
      navigator.clipboard.writeText(text).then(function() {
        msg._copied = true;
        setTimeout(function() { msg._copied = false; }, 2000);
      }).catch(function() {});
    },

    // Process queued messages after current response completes
    _processQueue: function() {
      if (!this.messageQueue.length || this.sending) return;
      var next = this.messageQueue.shift();
      this._sendPayload(next.text, next.files, next.images);
    },

    async sendMessage() {
      if (!this.currentAgent || (!this.inputText.trim() && !this.attachments.length)) return;
      var text = this.inputText.trim();

      // Handle slash commands
      if (text.startsWith('/') && !this.attachments.length) {
        var cmd = text.split(' ')[0].toLowerCase();
        var cmdArgs = text.substring(cmd.length).trim();
        var matched = this.slashCommands.find(function(c) { return c.cmd === cmd; });
        if (matched) {
          this.executeSlashCommand(matched.cmd, cmdArgs);
          return;
        }
      }

      this.inputText = '';

      // Reset textarea height to single line
      var ta = document.getElementById('msg-input');
      if (ta) ta.style.height = '';

      // Upload attachments first if any
      var fileRefs = [];
      var uploadedFiles = [];
      if (this.attachments.length) {
        for (var i = 0; i < this.attachments.length; i++) {
          var att = this.attachments[i];
          att.uploading = true;
          try {
            var uploadRes = await OpenFangAPI.upload(this.currentAgent.id, att.file);
            fileRefs.push('[File: ' + att.file.name + ']');
            uploadedFiles.push({ file_id: uploadRes.file_id, filename: uploadRes.filename, content_type: uploadRes.content_type });
          } catch(e) {
            OpenFangToast.error('Failed to upload ' + att.file.name);
            fileRefs.push('[File: ' + att.file.name + ' (upload failed)]');
          }
          att.uploading = false;
        }
        // Clean up previews
        for (var j = 0; j < this.attachments.length; j++) {
          if (this.attachments[j].preview) URL.revokeObjectURL(this.attachments[j].preview);
        }
        this.attachments = [];
      }

      // Build final message text
      var finalText = text;
      if (fileRefs.length) {
        finalText = (text ? text + '\n' : '') + fileRefs.join('\n');
      }

      // Collect image references for inline rendering
      var msgImages = uploadedFiles.filter(function(f) { return f.content_type && f.content_type.startsWith('image/'); });

      // A placeholder until _settle reads the record back
      this.messages.push({ id: ++msgId, role: 'user', text: finalText, meta: '', tools: [], images: msgImages, pending: true });
      this.scrollToBottom();
      localStorage.setItem('of-first-msg', 'true');

      // If already streaming, queue this message
      if (this.sending) {
        this.messageQueue.push({ text: finalText, files: uploadedFiles, images: msgImages });
        return;
      }

      await this.titleFromFirst(text);
      this._sendPayload(finalText, uploadedFiles, msgImages);
    },

    // A new chat takes its title from its first message: the first line,
    // trimmed to a few words, stored as the session label (the existing
    // label route). Written before the turn starts, since the turn saves the
    // session back with whatever label it loaded. Unlabeled older sessions
    // are never touched.
    async titleFromFirst(text) {
      var agent = this.currentAgent;
      if (!agent || this.messages.filter(function(m) { return m.role === 'user'; }).length !== 1) return;
      var title = String(text || '').split('\n')[0].replace(/['\u2019]/g, '')
        .replace(/[^\p{L}\p{N} _-]+/gu, ' ').trim().split(/\s+/).slice(0, 6).join(' ').slice(0, 60).trim();
      if (!title) return;
      try {
        var data = await OpenFangAPI.get('/api/agents/' + agent.id + '/sessions');
        var cur = (data.sessions || []).find(function(x) { return x.active; });
        if (!cur || cur.label || (cur.message_count || 0) > 0) return;
        await OpenFangAPI.put('/api/sessions/' + cur.session_id + '/label', { label: title });
      } catch(e) { /* the honest fallback title stays */ }
    },

    async _sendPayload(finalText, uploadedFiles, msgImages) {
      this.sending = true;
      this._turn = { text: finalText, images: msgImages || [] };

      // Try WebSocket first
      var wsPayload = { type: 'message', content: finalText };
      if (uploadedFiles && uploadedFiles.length) wsPayload.attachments = uploadedFiles;
      if (OpenFangAPI.wsSend(wsPayload)) {
        this.messages.push({ id: ++msgId, role: 'agent', text: '', meta: '', thinking: true, streaming: true, tools: [] });
        this._resetTypingTimeout();
        this.scrollToBottom();
        return;
      }

      // HTTP fallback
      var t = typeof window.t === 'function' ? window.t : function(s) { return s; };
      if (!OpenFangAPI.isWsConnected()) {
        OpenFangToast.info(t('chat.using_http_mode'));
      }
      this.messages.push({ id: ++msgId, role: 'agent', text: '', meta: '', thinking: true, tools: [] });
      this.scrollToBottom();

      var httpBody = { message: finalText };
      if (uploadedFiles && uploadedFiles.length) httpBody.attachments = uploadedFiles;
      var ok = await OpenFangAPI.post('/api/agents/' + this.currentAgent.id + '/message', httpBody).then(function() { return true; }, function() { return false; });
      this._settle(ok ? 'end' : 'fail');
    },

    // Stop the current run, then show what the record kept
    stopAgent: function() {
      if (!this.currentAgent) return;
      var self = this;
      this._stopped = true;
      OpenFangAPI.post('/api/agents/' + this.currentAgent.id + '/stop', {}).then(function() {
        self._settle('fail');
      }).catch(function() { self._stopped = false; OpenFangToast.error('Couldn\u2019t stop that. Try again in a moment.'); });
    },

    killAgent() {
      if (!this.currentAgent) return;
      var self = this;
      var t = typeof window.t === 'function' ? window.t : function(s) { return s; };
      var name = this.currentAgent.name;
      OpenFangToast.confirm(t('chat.stop_agent_title'), t('chat.stop_agent_confirm') + ' "' + name + '"?', async function() {
        try {
          await OpenFangAPI.del('/api/agents/' + self.currentAgent.id);
          OpenFangAPI.wsDisconnect();
          self._wsAgent = null;
          self.currentAgent = null;
          self.messages = [];
          try { localStorage.removeItem('of-active-agent'); } catch(e) { /* ignore */ }
          OpenFangToast.success(t('chat.agent_stopped') + ' "' + name + '"');
          Alpine.store('app').refreshAgents();
        } catch(e) {
          OpenFangToast.error(t('chat.stop_agent_failed') + ': ' + e.message);
        }
      });
    },

    // Permanently uninstall the agent: kill + remove ~/.openfang/agents/<name>/
    // Issue #1163.
    uninstallAgent: function() {
      if (!this.currentAgent) return;
      var self = this;
      var name = this.currentAgent.name;
      var agentId = this.currentAgent.id;
      OpenFangToast.confirm(
        'Uninstall Agent',
        'Uninstall agent "' + name + '"? This stops the agent AND deletes its files from your workspace. This cannot be undone.',
        async function() {
          try {
            var res = await OpenFangAPI.del('/api/agents/' + agentId + '/uninstall');
            OpenFangAPI.wsDisconnect();
            self._wsAgent = null;
            self.currentAgent = null;
            self.messages = [];
            try { localStorage.removeItem('of-active-agent'); } catch(e) { /* ignore */ }
            var msg = 'Agent "' + name + '" uninstalled';
            if (res && res.dir_removed === false) {
              msg += ' (no on-disk files found)';
            }
            OpenFangToast.success(msg);
            Alpine.store('app').refreshAgents();
          } catch(e) {
            OpenFangToast.error('Failed to uninstall agent: ' + e.message);
          }
        }
      );
    },

    _latexTimer: null,
    scrollToBottom() {
      var self = this;
      var el = document.getElementById('messages');
      if (el) self.$nextTick(function() {
        el.scrollTop = el.scrollHeight;
        // Debounce LaTeX; never on Home, where "$25, $50" are prices, not math
        if (self._latexTimer) clearTimeout(self._latexTimer);
        if (el.classList.contains('home-scroll')) return;
        self._latexTimer = setTimeout(function() { renderLatex(el); }, 150);
      });
    },

    addFiles(files) {
      var self = this;
      var allowed = ['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'text/plain', 'application/pdf',
                      'text/markdown', 'application/json', 'text/csv'];
      var allowedExts = ['.txt', '.pdf', '.md', '.json', '.csv'];
      for (var i = 0; i < files.length; i++) {
        var file = files[i];
        if (file.size > 10 * 1024 * 1024) {
          OpenFangToast.warn('File "' + file.name + '" exceeds 10MB limit');
          continue;
        }
        var typeOk = allowed.indexOf(file.type) !== -1;
        if (!typeOk) {
          var ext = file.name.lastIndexOf('.') !== -1 ? file.name.substring(file.name.lastIndexOf('.')).toLowerCase() : '';
          typeOk = allowedExts.indexOf(ext) !== -1 || file.type.startsWith('image/');
        }
        if (!typeOk) {
          OpenFangToast.warn('File type not supported: ' + file.name);
          continue;
        }
        var preview = null;
        if (file.type.startsWith('image/')) {
          preview = URL.createObjectURL(file);
        }
        self.attachments.push({ file: file, preview: preview, uploading: false });
      }
    },

    removeAttachment(idx) {
      var att = this.attachments[idx];
      if (att && att.preview) URL.revokeObjectURL(att.preview);
      this.attachments.splice(idx, 1);
    },

    handleDrop(e) {
      e.preventDefault();
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
        this.addFiles(e.dataTransfer.files);
      }
    },

    isGrouped(idx) {
      if (idx === 0) return false;
      var prev = this.messages[idx - 1];
      var curr = this.messages[idx];
      return prev && curr && prev.role === curr.role && !curr.thinking && !prev.thinking;
    },

    // Strip raw function-call text that some models (Llama, Groq, etc.) leak into output.
    // These models don't use proper tool_use blocks — they output function calls as plain text.
    sanitizeToolText: function(text) {
      if (!text) return text;
      // Pattern: tool_name</function={"key":"value"} or tool_name</function,{...}
      text = text.replace(/\s*\w+<\/function[=,]?\s*\{[\s\S]*$/gm, '');
      // Pattern: <function=tool_name>{...}</function>
      text = text.replace(/<function=\w+>[\s\S]*?<\/function>/g, '');
      // Pattern: tool_name{"type":"function",...}
      text = text.replace(/\s*\w+\{"type"\s*:\s*"function"[\s\S]*$/gm, '');
      // Pattern: lone </function...> tags
      text = text.replace(/<\/function[^>]*>/g, '');
      // Pattern: <|python_tag|> or similar special tokens
      text = text.replace(/<\|[\w_]+\|>/g, '');
      return text.trim();
    },

    formatToolJson: function(text) {
      if (!text) return '';
      if (typeof text === 'object') {
        return JSON.stringify(text, null, 2);
      }
      try { return JSON.stringify(JSON.parse(text), null, 2); }
      catch(e) { return text; }
    },

    // Voice: start recording
    startRecording: async function() {
      if (this.recording) return;
      try {
        var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        var mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' :
                       MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg';
        this._audioChunks = [];
        this._mediaRecorder = new MediaRecorder(stream, { mimeType: mimeType });
        var self = this;
        this._mediaRecorder.ondataavailable = function(e) {
          if (e.data.size > 0) self._audioChunks.push(e.data);
        };
        this._mediaRecorder.onstop = function() {
          stream.getTracks().forEach(function(t) { t.stop(); });
          self._handleRecordingComplete();
        };
        this._mediaRecorder.start(250);
        this.recording = true;
        this.recordingTime = 0;
        this._recordingTimer = setInterval(function() { self.recordingTime++; }, 1000);
      } catch(e) {
        if (typeof OpenFangToast !== 'undefined') OpenFangToast.error('Microphone access denied');
      }
    },

    // Voice: stop recording
    stopRecording: function() {
      if (!this.recording || !this._mediaRecorder) return;
      this._mediaRecorder.stop();
      this.recording = false;
      if (this._recordingTimer) { clearInterval(this._recordingTimer); this._recordingTimer = null; }
    },

    // Voice: handle completed recording — upload and transcribe
    _handleRecordingComplete: async function() {
      if (!this._audioChunks.length || !this.currentAgent) return;
      var blob = new Blob(this._audioChunks, { type: this._audioChunks[0].type || 'audio/webm' });
      this._audioChunks = [];
      if (blob.size < 100) return; // too small

      // Show a temporary "Transcribing..." message
      this.messages.push({ id: ++msgId, role: 'system', text: 'Transcribing audio...', thinking: true, ts: Date.now(), tools: [] });
      this.scrollToBottom();

      try {
        // Upload audio file
        var ext = blob.type.includes('webm') ? 'webm' : blob.type.includes('ogg') ? 'ogg' : 'mp3';
        var file = new File([blob], 'voice_' + Date.now() + '.' + ext, { type: blob.type });
        var upload = await OpenFangAPI.upload(this.currentAgent.id, file);

        // Remove the "Transcribing..." message
        this.messages = this.messages.filter(function(m) { return !m.thinking || m.role !== 'system'; });

        // Use server-side transcription if available, otherwise fall back to placeholder
        var text = (upload.transcription && upload.transcription.trim())
          ? upload.transcription.trim()
          : '[Voice message - audio: ' + upload.filename + ']';
        this._sendPayload(text, [upload], []);
      } catch(e) {
        this.messages = this.messages.filter(function(m) { return !m.thinking || m.role !== 'system'; });
        if (typeof OpenFangToast !== 'undefined') OpenFangToast.error('Failed to upload audio: ' + (e.message || 'unknown error'));
      }
    },

    // Voice: format recording time as MM:SS
    formatRecordingTime: function() {
      var m = Math.floor(this.recordingTime / 60);
      var s = this.recordingTime % 60;
      return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
    },

    // Search: toggle open/close
    toggleSearch: function() {
      this.searchOpen = !this.searchOpen;
      if (this.searchOpen) {
        var self = this;
        this.$nextTick(function() {
          var el = document.getElementById('chat-search-input');
          if (el) el.focus();
        });
      } else {
        this.searchQuery = '';
      }
    },

    // Search: filter messages by query
    get filteredMessages() {
      if (!this.searchQuery.trim()) return this.messages;
      var q = this.searchQuery.toLowerCase();
      return this.messages.filter(function(m) {
        return (m.text && m.text.toLowerCase().indexOf(q) !== -1) ||
               (m.tools && m.tools.some(function(t) { return t.name.toLowerCase().indexOf(q) !== -1; }));
      });
    },

    // Search: highlight matched text in a string
    highlightSearch: function(html) {
      if (!this.searchQuery.trim() || !html) return html;
      var q = this.searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      var regex = new RegExp('(' + q + ')', 'gi');
      return html.replace(regex, '<mark style="background:var(--warning);color:var(--bg);border-radius:2px;padding:0 2px">$1</mark>');
    },

    renderMarkdown: renderMarkdown,
    escapeHtml: escapeHtml
  };
}
