#!/usr/bin/env python3
"""mailsync — box-side carrier for the Fang Email channel.

Two deterministic phases, no model calls (briefstore pattern):

IN: pull parsed inbound mail from the fang-mail Worker (Cloudflare
Email Routing -> Worker -> KV, pull-on-wake like fang-forms) and store
each message in the daemon kv as mail/<uuid>, idempotent (an existing
record is never overwritten), then ack it in the Worker.

OUT: when a held email draft (draft/<uuid>, kind email_send) has been
decided in Needs you, verify the linked approval live against the
approvals API and mint the outbox record emailout/<uuid> carrying that
approval id. The record's own shape is never treated as proof of
approval — the VM sender re-verifies the same approval at the send
point before anything leaves (the Gate-2 discipline the SMS bridge
already follows). Rejected drafts never mint an outbox record.

Also stamps mailbox/status each run with plain facts for the surface.

Cron (box, rollback = delete this one line):
  1-56/5 * * * * flock -n ~/openfang-play/mailsync.lock \
    python3 ~/openfang-play/mailsync.py >> ~/openfang-play/mailsync.log 2>&1
"""
import json, re, sys, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone

HOME = "/home/staxbox"
CONFIG = HOME + "/.openfang/config.toml"
BASE = "http://127.0.0.1:4200"
WORKER = "https://fang-mail.tattoostax.workers.dev"
SECRET_PATH = HOME + "/openfang-play/pull-secret-mail"
ADDRESS = "support@staxcloud.ai"


def log(msg):
    print(datetime.now().isoformat(timespec="seconds"), msg, flush=True)


def api_key():
    return re.search(r'api_key\s*=\s*"([^"]+)"', open(CONFIG).read()).group(1)


def pull_secret():
    return open(SECRET_PATH).read().strip()


def daemon(key, method, path, body=None):
    r = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw) if raw else {}
        except Exception:
            return e.code, {}


def worker(method, path, secret, body=None):
    r = urllib.request.Request(WORKER + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"X-Pull-Secret": secret, "Content-Type": "application/json",
                 # The Worker edge refuses the default urllib UA (403);
                 # pull-sync's curl passes, so present the same face.
                 "User-Agent": "curl/8.5.0"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())


def kv_get(key, seg, k):
    code, body = daemon(key, "GET",
                        "/api/memory/agents/%s/kv/%s" % (seg, urllib.parse.quote(k, safe="")))
    if code != 200:
        return None
    v = body.get("value")
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return None
    return v


def kv_put(key, seg, k, value):
    code, _ = daemon(key, "PUT",
                     "/api/memory/agents/%s/kv/%s" % (seg, urllib.parse.quote(k, safe="")),
                     {"value": value})
    return code == 200


def main():
    key = api_key()
    secret = pull_secret()
    code, agents = daemon(key, "GET", "/api/agents")
    if code != 200 or not agents:
        log("no agents — daemon up?")
        return 1
    seg = agents[0]["id"]

    # ── Phase IN ──────────────────────────────────────────────────
    pulled = 0
    try:
        data = worker("GET", "/api/pull", secret)
    except Exception as e:
        log("pull failed: %s" % e)
        data = {"messages": []}
    for rec in data.get("messages", []):
        uuid = rec.get("uuid")
        if not uuid:
            continue
        k = "mail/" + uuid
        if kv_get(key, seg, k) is None:
            if kv_put(key, seg, k, rec):
                pulled += 1
            else:
                log("kv put failed for %s — leaving unacked" % k)
                continue
        try:
            worker("POST", "/api/ack", secret, {"uuid": uuid})
        except Exception as e:
            log("ack failed for %s: %s" % (uuid, e))
    if pulled:
        log("pulled %d new message(s)" % pulled)

    # ── Phase OUT ─────────────────────────────────────────────────
    code, doc = daemon(key, "GET", "/api/memory/agents/%s/kv" % seg)
    pairs = doc.get("kv_pairs", []) if code == 200 else []
    by_key = {}
    for p in pairs:
        v = p.get("value")
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except Exception:
                v = None
        by_key[p.get("key", "")] = v

    code, ap_doc = daemon(key, "GET", "/api/approvals")
    ap_list = ap_doc if isinstance(ap_doc, list) else ap_doc.get("approvals", [])
    ap_status = {a.get("id"): a.get("status") for a in ap_list}

    minted = 0
    mail_count = 0
    waiting = 0
    last_in = ""
    for k, v in sorted(by_key.items()):
        if k.startswith("mail/") and isinstance(v, dict):
            mail_count += 1
            if v.get("ts", "") > last_in:
                last_in = v["ts"]
        if k.startswith("emailout/") and isinstance(v, dict):
            if v.get("status") in ("queued", "sending"):
                waiting += 1
        if not k.startswith("draft/") or not isinstance(v, dict):
            continue
        if v.get("kind") != "email_send" or v.get("status") != "decided":
            continue
        uuid = k.split("/", 1)[1]
        out_key = "emailout/" + uuid
        if by_key.get(out_key) is not None:
            continue
        ap_id = v.get("approval_id", "")
        if ap_status.get(ap_id) != "approved":
            # A decided draft whose linked approval does not read
            # approved (rejected, or the decision is not visible) never
            # reaches the outbox.
            continue
        out = {
            "to": v.get("to", ""),
            "subject": v.get("subject", ""),
            "body": v.get("body") or v.get("text", ""),
            "in_reply_to": v.get("in_reply_to", ""),
            "references": v.get("references", ""),
            "approval_id": ap_id,
            "status": "queued",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if kv_put(key, seg, out_key, out):
            v["status"] = "queued-for-send"
            kv_put(key, seg, k, v)
            minted += 1
            log("approved email draft -> outbox: %s (to %s)" % (out_key, out["to"]))
    if minted:
        waiting += minted

    # ── Status stamp ──────────────────────────────────────────────
    status = {
        "address": ADDRESS,
        "via": "Cloudflare",
        "last_run": datetime.now(timezone.utc).isoformat(),
        "messages_stored": mail_count,
        "last_message_ts": last_in,
        "waiting_to_send": waiting,
    }
    kv_put(key, seg, "mailbox/status", status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
