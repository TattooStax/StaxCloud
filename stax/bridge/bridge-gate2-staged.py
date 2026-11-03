#!/usr/bin/env python3
"""Fang <-> StaxCloud SMS bridge (runs on the Dell, beside StaxCloud).

StaxCloud stays the system of record for the shop line and is not modified:
this bridge only uses its owner API. Inbound: StaxCloud threads are mirrored
into Fang kv records (sms/<digits>) whenever they change. Outbound: records
the Fang side has already approved into smsout/* (status "queued") are sent
through StaxCloud's own message flow, and the delivery state StaxCloud
reports is written back to the outbox record. Logs carry metadata only —
never message bodies.
"""
import json, os, sys, time, hashlib, urllib.request, urllib.error, http.cookiejar

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "state.json")
LOG_PATH = os.path.join(HERE, "bridge.log")

def log(msg):
    line = time.strftime("%Y-%m-%dT%H:%M:%S ") + msg
    try:
        with open(LOG_PATH, "a") as f: f.write(line + "\n")
    except Exception: pass
    print(line, flush=True)

def env(name):
    v = os.environ.get(name, "").strip()
    if not v: raise RuntimeError("missing env " + name)
    return v

STAX = env("STAX_BASE").rstrip("/")
STAX_PW = env("STAXCLOUD_PW")
FANG = env("FANG_BASE").rstrip("/")
FANG_KEY = env("FANG_KEY")
POLL = int(os.environ.get("POLL_SECS", "30"))

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def http(method, url, body=None, headers=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    if data: r.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items(): r.add_header(k, v)
    with opener.open(r, timeout=timeout) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}

def stax(method, path, body=None):
    try:
        return http(method, STAX + path, body)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            login()
            return http(method, STAX + path, body)
        raise

def login():
    http("POST", STAX + "/api/auth/login", {"password": STAX_PW})
    log("staxcloud session established")

def fang(method, path, body=None):
    # Cloudflare bans the default python UA (error 1010) — present as a browser.
    return http(method, FANG + path, body, headers={
        "Authorization": "Bearer " + FANG_KEY,
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    })

def digits(phone):
    d = "".join(c for c in (phone or "") if c.isdigit())
    return d[1:] if len(d) == 11 and d.startswith("1") else d

def load_state():
    try:
        with open(STATE_PATH) as f: return json.load(f)
    except FileNotFoundError:
        return {"hashes": {}, "sent": {}}
    except Exception as e:
        # Fail loud: a corrupt state file must never silently reset tracking.
        bad = STATE_PATH + ".corrupt-" + time.strftime("%Y%m%d%H%M%S")
        try: os.replace(STATE_PATH, bad)
        except Exception: pass
        log(f"STATE CORRUPT ({e}) — moved to {os.path.basename(bad)}, starting fresh")
        return {"hashes": {}, "sent": {}}

def save_state(s):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f: json.dump(s, f)
    os.replace(tmp, STATE_PATH)

