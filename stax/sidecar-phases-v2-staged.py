#!/usr/bin/env python3
# sidecar-phases-v2-staged.py — STAGED, NOT LIVE. Do not place this file
# beside pull-sync.sh and do not invoke it from cron.
#
# This file carries the Phase-2 / scorecard additions to sidecar-phases.py
# (Memory Sweep brief Parts 1–3 + 7.3; Decider Shadow brief Part 6), built
# ahead of activation so the Round A restart window only installs and arms.
# The LIVE sidecar-phases.py (digest phase only) is untouched by this file.
#
# HOW THE MERGE WORKS (activation step, ACTIVATION-RUNBOOK.md step 2):
#   MERGE-1  The helpers below (token / req / as_record / sha_of / kv_put /
#            kv_snapshot) duplicate the live file's on purpose, so this file
#            stands alone until the merge. At merge time keep the LIVE
#            copies and delete the duplicates here.
#   MERGE-2  The four phase functions (memwake_phase, verify_phase,
#            memcarry_phase, scorecard_phase) and their constants move into
#            sidecar-phases.py below digest_phase, unchanged.
#   MERGE-3  main() gains the four dispatch entries; pull-sync.sh gains the
#            invocation lines (before the existing digest line, so the
#            digest's same-cycle counts see this cycle's candidates):
#              python3 sidecar-phases.py memwake  >> pull-sync.log 2>&1 || true
#              python3 sidecar-phases.py verify   >> pull-sync.log 2>&1 || true
#              python3 sidecar-phases.py memcarry >> pull-sync.log 2>&1 || true
#              python3 sidecar-phases.py scorecard >> pull-sync.log 2>&1 || true
#              python3 jev-shadow.py --once       >> pull-sync.log 2>&1 || true
#            (jev-shadow.py's normal mode IS the cycle run; --once is its
#            default path — the flag is accepted for symmetry and ignored.)
#            Order matters: memwake before digest (see the ledger note in
#            memwake_phase), verify before memcarry so a dirty batch is in
#            the same cycle's log before anything is carried.
#   MERGE-4  The tripwire extension is NOT in this file: pull-sync.sh's
#            phase 3 CREW map and job checks gain the decider + memory
#            entries at activation (runbook step 5).
#
# Like the live file: deterministic code only, independently logged phases,
# a phase error is logged and swallowed so it can never break pull-sync.
import sys, os, json, hashlib, urllib.request, urllib.parse, urllib.error, datetime

API = "http://127.0.0.1:4200"
SHARED = "00000000-0000-4000-8000-000000000001"

# memwake rails (Memory Sweep brief Part 6): at most 10 source keys named
# per wake; the ledger makes deferral lossless.
WAKE_CAP = 10
# Scorecard constants (Decider Shadow brief Parts 6–7).
BOOKING_LINK = "https://squareup.com/appointments/book/L7VAHB1TPFGN2/start"
SETTLE_HOURS = 24
JEV_LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "jev-ledger.jsonl")
JEV_LIST_PRICE_IN_PER_M = 0.042
INFERENCE_RULE = (
    "Scope ground truth is inferred from behavior: drafted or answered by "
    "the owner => treated as business; left alone past a 24 h settle "
    "window => treated as personal/unsuitable. A left-alone business "
    "thread the sweep simply missed scores as a disagreement — the useful "
    "direction for the error to fall, since those keys are exactly the "
    "ones a human should eyeball.")


# ── MERGE-1: shared helpers (duplicates of the live file's; keep live) ────

def token():
    # Same source pull-sync uses: the api_key line of ~/.openfang/config.toml.
    with open(os.path.expanduser("~/.openfang/config.toml")) as f:
        for line in f:
            if line.strip().startswith("api_key"):
                return line.split('"')[1]
    raise RuntimeError("api_key not found in config.toml")


