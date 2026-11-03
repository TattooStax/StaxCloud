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
                    # Carry the approval id with the outbox record: the
                    # bridge verifies that decision live against the
                    # approvals API before sending, because the outbox
                    # record's own shape is not proof of approval — any
                    # kv writer could forge one.
                    out = {"to": v.get("to", ""), "body": v.get("body", ""), "thread": v.get("thread", ""),
                           "approval_id": v.get("approval_id", ""),
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

# ── Phase 3: crew-liveness tripwire (R13 follow-up, 2026-11-02). At 05:46 CST
# the Forms and Texts agents were killed inside the daemon (stock-ecosystem
# action on this shared playground box); their cron jobs were removed with
# them and the 06:00 brief failed silently. This phase makes that failure
# self-healing: verify the crew agents exist and their standing jobs are
# armed; restore a dead hand via the proven daemon-restart route (hand_state
# restore keeps the same agent ids); re-arm a missing sweep by waking the
# agent; re-create the brief job if it is gone; record any repair at
# crew/health in kv. Silent when everything is healthy. ──
python3 - "$API" "$TOK" <<'PYEOF' >> pull-sync.log 2>&1
import sys, json, urllib.request, urllib.parse, urllib.error, datetime, subprocess, time
api, tok = sys.argv[1], sys.argv[2]
CREW = {"forms": "d2ad79cf-0f4b-5680-9cac-010e47a62b5c", "sms": "aad03c1f-46b0-51f3-ae38-9872cc65881e",
        "stax": "8cad1d3b-58f9-5563-ba0f-966d734c8a1f", "surface-builder": "743f3e25-5327-5848-bb81-6be35685baa4",
        "deep-work": "b7953dc9-8210-5778-b012-50d2f4ee7618", "lead-hand": "f8bbf23d-820b-5f08-b291-313cd88d2ffc",
        "researcher-hand": "52a6d4df-6eb0-5c55-a200-b984514886ab"}
SHARED = "00000000-0000-4000-8000-000000000001"
def now():
    return datetime.datetime.now().isoformat()
def req(method, path, body=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(api + path, data=data, method=method)
    r.add_header("Authorization", "Bearer " + tok)
    if data: r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except Exception:
        return None
def daemon_up():
    try:
        with urllib.request.urlopen(api + "/api/health", timeout=8) as resp:
            return resp.status == 200
    except Exception:
        return False
def restart_daemon():
    subprocess.run(["bash", "-c",
                    "./openfang stop; sleep 2; set -a; . ./env; set +a; "
                    "setsid ./openfang start >> daemon.log 2>&1 &"], timeout=60)
    for _ in range(15):
        time.sleep(4)
        if daemon_up():
            return True
    return daemon_up()

actions = []
missing_agents = []
# Daemon itself down: one start attempt covers the box-reboot case too.
if not daemon_up():
    print(now(), "crew check: daemon DOWN — starting it")
    actions.append("daemon was down; started it")
    if not restart_daemon():
        print(now(), "crew check: daemon still unreachable after start attempt")
        sys.exit(0)
agents = req("GET", "/api/agents") or []
alive = {a.get("name"): a.get("id") for a in agents}
missing_agents = [n for n in CREW if n not in alive]
if missing_agents:
    print(now(), "crew check: MISSING agents:", ", ".join(missing_agents), "— restarting daemon to restore from hand_state")
    actions.append("missing agents: " + ", ".join(missing_agents))
    if restart_daemon():
        agents = req("GET", "/api/agents") or []
        alive = {a.get("name"): a.get("id") for a in agents}
        still = [n for n in CREW if n not in alive]
        if still:
            print(now(), "crew check: STILL missing after restart:", ", ".join(still))
            actions.append("restart did not restore: " + ", ".join(still))
        else:
            actions.append("daemon restart restored the crew")
    else:
        print(now(), "crew check: daemon unreachable after restart")
        actions.append("restart failed to bring the daemon back")
# Standing jobs: a */15 sweep per intake hand + the daily brief workflow job.
jobs_doc = req("GET", "/api/cron/jobs") or {}
jobs = jobs_doc.get("jobs", []) if isinstance(jobs_doc, dict) else []
def has_sweep(agent_name):
    aid = alive.get(agent_name)
    return any(j.get("agent_id") == aid and "*/15" in ((j.get("schedule") or {}).get("expr") or "")
               and j.get("enabled", True) for j in jobs)
missing_jobs = []
if "forms" in alive and not has_sweep("forms"):
    missing_jobs.append("forms sweep")
if "sms" in alive and not has_sweep("sms"):
    missing_jobs.append("texts sweep")
brief_ok = any(j.get("name") == "Morning Brief daily" and j.get("enabled", True) for j in jobs)
if not brief_ok:
    missing_jobs.append("morning brief job")
REARM = {
    "forms": "Your standing sweep job was removed while you were down. Re-arm it now: use schedule_create to register your recurring sweep for new form submissions every 15 minutes, exactly as your playbook prescribes. Confirm the job exists afterwards.",
    "sms": "Your standing sweep job was removed while you were down. Re-arm it now: use schedule_create to register your recurring Texts sweep every 15 minutes, exactly as your playbook prescribes (recall attention/sms and sweep). Confirm the job exists afterwards.",
}
for name in ("forms", "sms"):
    label = "forms sweep" if name == "forms" else "texts sweep"
    if label in missing_jobs and name in alive:
        r = req("POST", f"/api/agents/{alive[name]}/message", {"message": REARM[name]}, timeout=220)
        if r and r.get("response"):
            actions.append(f"re-armed {label} via the agent")
            print(now(), f"crew check: re-armed {label}")
        else:
            actions.append(f"re-arm of {label} got no response")
            print(now(), f"crew check: re-arm of {label} FAILED (no response)")
if "morning brief job" in missing_jobs and "stax" in alive:
    body = {"name": "Morning Brief daily", "agent_id": alive["stax"],
            "schedule": {"kind": "cron", "expr": "0 6 * * *", "tz": "America/Chicago"},
            "action": {"kind": "workflow_run", "workflow_id": "Morning Brief", "timeout_secs": 900},
            "enabled": True}
    r = req("POST", "/api/cron/jobs", body)
    if r and ("job_id" in json.dumps(r)):
        actions.append("re-created the Morning Brief daily job")
        print(now(), "crew check: re-created Morning Brief daily job")
    else:
        actions.append("re-creating the brief job failed")
        print(now(), "crew check: brief job re-create FAILED:", json.dumps(r)[:160])
if actions:
    rec = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "missing_agents": missing_agents, "missing_jobs": missing_jobs,
           "actions": actions, "status": "repaired" if not any("failed" in a or "did not" in a for a in actions) else "repair-incomplete"}
    enc = urllib.parse.quote("crew/health", safe="")
    req("PUT", f"/api/memory/agents/{SHARED}/kv/{enc}", {"value": rec})
    print(now(), "crew check: repair recorded at crew/health —", "; ".join(actions))
PYEOF