def mirror(state):
    threads = stax("GET", "/api/sms/threads")
    items = threads if isinstance(threads, list) else threads.get("threads", [])
    changed = 0
    for t in items:
        tid = t.get("id")
        num = digits(t.get("phone"))
        if not tid or not num: continue
        detail = stax("GET", f"/api/sms/threads/{tid}")
        msgs = []
        for m in detail.get("messages", []):
            msgs.append({
                "id": m.get("id", ""),
                "dir": "out" if m.get("direction") == "out" else "in",
                "body": m.get("body", ""),
                "ts": m.get("created_at", ""),
                "status": m.get("delivery_state") or m.get("approval_state") or "",
            })
        name = t.get("display_name") or ""
        if name.replace("(", "").replace(")", "").replace("-", "").replace(" ", "").replace("+", "").isdigit():
            name = ""
        rec = {"number": num, "name": name, "thread_id": tid, "messages": msgs}
        if msgs and msgs[-1].get("dir") == "in":
            state.setdefault("attention", {})[num] = True
        else:
            state.setdefault("attention", {}).pop(num, None)
        h = hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()
        if state["hashes"].get(num) != h:
            fang("PUT", "/api/memory/agents/x/kv/" + urllib.parse.quote(f"sms/{num}", safe=""), {"value": rec})
            state["hashes"][num] = h
            changed += 1
            log(f"mirrored sms/{num} ({len(msgs)} messages)")
    # Maintain the fixed attention index the Texts agent enumerates from:
    # threads whose latest message is an unanswered inbound text.
    att = sorted("sms/" + n for n, on in state.get("attention", {}).items() if on)
    att_h = hashlib.sha256(json.dumps(att).encode()).hexdigest()
    if state.get("attention_hash") != att_h:
        fang("PUT", "/api/memory/agents/x/kv/" + urllib.parse.quote("attention/sms", safe=""),
             {"value": {"threads": att, "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}})
        state["attention_hash"] = att_h
        log(f"attention/sms updated: {att}")
    return changed

def find_msg(detail, mid=None, body=None):
    msgs = detail.get("messages", [])
    if mid:
        for m in msgs:
            if m.get("id") == mid: return m
        return None
    outs = [m for m in msgs if m.get("direction") == "out" and m.get("body") == body]
    return outs[-1] if outs else None

def approval_consumed(aid):
    """Single-use ledger read: returns the outbox key that already spent
    this approval, or None if it is unspent. Raises on transport errors —
    the gate fails closed when it cannot check."""
    enc = "/api/memory/agents/x/kv/" + urllib.parse.quote("approvalused/" + aid, safe="")
    try:
        data = fang("GET", enc)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    v = data.get("value") if isinstance(data, dict) else None
    if isinstance(v, str):
        try: v = json.loads(v)
        except Exception: return None
    if isinstance(v, dict) and v.get("approval_id") == aid:
        return v.get("used_by") or "unknown"
    return None

def mark_consumed(key, v):
    """Write the single-use ledger entry for this record's approval. Called
    at the 'sent' transition — the first moment the send is committed in
    StaxCloud — never at verify time, so an approval is not burned by a
    record that failed to send. Every send path converges on that
    transition (fresh create and reconcile alike), and a crash before it
    leaves the record in 'sending' with provider_mid set, where reconcile
    adopts the existing StaxCloud message instead of creating a new one —
    so the approval still ends up consumed exactly once. Until the entry
    lands, the content binding in verify_approval is the backstop: any
    other record presenting the same approval must still match the exact
    recipient and body the owner approved."""
    aid = str(v.get("approval_id") or "").strip()
    if not aid: return
    rec = {"approval_id": aid, "used_by": key, "to": v.get("to", ""),
           "provider_mid": v.get("provider_mid", ""),
           "consumed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    enc = "/api/memory/agents/x/kv/" + urllib.parse.quote("approvalused/" + aid, safe="")
    try:
        fang("PUT", enc, {"value": rec})
        log(f"outbox {key}: approval marked consumed (single-use)")
    except Exception as e:
        log(f"outbox {key}: WARNING consumed-write failed for approval {aid}: {e}")

def verify_approval(v):
    """Enforced approval gate: an outbox record is sendable only if it names
    an approval that the Fang approvals API confirms, right now, as approved
    FOR THIS EXACT SEND — the approval's description must carry the record's
    exact recipient and its exact full body text (pull-sync composes that
    description from the held draft the owner saw, so pairing a real
    approval id with altered content fails here) — and only if the approval
    has not already funded a send: approvals are single-use.
    kv is writable by every agent holding memory_store, so the record's own
    shape is not proof of anything — the live API answer is the proof.
    Returns (ok, reason)."""
    aid = str(v.get("approval_id") or "").strip()
    if not aid:
        return False, "missing approval_id"
    try:
        data = fang("GET", "/api/approvals")
    except Exception as e:
        return False, "approvals API unreachable: " + str(e)[:120]
    ap_list = data if isinstance(data, list) else data.get("approvals", [])
    match = None
    for a in ap_list:
        if isinstance(a, dict) and a.get("id") == aid:
            match = a
            break
    if match is None:
        return False, f"approval {aid} not found in the approvals list"
    st = match.get("status")
    if st != "approved":
        return False, f"approval {aid} has status {st!r}, not 'approved'"
    try:
        used_by = approval_consumed(aid)
    except Exception as e:
        return False, "single-use ledger unreachable: " + str(e)[:120]
    if used_by:
        return False, f"approval {aid} already consumed by {used_by} (single-use)"
    desc = match.get("description") or ""
    to = str(v.get("to") or "")
    body = str(v.get("body") or "")
    if not to or to not in desc:
        return False, f"approval {aid} does not name this recipient (binding mismatch)"
    if not body or body not in desc:
        return False, f"approval {aid} does not cover this exact text (binding mismatch)"
    return True, ""

def refuse(key, v, enc, reason):
    # Terminal on purpose: the outbox loop only acts on queued/sending/sent,
    # so a refused record is never retried. Logged loudly — a refusal means
    # someone or something wrote an outbox record without a real approval.
    v["status"] = "refused"
    v["refusal_reason"] = reason
    v["refused_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    fang("PUT", enc, {"value": v})
    log(f"outbox {key}: REFUSED by approval gate — {reason}")

def outbox(state):
    data = fang("GET", "/api/memory/agents/x/kv")
    pairs = data.get("kv_pairs", [])
    threads = stax("GET", "/api/sms/threads")
    items = threads if isinstance(threads, list) else threads.get("threads", [])
    by_num = {digits(t.get("phone")): t.get("id") for t in items if t.get("id")}
    acted = 0
    for p in pairs:
        key = p.get("key", "")
        if not key.startswith("smsout/"): continue
        v = p.get("value")
        if isinstance(v, str):
            try: v = json.loads(v)
            except Exception: continue
        if not isinstance(v, dict): continue
        status = v.get("status")
        enc = "/api/memory/agents/x/kv/" + urllib.parse.quote(key, safe="")
        if status in ("queued", "sending"):
            if status == "queued":
                # Gate BEFORE the write-ahead: an unverified record must
                # never reach 'sending', let alone StaxCloud.
                ok, reason = verify_approval(v)
                if not ok:
                    refuse(key, v, enc, reason)
                    acted += 1; continue
            num = digits(v.get("to", ""))
            tid = by_num.get(num)
            if not tid:
                v["status"] = "failed"; v["error"] = "no existing StaxCloud thread for this number"
                fang("PUT", enc, {"value": v})
                log(f"outbox {key}: failed (no thread)")
                acted += 1; continue
            if status == "queued":
                # WRITE-AHEAD: record the attempt BEFORE any send. A crash from
                # here on leaves status 'sending', and the reconcile step below
                # adopts the already-created StaxCloud message instead of
                # sending a duplicate.
                v["status"] = "sending"
                v["attempted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                fang("PUT", enc, {"value": v})
                log(f"outbox {key}: write-ahead sending")
            detail = stax("GET", f"/api/sms/threads/{tid}")
            msg = find_msg(detail, mid=v.get("provider_mid"), body=v.get("body", ""))
            if msg is None:
                if status == "sending":
                    # A crashed attempt left no StaxCloud message behind, so
                    # creating one now is a fresh send — the gate applies
                    # again before anything is created.
                    ok, reason = verify_approval(v)
                    if not ok:
                        refuse(key, v, enc, reason)
                        acted += 1; continue
                try:
                    created = stax("POST", f"/api/sms/threads/{tid}/messages", {"body": v.get("body", "")})
                except Exception as e:
                    v["status"] = "failed"; v["error"] = str(e)[:160]
                    fang("PUT", enc, {"value": v})
                    log(f"outbox {key}: send failed {e}")
                    acted += 1; continue
                cm = created.get("message") if isinstance(created, dict) else None
                if not isinstance(cm, dict): cm = created if isinstance(created, dict) else {}
                if cm.get("id"):
                    msg = cm
                else:
                    detail = stax("GET", f"/api/sms/threads/{tid}")
                    msg = find_msg(detail, body=v.get("body", ""))
                if msg is None:
                    v["status"] = "failed"; v["error"] = "created message not found on read-back"
                    fang("PUT", enc, {"value": v})
                    log(f"outbox {key}: read-back failed")
                    acted += 1; continue
                log(f"outbox {key}: created staxcloud message")
            else:
                log(f"outbox {key}: reconciled existing staxcloud message (no duplicate sent)")
            v["provider_mid"] = msg.get("id")
            fang("PUT", enc, {"value": v})
            # StaxCloud composes as a draft; the human approval already happened
            # on the Fang side, so the bridge approves in the owner's session.
            if msg.get("approval_state") == "draft" or status == "sending":
                try:
                    stax("POST", f"/api/sms/threads/{tid}/messages/{msg.get('id')}/approve",
                         {"revision": msg.get("revision") if msg.get("revision") is not None else 1})
                except Exception as e:
                    v["status"] = "failed"; v["error"] = "approve step: " + str(e)[:140]
                    fang("PUT", enc, {"value": v})
                    log(f"outbox {key}: approve failed {e}")
                    acted += 1; continue
            v["status"] = "sent"; v["sent_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            state["sent"][key] = {"thread": tid, "number": num, "mid": v["provider_mid"]}
            fang("PUT", enc, {"value": v})
            # The send is committed in StaxCloud at this point: spend the
            # approval in the single-use ledger before anything else can
            # present it.
            mark_consumed(key, v)
            log(f"outbox {key}: sent via staxcloud thread")
            acted += 1
        elif status == "sent":
            track = state.get("sent", {}).get(key, {})
            tid = track.get("thread") or by_num.get(digits(v.get("to", "")))
            if not tid: continue
            try:
                detail = stax("GET", f"/api/sms/threads/{tid}")
            except Exception: continue
            m = find_msg(detail, mid=v.get("provider_mid") or track.get("mid"))
            if m is None:
                log(f"outbox {key}: WARNING sent message not found on read-back")
                continue
            ds = m.get("delivery_state") or ""
            if ds in ("delivered", "failed"):
                v["status"] = ds; v["provider_state"] = ds
                fang("PUT", enc, {"value": v})
                # Backstop: if the consumed-write at the 'sent' transition
                # failed, land it now — an approval that funded a send must
                # not stay spendable. Rewriting the same entry is harmless.
                aid = str(v.get("approval_id") or "").strip()
                if aid:
                    try:
                        if not approval_consumed(aid):
                            mark_consumed(key, v)
                    except Exception:
                        mark_consumed(key, v)
                log(f"outbox {key}: delivery read-back -> {ds}")
                acted += 1
    return acted

def main():
    login()
    state = load_state()
    log(f"bridge up (poll {POLL}s)")
    while True:
        try: mirror(state)
        except Exception as e: log(f"mirror error: {e}")
        try: outbox(state)
        except Exception as e: log(f"outbox error: {e}")
        save_state(state)
        time.sleep(POLL)

if __name__ == "__main__":
    main()
