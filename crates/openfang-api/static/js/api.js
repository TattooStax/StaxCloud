// OpenFang API Client — Fetch wrapper, WebSocket manager, auth injection, toast notifications
'use strict';

// ── Toast Notification System ──
var OpenFangToast = (function() {
  var _container = null;
  var _toastId = 0;

  function getContainer() {
    if (!_container) {
      _container = document.getElementById('toast-container');
      if (!_container) {
        _container = document.createElement('div');
        _container.id = 'toast-container';
        _container.className = 'toast-container';
        document.body.appendChild(_container);
      }
    }
    return _container;
  }

  function toast(message, type, duration) {
    type = type || 'info';
    duration = duration || 4000;
    var id = ++_toastId;
    var el = document.createElement('div');
    el.className = 'toast toast-' + type;
    el.setAttribute('data-toast-id', id);

    var msgSpan = document.createElement('span');
    msgSpan.className = 'toast-msg';
    msgSpan.textContent = message;
    el.appendChild(msgSpan);

    var closeBtn = document.createElement('button');
    closeBtn.className = 'toast-close';
    closeBtn.type = 'button';
    closeBtn.setAttribute('aria-label', 'Dismiss');
    closeBtn.textContent = '\u00D7';
    closeBtn.onclick = function() { dismissToast(el); };
    el.appendChild(closeBtn);

    el.onclick = function(e) { if (e.target === el) dismissToast(el); };
    getContainer().appendChild(el);

    // Auto-dismiss
    if (duration > 0) {
      setTimeout(function() { dismissToast(el); }, duration);
    }
    return id;
  }

  function dismissToast(el) {
    if (!el || el.classList.contains('toast-dismiss')) return;
    el.classList.add('toast-dismiss');
    setTimeout(function() { if (el.parentNode) el.parentNode.removeChild(el); }, 300);
  }

  function success(msg, duration) { return toast(msg, 'success', duration); }
  function error(msg, duration) { return toast(msg, 'error', duration || 6000); }
  function warn(msg, duration) { return toast(msg, 'warn', duration || 5000); }
  function info(msg, duration) { return toast(msg, 'info', duration); }

  // ── The one in-page question (V4's AppShell.ask, in the fork's style) ──
  // Native confirm()/prompt() can be dismissed without a word in an
  // installed web app or an embedded view, so every question goes here.
  //   StaxUI.ask({ title, message, fields: [{ name, label, value,
  //     placeholder, type, inputmode, required, options }], requireText,
  //     confirmLabel, cancelLabel, danger })
  // resolves an object of field values on confirm, or null on Cancel,
  // Escape or the backdrop. One question at a time. A dangerous question
  // opens on Cancel so Enter alone never removes anything. Focus stays in
  // the question while it is open and goes back where it was after.
  var _askQueue = Promise.resolve();
  function ask(options) {
    var turn = _askQueue.then(function() { return askNow(options); });
    _askQueue = turn.catch(function() { return null; });
    return turn;
  }

  function askNow(options) {
    var opts = typeof options === 'string' ? { message: options } : (options || {});
    var fields = Array.isArray(opts.fields) ? opts.fields.slice() : [];
    if (opts.requireText) fields.push({ name: '__require', label: 'Type ' + opts.requireText + ' to continue', required: true });
    return new Promise(function(resolve) {
      var returnFocus = document.activeElement;
      var uid = 'stax-ask-' + Math.random().toString(36).slice(2, 10);
      var overlay = document.createElement('div');
      overlay.className = 'confirm-overlay';
      var form = document.createElement('form');
      form.className = 'confirm-modal';
      form.setAttribute('role', 'alertdialog');
      form.setAttribute('aria-modal', 'true');
      form.setAttribute('aria-labelledby', uid + '-t');
      form.setAttribute('tabindex', '-1');
      form.noValidate = true;

      var titleEl = document.createElement('div');
      titleEl.className = 'confirm-title';
      titleEl.id = uid + '-t';
      titleEl.textContent = opts.title || 'Are you sure?';
      form.appendChild(titleEl);
      if (opts.message) {
        var msgEl = document.createElement('div');
        msgEl.className = 'confirm-message';
        msgEl.id = uid + '-m';
        msgEl.textContent = opts.message;
        form.setAttribute('aria-describedby', uid + '-m');
        form.appendChild(msgEl);
      }

      var inputs = [];
      fields.forEach(function(f, i) {
        var label = document.createElement('label');
        label.className = 'confirm-field';
        label.setAttribute('for', uid + '-f' + i);
        var span = document.createElement('span');
        span.textContent = f.label || f.name;
        label.appendChild(span);
        var input;
        if (Array.isArray(f.options)) {
          input = document.createElement('select');
          f.options.forEach(function(o) {
            var opt = document.createElement('option');
            opt.value = o.value; opt.textContent = o.label != null ? o.label : o.value;
            if (String(o.value) === String(f.value == null ? '' : f.value)) opt.selected = true;
            input.appendChild(opt);
          });
        } else {
          input = document.createElement('input');
          input.type = f.type || 'text';
          input.value = f.value == null ? '' : f.value;
          if (f.placeholder) input.placeholder = f.placeholder;
          if (f.inputmode) input.setAttribute('inputmode', f.inputmode);
          input.autocomplete = 'off';
        }
        input.id = uid + '-f' + i;
        input.name = f.name;
        input.className = 'form-input';
        if (f.required) input.required = true;
        label.appendChild(input);
        form.appendChild(label);
        inputs.push(input);
      });

      var actions = document.createElement('div');
      actions.className = 'confirm-actions';
      var cancelBtn = document.createElement('button');
      cancelBtn.type = 'button';
      cancelBtn.className = 'btn btn-ghost confirm-cancel';
      cancelBtn.textContent = opts.cancelLabel || 'Cancel';
      var okBtn = document.createElement('button');
      okBtn.type = 'submit';
      okBtn.className = 'btn confirm-ok ' + (opts.danger ? 'btn-danger' : 'btn-primary');
      okBtn.textContent = opts.confirmLabel || 'Continue';
      actions.appendChild(cancelBtn);
      actions.appendChild(okBtn);
      form.appendChild(actions);
      overlay.appendChild(form);

      function ready() {
        var filled = inputs.every(function(x) { return !x.required || String(x.value).trim(); });
        var typed = !opts.requireText || (form.elements.__require && form.elements.__require.value === opts.requireText);
        return filled && typed;
      }
      function sync() { okBtn.disabled = !ready(); }
      inputs.forEach(function(x) { x.addEventListener('input', sync); x.addEventListener('change', sync); });
      sync();

      var settled = false;
      function first() { return inputs[0] || (opts.danger ? cancelBtn : okBtn); }
      function keepFocus(e) { if (!overlay.contains(e.target)) { var f = first(); if (f) f.focus(); } }
      document.addEventListener('focusin', keepFocus, true);
      function finish(answer) {
        if (settled) return;
        settled = true;
        document.removeEventListener('focusin', keepFocus, true);
        if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
        try { if (returnFocus && returnFocus.focus) returnFocus.focus({ preventScroll: true }); } catch (e) {}
        resolve(answer);
      }
      form.addEventListener('submit', function(e) {
        e.preventDefault();
        if (!ready()) return;
        var values = {};
        inputs.forEach(function(x) { if (x.name !== '__require') values[x.name] = x.value; });
        finish(values);
      });
      cancelBtn.addEventListener('click', function() { finish(null); });
      // The backdrop dismisses only a press that also began on it, so a
      // text selection released outside the box never throws input away.
      var pressedBackdrop = false;
      overlay.addEventListener('pointerdown', function(e) { pressedBackdrop = e.target === overlay; });
      overlay.addEventListener('click', function(e) {
        if (e.target === overlay && pressedBackdrop) finish(null);
        pressedBackdrop = false;
      });
      overlay.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); finish(null); return; }
        if (e.key !== 'Tab') return;
        var nodes = Array.prototype.slice.call(overlay.querySelectorAll('input, select, button:not([disabled])'));
        if (!nodes.length) return;
        var i = nodes.indexOf(document.activeElement);
        e.preventDefault();
        nodes[(i + (e.shiftKey ? nodes.length - 1 : 1) + nodes.length) % nodes.length].focus();
      });
      document.body.appendChild(overlay);
      var f0 = first(); if (f0) f0.focus();
    });
  }

  // Yes/no form of ask(): resolves true only on the confirm button.
  function confirmAsk(options) {
    var opts = typeof options === 'string' ? { message: options } : (options || {});
    var plain = {};
    for (var k in opts) { if (k !== 'fields' && k !== 'requireText') plain[k] = opts[k]; }
    return ask(plain).then(function(answer) { return answer !== null; });
  }

  // The verb a destructive title starts with, for the button: a button
  // says what it does ("Delete"), never just "Confirm".
  var VERBS = ['Delete', 'Remove', 'Clear', 'Deactivate', 'Reject', 'Discard', 'Archive', 'Disconnect', 'Reset', 'Stop', 'Cancel', 'Unpublish', 'Uninstall', 'Forget', 'Revoke'];
  function verbOf(title) {
    var w = String(title || '').replace(/^[^A-Za-z]+/, '').split(/\s+/);
    var first = (w[0] || '').replace(/[^A-Za-z]/g, '');
    first = first.charAt(0).toUpperCase() + first.slice(1).toLowerCase();
    var tail = String(title || '').match(/\b(offline|down)\b/i);
    if (first === 'Take' && tail) return 'Take ' + tail[1].toLowerCase();
    if (first === 'Cancel') return 'Yes, cancel';
    return VERBS.indexOf(first) >= 0 ? first : 'Confirm';
  }

  // Older callers: confirm(title, message, onConfirm). Every one of them is
  // a destructive question, so it opens on Cancel and names its verb.
  function confirm(title, message, onConfirm, confirmLabel) {
    confirmAsk({ title: title, message: message, danger: true, confirmLabel: confirmLabel || verbOf(title) })
      .then(function(yes) { if (yes && onConfirm) onConfirm(); });
  }

  // A toast with one action (usually "Undo"). The action runs at most once,
  // and only while the toast is showing.
  function action(message, label, onAction, duration) {
    var id = toast(message, 'info', duration || 7000);
    var el = getContainer().querySelector('[data-toast-id="' + id + '"]');
    if (!el) return id;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'toast-action';
    btn.textContent = label || 'Undo';
    var done = false;
    btn.onclick = function() {
      if (done) return;
      done = true;
      dismissToast(el);
      if (onAction) onAction();
    };
    el.insertBefore(btn, el.querySelector('.toast-close'));
    return id;
  }
  function undo(message, onUndo) { return action(message, 'Undo', onUndo); }

  return {
    toast: toast,
    success: success,
    error: error,
    warn: warn,
    info: info,
    confirm: confirm,
    ask: ask,
    confirmAsk: confirmAsk,
    action: action,
    undo: undo,
    verbOf: verbOf
  };
})();

