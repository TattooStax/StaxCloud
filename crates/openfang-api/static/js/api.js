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

  // Styled confirmation modal — replaces native confirm()
  function confirm(title, message, onConfirm) {
    var overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';

    var modal = document.createElement('div');
    modal.className = 'confirm-modal';

    var titleEl = document.createElement('div');
    titleEl.className = 'confirm-title';
    titleEl.textContent = title;
    modal.appendChild(titleEl);

    var msgEl = document.createElement('div');
    msgEl.className = 'confirm-message';
    msgEl.textContent = message;
    modal.appendChild(msgEl);

    var actions = document.createElement('div');
    actions.className = 'confirm-actions';

    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn btn-ghost confirm-cancel';
    cancelBtn.textContent = 'Cancel';
    actions.appendChild(cancelBtn);

    var okBtn = document.createElement('button');
    okBtn.className = 'btn btn-danger confirm-ok';
    okBtn.textContent = 'Confirm';
    actions.appendChild(okBtn);

    modal.appendChild(actions);
    overlay.appendChild(modal);

    function close() { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); document.removeEventListener('keydown', onKey); }
    cancelBtn.onclick = close;
    okBtn.onclick = function() { close(); if (onConfirm) onConfirm(); };
    overlay.addEventListener('click', function(e) { if (e.target === overlay) close(); });

    function onKey(e) { if (e.key === 'Escape') close(); }
    document.addEventListener('keydown', onKey);

    document.body.appendChild(overlay);
    okBtn.focus();
  }

  return {
    toast: toast,
    success: success,
    error: error,
    warn: warn,
    info: info,
    confirm: confirm
  };
})();

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
