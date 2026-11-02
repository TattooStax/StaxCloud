#!/bin/bash
# pull-sync.sh — pull-on-wake sync beside the OpenFang daemon (R7).
# Polls the fang-forms Worker for un-acked submissions, writes each into the
# daemon's kv store under formsub/<form>/<uuid> (idempotent — re-delivery
# overwrites the same key), then acks it in Cloudflare KV.
# Runs from ~/openfang-play; state in pull-sync.log.
cd "$(dirname "$0")" || exit 1
PULL_URL="https://fang-forms.tattoostax.workers.dev"
SECRET="$(cat pull-secret)"
API="http://127.0.0.1:4200"
TOK="$(grep '^api_key ' ~/.openfang/config.toml | head -1 | cut -d'"' -f2)"
AGENT="$(curl -s "$API/api/agents" -H "Authorization: Bearer $TOK" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])" 2>/dev/null)"
[ -z "$AGENT" ] && { echo "$(date -Is) no agent id — daemon up?" >> pull-sync.log; exit 0; }

curl -s "$PULL_URL/api/pull" -H "X-Pull-Secret: $SECRET" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for s in d.get('submissions', []):
    print(s['uuid'])
" | while read -r UUID; do
  [ -z "$UUID" ] && continue
  REC="$(curl -s "$PULL_URL/api/pull" -H "X-Pull-Secret: $SECRET" | python3 -c "
import sys, json
want = '$UUID'
for s in json.load(sys.stdin).get('submissions', []):
    if s['uuid'] == want:
        print(json.dumps({'form': s['form'], 'uuid': s['uuid'], 'ts': s['ts'], 'source': 'web', 'data': s['data']}))
        break
")"
  [ -z "$REC" ] && continue
  FORM="$(echo "$REC" | python3 -c "import sys,json; print(json.load(sys.stdin)['form'])")"
  KEY="formsub/$FORM/$UUID"
  ENCKEY="$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$KEY")"
  # Skip-if-exists: a re-delivered record must never overwrite the stored one
  # (which may already carry processed/contact/draft fields). Still ack it.
  EXIST="$(curl -s "$API/api/memory/agents/$AGENT/kv/$ENCKEY" -H "Authorization: Bearer $TOK" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if d.get('value') is not None else 'no')" 2>/dev/null)"
  if [ "$EXIST" = "yes" ]; then
    curl -s -X POST "$PULL_URL/api/ack" -H "X-Pull-Secret: $SECRET" -H "Content-Type: application/json" -d "{\"uuid\": \"$UUID\"}" > /dev/null
    echo "$(date -Is) already stored $KEY — skipped overwrite, acked" >> pull-sync.log
    continue
  fi
  CODE="$(curl -s -o /dev/null -w '%{http_code}' -X PUT "$API/api/memory/agents/$AGENT/kv/$ENCKEY" -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" -d "{\"value\": $REC}")"
  if [ "$CODE" = "200" ]; then
    curl -s -X POST "$PULL_URL/api/ack" -H "X-Pull-Secret: $SECRET" -H "Content-Type: application/json" -d "{\"uuid\": \"$UUID\"}" > /dev/null
    echo "$(date -Is) pulled $KEY" >> pull-sync.log
    echo "$KEY" >> /tmp/pull-sync-new.$$
  else
    echo "$(date -Is) FAILED kv put $KEY (http $CODE) — will retry next cycle" >> pull-sync.log
  fi
done

