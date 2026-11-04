#!/usr/bin/env python3
"""mailsend — VM-side send point for the Fang Email channel.

The box never holds a Cloudflare credential (the standing token-placement
blocker), so sends execute here, where the registered Cloudflare
connector lives. This script is the send point, and it enforces the
approval law the way the SMS bridge does (Gate-2 discipline):

  * It only looks at emailout/<uuid> records — a record family the
    box-side mailsync mints solely from a decided, approved draft.
  * Before sending, it re-verifies that approval LIVE against the
    daemon's approvals API. An outbox record whose approval does not
    currently read "approved" is stamped "refused" and never sent —
    the record's own shape is not proof of approval.
  * Sends go through the one Cloudflare email sending call
    (POST /accounts/<acct>/email/sending/send). The provider mints its
    own Message-ID (probe, 2026-11-04), so exactly-once rests on the
    claim/stamp discipline here: a record is claimed ("sending")
    before the call and stamped with the outcome after it.
  * The outcome is stamped back onto the record (sent + provider
    result, or failed + error) — read-back, not assertion.

Runs on the Muse VM (the daemon api_key is fetched per run through
the established SSH chain and never stored here).
"""
import json, subprocess, sys, tempfile, os
from datetime import datetime, timezone

VSSH = os.path.expanduser("~/workspace/openfang-fork/.scratch/vssh.sh")
CF_REQ = os.path.expanduser("~/workspace/custom-connectors/custom.cloudflare/bin/cloudflare_req.py")
ACCOUNT = "e3304f1e4edd51e58650c7efcb0c09bc"
PUBLIC = "https://staxcloud.ai"
FROM = "support@staxcloud.ai"  # accepted shape proven 2026-11-04 (probe send)
STALE_CLAIM_MIN = 15


def log(msg):
    print(datetime.now().isoformat(timespec="seconds"), msg, flush=True)


def fetch_api_key():
    cmd = [VSSH, "ssh -o StrictHostKeyChecking=no staxbox@192.168.40.27 "
           "\"sed -n 's/^api_key *= *\\\"\\([^\\\"]*\\)\\\"/\\1/p' ~/.openfang/config.toml | head -1\""]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    key = out.stdout.strip().splitlines()
    if not key or not key[0]:
        raise RuntimeError("could not fetch daemon api_key via ssh chain")
    return key[0].strip()


import urllib.request, urllib.error, urllib.parse


def daemon(key, method, path, body=None):
    r = urllib.request.Request(PUBLIC + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json",
                 "User-Agent": "curl/8.5.0"})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, {}


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


def cf_send(rec, uuid):
    # Shape proven live 2026-11-04: from is a plain address string, to
    # is an array. The provider mints its own Message-ID (the probe's
    # response carried one), so exactly-once rests on this sender's
    # claim/stamp discipline; threading headers ride along when present.
    headers = {}
    if rec.get("in_reply_to"):
        headers["In-Reply-To"] = "<%s>" % rec["in_reply_to"]
    if rec.get("references"):
        headers["References"] = rec["references"]
    body = {
        "from": FROM,
        "to": [rec["to"]],
        "subject": rec["subject"],
        "text": rec["body"],
    }
    if headers:
        body["headers"] = headers
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(body, f)
        path = f.name
    try:
        out = subprocess.run(
            ["python3", CF_REQ, "req", "POST",
             "/accounts/%s/email/sending/send" % ACCOUNT, path],
            capture_output=True, text=True, timeout=120)
        text = out.stdout or ""
        # cloudflare_req exits 0 only on a 2xx; the body carries the
        # provider's own success flag and message id when present.
        ok = out.returncode == 0 and '"success": true' in text
        return ok, text[:600]
    finally:
        os.unlink(path)


def main():
    key = fetch_api_key()
    code, agents = daemon(key, "GET", "/api/agents")
    if code != 200 or not agents:
        log("daemon unreachable or no agents")
        return 1
    seg = agents[0]["id"]

    code, ap_doc = daemon(key, "GET", "/api/approvals")
    ap_list = ap_doc if isinstance(ap_doc, list) else ap_doc.get("approvals", [])
    ap_status = {a.get("id"): a.get("status") for a in ap_list}

    code, doc = daemon(key, "GET", "/api/memory/agents/%s/kv" % seg)
    if code != 200:
        log("kv read failed: %s" % code)
        return 1
    acted = 0
    for p in doc.get("kv_pairs", []):
        k = p.get("key", "")
        if not k.startswith("emailout/"):
            continue
        v = p.get("value")
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except Exception:
                continue
        if not isinstance(v, dict):
            continue
        uuid = k.split("/", 1)[1]
        now = datetime.now(timezone.utc)
        if v.get("status") == "sending":
            claim = v.get("claim_ts", "")
            try:
                age = (now - datetime.fromisoformat(claim)).total_seconds() / 60
            except Exception:
                age = 999
            if age < STALE_CLAIM_MIN:
                continue
            v["status"] = "queued"  # stale claim: reclaim below
        if v.get("status") != "queued":
            continue
        # The send-point check: the approval must read approved NOW.
        if ap_status.get(v.get("approval_id", "")) != "approved":
            v["status"] = "refused"
            v["refused_ts"] = now.isoformat()
            v["refused_reason"] = "no live approval at the send point"
            kv_put(key, seg, k, v)
            log("REFUSED %s — approval %s reads %r" % (
                k, v.get("approval_id", ""), ap_status.get(v.get("approval_id", ""))))
            acted += 1
            continue
        v["status"] = "sending"
        v["claim_ts"] = now.isoformat()
        if not kv_put(key, seg, k, v):
            log("claim failed for %s" % k)
            continue
        ok, detail = cf_send(v, uuid)
        v = kv_get(key, seg, k) or v
        if ok:
            v["status"] = "sent"
            v["sent_ts"] = datetime.now(timezone.utc).isoformat()
            v["provider"] = detail
            log("SENT %s -> %s" % (k, v.get("to")))
        else:
            v["status"] = "failed"
            v["failed_ts"] = datetime.now(timezone.utc).isoformat()
            v["error"] = detail
            log("FAILED %s -> %s : %s" % (k, v.get("to"), detail[:200]))
        kv_put(key, seg, k, v)
        acted += 1
    if not acted:
        log("no queued outbox records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
