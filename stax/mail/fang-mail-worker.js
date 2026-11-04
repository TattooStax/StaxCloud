// fang-mail — inbound leg for the StaxCloud-on-Fang Email channel.
// Cloudflare Email Routing hands mail for the shop address to this
// worker; each message is parsed to a normalized record and held in
// Workers KV until the studio box pulls it (pull-on-wake, the fang-forms
// pattern): nothing drops while the box sleeps. A copy is also forwarded
// to the owner's verified address, so his existing inbox keeps receiving
// support mail while the Fang surface takes over as the working view.
// Outbound never passes through here — sends go through the Cloudflare
// email sending API from the approved-outbox sender, never this worker.

// ---------- small MIME helpers (dependency-free, v1 scope) ----------

function decodeEncodedWord(str) {
  if (!str) return '';
  return str.replace(/=\?([^?]+)\?([bBqQ])\?([^?]*)\?=/g, function (m, cs, enc, text) {
    try {
      if (enc.toUpperCase() === 'B') {
        const bin = atob(text);
        const bytes = Uint8Array.from(bin, function (c) { return c.charCodeAt(0); });
        return new TextDecoder('utf-8').decode(bytes);
      }
      const qp = text.replace(/_/g, ' ').replace(/=([0-9A-Fa-f]{2})/g, function (mm, h) {
        return String.fromCharCode(parseInt(h, 16));
      });
      const bytes2 = Uint8Array.from(qp, function (c) { return c.charCodeAt(0) & 0xff; });
      return new TextDecoder('utf-8').decode(bytes2);
    } catch (e) { return text; }
  });
}

function parseHeaders(rawHead) {
  const out = {};
  const lines = rawHead.replace(/\r\n/g, '\n').split('\n');
  let cur = null;
  for (const line of lines) {
    if (/^[ \t]/.test(line) && cur) { out[cur] += ' ' + line.trim(); continue; }
    const idx = line.indexOf(':');
    if (idx < 0) continue;
    cur = line.slice(0, idx).trim().toLowerCase();
    out[cur] = line.slice(idx + 1).trim();
  }
  return out;
}

function decodeBody(body, cte) {
  const enc = (cte || '').toLowerCase();
  try {
    if (enc === 'base64') {
      const bin = atob(body.replace(/[\s]/g, ''));
      const bytes = Uint8Array.from(bin, function (c) { return c.charCodeAt(0); });
      return new TextDecoder('utf-8').decode(bytes);
    }
    if (enc === 'quoted-printable') {
      const clean = body.replace(/=\r?\n/g, '');
      const bytes = [];
      for (let i = 0; i < clean.length; i++) {
        if (clean[i] === '=' && /^[0-9A-Fa-f]{2}$/.test(clean.substr(i + 1, 2))) {
          bytes.push(parseInt(clean.substr(i + 1, 2), 16)); i += 2;
        } else bytes.push(clean.charCodeAt(i) & 0xff);
      }
      return new TextDecoder('utf-8').decode(Uint8Array.from(bytes));
    }
  } catch (e) { /* fall through with the raw body */ }
  return body;
}

function splitParts(body, boundary) {
  const parts = [];
  const chunks = body.split('--' + boundary);
  for (let i = 1; i < chunks.length; i++) {
    let chunk = chunks[i];
    if (chunk.startsWith('--')) break;
    if (chunk.startsWith('\r\n')) chunk = chunk.slice(2);
    else if (chunk.startsWith('\n')) chunk = chunk.slice(1);
    const splitAt = chunk.search(/\r\n\r\n|\n\n/);
    if (splitAt < 0) continue;
    const head = chunk.slice(0, splitAt);
    let partBody = chunk.slice(splitAt).replace(/^(\r\n\r\n|\n\n)/, '');
    if (partBody.endsWith('\r\n')) partBody = partBody.slice(0, -2);
    parts.push({ headers: parseHeaders(head), body: partBody });
  }
  return parts;
}

function pickText(headers, body, depth) {
  const ct = (headers['content-type'] || 'text/plain').toLowerCase();
  if (ct.indexOf('multipart/') === 0 && depth < 3) {
    const m = /boundary="?([^";]+)"?/.exec(headers['content-type'] || '');
    if (!m) return '';
    const parts = splitParts(body, m[1]);
    let html = '';
    for (const p of parts) {
      const t = pickText(p.headers, p.body, depth + 1);
      const pct = (p.headers['content-type'] || '').toLowerCase();
      if (pct.indexOf('text/plain') === 0 && t) return t;
      if (pct.indexOf('text/html') === 0 && t && !html) html = t;
    }
    return html;
  }
  if (ct.indexOf('text/plain') === 0 || ct.indexOf('text/html') === 0) {
    const decoded = decodeBody(body, headers['content-transfer-encoding']);
    if (ct.indexOf('text/html') === 0) {
      return decoded
        .replace(/<(script|style)[\s\S]*?<\/\1>/gi, ' ')
        .replace(/<br\s*\/?>/gi, '\n')
        .replace(/<\/p>/gi, '\n\n')
        .replace(/<[^>]+>/g, '')
        .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"').replace(/&#39;/g, "'");
    }
    return decoded;
  }
  return '';
}