# Wake the Forms agent when (and only when) this cycle stored NEW submissions,
# so intake is unattended end to end: pull -> agent processes -> drafts phase
# below carries the held draft on the next cycle.
if [ -s /tmp/pull-sync-new.$$ ]; then
  NEWKEYS="$(paste -sd', ' /tmp/pull-sync-new.$$)"
  FORMS_ID="$(curl -s "$API/api/agents" -H "Authorization: Bearer $TOK" | python3 -c "import sys,json; print(next((a['id'] for a in json.load(sys.stdin) if a.get('name')=='forms'), ''))" 2>/dev/null)"
  if [ -n "$FORMS_ID" ]; then
    curl -s -X POST "$API/api/agents/$FORMS_ID/message" -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" -d "{\"message\": \"New form submission(s) just landed in shared memory at these exact keys: $NEWKEYS. Recall each key exactly and process it per your playbook (resolve the contact, hold the reply draft, mark it processed).\"}" > /dev/null
    echo "$(date -Is) woke forms agent for: $NEWKEYS" >> pull-sync.log
  fi
fi
rm -f /tmp/pull-sync-new.$$

# ── Drafts phase: carry held reply drafts (draft/<uuid> in kv, written by the
# Forms agent) into Needs you as real approval requests. ──
python3 - "$API" "$TOK" <<'PYEOF' >> pull-sync.log 2>&1
import sys, json, urllib.request, urllib.parse, datetime
api, tok = sys.argv[1], sys.argv[2]
def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(api + path, data=data, method=method)
    r.add_header("Authorization", "Bearer " + tok)
    if data: r.add_header("Content-Type", "application/json")
    return json.load(urllib.request.urlopen(r, timeout=20))
agents = req("GET", "/api/agents")
forms_id = next((a["id"] for a in agents if a.get("name") == "forms"), None)
if not forms_id:
    print(datetime.datetime.now().isoformat(), "drafts: no forms agent found")
    sys.exit(0)
kv = req("GET", f"/api/memory/agents/{forms_id}/kv")
approvals = req("GET", "/api/approvals")
ap_list = approvals if isinstance(approvals, list) else approvals.get("approvals", [])
ap_status = {a.get("id"): a.get("status") for a in ap_list}
for pair in kv.get("kv_pairs", []):
    key = pair.get("key", "")
    if not key.startswith("draft/"):
        continue
    v = pair.get("value")
    if isinstance(v, str):
        try: v = json.loads(v)
        except Exception: continue
    if not isinstance(v, dict):
        continue
    # Lenient by design: the agent composes prose, this code enforces structure.
    # A draft with text and no LIVE approval is a held draft, whatever its flags
    # say. Fang approvals expire (policy timeout, max 300s) — an expired link
    # means the draft is still waiting, so it is carried again. An approved or
    # rejected link closes the draft for good.
    body_text = v.get("text") or v.get("body")
    if not body_text:
        continue
    # TERMINAL: a decided draft is final, whatever the approvals API says.
    # Approvals are in-memory; if a decision is ever lost from the API
    # (restart / recent-list eviction) before this sync sees it, the durable
    # kv record is the ledger of record — never re-carry, never re-apply.
    if v.get("status") == "decided":
        continue
    linked = ap_status.get(v.get("approval_id", ""))
    if linked in ("approved", "rejected"):
        if v.get("status") != "decided":
            if linked == "approved" and v.get("kind") == "sms_reply":
                enc_o = urllib.parse.quote("smsout/" + key.split("/", 1)[1], safe="")
                try:
                    existing_out = req("GET", f"/api/memory/agents/{forms_id}/kv/{enc_o}")
                except Exception:
                    existing_out = {}
                if isinstance(existing_out, dict) and existing_out.get("value") is not None:
                    print(datetime.datetime.now().isoformat(), "sms outbox already exists, not rewritten:", key)
                else:
                    out = {"to": v.get("to", ""), "body": v.get("body", ""), "thread": v.get("thread", ""),
                           "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(), "status": "queued"}
                    req("PUT", f"/api/memory/agents/{forms_id}/kv/{enc_o}", {"value": out})
                    print(datetime.datetime.now().isoformat(), "sms reply approved -> outbox:", key)
            v["status"] = "decided"
            enc = urllib.parse.quote(key, safe="")
            req("PUT", f"/api/memory/agents/{forms_id}/kv/{enc}", {"value": v})
            print(datetime.datetime.now().isoformat(), "draft decided, closed:", key)
        continue
    if v.get("approval_id") and linked == "pending":
        continue
    uuid = key.split("/", 1)[1]
    sub = next((p.get("value") for p in kv.get("kv_pairs", []) if p.get("key", "").startswith("formsub/") and p.get("key", "").endswith("/" + uuid)), {})
    if isinstance(sub, str):
        try: sub = json.loads(sub)
        except Exception: sub = {}
    to_name = v.get("to_name") or (sub.get("data", {}) or {}).get("name", "")
    form = v.get("form") or sub.get("form", "")
    if v.get("kind") == "sms_reply":
        desc = f"Text reply to {v.get('to_name') or v.get('to','')} ({v.get('to','')}): {body_text}"
        tool = "sms_reply"
    else:
        desc = f"Draft reply to {to_name} ({form}): {body_text}"
        tool = "reply_draft"
    ap = req("POST", "/api/approvals", {"agent_id": forms_id, "tool_name": tool,
                                        "description": desc, "action_summary": "Reply draft held for your call"})
    v["status"] = "in-needs-you"
    v["approval_id"] = ap.get("id", "")
    enc = urllib.parse.quote(key, safe="")
    req("PUT", f"/api/memory/agents/{forms_id}/kv/{enc}", {"value": v})
    print(datetime.datetime.now().isoformat(), "draft carried to Needs you:", key, "approval:", v["approval_id"])
PYEOF