def req(tok, method, path, body=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(API + path, data=data, method=method)
    r.add_header("Authorization", "Bearer " + tok)
    if data:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def as_record(v):
    """kv values arrive as dicts or JSON strings; return the dict or None."""
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return None
    return v if isinstance(v, dict) else None


def sha_of(v):
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            pass
    blob = v if isinstance(v, str) else json.dumps(
        v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def kv_snapshot(tok):
    kv = req(tok, "GET", f"/api/memory/agents/{SHARED}/kv")
    pairs = kv.get("kv_pairs", []) if isinstance(kv, dict) else []
    return {p.get("key", ""): p.get("value") for p in pairs}


def kv_put(tok, key, value):
    enc = urllib.parse.quote(key, safe="")
    req(tok, "PUT", f"/api/memory/agents/{SHARED}/kv/{enc}", {"value": value})


def now_local():
    return datetime.datetime.now().astimezone()


def agent_id(tok, name):
    agents = req(tok, "GET", "/api/agents")
    if isinstance(agents, dict):
        agents = agents.get("agents", [])
    return next((a.get("id") for a in agents if a.get("name") == name), None)


def approvals_map(tok):
    approvals = req(tok, "GET", "/api/approvals")
    ap_list = approvals if isinstance(approvals, list) else approvals.get("approvals", [])
    return {a.get("id"): a.get("status") for a in ap_list}, ap_list


def parse_ts(s):
    if not s or not isinstance(s, str):
        return None
    try:
        d = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)
    return d


# ── MERGE-2a: memwake — enumeration + wake (Memory Sweep Part 1) ──────────
#
# Ledger note (why TWO ledgers exist): memsweep/state belongs to the digest
# — it answers "when did we first see this key" and refreshes every key's
# sha every cycle by design. Extraction needs the opposite discipline —
# "update the hash only for keys named in a wake" — so a changed record the
# wake cap defers is still changed next cycle instead of being silently
# absorbed. memwake/state is that ledger; do not unify them. There is
# deliberately NO baseline seed here (the digest's seeding was digest-only):
# the first live run is the brief's Part 7 gate run, which must process the
# thread records already on the box; the 10-key cap drains any backlog over
# the first hours and the ledger makes the drain exact.

def qualifying_keys(snapshot):
    """Conversation records the sweep may process: sms/<digits> threads and
    formsub/<slug>/<uuid> submissions already marked processed. The shape
    tests are what keep the family's debris keys (a bare formsub/ key,
    formsub/status, unslugged copies) out of the work list."""
    out = {}
    for key, raw in snapshot.items():
        rec = as_record(raw)
        if rec is None:
            continue
        if key.startswith("sms/") and key.count("/") == 1:
            out[key] = raw
        elif (key.startswith("formsub/") and key.count("/") >= 2
              and rec.get("processed") is True):
            out[key] = raw
    return out


def memwake_phase(tok):
    now = now_local()
    stamp = now.isoformat(timespec="seconds")
    snapshot = kv_snapshot(tok)
    state = as_record(snapshot.get("memwake/state")) or {}
    entries = state.get("entries") if isinstance(state.get("entries"), dict) else {}
    work = []
    for key, raw in qualifying_keys(snapshot).items():
        sha = sha_of(raw)
        prev = entries.get(key)
        if not prev or prev.get("sha") != sha:
            work.append((key, sha))
    work.sort()
    named = work[:WAKE_CAP]
    if not named:
        print(stamp, "memwake: no changed conversation records")
        return
    mem_id = agent_id(tok, "memory")
    if not mem_id:
        # Ledger untouched on purpose: the same diff is retried next cycle.
        print(stamp, "memwake: memory agent not found — ledger untouched, will retry")
        return
    keys = ", ".join(k for k, _ in named)
    msg = ("New or changed conversation records are waiting at these exact "
           f"keys: {keys}. Recall each key exactly and extract per your "
           "playbook (candidates only — quote or nothing). Keys not named "
           "here are not yours to process.")
    r = req(tok, "POST", f"/api/agents/{mem_id}/message",
            {"message": msg}, timeout=220)
    if not (isinstance(r, dict) and r.get("response")):
        print(stamp, "memwake: wake got no response — ledger untouched, will retry")
        return
    for k, sha in named:
        entries[k] = {"sha": sha, "named_ts": stamp}
    kv_put(tok, "memwake/state",
           {"version": 1, "updated": stamp, "entries": entries})
    print(stamp, f"memwake: woke memory over {len(named)} key(s); "
                 f"{len(work) - len(named)} deferred")


# ── MERGE-2b: verify — the fabrication grep (Memory Sweep Part 7.3) ───────

def string_leaves(v, out):
    if isinstance(v, str):
        out.append(v)
    elif isinstance(v, dict):
        for x in v.values():
            string_leaves(x, out)
    elif isinstance(v, list):
        for x in v:
            string_leaves(x, out)


def verify_phase(tok):
    """Mechanical, 100%: every memcand quote must appear verbatim in its
    source record. The haystacks are the source's raw stored string (when
    it is one), its canonical JSON, and every string leaf it holds — the
    quote must match the record's actual text, not an artifact of JSON
    escaping. One miss fails the run: the caller files a Ratchet case and
    no candidate from the batch is carried until a re-run is clean.
    Also reports (warning only) keys that differ from their content hash —
    the hand derives hash16 by reasoning, so the deterministic side owns
    checking its work."""
    stamp = now_local().isoformat(timespec="seconds")
    snapshot = kv_snapshot(tok)
    fails, warns, checked = [], [], 0
    for key in sorted(snapshot):
        if not key.startswith("memcand/"):
            continue
        rec = as_record(snapshot[key])
        if rec is None:
            fails.append((key, "candidate is not a record"))
            continue
        quote, src_key = rec.get("quote"), rec.get("source_key")
        if not quote or not src_key:
            fails.append((key, "missing quote or source_key"))
            continue
        src_raw = snapshot.get(src_key)
        if src_raw is None:
            fails.append((key, f"source {src_key} not in store"))
            continue
        hay = []
        if isinstance(src_raw, str):
            hay.append(src_raw)
        src = as_record(src_raw)
        if src is not None:
            hay.append(json.dumps(src, ensure_ascii=False))
            string_leaves(src, hay)
        checked += 1
        if not any(quote in h for h in hay):
            fails.append((key, "quote not verbatim in source"))
        expect = hashlib.sha256((src_key + quote).encode("utf-8")).hexdigest()[:16]
        if key != "memcand/" + expect:
            warns.append((key, "key != content hash " + expect))
    for k, why in fails:
        print(stamp, "verify FAIL:", k, "—", why)
    for k, why in warns:
        print(stamp, "verify warn:", k, "—", why)
    print(stamp, f"verify: {checked} candidate(s) checked, "
                 f"{len(fails)} failed, {len(warns)} key warnings")
    return len(fails)


# ── MERGE-2c: memcarry — candidates to Needs you (Memory Sweep Part 3) ────
#
# Mirrors the drafts phase's discipline exactly: approval-id stamping,
# decided closure in kv as the ledger of record, expired approvals
# re-carried, decided records never re-carried. The two acts no hand can
# perform live here: the DELETE on rejection (hands hold no delete) and
# the promotion wake (the hand promotes; the carrier only tells it to).

def source_plain(rec, snapshot):
    sk = rec.get("source_key", "")
    if sk.startswith("sms/"):
        digits = sk.split("/", 1)[1]
        thread = as_record(snapshot.get(sk)) or {}
        contact = as_record(snapshot.get("contact/" + digits)) or {}
        name = contact.get("name") or thread.get("name")
        return f"a text conversation with {name}" if name else "a text conversation"
    if sk.startswith("formsub/"):
        parts = sk.split("/")
        slug = parts[1] if len(parts) > 1 else "web"
        return f"their {slug} form submission"
    return "a conversation record"


def contact_name_for(rec, snapshot):
    ck = rec.get("contact_key", "")
    contact = as_record(snapshot.get(ck)) if ck else None
    if contact and contact.get("name"):
        return contact["name"]
    sk = rec.get("source_key", "")
    if sk.startswith("sms/"):
        thread = as_record(snapshot.get(sk)) or {}
        if thread.get("name"):
            return thread["name"]
    return "this customer"


def delete_candidate(tok, key):
    """DELETE the candidate and read back GET: gone (404 / null value) is
    the only success. Returns True only on a verified absence."""
    enc = urllib.parse.quote(key, safe="")
    path = f"/api/memory/agents/{SHARED}/kv/{enc}"
    req(tok, "DELETE", path)
    try:
        after = req(tok, "GET", path)
        return not (isinstance(after, dict) and after.get("value") is not None)
    except urllib.error.HTTPError as e:
        return e.code == 404


def memcarry_phase(tok):
    stamp = now_local().isoformat(timespec="seconds")
    snapshot = kv_snapshot(tok)
    ap_status, _ = approvals_map(tok)
    mem_id = agent_id(tok, "memory")
    if not mem_id:
        print(stamp, "memcarry: memory agent not found — nothing carried")
        return
    carried = deleted = woken = 0
    for key in sorted(snapshot):
        if not key.startswith("memcand/"):
            continue
        rec = as_record(snapshot[key])
        if rec is None:
            continue
        if rec.get("status") == "promoted":
            continue  # decided closure: a promoted candidate is final
        linked = ap_status.get(rec.get("approval_id", ""))
        if linked == "rejected":
            if delete_candidate(tok, key):
                deleted += 1
                print(stamp, "memcarry: rejected candidate deleted + verified:", key)
            else:
                print(stamp, "memcarry: DELETE read-back STILL PRESENT:", key)
            continue
        if linked == "approved":
            if rec.get("promote_woken"):
                continue  # woken once; the hand's promotion closes it
            msg = ("The owner approved the memory candidate at this exact "
                   f"key: {key}. Promote it per your playbook — recall the "
                   "candidate, append the one notes[] entry to its contact, "
                   "mark it promoted. No other key is yours in this wake.")
            r = req(tok, "POST", f"/api/agents/{mem_id}/message",
                    {"message": msg}, timeout=220)
            if isinstance(r, dict) and r.get("response"):
                rec["promote_woken"] = True
                rec["promote_wake_ts"] = stamp
                kv_put(tok, key, rec)
                woken += 1
                print(stamp, "memcarry: promotion wake sent for", key)
            else:
                print(stamp, "memcarry: promotion wake got no response:", key)
            continue
        if linked == "pending":
            if rec.get("status") == "candidate":
                rec["status"] = "in-needs-you"
                kv_put(tok, key, rec)
            continue
        # No live link — a fresh candidate, or an approval that expired
        # undecided (the 300 s TTL): (re-)carry it, like the drafts phase.
        if rec.get("status") not in ("candidate", "in-needs-you"):
            continue
        desc = (f"{rec.get('field', 'fact')}: {rec.get('value', '')} — "
                f"from {source_plain(rec, snapshot)}")
        ap = req(tok, "POST", "/api/approvals",
                 {"agent_id": mem_id, "tool_name": "memory_candidate",
                  "description": desc,
                  "action_summary": "Remember this about "
                                    + contact_name_for(rec, snapshot)})
        rec["status"] = "in-needs-you"
        rec["approval_id"] = ap.get("id", "")
        kv_put(tok, key, rec)
        carried += 1
        print(stamp, "memcarry: candidate carried to Needs you:", key,
              "approval:", rec["approval_id"])
    print(stamp, f"memcarry: {carried} carried, {woken} promotion wakes, "
                 f"{deleted} rejected+deleted")


# ── MERGE-2d: scorecard — the three-way grading (Decider Shadow Part 6) ───

def latest_boundary(now):
    """The weekly boundary: the most recent Sunday 18:00 local at or
    before now. The scorecard's record is keyed by the boundary's date,
    which makes the phase idempotent — a boundary already scored is
    skipped, however many cycles run after it."""
    d = now.date() - datetime.timedelta(days=(now.date().weekday() + 1) % 7)
    boundary = datetime.datetime(d.year, d.month, d.day, 18, 0,
                                 tzinfo=now.tzinfo)
    if now < boundary:
        boundary -= datetime.timedelta(days=7)
    return boundary


def bucket(conf):
    if conf >= 0.9:
        return ">=0.9"
    if conf >= 0.7:
        return "0.7-0.9"
    return "<0.7"


def percentile(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    k = max(0, min(len(s) - 1, int(round(p * (len(s) - 1)))))
    return round(s[k], 2)


def observed_behavior(snapshot, ap_status, thread_key, inbound_id, now):
    """The sweep's behavior for one inbound, derived from records only:
    a draft at the deterministic key => drafted (its body settles the link
    question; an outbox record or a live approval settles the outcome);
    no draft but a later outbound in the thread => the owner answered it
    himself (drafted-equivalent for scope/action, excluded for link);
    nothing after a 24 h settle => left alone; anything younger is
    unsettled and excluded; no thread/inbound at all => unseen (the shadow
    decided something the sweep never saw — excluded, and counted)."""
    digits = thread_key.split("/", 1)[1] if "/" in thread_key else ""
    draft_key = f"draft/sms-{digits}-{inbound_id}"
    draft = as_record(snapshot.get(draft_key))
    thread = as_record(snapshot.get(thread_key))
    inbound_ts = None
    if thread:
        for m in thread.get("messages", []):
            if isinstance(m, dict) and m.get("id") == inbound_id:
                inbound_ts = parse_ts(m.get("ts"))
    if thread is None or inbound_ts is None:
        return {"kind": "unseen", "inbound_ts": inbound_ts}
    if draft is not None:
        body = draft.get("body") or draft.get("text") or ""
        outcome = "unverified"
        if (snapshot.get(f"smsout/sms-{digits}-{inbound_id}") is not None
                or ap_status.get(draft.get("approval_id", "")) == "approved"):
            outcome = "approved"
        elif ap_status.get(draft.get("approval_id", "")) == "rejected":
            outcome = "rejected"
        return {"kind": "drafted",
                "scope": "business", "action": "draft_reply",
                "link": "link" if BOOKING_LINK in body else "no_link",
                "outcome": outcome, "against": draft_key,
                "inbound_ts": inbound_ts}
    msgs = [m for m in thread.get("messages", []) if isinstance(m, dict)]
    if any(m.get("dir") == "out"
           and (parse_ts(m.get("ts")) or inbound_ts) > inbound_ts
           for m in msgs):
        return {"kind": "owner_answered", "scope": "business",
                "action": "draft_reply", "link": None, "outcome": None,
                "against": thread_key, "inbound_ts": inbound_ts}
    if now - inbound_ts > datetime.timedelta(hours=SETTLE_HOURS):
        return {"kind": "left_alone", "scope": "personal",
                "action": "hold_flag", "link": None, "outcome": None,
                "against": thread_key, "inbound_ts": inbound_ts}
    return {"kind": "unsettled", "inbound_ts": inbound_ts}


def fetch_usage(tok, window_start, window_end):
    """Best-effort pull of the daemon's usage records for per-decision
    cost. Usage shapes vary by build; anything unparseable yields {} and
    the scorecard reports cost as unavailable rather than inventing it.
    The activation staging run pins the live shape (runbook step 6)."""
    try:
        doc = req(tok, "GET", "/api/usage")
    except Exception:
        return {}
    rows = doc if isinstance(doc, list) else (
        doc.get("usage", []) if isinstance(doc, dict) else [])
    totals = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        ts = parse_ts(row.get("ts") or row.get("timestamp") or "")
        if ts and not (window_start <= ts <= window_end):
            continue
        name = row.get("agent_name") or row.get("agent") or ""
        cost = row.get("cost_usd", row.get("total_cost", row.get("cost")))
        if name and isinstance(cost, (int, float)):
            totals[name] = totals.get(name, 0.0) + float(cost)
    return totals


def grade_contestant(records, observed, contestant):
    """Grade one contestant's records against observed behavior + verified
    outcomes. Outcome grading exists only where a draft's fate is verified:
    approved => the incumbent's observed choices were right; rejected =>
    they were wrong, so agreeing with the OUTCOME means NOT matching the
    incumbent on scope/action. Link outcomes grade on approved drafts
    only — a rejected draft's link was never sent, so its correctness is
    unknowable and excluded rather than guessed."""
    stats = {}
    disagreements, dangerous, latencies = [], [], []
    scored = excluded = unsettled = 0
    for join, (key, rec) in records.items():
        obs = observed.get(join)
        if obs is None or obs["kind"] == "unseen":
            excluded += 1
            continue
        if obs["kind"] == "unsettled":
            unsettled += 1
            continue
        scored += 1
        dec = rec.get("decisions", {}) if isinstance(rec.get("decisions"), dict) else {}
        rts = parse_ts(rec.get("ts"))
        if rts and obs.get("inbound_ts"):
            latencies.append((rts - obs["inbound_ts"]).total_seconds())
        for dtype in ("scope", "action", "link"):
            obs_choice = obs.get(dtype)
            if obs_choice is None:
                continue
            mine = dec.get(dtype, {}) if isinstance(dec.get(dtype), dict) else {}
            choice, conf = mine.get("choice"), float(mine.get("confidence", 0) or 0)
            s = stats.setdefault(dtype, {
                "n": 0, "behavior_agree": 0,
                "buckets": {"<0.7": {"n": 0, "agree": 0},
                            "0.7-0.9": {"n": 0, "agree": 0},
                            ">=0.9": {"n": 0, "agree": 0}},
                "outcome_n": 0, "outcome_agree": 0})
            s["n"] += 1
            agree = choice == obs_choice
            s["behavior_agree"] += 1 if agree else 0
            b = s["buckets"][bucket(conf)]
            b["n"] += 1
            b["agree"] += 1 if agree else 0
            if not agree:
                disagreements.append({
                    "contestant": contestant, "decide_key": key,
                    "against": obs.get("against", ""), "type": dtype,
                    "chose": choice, "observed": obs_choice})
            if obs.get("outcome") in ("approved", "rejected"):
                if dtype == "link" and obs["outcome"] == "rejected":
                    pass  # unknowable — excluded, per the note above
                else:
                    s["outcome_n"] += 1
                    if obs["outcome"] == "approved":
                        s["outcome_agree"] += 1 if agree else 0
                    else:
                        s["outcome_agree"] += 0 if agree else 1
        act = dec.get("action", {}) if isinstance(dec.get("action"), dict) else {}
        if (obs["kind"] == "left_alone"
                and act.get("choice") == "draft_reply"
                and float(act.get("confidence", 0) or 0) >= 0.9):
            dangerous.append({"contestant": contestant, "decide_key": key,
                              "thread": join[0],
                              "note": "draft_reply at >=0.9 where the sweep "
                                      "left a personal thread alone"})
    for s in stats.values():
        s["behavior_rate"] = (round(s["behavior_agree"] / s["n"], 4)
                              if s["n"] else None)
        s["outcome_rate"] = (round(s["outcome_agree"] / s["outcome_n"], 4)
                             if s["outcome_n"] else None)
    return {"decisions": stats, "scored": scored, "excluded_unseen": excluded,
            "excluded_unsettled": unsettled, "disagreements": disagreements,
            "dangerous": dangerous,
            "latency_secs": {"median": percentile(latencies, 0.5),
                             "p95": percentile(latencies, 0.95),
                             "basis": "decide record ts minus inbound ts "
                                      "(cadence-bound, not model latency)"}}


def jev_cost(window_start, window_end, jev_records):
    """Jev's cost from its own ledger lines, computed from list price —
    flagged as such in the record, never presented as metered."""
    tokens = 0
    seen = set()
    try:
        with open(JEV_LEDGER) as f:
            lines = f.readlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            e = json.loads(line)
        except Exception:
            continue
        ts = parse_ts(e.get("ts"))
        if ts and window_start <= ts <= window_end:
            tokens += int(e.get("tokens_in", 0) or 0)
            seen.add(e.get("key"))
    n = len(jev_records)
    total = tokens * JEV_LIST_PRICE_IN_PER_M / 1e6
    return {"tokens_in": tokens, "cost_total_usd": round(total, 6),
            "cost_per_decision_usd": round(total / n, 6) if n else None,
            "cost_basis": "computed_from_list",
            "ledger_keys_in_window": len(seen)}


def scorecard_phase(tok):
    now = now_local()
    stamp = now.isoformat(timespec="seconds")
    boundary = latest_boundary(now)
    window_end = boundary
    window_start = boundary - datetime.timedelta(days=7)
    out_key = f"decide/scorecard-{boundary.date().isoformat()}"
    snapshot = kv_snapshot(tok)
    if out_key in snapshot:
        print(stamp, "scorecard: boundary already scored:", out_key)
        return
    native, jev = {}, {}
    for key in sorted(snapshot):
        rec = as_record(snapshot[key])
        if rec is None:
            continue
        if key.startswith("decide/jev-sms-"):
            fam = jev
        elif key.startswith("decide/sms-"):
            fam = native
        else:
            continue
        ts = parse_ts(rec.get("ts"))
        if ts and window_start <= ts <= window_end:
            fam[(rec.get("thread", ""), rec.get("inbound_id", ""))] = (key, rec)
    ap_status, _ = approvals_map(tok)
    observed = {}
    for join in set(native) | set(jev):
        observed[join] = observed_behavior(
            snapshot, ap_status, join[0], join[1], now)
    all_joins = set(native) | set(jev)
    parity = {}
    for name, fam in (("native", native), ("jev", jev)):
        parity[name] = (round(len(fam) / len(all_joins), 4)
                        if all_joins else None)
    incomplete = [n for n, p in parity.items() if p is not None and p < 0.95]
    usage = fetch_usage(tok, window_start, window_end)

    def contestant_block(fam, graded, cost):
        return {"records": len(fam), "scored": graded["scored"],
                "excluded_unseen": graded["excluded_unseen"],
                "excluded_unsettled": graded["excluded_unsettled"],
                "decisions": graded["decisions"],
                "latency_secs": graded["latency_secs"], "cost": cost}

    native_graded = grade_contestant(native, observed, "native")
    jev_graded = grade_contestant(jev, observed, "jev")
    native_cost = None
    if usage.get("decider") is not None and native_graded["scored"]:
        native_cost = {"cost_total_usd": round(usage["decider"], 6),
                       "cost_per_decision_usd": round(
                           usage["decider"] / native_graded["scored"], 6),
                       "cost_basis": "daemon_usage_records"}
    incumbent_kinds = {}
    incumbent_outcomes = {"approved": 0, "rejected": 0, "unverified": 0}
    for obs in observed.values():
        incumbent_kinds[obs["kind"]] = incumbent_kinds.get(obs["kind"], 0) + 1
        if obs["kind"] == "drafted":
            incumbent_outcomes[obs["outcome"]] += 1
    incumbent_cost = None
    if usage.get("sms") is not None and incumbent_kinds.get("drafted"):
        incumbent_cost = {"cost_total_usd": round(usage["sms"], 6),
                          "cost_per_scored_decision_usd": round(
                              usage["sms"] / incumbent_kinds["drafted"], 6),
                          "cost_basis": "daemon_usage_records"}
    record = {
        "window": {"start": window_start.isoformat(timespec="seconds"),
                   "end": window_end.isoformat(timespec="seconds")},
        "generated": stamp,
        "inference_rule": INFERENCE_RULE,
        "coverage": {
            "distinct_inbounds": len(all_joins),
            "parity": parity,
            "incompletely_measured": incomplete,
            "only_native": [],  # filled by decide key just below
            "only_jev": [],
        },
        "incumbent": {"behavior": incumbent_kinds,
                      "outcomes": incumbent_outcomes,
                      "cost": incumbent_cost},
        "native": contestant_block(native, native_graded, native_cost),
        "jev": contestant_block(
            jev, jev_graded, jev_cost(window_start, window_end, jev)),
        "disagreements": (native_graded["disagreements"]
                          + jev_graded["disagreements"]),
        "dangerous": native_graded["dangerous"] + jev_graded["dangerous"],
    }
    # One-sided coverage, rendered as the decide keys a reader would open.
    record["coverage"]["only_native"] = sorted(
        native[j][0] for j in set(native) - set(jev))
    record["coverage"]["only_jev"] = sorted(
        jev[j][0] for j in set(jev) - set(native))
    kv_put(tok, out_key, record)
    print(stamp, f"scorecard: wrote {out_key} — "
                 f"native {len(native)} / jev {len(jev)} records, "
                 f"{len(record['disagreements'])} disagreements, "
                 f"{len(record['dangerous'])} dangerous")


# ── MERGE-3: dispatch (the live main() gains these four entries) ──────────

def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        tok = token()
        if phase == "memwake":
            memwake_phase(tok)
        elif phase == "verify":
            verify_phase(tok)
        elif phase == "memcarry":
            memcarry_phase(tok)
        elif phase == "scorecard":
            scorecard_phase(tok)
        else:
            print(now_local().isoformat(timespec="seconds"),
                  "sidecar-phases-v2: unknown phase", phase)
    except Exception as e:
        # Never break pull-sync: log and exit clean; the next cycle retries.
        print(now_local().isoformat(timespec="seconds"),
              "sidecar-phases-v2", phase, "FAILED:", repr(e)[:200])
    sys.exit(0)


if __name__ == "__main__":
    main()