// ── Every pop-up window behaves the same (V4: bounded, focus kept) ──
// Pages open windows with Alpine (x-show on a .modal-overlay, or a sheet
// marked role="dialog"). This watcher gives each one the same manners
// without touching the pages: it is announced as a dialog, focus moves
// into it, Tab stays inside it, and when it closes focus goes back to
// what opened it. Escape and backdrop closing stay with each page.
var StaxDialogs = (function() {
  var open = [];  // { el, back }
  var SEL = '.modal-overlay, [role="dialog"][aria-modal="true"]';
  var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  function shown(el) {
    if (!el.isConnected) return false;
    var r = el.getBoundingClientRect();
    var st = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && st.display !== 'none' && st.visibility !== 'hidden';
  }
  function focusables(el) {
    return Array.prototype.slice.call(el.querySelectorAll(FOCUSABLE)).filter(function(n) {
      var r = n.getBoundingClientRect(); return r.width > 0 && r.height > 0;
    });
  }
  function panelOf(el) { return el.classList.contains('modal-overlay') ? (el.querySelector('.modal') || el) : el; }
  function opened(el) {
    var panel = panelOf(el);
    if (!panel.getAttribute('role')) panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    if (!panel.getAttribute('aria-label') && !panel.getAttribute('aria-labelledby')) {
      var h = panel.querySelector('h1, h2, h3, h4, .modal-title');
      if (h && h.textContent.trim()) panel.setAttribute('aria-label', h.textContent.trim().slice(0, 80));
    }
    open.push({ el: el, back: document.activeElement });
    setTimeout(function() {
      if (!shown(el) || el.contains(document.activeElement)) return;
      var f = focusables(panel);
      var target = f.filter(function(n) { return /^(INPUT|SELECT|TEXTAREA)$/.test(n.tagName); })[0] || f[0];
      if (target) target.focus({ preventScroll: true });
      else { panel.setAttribute('tabindex', '-1'); panel.focus({ preventScroll: true }); }
    }, 30);
  }
  function closed(entry) {
    var back = entry.back;
    if (back && back.isConnected && back.focus && !document.querySelector('.confirm-overlay')) {
      try { back.focus({ preventScroll: true }); } catch (e) {}
    }
  }
  function scan() {
    var now = Array.prototype.slice.call(document.querySelectorAll(SEL)).filter(shown);
    open = open.filter(function(o) {
      if (now.indexOf(o.el) >= 0) return true;
      closed(o); return false;
    });
    now.forEach(function(el) {
      if (!open.some(function(o) { return o.el === el; })) opened(el);
    });
  }
  var pending = false;
  function later() { if (pending) return; pending = true; requestAnimationFrame(function() { pending = false; scan(); }); }
  function top() { return open.length ? open[open.length - 1].el : null; }
  document.addEventListener('keydown', function(e) {
    if (e.key !== 'Tab' || document.querySelector('.confirm-overlay')) return;
    var el = top(); if (!el) return;
    var f = focusables(panelOf(el)); if (!f.length) return;
    var i = f.indexOf(document.activeElement);
    if (i < 0) { e.preventDefault(); f[0].focus(); return; }
    if (!e.shiftKey && i === f.length - 1) { e.preventDefault(); f[0].focus(); }
    else if (e.shiftKey && i === 0) { e.preventDefault(); f[f.length - 1].focus(); }
  }, true);
  function start() {
    new MutationObserver(later).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['style', 'class', 'hidden'] });
    scan();
  }
  if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
  return { scan: scan, openCount: function() { return open.length; } };
})();