function parseFrom(value) {
  const v = decodeEncodedWord(value || '');
  const m = /^(.*?)<([^>]+)>/.exec(v);
  if (m) return { name: m[1].replace(/^"|"$/g, '').trim(), addr: m[2].trim() };
  return { name: '', addr: v.trim() };
}

// ---------- worker ----------

function json(body, status) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
    headers: { 'Content-Type': 'application/json' }
  });
}

async function handleEmail(message) {
  const raw = await new Response(message.raw).text();
  const splitAt = raw.search(/\r\n\r\n|\n\n/);
  const head = splitAt >= 0 ? raw.slice(0, splitAt) : raw;
  const body = splitAt >= 0 ? raw.slice(splitAt).replace(/^(\r\n\r\n|\n\n)/, '') : '';
  const headers = parseHeaders(head);
  const from = parseFrom(headers['from']);
  let text = pickText(headers, body, 0) || '';
  text = text.replace(/\r\n/g, '\n').trim();
  if (text.length > 24000) text = text.slice(0, 24000);
  const snippet = text.replace(/\s+/g, ' ').slice(0, 140);
  const dateHdr = headers['date'] || '';
  let ts = new Date().toISOString();
  const parsed = Date.parse(dateHdr);
  if (!isNaN(parsed)) ts = new Date(parsed).toISOString();
  const rec = {
    uuid: crypto.randomUUID(),
    message_id: (headers['message-id'] || '').replace(/[<>]/g, ''),
    from: from.addr,
    from_name: from.name,
    to: message.to || headers['to'] || '',
    subject: decodeEncodedWord(headers['subject'] || '(no subject)'),
    date: dateHdr,
    ts: ts,
    snippet: snippet,
    text: text,
    in_reply_to: (headers['in-reply-to'] || '').replace(/[<>]/g, ''),
    references: headers['references'] || '',
    unread: true
  };
  await MAIL.put('msg:' + rec.uuid, JSON.stringify({ rec: rec, acked: false }));
  // Transition copy: the owner's verified address keeps receiving support
  // mail in his own inbox while the Fang surface is the working view.
  try { await message.forward('shawn@fargotattoo.com'); } catch (e) { /* store already landed */ }
}

// Classic service-worker syntax: bindings (MAIL, PULL_SECRET) are globals.
addEventListener('email', function (event) {
  event.waitUntil(handleEmail(event.message));
});

addEventListener('fetch', function (event) {
  event.respondWith(handleFetch(event.request));
});

async function handleFetch(request) {
  const url = new URL(request.url);

  if (url.pathname === '/api/status' && request.method === 'GET') {
    let stored = 0, unacked = 0, cursor;
    do {
      const list = await MAIL.list({ prefix: 'msg:', cursor: cursor, limit: 200 });
      for (const k of list.keys) {
        stored++;
        const raw = await MAIL.get(k.name);
        if (raw && !JSON.parse(raw).acked) unacked++;
      }
      cursor = list.list_complete ? null : list.cursor;
    } while (cursor);
    return json({ ok: true, stored: stored, unacked: unacked });
  }

  if (request.headers.get('X-Pull-Secret') !== PULL_SECRET) return json({ error: 'unauthorized' }, 401);

  if (url.pathname === '/api/pull' && request.method === 'GET') {
    const out = [];
    let cursor;
    do {
      const list = await MAIL.list({ prefix: 'msg:', cursor: cursor, limit: 200 });
      for (const k of list.keys) {
        const raw = await MAIL.get(k.name);
        if (!raw) continue;
        const rec = JSON.parse(raw);
        if (!rec.acked) out.push(rec.rec);
      }
      cursor = list.list_complete ? null : list.cursor;
    } while (cursor);
    out.sort(function (a, b) { return new Date(a.ts) - new Date(b.ts); });
    return json({ messages: out });
  }

  if (url.pathname === '/api/ack' && request.method === 'POST') {
    let body;
    try { body = await request.json(); } catch (e) { return json({ error: 'bad json' }, 400); }
    const key = 'msg:' + String(body.uuid || '');
    const raw = await MAIL.get(key);
    if (!raw) return json({ error: 'not found' }, 404);
    const rec = JSON.parse(raw);
    rec.acked = true;
    await MAIL.put(key, JSON.stringify(rec));
    return json({ ok: true });
  }

  return new Response('not found', { status: 404 });
}
