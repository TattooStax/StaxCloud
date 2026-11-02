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
    except Exception: return {"hashes": {}, "sent": {}}

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
        h = hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()
        if state["hashes"].get(num) != h:
            fang("PUT", "/api/memory/agents/x/kv/" + urllib.parse.quote(f"sms/{num}", safe=""), {"value": rec})
            state["hashes"][num] = h
            changed += 1
            log(f"mirrored sms/{num} ({len(msgs)} messages)")
    return changed

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
        if status == "queued":
            num = digits(v.get("to", ""))
            tid = by_num.get(num)
            if not tid:
                v["status"] = "failed"; v["error"] = "no existing StaxCloud thread for this number"
                fang("PUT", "/api/memory/agents/x/kv/" + urllib.parse.quote(key, safe=""), {"value": v})
                log(f"outbox {key}: failed (no thread)")
                acted += 1; continue
            try:
                created = stax("POST", f"/api/sms/threads/{tid}/messages", {"body": v.get("body", "")})
            except Exception as e:
                v["status"] = "failed"; v["error"] = str(e)[:160]
                fang("PUT", "/api/memory/agents/x/kv/" + urllib.parse.quote(key, safe=""), {"value": v})
                log(f"outbox {key}: send failed {e}")
                acted += 1; continue
            # StaxCloud composes as a draft (approval_state 'draft'); the human
            # approval already happened on the Fang side, so the bridge — acting
            # in the owner's own session — approves the draft to dispatch it.
            msg = created.get("message") if isinstance(created, dict) else None
            if not isinstance(msg, dict): msg = created if isinstance(created, dict) else {}
            mid = msg.get("id"); rev = msg.get("revision")
            if not mid:
                detail = stax("GET", f"/api/sms/threads/{tid}")
                outs = [m for m in detail.get("messages", []) if m.get("direction") == "out"]
                if outs: mid = outs[-1].get("id"); rev = outs[-1].get("revision")
            try:
                if not mid: raise RuntimeError("created message id not found")
                stax("POST", f"/api/sms/threads/{tid}/messages/{mid}/approve", {"revision": rev if rev is not None else 1})
            except Exception as e:
                v["status"] = "failed"; v["error"] = "approve step: " + str(e)[:140]
                fang("PUT", "/api/memory/agents/x/kv/" + urllib.parse.quote(key, safe=""), {"value": v})
                log(f"outbox {key}: approve failed {e}")
                acted += 1; continue
            v["status"] = "sent"; v["sent_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            state["sent"][key] = {"thread": tid, "number": num}
            fang("PUT", "/api/memory/agents/x/kv/" + urllib.parse.quote(key, safe=""), {"value": v})
            log(f"outbox {key}: sent via staxcloud thread")
            acted += 1
        elif status == "sent" and key in state.get("sent", {}):
            tid = state["sent"][key]["thread"]
            try:
                detail = stax("GET", f"/api/sms/threads/{tid}")
            except Exception: continue
            outs = [m for m in detail.get("messages", []) if m.get("direction") == "out"]
            if outs:
                ds = outs[-1].get("delivery_state") or ""
                if ds in ("delivered", "failed"):
                    v["status"] = ds; v["provider_state"] = ds
                    fang("PUT", "/api/memory/agents/x/kv/" + urllib.parse.quote(key, safe=""), {"value": v})
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