// The shared UI primitives under one name (V4 calls these AppShell.ask /
// AppShell.confirm). Pages use StaxUI; OpenFangToast keeps working.
var StaxUI = {
  ask: OpenFangToast.ask,
  confirm: OpenFangToast.confirmAsk,
  undo: OpenFangToast.undo,
  action: OpenFangToast.action
};

// ── Friendly Error Messages ──
function friendlyError(status, serverMsg) {
  if (status === 0 || !status) return 'Cannot reach daemon — is openfang running?';
  if (status === 401) return 'Not authorized — check your API key';
  if (status === 403) return 'Permission denied';
  if (status === 404) return serverMsg || 'Resource not found';
  if (status === 429) return 'Rate limited — slow down and try again';
  if (status === 413) return 'Request too large';
  if (status === 500) return 'Server error — check daemon logs';
  if (status === 502 || status === 503) return 'Daemon unavailable — is it running?';
  return serverMsg || 'Unexpected error (' + status + ')';
}

// ── API Client ──
var OpenFangAPI = (function() {
  var BASE = window.location.origin;
  var WS_BASE = BASE.replace(/^http/, 'ws');
  var _authToken = '';

  // Connection state tracking
  var _connectionState = 'connected';
  var _reconnectAttempt = 0;
  var _connectionListeners = [];

  function setAuthToken(token) { _authToken = token; }

  function headers() {
    var h = { 'Content-Type': 'application/json' };
    if (_authToken) h['Authorization'] = 'Bearer ' + _authToken;
    return h;
  }

  function setConnectionState(state) {
    if (_connectionState === state) return;
    _connectionState = state;
    _connectionListeners.forEach(function(fn) { fn(state); });
  }

  function onConnectionChange(fn) { _connectionListeners.push(fn); }

  function request(method, path, body, timeoutMs) {
    var opts = { method: method, headers: headers() };
    if (body !== undefined) opts.body = JSON.stringify(body);
    // Optional hard timeout: a caller that renders a loading state
    // passes one so a stalled response rejects (and its error state
    // shows) instead of leaving the spinner up forever. Callers that
    // pass nothing keep the historical unbounded behavior.
    var ctl = null, timer = null;
    if (timeoutMs && typeof AbortController !== 'undefined') {
      ctl = new AbortController();
      opts.signal = ctl.signal;
      timer = setTimeout(function() { ctl.abort(); }, timeoutMs);
    }
    var done = function() { if (timer) clearTimeout(timer); };
    return fetch(BASE + path, opts).then(function(r) {
      if (_connectionState !== 'connected') setConnectionState('connected');
      if (!r.ok) {
        // On 401, auto-show auth prompt so the user can re-enter their key
        if (r.status === 401 && typeof Alpine !== 'undefined') {
          try {
            var store = Alpine.store('app');
            if (store && !store.showAuthPrompt) {
              _authToken = '';
              localStorage.removeItem('openfang-api-key');
              store.showAuthPrompt = true;
            }
          } catch(e2) { /* ignore Alpine errors */ }
        }
        return r.text().then(function(text) {
          var msg = '';
          try {
            var json = JSON.parse(text);
            msg = json.error || r.statusText;
          } catch(e) {
            msg = r.statusText;
          }
          var err = new Error(friendlyError(r.status, msg));
          err.status = r.status;
          throw err;
        });
      }
      var ct = r.headers.get('content-type') || '';
      if (ct.indexOf('application/json') >= 0) return r.json();
      return r.text().then(function(t) {
        try { return JSON.parse(t); } catch(e) { return { text: t }; }
      });
    }).catch(function(e) {
      if (e.name === 'TypeError' && e.message.includes('Failed to fetch')) {
        setConnectionState('disconnected');
        throw new Error('Cannot connect to daemon — is openfang running?');
      }
      throw e;
    }).then(function(v) {
      done();
      return v;
    }, function(e) {
      done();
      if (e && e.name === 'AbortError') throw new Error('That took too long — check your connection and try again.');
      throw e;
    });
  }

  function get(path, opts) { return request('GET', path, undefined, opts && opts.timeoutMs); }
  function post(path, body) { return request('POST', path, body); }
  function put(path, body) { return request('PUT', path, body); }
  function patch(path, body) { return request('PATCH', path, body); }
  function del(path) { return request('DELETE', path); }

  // WebSocket manager with auto-reconnect
  var _ws = null;
  var _wsCallbacks = {};
  var _wsConnected = false;
  var _wsAgentId = null;
  var _reconnectTimer = null;
  var _reconnectAttempts = 0;
  var MAX_RECONNECT = 5;

  function wsConnect(agentId, callbacks) {
    wsDisconnect();
    _wsCallbacks = callbacks || {};
    _wsAgentId = agentId;
    _reconnectAttempts = 0;
    _doConnect(agentId);
  }

  function _doConnect(agentId) {
    try {
      var url = WS_BASE + '/api/agents/' + agentId + '/ws';
      if (_authToken) url += '?token=' + encodeURIComponent(_authToken);
      var socket = new WebSocket(url);
      _ws = socket;

      socket.onopen = function() {
        // Guard: ignore if this socket was superseded by a newer connection
        if (_ws !== socket) return;
        _wsConnected = true;
        _reconnectAttempts = 0;
        setConnectionState('connected');
        if (_reconnectAttempt > 0) {
          OpenFangToast.success('Reconnected');
          _reconnectAttempt = 0;
        }
        if (_wsCallbacks.onOpen) _wsCallbacks.onOpen();
      };

      socket.onmessage = function(e) {
        try {
          var data = JSON.parse(e.data);
        } catch(parseErr) {
          return; // Ignore malformed JSON frames
        }
        // Dispatch outside try/catch so handler errors are not swallowed
        if (_wsCallbacks.onMessage) _wsCallbacks.onMessage(data);
      };

      socket.onclose = function(e) {
        // Guard: only update state if this is still the active socket.
        // A superseded socket closing must not null-out the new connection.
        if (_ws !== socket) return;
        _wsConnected = false;
        _ws = null;
        if (_wsAgentId && _reconnectAttempts < MAX_RECONNECT && e.code !== 1000) {
          _reconnectAttempts++;
          _reconnectAttempt = _reconnectAttempts;
          setConnectionState('reconnecting');
          if (_reconnectAttempts === 1) {
            OpenFangToast.warn('Connection lost, reconnecting...');
          }
          var delay = Math.min(1000 * Math.pow(2, _reconnectAttempts - 1), 10000);
          _reconnectTimer = setTimeout(function() { _doConnect(_wsAgentId); }, delay);
          return;
        }
        if (_wsAgentId && _reconnectAttempts >= MAX_RECONNECT) {
          setConnectionState('disconnected');
          OpenFangToast.error('Connection lost — switched to HTTP mode', 0);
        }
        if (_wsCallbacks.onClose) _wsCallbacks.onClose();
      };

      socket.onerror = function() {
        // Guard: ignore errors from superseded sockets
        if (_ws !== socket) return;
        _wsConnected = false;
        if (_wsCallbacks.onError) _wsCallbacks.onError();
      };
    } catch(e) {
      _wsConnected = false;
    }
  }

  function wsDisconnect() {
    _wsAgentId = null;
    _reconnectAttempts = MAX_RECONNECT;
    if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null; }
    if (_ws) { _ws.close(1000); _ws = null; }
    _wsConnected = false;
  }

  function wsSend(data) {
    if (_ws && _ws.readyState === WebSocket.OPEN) {
      _ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

  function isWsConnected() { return _wsConnected; }

  function getConnectionState() { return _connectionState; }

  function getToken() { return _authToken; }

  // A phone photo can be 5-15 MB. Pictures over 3 MB (or wider than
  // 2560 px) are redrawn at 2560 px on the long side as a JPEG before they
  // leave the device: faster on a shop's connection, and plenty for any
  // model. Anything that cannot be redrawn is sent as it is.
  var SHRINK_OVER_BYTES = 3 * 1024 * 1024, SHRINK_TO_SIDE = 2560;
  function shrinkPhoto(file) {
    if (!file || !/^image\/(jpeg|png|webp)$/.test(file.type || '') || typeof createImageBitmap !== 'function') return Promise.resolve(file);
    return createImageBitmap(file).then(function(bmp) {
      var side = Math.max(bmp.width, bmp.height);
      if (file.size <= SHRINK_OVER_BYTES && side <= SHRINK_TO_SIDE) { if (bmp.close) bmp.close(); return file; }
      var scale = Math.min(1, SHRINK_TO_SIDE / side);
      var w = Math.round(bmp.width * scale), h = Math.round(bmp.height * scale);
      var canvas = document.createElement('canvas');
      canvas.width = w; canvas.height = h;
      var ctx = canvas.getContext('2d');
      ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, w, h);
      ctx.drawImage(bmp, 0, 0, w, h);
      if (bmp.close) bmp.close();
      return new Promise(function(res) { canvas.toBlob(res, 'image/jpeg', 0.9); }).then(function(blob) {
        if (!blob || blob.size >= file.size) return file;
        var name = (file.name || 'photo').replace(/\.[a-z0-9]+$/i, '') + '.jpg';
        try { return new File([blob], name, { type: 'image/jpeg' }); } catch(e) { blob.name = name; return blob; }
      });
    }).catch(function() { return file; });
  }

  // One shared record by its exact key. A record that was never written
  // comes back as null (an answer), not as a "not found" error: the read
  // goes through the prefix list, which returns an empty list instead.
  function getRecord(key) {
    return get('/api/memory/agents/shared/kv?prefix=' + encodeURIComponent(key)).then(function(d) {
      var hit = ((d && d.kv_pairs) || []).find(function(pr) { return pr.key === key; });
      var v = hit ? hit.value : null;
      if (typeof v === 'string') { try { v = JSON.parse(v); } catch(e) { /* plain string record */ } }
      return v === undefined ? null : v;
    });
  }

  function upload(agentId, file) {
    return shrinkPhoto(file).then(function(f) { return uploadAsIs(agentId, f); });
  }

  function uploadAsIs(agentId, file) {
    var hdrs = {};
    if (_authToken) hdrs['Authorization'] = 'Bearer ' + _authToken;
	var form = new FormData();
    form.append('file', file, file.name || 'upload');
    form.append('filename', file.name || 'upload');
    return fetch(BASE + '/api/agents/' + agentId + '/upload', {
      method: 'POST',
      headers: hdrs,
      body: form
    }).then(function(r) {
      if (r.ok) return r.json();
      return r.json().catch(function() { return {}; }).then(function(j) {
        throw new Error(j.error || 'Upload failed');
      });
    });
  }

  return {
    setAuthToken: setAuthToken,
    getRecord: getRecord,
    getToken: getToken,
    get: get,
    post: post,
    put: put,
    patch: patch,
    del: del,
    delete: del,
    upload: upload,
    wsConnect: wsConnect,
    wsDisconnect: wsDisconnect,
    wsSend: wsSend,
    isWsConnected: isWsConnected,
    getConnectionState: getConnectionState,
    onConnectionChange: onConnectionChange
  };
})();
